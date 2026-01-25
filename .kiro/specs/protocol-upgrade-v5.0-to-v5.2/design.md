# 设计文档 - 服务器端协议升级 v5.0 到 v5.2

## 1. 概述

### 1.1 设计目标

本设计文档定义了 xiaozhi-server 从协议 v5.0 升级到 v5.2 的技术实现方案。主要目标包括：

1. **协议兼容性**：支持 ESP32 v5.2 协议的所有新特性
2. **消息可靠性**：实现两级确认机制，确保命令执行状态可追溯
3. **数据完整性**：支持新增字段和消息类型，完整存储设备数据
4. **系统健壮性**：增强错误处理和日志记录能力

### 1.2 升级范围

| 模块 | 影响范围 | 优先级 |
|------|----------|--------|
| 消息处理器 | 新增 3 个 Handler，更新 4 个 Handler | P0 |
| 消息路由 | 更新 textHandle.py 路由表 | P0 |
| 数据库层 | 新增 1 个表，更新 2 个表 | P1 |
| 错误码定义 | 新增统一错误码常量 | P1 |
| 日志记录 | 增强日志输出 | P2 |

### 1.3 技术栈

- **语言**：Python 3.10
- **异步框架**：asyncio
- **WebSocket**：websockets 库
- **数据库**：MySQL（通过 face_service.db）
- **日志**：loguru
- **配置**：ruamel.yaml

---

## 2. 架构设计

### 2.1 消息处理流程

```
WebSocket 连接
    │
    ├─> Text Frame (JSON)
    │       │
    │       ├─> handleTextMessage()
    │       │       │
    │       │       ├─> 解析 JSON
    │       │       ├─> 路由到对应 Handler
    │       │       └─> Handler.handle()
    │       │               │
    │       │               ├─> 业务处理
    │       │               ├─> 数据库存储
    │       │               └─> 转发到 App
    │       │
    │       └─> 错误处理
    │
    └─> Binary Frame
            │
            └─> _route_message()
                    │
                    ├─> 人脸识别 (type=2)
                    └─> 音频流 (type=0)
```

### 2.2 Handler 模式

所有消息处理器继承自 `TextMessageHandler` 抽象基类：

```python
class TextMessageHandler(ABC):
    @property
    @abstractmethod
    def message_type(self) -> TextMessageType:
        pass
    
    @abstractmethod
    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        pass
```

**优势**：
- 统一接口，易于扩展
- 类型安全（通过 TextMessageType 枚举）
- 职责单一，每个 Handler 处理一种消息类型

### 2.3 消息转发机制

Server 作为 ESP32 和 App 之间的中间层，负责：

1. **接收 ESP32 上报**：解析、验证、存储
2. **转发到 App**：通过 ConnectionManager 获取关联的 App 连接
3. **下发 App 命令**：构建消息并发送到 ESP32

```python
# 转发示例
manager = ConnectionManager.get_instance()
app_conns = manager.get_app_conns(conn.device_id)

for app_conn in app_conns:
    if app_conn.websocket:
        await app_conn.websocket.send(json.dumps(msg_json))
```

---

## 3. 组件和接口

### 3.1 新增消息处理器

#### 3.1.1 Esp32AckHandler

**文件路径**：`main/xiaozhi-server/core/handle/textHandler/esp32AckHandler.py`

**职责**：处理 ESP32 的第二级确认（命令已收到，开始处理）

**接口**：

```python
class Esp32AckHandler(TextMessageHandler):
    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.ESP32_ACK
    
    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理 esp32_ack 消息
        
        消息格式:
        {
            "type": "esp32_ack",
            "seq_id": "1702234567890_0",
            "code": 0,
            "msg": "received"
        }
        """
```

**处理逻辑**：
1. 提取 `seq_id`、`code`、`msg`
2. 记录日志（DEBUG 级别）
3. 更新命令状态为"已送达"（如果有待处理命令队列）
4. **必须转发到关联的 App**（让 App 知道命令已被 ESP32 接收）
5. 如果 code != 0，表示 ESP32 拒绝接收命令，需要记录错误

#### 3.1.2 DoorOpenedReportHandler

**文件路径**：`main/xiaozhi-server/core/handle/textHandler/doorOpenedReportHandler.py`

**职责**：处理开门日志上报

**接口**：

```python
class DoorOpenedReportHandler(TextMessageHandler):
    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.DOOR_OPENED_REPORT
    
    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理 door_opened_report 消息
        
        消息格式:
        {
            "type": "door_opened_report",
            "ts": 1702234567890,
            "data": {
                "method": "finger",
                "source": "outside"
            }
        }
        """
```

**处理逻辑**：
1. 提取 `method` 和 `source`
2. 存储到数据库（door_opened_logs 表）
3. 转发到关联的 App

#### 3.1.3 PasswordReportHandler

**文件路径**：`main/xiaozhi-server/core/handle/textHandler/passwordReportHandler.py`

**职责**：处理密码查询结果上报

**接口**：

```python
class PasswordReportHandler(TextMessageHandler):
    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.PASSWORD_REPORT
    
    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理 password_report 消息
        
        消息格式:
        {
            "type": "password_report",
            "ts": 1702234567890,
            "data": {
                "password": "123456"
            }
        }
        """
```

**处理逻辑**：
1. 提取 `password`
2. 转发到请求查询的 App（不存储到数据库）
3. 记录日志（INFO 级别，不记录密码明文）

### 3.2 更新现有处理器

#### 3.2.1 AckHandler 更新

**变更内容**：
1. 字段名兼容：同时支持 `seq_id` 和 `msg_id`
2. 错误码验证：检查 code 是否在 0-10 范围内
3. 日志增强：记录 seq_id 和 code

**更新后接口**：

```python
async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
    # 兼容旧版 msg_id
    seq_id = msg_json.get("seq_id") or msg_json.get("msg_id")
    code = msg_json.get("code", 0)
    msg = msg_json.get("msg", "")
    
    # 验证错误码
    if code < 0 or code > 10:
        conn.logger.bind(tag=TAG).warning(
            f"无效的错误码: seq_id={seq_id}, code={code}"
        )
    
    # 记录日志
    if code == 0:
        conn.logger.bind(tag=TAG).debug(f"ACK 成功: seq_id={seq_id}")
    else:
        conn.logger.bind(tag=TAG).warning(
            f"ACK 失败: seq_id={seq_id}, code={code}, msg={msg}"
        )
```

#### 3.2.2 LogReportHandler 更新

**变更内容**：
1. 字段兼容：同时支持 `result` (bool) 和 `status` (string)
2. 新增字段：解析 `lock_time`
3. 数据库更新：存储 `status` 和 `lock_time`

**更新后接口**：

