# App 通信协议 v2.5 更新清单

## 1. 版本信息

- **当前版本**：v2.4
- **目标版本**：v2.5
- **更新日期**：2026年2月19日
- **更新原因**：新增智能门锁AI功能的协议支持

## 2. 需要更新的章节

### 2.1 第1章 - 协议概述

**位置**：文档开头

**更新内容**：

```markdown
# 智能猫眼门锁系统 - App 通信协议规范 v2.5

> **协议升级提示**：本文档已从 v2.4 升级到 v2.5，主要变更：
>
> - 新增 visitor_intent_notification 消息（访客意图通知）
> - 新增 face_result 消息（人脸识别结果推送）
> - 更新 event_report 事件类型（完善 bolt_alarm 说明）
> - 新增 HTTP 图片上传接口说明
> - 完善智能门锁AI功能的协议支持

> **v2.4 变更回顾**：
>
> - 统一所有错误码为 0-10 体系（简化 server_ack 错误码使用）
> - 明确 server_ack 只用于接收确认（0/3/8/9），业务错误在业务响应中返回
> - 删除 server_ack 的 0-5 错误码定义，统一使用 0-10 错误码
```

### 2.2 第7.2节 - 事件推送 (event_report)

**位置**：第7章 服务器推送消息

**更新内容**：完善 bolt_alarm 事件说明

**当前版本**：

```markdown
| `bolt_alarm` | 反锁报警 | 无 |
```

**更新为**：

```markdown
| `bolt_alarm` | 锁舌未到位报警 | 报警类型 | 门未成功上锁，锁舌未到位 |
```

**完整事件类型表**：

| event          | 说明           | param含义      | 触发条件                 |
| -------------- | -------------- | -------------- | ------------------------ |
| `bell`         | 门铃按下       | 无             | 用户按门铃               |
| `pir_trigger`  | PIR人体检测    | 持续时间(秒)   | PIR检测到人体            |
| `tamper`       | 撬锁报警       | 报警级别(1-3)  | 检测到撬锁行为           |
| `door_open`    | 门未关超时     | 超时时间(分钟) | 门长时间未关闭           |
| `door_closed`  | 门已关闭       | 无             | 门从开启变为关闭         |
| `lock_success` | 上锁成功       | 无             | 门锁成功上锁             |
| `bolt_alarm`   | 锁舌未到位报警 | 报警类型       | 门未成功上锁，锁舌未到位 |
| `low_battery`  | 低电量警告     | 当前电量(%)    | 电量低于阈值             |

### 2.3 第7章 - 新增7.9节：访客意图通知

**位置**：第7.8节（密码上报）之后

**新增内容**：

````markdown
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
````

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
| other       | 其他情况      | 无法识别的意图     |

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

````

### 2.4 第7章 - 新增7.10节：人脸识别结果推送

**位置**：第7.9节之后

**新增内容**：

```markdown
### 7.10 人脸识别结果推送 (face_result)

PIR事件或门铃事件触发人脸识别后，服务器推送识别结果给App：

```json
{
  "type": "face_result",
  "ts": 1702234567890,
  "result": "known",
  "user_id": 10,
  "user_name": "张三",
  "access": {
    "granted": true,
    "reason": "authorized_user"
  }
}
````

**字段说明**：

| 字段           | 类型   | 必填 | 说明                                  |
| -------------- | ------ | ---- | ------------------------------------- |
| type           | string | 是   | 固定为 `"face_result"`                |
| ts             | int    | 是   | 时间戳（毫秒）                        |
| result         | string | 是   | 识别结果：known/unknown/no_face/error |
| user_id        | int    | 否   | 用户ID（识别成功时有值）              |
| user_name      | string | 否   | 用户姓名（识别成功时有值）            |
| access         | object | 是   | 访问控制信息                          |
| access.granted | bool   | 是   | 是否授权开锁                          |
| access.reason  | string | 是   | 授权/拒绝原因                         |

**识别结果说明**：

| result  | 说明         | access.granted | access.reason                       |
| ------- | ------------ | -------------- | ----------------------------------- |
| known   | 识别成功     | true/false     | authorized_user / unauthorized_user |
| unknown | 陌生人       | false          | unauthorized_user                   |
| no_face | 未检测到人脸 | false          | no_face_detected                    |
| error   | 识别错误     | false          | recognition_error                   |

