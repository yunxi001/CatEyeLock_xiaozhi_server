# seq_id 使用规范与注意事项

> 版本：v1.0  
> 创建日期：2026-01-17  
> 适用于：智能猫眼门锁系统 v5.2 协议

---

## 一、seq_id 核心规则

### 1.1 格式定义

**标准格式**：`时间戳_序号`

```
示例：1702234567890_0
      └─────┬─────┘ │
        13位时间戳  序号
```

**组成部分**：
- **时间戳**：13 位毫秒级时间戳（JavaScript: `Date.now()`，Python: `int(time.time() * 1000)`）
- **序号**：从 0 开始递增的整数，用于区分同一毫秒内的多个请求

### 1.2 生成规则

**生成方**：App 端

**生成时机**：用户发起命令时

**生成算法**：
```javascript
// JavaScript (App 端)
let sequence = 0;
let lastTimestamp = 0;

function generateSeqId() {
    const timestamp = Date.now();
    
    // 如果时间戳相同，序号递增
    if (timestamp === lastTimestamp) {
        sequence++;
    } else {
        // 新的时间戳，序号重置
        sequence = 0;
        lastTimestamp = timestamp;
    }
    
    return `${timestamp}_${sequence}`;
}
```

```python
# Python (Server 端，仅用于主动发起的消息)
import time

class SeqIdGenerator:
    def __init__(self):
        self.sequence = 0
        self.last_timestamp = 0
    
    def generate(self) -> str:
        timestamp = int(time.time() * 1000)
        
        # 如果时间戳相同，序号递增
        if timestamp == self.last_timestamp:
            self.sequence += 1
        else:
            # 新的时间戳，序号重置
            self.sequence = 0
            self.last_timestamp = timestamp
        
        return f"{timestamp}_{self.sequence}"
```

### 1.3 唯一性保证

**核心原则**：对于一个完整的命令流程，seq_id 必须全局唯一且保持不变。

**唯一性范围**：
- 同一个 App 实例内唯一
- 同一个设备（device_id）内唯一
- 时间窗口：理论上永久唯一（13 位时间戳 + 序号）

**冲突避免**：
- 使用毫秒级时间戳（精度足够）
- 同一毫秒内使用序号递增
- 不同 App 实例的时间戳不会完全相同

---

## 二、seq_id 传递规则

### 2.1 哪些消息需要携带 seq_id？

**核心原则**：只有命令及其响应需要携带 seq_id，主动上报的消息不需要。

#### 2.1.1 需要携带 seq_id 的消息

| 方向 | 消息类型 | 说明 | seq_id 来源 |
|------|----------|------|-------------|
| App → Server | `lock_control` | 锁控命令 | App 生成 |
| App → Server | `dev_control` | 设备控制命令 | App 生成 |
| App → Server | `user_mgmt` | 用户管理命令 | App 生成 |
| App → Server | `query` | 查询命令 | App 生成 |
| Server → App | `server_ack` | 服务器确认 | 透传 App 的 seq_id |
| Server → ESP32 | `lock_control` | 锁控命令（转发） | 透传 App 的 seq_id |
| Server → ESP32 | `dev_control` | 设备控制命令（转发） | 透传 App 的 seq_id |
| Server → ESP32 | `user_mgmt` | 用户管理命令（转发） | 透传 App 的 seq_id |
| Server → ESP32 | `query` | 查询命令（转发） | 透传 App 的 seq_id |
| ESP32 → Server | `esp32_ack` | 第一级确认：命令已收到 | 透传命令的 seq_id |
| ESP32 → Server | `ack` | 第二级确认：命令执行完成 | 透传命令的 seq_id |
| Server → App | `esp32_ack` | 第一级确认（转发） | 透传 ESP32 的 seq_id |
| Server → App | `ack` | 第二级确认（转发） | 透传 ESP32 的 seq_id |

#### 2.1.2 不需要携带 seq_id 的消息