```python
async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
    data = msg_json.get("data", {})
    
    # 兼容旧版 result 字段
    if "status" in data:
        status = data["status"]
        lock_time = data.get("lock_time", 0)
    elif "result" in data:
        # 旧版兼容：result=true -> status=success
        status = "success" if data["result"] else "fail"
        lock_time = 0
    else:
        conn.logger.bind(tag=TAG).error("缺少 status 或 result 字段")
        return
    
    # 验证 status 取值
    if status not in ["success", "fail", "locked"]:
        conn.logger.bind(tag=TAG).error(f"无效的 status: {status}")
        return
    
    # 验证 lock_time
    if status == "locked" and lock_time <= 0:
        conn.logger.bind(tag=TAG).warning(
            f"locked 状态但 lock_time 无效: {lock_time}"
        )
```

#### 3.2.3 EventReportHandler 更新

**变更内容**：
1. 新增事件类型：`door_closed`、`lock_success`、`bolt_alarm`
2. 数据库更新：支持新增事件类型

**更新后接口**：

```python
async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
    event = msg_json.get("event")
    param = msg_json.get("param")
    
    # 验证事件类型
    valid_events = [
        "bell", "pir_trigger", "tamper", "door_open", "low_battery",
        "door_closed", "lock_success", "bolt_alarm"  # v5.2 新增
    ]
    
    if event not in valid_events:
        conn.logger.bind(tag=TAG).warning(f"未知事件类型: {event}")
        # 仍然转发，但记录警告
    
    # 根据事件类型处理
    if event == "door_closed":
        await self._handle_door_closed_event(conn, ts, param)
    elif event == "lock_success":
        await self._handle_lock_success_event(conn, ts, param)
    elif event == "bolt_alarm":
        await self._handle_bolt_alarm_event(conn, ts, param)
```

### 3.3 消息类型枚举更新

**文件路径**：`main/xiaozhi-server/core/handle/textMessageType.py`

**新增枚举值**：

```python
class TextMessageType(Enum):
    # 现有类型
    ACK = "ack"
    STATUS_REPORT = "status_report"
    EVENT_REPORT = "event_report"
    LOG_REPORT = "log_report"
    
    # v5.2 新增
    ESP32_ACK = "esp32_ack"
    DOOR_OPENED_REPORT = "door_opened_report"
    PASSWORD_REPORT = "password_report"
    QUERY = "query"
```

### 3.4 命令下发与重试机制

**文件路径**：更新 `main/xiaozhi-server/core/handle/textHandler/commandProxyHandler.py`

**设计原则**：
1. Server 对 ESP32 的重试对 App 透明
2. 等待 esp32_ack：2秒超时，最多3次重试
3. 如果重试全部失败，返回错误给 App
4. 成功收到 esp32_ack 后，继续等待 ack（根据命令类型设置超时）

**实现接口**：

```python
class CommandProxyHandler:
    async def _forward_with_retry(self, conn, esp32_conn, msg_json: Dict[str, Any]):
        """转发命令到 ESP32，带重试机制
        
        Args:
            conn: App 连接对象
            esp32_conn: ESP32 连接对象
            msg_json: 命令消息
            
        Returns:
            bool: 是否成功收到 esp32_ack
        """
        seq_id = msg_json.get("seq_id")
        max_retries = 3
        timeout = 2.0  # 2秒超时
        
        for retry in range(max_retries):
            try:
                # 发送命令到 ESP32
                await esp32_conn.websocket.send(json.dumps(msg_json))
                
                # 等待 esp32_ack
                ack_received = await self._wait_for_esp32_ack(
                    esp32_conn, seq_id, timeout
                )
                
                if ack_received:
                    return True
                    
            except Exception as e:
                conn.logger.bind(tag=TAG).warning(
                    f"发送命令失败（第 {retry + 1} 次）: {e}"
                )
        
        # 重试全部失败，通知 App
        await self._send_error(conn, "设备无响应，请检查设备状态", code=5)
        return False
    
    async def _wait_for_esp32_ack(self, esp32_conn, seq_id: str, timeout: float) -> bool:
        """等待 ESP32 的 esp32_ack 响应
        
        Args:
            esp32_conn: ESP32 连接对象
            seq_id: 消息序列 ID
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否收到 esp32_ack
        """
        # 注册回调到待处理命令队列
        future = asyncio.Future()
        
        if not hasattr(esp32_conn, "_pending_esp32_acks"):
            esp32_conn._pending_esp32_acks = {}
        
        esp32_conn._pending_esp32_acks[seq_id] = future
        
        try:
            # 等待 esp32_ack
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            return False
        finally:
            # 清理
            esp32_conn._pending_esp32_acks.pop(seq_id, None)
```

**Esp32AckHandler 配合**：

```python
class Esp32AckHandler(TextMessageHandler):
    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        seq_id = msg_json.get("seq_id")
        code = msg_json.get("code", 0)
        
        # 触发等待的 Future
        if hasattr(conn, "_pending_esp32_acks") and seq_id in conn._pending_esp32_acks:
            future = conn._pending_esp32_acks[seq_id]
            if not future.done():
                future.set_result(code == 0)
        
        # 转发给 App
        await self._forward_to_apps(conn, msg_json)
```

### 3.5 错误码常量定义

**文件路径**：`main/xiaozhi-server/core/constants/error_codes.py`（新建）

**重要说明**：
- ESP32 端已经完成了 STM32 错误码到统一错误码的映射
- 服务器端接收到的 `code` 字段已经是 0-10 的统一错误码
- 服务器端不需要进行错误码映射，只需定义常量方便使用

**内容**：

```python
"""统一错误码定义（v5.2）

注意：ESP32 端已经将 STM32 的十六进制错误码映射为统一错误码
服务器端接收到的 code 字段已经是 0-10 的十进制错误码
"""

class ErrorCode:
    SUCCESS = 0
    DEVICE_OFFLINE = 1
    DEVICE_BUSY = 2
    PARAM_ERROR = 3
    NOT_SUPPORTED = 4
    TIMEOUT = 5
    HARDWARE_FAULT = 6
    RESOURCE_FULL = 7
    UNAUTHORIZED = 8
    DUPLICATE_MESSAGE = 9
    INTERNAL_ERROR = 10

ERROR_MESSAGES = {
    ErrorCode.SUCCESS: "成功",
    ErrorCode.DEVICE_OFFLINE: "设备离线",
    ErrorCode.DEVICE_BUSY: "设备忙碌",
    ErrorCode.PARAM_ERROR: "参数错误",
    ErrorCode.NOT_SUPPORTED: "不支持",
    ErrorCode.TIMEOUT: "超时",
    ErrorCode.HARDWARE_FAULT: "硬件故障",
    ErrorCode.RESOURCE_FULL: "资源已满",
    ErrorCode.UNAUTHORIZED: "未认证",
    ErrorCode.DUPLICATE_MESSAGE: "重复消息",
    ErrorCode.INTERNAL_ERROR: "内部错误",
}

def is_valid_error_code(code: int) -> bool:
    """验证错误码是否在有效范围内"""
    return 0 <= code <= 10

def get_error_message(code: int) -> str:
    """获取错误码对应的错误消息"""
    return ERROR_MESSAGES.get(code, "未知错误")
```

