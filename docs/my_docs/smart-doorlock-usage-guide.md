# 智能门锁使用指南

## 概述

本文档说明如何使用智能门锁服务器端的各项功能。

---

## 1. 连接方式

### ESP32 连接
```
WebSocket 端点: ws://server:port/ws/xiaozhi
Headers:
  - device-id: AA:BB:CC:DD:EE:FF
```

### App 连接
```
WebSocket 端点: ws://server:port/ws/app

Hello 消息:
{
  "type": "hello",
  "device_id": "AA:BB:CC:DD:EE:FF",
  "client_type": "app"
}

响应:
{
  "type": "hello",
  "status": "ok",
  "device_info": {
    "online": true,
    "mode": "normal"
  }
}
```

---

## 2. 模式切换

### 启动监控模式
```json
{
  "type": "system",
  "command": "start_monitor"
}
```

### 停止监控模式
```json
{
  "type": "system",
  "command": "stop_monitor"
}
```

---

## 3. 设备状态管理

### 注册设备描述符（ESP32 发送）
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

### 上报状态（ESP32 发送）
```json
{
  "type": "iot",
  "forward": true,
  "states": [{
    "name": "smart_doorlock",
    "state": {
      "lock_state": "locked",
      "battery": 85,
      "door_state": "closed",
      "last_unlock_time": "2024-01-01 12:00:00"
    }
  }]
}
```

**说明**：
- 带 `forward: true` 的消息会自动转发给所有关联的 App
- 状态数据会存储在服务器的 `iot_descriptors` 中

---

## 4. 消息转发

### ESP32 → App
```json
{
  "type": "status",
  "forward": true,
  "data": {
    "battery": 85,
    "lock_state": "locked"
  }
}
```

### App → ESP32
```json
{
  "type": "control",
  "forward": true,
  "command": "unlock",
  "params": {}
}
```

**说明**：
- 带 `forward: true` 的消息会删除该字段后转发给目标端
- 不带 `forward` 字段的消息按 `type` 进行本地处理

---

## 5. 二进制协议（BinaryProtocol2）

### 协议格式
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

### 数据类型
| type | reserved | 数据类型 |
|------|----------|----------|
| 0 | 0 | OPUS 音频 |
| 0 | ≠0 | JPEG 视频（reserved = width<<16 \| height）|
| 1 | - | JSON 文本 |

### 示例：发送 640x480 视频帧
```c
uint16_t version = 2;
uint16_t type = 0;
uint32_t reserved = (640 << 16) | 480;  // 0x02800 1E0
uint32_t timestamp = get_timestamp_ms();
uint32_t payload_size = jpeg_size;

// 构造消息并发送
```

---

## 6. 工作流程

### 正常模式
```
ESP32 音频 → Server → ASR → LLM → TTS → ESP32
ESP32 状态(forward) → Server(存储) → App
App 控制(forward) → Server → ESP32
```

### 监控模式
```
ESP32 音频/视频 → Server → App（实时转发）
App 音频 → Server → ESP32（双向对讲）
App 控制命令 → Server → ESP32
```

---

## 7. 实现状态

✅ 已完成的功能：
- ConnectionManager 连接管理
- App 端连接支持（/ws/app）
- 模式切换（start_monitor / stop_monitor）
- BinaryProtocol2 协议解析
- 音视频数据转发
- 消息转发机制（forward 字段）
- 多 App 广播
- 双向对讲
- 设备状态存储（基于 iot_descriptors）

---

## 8. 测试建议

1. **连接测试**
   - ESP32 连接 `/ws/xiaozhi`
   - App 连接 `/ws/app` 并发送 hello 消息

2. **模式切换测试**
   - App 发送 start_monitor 命令
   - 验证 ESP32 收到通知
   - 验证音视频开始转发

3. **消息转发测试**
   - ESP32 发送带 forward 的状态消息
   - 验证 App 收到消息（不含 forward 字段）

4. **音视频转发测试**
   - 监控模式下 ESP32 发送音频/视频
   - 验证 App 收到数据
   - App 发送音频，验证 ESP32 收到（对讲）