| 方向 | 消息类型 | 说明 | 原因 |
|------|----------|------|------|
| ESP32 → Server | `status_report` | 状态上报 | 主动上报，非命令响应 |
| ESP32 → Server | `event_report` | 事件上报 | 主动上报，非命令响应 |
| ESP32 → Server | `log_report` | 开锁日志 | 主动上报，非命令响应 |
| ESP32 → Server | `door_opened_report` | 开门日志 | 主动上报，非命令响应 |
| ESP32 → Server | `password_report` | 密码查询结果 | 主动上报，非命令响应 |
| ESP32 → Server | `user_mgmt_result` | 用户管理结果 | 主动上报，非命令响应 |
| ESP32 → Server | `heartbeat` | 心跳 | 主动上报，非命令响应 |
| Server → ESP32 | `face_result` | 人脸识别结果 | 响应 ESP32 的主动请求，非命令响应 |
| Server → App | 上述所有上报消息 | 转发上报 | 转发时保持原样（无 seq_id） |

**关键区别**：
- ✅ **命令-响应模式**：需要 seq_id 追踪整个流程
- ❌ **主动上报模式**：不需要 seq_id，Server 不回复 ack
- ❌ **主动请求-响应模式**：ESP32 主动请求（如人脸识别），Server 响应，不需要 seq_id

**特殊说明：face_result**
```
ESP32 检测到人脸（主动）
    ↓
ESP32 发送二进制人脸识别请求（不携带 seq_id）
    ↓
Server 处理并返回 face_result（不携带 seq_id）
    ↓
ESP32 执行开锁并上报 log_report（不携带 seq_id）
```

### 2.2 完整命令流程中的 seq_id 传递

**核心原则**：seq_id 在整个命令流程中保持不变，所有响应和确认都必须携带原始 seq_id。

```
App                    Server                  ESP32                   STM32
 │                       │                       │                       │
 │ ① 命令                │                       │                       │
 │   seq_id=1234_0       │                       │                       │
 │──────────────────────>│                       │                       │
 │                       │                       │                       │
 │ ② server_ack          │                       │                       │
 │   seq_id=1234_0 ✅    │                       │                       │
 │<──────────────────────│                       │                       │
 │                       │                       │                       │
 │                       │ ③ 命令转发            │                       │
 │                       │   seq_id=1234_0 ✅    │                       │
 │                       │──────────────────────>│                       │
 │                       │                       │                       │
 │                       │ ④ esp32_ack           │                       │
 │                       │   seq_id=1234_0 ✅    │                       │
 │                       │<──────────────────────│                       │
 │                       │                       │                       │
 │                       │                       │ ⑤ UART 命令           │
 │                       │                       │   (无 seq_id)         │
 │                       │                       │──────────────────────>│
 │                       │                       │                       │
 │                       │                       │ ⑥ UART 响应           │
 │                       │                       │   (无 seq_id)         │
 │                       │                       │<──────────────────────│
 │                       │                       │                       │
 │                       │ ⑦ ack                 │                       │
 │                       │   seq_id=1234_0 ✅    │                       │
 │                       │<──────────────────────│                       │
 │                       │                       │                       │
 │ ⑧ ack 转发            │                       │                       │
 │   seq_id=1234_0 ✅    │                       │                       │
 │<──────────────────────│                       │                       │
```

**关键点**：
- ✅ App 生成 seq_id：`1234_0`
- ✅ Server 的 server_ack 携带原始 seq_id：`1234_0`
- ✅ Server 转发给 ESP32 时携带原始 seq_id：`1234_0`
- ✅ ESP32 的 esp32_ack 携带原始 seq_id：`1234_0`
- ❌ UART 协议不支持 seq_id（ESP32 内部维护映射）
- ✅ ESP32 的 ack 携带原始 seq_id：`1234_0`
- ✅ Server 转发 ack 给 App 时携带原始 seq_id：`1234_0`

### 2.3 各端职责

| 端 | 职责 | seq_id 处理 |
|----|------|-------------|
| **App** | 生成 seq_id | 生成并发送，接收响应时验证 seq_id 匹配 |
| **Server** | 透传 seq_id | 接收后原样转发，不修改 |
| **ESP32** | 维护 seq_id 映射 | 接收后保存，UART 响应后查找并携带原始 seq_id |
| **STM32** | 不处理 seq_id | UART 协议不支持 seq_id |

---

## 三、常见错误与纠正

### 3.1 ❌ 错误：使用前缀

**错误示例**：
```python
# ❌ 错误：添加了 "face_" 前缀
seq_id = f"face_{int(time.time() * 1000)}"
# 结果：face_1702234567890

# ❌ 错误：添加了 "cmd_" 前缀
seq_id = f"cmd_{int(time.time() * 1000)}"
# 结果：cmd_1702234567890
```

