# 服务器触发人脸识别 - 完整实施方案

## 文档信息

- **创建日期**：2024-02-14
- **版本**：v1.0
- **状态**：待实施

## 背景

ESP32端已修改实现，不再主动触发拍照进行人脸识别。需要由服务器在收到PIR或门铃事件后，主动调用ESP32拍照，然后进行人脸识别和权限判断。

## 当前实现分析

### 已有的MCP拍照机制

**完整流程**：

1. 服务器通过 WebSocket 发送 MCP `tools/call` 请求
2. ESP32 收到后拍照
3. ESP32 通过 HTTP POST 上传照片到 `/api/doorlock/image/upload`
4. 服务器通过回调机制接收照片

**关键代码位置**：

- MCP工具调用：`core/providers/tools/device_mcp/mcp_handler.py` - `call_mcp_tool()`
- MCP客户端：`core/providers/tools/device_mcp/mcp_client.py` - `MCPClient`
- 图片上传接口：`core/handle/image_upload_handler.py` - `ImageUploadHandler`

**ESP32 MCP工具**：

- 工具名：`capture_image`
- 参数：`{"question": "你看到了什么？"}`
- 返回：通过HTTP POST异步上传照片

### 问题识别

1. **MCP调用是异步的**：`call_mcp_tool()` 返回的是文本结果，不是照片数据
2. **照片通过HTTP上传**：需要通过回调机制接收
3. **缺少同步等待机制**：发送拍照请求后无法等待照片上传完成
4. **doorlock模块不完整**：
   - `ESP32CameraService` 未集成MCP调用
   - `DoorlockIntentHandler._capture_visitor_photo` 返回None
   - 缺少照片上传与拍照请求的关联机制

---

## 修订后的任务规划

### 阶段一：完善拍照请求-响应机制（核心）

#### 任务 1.1：实现基于MCP的拍照同步等待机制

**目标**：封装MCP拍照调用，实现发送请求后等待照片上传的同步机制

**文件**：

- `core/providers/doorlock/esp32_camera.py`
- `core/handle/image_upload_handler.py`

**实现方案**：

