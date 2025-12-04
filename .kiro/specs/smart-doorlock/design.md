# Design Document

## Overview

本设计文档描述智能猫眼门锁服务器端功能扩展的技术实现方案。基于现有 xiaozhi-server 架构，通过最小化修改实现 ESP32 门锁设备与 App 客户端之间的实时通信、监控和控制功能。

### 核心设计原则

- **最小修改**：复用现有代码架构，仅扩展必要功能
- **职责分离**：ESP32 和 App 使用独立的连接处理器
- **简单可靠**：优先保证功能可用，避免过度设计

## Architecture

### 系统架构图

```
┌─────────────┐                                           ┌─────────────┐
│   ESP32     │                                           │    App      │
│  (门锁端)   │                                           │  (用户端)   │
└──────┬──────┘                                           └──────┬──────┘
       │                                                         │
       │  /ws/xiaozhi                                 /ws/app    │
       │                                                         │
       ▼                                                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        xiaozhi-server                                │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    ConnectionManager (新增)                    │  │
│  │  - esp32_connections: Dict[device_id, ConnectionHandler]       │  │
│  │  - app_connections: Dict[device_id, List[AppConnectionHandler]]│  │
│  │  - get_esp32_conn(device_id) / get_app_conns(device_id)        │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐  │
│  │  ConnectionHandler      │    │  AppConnectionHandler (新增)    │  │
│  │  (现有，小幅修改)       │    │  - 处理 App 连接                │  │
│  │  - 处理 ESP32 连接      │    │  - 转发音视频到 App             │  │
│  │  - 模式状态管理         │    │  - 接收 App 控制命令            │  │
│  └─────────────────────────┘    └─────────────────────────────────┘  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                  TextMessageProcessor (修改)                    │ │
│  │  - 优先处理 forward 字段                                        │ │
│  │  - 再进行 type 分发                                             │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### 消息流向

**正常模式：**
```
ESP32 音频 → Server → ASR → LLM → TTS → ESP32
ESP32 状态(forward) → Server(存储) → App
App 控制(forward) → Server → ESP32
```

**监控模式：**
```
ESP32 音频/视频 → Server → App (直接转发)
App 音频 → Server → ESP32 (双向对讲)
App 控制命令 → Server → ESP32
```

## Components and Interfaces

### 1. ConnectionManager (新增)

**文件**: `core/connection_manager.py`

```python
class ConnectionManager:
    """全局连接管理器，单例模式"""
    _instance = None
    
    def __init__(self):
        self.esp32_connections: Dict[str, ConnectionHandler] = {}
        self.app_connections: Dict[str, List[AppConnectionHandler]] = {}
    
    @classmethod
    def get_instance(cls) -> 'ConnectionManager':
        if cls._instance is None:
            cls._instance = ConnectionManager()
        return cls._instance
    
    def register_esp32(self, device_id: str, conn: ConnectionHandler):
        """注册 ESP32 连接"""
        
    def register_app(self, device_id: str, conn: AppConnectionHandler):
        """注册 App 连接"""
        
    def unregister_esp32(self, device_id: str):
        """注销 ESP32 连接"""
        
    def unregister_app(self, device_id: str, conn: AppConnectionHandler):
        """注销 App 连接"""
        
    def get_esp32_conn(self, device_id: str) -> Optional[ConnectionHandler]:
        """获取 ESP32 连接"""
        
    def get_app_conns(self, device_id: str) -> List[AppConnectionHandler]:
        """获取所有关联的 App 连接"""
        
    def is_esp32_online(self, device_id: str) -> bool:
        """检查 ESP32 是否在线"""