---

## 4. 数据模型

### 4.1 数据库表结构

#### 4.1.1 unlock_logs 表更新

**新增字段**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| status | VARCHAR(16) | 'success' | 状态：success/fail/locked |
| lock_time | INT | 0 | 剩余锁定时间（分钟） |

**迁移脚本**：

```sql
-- 新增字段
ALTER TABLE unlock_logs 
ADD COLUMN status VARCHAR(16) DEFAULT 'success' AFTER result,
ADD COLUMN lock_time INT DEFAULT 0 AFTER status;

-- 迁移旧数据
UPDATE unlock_logs 
SET status = CASE 
    WHEN result = 1 THEN 'success' 
    ELSE 'fail' 
END
WHERE status = 'success';

-- 添加索引
CREATE INDEX idx_status ON unlock_logs(status);
```

#### 4.1.2 door_opened_logs 表（新建）

**表结构**：

```sql
CREATE TABLE door_opened_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL COMMENT '设备 ID',
    method VARCHAR(16) NOT NULL COMMENT '开锁方式',
    source VARCHAR(16) NOT NULL COMMENT '开门来源: outside/inside/unknown',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_device_time (device_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='开门日志表';
```

**字段说明**：

| 字段 | 说明 | 取值范围 |
|------|------|----------|
| method | 开锁方式 | finger/nfc/face/pwd/temp_pwd/key/remote |
| source | 开门来源 | outside/inside/unknown |

#### 4.1.3 device_events 表更新

**变更内容**：更新 event_type 字段的枚举值

**迁移脚本**：

```sql
-- 如果使用 ENUM 类型
ALTER TABLE device_events 
MODIFY COLUMN event_type ENUM(
    'bell', 'pir_trigger', 'tamper', 'door_open', 'low_battery',
    'door_closed', 'lock_success', 'bolt_alarm'
) NOT NULL;

-- 如果使用 VARCHAR 类型，无需修改
```

### 4.2 数据库访问接口

**文件路径**：`main/xiaozhi-server/core/handle/textHandler/faceRecognitionHandler.py`（复用现有 face_service.db）

**新增方法**：

```python
class Database:
    def save_unlock_log(self, device_id: str, method: str, user_id: int,
                        result: bool, fail_count: int, 
                        status: str = None, lock_time: int = 0):
        """保存开锁日志（兼容新旧字段）"""
        if status is None:
            status = "success" if result else "fail"
        
        # 插入数据库
        ...
    
    def save_door_opened_log(self, device_id: str, method: str, source: str):
        """保存开门日志"""
        # 插入 door_opened_logs 表
        ...
    
    def save_device_event(self, device_id: str, event_type: str, param: int):
        """保存设备事件"""
        # 插入 device_events 表
        ...
```

---

## 5. 正确性属性

基于需求文档的验收标准，定义以下正确性属性用于验证系统行为。

### 5.1 两级确认机制属性

**Property 1.1: esp32_ack 消息必须被正确解析和转发**

**Validates: Requirements 1.1, 1.2, 1.3**

For all ESP32 connections `conn` and for all messages `msg` where `msg.type == "esp32_ack"`:
- IF `msg` contains valid `seq_id` and `code` fields
- THEN Server SHALL successfully parse the message AND forward it to all associated App connections
- AND Server SHALL log the message with DEBUG level

**Property 1.2: esp32_ack 的 seq_id 必须与原命令匹配**

**Validates: Requirements 1.2**

For all ESP32 connections `conn` and for all `esp32_ack` messages `msg`:
- IF Server has a pending command with `seq_id == msg.seq_id`
- THEN Server SHALL update the command status to "received"
- AND Server SHALL preserve the `seq_id` when forwarding to App

**Property 1.3: ack 消息必须携带执行结果**

**Validates: Requirements 1.5, 1.6**

For all ESP32 connections `conn` and for all `ack` messages `msg`:
- IF `msg` contains `seq_id` and `code` fields
- THEN Server SHALL determine command execution result based on `code`
- AND IF `code == 0` THEN Server SHALL log success
- AND IF `code != 0` THEN Server SHALL log failure with error message

### 5.2 消息 ID 统一属性

**Property 2.1: 下发命令必须使用 seq_id**

**Validates: Requirements 2.1**

For all commands `cmd` sent from Server to ESP32:
- IF `cmd.type` in ["lock_control", "dev_control", "user_mgmt", "face_result", "query"]
- THEN `cmd` SHALL contain a `seq_id` field
- AND `seq_id` SHALL NOT be empty

**Property 2.2: 接收消息必须解析 seq_id**

**Validates: Requirements 2.2**

For all messages `msg` received from ESP32:
- IF `msg.type` in ["ack", "esp32_ack"]
- THEN Server SHALL attempt to parse `seq_id` field
- AND IF `seq_id` is missing THEN Server SHALL log error and reject the message

**Property 2.3: 转发消息必须保留 seq_id**

**Validates: Requirements 2.3**

For all messages `msg` forwarded from ESP32 to App:
- IF `msg` contains `seq_id` field
- THEN forwarded message SHALL contain the same `seq_id` value

### 5.3 统一错误码属性

**Property 3.1: 错误码必须在有效范围内**

**Validates: Requirements 3.1**

For all `ack` or `esp32_ack` messages `msg` received from ESP32:
- IF `msg` contains `code` field
- THEN `code` SHALL be an integer in range [0, 10]
- AND IF `code` is out of range THEN Server SHALL log warning

**Property 3.2: Server 生成的错误码必须符合规范**

**Validates: Requirements 3.2, 3.3, 3.4, 3.5, 3.6**

For all error responses `resp` generated by Server:
- IF device is offline THEN `resp.code == 1`
- IF parameters are invalid THEN `resp.code == 3`
- IF user is not authenticated THEN `resp.code == 8`
- IF `seq_id` is duplicate THEN `resp.code == 9`
- IF unknown error occurs THEN `resp.code == 10`

### 5.4 log_report 格式属性

**Property 4.1: status 字段必须被正确解析**

**Validates: Requirements 4.1**