```python
# core/providers/doorlock/esp32_camera.py

import asyncio
import json
import time
from typing import Optional, Dict, Any
from loguru import logger

TAG = "ESP32Camera"


class ESP32CameraService:
    """ESP32摄像头服务（基于MCP协议）"""

    def __init__(self, config: dict, logger_instance=None):
        """初始化摄像头服务"""
        self.logger = logger_instance or logger
        self.config = config

        # 待处理的拍照请求 {device_id: Future}
        self.pending_captures = {}

        # 图片保存路径配置
        doorlock_config = config.get('doorlock', {})
        package_guard_config = doorlock_config.get('package_guard', {})

        from pathlib import Path
        self.baseline_dir = Path(package_guard_config.get(
            'baseline_dir',
            'data/face_recognition/package_baseline/'
        ))
        self.visits_dir = Path('data/visits/')

        # 确保目录存在
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.visits_dir.mkdir(parents=True, exist_ok=True)

        self.logger.bind(tag=TAG).info("ESP32摄像头服务初始化完成（MCP模式）")

    async def capture_image(
        self,
        device_id: str,
        conn,
        question: str = "拍照",
        timeout: int = 10
    ) -> Optional[bytes]:
        """拍摄照片（通过MCP协议）

        Args:
            device_id: 设备ID
            conn: 连接对象（必须有mcp_client）
            question: 拍照问题描述
            timeout: 超时时间（秒）

        Returns:
            JPEG图片数据，失败返回None
        """
        try:
            # 检查MCP客户端
            if not hasattr(conn, 'mcp_client') or not conn.mcp_client:
                self.logger.bind(tag=TAG).error(
                    f"设备 {device_id} 未初始化MCP客户端"
                )
                return None

            if not await conn.mcp_client.is_ready():
                self.logger.bind(tag=TAG).error(
                    f"设备 {device_id} MCP客户端未就绪"
                )
                return None

            # 检查是否有capture_image工具
            if not conn.mcp_client.has_tool('capture_image'):
                self.logger.bind(tag=TAG).error(
                    f"设备 {device_id} 不支持capture_image工具"
                )
                return None

            self.logger.bind(tag=TAG).info(
                f"开始拍照 - 设备: {device_id}, 问题: {question}"
            )

            # 1. 创建Future对象等待照片上传
            future = asyncio.Future()
            self.pending_captures[device_id] = future

            # 2. 注册图片上传回调
            from core.http_server import SimpleHttpServer
            # 获取全局HTTP服务器实例（需要在http_server中实现单例）
            http_server = SimpleHttpServer.get_instance()
            if http_server:
                async def upload_callback(dev_id, image_data, ts, w, h):
                    """图片上传回调"""
                    if dev_id == device_id and dev_id in self.pending_captures:
                        self.logger.bind(tag=TAG).info(
                            f"收到拍照结果 - 设备: {dev_id}, "
                            f"大小: {len(image_data)} bytes, 尺寸: {w}x{h}"
                        )
                        if not self.pending_captures[dev_id].done():
                            self.pending_captures[dev_id].set_result(image_data)

                http_server.image_upload_handler.register_callback(
                    device_id, upload_callback
                )

            # 3. 通过MCP调用capture_image工具
            from core.providers.tools.device_mcp import call_mcp_tool

            try:
                # 调用MCP工具（这会发送拍照请求给ESP32）
                # 注意：call_mcp_tool返回的是文本结果，不是照片
                mcp_result = await call_mcp_tool(
                    conn=conn,
                    mcp_client=conn.mcp_client,
                    tool_name='capture_image',
                    args=json.dumps({"question": question}),
                    timeout=timeout
                )

                self.logger.bind(tag=TAG).debug(
                    f"MCP拍照请求已发送 - 设备: {device_id}, "
                    f"MCP返回: {mcp_result}"
                )

            except Exception as e:
                self.logger.bind(tag=TAG).error(
                    f"MCP拍照请求失败 - 设备: {device_id}, 错误: {e}"
                )
                # 清理并返回
                self.pending_captures.pop(device_id, None)
                if http_server:
                    http_server.image_upload_handler.unregister_callback(device_id)
                return None

            # 4. 等待照片上传（带超时）
            try:
                jpeg_data = await asyncio.wait_for(future, timeout=timeout)

                self.logger.bind(tag=TAG).info(
                    f"拍照成功 - 设备: {device_id}, "
                    f"大小: {len(jpeg_data)} bytes"
                )

                return jpeg_data

            except asyncio.TimeoutError:
                self.logger.bind(tag=TAG).error(
                    f"等待照片上传超时 - 设备: {device_id}, "
                    f"超时时间: {timeout}秒"
                )
                return None

        except Exception as e:
            self.logger.bind(tag=TAG).error(
                f"拍照失败 - 设备: {device_id}, 错误: {e}"
            )
            import traceback
            self.logger.bind(tag=TAG).error(traceback.format_exc())
            return None

        finally:
            # 5. 清理资源
            self.pending_captures.pop(device_id, None)
            if http_server:
                http_server.image_upload_handler.unregister_callback(device_id)

    # ... 其他方法保持不变（save_baseline_image, save_visit_image等）
```

**关键点**：

1. ✅ 使用现有的 `call_mcp_tool()` 发送拍照请求
2. ✅ 通过 `ImageUploadHandler` 的回调机制接收照片
3. ✅ 使用 `asyncio.Future` 实现同步等待
4. ✅ 完善的超时和错误处理
5. ✅ 资源清理（Future和回调）

**验收标准**：

- ✅ 能成功调用ESP32的 `capture_image` 工具
- ✅ 能等待并接收HTTP上传的照片
- ✅ 超时机制正常工作
- ✅ 资源正确清理，无内存泄漏

