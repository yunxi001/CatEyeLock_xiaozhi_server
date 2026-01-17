# App 协议 v2.2 代码修改计划

## 一、修改概述

根据 `智能猫眼门锁系统-App通信协议规范-v2.2.md`，需要对服务器代码进行以下修改：

| 序号 | 功能模块 | 优先级 | 工作量 | 状态 |
|------|----------|--------|--------|------|
| 1 | 移除 forward 转发机制 | 高 | 小 | ✅ 已完成 |
| 2 | 新增 app_id 支持 | 高 | 小 | ✅ 已完成 |
| 3 | 新增服务器 ACK 机制 (server_ack) | 高 | 中 | ✅ 已完成 |
| 4 | 新增设备上下线通知 | 高 | 中 | ✅ 已完成 |
| 5 | 到访通知推送人脸图片 | 中 | 小 | ✅ 已完成 |
| 6 | 新增数据查询 Handler | 中 | 中 | ✅ 已完成 |
| 7 | 新增媒体下载 Handler | 中 | 中 | ✅ 已完成 |
| 8 | 命令代理（记录日志后转发） | 中 | 中 | ✅ 已完成 |

**完成日期**: 2024-12-11

---

## 二、详细修改计划

### 2.1 移除 forward 转发机制

**文件**: `main/xiaozhi-server/core/app_connection.py`

**当前实现**:
```python
async def _handle_text_message(self, message: str):
    msg_json = json.loads(message)
    if msg_json.get("forward") == True:
        await self._forward_to_esp32(msg_json)
    else:
        await handleTextMessage(self, message)
```

**修改方案**:
- 删除 `forward` 字段检查逻辑
- 删除 `_forward_to_esp32` 方法
- 所有消息统一走 Handler 处理
- 需要转发的命令（lock_control, dev_control, user_mgmt）由对应 Handler 处理

---

### 2.2 新增 app_id 支持

**文件**: `main/xiaozhi-server/core/app_connection.py`

**修改内容**:
1. 在 `_authenticate` 方法中提取并保存 `app_id`
2. 新增 `self.app_id` 属性

```python
class AppConnectionHandler:
    def __init__(self, config):
        # ... 现有代码 ...
        self.app_id = None  # 新增

    async def _authenticate(self, message: str) -> bool:
        # ... 现有验证逻辑 ...
        self.app_id = msg_json.get("app_id")  # 新增
        if not self.app_id:
            await self._send_error("缺少 app_id")
            return False
```

---

### 2.3 新增服务器 ACK 机制

**新增文件**: `main/xiaozhi-server/core/utils/seq_id_cache.py`

```python
"""
seq_id 防重放缓存
"""
from collections import OrderedDict
from typing import Dict

class SeqIdCache:
    """按 app_id 分组的 seq_id 缓存，用于防重放"""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._cache: Dict[str, OrderedDict] = {}
    
    def check_and_add(self, app_id: str, seq_id: str) -> bool:
        """检查 seq_id 是否重复，如果不重复则添加
        
        Returns:
            True 如果是新消息，False 如果是重复消息
        """
        if app_id not in self._cache:
            self._cache[app_id] = OrderedDict()
        
        cache = self._cache[app_id]
        
        if seq_id in cache:
            return False  # 重复消息
        
        # 添加新 seq_id
        cache[seq_id] = True
        
        # FIFO 淘汰
        while len(cache) > self.max_size:
            cache.popitem(last=False)
        
        return True
```

**修改文件**: `main/xiaozhi-server/core/app_connection.py`

```python
from core.utils.seq_id_cache import SeqIdCache

class AppConnectionHandler:
    # 类级别的 seq_id 缓存（所有连接共享）
    _seq_id_cache = SeqIdCache(max_size=100)
    
    async def _handle_text_message(self, message: str):
        msg_json = json.loads(message)
        seq_id = msg_json.get("seq_id")
        
        # 发送 server_ack
        if seq_id:
            # 检查重复
            if not self._seq_id_cache.check_and_add(self.app_id, seq_id):
                await self._send_server_ack(seq_id, code=5, msg="重复消息")
                return
            
            # 先发送 ACK 确认收到
            await self._send_server_ack(seq_id, code=0, msg="已接收")
        
        # 继续处理消息
        await handleTextMessage(self, message)
    
    async def _send_server_ack(self, seq_id: str, code: int, msg: str):
        """发送服务器 ACK"""
        import time
        await self.websocket.send(json.dumps({
            "type": "server_ack",
            "seq_id": seq_id,
            "code": code,
            "msg": msg,
            "ts": int(time.time() * 1000)
        }))
```