```

### 2. AppConnectionHandler (新增)

**文件**: `core/app_connection.py`

```python
class AppConnectionHandler:
    """App 端连接处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.websocket = None
        self.device_id = None
        self.authenticated = False
        self.logger = setup_logging()
    
    async def handle_connection(self, ws):
        """处理 App WebSocket 连接"""
        
    async def _route_message(self, message):
        """消息路由"""
        if isinstance(message, str):
            await self._handle_text_message(message)
        elif isinstance(message, bytes):
            await self._handle_binary_message(message)
    
    async def _handle_text_message(self, message: str):
        """处理文本消息"""
        
    async def _handle_binary_message(self, message: bytes):
        """处理二进制消息（App 发送的音频，用于对讲）"""
        
    async def send_to_esp32(self, message):
        """转发消息到 ESP32"""
        
    async def broadcast_to_apps(self, device_id: str, message):
        """广播消息到所有关联的 App"""
```

### 3. SystemTextMessageHandler (新增)

**文件**: `core/handle/textHandler/systemMessageHandler.py`

```python
class SystemTextMessageHandler(TextMessageHandler):
    """系统命令消息处理器"""
    
    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.SYSTEM
    
    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        command = msg_json.get("command")
        
        if command == "start_monitor":
            await self._start_monitor(conn)
        elif command == "stop_monitor":
            await self._stop_monitor(conn)
    
    async def _start_monitor(self, conn):
        """启动监控模式"""
        conn.current_mode = "monitor"
        # 停止 TTS 音频发送
        if conn.tts:
            conn.tts.stop_sending()
        # 通知 ESP32
        await self._notify_esp32(conn, "start_monitor")
        # 返回成功响应
        await conn.websocket.send(json.dumps({
            "type": "system",
            "status": "success",
            "command": "start_monitor"
        }))
    
    async def _stop_monitor(self, conn):
        """停止监控模式"""
        conn.current_mode = "normal"
        # 通知 ESP32
        await self._notify_esp32(conn, "stop_monitor")
        # 返回成功响应
        await conn.websocket.send(json.dumps({
            "type": "system",
            "status": "success",
            "command": "stop_monitor"
        }))
```

### 4. TextMessageProcessor (修改)

**文件**: `core/handle/textMessageProcessor.py`

```python
class TextMessageProcessor:
    async def process_message(self, conn, message: str) -> None:
        try:
            msg_json = json.loads(message)
            
            if isinstance(msg_json, dict):
                # 优先处理 forward 字段
                if msg_json.get("forward") == True:
                    await self._handle_forward(conn, msg_json)
                    return
                
                # 再进行 type 分发处理
                message_type = msg_json.get("type")
                handler = self.registry.get_handler(message_type)
                if handler:
                    await handler.handle(conn, msg_json)
                    
        except json.JSONDecodeError:
            conn.logger.error(f"解析消息失败: {message}")
    
    async def _handle_forward(self, conn, msg_json: Dict[str, Any]):
        """处理需要转发的消息"""
        # 删除 forward 字段
        del msg_json["forward"]
        forward_msg = json.dumps(msg_json, ensure_ascii=False)
        
        manager = ConnectionManager.get_instance()
        
        # 判断消息来源并转发
        if hasattr(conn, 'client_type') and conn.client_type == 'app':
            # App → ESP32
            esp32_conn = manager.get_esp32_conn(conn.device_id)
            if esp32_conn:
                await esp32_conn.websocket.send(forward_msg)
        else:
            # ESP32 → App
            app_conns = manager.get_app_conns(conn.device_id)
            for app_conn in app_conns:
                await app_conn.websocket.send(forward_msg)
```

### 5. ConnectionHandler (修改)

**文件**: `core/connection.py`

新增属性和方法：

```python
class ConnectionHandler:
    def __init__(self, ...):
        # ... 现有代码 ...
        
        # 新增：模式管理
        self.current_mode = "normal"  # "normal" | "monitor"
        
    async def _route_message(self, message):
        """消息路由（修改）"""
        if isinstance(message, str):
            await handleTextMessage(self, message)
        elif isinstance(message, bytes):
            # 检查是否为 BinaryProtocol2 格式
            if len(message) >= 16:
                await self._process_binary_protocol2(message)
            else:
                # 兼容旧格式
                if self.vad is not None and self.asr is not None:
                    self.asr_audio_queue.put(message)
    
    async def _process_binary_protocol2(self, message: bytes):
        """处理 BinaryProtocol2 格式的二进制消息"""
        # 解析16字节头部
        version = int.from_bytes(message[0:2], "big")
        msg_type = int.from_bytes(message[2:4], "big")
        reserved = int.from_bytes(message[4:8], "big")
        timestamp = int.from_bytes(message[8:12], "big")
        payload_size = int.from_bytes(message[12:16], "big")
        
        if version != 2:
            # 非 v2 协议，按旧方式处理
            self.asr_audio_queue.put(message)
            return
        
        payload = message[16:16 + payload_size]
        
        if msg_type == 0:
            if reserved == 0:
                # OPUS 音频
                await self._handle_audio_data(payload, timestamp)
            else:
                # JPEG 视频
                width = (reserved >> 16) & 0xFFFF
                height = reserved & 0xFFFF
                await self._handle_video_data(payload, timestamp, width, height)
    
    async def _handle_audio_data(self, audio_data: bytes, timestamp: int):
        """处理音频数据"""
        if self.current_mode == "monitor":
            # 监控模式：转发给 App
            await self._forward_to_apps(audio_data, is_video=False)
        else:
            # 正常模式：送入 ASR
            self._process_websocket_audio(audio_data, timestamp)
    
    async def _handle_video_data(self, jpeg_data: bytes, timestamp: int, width: int, height: int):
        """处理视频数据"""
        if self.current_mode == "monitor":
            # 监控模式：转发给 App
            await self._forward_to_apps(jpeg_data, is_video=True, width=width, height=height)
        # 正常模式：忽略视频数据
    
    async def _forward_to_apps(self, data: bytes, is_video: bool, width: int = 0, height: int = 0):
        """转发数据到所有关联的 App"""
        manager = ConnectionManager.get_instance()
        app_conns = manager.get_app_conns(self.device_id)
        for app_conn in app_conns:
            await app_conn.websocket.send(data)
```

## Data Models

### BinaryProtocol2 协议结构

```
+----------------+----------------+--------------------------------+
|   version(2)   |    type(2)     |         reserved(4)            |
|     0x0002     |     0x0000     |  音频:0 / 视频:(w<<16)|h       |
+----------------+----------------+--------------------------------+
|           timestamp(4)          |        payload_size(4)         |
+----------------+----------------+--------------------------------+
|                    payload data...                               |
+------------------------------------------------------------------+
```

### 文本消息格式

**系统命令：**
```json
{
  "type": "system",
  "command": "start_monitor" | "stop_monitor"
}
```

**转发消息：**
```json
{
  "type": "any",
  "forward": true,
  "...": "其他字段"
}
```

**App Hello 消息：**
```json
{
  "type": "hello",
  "device_id": "AA:BB:CC:DD:EE:FF",
  "client_type": "app"
}
```

### 设备状态数据

复用现有 `iot_descriptors` 机制：

```json
{
  "type": "iot",
  "states": [{
    "name": "smart_doorlock",
    "state": {
      "lock_state": "locked",
      "battery": 85,
      "door_state": "closed"
    }
  }]
}
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: App 认证验证

*For any* App 连接请求和 device_id，当 device_id 对应的 ESP32 在线时返回成功响应，否则返回错误响应。

**Validates: Requirements 1.2, 1.3**

### Property 2: 连接注册一致性

*For any* 连接（ESP32 或 App），注册后 ConnectionManager 中应包含该连接，注销后应不再包含。

**Validates: Requirements 2.1, 2.2, 2.3**

### Property 3: 多 App 广播

*For any* device_id 关联的多个 App 连接，当 ESP32 发送消息时，所有 App 都应收到该消息。

**Validates: Requirements 1.5, 5.1, 5.2**

### Property 4: 模式切换状态一致性

*For any* 模式切换命令（start_monitor/stop_monitor），执行后 current_mode 应正确更新，且 ESP32 应收到对应通知。

**Validates: Requirements 3.1, 3.2, 8.1, 8.2**

### Property 5: 监控模式数据转发

*For any* 处于监控模式的连接，ESP32 发送的音频/视频数据应转发给所有关联的 App，而非送入 ASR。

**Validates: Requirements 3.4, 4.5, 5.1, 5.2**

### Property 6: 双向对讲转发

*For any* 处于监控模式的连接，App 发送的音频数据应转发给 ESP32。

**Validates: Requirements 5.3**

### Property 7: BinaryProtocol2 解析正确性

*For any* 符合 BinaryProtocol2 格式的二进制消息，解析后应正确识别数据类型（音频/视频）和提取负载数据。

**Validates: Requirements 4.1, 4.2, 4.3**

### Property 8: 消息转发字段处理

*For any* 包含 `forward: true` 的文本消息，转发后的消息应不包含 forward 字段，且应发送到正确的目标端。

**Validates: Requirements 6.1, 6.2, 6.3, 6.4**

### Property 9: 无 forward 字段消息处理

*For any* 不包含 forward 字段的文本消息，应按 type 字段进行正常分发处理。

**Validates: Requirements 6.5**

### Property 10: 设备状态存储查询一致性

*For any* ESP32 上报的状态数据，存储后通过查询应能获取到相同的数据。

**Validates: Requirements 7.1, 7.2**

## Error Handling

### 连接错误处理

| 错误场景 | 处理方式 |
|----------|----------|
| App 连接时 ESP32 不在线 | 返回错误响应，关闭连接 |
| ESP32 断开连接 | 通知所有关联的 App，清理连接状态 |
| App 断开连接 | 从 app_connections 中移除 |
| 消息解析失败 | 记录日志，忽略该消息 |

### 模式切换错误处理

| 错误场景 | 处理方式 |
|----------|----------|
| 已处于目标模式 | 返回成功响应（幂等操作） |
| ESP32 不在线 | 返回错误响应 |

## Testing Strategy

### 单元测试

使用 pytest 进行单元测试：

1. **ConnectionManager 测试**
   - 测试连接注册/注销
   - 测试连接查询
   - 测试多 App 连接管理

2. **BinaryProtocol2 解析测试**
   - 测试音频数据解析
   - 测试视频数据解析
   - 测试无效数据处理

3. **TextMessageProcessor 测试**
   - 测试 forward 字段优先处理
   - 测试 type 分发处理

### 属性测试

使用 hypothesis 库进行属性测试：

**测试要求：**
- 每个属性测试运行至少 100 次迭代
- 每个属性测试需标注对应的正确性属性编号
- 格式：`**Feature: smart-doorlock, Property {number}: {property_text}**`

**属性测试示例：**

```python
from hypothesis import given, strategies as st

# **Feature: smart-doorlock, Property 7: BinaryProtocol2 解析正确性**
@given(
    version=st.just(2),
    msg_type=st.just(0),
    reserved=st.integers(min_value=0, max_value=0xFFFFFFFF),
    timestamp=st.integers(min_value=0, max_value=0xFFFFFFFF),
    payload=st.binary(min_size=0, max_size=1024)
)
def test_binary_protocol2_parsing(version, msg_type, reserved, timestamp, payload):
    """验证 BinaryProtocol2 解析正确性"""
    # 构造消息
    message = construct_binary_message(version, msg_type, reserved, timestamp, payload)
    
    # 解析消息
    parsed = parse_binary_protocol2(message)
    
    # 验证解析结果
    assert parsed.version == version
    assert parsed.msg_type == msg_type
    assert parsed.reserved == reserved
    assert parsed.timestamp == timestamp
    assert parsed.payload == payload
    
    # 验证数据类型识别
    if reserved == 0:
        assert parsed.data_type == "audio"
    else:
        assert parsed.data_type == "video"
        assert parsed.width == (reserved >> 16) & 0xFFFF
        assert parsed.height == reserved & 0xFFFF
```

### 集成测试

1. **端到端连接测试**
   - ESP32 连接 → App 连接 → 消息转发

2. **模式切换测试**
   - 正常模式 → 监控模式 → 正常模式

3. **音视频转发测试**
   - 监控模式下的数据流验证
