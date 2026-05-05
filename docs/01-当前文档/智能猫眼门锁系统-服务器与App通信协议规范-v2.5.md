# 智能猫眼门锁系统 - App 通信协议规范 v2.5

> **协议升级提示**：本文档已从 v2.4 升级到 v2.5，主要变更：
>
> - 新增 visitor_intent_notification 消息（访客意图通知）
> - 更新 event_report 事件类型（完善 bolt_alarm 说明）
> - 新增访客意图和快递警报查询接口
> - 完善智能门锁AI功能的协议支持

> **v2.4 变更回顾**：
>
> - 统一所有错误码为 0-10 体系（简化 server_ack 错误码使用）
> - 明确 server_ack 只用于接收确认（0/3/8/9），业务错误在业务响应中返回
> - 删除 server_ack 的 0-5 错误码定义，统一使用 0-10 错误码

## 1. 协议概述

### 1.1 传输层

| 项目     | 说明                           |
| -------- | ------------------------------ |
| 传输协议 | WebSocket                      |
| 连接端点 | `ws://{server}:8000/ws/app`    |
| 数据格式 | JSON (文本帧) / PCM (二进制帧) |

### 1.2 连接架构

```
┌─────────┐         ┌─────────┐         ┌─────────┐
│   App   │◄───────►│ Server  │◄───────►│  ESP32  │
└─────────┘         └─────────┘         └─────────┘
   /ws/app              │                  /ws
                        │
                   ConnectionManager
                   (设备关联管理)
```

### 1.3 通信模式

| 模式       | 说明                                      |
| ---------- | ----------------------------------------- |
| 请求-响应  | App 发送命令，Server 返回 server_ack 确认 |
| 服务器推送 | Server 主动推送设备状态、事件、通知       |
| 命令代理   | Server 记录日志后转发命令给 ESP32         |
| 实时流     | 监控模式下的音视频流传输                  |

### 1.4 设计原则

1. **消息类型统一**：App 发送的命令类型与 ESP32 协议一致
2. **服务器代理**：所有命令经服务器处理，便于日志记录和权限控制
3. **身份追踪**：通过 `app_id` 记录操作来源，支持审计
4. **消息确认**：通过 `seq_id` + `server_ack` 机制确保消息可靠送达

---

## 2. 连接认证

### 2.1 认证流程

```
App                          Server
 │                              │
 │──── WebSocket 连接 ─────────►│
 │                              │
 │──── hello 消息 ─────────────►│
 │                              │ 验证 device_id
 │                              │ 检查 ESP32 是否在线
 │                              │ 记录 app_id
 │◄─── hello 响应 ─────────────│
 │                              │
```

### 2.2 Hello 请求 (App → Server)

```json
{
  "type": "hello",
  "device_id": "AA:BB:CC:DD:EE:FF",
  "app_id": "user_12345",
  "client_type": "app"
}
```

| 字段        | 类型   | 必填 | 说明                             |
| ----------- | ------ | ---- | -------------------------------- |
| type        | string | 是   | 固定为 `"hello"`                 |
| device_id   | string | 是   | 要关联的 ESP32 设备 MAC 地址     |
| app_id      | string | 是   | App 用户唯一标识（用于日志审计） |
| client_type | string | 是   | 固定为 `"app"`                   |

### 2.3 Hello 响应 (Server → App)

**成功响应：**

```json
{
  "type": "hello",
  "status": "ok",
  "device_info": {
    "online": true,
    "mode": "normal"
  }
}
```

| 字段               | 类型   | 说明                           |
| ------------------ | ------ | ------------------------------ |
| status             | string | `"ok"` 表示成功                |
| device_info.online | bool   | ESP32 是否在线                 |
| device_info.mode   | string | 当前模式：`normal` / `monitor` |

**失败响应：**

```json
{
  "type": "hello",
  "status": "error",
  "message": "设备 AA:BB:CC:DD:EE:FF 不在线"
}
```

| 错误消息               | 说明                 |
| ---------------------- | -------------------- |
| 期望收到 hello 消息    | 首条消息不是 hello   |
| client_type 必须为 app | client_type 字段错误 |
| 缺少 device_id         | 未提供设备 ID        |
| 缺少 app_id            | 未提供 App 用户标识  |
| 设备 {id} 不在线       | ESP32 未连接到服务器 |

---

## 3. 消息确认机制 (ACK)

### 3.1 设计背景

WebSocket 基于 TCP，但存在以下问题：

- TCP 自动重传可能导致消息重复执行
- 无法确认服务器是否正确处理了消息
- App 无法判断是网络问题还是服务器问题

因此引入 `server_ack` 机制，与 ESP32 的 `ack` 区分开。

### 3.2 App 请求格式

App 发送的所有命令消息应携带 `seq_id` 字段：

```json
{
  "type": "lock_control",
  "seq_id": "1702234567890_001",
  "command": "unlock",
  "duration": 5
}
```

| 字段   | 类型   | 必填 | 说明                 |
| ------ | ------ | ---- | -------------------- |
| seq_id | string | 推荐 | App 生成的消息序列号 |

> **seq_id 格式规范**：`{timestamp}_{sequence}`（如 `1702234567890_0`）
>
> - timestamp: 毫秒级时间戳（13位）
> - sequence: 同一毫秒内的序号（从0开始递增）

### 3.3 服务器 ACK 响应 (Server → App)

服务器收到 App 消息后，立即返回 ACK 确认：

```json
{
  "type": "server_ack",
  "seq_id": "1702234567890_001",
  "code": 0,
  "msg": "已接收",
  "ts": 1702234567891
}
```

| 字段   | 类型   | 说明                  |
| ------ | ------ | --------------------- |
| type   | string | 固定为 `"server_ack"` |
| seq_id | string | 回填 App 发送的序列号 |
| code   | int    | 服务器处理状态码      |
| msg    | string | 状态描述              |
| ts     | int    | 服务器时间戳（毫秒）  |

### 3.4 服务器 ACK 错误码

服务器 ACK 使用统一的 0-10 错误码体系，但实际只用于接收确认场景：

| code | 含义     | 使用场景                  |
| ---- | -------- | ------------------------- |
| 0    | 成功     | 消息已接收并处理          |
| 3    | 参数错误 | 消息格式或参数不合法      |
| 8    | 未认证   | App 未完成 hello 认证     |
| 9    | 重复消息 | seq_id 重复，消息已处理过 |

> **重要说明**：
>
> - server_ack 只用于确认"服务器是否成功接收消息"，不涉及业务逻辑
> - 设备状态相关错误（如设备离线、设备忙、超时等）应在业务响应中返回
> - 所有错误码使用统一的 0-10 体系，与 ESP32 ack 保持一致
> - 业务响应可以使用完整的 0-10 错误码（见第 7.6 节）

### 3.5 防重放机制

服务器维护最近 100 条 `seq_id` 缓存（按 app_id 分组）：

- 收到消息时检查 `seq_id` 是否已存在
- 已存在则返回 `code=9`，不重复处理
- 缓存采用 FIFO 淘汰策略

### 3.6 重传策略建议

App 应实现以下重传逻辑：