For all `log_report` messages `msg` received from ESP32:
- IF `msg.data` contains `status` field
- THEN `status` SHALL be one of ["success", "fail", "locked"]
- AND IF `status` is invalid THEN Server SHALL log error and reject the message

**Property 4.2: locked 状态必须包含 lock_time**

**Validates: Requirements 4.2**

For all `log_report` messages `msg` where `msg.data.status == "locked"`:
- `msg.data` SHALL contain `lock_time` field
- AND `lock_time` SHALL be a positive integer (minutes)

**Property 4.3: success/fail 状态的 lock_time 必须为 0**

**Validates: Requirements 4.3**

For all `log_report` messages `msg` where `msg.data.status` in ["success", "fail"]:
- IF `msg.data` contains `lock_time` field
- THEN `lock_time` SHALL equal 0

**Property 4.4: 数据库存储必须包含新字段**

**Validates: Requirements 4.4**

For all `log_report` messages `msg` successfully processed:
- Server SHALL store `status` and `lock_time` to database
- AND database record SHALL contain both fields with correct values

**Property 4.5: 转发消息必须保留完整格式**

**Validates: Requirements 4.5**

For all `log_report` messages `msg` forwarded to App:
- Forwarded message SHALL contain `status` and `lock_time` fields
- AND field values SHALL match the original message

### 5.5 新增消息类型属性

**Property 5.1: door_opened_report 必须被正确处理**

**Validates: Requirements 5.2, 5.3**

For all `door_opened_report` messages `msg` received from ESP32:
- Server SHALL parse `method` and `source` fields
- AND Server SHALL store the record to `door_opened_logs` table
- AND Server SHALL forward the message to all associated App connections

**Property 5.2: password_report 必须被转发但不存储**

**Validates: Requirements 5.4, 5.5**

For all `password_report` messages `msg` received from ESP32:
- Server SHALL parse `password` field
- AND Server SHALL forward the message to requesting App
- AND Server SHALL NOT store the password to database

**Property 5.3: query 命令必须被正确下发**

**Validates: Requirements 5.6, 5.7, 5.8**

For all `query` commands `cmd` sent from App to Server:
- Server SHALL construct a query message with `seq_id` and `command` fields
- AND Server SHALL send the message to ESP32
- AND Server SHALL wait for `esp32_ack`, `ack`, and `status_report` responses

### 5.6 新增事件类型属性

**Property 6.1: 新增事件类型必须被识别**

**Validates: Requirements 6.1, 6.2, 6.3**

For all `event_report` messages `msg` where `msg.event` in ["door_closed", "lock_success", "bolt_alarm"]:
- Server SHALL recognize the event type
- AND Server SHALL store the event to `device_events` table
- AND Server SHALL forward the message to all associated App connections

**Property 6.2: 事件存储必须包含正确的类型**

**Validates: Requirements 6.4**

For all `event_report` messages `msg` successfully processed:
- Database record SHALL contain `event_type` matching `msg.event`
- AND `event_type` SHALL be one of the valid event types

**Property 6.3: 转发事件必须保留原始格式**

**Validates: Requirements 6.5**

For all `event_report` messages `msg` forwarded to App:
- Forwarded message SHALL contain `event` and `param` fields
- AND field values SHALL match the original message

### 5.7 user_mgmt_result 特殊场景属性

**Property 7.1: "Already exists" 场景必须被识别**

**Validates: Requirements 7.1**

For all `user_mgmt_result` messages `msg` where `msg.result == true` AND `msg.msg == "Already exists"`:
- Server SHALL recognize this as a special success scenario
- AND Server SHALL log the scenario for debugging

**Property 7.2: "ID occupied" 场景必须被识别**

**Validates: Requirements 7.2**

For all `user_mgmt_result` messages `msg` where `msg.result == true` AND `msg.msg == "ID occupied, auto assigned"`:
- Server SHALL recognize this as a special success scenario
- AND Server SHALL log the scenario for debugging

**Property 7.3: 特殊场景必须保留原始 msg**

**Validates: Requirements 7.3**

For all `user_mgmt_result` messages `msg` in special success scenarios:
- Forwarded message SHALL preserve the original `msg` field
- AND App SHALL receive the exact `msg` value

### 5.8 数据库更新属性

**Property 8.1: unlock_logs 表必须包含新字段**

**Validates: Requirements 8.1, 8.2**

For any Server instance:
- On startup, Server SHALL check if `unlock_logs` table contains `status` and `lock_time` columns
- AND IF columns are missing THEN Server SHALL execute migration script
- AND IF migration fails THEN Server SHALL log error but continue running

**Property 8.2: door_opened_logs 表必须存在**

**Validates: Requirements 8.3**

For any Server instance:
- On startup, Server SHALL check if `door_opened_logs` table exists
- AND IF table is missing THEN Server SHALL create the table
- AND table SHALL contain `device_id`, `method`, `source`, `created_at` columns

**Property 8.3: device_events 表必须支持新事件类型**

**Validates: Requirements 8.4**

For any Server instance:
- `device_events` table SHALL support event types: "door_closed", "lock_success", "bolt_alarm"
- AND Server SHALL be able to insert records with these event types

**Property 8.4: 数据库失败不影响转发**

**Validates: Requirements 8.5**

For all messages `msg` where database operation fails:
- Server SHALL log the error
- AND Server SHALL continue to forward the message to App
- AND Server SHALL NOT throw exception

### 5.9 消息处理健壮性属性

**Property 9.1: 格式错误的 JSON 必须被拒绝**

**Validates: Requirements 9.1**

For all text messages `msg` received from ESP32:
- IF `msg` is not valid JSON
- THEN Server SHALL log error and discard the message
- AND Server SHALL NOT crash or throw exception

**Property 9.2: 未知消息类型必须被记录**

**Validates: Requirements 9.2**

For all JSON messages `msg` where `msg.type` is not recognized:
- Server SHALL log warning with message type
- AND Server SHALL discard the message

**Property 9.3: 缺少必需字段必须被拒绝**

**Validates: Requirements 9.3**

For all messages `msg` of known type:
- IF `msg` is missing required fields
- THEN Server SHALL log error with missing field names
- AND Server SHALL reject the message

**Property 9.4: 转发失败必须重试**

**Validates: Requirements 9.5**

For all messages `msg` where forwarding to App fails:
- Server SHALL log error with failure reason
- AND Server SHALL retry up to 3 times
- AND IF all retries fail THEN Server SHALL log final error

### 5.10 日志与监控属性

**Property 10.1: esp32_ack 必须被记录**

**Validates: Requirements 10.1**

For all `esp32_ack` messages `msg` received:
- Server SHALL log the message with DEBUG level
- AND log SHALL contain `seq_id` and `code` fields