**server_ack 错误码**:
| code | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 设备离线 |
| 2 | 参数错误 |
| 3 | 未认证 |
| 4 | 内部错误 |
| 5 | 重复消息 |

---

### 2.4 新增设备上下线通知

**修改文件**: `main/xiaozhi-server/core/connection_manager.py`

```python
import json
import time
import asyncio

class ConnectionManager:
    
    async def notify_apps_device_status(self, device_id: str, status: str, reason: str = None):
        """通知所有关联的 App 设备状态变化
        
        Args:
            device_id: 设备 ID
            status: "online" 或 "offline"
            reason: 下线原因（仅 offline 时）
        """
        app_conns = self.get_app_conns(device_id)
        if not app_conns:
            return
        
        notification = {
            "type": "device_status",
            "status": status,
            "device_id": device_id,
            "ts": int(time.time() * 1000)
        }
        
        if status == "offline" and reason:
            notification["reason"] = reason
        
        msg = json.dumps(notification)
        
        for app_conn in app_conns:
            try:
                if app_conn.websocket:
                    await app_conn.websocket.send(msg)
            except Exception as e:
                self.logger.bind(tag=TAG).warning(f"通知 App 失败: {e}")
    
    def register_esp32(self, device_id: str, conn) -> None:
        """注册 ESP32 连接"""
        self.esp32_connections[device_id] = conn
        self.logger.bind(tag=TAG).info(f"ESP32 连接已注册: {device_id}")
        
        # 通知 App 设备上线
        asyncio.create_task(self.notify_apps_device_status(device_id, "online"))
    
    def unregister_esp32(self, device_id: str, reason: str = "connection_lost") -> None:
        """注销 ESP32 连接"""
        if device_id in self.esp32_connections:
            del self.esp32_connections[device_id]
            self.logger.bind(tag=TAG).info(f"ESP32 连接已注销: {device_id}")
            
            # 通知 App 设备下线
            asyncio.create_task(self.notify_apps_device_status(device_id, "offline", reason))
```

**修改文件**: `main/xiaozhi-server/core/connection.py`

在 ESP32 连接断开时调用 `unregister_esp32` 并传入原因：
```python
# 在 _cleanup 或连接断开处
manager.unregister_esp32(self.device_id, reason="connection_lost")
```

---

### 2.5 到访通知推送人脸图片

**修改文件**: `main/xiaozhi-server/core/handle/textHandler/faceRecognitionHandler.py`

修改 `_notify_apps` 方法，添加图片数据：

```python
async def _notify_apps(self, conn, result, access_granted: bool, visit_id: int, jpeg_data: bytes = None, image_path: str = None):
    """推送到访通知给 App（含人脸图片）"""
    try:
        manager = ConnectionManager.get_instance()
        app_conns = manager.get_app_conns(conn.device_id)
        
        if not app_conns:
            return
        
        notification = {
            "type": "visit_notification",
            "ts": int(time.time() * 1000),
            "data": {
                "visit_id": visit_id,
                "person_id": result.person.id if result.person else None,
                "person_name": result.person.name if result.person else "陌生人",
                "relation": result.person.relation_type if result.person else None,
                "result": result.result,
                "access_granted": access_granted,
                "image": base64.b64encode(jpeg_data).decode() if jpeg_data else None,
                "image_path": image_path
            }
        }
        
        for app_conn in app_conns:
            if app_conn.websocket:
                await app_conn.websocket.send(json.dumps(notification))
                
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"推送通知失败: {e}")
```

---

### 2.6 新增数据查询 Handler

**新增文件**: `main/xiaozhi-server/core/handle/textHandler/queryHandler.py`