1. 发送消息后启动 3 秒超时计时器
2. 收到 `server_ack` 后取消计时器
3. 超时未收到 `server_ack`，重传消息（最多 3 次）
4. 重传时使用相同的 `seq_id`

---

## 4. 设备上下线通知

### 4.1 设备上线通知 (Server → App)

ESP32 连接到服务器时，通知所有关联的 App：

```json
{
  "type": "device_status",
  "status": "online",
  "device_id": "AA:BB:CC:DD:EE:FF",
  "ts": 1702234567890
}
```

### 4.2 设备下线通知 (Server → App)

ESP32 断开连接时，通知所有关联的 App：

```json
{
  "type": "device_status",
  "status": "offline",
  "device_id": "AA:BB:CC:DD:EE:FF",
  "ts": 1702234567890,
  "reason": "connection_lost"
}
```

| 字段      | 类型   | 说明                      |
| --------- | ------ | ------------------------- |
| type      | string | 固定为 `"device_status"`  |
| status    | string | `online` / `offline`      |
| device_id | string | 设备 MAC 地址             |
| ts        | int    | 时间戳（毫秒）            |
| reason    | string | 下线原因（仅 offline 时） |

### 4.3 下线原因

| reason              | 说明         |
| ------------------- | ------------ |
| `connection_lost`   | 网络连接丢失 |
| `connection_closed` | 正常关闭连接 |
| `timeout`           | 超时断开     |
| `error`             | 错误断开     |

---

## 5. 设备控制命令 (App → Server → ESP32)

> 以下命令格式与 ESP32 协议完全一致，Server 记录操作日志后转发给 ESP32

### 5.1 远程开锁/关锁 (lock_control)

```json
{
  "type": "lock_control",
  "seq_id": "1702234567890_001",
  "command": "unlock",
  "duration": 5
}
```

| 字段     | 类型   | 说明                          |
| -------- | ------ | ----------------------------- |
| command  | string | `unlock`(开锁), `lock`(关锁)  |
| duration | int    | 开锁保持时间(秒)，0=默认3分钟 |

> **日志记录**：Server 记录 `app_id` 到开锁日志，`method` 为 `remote`

### 5.2 临时密码 (lock_control)

```json
{
  "type": "lock_control",
  "seq_id": "1702234567890_002",
  "command": "temp_code",
  "code": "123456",
  "expires": 3600
}
```

| 字段    | 类型   | 说明        |
| ------- | ------ | ----------- |
| code    | string | 6位临时密码 |
| expires | int    | 有效期(秒)  |

### 5.3 蜂鸣器控制 (dev_control)

```json
{
  "type": "dev_control",
  "seq_id": "1702234567890_003",
  "target": "beep",
  "count": 3,
  "mode": "alarm"
}
```

| 字段   | 类型   | 说明                                       |
| ------ | ------ | ------------------------------------------ |
| target | string | 固定为 `"beep"`                            |
| count  | int    | 响铃次数                                   |
| mode   | string | `short`(短滴), `long`(长鸣), `alarm`(报警) |

### 5.4 补光灯控制 (dev_control)

```json
{
  "type": "dev_control",
  "seq_id": "1702234567890_004",
  "target": "light",
  "action": "on"
}
```

| 字段   | 类型   | 说明                              |
| ------ | ------ | --------------------------------- |
| target | string | 固定为 `"light"`                  |
| action | string | `on`(开), `off`(关), `auto`(自动) |

### 5.5 OLED 显示控制 (dev_control)

```json
{
  "type": "dev_control",
  "seq_id": "1702234567890_005",
  "target": "oled",
  "icon": 3
}
```

| icon | 说明        |
| ---- | ----------- |
| 0    | 清屏/待机   |
| 1    | WiFi 已连接 |
| 2    | 云端已连接  |
| 3    | 识别中      |
| 4    | 识别成功    |
| 5    | 识别失败    |

### 5.6 用户管理 (user_mgmt)

```json
{
  "type": "user_mgmt",
  "seq_id": "1702234567890_006",
  "category": "finger",
  "command": "add",
  "user_id": 0,
  "user_name": "张三的右手食指"
}
```

| 字段      | 类型   | 说明                                                            |
| --------- | ------ | --------------------------------------------------------------- |
| category  | string | `finger`(指纹), `nfc`(卡片), `password`(密码)                   |
| command   | string | `add`(增), `del`(删), `clear`(清), `query`(查), `set`(设置密码) |
| user_id   | int    | 0=自动分配，删除时必填                                          |
| user_name | string | 用户备注名称（可选，仅 `add` 命令时有效）                       |
| payload   | string | 仅 `category=password` 且 `command=set` 时有效                  |

> **说明**：
>
> - `user_name` 字段为可选，用于给指纹/NFC 添加备注（如"张三的右手食指"）
> - Server 会将 `user_name` 存储到数据库，ESP32 不接收此字段
> - 添加成功后，可通过 `query` 接口（`target=doorlock_users`）查询用户列表
> - 密码查询已改为使用 `query` 接口（`target=password`），不再支持 `user_mgmt` 查询

---

## 6. 系统命令 (App → Server)

### 6.1 启动监控模式

```json
{
  "type": "system",
  "seq_id": "1702234567890_007",
  "command": "start_monitor",
  "record": false
}
```

| 字段    | 类型   | 必填 | 说明                       |
| ------- | ------ | ---- | -------------------------- |
| command | string | 是   | 固定为 `"start_monitor"`   |
| record  | bool   | 否   | 是否保存录像，默认 `false` |

**响应：**

```json
{
  "type": "system",
  "status": "success",
  "command": "start_monitor",
  "recording": false
}
```

### 6.2 停止监控模式

```json
{
  "type": "system",
  "seq_id": "1702234567890_008",
  "command": "stop_monitor"
}
```

**响应：**

```json
{
  "type": "system",
  "status": "success",
  "command": "stop_monitor"
}
```

### 6.3 错误响应

```json
{
  "type": "system",
  "status": "error",
  "message": "ESP32 连接不可用"
}
```

---

## 7. 服务器推送消息 (Server → App)

### 7.1 设备状态推送 (status_report)

ESP32 上报状态时，Server 自动推送给 App：

```json
{
  "type": "status_report",
  "ts": 1702234567890,
  "data": {
    "bat": 85,
    "lux": 300,
    "lock": 0,
    "light": 1
  }
}
```

| 字段  | 类型 | 说明                   |
| ----- | ---- | ---------------------- |
| bat   | int  | 电量百分比 (0-100)     |
| lux   | int  | 光照值 (Lux)           |
| lock  | int  | 锁状态：0=关闭, 1=打开 |
| light | int  | 补光灯：0=灭, 1=亮     |

### 7.2 事件推送 (event_report)

```json
{
  "type": "event_report",
  "ts": 1702234567890,
  "event": "bell",
  "param": 1
}
```

