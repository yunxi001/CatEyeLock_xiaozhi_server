# App 协议与 ESP32 协议一致性分析报告

> 创建日期：2026-01-17  
> 分析范围：App 协议 v2.2 与 ESP32 协议 v5.2 的一致性

---

## 一、分析概述

本报告分析 App 协议 v2.2 与 ESP32 协议 v5.2 之间的一致性，识别潜在的矛盾和需要完善的地方。

### 分析维度

1. 消息类型一致性
2. 字段格式一致性
3. 错误码一致性
4. seq_id/msg_id 使用一致性
5. ACK 机制一致性
6. 数据流向一致性

---

## 二、发现的主要问题

### 问题 1：错误码不一致 ⚠️ 严重

**ESP32 协议 v5.2 错误码（0-10）：**
| code | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 设备离线 |
| 2 | 设备忙 |
| 3 | 参数错误 |
| 4 | 不支持 |
| 5 | 超时 |
| 6 | 硬件故障 |
| 7 | 资源已满 |
| 8 | 未认证 |
| 9 | 重复消息 |
| 10 | 内部错误 |

**App 协议 v2.2 错误码（0-7）：**
| code | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 设备忙碌 |
| 2 | 参数错误 |
| 3 | 硬件故障 |
| 4 | 超时 |
| 5 | 未授权 |
| 6 | 资源不足 |
| 7 | 不支持 |

**server_ack 错误码（0-5）：**
| code | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 设备离线 |
| 2 | 参数错误 |
| 3 | 未认证 |
| 4 | 内部错误 |
| 5 | 重复消息 |

**问题分析：**
- ESP32 协议使用 0-10 共 11 个错误码
- App 协议的 ESP32 ACK 使用 0-7 共 8 个错误码
- App 协议的 server_ack 使用 0-5 共 6 个错误码
- 三套错误码定义不一致，容易混淆

**影响：**
- App 收到 ESP32 的 ack 时，错误码含义与 ESP32 协议不一致
- Server 转发 ESP32 ack 时需要进行错误码映射
- 增加了理解和维护成本

**建议修复：**
统一使用 ESP32 协议 v5.2 的错误码（0-10），修改 App 协议文档。

---

### 问题 2：log_report 字段不一致 ⚠️ 严重

**ESP32 协议 v5.2：**
```json
{
    "type": "log_report",
    "ts": 1702234567890,
    "data": {
        "method": "finger",
        "status": "success",     // v5.2 新增
        "uid": 5,
        "lock_time": 0,          // v5.2 新增
        "fail_count": 0
    }
}
```

**App 协议 v2.2：**
```json
{
    "type": "log_report",
    "ts": 1702234567890,
    "data": {
        "method": "finger",
        "uid": 5,
        "result": true,          // 旧版字段
        "fail_count": 0
    }
}
```

**问题分析：**
- ESP32 协议已升级到 v5.2，使用 `status` 字段（success/fail/locked）
- App 协议仍使用旧版 `result` 字段（true/false）
- App 协议缺少 `lock_time` 字段，无法显示设备锁定时间

**影响：**
- App 无法区分"认证失败"和"设备锁定"两种状态
- App 无法显示剩余锁定时间
- Server 转发时需要进行字段转换

**建议修复：**
更新 App 协议文档，采用 ESP32 协议 v5.2 的字段定义。

---

### 问题 3：event_report 缺少新增事件 ⚠️ 中等

**ESP32 协议 v5.2 新增事件：**
- `door_closed`：门已关闭
- `lock_success`：上锁成功
- `bolt_alarm`：反锁报警

**App 协议 v2.2：**
仅列出了旧版事件，未包含 v5.2 新增的 3 个事件。

**影响：**
- App 收到新增事件时可能无法正确处理
- 文档不完整，开发者不知道有这些事件

**建议修复：**
更新 App 协议文档，添加 v5.2 新增的事件类型。

---

### 问题 4：缺少 door_opened_report 和 password_report ⚠️ 中等

**ESP32 协议 v5.2 新增消息：**
- `door_opened_report`：开门日志上报
- `password_report`：密码查询结果上报

**App 协议 v2.2：**
未包含这两个消息类型。

**影响：**
- App 无法接收开门日志（与开锁日志不同）
- App 无法接收密码查询结果
- Server 转发这些消息时，App 可能无法处理

**建议修复：**
更新 App 协议文档，添加这两个消息类型的定义。

---

### 问题 5：seq_id 与 msg_id 混用 ⚠️ 中等

**ESP32 协议 v5.2：**
- 统一使用 `seq_id` 字段
- 格式：`时间戳_序号`（如 `1702234567890_0`）
- 兼容旧版 `msg_id`

