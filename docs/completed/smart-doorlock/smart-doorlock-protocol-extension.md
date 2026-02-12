# 智能门锁协议扩展实现方案

## 概述

本文档描述在现有 xiaozhi-server 通信协议基础上进行的扩展，以支持智能猫眼门锁功能。

**核心原则**：最小修改、最大复用，在现有完善的通信协议代码基础上进行消息解析扩展。

---

## 1. 系统架构

### 1.1 整体架构

```
┌─────────────┐                                           ┌─────────────┐
│   ESP32     │                                           │    App      │
│  (门锁端)   │                                           │  (用户端)   │
└──────┬──────┘                                           └──────┬──────┘
       │                                                         │
       │  WebSocket                                   WebSocket  │
       │                                                         │
       ▼                                                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        xiaozhi-server                                │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    ConnectionManager                           │  │
│  │  - esp32_connections: Dict[device_id, Connection]              │  │
│  │  - app_connections: Dict[device_id, List[Connection]]          │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─────────────────────┐    ┌─────────────────────────────────────┐  │
│  │   ModeController    │    │       DeviceStateStore              │  │
│  │  - current_mode     │    │  - 锁状态、电量、传感器数据等       │  │
│  │  - switch_mode()    │    │  - 基于现有 iot_descriptors 扩展    │  │
│  └─────────────────────┘    └─────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 工作模式

| 模式 | 说明 | 二进制消息处理 | 文本消息处理 |
|------|------|----------------|--------------|
| **正常模式** | 现有功能 | 音频 → ASR → LLM → TTS | 现有处理 + 扩展 |
| **监控模式** | 实时监控 | 音频/视频 → 转发给 App | 控制命令转发 |

---

## 2. App 连接方式对比

### 方案对比

| 对比项 | 方案A: 共用端点 | 方案B: 独立端点 |
|--------|----------------|----------------|
| **端点** | `/ws/xiaozhi` | ESP32: `/ws/xiaozhi`<br>App: `/ws/app` |
| **设备区分** | headers 或 hello 消息中的 `client_type` 字段 | URL 路径自动区分 |
| **代码改动** | 较小，复用现有 ConnectionHandler | 较大，需要新建 AppConnectionHandler |
| **消息路由** | 同一 Handler 内部判断 | 不同 Handler 各自处理 |
| **连接管理** | 需要在 ConnectionHandler 中区分处理 | 天然分离，逻辑清晰 |
| **协议一致性** | 高，ESP32 和 App 使用相同协议 | 可以针对 App 优化协议 |
| **调试难度** | 稍高，需要区分日志来源 | 较低，日志天然分离 |
| **扩展性** | 一般 | 好，App 端可独立演进 |

### 推荐方案

**推荐方案B（独立端点）**，理由：

1. **职责分离** - ESP32 和 App 的消息处理逻辑差异较大
2. **代码清晰** - 不需要在每个处理逻辑中判断客户端类型
3. **独立演进** - App 端协议可以根据需要独立优化
4. **现有代码影响小** - 现有 ESP32 处理逻辑基本不变

### 方案B 实现要点

```python
# websocket_server.py 中添加路由
async def handler(websocket, path):
    if path.startswith("/ws/xiaozhi"):
        # ESP32 连接 - 使用现有 ConnectionHandler
        conn = ConnectionHandler(config, ...)
        await conn.handle_connection(websocket)
    elif path.startswith("/ws/app"):
        # App 连接 - 使用新的 AppConnectionHandler
        conn = AppConnectionHandler(config, ...)
        await conn.handle_connection(websocket)
```

---

## 3. 现有状态存储机制分析

### 3.1 现有实现：IoT Descriptors

xiaozhi-server 已有 IoT 设备状态管理机制：

**文件位置**：`core/providers/tools/device_iot/`

```python
# iot_descriptor.py - 设备描述符
class IotDescriptor:
    def __init__(self, name, description, properties, methods):
        self.name = name
        self.description = description
        self.properties = []  # 属性列表，包含 name, description, value
        self.methods = []     # 方法列表

# iot_handler.py - 状态处理
async def handleIotStatus(conn, states):
    """处理物联网状态更新"""
    for state in states:
        for key, value in conn.iot_descriptors.items():
            if key == state["name"]:
                # 更新属性值
                for property_item in value.properties:
                    for k, v in state["state"].items():
                        if property_item["name"] == k:
                            property_item["value"] = v