| event          | 说明           | param 含义     |
| -------------- | -------------- | -------------- |
| `bell`         | 门铃按下       | 无             |
| `pir_trigger`  | PIR 人体检测   | 持续时间(秒)   |
| `tamper`       | 撬锁报警       | 报警级别 (1-3) |
| `door_open`    | 门未关超时     | 超时时间(分钟) |
| `door_closed`  | 门已关闭       | 无             |
| `lock_success` | 上锁成功       | 无             |
| `bolt_alarm`   | 锁舌未到位报警 | 报警类型       |
| `low_battery`  | 低电量警告     | 当前电量(%)    |

> **说明**：
>
> - `bolt_alarm`：锁舌未到位报警，即门未成功上锁报警。当门锁尝试上锁但锁舌未能到达预定位置时触发。

### 7.3 开锁日志推送 (log_report)

```json
{
  "type": "log_report",
  "ts": 1702234567890,
  "data": {
    "method": "finger",
    "uid": 5,
    "status": "success",
    "lock_time": 0,
    "fail_count": 0
  }
}
```

| 字段       | 类型   | 说明                                                        |
| ---------- | ------ | ----------------------------------------------------------- |
| method     | string | 开锁方式                                                    |
| uid        | int    | 用户 ID                                                     |
| status     | string | 开锁状态：success=成功, fail=失败, locked=已锁定            |
| lock_time  | int    | 剩余锁定时间（分钟），仅 status=locked 时 > 0，其他情况为 0 |
| fail_count | int    | 连续失败次数                                                |

| method     | 说明          |
| ---------- | ------------- |
| `finger`   | 指纹开锁      |
| `nfc`      | NFC 开锁      |
| `face`     | 人脸开锁      |
| `pwd`      | 密码开锁      |
| `temp_pwd` | 临时密码开锁  |
| `key`      | 机械钥匙      |
| `remote`   | 远程开锁(App) |

| status    | 说明                           |
| --------- | ------------------------------ |
| `success` | 开锁成功                       |
| `fail`    | 开锁失败                       |
| `locked`  | 设备已锁定（连续失败次数过多） |

> **协议升级说明**：v2.3 版本将 `result` (bool) 字段改为 `status` (string) 字段，并新增 `lock_time` 字段表示剩余锁定时间，提供更精确的状态信息。v5.0 旧版使用 `result: true/false` 表示成功/失败，服务器会自动兼容转换。

### 7.4 到访通知 (visit_notification)

人脸识别完成后，Server 主动推送识别结果和抓拍图片：

```json
{
  "type": "visit_notification",
  "ts": 1702234567890,
  "data": {
    "visit_id": 123,
    "person_id": 5,
    "person_name": "张三",
    "relation": "family",
    "result": "known",
    "access_granted": true,
    "image": "base64_encoded_jpeg_data",
    "image_path": "faces/AA:BB:CC:DD:EE:FF/2024-12-11/face_1702234567890_5.jpg"
  }
}
```

| 字段           | 类型   | 说明                          |
| -------------- | ------ | ----------------------------- |
| ts             | int    | 识别时间戳（毫秒）            |
| visit_id       | int    | 到访记录 ID                   |
| person_id      | int    | 人员 ID（陌生人为 null）      |
| person_name    | string | 人员姓名（陌生人为 "陌生人"） |
| relation       | string | 关系类型                      |
| result         | string | `known`/`unknown`/`no_face`   |
| access_granted | bool   | 是否授权开锁                  |
| image          | string | Base64 编码的 JPEG 图片       |
| image_path     | string | 图片存储路径（用于后续下载）  |

### 7.5 用户管理结果 (user_mgmt_result)

```json
{
  "type": "user_mgmt_result",
  "category": "finger",
  "command": "add",
  "result": true,
  "val": 6,
  "msg": "Success"
}
```

| 字段   | 类型   | 说明                           |
| ------ | ------ | ------------------------------ |
| result | bool   | 操作结果                       |
| val    | int    | 成功时=分配的ID，失败时=错误码 |
| msg    | string | 结果描述                       |

### 7.6 ESP32 ACK 响应 (ack)

ESP32 执行命令后的确认，Server 转发给 App：

```json
{
  "type": "ack",
  "seq_id": "1702234567890_001",
  "code": 0,
  "msg": "OK"
}
```

| 字段   | 类型   | 说明                   |
| ------ | ------ | ---------------------- |
| type   | string | 固定为 `"ack"`         |
| seq_id | string | App 发送命令时的序列号 |
| code   | int    | 执行结果错误码（0-10） |
| msg    | string | 结果描述               |

**统一错误码（0-10）**：

| code | 含义     | 说明             |
| ---- | -------- | ---------------- |
| 0    | 成功     | 命令执行成功     |
| 1    | 设备离线 | ESP32 未连接     |
| 2    | 设备忙碌 | 正在执行其他任务 |
| 3    | 参数错误 | 命令参数不合法   |
| 4    | 不支持   | 设备不支持该命令 |
| 5    | 超时     | 命令执行超时     |
| 6    | 硬件故障 | 硬件错误         |
| 7    | 资源已满 | 存储空间不足     |
| 8    | 未认证   | 权限不足         |
| 9    | 重复消息 | 消息已处理过     |
| 10   | 内部错误 | 设备内部错误     |

> **ID 映射说明**：
>
> - App 发送命令时携带 `seq_id`（如 `app_1702234567890_001`）
> - Server 转发给 ESP32 时使用 `msg_id`（透传 seq_id）
> - ESP32 返回 ack 时携带 `msg_id`
> - Server 转发给 App 时保持原始 `seq_id`，确保 App 可以匹配响应
>
> **注意**：`esp32_ack`（ESP32 收到命令的即时确认）不会转发给 App，只有最终的 `ack`（命令执行结果）会转发

### 7.7 门已开启通知 (door_opened_report)

ESP32 检测到门已开启时上报，Server 转发给 App：

```json
{
  "type": "door_opened_report",
  "ts": 1702234567890,
  "data": {
    "method": "finger",
    "source": "outside"
  }
}
```

| 字段   | 类型   | 说明                                                       |
| ------ | ------ | ---------------------------------------------------------- |
| method | string | 开锁方式（同 log_report）                                  |
| source | string | 开门来源：`outside`(外侧), `inside`(内侧), `unknown`(未知) |

> **说明**：此消息用于记录门的物理开启事件，与 log_report（开锁日志）配合使用

### 7.8 密码上报 (password_report)

ESP32 上报密码查询结果：

```json
{
  "type": "password_report",
  "ts": 1702234567890,
  "data": {
    "password": "123456"
  }
}
```

| 字段     | 类型   | 说明     |
| -------- | ------ | -------- |
| password | string | 密码内容 |

> **说明**：此消息仅用于密码查询结果的返回，不存储到数据库

### 7.9 访客意图通知 (visitor_intent_notification)

访客对话结束后，服务器生成意图总结并推送给App：