**App 协议 v2.2：**
- App 发送消息使用 `seq_id`
- ESP32 ACK 响应使用 `msg_id`
- 格式建议：`app_{timestamp}_{sequence}`

**问题分析：**
- App 发送时用 `seq_id`，收到 ESP32 响应时是 `msg_id`
- 两个字段名不一致，容易混淆
- App 需要同时处理两种字段名

**影响：**
- 增加 App 端代码复杂度
- 消息追踪困难（seq_id 和 msg_id 无法对应）

**建议修复：**
1. Server 转发 ESP32 ack 时，将 `msg_id` 转换为 `seq_id`
2. 或者统一使用 `seq_id`，ESP32 协议也完全废弃 `msg_id`

---

### 问题 6：缺少 esp32_ack 说明 ⚠️ 轻微

**ESP32 协议 v5.2：**
实现了两级确认机制：
- 第一级：`esp32_ack`（命令已收到）
- 第二级：`ack`（命令执行完成）

**App 协议 v2.2：**
- 只提到了 `ack`（ESP32 ACK 响应）
- 未提到 `esp32_ack`

**问题分析：**
- App 可能会收到 `esp32_ack` 消息（如果 Server 转发）
- 但协议文档中没有说明

**影响：**
- App 收到 `esp32_ack` 时可能不知道如何处理
- 文档不完整

**建议修复：**
在 App 协议文档中说明两级确认机制，或明确 `esp32_ack` 不转发给 App。

---

### 问题 7：query 消息定义不明确 ⚠️ 轻微

**ESP32 协议 v5.2：**
```json
{
    "type": "query",
    "seq_id": "1702234567890_0",
    "command": "sensors"  // 或 "status"
}
```

**App 协议 v2.2：**
```json
{
    "type": "query",
    "seq_id": "app_1702234567890_014",
    "target": "status"  // 不是 "command"
}
```

**问题分析：**
- ESP32 协议使用 `command` 字段
- App 协议使用 `target` 字段
- 两者字段名不一致

**影响：**
- 如果 App 需要查询 ESP32 实时数据，字段名不匹配
- 目前 App 的 query 是查询 Server 数据库，不涉及 ESP32

**建议修复：**
明确区分两种 query 场景：
- App → Server 查询历史数据：使用 `target`
- Server → ESP32 查询实时数据：使用 `command`

---

## 三、字段一致性对比

### 3.1 status_report 消息

| 字段 | ESP32 协议 | App 协议 | 一致性 |
|------|------------|----------|--------|
| type | ✅ | ✅ | ✅ |
| ts | ✅ | ✅ | ✅ |
| data.bat | ✅ | ✅ | ✅ |
| data.lux | ✅ | ✅ | ✅ |
| data.lock | ✅ | ✅ | ✅ |
| data.light | ✅ | ✅ | ✅ |

**结论**：✅ 完全一致

### 3.2 event_report 消息

| 字段 | ESP32 协议 | App 协议 | 一致性 |
|------|------------|----------|--------|
| type | ✅ | ✅ | ✅ |
| ts | ✅ | ✅ | ✅ |
| event | ✅ | ✅ | ✅ |
| param | ✅ | ✅ | ✅ |

**事件类型对比：**
| 事件 | ESP32 协议 | App 协议 | 一致性 |
|------|------------|----------|--------|
| bell | ✅ | ✅ | ✅ |
| pir_trigger | ✅ | ✅ | ✅ |
| tamper | ✅ | ✅ | ✅ |
| door_open | ✅ | ✅ | ✅ |
| low_battery | ✅ | ✅ | ✅ |
| door_closed | ✅ v5.2 新增 | ❌ 缺失 | ❌ |
| lock_success | ✅ v5.2 新增 | ❌ 缺失 | ❌ |
| bolt_alarm | ✅ v5.2 新增 | ❌ 缺失 | ❌ |

**结论**：⚠️ 部分一致，缺少 3 个新增事件

### 3.3 log_report 消息

| 字段 | ESP32 协议 v5.2 | App 协议 v2.2 | 一致性 |
|------|-----------------|---------------|--------|
| type | ✅ | ✅ | ✅ |
| ts | ✅ | ✅ | ✅ |
| data.method | ✅ | ✅ | ✅ |
| data.uid | ✅ | ✅ | ✅ |
| data.status | ✅ 新增 | ❌ 使用 result | ❌ |
| data.result | ❌ 废弃 | ✅ | ❌ |
| data.lock_time | ✅ 新增 | ❌ 缺失 | ❌ |
| data.fail_count | ✅ | ✅ | ✅ |