**授权原因说明**：

| reason            | 说明                             |
| ----------------- | -------------------------------- |
| authorized_user   | 已授权用户（有开门权限）         |
| unauthorized_user | 未授权用户（无开门权限或陌生人） |
| no_face_detected  | 未检测到人脸                     |
| recognition_error | 识别过程出错                     |

**触发时机**：

- PIR事件或门铃事件触发人脸识别
- 人脸识别完成后立即推送

**与visit_notification的区别**：

- `face_result`：实时推送识别结果，用于快速显示访客身份
- `visit_notification`：包含完整的到访记录和抓拍图片
- 两者可能同时推送，也可能只推送其中一个

**注意事项**：

- 此消息仅推送给App，不转发给ESP32
- ESP32有自己的face_result消息（v5.2协议）
- App收到此消息后应更新UI显示访客信息
- 如果access.granted=true，ESP32会自动开锁

```

```

### 2.5 第12章 - 消息类型汇总

**位置**：第12.2节 Server推送的消息类型

**更新内容**：在表格中新增两行

**当前表格**：

```markdown
| type                   | 说明         | 来源       |
| ---------------------- | ------------ | ---------- |
| `hello`                | 认证响应     | Server     |
| `server_ack`           | 消息确认     | Server     |
| `device_status`        | 设备上下线   | Server     |
| `status_report`        | 状态上报     | ESP32 转发 |
| `event_report`         | 事件上报     | ESP32 转发 |
| `log_report`           | 开锁日志     | ESP32 转发 |
| `door_opened_report`   | 门已开启通知 | ESP32 转发 |
| `password_report`      | 密码上报     | ESP32 转发 |
| `user_mgmt_result`     | 用户管理结果 | ESP32 转发 |
| `ack`                  | ESP32 ACK    | ESP32 转发 |
| `visit_notification`   | 到访通知     | Server     |
| `query_result`         | 查询结果     | Server     |
| `media_download`       | 下载响应     | Server     |
| `media_download_chunk` | 分片响应     | Server     |
| `system`               | 系统响应     | Server     |
| `face_management`      | 人脸管理响应 | Server     |
```

**更新为**（新增两行）：

```markdown
| type                          | 说明         | 来源       |
| ----------------------------- | ------------ | ---------- | ------ |
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
| `visitor_intent_notification` | 访客意图通知 | Server     | ← 新增 |
| `face_result`                 | 人脸识别结果 | Server     | ← 新增 |
| `query_result`                | 查询结果     | Server     |
| `media_download`              | 下载响应     | Server     |
| `media_download_chunk`        | 分片响应     | Server     |
| `system`                      | 系统响应     | Server     |
| `face_management`             | 人脸管理响应 | Server     |
```

### 2.6 第13章 - 与ESP32协议对比

**位置**：第13.1节 消息类型对比

**更新内容**：在表格中新增两行

**当前表格**：

```markdown
| 消息类型             | ESP32 协议 | App 协议 | 说明                 |
| -------------------- | ---------- | -------- | -------------------- |
| `hello`              | ❌         | ✅       | App 认证专用         |
| `status_report`      | ✅ 上报    | ✅ 接收  | Server 转发          |
| `event_report`       | ✅ 上报    | ✅ 接收  | Server 转发          |
| `log_report`         | ✅ 上报    | ✅ 接收  | Server 转发          |
| `door_opened_report` | ✅ 上报    | ✅ 接收  | Server 转发          |
| `password_report`    | ✅ 上报    | ✅ 接收  | Server 转发          |
| `lock_control`       | ✅ 接收    | ✅ 发送  | Server 代理转发      |
| `dev_control`        | ✅ 接收    | ✅ 发送  | Server 代理转发      |
| `user_mgmt`          | ✅ 接收    | ✅ 发送  | Server 代理转发      |
| `user_mgmt_result`   | ✅ 上报    | ✅ 接收  | Server 转发          |
| `system`             | ✅ 接收    | ✅ 发送  | 监控模式控制         |
| `query`              | ✅ 接收    | ✅ 发送  | 数据查询             |
| `face_result`        | ✅ 接收    | ❌       | ESP32 专用（不转发） |
| `face_management`    | ❌         | ✅       | App 专用             |
| `media_download`     | ❌         | ✅       | App 专用             |
| `visit_notification` | ❌         | ✅       | Server 推送          |
| `server_ack`         | ❌         | ✅       | Server 确认          |
| `device_status`      | ❌         | ✅       | Server 推送          |
| `esp32_ack`          | ✅ 上报    | ❌       | ESP32 专用（不转发） |
| `ack`                | ✅ 上报    | ✅ 接收  | Server 转发          |
```