```json
{
  "type": "visitor_intent_notification",
  "ts": 1702234567890,
  "visit_id": 12345,
  "session_id": "session_123",
  "person_info": {
    "person_id": 10,
    "name": "张三",
    "relation_type": "family"
  },
  "intent_summary": {
    "intent_type": "delivery",
    "summary": "快递员送快递，已放门口",
    "important_notes": ["【留言】快递放门口了，麻烦签收一下"],
    "ai_analysis": "访客是快递员，来送快递，表示快递已放在门口，请求签收。"
  },
  "dialogue_history": [
    {
      "role": "assistant",
      "content": "您好，请问有什么可以帮您？"
    },
    {
      "role": "user",
      "content": "我是来送快递的"
    },
    {
      "role": "assistant",
      "content": "好的，请问快递放在哪里？"
    },
    {
      "role": "user",
      "content": "我放门口了，麻烦签收一下"
    }
  ],
  "package_check": {
    "threat_level": "low",
    "action": "normal",
    "description": "快递安全，未被触碰"
  }
}
```

**字段说明**：

| 字段                           | 类型   | 必填 | 说明                                   |
| ------------------------------ | ------ | ---- | -------------------------------------- |
| type                           | string | 是   | 固定为 `"visitor_intent_notification"` |
| ts                             | int    | 是   | 时间戳（毫秒）                         |
| visit_id                       | int    | 是   | 访问记录ID                             |
| session_id                     | string | 是   | 会话ID                                 |
| person_info                    | object | 否   | 人员信息（识别成功时有值）             |
| person_info.person_id          | int    | 否   | 人员ID                                 |
| person_info.name               | string | 否   | 人员姓名                               |
| person_info.relation_type      | string | 否   | 关系类型：family/friend/unknown        |
| intent_summary                 | object | 是   | 意图总结                               |
| intent_summary.intent_type     | string | 是   | 意图类型                               |
| intent_summary.summary         | string | 是   | 简洁总结（一句话）                     |
| intent_summary.important_notes | array  | 是   | 重要信息列表                           |
| intent_summary.ai_analysis     | string | 是   | 详细AI分析                             |
| dialogue_history               | array  | 是   | 完整对话历史                           |
| dialogue_history[].role        | string | 是   | 角色：assistant/user                   |
| dialogue_history[].content     | string | 是   | 对话内容                               |
| package_check                  | object | 否   | 快递检查结果（看护模式激活时有值）     |
| package_check.threat_level     | string | 否   | 威胁等级：low/medium/high              |
| package_check.action           | string | 否   | 行为类型                               |
| package_check.description      | string | 否   | 详细描述                               |

**意图类型说明**：

| intent_type | 说明          | 示例场景           |
| ----------- | ------------- | ------------------ |
| delivery    | 送快递/外卖   | 快递员、外卖员送货 |
| visit       | 拜访朋友/家人 | 朋友来访、邻居串门 |
| sales       | 推销产品/服务 | 推销员、广告宣传   |
| maintenance | 维修/物业工作 | 维修工、抄表员     |
| other       | 其他情况      | 未列出的意图识别   |

**威胁等级说明**：

| threat_level | 说明   | 触发条件                           |
| ------------ | ------ | ---------------------------------- |
| low          | 低威胁 | 快递未被触碰、主人取快递、路人经过 |
| medium       | 中威胁 | 快递被移动但未拿走、访客翻看快递   |
| high         | 高威胁 | 快递被非主人拿走、快递被破坏       |

**行为类型说明**：

| action    | 说明                   |
| --------- | ---------------------- |
| normal    | 正常状态，快递未被触碰 |
| passing   | 路人经过，未触碰快递   |
| searching | 翻看或移动快递         |
| taking    | 拿走快递               |
| damaging  | 破坏快递               |

**触发时机**：

- PIR事件或门铃事件触发人脸识别
- 人脸识别完成后，无权限访客启动意图识别对话
- 对话结束后，服务器生成意图总结并推送此消息

**使用场景**：

1. App接收到此消息后，在通知栏显示访客意图
2. 如果有重要信息（important_notes），高亮显示
3. 如果威胁等级为medium或high，发送警报通知
4. 保存对话历史供用户查看

---

## 8. 人脸管理 (App → Server)

### 8.1 人脸录入

```json
{
  "type": "face_management",
  "seq_id": "1702234567890_009",
  "action": "register",
  "data": {
    "name": "张三",
    "relation_type": "family",
    "images": ["base64_jpeg_1", "base64_jpeg_2"],
    "permission": {
      "permission_type": "permanent",
      "time_start": "08:00:00",
      "time_end": "22:00:00"
    }
  }
}
```

**响应：**

```json
{
  "type": "face_management",
  "action": "register",
  "status": "success",
  "person_id": 5
}
```

### 8.2 获取人员列表

```json
{
  "type": "face_management",
  "seq_id": "1702234567890_010",
  "action": "get_persons"
}
```

**响应：**

```json
{
  "type": "face_management",
  "action": "get_persons",
  "status": "success",
  "data": [
    {
      "id": 1,
      "name": "张三",
      "relation_type": "family",
      "created_at": "2024-12-11T10:00:00"
    }
  ]
}
```

### 8.3 删除人员

```json
{
  "type": "face_management",
  "seq_id": "1702234567890_011",
  "action": "delete_person",
  "data": { "person_id": 5 }
}
```

### 8.4 更新权限

```json
{
  "type": "face_management",
  "seq_id": "1702234567890_012",
  "action": "update_permission",
  "data": {
    "person_id": 5,
    "permission": {
      "permission_type": "temporary",
      "valid_from": "2024-12-11",
      "valid_until": "2024-12-31",
      "remaining_count": 10
    }
  }
}
```

### 8.5 获取到访记录

```json
{
  "type": "face_management",
  "seq_id": "1702234567890_013",
  "action": "get_visits",
  "data": {
    "page": 1,
    "page_size": 20,
    "date_from": "2024-12-01",
    "date_to": "2024-12-11"
  }
}
```

---

## 9. 数据查询接口 (App → Server)

### 9.1 查询设备状态

获取设备当前状态（从内存缓存或数据库读取）：

**请求：**

```json
{
  "type": "query",
  "seq_id": "1702234567890_014",
  "target": "status"
}
```

**响应：**

```json
{
  "type": "query_result",
  "target": "status",
  "status": "success",
  "data": {
    "battery": 85,
    "lux": 300,
    "lock_state": 0,
    "light_state": 1,
    "last_update": 1702234567890
  }
}
```

### 9.2 查询历史状态

**请求：**

```json
{
  "type": "query",
  "seq_id": "1702234567890_015",
  "target": "status_history",
  "data": {
    "limit": 100,
    "offset": 0
  }
}
```

**响应：**

```json
{
  "type": "query_result",
  "target": "status_history",
  "status": "success",
  "data": {
    "records": [
      {
        "id": 1001,
        "battery": 85,
        "lux": 300,
        "lock_state": 0,
        "light_state": 1,
        "created_at": "2024-12-11T10:00:00"
      }
    ],
    "total": 1500,
    "limit": 100,
    "offset": 0
  }
}
```

### 9.3 查询事件历史

**请求：**

```json
{
  "type": "query",
  "seq_id": "1702234567890_016",
  "target": "events",
  "data": {
    "event_type": "bell",
    "limit": 100,
    "offset": 0
  }
}
```

| 字段       | 类型   | 必填 | 说明                         |
| ---------- | ------ | ---- | ---------------------------- |
| event_type | string | 否   | 事件类型过滤                 |
| limit      | int    | 否   | 返回条数，默认 100，最大 500 |
| offset     | int    | 否   | 偏移量，默认 0               |