**结论**：❌ 不一致，App 协议使用旧版字段

### 3.4 lock_control 消息

| 字段 | ESP32 协议 | App 协议 | 一致性 |
|------|------------|----------|--------|
| type | ✅ | ✅ | ✅ |
| seq_id | ✅ | ✅ | ✅ |
| command | ✅ | ✅ | ✅ |
| duration | ✅ | ✅ | ✅ |
| code | ✅ | ✅ | ✅ |
| expires | ✅ | ✅ | ✅ |

**结论**：✅ 完全一致

### 3.5 dev_control 消息

| 字段 | ESP32 协议 | App 协议 | 一致性 |
|------|------------|----------|--------|
| type | ✅ | ✅ | ✅ |
| seq_id | ✅ | ✅ | ✅ |
| target | ✅ | ✅ | ✅ |
| count | ✅ | ✅ | ✅ |
| mode | ✅ | ✅ | ✅ |
| action | ✅ | ✅ | ✅ |
| icon | ✅ | ✅ | ✅ |

**结论**：✅ 完全一致

### 3.6 user_mgmt 消息

| 字段 | ESP32 协议 | App 协议 | 一致性 |
|------|------------|----------|--------|
| type | ✅ | ✅ | ✅ |
| seq_id | ✅ | ✅ | ✅ |
| category | ✅ | ✅ | ✅ |
| command | ✅ | ✅ | ✅ |
| user_id | ✅ | ✅ | ✅ |
| payload | ✅ | ✅ | ✅ |

**结论**：✅ 完全一致

---

## 四、ACK 机制对比

### 4.1 ESP32 协议 v5.2

**两级确认机制：**
1. **esp32_ack**（第一级）：命令已收到
   - 格式：`{"type": "esp32_ack", "seq_id": "...", "code": 0, "msg": "received"}`
   - 用途：Server 判断是否需要重试

2. **ack**（第二级）：命令执行完成
   - 格式：`{"type": "ack", "seq_id": "...", "code": 0, "msg": "OK"}`
   - 用途：反馈执行结果

### 4.2 App 协议 v2.2

**两级确认机制：**
1. **server_ack**：Server 收到消息
   - 格式：`{"type": "server_ack", "seq_id": "...", "code": 0, "msg": "已接收", "ts": ...}`
   - 用途：App 判断消息是否送达 Server

2. **ack**：ESP32 执行完成（转发）
   - 格式：`{"type": "ack", "msg_id": "...", "code": 0, "msg": "OK"}`
   - 用途：反馈 ESP32 执行结果

### 4.3 对比分析

| 项目 | ESP32 协议 | App 协议 | 一致性 |
|------|------------|----------|--------|
| 第一级确认名称 | esp32_ack | server_ack | ❌ 不同 |
| 第二级确认名称 | ack | ack | ✅ 相同 |
| 第一级 ID 字段 | seq_id | seq_id | ✅ 相同 |
| 第二级 ID 字段 | seq_id | msg_id | ❌ 不同 |
| 错误码范围 | 0-10 | 0-7 | ❌ 不同 |

**结论**：⚠️ 部分一致，但字段名和错误码不统一

---

## 五、消息流向一致性

### 5.1 命令下发流程

**ESP32 协议：**
```
App → Server → ESP32
    seq_id      seq_id (透传)
```

**App 协议：**
```
App → Server → ESP32
    seq_id      msg_id (生成新的)
```

**问题**：
- Server 应该透传 App 的 seq_id，而不是生成新的 msg_id
- 当前 App 协议文档中的命令代理示例生成了新的 msg_id

**建议修复：**
Server 应透传 App 的 seq_id 给 ESP32，保持消息追踪的一致性。

### 5.2 响应返回流程

**ESP32 协议：**
```
ESP32 → Server → App
    ack(seq_id)  转发
```

**App 协议：**
```
ESP32 → Server → App
    ack(msg_id)  转发
```

**问题**：
- ESP32 返回的 ack 使用 msg_id（或 seq_id）
- App 收到的 ack 也使用 msg_id
- 但 App 发送时使用的是 seq_id
- 无法通过 ID 匹配请求和响应

**建议修复：**
Server 转发 ESP32 ack 时，将 msg_id 映射回 App 的 seq_id。

---

## 六、修复建议优先级

### 高优先级（必须修复）

1. **统一错误码定义** ⚠️ 严重
   - 将 App 协议的错误码更新为 ESP32 协议 v5.2 的 0-10 定义
   - 更新 server_ack 错误码，与 ESP32 协议保持一致

2. **更新 log_report 字段** ⚠️ 严重
   - 将 `result` 字段改为 `status`（success/fail/locked）
   - 新增 `lock_time` 字段
   - 保持与 ESP32 协议 v5.2 一致