```

**消息格式**：
```json
{
  "type": "iot",
  "descriptors": [...],  // 设备描述符注册
  "states": [...]        // 状态更新
}
```

### 3.2 扩展方案

可以复用现有 IoT 机制，为门锁定义专用描述符：

```json
{
  "type": "iot",
  "descriptors": [{
    "name": "smart_doorlock",
    "description": "智能门锁",
    "properties": {
      "lock_state": {"description": "锁状态", "type": "string"},
      "battery": {"description": "电量百分比", "type": "number"},
      "door_state": {"description": "门状态", "type": "string"},
      "last_unlock_time": {"description": "最后解锁时间", "type": "string"}
    },
    "methods": {
      "unlock": {"description": "解锁", "parameters": {}},
      "lock": {"description": "上锁", "parameters": {}}
    }
  }]
}
```

---

## 4. 协议扩展设计

### 4.1 二进制协议（BinaryProtocol2）

**协议结构（16字节头部 + 负载）：**
```c
struct BinaryProtocol2 {
    uint16_t version;      // 协议版本 (2)
    uint16_t type;         // 消息类型 (0: OPUS/VIDEO, 1: JSON)
    uint32_t reserved;     // 保留字段 - 用于区分音频和视频
    uint32_t timestamp;    // 时间戳（毫秒）
    uint32_t payload_size; // 负载大小（字节）
    uint8_t payload[];     // 负载数据
} __attribute__((packed));
```

**数据类型区分：**
| type | reserved | 数据类型 |
|------|----------|----------|
| 0 | 0 | OPUS 音频 |
| 0 | ≠0 | JPEG 视频（reserved = width<<16 \| height）|
| 1 | - | JSON 文本 |

### 4.2 文本消息扩展

#### 4.2.1 系统命令（新增 type: system）

```json
// 启动监控模式
{"type": "system", "command": "start_monitor"}

// 停止监控模式
{"type": "system", "command": "stop_monitor"}
```

#### 4.2.2 消息转发机制

**ESP32 → Server → App 转发：**
```json
// ESP32 发送（带 forward 标记）
{
  "type": "status",
  "forward": true,
  "data": {
    "battery": 85,
    "lock_state": "locked",
    "door_state": "closed"
  }
}

// Server 转发给 App（删除 forward 字段）
{
  "type": "status",
  "data": {
    "battery": 85,
    "lock_state": "locked",
    "door_state": "closed"
  }
}
```

**App → Server → ESP32 转发：**
```json
// App 发送控制命令
{
  "type": "control",
  "forward": true,
  "command": "unlock",
  "params": {}
}

// Server 转发给 ESP32
{
  "type": "control",
  "command": "unlock",
  "params": {}
}
```

---

## 5. 消息流向设计

### 5.1 正常模式

```
┌─────────┐                  ┌─────────┐                  ┌─────────┐
│  ESP32  │                  │ Server  │                  │   App   │
└────┬────┘                  └────┬────┘                  └────┬────┘
     │                            │                            │
     │  音频数据                  │                            │
     │ ─────────────────────────► │                            │
     │                            │ ASR → LLM → TTS            │
     │  TTS 音频                  │                            │
     │ ◄───────────────────────── │                            │
     │                            │                            │
     │  状态上报 (forward:true)   │                            │
     │ ─────────────────────────► │ 存储状态                   │
     │                            │ ─────────────────────────► │
     │                            │                            │
     │                            │  控制命令 (forward:true)   │
     │  控制命令                  │ ◄───────────────────────── │
     │ ◄───────────────────────── │                            │
     │                            │                            │
```

### 5.2 监控模式

```
┌─────────┐                  ┌─────────┐                  ┌─────────┐
│  ESP32  │                  │ Server  │                  │   App   │
└────┬────┘                  └────┬────┘                  └────┬────┘
     │                            │                            │
     │                            │  start_monitor             │
     │  start_monitor             │ ◄───────────────────────── │
     │ ◄───────────────────────── │                            │
     │                            │                            │
     │  音频/视频数据             │                            │
     │ ─────────────────────────► │ 直接转发                   │
     │                            │ ─────────────────────────► │
     │                            │                            │
     │                            │  音频数据（对讲）          │
     │  音频数据                  │ ◄───────────────────────── │
     │ ◄───────────────────────── │                            │
     │                            │                            │
     │                            │  stop_monitor              │
     │  stop_monitor              │ ◄───────────────────────── │
     │ ◄───────────────────────── │                            │
     │                            │                            │