**响应：**

```json
{
  "type": "query_result",
  "target": "events",
  "status": "success",
  "data": {
    "records": [
      {
        "id": 501,
        "event_type": "bell",
        "param": 1,
        "created_at": "2024-12-11T10:30:00"
      }
    ],
    "total": 501,
    "limit": 100,
    "offset": 0
  }
}
```

### 9.4 查询开锁日志

**请求：**

```json
{
  "type": "query",
  "seq_id": "1702234567890_017",
  "target": "unlock_logs",
  "data": {
    "method": "finger",
    "result": 1,
    "limit": 100,
    "offset": 0
  }
}
```

| 字段   | 类型   | 必填 | 说明                         |
| ------ | ------ | ---- | ---------------------------- |
| method | string | 否   | 开锁方式过滤                 |
| result | int    | 否   | 结果过滤：1=成功, 0=失败     |
| limit  | int    | 否   | 返回条数，默认 100，最大 500 |
| offset | int    | 否   | 偏移量，默认 0               |

**响应：**

```json
{
  "type": "query_result",
  "target": "unlock_logs",
  "status": "success",
  "data": {
    "records": [
      {
        "id": 201,
        "method": "finger",
        "user_id": 5,
        "result": 1,
        "fail_count": 0,
        "created_at": "2024-12-11T10:30:00"
      }
    ],
    "total": 201,
    "limit": 100,
    "offset": 0
  }
}
```

### 9.5 查询媒体文件列表

**请求：**

```json
{
  "type": "query",
  "seq_id": "1702234567890_018",
  "target": "media_files",
  "data": {
    "file_type": "face",
    "date_from": "2024-12-01",
    "date_to": "2024-12-11",
    "limit": 100,
    "offset": 0
  }
}
```

| 字段      | 类型   | 必填 | 说明                                          |
| --------- | ------ | ---- | --------------------------------------------- |
| file_type | string | 否   | 文件类型：`face`(人脸图片), `recording`(录像) |
| date_from | string | 否   | 开始日期 (YYYY-MM-DD)                         |
| date_to   | string | 否   | 结束日期 (YYYY-MM-DD)                         |
| limit     | int    | 否   | 返回条数，默认 100，最大 500                  |
| offset    | int    | 否   | 偏移量，默认 0                                |

**响应：**

```json
{
  "type": "query_result",
  "target": "media_files",
  "status": "success",
  "data": {
    "records": [
      {
        "id": 101,
        "file_type": "face",
        "file_path": "faces/AA:BB:CC:DD:EE:FF/2024-12-11/face_1702234567890_5.jpg",
        "file_size": 51200,
        "user_id": 5,
        "duration": null,
        "created_at": "2024-12-11T10:30:00"
      }
    ],
    "total": 101,
    "limit": 100,
    "offset": 0
  }
}
```

### 9.6 查询设备密码

从服务器数据库查询设备密码（不查询 ESP32）：

**请求：**

```json
{
  "type": "query",
  "seq_id": "1702234567890_022",
  "target": "password"
}
```

**响应（成功）：**

```json
{
  "type": "query_result",
  "target": "password",
  "status": "success",
  "data": {
    "password": "654321"
  }
}
```

**响应（密码不存在）：**

```json
{
  "type": "query_result",
  "target": "password",
  "status": "success",
  "data": {
    "password": "123456"
  }
}
```

| 字段     | 类型   | 说明                                  |
| -------- | ------ | ------------------------------------- |
| password | string | 设备密码，不存在时返回默认值 "123456" |

> **说明**：
>
> - 密码存储在服务器数据库，不需要查询 ESP32
> - 如果数据库中没有密码记录，返回默认密码 "123456"
> - 此接口替代了旧版通过 user_mgmt 查询密码的方式

### 9.7 查询门锁用户列表

查询设备的指纹、NFC、密码用户列表（从服务器数据库读取）：

**请求：**

```json
{
  "type": "query",
  "seq_id": "1702234567890_023",
  "target": "doorlock_users",
  "data": {
    "user_type": "finger",
    "limit": 100,
    "offset": 0
  }
}
```

| 字段      | 类型   | 必填 | 说明                                                                            |
| --------- | ------ | ---- | ------------------------------------------------------------------------------- |
| user_type | string | 否   | 用户类型过滤：`finger`(指纹), `nfc`(卡片), `password`(密码)，不填则查询所有类型 |
| limit     | int    | 否   | 返回条数，默认 100，最大 500                                                    |
| offset    | int    | 否   | 偏移量，默认 0                                                                  |

**响应（成功）：**

```json
{
  "type": "query_result",
  "target": "doorlock_users",
  "status": "success",
  "data": {
    "records": [
      {
        "id": 1,
        "device_id": "AA:BB:CC:DD:EE:FF",
        "user_type": "finger",
        "user_id": 5,
        "user_name": "张三的右手食指",
        "user_data": null,
        "status": 1,
        "created_at": "2024-12-11T10:30:00",
        "created_by": "user_12345"
      },
      {
        "id": 2,
        "device_id": "AA:BB:CC:DD:EE:FF",
        "user_type": "nfc",
        "user_id": 3,
        "user_name": "李四的门禁卡",
        "user_data": "1234567890ABCDEF",
        "status": 1,
        "created_at": "2024-12-11T11:00:00",
        "created_by": "user_12345"
      }
    ],
    "total": 2,
    "limit": 100,
    "offset": 0
  }
}
```

| 字段       | 类型   | 说明                                      |
| ---------- | ------ | ----------------------------------------- |
| id         | int    | 数据库记录 ID                             |
| device_id  | string | 设备 MAC 地址                             |
| user_type  | string | 用户类型：finger/nfc/password             |
| user_id    | int    | ESP32 分配的用户 ID（指纹/NFC 的槽位 ID） |
| user_name  | string | 用户备注名称                              |
| user_data  | string | 额外数据（如 NFC 卡号）                   |
| status     | int    | 状态：0=已删除，1=正常                    |
| created_at | string | 创建时间                                  |
| created_by | string | 创建者 app_id                             |

> **说明**：
>
> - 用户数据存储在服务器数据库，不需要查询 ESP32
> - 通过 `user_mgmt` 命令添加用户时，如果提供了 `user_name`，会自动保存到数据库
> - 删除用户时会软删除（status=0），不会物理删除记录
> - 清空用户时会批量软删除所有该类型的用户

### 9.8 查询访客意图历史

查询设备的访客意图识别历史记录（从服务器数据库读取）：

**请求：**

```json
{
  "type": "query",
  "seq_id": "1702234567890_024",
  "target": "visitor_intents",
  "data": {
    "start_date": "2024-12-01",
    "end_date": "2024-12-31",
    "limit": 20,
    "offset": 0
  }
}
```

| 字段       | 类型   | 必填 | 说明                      |
| ---------- | ------ | ---- | ------------------------- |
| start_date | string | 否   | 开始日期 (YYYY-MM-DD)     |
| end_date   | string | 否   | 结束日期 (YYYY-MM-DD)     |
| limit      | int    | 否   | 返回条数，默认20，最大100 |
| offset     | int    | 否   | 偏移量，默认0             |