```python
"""
数据查询消息处理器
"""
import json
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType

TAG = __name__


class QueryHandler(TextMessageHandler):
    """处理 App 数据查询请求"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.QUERY

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        target = msg_json.get("target")
        data = msg_json.get("data", {})
        
        handlers = {
            "status": self._query_status,
            "status_history": self._query_status_history,
            "events": self._query_events,
            "unlock_logs": self._query_unlock_logs,
            "media_files": self._query_media_files,
        }
        
        handler = handlers.get(target)
        if handler:
            await handler(conn, data)
        else:
            await self._send_error(conn, target, f"未知查询目标: {target}")

    async def _query_status(self, conn, data: Dict):
        """查询当前设备状态"""
        # 从内存缓存或数据库读取
        # TODO: 实现具体逻辑
        pass

    async def _query_status_history(self, conn, data: Dict):
        """查询历史状态"""
        limit = min(data.get("limit", 100), 500)
        offset = data.get("offset", 0)
        # TODO: 从数据库查询
        pass

    async def _query_events(self, conn, data: Dict):
        """查询事件历史"""
        event_type = data.get("event_type")
        limit = min(data.get("limit", 100), 500)
        offset = data.get("offset", 0)
        # TODO: 从数据库查询
        pass

    async def _query_unlock_logs(self, conn, data: Dict):
        """查询开锁日志"""
        method = data.get("method")
        result = data.get("result")
        limit = min(data.get("limit", 100), 500)
        offset = data.get("offset", 0)
        # TODO: 从数据库查询
        pass

    async def _query_media_files(self, conn, data: Dict):
        """查询媒体文件列表"""
        file_type = data.get("file_type")
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        limit = min(data.get("limit", 100), 500)
        offset = data.get("offset", 0)
        # TODO: 从数据库查询
        pass

    async def _send_response(self, conn, target: str, data: Any, total: int = None):
        """发送查询响应"""
        response = {
            "type": "query_result",
            "target": target,
            "status": "success",
            "data": data
        }
        await conn.websocket.send(json.dumps(response))

    async def _send_error(self, conn, target: str, error: str):
        """发送错误响应"""
        await conn.websocket.send(json.dumps({
            "type": "query_result",
            "target": target,
            "status": "error",
            "error": error
        }))
```

---

### 2.7 新增媒体下载 Handler

**新增文件**: `main/xiaozhi-server/core/handle/textHandler/mediaDownloadHandler.py`

```python
"""
媒体文件下载处理器
"""
import json
import base64
import os
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType

TAG = __name__


class MediaDownloadHandler(TextMessageHandler):
    """处理 App 媒体文件下载请求"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.MEDIA_DOWNLOAD

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        file_id = msg_json.get("file_id")
        file_path = msg_json.get("file_path")
        
        if not file_id and not file_path:
            await self._send_error(conn, "missing_params", "需要 file_id 或 file_path")
            return
        
        await self._download_file(conn, file_id, file_path)

    async def _download_file(self, conn, file_id: int = None, file_path: str = None):
        """下载文件"""
        try:
            # 获取文件信息
            if file_id:
                # 从数据库查询文件路径
                # TODO: 实现数据库查询
                pass
            
            # 读取文件
            full_path = os.path.join("data/media", file_path)
            
            if not os.path.exists(full_path):
                await self._send_error(conn, "file_not_found", "文件不存在")
                return
            
            file_size = os.path.getsize(full_path)
            
            # 检查文件大小（超过 50MB 拒绝）
            if file_size > 50 * 1024 * 1024:
                await self._send_error(conn, "file_too_large", "文件过大，请使用分片下载")
                return
            
            # 读取并编码
            with open(full_path, "rb") as f:
                content = base64.b64encode(f.read()).decode()
            
            # 确定 MIME 类型
            mime_type = self._get_mime_type(file_path)
            
            await conn.websocket.send(json.dumps({
                "type": "media_download",
                "status": "success",
                "data": {
                    "file_id": file_id,
                    "file_type": "face" if "face" in file_path else "recording",
                    "file_name": os.path.basename(file_path),
                    "file_size": file_size,
                    "mime_type": mime_type,
                    "content": content
                }
            }))
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"下载文件失败: {e}")
            await self._send_error(conn, "internal_error", str(e))

    def _get_mime_type(self, file_path: str) -> str:
        """获取 MIME 类型"""
        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".mp4": "video/mp4",
            ".avi": "video/x-msvideo",
        }
        return mime_map.get(ext, "application/octet-stream")

    async def _send_error(self, conn, error: str, message: str):
        """发送错误响应"""
        await conn.websocket.send(json.dumps({
            "type": "media_download",
            "status": "error",
            "error": error,
            "message": message
        }))


class MediaDownloadChunkHandler(TextMessageHandler):
    """处理大文件分片下载"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.MEDIA_DOWNLOAD_CHUNK

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        file_id = msg_json.get("file_id")
        chunk_index = msg_json.get("chunk_index", 0)
        chunk_size = min(msg_json.get("chunk_size", 1024 * 1024), 5 * 1024 * 1024)  # 最大 5MB
        
        # TODO: 实现分片下载逻辑
        pass
```