**更新为**（修改face_result行，新增visitor_intent_notification行）：

```markdown
| 消息类型                      | ESP32 协议 | App 协议 | 说明                          |
| ----------------------------- | ---------- | -------- | ----------------------------- |
| `hello`                       | ❌         | ✅       | App 认证专用                  |
| `status_report`               | ✅ 上报    | ✅ 接收  | Server 转发                   |
| `event_report`                | ✅ 上报    | ✅ 接收  | Server 转发                   |
| `log_report`                  | ✅ 上报    | ✅ 接收  | Server 转发                   |
| `door_opened_report`          | ✅ 上报    | ✅ 接收  | Server 转发                   |
| `password_report`             | ✅ 上报    | ✅ 接收  | Server 转发                   |
| `lock_control`                | ✅ 接收    | ✅ 发送  | Server 代理转发               |
| `dev_control`                 | ✅ 接收    | ✅ 发送  | Server 代理转发               |
| `user_mgmt`                   | ✅ 接收    | ✅ 发送  | Server 代理转发               |
| `user_mgmt_result`            | ✅ 上报    | ✅ 接收  | Server 转发                   |
| `system`                      | ✅ 接收    | ✅ 发送  | 监控模式控制                  |
| `query`                       | ✅ 接收    | ✅ 发送  | 数据查询                      |
| `face_result`                 | ✅ 接收    | ✅ 接收  | Server 推送（v2.5新增）← 修改 |
| `face_management`             | ❌         | ✅       | App 专用                      |
| `media_download`              | ❌         | ✅       | App 专用                      |
| `visit_notification`          | ❌         | ✅       | Server 推送                   |
| `visitor_intent_notification` | ❌         | ✅       | Server 推送（v2.5新增）← 新增 |
| `server_ack`                  | ❌         | ✅       | Server 确认                   |
| `device_status`               | ❌         | ✅       | Server 推送                   |
| `esp32_ack`                   | ✅ 上报    | ❌       | ESP32 专用（不转发）          |
| `ack`                         | ✅ 上报    | ✅ 接收  | Server 转发                   |
```

**注意**：face_result 在v2.5中改为推送给App，不再是"ESP32专用（不转发）"

### 2.7 第17章 - 版本历史

**位置**：文档末尾

**更新内容**：在表格顶部新增v2.5版本记录

**当前表格**：

```markdown
| 版本 | 日期       | 变更说明                                                                                                                                                                                                                                                                                                            |
| ---- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| v2.4 | 2026-01-30 | 统一所有错误码为 0-10 体系；简化 server_ack 错误码使用（0/3/8/9）；明确 server_ack 只用于接收确认，业务错误在业务响应中返回；删除"两套错误码"的说明；补充密码查询接口、媒体文件大小限制、音频解码错误处理、错误响应格式规范、实现注意事项；新增门锁用户查询接口（第 9.7 节）；user_mgmt 命令新增 user_name 字段支持 |
| v2.3 | 2024-12-11 | 统一错误码为 0-10；更新 log_report 字段（status + lock_time）；新增 door_opened_report 和 password_report 消息；新增 door_closed、lock_success、bolt_alarm 事件；明确 esp32_ack 不转发；说明 ack 转发时的 ID 映射                                                                                                   |
```

**更新为**（新增v2.5行）：