**响应（成功）：**

```json
{
  "type": "query_result",
  "target": "visitor_intents",
  "status": "success",
  "data": {
    "records": [
      {
        "id": 123,
        "visit_id": 456,
        "session_id": "device001_1707379822000",
        "person_id": 10,
        "intent_type": "delivery",
        "intent_summary": {
          "intent_type": "delivery",
          "summary": "快递员送快递，已放门口",
          "important_notes": ["【留言】快递放门口了"],
          "ai_analysis": "访客是快递员，来送快递..."
        },
        "dialogue_history": [
          { "role": "assistant", "content": "您好，请问有什么可以帮您？" },
          { "role": "user", "content": "我是来送快递的" }
        ],
        "created_at": "2024-12-11T10:30:00"
      }
    ],
    "total": 50,
    "limit": 20,
    "offset": 0
  }
}
```

| 字段             | 类型   | 说明                   |
| ---------------- | ------ | ---------------------- |
| id               | int    | 记录ID                 |
| visit_id         | int    | 关联的访问记录ID       |
| session_id       | string | 会话ID                 |
| person_id        | int    | 人员ID（陌生人为null） |
| intent_type      | string | 意图类型               |
| intent_summary   | object | 意图总结（JSON对象）   |
| dialogue_history | array  | 对话历史（JSON数组）   |
| created_at       | string | 创建时间               |

> **说明**：
>
> - 访客意图记录存储在服务器数据库
> - 支持按日期范围过滤
> - 支持分页查询
> - 返回完整的对话历史和意图总结

### 9.9 查询快递警报历史

查询设备的快递异常警报历史记录（从服务器数据库读取）：

**请求：**

```json
{
  "type": "query",
  "seq_id": "1702234567890_025",
  "target": "package_alerts",
  "data": {
    "threat_level": "high",
    "start_date": "2024-12-01",
    "end_date": "2024-12-31",
    "limit": 20,
    "offset": 0
  }
}
```

| 字段         | 类型   | 必填 | 说明                          |
| ------------ | ------ | ---- | ----------------------------- |
| threat_level | string | 否   | 威胁等级过滤：low/medium/high |
| start_date   | string | 否   | 开始日期 (YYYY-MM-DD)         |
| end_date     | string | 否   | 结束日期 (YYYY-MM-DD)         |
| limit        | int    | 否   | 返回条数，默认20，最大100     |
| offset       | int    | 否   | 偏移量，默认0                 |

**响应（成功）：**

```json
{
  "type": "query_result",
  "target": "package_alerts",
  "status": "success",
  "data": {
    "records": [
      {
        "id": 789,
        "device_id": "AA:BB:CC:DD:EE:FF",
        "session_id": "device001_1707379822000",
        "threat_level": "high",
        "action": "taking",
        "description": "检测到非主人拿走快递",
        "photo_path": "alerts/device001/2024-12-11/alert_1707379822000.jpg",
        "voice_warning_sent": true,
        "notified": true,
        "created_at": "2024-12-11T10:30:00"
      }
    ],
    "total": 5,
    "limit": 20,
    "offset": 0
  }
}
```

| 字段               | 类型   | 说明                      |
| ------------------ | ------ | ------------------------- |
| id                 | int    | 记录ID                    |
| device_id          | string | 设备ID                    |
| session_id         | string | 会话ID                    |
| threat_level       | string | 威胁等级：low/medium/high |
| action             | string | 行为类型                  |
| description        | string | 详细描述                  |
| photo_path         | string | 警报照片路径              |
| voice_warning_sent | bool   | 是否已发送语音警告        |
| notified           | bool   | 是否已通知App             |
| created_at         | string | 创建时间                  |

> **说明**：
>
> - 快递警报记录存储在服务器数据库
> - 支持按威胁等级和日期范围过滤
> - 支持分页查询
> - 可通过photo_path下载警报照片

### 9.10 查询错误响应

```json
{
  "type": "query_result",
  "target": "status",
  "status": "error",
  "error": "数据库不可用"
}
```

---

## 10. 媒体文件下载 (App → Server)

### 10.1 下载完整文件

用于下载小于 50MB 的文件：

**请求（通过 ID）：**

```json
{
  "type": "media_download",
  "seq_id": "1702234567890_019",
  "file_id": 101
}
```

**请求（通过路径）：**

```json
{
  "type": "media_download",
  "seq_id": "1702234567890_020",
  "file_path": "faces/AA:BB:CC:DD:EE:FF/2024-12-11/face_1702234567890_5.jpg"
}
```

**响应（成功）：**

```json
{
  "type": "media_download",
  "status": "success",
  "data": {
    "file_id": 101,
    "file_type": "face",
    "file_name": "face_1702234567890_5.jpg",
    "file_size": 51200,
    "mime_type": "image/jpeg",
    "content": "base64_encoded_file_data"
  }
}
```

**响应（失败）：**

```json
{
  "type": "media_download",
  "status": "error",
  "error": "file_not_found",
  "message": "文件不存在或已被删除"
}
```

| error            | 说明                  |
| ---------------- | --------------------- |
| `missing_params` | 缺少必要参数          |
| `file_not_found` | 文件不存在            |
| `file_too_large` | 文件过大（超过 50MB） |
| `access_denied`  | 无权访问该文件        |
| `internal_error` | 服务器内部错误        |

### 10.2 分片下载大文件

用于下载超过 5MB 的大文件（如监控录像）：

**请求：**

```json
{
  "type": "media_download_chunk",
  "seq_id": "1702234567890_021",
  "file_id": 100,
  "chunk_index": 0,
  "chunk_size": 1048576
}
```

| 字段        | 类型 | 必填 | 说明                                 |
| ----------- | ---- | ---- | ------------------------------------ |
| file_id     | int  | 是   | 文件记录 ID                          |
| chunk_index | int  | 是   | 分片索引（从 0 开始）                |
| chunk_size  | int  | 否   | 分片大小（字节），默认 1MB，最大 5MB |

**响应：**

```json
{
  "type": "media_download_chunk",
  "status": "success",
  "data": {
    "file_id": 100,
    "chunk_index": 0,
    "total_chunks": 10,
    "file_size": 10485760,
    "chunk_size": 1048576,
    "content": "base64_encoded_chunk_data"
  }
}
```

### 10.3 文件大小限制说明

**完整下载限制：**

- 最大文件大小：50MB (52,428,800 字节)
- 超过限制返回 `file_too_large` 错误
- 建议使用分片下载

**分片下载参数：**

- 默认分片大小：1MB (1,048,576 字节)
- 最大分片大小：5MB (5,242,880 字节)
- 最小分片大小：100KB (102,400 字节)

**使用建议：**

| 文件大小 | 推荐方式 | 说明                   |
| -------- | -------- | ---------------------- |
| < 5MB    | 完整下载 | 一次性下载，速度快     |
| 5-50MB   | 完整下载 | 可能较慢，建议分片下载 |
| > 50MB   | 分片下载 | 必须使用分片下载       |
| > 100MB  | 分片下载 | 建议使用 2-5MB 分片    |