```

---

## 6. 模式切换处理

### 6.1 切换时的任务处理

**从正常模式 → 监控模式：**

```python
async def switch_to_monitor_mode(conn):
    """切换到监控模式"""
    # 1. 标记模式切换
    conn.mode_switching = True
    conn.current_mode = "monitor"
    
    # 2. 处理正在进行的任务
    if conn.tts and conn.tts.is_speaking:
        # 方案A: 暂停 TTS 输出，缓存剩余音频
        conn.pending_tts_audio = conn.tts.get_remaining_audio()
        conn.tts.pause()
        
        # 方案B: 直接丢弃剩余音频
        # conn.tts.stop()
    
    # 3. 停止 ASR 处理（监控模式不需要语音识别）
    if conn.asr:
        conn.asr.pause()
    
    # 4. 通知 ESP32 进入监控模式
    await conn.websocket.send(json.dumps({
        "type": "system",
        "command": "start_monitor"
    }))
    
    conn.mode_switching = False
```

**从监控模式 → 正常模式：**

```python
async def switch_to_normal_mode(conn):
    """切换到正常模式"""
    conn.mode_switching = True
    conn.current_mode = "normal"
    
    # 1. 通知 ESP32 退出监控模式
    await conn.websocket.send(json.dumps({
        "type": "system",
        "command": "stop_monitor"
    }))
    
    # 2. 恢复 ASR
    if conn.asr:
        conn.asr.resume()
    
    # 3. 恢复之前暂停的 TTS（可选）
    if hasattr(conn, 'pending_tts_audio') and conn.pending_tts_audio:
        conn.tts.play(conn.pending_tts_audio)
        conn.pending_tts_audio = None
    
    conn.mode_switching = False
```

### 6.2 TTS 音频处理策略对比

| 策略 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **暂停并缓存** | 用户体验好，不丢失信息 | 实现复杂，占用内存 | 短时间监控 |
| **直接丢弃** | 实现简单 | 可能丢失重要信息 | 紧急监控场景 |
| **完成后切换** | 信息完整 | 切换延迟 | 非紧急场景 |

**建议**：默认使用"直接丢弃"策略，简化实现。如果是用户主动触发的监控（如门铃响），通常意味着需要立即查看，此时丢弃正在播放的内容是合理的。

---

## 7. 修改文件清单

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `core/handle/textMessageType.py` | 修改 | 新增 SYSTEM 枚举值 |
| `core/handle/textHandler/systemMessageHandler.py` | 新增 | system 命令处理器 |
| `core/handle/textMessageHandlerRegistry.py` | 修改 | 注册 SystemTextMessageHandler |
| `core/connection.py` | 修改 | 扩展二进制协议解析，新增模式管理 |
| `core/app_connection.py` | 新增 | App 端连接处理器 |
| `websocket_server.py` | 修改 | 添加 App 端点路由 |
| `core/connection_manager.py` | 新增 | 连接管理器，维护设备映射关系 |

---

## 8. 确定的设计决策

| 决策项 | 选择 | 说明 |
|--------|------|------|
| App 连接方式 | 方案B（独立端点） | `/ws/app` 独立端点 |
| TTS 音频处理 | 直接丢弃 | 模式切换时丢弃正在播放的音频 |
| App 认证 | 简单验证 | 通过 device_id 配对，验证 ESP32 是否在线 |
| 多 App 连接 | 允许 | 广播模式，方便演示 |
| 视频处理 | 直接转发 | 不做转码，保持简单 |

---

## 9. 简化的认证流程

### App 连接认证

```
App                          Server                        ESP32
 │                              │                             │
 │  连接 /ws/app                │                             │
 │ ────────────────────────────►│                             │
 │                              │                             │
 │  hello {device_id: "xxx"}    │                             │
 │ ────────────────────────────►│                             │
 │                              │ 检查 device_id              │
 │                              │ 对应的 ESP32 是否在线       │
 │                              │                             │
 │  hello_ack {status: "ok"}    │                             │
 │ ◄────────────────────────────│                             │
 │                              │                             │
```

### App Hello 消息格式

```json
{
  "type": "hello",
  "device_id": "AA:BB:CC:DD:EE:FF",
  "client_type": "app"
}
```

### 认证响应

```json
// 成功
{
  "type": "hello",
  "status": "ok",
  "device_info": {
    "online": true,
    "mode": "normal"
  }
}

// 失败
{
  "type": "hello",
  "status": "error",
  "message": "设备不在线"
}
```