**正确示例**：
```python
# ✅ 正确：时间戳_序号格式
seq_id = f"{int(time.time() * 1000)}_0"
# 结果：1702234567890_0
```

**原因**：
- seq_id 的格式是标准化的：`时间戳_序号`
- 添加前缀会破坏格式，导致解析失败
- 前缀信息应该通过消息的 `type` 字段区分，而不是 seq_id

### 3.2 ❌ 错误：Server 端生成新的 seq_id

**错误示例**：
```python
# ❌ 错误：Server 收到 App 的命令后，生成新的 seq_id
app_seq_id = msg_json.get("seq_id")  # 1234_0
server_seq_id = f"{int(time.time() * 1000)}_0"  # 1234_1 (新生成)

# 转发给 ESP32 时使用新的 seq_id
msg_json["seq_id"] = server_seq_id  # ❌ 错误！
```

**正确示例**：
```python
# ✅ 正确：Server 透传 App 的 seq_id
app_seq_id = msg_json.get("seq_id")  # 1234_0

# 转发给 ESP32 时保持原始 seq_id
# msg_json["seq_id"] 保持不变  # ✅ 正确！
await esp32_conn.websocket.send(json.dumps(msg_json))
```

**原因**：
- seq_id 用于追踪整个命令流程
- 如果 Server 生成新的 seq_id，App 无法匹配响应
- Server 的职责是透传，不是生成

### 3.3 ❌ 错误：ESP32 修改 seq_id

**错误示例**：
```cpp
// ❌ 错误：ESP32 收到命令后，修改 seq_id
std::string original_seq_id = json["seq_id"];  // "1234_0"
std::string new_seq_id = std::to_string(millis()) + "_0";  // 生成新的

// 发送 esp32_ack 时使用新的 seq_id
json["seq_id"] = new_seq_id;  // ❌ 错误！
```

**正确示例**：
```cpp
// ✅ 正确：ESP32 保持原始 seq_id
std::string original_seq_id = json["seq_id"];  // "1234_0"

// 保存到待处理命令队列
pending_commands_[uart_type] = {
    .seq_id = original_seq_id,  // 保存原始 seq_id
    .uart_type = uart_type,
    .timestamp_ms = millis()
};

// 发送 esp32_ack 时使用原始 seq_id
json["seq_id"] = original_seq_id;  // ✅ 正确！
```

**原因**：
- ESP32 必须保持原始 seq_id，以便 App 能够匹配响应
- ESP32 内部通过 UART TYPE 映射到 seq_id，但对外始终使用原始 seq_id

### 3.4 ❌ 错误：缺少序号

**错误示例**：
```python
# ❌ 错误：只有时间戳，没有序号
seq_id = f"{int(time.time() * 1000)}"
# 结果：1702234567890
```

**正确示例**：
```python
# ✅ 正确：时间戳_序号
seq_id = f"{int(time.time() * 1000)}_0"
# 结果：1702234567890_0
```

**原因**：
- 序号用于区分同一毫秒内的多个请求
- 缺少序号可能导致 seq_id 冲突

---

## 四、特殊场景处理

### 4.1 Server 主动发起的消息

**场景**：Server 主动向 ESP32 发送命令（非 App 触发）

**示例**：
- 系统配置更新
- 固件升级通知
- 定时任务触发

**处理方式**：
```python
# Server 生成 seq_id（因为没有 App 的 seq_id）
seq_id_generator = SeqIdGenerator()
seq_id = seq_id_generator.generate()

message = {
    "type": "system_config",
    "seq_id": seq_id,  # Server 生成的 seq_id
    "data": {...}
}
```

**注意**：
- 仅在 Server 主动发起时生成 seq_id
- 如果是转发 App 的命令，必须使用 App 的 seq_id

### 4.2 ESP32 主动上报的消息（不携带 seq_id）

**场景**：ESP32 主动向 Server 上报事件/状态/日志（非命令响应）

**消息类型**：