---

## 11. 监控模式音视频流

### 11.1 视频流 (Server → App)

监控模式下，Server 将 ESP32 的视频帧转发给 App：

| 参数     | 值                 |
| -------- | ------------------ |
| 格式     | JPEG 图像序列      |
| 分辨率   | 640×480            |
| 帧率     | 约 10 fps          |
| 传输方式 | WebSocket 二进制帧 |

### 11.2 音频流 (双向)

**Server → App（ESP32 音频）：**

| 参数   | 值     |
| ------ | ------ |
| 格式   | PCM    |
| 采样率 | 16kHz  |
| 声道   | 单声道 |
| 位深   | 16-bit |

**App → Server → ESP32（对讲音频）：**

| 参数          | 值                          |
| ------------- | --------------------------- |
| App 发送格式  | PCM (24kHz, 单声道, 16-bit) |
| Server 编码后 | OPUS (24kHz, 60ms 帧)       |

### 11.3 音频解码错误处理

**Server → App 音频流错误处理：**

Server 在转发 ESP32 音频流时，会进行 OPUS → PCM 解码。解码过程中可能出现错误，Server 采用以下策略：

**错误处理机制：**

1. **日志限流**：
   - 每 5 秒最多打印一次错误日志
   - 或每 100 次错误打印一次
   - 避免日志洪水

2. **解码器重置**：
   - 累计错误次数 > 10 次时自动重置解码器
   - 重置后错误计数清零
   - 重置失败不影响后续流程

3. **帧跳过策略**：
   - 解码失败的帧直接跳过
   - 不中断音频流传输
   - 继续处理后续帧

**错误场景：**

| 错误类型       | 原因          | 处理方式       |
| -------------- | ------------- | -------------- |
| 解码失败       | OPUS 数据损坏 | 跳过该帧       |
| 帧长度不匹配   | 网络传输错误  | 跳过该帧       |
| 解码器状态异常 | 累计错误过多  | 重置解码器     |
| 内存不足       | 系统资源不足  | 记录错误，跳过 |

**App 端建议：**

- 实现音频缓冲区，容忍少量丢帧
- 检测音频流中断，提示用户网络问题
- 支持重新连接监控模式

---

## 12. 消息类型汇总

### 12.1 App 发送的消息类型

| type                   | 说明     | Handler                   |
| ---------------------- | -------- | ------------------------- |
| `hello`                | 连接认证 | HelloTextMessageHandler   |
| `lock_control`         | 锁控命令 | LockControlProxyHandler   |
| `dev_control`          | 设备控制 | DevControlProxyHandler    |
| `user_mgmt`            | 用户管理 | UserMgmtProxyHandler      |
| `system`               | 系统命令 | SystemTextMessageHandler  |
| `face_management`      | 人脸管理 | FaceManagementHandler     |
| `query`                | 数据查询 | QueryHandler              |
| `media_download`       | 媒体下载 | MediaDownloadHandler      |
| `media_download_chunk` | 分片下载 | MediaDownloadChunkHandler |

### 12.2 Server 推送的消息类型

| type                          | 说明         | 来源       |
| ----------------------------- | ------------ | ---------- |
| `hello`                       | 认证响应     | Server     |
| `server_ack`                  | 消息确认     | Server     |
| `device_status`               | 设备上下线   | Server     |
| `status_report`               | 状态上报     | ESP32 转发 |
| `event_report`                | 事件上报     | ESP32 转发 |
| `log_report`                  | 开锁日志     | ESP32 转发 |
| `door_opened_report`          | 门已开启通知 | ESP32 转发 |
| `password_report`             | 密码上报     | ESP32 转发 |
| `user_mgmt_result`            | 用户管理结果 | ESP32 转发 |
| `ack`                         | ESP32 ACK    | ESP32 转发 |
| `visit_notification`          | 到访通知     | Server     |
| `visitor_intent_notification` | 访客意图通知 | Server     |
| `query_result`                | 查询结果     | Server     |
| `media_download`              | 下载响应     | Server     |
| `media_download_chunk`        | 分片响应     | Server     |
| `system`                      | 系统响应     | Server     |
| `face_management`             | 人脸管理响应 | Server     |

> **注意**：`esp32_ack`（ESP32 收到命令的即时确认）不会转发给 App

---

## 13. 与 ESP32 协议对比

### 13.1 消息类型对比

| 消息类型                      | ESP32 协议 | App 协议 | 说明                 |
| ----------------------------- | ---------- | -------- | -------------------- |
| `hello`                       | ❌         | ✅       | App 认证专用         |
| `status_report`               | ✅ 上报    | ✅ 接收  | Server 转发          |
| `event_report`                | ✅ 上报    | ✅ 接收  | Server 转发          |
| `log_report`                  | ✅ 上报    | ✅ 接收  | Server 转发          |
| `door_opened_report`          | ✅ 上报    | ✅ 接收  | Server 转发          |
| `password_report`             | ✅ 上报    | ✅ 接收  | Server 转发          |
| `lock_control`                | ✅ 接收    | ✅ 发送  | Server 代理转发      |
| `dev_control`                 | ✅ 接收    | ✅ 发送  | Server 代理转发      |
| `user_mgmt`                   | ✅ 接收    | ✅ 发送  | Server 代理转发      |
| `user_mgmt_result`            | ✅ 上报    | ✅ 接收  | Server 转发          |
| `system`                      | ✅ 接收    | ✅ 发送  | 监控模式控制         |
| `query`                       | ✅ 接收    | ✅ 发送  | 数据查询             |
| `face_result`                 | ✅ 接收    | ❌       | ESP32 专用（不转发） |
| `face_management`             | ❌         | ✅       | App 专用             |
| `media_download`              | ❌         | ✅       | App 专用             |
| `visit_notification`          | ❌         | ✅       | Server 推送          |
| `visitor_intent_notification` | ❌         | ✅       | Server 推送（v2.5）  |
| `server_ack`                  | ❌         | ✅       | Server 确认          |
| `device_status`               | ❌         | ✅       | Server 推送          |
| `esp32_ack`                   | ✅ 上报    | ❌       | ESP32 专用（不转发） |
| `ack`                         | ✅ 上报    | ✅ 接收  | Server 转发          |

### 13.2 协议差异

| 差异点   | ESP32 协议        | App 协议            |
| -------- | ----------------- | ------------------- |
| 连接端点 | `/xiaozhi/v1/`    | `/ws/app`           |
| 认证方式 | HTTP Header Token | hello 消息          |
| 身份标识 | device_id (MAC)   | app_id (用户ID)     |
| 二进制流 | BinaryProtocol2   | 透传 JPEG/PCM       |
| ACK 机制 | msg_id + ack      | seq_id + server_ack |

---

## 14. 数据流示意图

### 14.1 命令代理流程

```
App                    Server                   ESP32
 │                        │                        │
 │── lock_control ───────►│                        │
 │   (seq_id=app_001)     │                        │
 │                        │                        │
 │◄── server_ack ────────│ (code=0, 已接收)       │
 │                        │                        │
 │                        │── lock_control ───────►│
 │                        │   (msg_id=cmd_1001)    │
 │                        │                        │
 │                        │◄───── ack ────────────│
 │                        │   (msg_id=cmd_1001)    │
 │◄── ack ───────────────│ (ESP32 执行结果)       │
 │                        │                        │
```