---

### 2.8 命令代理 Handler

**新增文件**: `main/xiaozhi-server/core/handle/textHandler/commandProxyHandler.py`

处理 App 发送的 `lock_control`、`dev_control`、`user_mgmt` 命令，记录日志后转发给 ESP32：

```python
"""
命令代理处理器 - 处理 App 发送的设备控制命令
"""
import json
import time
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.connection_manager import ConnectionManager

TAG = __name__


class LockControlProxyHandler(TextMessageHandler):
    """处理 App 发送的锁控命令"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.LOCK_CONTROL

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        # 仅处理 App 发送的命令
        if not hasattr(conn, "client_type") or conn.client_type != "app":
            return
        
        command = msg_json.get("command")
        
        # 记录操作日志
        await self._log_operation(conn, msg_json)
        
        # 转发给 ESP32
        await self._forward_to_esp32(conn, msg_json)

    async def _log_operation(self, conn, msg_json: Dict[str, Any]):
        """记录操作日志"""
        try:
            # 如果是开锁命令，记录到 unlock_logs
            if msg_json.get("command") == "unlock":
                if hasattr(conn, "doorlock_db") and conn.doorlock_db:
                    conn.doorlock_db.save_unlock_log(
                        device_id=conn.device_id,
                        method="remote",
                        user_id=0,  # App 用户 ID 可以从 app_id 映射
                        result=True,  # 命令发送成功
                        fail_count=0,
                        app_id=conn.app_id  # 记录 app_id
                    )
        except Exception as e:
            conn.logger.bind(tag=TAG).warning(f"记录操作日志失败: {e}")

    async def _forward_to_esp32(self, conn, msg_json: Dict[str, Any]):
        """转发命令到 ESP32"""
        try:
            manager = ConnectionManager.get_instance()
            esp32_conn = manager.get_esp32_conn(conn.device_id)
            
            if not esp32_conn or not esp32_conn.websocket:
                await self._send_error(conn, "设备离线")
                return
            
            # 添加 msg_id（ESP32 需要）
            msg_json["msg_id"] = f"cmd_{int(time.time() * 1000)}"
            
            await esp32_conn.websocket.send(json.dumps(msg_json))
            conn.logger.bind(tag=TAG).info(f"命令已转发: {msg_json}")
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发命令失败: {e}")
            await self._send_error(conn, str(e))

    async def _send_error(self, conn, message: str):
        """发送错误响应"""
        await conn.websocket.send(json.dumps({
            "type": "lock_control",
            "status": "error",
            "message": message
        }))


class DevControlProxyHandler(TextMessageHandler):
    """处理 App 发送的设备控制命令"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.DEV_CONTROL

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        # 仅处理 App 发送的命令
        if not hasattr(conn, "client_type") or conn.client_type != "app":
            return
        
        # 转发给 ESP32
        await self._forward_to_esp32(conn, msg_json)

    async def _forward_to_esp32(self, conn, msg_json: Dict[str, Any]):
        """转发命令到 ESP32"""
        # 类似 LockControlProxyHandler
        pass


class UserMgmtProxyHandler(TextMessageHandler):
    """处理 App 发送的用户管理命令"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.USER_MGMT

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        # 仅处理 App 发送的命令
        if not hasattr(conn, "client_type") or conn.client_type != "app":
            return
        
        # 转发给 ESP32
        await self._forward_to_esp32(conn, msg_json)

    async def _forward_to_esp32(self, conn, msg_json: Dict[str, Any]):
        """转发命令到 ESP32"""
        # 类似 LockControlProxyHandler
        pass
```