**Property 10.2: 新版 log_report 必须被记录**

**Validates: Requirements 10.2**

For all `log_report` messages `msg` with `status` field:
- Server SHALL log the message with INFO level
- AND log SHALL contain `status` and `lock_time` fields

**Property 10.3: 新增消息类型必须被标注**

**Validates: Requirements 10.3**

For all messages `msg` where `msg.type` in ["esp32_ack", "door_opened_report", "password_report"]:
- Server SHALL log the message with message type annotation
- AND log SHALL clearly indicate this is a v5.2 message type

---

## 6. 错误处理

### 6.1 三级确认与错误传递

**设计原则**：
1. **Server 内部重试对 App 透明**：App 只收到最终结果
2. **错误必须传递给 App**：无论是 Server 错误还是 ESP32/STM32 错误
3. **统一错误码**：使用 0-10 的错误码体系

**错误传递流程**：

```
App                    Server                  ESP32                   STM32
 │                       │                       │                       │
 │ ① 命令 (seq_id=xxx)   │                       │                       │
 │──────────────────────>│                       │                       │
 │                       │                       │                       │
 │                       │ ② 转发命令（重试3次） │                       │
 │                       │──────────────────────>│                       │
 │                       │                       │                       │
 │                       │ ③ esp32_ack (code=0)  │                       │
 │                       │<──────────────────────│                       │
 │                       │                       │                       │
 │ ④ esp32_ack 转发      │                       │                       │
 │<──────────────────────│                       │                       │
 │                       │                       │                       │
 │                       │                       │ ⑤ UART 命令           │
 │                       │                       │──────────────────────>│
 │                       │                       │                       │
 │                       │                       │ ⑥ UART 响应（错误）   │
 │                       │                       │<──────────────────────│
 │                       │                       │                       │
 │                       │ ⑦ ack (code=6, 硬件故障)                      │
 │                       │<──────────────────────│                       │
 │                       │                       │                       │
 │ ⑧ ack 转发（错误）    │                       │                       │
 │<──────────────────────│                       │                       │
 │                       │                       │                       │
 │ ⑨ App 展示错误        │                       │                       │
```

**超时场景**：

```
App                    Server                  ESP32
 │                       │                       │
 │ ① 命令 (seq_id=xxx)   │                       │
 │──────────────────────>│                       │
 │                       │                       │
 │                       │ ② 转发命令（第1次）   │
 │                       │──────────────────────>│
 │                       │                       │
 │                       │     ... 2秒超时 ...   │
 │                       │                       │
 │                       │ ③ 转发命令（第2次）   │
 │                       │──────────────────────>│
 │                       │                       │
 │                       │     ... 2秒超时 ...   │
 │                       │                       │
 │                       │ ④ 转发命令（第3次）   │
 │                       │──────────────────────>│
 │                       │                       │
 │                       │     ... 2秒超时 ...   │
 │                       │                       │
 │ ⑤ 错误响应 (code=5)   │                       │
 │<──────────────────────│                       │
 │                       │                       │
 │ ⑥ App 展示"设备无响应"│                       │
```

### 6.2 消息解析错误

| 错误类型 | 处理策略 | 日志级别 | 通知 App |
|----------|----------|----------|----------|
| JSON 解析失败 | 丢弃消息，记录错误 | ERROR | 否 |
| 缺少 type 字段 | 丢弃消息，记录错误 | ERROR | 否 |
| 未知 type 值 | 丢弃消息，记录警告 | WARNING | 否 |
| 缺少必需字段 | 拒绝处理，记录错误 | ERROR | 是（如果是命令） |
| 字段类型错误 | 拒绝处理，记录错误 | ERROR | 是（如果是命令） |

**实现示例**：

```python
async def handleTextMessage(conn, message: str):
    try:
        msg_json = json.loads(message)
    except json.JSONDecodeError as e:
        conn.logger.bind(tag=TAG).error(f"JSON 解析失败: {e}")
        return
    
    msg_type = msg_json.get("type")
    if not msg_type:
        conn.logger.bind(tag=TAG).error("缺少 type 字段")
        return
    
    handler = get_handler(msg_type)
    if not handler:
        conn.logger.bind(tag=TAG).warning(f"未知消息类型: {msg_type}")
        return
    
    try:
        await handler.handle(conn, msg_json)
    except KeyError as e:
        conn.logger.bind(tag=TAG).error(f"缺少必需字段: {e}")
        # 如果是 App 发送的命令，返回错误
        if msg_type in ["lock_control", "dev_control", "user_mgmt"]:
            await send_command_error(conn, msg_type, f"缺少必需字段: {e}", code=3)
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"处理消息失败: {e}")
        if msg_type in ["lock_control", "dev_control", "user_mgmt"]:
            await send_command_error(conn, msg_type, f"处理失败: {e}", code=10)
```

### 6.3 命令下发错误

| 错误场景 | 错误码 | 处理策略 | 重试 |
|----------|--------|----------|------|
| ESP32 离线 | 1 | 立即返回错误给 App | 否 |
| 等待 esp32_ack 超时 | 5 | 重试3次，失败后返回错误 | 是 |
| esp32_ack code != 0 | 根据 code | 立即返回错误给 App | 否 |
| 等待 ack 超时 | 5 | 返回错误给 App | 否 |
| ack code != 0 | 根据 code | 转发错误给 App | 否 |

**错误响应格式**：

```python
async def send_command_error(conn, cmd_type: str, message: str, code: int):
    """发送命令错误响应给 App
    
    Args:
        conn: App 连接对象
        cmd_type: 命令类型（lock_control/dev_control/user_mgmt）
        message: 错误消息
        code: 统一错误码（0-10）
    """
    try:
        await conn.websocket.send(json.dumps({
            "type": cmd_type,
            "status": "error",
            "code": code,
            "message": message
        }))
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"发送错误响应失败: {e}")
```

### 6.4 数据库错误

| 错误类型 | 处理策略 | 影响范围 | 通知 App |
|----------|----------|----------|----------|
| 连接失败 | 记录错误，继续转发 | 仅影响存储 | 否 |
| 插入失败 | 记录错误，继续转发 | 仅影响存储 | 否 |
| 表不存在 | 记录错误，尝试创建 | 仅影响存储 | 否 |
| 字段不存在 | 记录错误，尝试迁移 | 仅影响存储 | 否 |

**设计原则**：数据库故障不应阻塞消息转发

**实现示例**：

```python
async def _save_to_database(self, conn, ...):
    try:
        db = _get_database(conn)
        if db:
            db.save_unlock_log(...)
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"保存到数据库失败: {e}")
        # 不抛出异常，继续执行
```

### 6.5 转发错误