### 14.2 状态推送流程

```
App                    Server                   ESP32
 │                        │                        │
 │                        │◄── status_report ─────│
 │                        │   (bat=85, lock=0)    │
 │                        │                        │
 │◄── status_report ─────│ (转发给所有 App)       │
 │                        │                        │
```

### 14.3 数据查询流程

```
App                    Server
 │                        │
 │── query ──────────────►│
 │   (target=status)      │
 │                        │ 从缓存/数据库读取
 │◄── query_result ──────│
 │   (data={...})         │
 │                        │
```

---

## 15. 错误处理

### 15.1 通用错误响应格式

```json
{
  "type": "{原消息类型}",
  "status": "error",
  "error": "错误代码",
  "message": "错误描述"
}
```

### 15.2 常见错误

| 错误             | 说明             |
| ---------------- | ---------------- |
| `device_offline` | ESP32 设备不在线 |
| `missing_params` | 缺少必要字段     |
| `invalid_params` | 参数格式错误     |
| `unauthorized`   | 未认证或权限不足 |
| `internal_error` | 服务器内部错误   |

### 15.3 错误响应格式规范

**不同接口的错误响应格式：**

| 接口类型   | 错误字段 | 格式   | 示例                                                 |
| ---------- | -------- | ------ | ---------------------------------------------------- |
| server_ack | code     | int    | `{"type":"server_ack","code":9,"msg":"重复消息"}`    |
| ack        | code     | int    | `{"type":"ack","code":1,"msg":"设备离线"}`           |
| query      | error    | string | `{"type":"query_result","error":"数据库不可用"}`     |
| media      | error    | string | `{"type":"media_download","error":"file_not_found"}` |
| system     | message  | string | `{"type":"system","status":"error","message":"..."}` |

**设计原则：**

1. **server_ack 和 ack**：使用 code 字段（0-10 统一错误码）
   - 需要与 ESP32 协议保持一致
   - 便于错误码统一管理

2. **query 和 media**：使用 error 字段（字符串）
   - 错误类型更语义化
   - 便于前端国际化处理

3. **system 和其他**：使用 message 字段（字符串）
   - 提供详细的错误描述
   - 便于调试和用户提示

---

## 16. 实现状态

### 16.1 服务器端实现

| 功能            | 代码位置                                            | 状态 |
| --------------- | --------------------------------------------------- | ---- |
| App 连接处理    | `core/app_connection.py`                            | ✅   |
| 连接管理        | `core/connection_manager.py`                        | ✅   |
| server_ack 机制 | `core/app_connection.py`                            | ✅   |
| seq_id 防重放   | `core/utils/seq_id_cache.py`                        | ✅   |
| 设备上下线通知  | `core/connection_manager.py`                        | ✅   |
| 命令代理        | `core/handle/textHandler/commandProxyHandler.py`    | ✅   |
| 数据查询        | `core/handle/textHandler/queryHandler.py`           | ✅   |
| 媒体下载        | `core/handle/textHandler/mediaDownloadHandler.py`   | ✅   |
| 到访通知        | `core/handle/textHandler/faceRecognitionHandler.py` | ✅   |
| ESP32 消息转发  | 各 Handler 的 `_forward_to_apps()`                  | ✅   |

### 16.2 数据库方法

| 方法                 | 代码位置                              | 状态 |
| -------------------- | ------------------------------------- | ---- |
| get_latest_status    | `core/providers/doorlock/database.py` | ✅   |
| get_status_history   | `core/providers/doorlock/database.py` | ✅   |
| get_events           | `core/providers/doorlock/database.py` | ✅   |
| get_unlock_logs      | `core/providers/doorlock/database.py` | ✅   |
| get_media_files      | `core/providers/doorlock/database.py` | ✅   |
| get_media_file_by_id | `core/providers/doorlock/database.py` | ✅   |

### 16.3 实现注意事项

**Server 端实现：**

1. **日志记录**：
   - 所有错误都应记录到日志
   - 包含 app_id、device_id、错误类型、错误详情
   - 便于问题追踪和审计

2. **错误恢复**：
   - 解码器错误：自动重置
   - 数据库错误：返回缓存数据或默认值
   - 网络错误：记录日志，不中断服务

3. **用户体验**：
   - 错误消息应清晰易懂
   - 提供可操作的建议（如"请检查网络连接"）
   - 避免暴露内部实现细节

**App 端实现：**

1. **错误处理**：
   - 根据 code/error 字段判断错误类型
   - 提供友好的错误提示
   - 支持重试机制

2. **超时处理**：
   - server_ack 超时：重传消息（最多 3 次）
   - 查询超时：提示用户重试
   - 下载超时：支持断点续传

3. **降级策略**：
   - 设备离线：显示离线状态，禁用控制功能
   - 查询失败：显示缓存数据
   - 下载失败：提供重新下载选项

---

## 17. 版本历史

| 版本 | 日期       | 变更说明                                                                                                                                                                                                                                                                                                            |
| ---- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| v2.5 | 2026-02-19 | 新增 visitor_intent_notification 消息（访客意图通知）；完善 bolt_alarm 事件说明（锁舌未到位报警）；新增访客意图查询接口（第 9.8 节）；新增快递警报查询接口（第 9.9 节）；新增智能门锁AI功能的完整协议支持；新增3个数据表（doorlock_visitor_intents、doorlock_package_alerts、doorlock_configs）                     |
| v2.4 | 2026-01-30 | 统一所有错误码为 0-10 体系；简化 server_ack 错误码使用（0/3/8/9）；明确 server_ack 只用于接收确认，业务错误在业务响应中返回；删除"两套错误码"的说明；补充密码查询接口、媒体文件大小限制、音频解码错误处理、错误响应格式规范、实现注意事项；新增门锁用户查询接口（第 9.7 节）；user_mgmt 命令新增 user_name 字段支持 |
| v2.3 | 2024-12-11 | 统一错误码为 0-10；更新 log_report 字段（status + lock_time）；新增 door_opened_report 和 password_report 消息；新增 door_closed、lock_success、bolt_alarm 事件；明确 esp32_ack 不转发；说明 ack 转发时的 ID 映射                                                                                                   |
| v2.2 | 2024-12-11 | 移除心跳机制；新增 server_ack 机制；新增设备上下线通知；新增防重放机制；完善实现状态                                                                                                                                                                                                                                |
| v2.1 | 2024-12-11 | 到访通知新增人脸图片推送；完善数据查询接口响应格式；新增媒体文件下载接口                                                                                                                                                                                                                                            |
| v2.0 | 2024-12-11 | 新增 app_id 身份标识；去除 forward 转发机制；统一消息类型与 ESP32 协议                                                                                                                                                                                                                                              |
| v1.0 | 2024-12-11 | 初始版本                                                                                                                                                                                                                                                                                                            |

---

**文档维护者：** 毕业设计项目组  
**最后更新：** 2026-02-19