```markdown
| 版本 | 日期       | 变更说明                                                                                                                                                                                                                                                                                                            |
| ---- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| v2.5 | 2026-02-19 | 新增 visitor_intent_notification 消息（访客意图通知）；新增 face_result 消息（人脸识别结果推送）；完善 bolt_alarm 事件说明（锁舌未到位报警）；新增智能门锁AI功能的完整协议支持；face_result 改为推送给App（不再是ESP32专用）                                                                                        |
| v2.4 | 2026-01-30 | 统一所有错误码为 0-10 体系；简化 server_ack 错误码使用（0/3/8/9）；明确 server_ack 只用于接收确认，业务错误在业务响应中返回；删除"两套错误码"的说明；补充密码查询接口、媒体文件大小限制、音频解码错误处理、错误响应格式规范、实现注意事项；新增门锁用户查询接口（第 9.7 节）；user_mgmt 命令新增 user_name 字段支持 |
| v2.3 | 2024-12-11 | 统一错误码为 0-10；更新 log_report 字段（status + lock_time）；新增 door_opened_report 和 password_report 消息；新增 door_closed、lock_success、bolt_alarm 事件；明确 esp32_ack 不转发；说明 ack 转发时的 ID 映射                                                                                                   |
```

## 3. 可选新增章节

### 3.1 建议新增：附录A - HTTP图片上传接口

**位置**：第17章版本历史之前

**新增内容**：

```markdown
---

## 附录A：HTTP 图片上传接口

### A.1 接口说明

ESP32通过HTTP POST方式上传访客照片到服务器。

**接口地址**：`POST http://{server}:8003/upload/image`

**请求头**：
```

Content-Type: application/octet-stream
device-id: AA:BB:CC:DD:EE:FF
timestamp: 1702234567890
width: 640
height: 480

````

| 请求头 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| Content-Type | string | 是 | 固定为 `application/octet-stream` |
| device-id | string | 是 | 设备MAC地址 |
| timestamp | int | 是 | 时间戳（毫秒） |
| width | int | 否 | 图片宽度，默认640 |
| height | int | 否 | 图片高度，默认480 |

**请求体**：JPEG图片二进制数据

**响应格式（成功）**：
```json
{
  "success": true,
  "message": "图片上传成功"
}
````

**响应格式（失败）**：

```json
{
  "success": false,
  "message": "缺少device-id头部"
}
```

| 错误消息          | 说明                |
| ----------------- | ------------------- |
| 缺少device-id头部 | 请求头缺少device-id |
| 图片数据为空      | 请求体为空          |
| 处理失败: {error} | 服务器内部错误      |

### A.2 使用场景

- PIR事件或门铃事件触发拍照
- 定时拍照任务（对话期间每5秒）
- 人脸识别前的照片采集

### A.3 注意事项

- 此接口仅供ESP32使用，App不需要调用
- 服务器收到图片后会触发回调处理
- 图片不会直接转发给App，而是在意图通知中包含
- 支持CORS预检请求（OPTIONS方法）

---

````

### 3.2 建议新增：附录B - 智能门锁AI功能说明

**位置**：附录A之后

**新增内容**：

```markdown
## 附录B：智能门锁AI功能说明

### B.1 功能概述

智能门锁AI功能是v2.5新增的核心功能，实现了访客到访时的智能对话和意图识别。

**核心能力**：
- 访客人脸识别
- 智能对话交互
- 意图识别分析
- 快递看护监控
- 威胁等级评估

### B.2 工作流程

````

访客到访
↓
PIR检测 / 门铃按下
↓
触发拍照
↓
人脸识别
├─ 有权限 → 自动开锁 + 欢迎词
└─ 无权限 → 启动意图识别对话
↓
智能对话（最多10轮）
├─ 实时拍照（每5秒）
├─ AI分析访客意图
├─ 监控快递安全（如果看护激活）
└─ 检测威胁行为
↓
对话结束
├─ 生成意图总结
├─ 检查快递状态
├─ 保存访问记录
└─ 推送App通知

```

### B.3 消息推送时序

```

时间轴 服务器推送消息
│
├─ T0: PIR检测
│
├─ T1: 人脸识别完成
│ └─→ face_result（识别结果）
│
├─ T2-T10: 对话进行中
│ └─→ （无推送，后台处理）
│
└─ T11: 对话结束
└─→ visitor_intent_notification（意图通知）

```