| 错误类型 | 处理策略 | 重试次数 | 通知发送方 |
|----------|----------|----------|------------|
| App 连接断开 | 跳过该连接，继续转发其他 | 0 | 否 |
| 发送超时 | 重试，记录错误 | 3 | 否 |
| 序列化失败 | 记录错误，跳过 | 0 | 否 |

**实现示例**：

```python
async def _forward_to_apps(self, conn, msg_json: Dict[str, Any]):
    manager = ConnectionManager.get_instance()
    app_conns = manager.get_app_conns(conn.device_id)
    
    if not app_conns:
        return
    
    msg = json.dumps(msg_json)
    failed_conns = []
    
    for app_conn in app_conns:
        if not app_conn.websocket:
            continue
        
        retry_count = 0
        while retry_count < 3:
            try:
                await app_conn.websocket.send(msg)
                break
            except Exception as e:
                retry_count += 1
                if retry_count >= 3:
                    conn.logger.bind(tag=TAG).error(
                        f"转发失败（重试 {retry_count} 次）: {e}"
                    )
                    failed_conns.append(app_conn)
```

### 6.6 错误码验证

**服务器端职责**：
- ✅ **接收统一错误码**：ESP32 已经完成了错误码映射，服务器端接收到的是 0-10 的统一错误码
- ✅ **验证错误码范围**：检查 code 是否在 0-10 范围内
- ✅ **记录异常错误码**：如果 code 超出范围，记录警告日志

**AckHandler 错误码验证**：

```python
from core.constants.error_codes import is_valid_error_code, get_error_message

class AckHandler(TextMessageHandler):
    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        seq_id = msg_json.get("seq_id") or msg_json.get("msg_id")
        code = msg_json.get("code", 0)
        msg = msg_json.get("msg", "")
        
        # 验证错误码范围
        if not is_valid_error_code(code):
            conn.logger.bind(tag=TAG).warning(
                f"无效的错误码: seq_id={seq_id}, code={code}"
            )
        
        # 记录日志
        if code == 0:
            conn.logger.bind(tag=TAG).debug(f"ACK 成功: seq_id={seq_id}")
        else:
            error_msg = get_error_message(code)
            conn.logger.bind(tag=TAG).warning(
                f"ACK 失败: seq_id={seq_id}, code={code} ({error_msg}), msg={msg}"
            )
        
        # 执行等待回调（如果有）
        if hasattr(conn, "_pending_commands") and seq_id in conn._pending_commands:
            callback = conn._pending_commands.pop(seq_id)
            if callback:
                await callback(code, msg)
        
        # 必须转发 ACK 给关联的 App（包括错误情况）
        await self._forward_to_apps(conn, msg_json)
```

**关键点**：
1. 使用 `is_valid_error_code()` 验证错误码范围
2. 使用 `get_error_message()` 获取友好的错误消息
3. 超出范围的错误码记录警告，但仍然转发给 App

### 6.7 AckHandler 错误处理

**更新 AckHandler**：

```python
from core.constants.error_codes import is_valid_error_code, get_error_message

class AckHandler(TextMessageHandler):
    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        seq_id = msg_json.get("seq_id") or msg_json.get("msg_id")
        code = msg_json.get("code", 0)
        msg = msg_json.get("msg", "")
        
        # 验证错误码（ESP32 已完成映射，这里只验证范围）
        if not is_valid_error_code(code):
            conn.logger.bind(tag=TAG).warning(
                f"无效的错误码: seq_id={seq_id}, code={code}"
            )
        
        # 记录日志
        if code == 0:
            conn.logger.bind(tag=TAG).debug(f"ACK 成功: seq_id={seq_id}")
        else:
            error_msg = get_error_message(code)
            conn.logger.bind(tag=TAG).warning(
                f"ACK 失败: seq_id={seq_id}, code={code} ({error_msg}), msg={msg}"
            )
        
        # 执行等待回调（如果有）
        if hasattr(conn, "_pending_commands") and seq_id in conn._pending_commands:
            callback = conn._pending_commands.pop(seq_id)
            if callback:
                await callback(code, msg)
        
        # 必须转发 ACK 给关联的 App（包括错误情况）
        # App 需要知道命令执行结果，无论成功还是失败
        await self._forward_to_apps(conn, msg_json)
```

**关键点**：
1. **所有 ack 都必须转发给 App**，包括错误的 ack
2. **ESP32 已完成错误码映射**，服务器端只需验证范围
3. App 根据 code 判断命令执行结果
4. Server 不应该过滤或修改 ack 消息

---

## 7. 测试策略

### 7.1 单元测试

#### 7.1.1 消息处理器测试

**测试范围**：每个 Handler 的 handle() 方法

**测试用例**：

| Handler | 测试场景 | 预期结果 |
|---------|----------|----------|
| Esp32AckHandler | 正常消息 | 成功解析并转发 |
| Esp32AckHandler | 缺少 seq_id | 记录错误并拒绝 |
| Esp32AckHandler | code 超出范围 | 记录警告但继续处理 |
| DoorOpenedReportHandler | 正常消息 | 存储到数据库并转发 |
| DoorOpenedReportHandler | 无效 source | 记录错误并拒绝 |
| PasswordReportHandler | 正常消息 | 仅转发不存储 |
| LogReportHandler | status=success | 正确解析并存储 |
| LogReportHandler | status=locked | 正确解析 lock_time |
| LogReportHandler | 旧版 result | 兼容转换为 status |
| EventReportHandler | 新增事件类型 | 正确识别并存储 |

**测试框架**：pytest + pytest-asyncio

**示例测试**：

```python
import pytest
from unittest.mock import Mock, AsyncMock
from core.handle.textHandler.esp32AckHandler import Esp32AckHandler

@pytest.mark.asyncio
async def test_esp32_ack_handler_success():
    # Arrange
    handler = Esp32AckHandler()
    conn = Mock()
    conn.logger = Mock()
    conn.device_id = "test_device"
    
    msg_json = {
        "type": "esp32_ack",
        "seq_id": "1702234567890_0",
        "code": 0,
        "msg": "received"
    }
    
    # Act
    await handler.handle(conn, msg_json)
    
    # Assert
    conn.logger.bind().debug.assert_called_once()

@pytest.mark.asyncio
async def test_esp32_ack_handler_missing_seq_id():
    # Arrange
    handler = Esp32AckHandler()
    conn = Mock()
    conn.logger = Mock()
    
    msg_json = {
        "type": "esp32_ack",
        "code": 0,
        "msg": "received"
    }
    
    # Act & Assert
    with pytest.raises(KeyError):
        await handler.handle(conn, msg_json)
```

#### 7.1.2 错误码测试

**测试用例**：