| 消息类型 | 触发来源 | 说明 | 携带 seq_id |
|----------|----------|------|-------------|
| `status_report` | STM32 上报 | 状态上报（电量、光照、锁、灯） | ❌ |
| `event_report` | STM32 上报 | 事件上报（门铃、PIR、撬锁等） | ❌ |
| `log_report` | STM32 上报 | 开锁日志 | ❌ |
| `door_opened_report` | STM32 上报 | 开门日志 | ❌ |
| `password_report` | STM32 上报 | 密码查询结果 | ❌ |
| `user_mgmt_result` | STM32 上报 | 用户管理结果 | ❌ |
| `heartbeat` | 定时器（预留） | 心跳 | ❌ |

**处理方式**：
```cpp
// ❌ 错误：主动上报不需要 seq_id
json message = {
    {"type", "event_report"},
    {"seq_id", seq_id},  // ❌ 不需要！
    {"event", "bell"},
    {"ts", millis()}
};

// ✅ 正确：主动上报不携带 seq_id
json message = {
    {"type", "event_report"},
    {"event", "bell"},
    {"ts", millis()}
};
```

### 4.3 Server 响应 ESP32 主动请求（不携带 seq_id）

**场景**：ESP32 主动发起请求（非命令），Server 响应

**典型示例：face_result**

```
ESP32 检测到人脸（主动，无命令触发）
    ↓
ESP32 发送二进制人脸识别请求（不携带 seq_id）
    ↓
Server 处理人脸识别
    ↓
Server 返回 face_result 给 ESP32（不携带 seq_id）
    ↓
ESP32 执行开锁操作
    ↓
ESP32 上报 log_report（开锁日志，不携带 seq_id）
```

**处理方式**：
```python
# ❌ 错误：响应主动请求不需要 seq_id
response = {
    "type": "face_result",
    "seq_id": f"face_{int(time.time() * 1000)}",  # ❌ 不需要！
    "result": "known",
    "user_id": 5,
    "access": {"granted": True, "reason": "authorized_user"}
}

# ✅ 正确：响应主动请求不携带 seq_id
response = {
    "type": "face_result",
    "result": "known",
    "user_id": 5,
    "access": {"granted": True, "reason": "authorized_user"}
}
```

**核心原则**：
- ✅ **命令响应**（esp32_ack、ack）：必须携带原始 seq_id
- ❌ **主动上报**（status_report、event_report、log_report 等）：不携带 seq_id
- ❌ **响应主动请求**（face_result）：不携带 seq_id
- 📌 **原因**：主动上报和主动请求都不是对命令的响应，Server 不需要回复 ack，因此不需要 seq_id 追踪

### 4.3 重试场景

**场景**：Server 向 ESP32 发送命令，超时后重试

**错误处理**：
```python
# ❌ 错误：重试时生成新的 seq_id
for retry in range(3):
    seq_id = f"{int(time.time() * 1000)}_0"  # ❌ 每次重试都生成新的
    msg_json["seq_id"] = seq_id
    await esp32_conn.websocket.send(json.dumps(msg_json))
```

**正确处理**：
```python
# ✅ 正确：重试时保持原始 seq_id
original_seq_id = msg_json.get("seq_id")  # 保存原始 seq_id

for retry in range(3):
    # 重试时使用原始 seq_id
    msg_json["seq_id"] = original_seq_id  # ✅ 保持不变
    await esp32_conn.websocket.send(json.dumps(msg_json))
    
    # 等待响应...
    if ack_received:
        break
```

**原因**：
- 重试是同一个命令的多次尝试，不是新命令
- seq_id 必须保持不变，以便追踪整个流程

---

## 五、实现检查清单

### 5.1 App 端检查

- [ ] seq_id 格式为 `时间戳_序号`
- [ ] 使用毫秒级时间戳（13 位）
- [ ] 同一毫秒内序号递增
- [ ] 发送命令时携带 seq_id
- [ ] 接收响应时验证 seq_id 匹配

### 5.2 Server 端检查

- [ ] 接收 App 命令时提取 seq_id
- [ ] 转发给 ESP32 时保持原始 seq_id（不修改）
- [ ] server_ack 携带原始 seq_id
- [ ] 转发 ESP32 响应时保持原始 seq_id
- [ ] 重试时保持原始 seq_id（不生成新的）
- [ ] 主动发起命令时才生成新的 seq_id

### 5.3 ESP32 端检查