3. **统一 seq_id 使用** ⚠️ 严重
   - Server 透传 App 的 seq_id 给 ESP32
   - Server 转发 ESP32 ack 时，将 msg_id 映射回 seq_id
   - 确保消息追踪的一致性

### 中优先级（建议修复）

4. **添加新增消息类型**
   - 添加 `door_opened_report` 消息定义
   - 添加 `password_report` 消息定义

5. **更新 event_report 事件列表**
   - 添加 `door_closed` 事件
   - 添加 `lock_success` 事件
   - 添加 `bolt_alarm` 事件

6. **明确 esp32_ack 处理**
   - 说明 `esp32_ack` 不转发给 App（仅 Server 内部使用）
   - 或者定义 `esp32_ack` 的转发规则

### 低优先级（可选修复）

7. **统一 query 消息字段名**
   - 明确区分 App → Server 查询（target）和 Server → ESP32 查询（command）
   - 或者统一使用同一个字段名

---

## 七、修复后的协议对比

### 修复后的 log_report（App 协议）

```json
{
    "type": "log_report",
    "ts": 1702234567890,
    "data": {
        "method": "finger",
        "status": "success",     // 修复：使用 status 替代 result
        "uid": 5,
        "lock_time": 0,          // 修复：新增 lock_time 字段
        "fail_count": 0
    }
}
```

### 修复后的错误码（App 协议）

**ESP32 ACK 错误码（0-10）：**
| code | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 设备离线 |
| 2 | 设备忙 |
| 3 | 参数错误 |
| 4 | 不支持 |
| 5 | 超时 |
| 6 | 硬件故障 |
| 7 | 资源已满 |
| 8 | 未认证 |
| 9 | 重复消息 |
| 10 | 内部错误 |

**server_ack 错误码（0-10）：**
| code | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 设备离线 |
| 2 | 设备忙 |
| 3 | 参数错误 |
| 4 | 不支持 |
| 5 | 超时 |
| 6 | 硬件故障 |
| 7 | 资源已满 |
| 8 | 未认证 |
| 9 | 重复消息 |
| 10 | 内部错误 |

### 修复后的 seq_id 流向

```
App                    Server                   ESP32
 │                        │                        │
 │── lock_control ───────►│                        │
 │   (seq_id=app_001)     │                        │
 │                        │                        │
 │◄── server_ack ────────│ (seq_id=app_001)       │
 │                        │                        │
 │                        │── lock_control ───────►│
 │                        │   (seq_id=app_001)     │  // 修复：透传 seq_id
 │                        │                        │
 │                        │◄── esp32_ack ─────────│
 │                        │   (seq_id=app_001)     │
 │                        │                        │
 │                        │◄───── ack ────────────│
 │                        │   (seq_id=app_001)     │  // 修复：使用 seq_id
 │◄── ack ───────────────│ (seq_id=app_001)       │  // 修复：映射回 seq_id
 │                        │                        │
```

---

## 八、总体结论

### 8.1 一致性评分

| 评估项 | 得分 | 说明 |
|--------|------|------|
| 消息类型一致性 | 85% | 大部分一致，缺少 2 个新增消息 |
| 字段格式一致性 | 70% | log_report 字段不一致 |
| 错误码一致性 | 60% | 三套错误码定义不统一 |
| seq_id 使用一致性 | 65% | 存在 seq_id/msg_id 混用 |
| ACK 机制一致性 | 75% | 机制相似，但字段名不统一 |
| **总体一致性** | **71%** | 需要修复多处不一致 |

### 8.2 主要问题总结

1. ❌ **错误码不统一**：ESP32 协议 0-10，App 协议 0-7，server_ack 0-5
2. ❌ **log_report 字段不一致**：ESP32 使用 status/lock_time，App 使用 result
3. ⚠️ **缺少新增消息**：door_opened_report、password_report
4. ⚠️ **缺少新增事件**：door_closed、lock_success、bolt_alarm
5. ⚠️ **seq_id/msg_id 混用**：消息追踪困难

### 8.3 修复建议

**必须修复（高优先级）：**
1. 统一错误码定义为 0-10
2. 更新 log_report 字段（status + lock_time）
3. 统一使用 seq_id，废弃 msg_id

**建议修复（中优先级）：**
4. 添加新增消息类型定义
5. 更新事件列表
6. 明确 esp32_ack 处理规则

**可选修复（低优先级）：**
7. 统一 query 消息字段名

---

**分析人员**：Kiro AI  
**分析日期**：2026-01-17  
**文档版本**：v1.0