---

### 2.9 更新消息类型枚举

**修改文件**: `main/xiaozhi-server/core/handle/textMessageType.py`

```python
class TextMessageType(Enum):
    # ... 现有类型 ...
    
    # App 协议 v2.2 新增
    QUERY = "query"
    MEDIA_DOWNLOAD = "media_download"
    MEDIA_DOWNLOAD_CHUNK = "media_download_chunk"
    LOCK_CONTROL = "lock_control"
    DEV_CONTROL = "dev_control"
    USER_MGMT = "user_mgmt"
```

---

### 2.10 注册新 Handler

**修改文件**: `main/xiaozhi-server/core/handle/textMessageHandlerRegistry.py`

```python
from core.handle.textHandler.queryHandler import QueryHandler
from core.handle.textHandler.mediaDownloadHandler import MediaDownloadHandler, MediaDownloadChunkHandler
from core.handle.textHandler.commandProxyHandler import (
    LockControlProxyHandler, 
    DevControlProxyHandler, 
    UserMgmtProxyHandler
)

class TextMessageHandlerRegistry:
    def _register_default_handlers(self) -> None:
        handlers = [
            # ... 现有 handlers ...
            
            # App 协议 v2.2 新增
            QueryHandler(),
            MediaDownloadHandler(),
            MediaDownloadChunkHandler(),
            LockControlProxyHandler(),
            DevControlProxyHandler(),
            UserMgmtProxyHandler(),
        ]
```

---

## 三、文件修改清单

### 新增文件
| 文件路径 | 说明 |
|----------|------|
| `core/utils/seq_id_cache.py` | seq_id 防重放缓存 |
| `core/handle/textHandler/queryHandler.py` | 数据查询处理器 |
| `core/handle/textHandler/mediaDownloadHandler.py` | 媒体下载处理器 |
| `core/handle/textHandler/commandProxyHandler.py` | 命令代理处理器 |

### 修改文件
| 文件路径 | 修改内容 |
|----------|----------|
| `core/app_connection.py` | 移除 forward、新增 app_id、新增 server_ack |
| `core/connection_manager.py` | 新增设备上下线通知 |
| `core/connection.py` | 断开时传入原因 |
| `core/handle/textHandler/faceRecognitionHandler.py` | 到访通知推送图片 |
| `core/handle/textMessageType.py` | 新增消息类型枚举 |
| `core/handle/textMessageHandlerRegistry.py` | 注册新 Handler |

---

## 四、实施顺序

1. **第一阶段（基础设施）**
   - 新增 `seq_id_cache.py`
   - 修改 `textMessageType.py` 添加新类型

2. **第二阶段（核心功能）**
   - 修改 `app_connection.py`（移除 forward、新增 app_id、server_ack）
   - 修改 `connection_manager.py`（设备上下线通知）

3. **第三阶段（Handler 实现）**
   - 新增 `commandProxyHandler.py`
   - 新增 `queryHandler.py`
   - 新增 `mediaDownloadHandler.py`
   - 修改 `faceRecognitionHandler.py`

4. **第四阶段（集成测试）**
   - 注册所有新 Handler
   - 端到端测试

---

## 五、测试要点

1. **server_ack 机制**
   - 发送带 seq_id 的消息，验证收到 server_ack
   - 发送重复 seq_id，验证返回 code=5
   - 发送不带 seq_id 的消息，验证正常处理

2. **设备上下线通知**
   - ESP32 连接时，App 收到 online 通知
   - ESP32 断开时，App 收到 offline 通知

3. **命令代理**
   - App 发送 lock_control，验证转发到 ESP32
   - 验证操作日志记录了 app_id

4. **数据查询**
   - 测试各种查询接口的响应格式

5. **媒体下载**
   - 测试小文件下载
   - 测试大文件分片下载

---

**文档维护者：** 毕业设计项目组  
**创建日期：** 2024-12-11