---

#### 任务 1.2：HTTP服务器单例模式

**目标**：让 `ESP32CameraService` 能访问 `ImageUploadHandler`

**文件**：

- `core/http_server.py`

**修改**：

```python
class SimpleHttpServer:
    _instance = None  # 单例实例

    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()
        self.ota_handler = OTAHandler(config)
        self.vision_handler = VisionHandler(config)
        self.image_upload_handler = ImageUploadHandler(config, self.logger)

        # ... 其他初始化代码 ...

        # 保存单例
        SimpleHttpServer._instance = self

    @classmethod
    def get_instance(cls):
        """获取HTTP服务器单例"""
        return cls._instance

    # ... 其他方法保持不变 ...
```

**验收标准**：

- ✅ `ESP32CameraService` 能获取HTTP服务器实例
- ✅ 能访问 `image_upload_handler`

---

#### 任务 1.3：修复 `_capture_visitor_photo` 方法

**目标**：让智能门锁AI模式能够正常拍照

**文件**：

- `core/handle/doorlock_intent_handler.py`

**修改**：

```python
async def _capture_visitor_photo(
    self,
    device_id: str,
    conn=None
) -> Optional[bytes]:
    """拍摄访客照片

    Args:
        device_id: 设备ID
        conn: 连接对象（必须有mcp_client）

    Returns:
        JPEG图片数据，失败返回None
    """
    try:
        from core.providers.doorlock.esp32_camera import ESP32CameraService

        # 创建摄像头服务
        camera_service = ESP32CameraService(
            config=self.config if hasattr(self, 'config') else {},
            logger_instance=logger
        )

        # 调用拍照（通过MCP协议）
        jpeg_data = await camera_service.capture_image(
            device_id=device_id,
            conn=conn,
            question="访客到访拍照",
            timeout=10
        )

        if jpeg_data:
            logger.bind(tag=TAG).info(
                f"拍照成功 - 设备: {device_id}, "
                f"大小: {len(jpeg_data)} bytes"
            )
            return jpeg_data
        else:
            logger.bind(tag=TAG).error(
                f"拍照失败 - 设备: {device_id}"
            )
            return None

    except Exception as e:
        logger.bind(tag=TAG).error(
            f"拍摄访客照片异常 - 设备: {device_id}, 错误: {e}"
        )
        import traceback
        logger.bind(tag=TAG).error(traceback.format_exc())
        return None
```

**验收标准**：

- ✅ PIR触发后能成功拍照
- ✅ 拍照失败时有明确日志
- ✅ 超时后流程能正常继续

---

### 阶段二：统一人脸识别流程

#### 任务 2.1：门铃事件触发人脸识别

**目标**：门铃按下时也触发人脸识别流程

**文件**：

- `core/handle/textHandler/eventReportHandler.py`

**修改**：参考之前的规划，提取 `_trigger_face_recognition` 统一方法

**验收标准**：

- ✅ 门铃按下触发人脸识别
- ✅ PIR触发人脸识别
- ✅ 代码逻辑统一

---

#### 任务 2.2：实现开锁命令下发

**目标**：人脸识别成功且有权限时，下发 `face_result` 消息

**文件**：

- `core/handle/doorlock_intent_handler.py`

**修改**：参考之前的规划，添加 `_send_face_result` 方法

**验收标准**：

- ✅ 识别成功有权限时下发 `face_result` (granted=true)
- ✅ 识别失败或无权限时下发 `face_result` (granted=false)
- ✅ ESP32能正确接收并处理

---

### 阶段三：配置与开关

#### 任务 3.1：添加人脸识别功能开关

**目标**：支持通过配置启用/禁用人脸识别功能

**配置文件**：

- `config/doorlock_config.yaml`

**配置项**：