- [ ] 接收命令时提取 seq_id
- [ ] 保存 seq_id 到待处理命令队列
- [ ] esp32_ack 携带原始 seq_id
- [ ] UART 响应后通过 TYPE 查找原始 seq_id
- [ ] ack 携带原始 seq_id
- [ ] 主动上报消息（status_report、event_report 等）不携带 seq_id

### 5.4 代码审查要点

**查找可疑代码**：
```bash
# 查找可能错误的 seq_id 生成（带前缀）
grep -r "seq_id.*=.*f\".*_" --include="*.py"
grep -r "seq_id.*=.*\".*_" --include="*.cpp"

# 查找可能的 seq_id 修改
grep -r "seq_id.*=.*time" --include="*.py"
grep -r "seq_id.*=.*millis" --include="*.cpp"
```

**正确的模式**：
- App 生成：`seq_id = f"{timestamp}_{sequence}"`
- Server 透传：`seq_id = msg_json.get("seq_id")`（不修改）
- ESP32 保存：`pending_commands_[type].seq_id = original_seq_id`

**错误的模式**：
- ❌ `seq_id = f"face_{timestamp}"`（带前缀）
- ❌ `seq_id = f"cmd_{timestamp}_{sequence}"`（带前缀）
- ❌ `seq_id = f"{new_timestamp}_{sequence}"`（Server/ESP32 生成新的）

---

## 六、调试与追踪

### 6.1 日志记录建议

**App 端**：
```javascript
console.log(`[发送命令] type=${type}, seq_id=${seq_id}`);
console.log(`[收到响应] type=${type}, seq_id=${seq_id}, code=${code}`);
```

**Server 端**：
```python
logger.info(f"[收到App命令] type={type}, seq_id={seq_id}, device_id={device_id}")
logger.info(f"[转发ESP32] type={type}, seq_id={seq_id}")
logger.info(f"[收到ESP32响应] type={type}, seq_id={seq_id}, code={code}")
logger.info(f"[转发App] type={type}, seq_id={seq_id}")
```

**ESP32 端**：
```cpp
Serial.printf("[收到命令] type=%s, seq_id=%s\n", type.c_str(), seq_id.c_str());
Serial.printf("[发送esp32_ack] seq_id=%s\n", seq_id.c_str());
Serial.printf("[发送UART] type=0x%02X, seq_id=%s\n", uart_type, seq_id.c_str());
Serial.printf("[收到UART响应] type=0x%02X\n", uart_type);
Serial.printf("[发送ack] seq_id=%s, code=%d\n", seq_id.c_str(), code);
```

### 6.2 seq_id 追踪示例

**完整流程日志**：
```
[App] [发送命令] type=lock_control, seq_id=1702234567890_0
[Server] [收到App命令] type=lock_control, seq_id=1702234567890_0, device_id=ESP32_001
[Server] [转发ESP32] type=lock_control, seq_id=1702234567890_0
[ESP32] [收到命令] type=lock_control, seq_id=1702234567890_0
[ESP32] [发送esp32_ack] seq_id=1702234567890_0
[Server] [收到ESP32响应] type=esp32_ack, seq_id=1702234567890_0, code=0
[ESP32] [发送UART] type=0x10, seq_id=1702234567890_0
[ESP32] [收到UART响应] type=0x10
[ESP32] [发送ack] seq_id=1702234567890_0, code=0
[Server] [收到ESP32响应] type=ack, seq_id=1702234567890_0, code=0
[Server] [转发App] type=ack, seq_id=1702234567890_0
[App] [收到响应] type=ack, seq_id=1702234567890_0, code=0
```

**关键验证点**：
- ✅ 所有日志中的 seq_id 都是 `1702234567890_0`（保持不变）
- ✅ 格式正确：`时间戳_序号`
- ✅ 没有前缀（如 `face_`、`cmd_` 等）

---

## 七、常见问题 FAQ

### Q1: 为什么 seq_id 不能有前缀？

**A**: seq_id 的格式是标准化的 `时间戳_序号`，这样设计有以下好处：
1. **解析简单**：可以直接通过 `_` 分割提取时间戳和序号
2. **全局统一**：所有消息类型使用相同格式，便于追踪
3. **类型区分**：消息类型通过 `type` 字段区分，不需要在 seq_id 中体现

### Q2: Server 什么时候可以生成 seq_id？

**A**: 仅在以下情况下 Server 可以生成 seq_id：
1. Server 主动发起命令（非 App 触发）
2. Server 主动推送通知（非响应）