### B.4 意图类型详解

**delivery（送快递/外卖）**
- 典型对话："我是来送快递的"、"外卖到了"
- 处理方式：记录快递信息，可选启用看护模式
- 威胁等级：通常为low

**visit（拜访朋友/家人）**
- 典型对话："我来找XXX"、"我是XXX的朋友"
- 处理方式：记录访客信息，通知主人
- 威胁等级：通常为low

**sales（推销产品/服务）**
- 典型对话："了解一下我们的产品"、"办理业务"
- 处理方式：记录推销信息，可选拒绝
- 威胁等级：通常为low

**maintenance（维修/物业工作）**
- 典型对话："来检查水表"、"物业维修"
- 处理方式：记录工作信息，验证身份
- 威胁等级：通常为low

**other（其他情况）**
- 典型对话：无法识别的意图
- 处理方式：记录完整对话，人工审核
- 威胁等级：根据行为判断

### B.5 威胁等级评估

**low（低威胁）**
- 访客正常对话，无异常行为
- 快递未被触碰
- 主人取快递
- 路人经过

**medium（中威胁）**
- 访客翻看快递
- 快递被移动但未拿走
- 长时间停留
- 行为可疑

**high（高威胁）**
- 非主人拿走快递
- 破坏快递
- 强行开门
- 暴力行为

**处理策略**：
- low：正常记录，无需警报
- medium：发送通知，提醒主人
- high：立即警报，播放警告语音

### B.6 App端集成建议

**UI设计**：
1. 实时显示访客识别结果（face_result）
2. 对话结束后显示意图总结（visitor_intent_notification）
3. 高亮显示重要信息（important_notes）
4. 威胁等级用颜色区分（绿/黄/红）

**通知策略**：
1. low威胁：普通通知
2. medium威胁：重要通知 + 声音
3. high威胁：紧急通知 + 声音 + 震动

**数据存储**：
1. 保存完整对话历史
2. 保存访客照片
3. 保存意图总结
4. 支持历史记录查询

---
```

## 4. 更新优先级

### 4.1 必须更新（P0）

- ✅ 第1章：协议概述（版本号和升级说明）
- ✅ 第7.2节：event_report事件类型表（完善bolt_alarm说明）
- ✅ 第7.9节：新增visitor_intent_notification消息
- ✅ 第7.10节：新增face_result消息
- ✅ 第12.2节：消息类型汇总表（新增2行）
- ✅ 第13.1节：与ESP32协议对比表（修改1行，新增1行）
- ✅ 第17章：版本历史（新增v2.5记录）

### 4.2 建议更新（P1）

- ⏳ 附录A：HTTP图片上传接口
- ⏳ 附录B：智能门锁AI功能说明

### 4.3 可选更新（P2）

- ⏳ 第16.1节：服务器端实现状态（更新实现文件列表）
- ⏳ 添加更多使用示例和场景说明

## 5. 验证清单

更新完成后，请验证以下内容：

- [ ] 所有新增消息类型都有完整的字段说明
- [ ] 所有表格都已更新（消息类型汇总、协议对比）
- [ ] 版本号已更新到v2.5
- [ ] 版本历史已添加v2.5记录
- [ ] bolt_alarm事件说明已完善
- [ ] face_result消息说明已从"不转发"改为"推送给App"
- [ ] 文档格式一致（Markdown语法正确）
- [ ] 所有链接和引用正确
- [ ] 示例JSON格式正确

## 6. 相关文档

更新完成后，建议同步更新以下文档：

- `智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md`（参考对比）
- `CHANGELOG.md`（记录协议变更）
- `README.md`（更新协议版本号）
- App端开发文档（如果有）

## 7. 注意事项

1. **向后兼容**：所有新增功能都是可选的，不影响现有功能
2. **消息顺序**：face_result先于visitor_intent_notification推送
3. **数据一致性**：确保visit_id在不同消息中保持一致
4. **错误处理**：App端需要处理消息解析失败的情况
5. **性能考虑**：对话历史可能很长，注意内存占用

---

**清单生成时间**：2026年2月19日  
**生成人员**：Kiro AI  
**文档版本**：v1.0