```yaml
# 人脸识别配置
face_recognition:
  # 是否启用人脸识别功能
  enabled: true
  # 最大重试次数
  max_retries: 3
  # 重试间隔（秒）
  retry_interval: 1
  # 拍照超时（秒）
  capture_timeout: 10
```

**验收标准**：

- ✅ 配置项生效
- ✅ 禁用后不触发人脸识别

---

## 任务优先级与时间估算（修订）

| 阶段 | 任务                 | 优先级 | 预计时间 | 依赖     |
| ---- | -------------------- | ------ | -------- | -------- |
| 一   | 1.1 MCP拍照同步等待  | P0     | 6h       | 无       |
| 一   | 1.2 HTTP服务器单例   | P0     | 1h       | 无       |
| 一   | 1.3 修复拍照方法     | P0     | 2h       | 1.1, 1.2 |
| 二   | 2.1 门铃触发人脸识别 | P1     | 2h       | 1.3      |
| 二   | 2.2 实现开锁命令     | P0     | 3h       | 1.3      |
| 三   | 3.1 功能开关         | P2     | 2h       | 无       |

**总计**：约 16 小时

---

## 关键技术点

### 1. MCP工具调用流程

```
服务器 → call_mcp_tool()
    ↓
发送 MCP tools/call 请求（WebSocket）
    ↓
ESP32 收到请求 → 拍照
    ↓
ESP32 通过 HTTP POST 上传照片
    ↓
ImageUploadHandler 接收
    ↓
触发回调 → 设置 Future 结果
    ↓
服务器 await Future → 获取照片数据
```

### 2. 异步等待机制

- 使用 `asyncio.Future` 实现跨协议同步
- MCP请求（WebSocket）+ HTTP上传（回调）→ 统一的同步接口

### 3. 资源管理

- 及时清理 `pending_captures`
- 及时注销 `ImageUploadHandler` 回调
- 避免内存泄漏

---

## 风险与注意事项

1. **MCP客户端状态检查**：确保 `conn.mcp_client` 已初始化且就绪
2. **工具可用性检查**：确保ESP32注册了 `capture_image` 工具
3. **超时时间设置**：需要考虑拍照+上传的总时间（建议10-15秒）
4. **并发安全**：多个设备同时拍照时的Future管理
5. **HTTP服务器单例**：确保在服务器启动时正确初始化
6. **错误降级**：拍照失败时的处理策略（是否继续意图识别对话）

---

## 测试计划

### 单元测试

1. MCP拍照请求发送测试
2. 照片上传回调测试
3. Future超时处理测试
4. 资源清理测试

### 集成测试

1. PIR → MCP拍照 → 人脸识别 → 开锁（完整流程）
2. 门铃 → MCP拍照 → 人脸识别 → 开锁（完整流程）
3. 拍照超时 → 降级处理
4. 并发多设备拍照

### 性能测试

1. 拍照响应时间
2. 内存泄漏检查
3. 并发压力测试

---

## 建议实施顺序

1. **第一步**：完成任务 1.1 和 1.2（MCP拍照机制），这是核心基础
2. **第二步**：完成任务 1.3（修复拍照方法），验证拍照流程
3. **第三步**：完成任务 2.2（开锁命令），验证完整流程
4. **第四步**：完成任务 2.1（门铃触发），扩展触发场景
5. **第五步**：完成任务 3.1（配置开关），完善功能

这样可以快速验证核心功能，然后逐步完善。

---

## 📋 相关文档

- **任务检查清单**：[server-trigger-face-recognition-implementation-checklist.md](./server-trigger-face-recognition-implementation-checklist.md)
- **MCP拍照指南**：[esp32-vision-guide.md](./esp32-vision-guide.md)
- **协议规范**：[智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md](./智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md)
- **智能门锁AI需求**：[smart-doorlock-ai-requirements.md](./smart-doorlock-ai-requirements.md)

---

**文档版本**：v1.0  
**最后更新**：2024-02-14  
**状态**：待实施