**绝对不能**在以下情况生成新的 seq_id：
1. 转发 App 的命令
2. 重试发送命令
3. 转发 ESP32 的响应

### Q3: ESP32 如何关联 UART 响应与 seq_id？

**A**: ESP32 维护一个待处理命令队列：
```cpp
std::map<uint8_t, PendingCommand> pending_commands_;

struct PendingCommand {
    std::string seq_id;       // 原始 seq_id
    uint8_t uart_type;        // UART 命令 TYPE
    int64_t timestamp_ms;     // 发送时间戳
};
```

**工作流程**：
1. 收到 WebSocket 命令 → 保存 `pending_commands_[uart_type] = {seq_id, ...}`
2. 发送 UART 命令
3. 收到 UART 响应 → 通过 `uart_type` 查找 `seq_id`
4. 发送 WebSocket ack（携带原始 seq_id）

### Q4: 重试时 seq_id 会变吗？

**A**: 不会！重试是同一个命令的多次尝试，seq_id 必须保持不变。

**示例**：
```
第1次发送：seq_id=1234_0
超时...
第2次发送：seq_id=1234_0  ← 保持不变
超时...
第3次发送：seq_id=1234_0  ← 保持不变
```

### Q5: 如何验证 seq_id 实现是否正确？

**A**: 检查以下几点：
1. 格式检查：`^\d{13}_\d+$`（正则表达式）
2. 流程追踪：从 App 到 ESP32 再回到 App，seq_id 保持不变
3. 日志验证：所有日志中的 seq_id 一致
4. 代码审查：查找可疑的 seq_id 生成代码

### Q6: 主动上报的消息为什么不需要 seq_id？

**A**: 原因如下：
1. **不是命令响应**：主动上报不是对某个命令的响应，没有对应的命令 seq_id
2. **Server 不回复**：Server 收到上报后不需要回复 ack，因此不需要 seq_id 追踪
3. **单向通信**：上报是单向的（ESP32 → Server → App），不需要追踪往返流程
4. **时间戳足够**：上报消息通常携带 `ts` 字段（时间戳），足以标识消息

**示例对比**：
```json
// ✅ 命令响应：需要 seq_id
{
    "type": "ack",
    "seq_id": "1702234567890_0",  // 必须携带
    "code": 0
}

// ✅ 主动上报：不需要 seq_id
{
    "type": "event_report",
    "event": "bell",
    "ts": 1702234567890  // 使用时间戳标识
}
```

---

## 八、总结

### 8.1 核心要点

1. **格式标准**：`时间戳_序号`，不允许有前缀
2. **生成方**：App 端生成，Server/ESP32 透传
3. **唯一性**：整个命令流程中保持不变
4. **追踪性**：命令响应（esp32_ack、ack）必须携带原始 seq_id
5. **重试规则**：重试时保持原始 seq_id
6. **上报规则**：主动上报消息（status_report、event_report 等）不携带 seq_id

### 8.2 记忆口诀

```
seq_id 格式要记牢，时间戳加序号标。
App 生成不能改，Server 透传要做到。
命令响应带 seq_id，主动上报不需要。
ESP32 保存映射表，UART 响应找得到。
重试保持原 seq_id，追踪流程少不了。
```

### 8.3 快速判断表

**如何判断一个消息是否需要携带 seq_id？**

| 问题 | 答案 | 结论 |
|------|------|------|
| 这是命令吗？ | 是 | ✅ 需要 seq_id |
| 这是命令的响应吗？ | 是 | ✅ 需要 seq_id |
| 这是主动上报吗？ | 是 | ❌ 不需要 seq_id |
| Server 需要回复 ack 吗？ | 是 | ✅ 需要 seq_id |
| Server 需要回复 ack 吗？ | 否 | ❌ 不需要 seq_id |

**示例**：
- `lock_control`（命令）→ ✅ 需要 seq_id
- `esp32_ack`（命令响应）→ ✅ 需要 seq_id
- `ack`（命令响应）→ ✅ 需要 seq_id
- `event_report`（主动上报）→ ❌ 不需要 seq_id
- `log_report`（主动上报）→ ❌ 不需要 seq_id

---

**文档维护者**：毕业设计项目组  
**创建日期**：2026-01-17  
**最后更新**：2026-01-17