```python
def test_error_code_mapping():
    assert map_esp32_error_code(0x00) == ErrorCode.SUCCESS
    assert map_esp32_error_code(0x01) == ErrorCode.DEVICE_BUSY
    assert map_esp32_error_code(0xFF) == ErrorCode.TIMEOUT
    assert map_esp32_error_code(0x99) == ErrorCode.INTERNAL_ERROR

def test_error_code_range():
    for code in range(11):
        assert code in ERROR_MESSAGES
```

### 7.2 集成测试

#### 7.2.1 端到端消息流测试

**测试场景**：模拟 ESP32 → Server → App 完整流程

**测试用例**：

| 场景 | 输入 | 预期输出 |
|------|------|----------|
| 两级确认流程 | lock_control 命令 | esp32_ack + ack |
| 开锁日志上报 | log_report (status) | 数据库记录 + App 转发 |
| 开门日志上报 | door_opened_report | 数据库记录 + App 转发 |
| 密码查询 | password_report | 仅 App 转发 |
| 新增事件上报 | event_report (door_closed) | 数据库记录 + App 转发 |

**测试框架**：pytest + websockets

**示例测试**：

```python
@pytest.mark.asyncio
async def test_two_level_ack_flow():
    # 启动测试服务器
    server = await start_test_server()
    
    # 模拟 ESP32 连接
    esp32_ws = await websockets.connect(server.url)
    
    # 模拟 App 连接
    app_ws = await websockets.connect(server.url)
    
    # App 发送 lock_control 命令
    cmd = {
        "type": "lock_control",
        "seq_id": "test_123",
        "command": "unlock"
    }
    await app_ws.send(json.dumps(cmd))
    
    # ESP32 接收命令
    received_cmd = await esp32_ws.recv()
    assert json.loads(received_cmd)["seq_id"] == "test_123"
    
    # ESP32 发送 esp32_ack
    esp32_ack = {
        "type": "esp32_ack",
        "seq_id": "test_123",
        "code": 0,
        "msg": "received"
    }
    await esp32_ws.send(json.dumps(esp32_ack))
    
    # App 接收 esp32_ack
    received_ack1 = await app_ws.recv()
    assert json.loads(received_ack1)["type"] == "esp32_ack"
    
    # ESP32 发送 ack
    ack = {
        "type": "ack",
        "seq_id": "test_123",
        "code": 0,
        "msg": "OK"
    }
    await esp32_ws.send(json.dumps(ack))
    
    # App 接收 ack
    received_ack2 = await app_ws.recv()
    assert json.loads(received_ack2)["type"] == "ack"
```

#### 7.2.2 数据库集成测试

**测试场景**：验证数据库操作

**测试用例**：

```python
@pytest.mark.asyncio
async def test_unlock_log_with_new_fields():
    # 发送 log_report
    msg = {
        "type": "log_report",
        "ts": 1702234567890,
        "data": {
            "method": "finger",
            "status": "locked",
            "uid": 5,
            "fail_count": 0,
            "lock_time": 10
        }
    }
    await esp32_ws.send(json.dumps(msg))
    
    # 验证数据库记录
    db = get_test_database()
    record = db.get_latest_unlock_log("test_device")
    assert record["status"] == "locked"
    assert record["lock_time"] == 10

@pytest.mark.asyncio
async def test_door_opened_log_creation():
    # 发送 door_opened_report
    msg = {
        "type": "door_opened_report",
        "ts": 1702234567890,
        "data": {
            "method": "finger",
            "source": "outside"
        }
    }
    await esp32_ws.send(json.dumps(msg))
    
    # 验证数据库记录
    db = get_test_database()
    record = db.get_latest_door_opened_log("test_device")
    assert record["method"] == "finger"
    assert record["source"] == "outside"
```

### 7.3 性能测试

#### 7.3.1 消息处理延迟

**测试目标**：验证消息处理延迟 < 50ms

**测试方法**：

```python
@pytest.mark.asyncio
async def test_message_processing_latency():
    latencies = []
    
    for i in range(1000):
        start_time = time.time()
        
        # 发送消息
        msg = {"type": "status_report", "ts": int(time.time() * 1000), ...}
        await esp32_ws.send(json.dumps(msg))
        
        # 等待转发
        await app_ws.recv()
        
        end_time = time.time()
        latencies.append((end_time - start_time) * 1000)
    
    avg_latency = sum(latencies) / len(latencies)
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
    
    assert avg_latency < 50, f"平均延迟 {avg_latency}ms 超过 50ms"
    assert p95_latency < 100, f"P95 延迟 {p95_latency}ms 超过 100ms"
```

#### 7.3.2 并发连接测试

**测试目标**：验证支持 1000 个并发连接

**测试方法**：

```python
@pytest.mark.asyncio
async def test_concurrent_connections():
    connections = []
    
    # 创建 1000 个连接
    for i in range(1000):
        ws = await websockets.connect(server.url)
        connections.append(ws)
    
    # 验证所有连接正常
    for ws in connections:
        await ws.send(json.dumps({"type": "heartbeat", ...}))
        response = await ws.recv()
        assert json.loads(response)["type"] == "heartbeat_ack"
    
    # 关闭连接
    for ws in connections:
        await ws.close()
```

### 7.4 兼容性测试

#### 7.4.1 旧版消息兼容

**测试场景**：验证对旧版 msg_id 和 result 字段的兼容

**测试用例**：

```python
@pytest.mark.asyncio
async def test_backward_compatibility_msg_id():
    # 发送旧版 ack（使用 msg_id）
    msg = {
        "type": "ack",
        "msg_id": "old_123",  # 旧版字段名
        "code": 0,
        "msg": "OK"
    }
    await esp32_ws.send(json.dumps(msg))
    
    # 验证服务器正确处理
    received = await app_ws.recv()
    assert "msg_id" in json.loads(received) or "seq_id" in json.loads(received)

@pytest.mark.asyncio
async def test_backward_compatibility_result():
    # 发送旧版 log_report（使用 result）
    msg = {
        "type": "log_report",
        "ts": 1702234567890,
        "data": {
            "method": "finger",
            "result": True,  # 旧版字段
            "uid": 5,
            "fail_count": 0
        }
    }
    await esp32_ws.send(json.dumps(msg))
    
    # 验证数据库记录
    db = get_test_database()
    record = db.get_latest_unlock_log("test_device")
    assert record["status"] == "success"  # 转换为新版
```

### 7.5 故障恢复测试

#### 7.5.1 数据库故障测试

**测试场景**：数据库不可用时，消息仍能转发

**测试用例**：

```python
@pytest.mark.asyncio
async def test_database_failure_resilience():
    # 模拟数据库故障
    with mock.patch('core.handle.textHandler.faceRecognitionHandler.get_face_service', return_value=None):
        # 发送 log_report
        msg = {
            "type": "log_report",
            "ts": 1702234567890,
            "data": {"method": "finger", "status": "success", ...}
        }
        await esp32_ws.send(json.dumps(msg))
        
        # 验证消息仍被转发到 App
        received = await app_ws.recv()
        assert json.loads(received)["type"] == "log_report"
```

#### 7.5.2 App 连接断开测试

**测试场景**：部分 App 断开时，其他 App 仍能接收消息

**测试用例**：

```python
@pytest.mark.asyncio
async def test_partial_app_disconnection():
    # 创建 3 个 App 连接
    app1 = await websockets.connect(server.url)
    app2 = await websockets.connect(server.url)
    app3 = await websockets.connect(server.url)
    
    # 断开 app2
    await app2.close()
    
    # 发送消息
    msg = {"type": "status_report", ...}
    await esp32_ws.send(json.dumps(msg))
    
    # 验证 app1 和 app3 仍能接收
    received1 = await app1.recv()
    received3 = await app3.recv()
    assert json.loads(received1)["type"] == "status_report"
    assert json.loads(received3)["type"] == "status_report"
```

---

## 8. 实现计划

### 8.1 实施阶段

#### 阶段 1: 基础设施（P0）

**时间**：1-2 天

**任务**：
1. 创建错误码常量文件 `error_codes.py`
2. 更新 `TextMessageType` 枚举
3. 创建数据库迁移脚本

**交付物**：
- `core/constants/error_codes.py`
- 更新的 `core/handle/textMessageType.py`
- 数据库迁移脚本

#### 阶段 2: 核心消息处理（P0）

**时间**：3-4 天

**任务**：
1. 实现 `Esp32AckHandler`
2. 实现 `DoorOpenedReportHandler`
3. 实现 `PasswordReportHandler`
4. 更新 `AckHandler`
5. 更新 `LogReportHandler`
6. 更新 `EventReportHandler`
7. 更新消息路由表

**交付物**：
- 3 个新 Handler 文件
- 3 个更新的 Handler 文件
- 更新的 `textHandle.py`

#### 阶段 3: 数据库集成（P1）

**时间**：2-3 天

**任务**：
1. 执行数据库迁移
2. 实现数据库访问方法
3. 集成到 Handler 中

**交付物**：
- 更新的数据库表结构
- 新增的数据库访问方法

#### 阶段 4: 测试与验证（P1）

**时间**：3-4 天

**任务**：
1. 编写单元测试
2. 编写集成测试
3. 执行性能测试
4. 执行兼容性测试

**交付物**：
- 完整的测试套件
- 测试报告

#### 阶段 5: 日志与监控（P2）

**时间**：1-2 天

**任务**：
1. 增强日志输出
2. 添加监控指标
3. 更新文档

**交付物**：
- 增强的日志记录
- 监控指标定义
- 更新的文档

### 8.2 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 数据库迁移失败 | 高 | 中 | 提供回滚脚本，支持降级运行 |
| 旧版消息兼容问题 | 中 | 低 | 充分测试，保留兼容代码 |
| 性能下降 | 中 | 低 | 性能测试，优化关键路径 |
| ESP32 协议不一致 | 高 | 低 | 与 ESP32 团队对齐协议 |

### 8.3 验收标准

#### 功能验收

- [ ] 所有 P0 需求的验收标准通过
- [ ] 所有 P1 需求的验收标准通过
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试全部通过

#### 性能验收

- [ ] 消息处理延迟 < 50ms (P95)
- [ ] 支持 1000 个并发连接
- [ ] 数据库写入延迟 < 100ms (P95)

#### 兼容性验收

- [ ] 旧版 msg_id 消息正常处理
- [ ] 旧版 result 字段正常转换
- [ ] 数据库故障不影响转发

---

## 9. 附录

### 9.1 文件清单

#### 新增文件

| 文件路径 | 说明 |
|----------|------|
| `core/constants/error_codes.py` | 统一错误码定义 |
| `core/handle/textHandler/esp32AckHandler.py` | esp32_ack 处理器 |
| `core/handle/textHandler/doorOpenedReportHandler.py` | door_opened_report 处理器 |
| `core/handle/textHandler/passwordReportHandler.py` | password_report 处理器 |
| `migrations/upgrade_v5.0_to_v5.2.sql` | 数据库迁移脚本 |

#### 修改文件

| 文件路径 | 变更说明 |
|----------|----------|
| `core/handle/textMessageType.py` | 新增消息类型枚举 |
| `core/handle/textHandle.py` | 更新消息路由表 |
| `core/handle/textHandler/ackHandler.py` | 支持 seq_id，验证错误码 |
| `core/handle/textHandler/logReportHandler.py` | 支持 status 和 lock_time |
| `core/handle/textHandler/eventReportHandler.py` | 支持新增事件类型 |

### 9.2 数据库迁移脚本

**文件路径**：`migrations/upgrade_v5.0_to_v5.2.sql`

```sql
-- 升级 unlock_logs 表
ALTER TABLE unlock_logs 
ADD COLUMN status VARCHAR(16) DEFAULT 'success' AFTER result,
ADD COLUMN lock_time INT DEFAULT 0 AFTER status;

-- 迁移旧数据
UPDATE unlock_logs 
SET status = CASE 
    WHEN result = 1 THEN 'success' 
    ELSE 'fail' 
END
WHERE status = 'success';

-- 添加索引
CREATE INDEX idx_status ON unlock_logs(status);

-- 创建 door_opened_logs 表
CREATE TABLE IF NOT EXISTS door_opened_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL COMMENT '设备 ID',
    method VARCHAR(16) NOT NULL COMMENT '开锁方式',
    source VARCHAR(16) NOT NULL COMMENT '开门来源: outside/inside/unknown',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_device_time (device_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='开门日志表';

-- 更新 device_events 表（如果使用 ENUM）
ALTER TABLE device_events 
MODIFY COLUMN event_type VARCHAR(32) NOT NULL;
```

### 9.3 配置示例

**config.yaml 无需修改**，所有变更在代码层面实现。

### 9.4 参考文档

1. **协议规范**：
   - `docs/my_docs/智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md`
   - `docs/my_docs/服务器端协议升级需求-v5.0到v5.2.md`

2. **需求文档**：
   - `.kiro/specs/protocol-upgrade-v5.0-to-v5.2/requirements.md`

3. **代码规范**：
   - `.kiro/steering/tech.md`
   - `.kiro/steering/structure.md`

---

## 10. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-01-17 | 初始版本，基于需求文档 v1.0 |

---

**文档维护者**: 毕业设计项目组  
**最后更新**: 2026-01-17
