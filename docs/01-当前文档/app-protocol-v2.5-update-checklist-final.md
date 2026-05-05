# App 通信协议 v2.5 更新清单（最终版）

## 1. 版本信息

- **当前版本**：v2.4
- **目标版本**：v2.5
- **更新日期**：2026年2月19日
- **更新原因**：新增智能门锁AI功能的协议支持

## 2. 数据库变更分析

### 2.1 新增数据表

根据代码分析，v2.5版本新增了以下数据表：

**doorlock_visitor_intents（访客意图记录表）**

| 字段             | 类型     | 说明                                             |
| ---------------- | -------- | ------------------------------------------------ |
| id               | INT      | 主键，自增                                       |
| visit_id         | INT      | 关联visit_records表（可选）                      |
| session_id       | VARCHAR  | 会话ID                                           |
| person_id        | INT      | 人员ID（可选）                                   |
| intent_type      | VARCHAR  | 意图类型：delivery/visit/sales/maintenance/other |
| intent_summary   | JSON     | 意图总结（JSON格式）                             |
| dialogue_history | JSON     | 对话历史（JSON格式）                             |
| created_at       | DATETIME | 创建时间                                         |

**doorlock_package_alerts（快递警报表）**

| 字段               | 类型     | 说明                                               |
| ------------------ | -------- | -------------------------------------------------- |
| id                 | INT      | 主键，自增                                         |
| device_id          | VARCHAR  | 设备ID                                             |
| session_id         | VARCHAR  | 会话ID                                             |
| threat_level       | VARCHAR  | 威胁等级：low/medium/high                          |
| action             | VARCHAR  | 行为类型：taking/searching/damaging/normal/passing |
| description        | TEXT     | 详细描述                                           |
| photo_path         | VARCHAR  | 照片路径                                           |
| voice_warning_sent | BOOLEAN  | 是否已发送语音警告                                 |
| notified           | BOOLEAN  | 是否已通知App                                      |
| created_at         | DATETIME | 创建时间                                           |

**doorlock_configs（门锁配置表）**

| 字段                       | 类型     | 说明               |
| -------------------------- | -------- | ------------------ |
| device_id                  | VARCHAR  | 设备ID（主键）     |
| intent_recognition_enabled | BOOLEAN  | 是否启用意图识别   |
| face_recognition_enabled   | BOOLEAN  | 是否启用人脸识别   |
| package_guard_available    | BOOLEAN  | 看护功能是否可用   |
| package_guard_active       | BOOLEAN  | 看护模式是否激活   |
| package_baseline_image     | TEXT     | 基准图片（Base64） |
| package_guard_start_time   | DATETIME | 看护开始时间       |
| created_at                 | DATETIME | 创建时间           |
| updated_at                 | DATETIME | 更新时间           |

### 2.2 已有数据表（未修改）

以下表是人脸识别功能的核心表，在v2.5之前已存在，本次未修改：

**persons（人员信息表）**

| 字段            | 类型         | 说明                                                                              | v2.5变更 |
| --------------- | ------------ | --------------------------------------------------------------------------------- | -------- |
| id              | INT          | 主键，自增                                                                        |          |
| name            | VARCHAR(50)  | 人员姓名                                                                          |          |
| relation_type   | ENUM         | 关系类型：family/friend/colleague/property/courier/delivery/tutor/classmate/other |          |
| face_encoding   | BLOB         | 人脸特征编码                                                                      |          |
| photo_path      | VARCHAR(255) | 照片路径                                                                          |          |
| custom_greeting | TEXT         | 欢迎词配置（JSON格式，支持分时段问候）                                            | 修改类型 |
| is_owner        | BOOLEAN      | 是否为主人（可取走快递），默认FALSE                                               | 新增     |
| created_at      | DATETIME     | 创建时间                                                                          |          |
| updated_at      | DATETIME     | 更新时间                                                                          |          |

**access_permissions（访问权限表）**

| 字段            | 类型         | 说明                                                   |
| --------------- | ------------ | ------------------------------------------------------ |
| id              | INT          | 主键，自增                                             |
| person_id       | INT          | 人员ID（外键关联persons表）                            |
| permission_type | ENUM         | 权限类型：permanent（永久）/temporary（临时）          |
| time_start      | TIME         | 允许时段开始时间（默认00:00:00）                       |
| time_end        | TIME         | 允许时段结束时间（默认23:59:59）                       |
| day_type        | ENUM         | 日期类型：daily（每天）/weekly（每周）/monthly（每月） |
| week_days       | VARCHAR(20)  | 允许的星期几（1-7，逗号分隔）                          |
| month_days      | VARCHAR(100) | 允许的日期（1-31，逗号分隔）                           |
| remaining_count | INT          | 剩余使用次数（临时权限用）                             |
| valid_from      | DATE         | 有效期开始日期                                         |
| valid_until     | DATE         | 有效期结束日期                                         |
| is_active       | BOOLEAN      | 是否激活                                               |
| created_at      | DATETIME     | 创建时间                                               |

**visit_records（访问记录表）**

| 字段               | 类型         | 说明                                  |
| ------------------ | ------------ | ------------------------------------- |
| id                 | INT          | 主键，自增                            |
| person_id          | INT          | 人员ID（外键关联persons表，可为NULL） |
| recognition_result | ENUM         | 识别结果：known/unknown/no_face       |
| access_granted     | BOOLEAN      | 是否授权开门                          |
| deny_reason        | VARCHAR(100) | 拒绝原因                              |
| photo_path         | VARCHAR(255) | 访客照片路径                          |
| visit_time         | DATETIME     | 访问时间                              |
| notified           | BOOLEAN      | 是否已通知App                         |

> **说明**：
>
> - persons表和access_permissions表用于人脸识别和权限管理
> - 权限判断逻辑在`face_service.py`的`check_permission()`方法中实现
> - 支持永久权限和临时权限（可限制使用次数）
> - 支持时段限制（如只允许8:00-22:00开门）
> - 支持日期限制（如只允许周一到周五，或每月1-15号）
>
> **v2.5 新增字段**：
>
> 1. **persons.is_owner**（新增）：
>    - 类型：BOOLEAN，默认FALSE
>    - 用途：标识是否为主人，用于快递看护功能
>    - 主人取走快递被判定为低威胁（正常行为）
>    - 非主人取走快递被判定为高威胁（需要警报）
> 2. **persons.custom_greeting**（类型修改）：
>    - 从 VARCHAR(255) 改为 TEXT
>    - 支持 JSON 格式的分时段欢迎词配置
>    - 示例：`{"morning":"早上好","afternoon":"下午好","evening":"晚上好","night":"夜深了","default":"欢迎回家"}`
>
> **快递看护的权限判断机制**：
>
> - 快递看护功能使用现有的 `access_permissions` 表判断开门权限
> - 威胁判断基于视觉分析（对比基准图片和当前图片），不涉及单独的"取快递权限"
> - 工作流程：
>   1. PIR检测到人体 → 拍摄基准图片
>   2. 人脸识别 → 调用 `check_permission()` 判断开门权限
>   3. 有权限：直接开门，不启动看护对话
>   4. 无权限或识别失败：启动意图识别对话并监控快递状态
>   5. 对话结束 → 调用 `final_package_check()` 对比图片判断威胁
>   6. 如果识别到的人员 `is_owner=true`，取走快递为低威胁
>   7. 如果识别到的人员 `is_owner=false` 或未识别，取走快递为高威胁
> - 威胁等级（low/medium/high）由VLLM视觉分析生成，结合 `is_owner` 字段判断

### 2.3 新增查询接口

**服务器端已实现**：

1. `save_visitor_intent(intent)` - 保存访客意图记录
2. `get_visitor_intents(device_id, limit, offset, start_date, end_date)` - 查询访客意图历史
3. `save_package_alert(alert)` - 保存快递警报
4. `get_package_alerts(device_id, limit, offset, start_date, end_date)` - 查询快递警报历史
5. `get_config(device_id)` - 获取设备配置
6. `update_config(config)` - 更新设备配置

### 2.4 App协议需要新增的查询接口

**建议新增到第9章（数据查询接口）**：

#### 9.X 查询访客意图历史

**请求**：

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

**响应**：

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
          "ai_analysis": "访客是快递员..."
        },
        "dialogue_history": [
          { "role": "assistant", "content": "您好" },
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

#### 9.Y 查询快递警报历史

**请求**：

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

**响应**：

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

## 3. 需要更新的章节

### 3.1 第1章 - 协议概述

**位置**：文档开头

**更新内容**：

```markdown
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
```

### 3.2 第7.2节 - 事件推送 (event_report)

**位置**：第7章 服务器推送消息

**更新内容**：完善 bolt_alarm 事件说明

**当前版本**：

```markdown
| `bolt_alarm` | 反锁报警 | 无 |
```

**更新为**：

```markdown
| `bolt_alarm` | 锁舌未到位报警 | 报警类型 |
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

### 3.3 第7章 - 新增7.9节：访客意图通知

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

```

```

### 3.4 第9章 - 新增查询接口

**位置**：第9.7节（查询门锁用户列表）之后

**新增内容**：

````markdown
### 9.8 查询访客意图历史

查询设备的访客意图识别历史记录（从服务器数据库读取）：

**请求**：

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
````

| 字段       | 类型   | 必填 | 说明                      |
| ---------- | ------ | ---- | ------------------------- |
| start_date | string | 否   | 开始日期 (YYYY-MM-DD)     |
| end_date   | string | 否   | 结束日期 (YYYY-MM-DD)     |
| limit      | int    | 否   | 返回条数，默认20，最大100 |
| offset     | int    | 否   | 偏移量，默认0             |

**响应（成功）**：

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

**请求**：

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

**响应（成功）**：

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

````

### 3.5 第12章 - 消息类型汇总

**位置**：第12.2节 Server推送的消息类型

**更新内容**：在表格中新增一行

**当前表格最后几行**：
```markdown
| `visit_notification`   | 到访通知     | Server     |
| `query_result`         | 查询结果     | Server     |
| `media_download`       | 下载响应     | Server     |
````

**更新为**（新增一行）：

```markdown
| `visit_notification` | 到访通知 | Server |
| `visitor_intent_notification` | 访客意图通知 | Server | ← 新增
| `query_result` | 查询结果 | Server |
| `media_download` | 下载响应 | Server |
```

### 3.6 第13章 - 与ESP32协议对比

**位置**：第13.1节 消息类型对比

**更新内容**：在表格中新增一行

**当前表格相关行**：

```markdown
| `visit_notification` | ❌ | ✅ | Server 推送 |
| `server_ack` | ❌ | ✅ | Server 确认 |
```

**更新为**（新增一行）：

```markdown
| `visit_notification` | ❌ | ✅ | Server 推送 |
| `visitor_intent_notification` | ❌ | ✅ | Server 推送（v2.5新增）| ← 新增
| `server_ack` | ❌ | ✅ | Server 确认 |
```

### 3.7 第17章 - 版本历史

**位置**：文档末尾

**更新内容**：在表格顶部新增v2.5版本记录

**当前表格**：

```markdown
| 版本 | 日期       | 变更说明                                                                                                                                                                                                                                                                                                            |
| ---- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| v2.4 | 2026-01-30 | 统一所有错误码为 0-10 体系；简化 server_ack 错误码使用（0/3/8/9）；明确 server_ack 只用于接收确认，业务错误在业务响应中返回；删除"两套错误码"的说明；补充密码查询接口、媒体文件大小限制、音频解码错误处理、错误响应格式规范、实现注意事项；新增门锁用户查询接口（第 9.7 节）；user_mgmt 命令新增 user_name 字段支持 |
```

**更新为**（新增v2.5行）：

```markdown
| 版本 | 日期       | 变更说明                                                                                                                                                                                                                                                                                                            |
| ---- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| v2.5 | 2026-02-19 | 新增 visitor_intent_notification 消息（访客意图通知）；完善 bolt_alarm 事件说明（锁舌未到位报警）；新增访客意图查询接口（第 9.8 节）；新增快递警报查询接口（第 9.9 节）；新增智能门锁AI功能的完整协议支持；新增3个数据表（doorlock_visitor_intents、doorlock_package_alerts、doorlock_configs）                     |
| v2.4 | 2026-01-30 | 统一所有错误码为 0-10 体系；简化 server_ack 错误码使用（0/3/8/9）；明确 server_ack 只用于接收确认，业务错误在业务响应中返回；删除"两套错误码"的说明；补充密码查询接口、媒体文件大小限制、音频解码错误处理、错误响应格式规范、实现注意事项；新增门锁用户查询接口（第 9.7 节）；user_mgmt 命令新增 user_name 字段支持 |
```

## 4. 更新优先级

### 4.1 必须更新（P0）

- ✅ 第1章：协议概述（版本号和升级说明）
- ✅ 第7.2节：event_report事件类型表（完善bolt_alarm说明）
- ✅ 第7.9节：新增visitor_intent_notification消息
- ✅ 第9.8节：新增访客意图查询接口
- ✅ 第9.9节：新增快递警报查询接口
- ✅ 第12.2节：消息类型汇总表（新增1行）
- ✅ 第13.1节：与ESP32协议对比表（新增1行）
- ✅ 第17章：版本历史（新增v2.5记录）

### 4.2 不需要更新

- ❌ 人脸识别结果推送（face_result）- 已确认不需要
- ❌ HTTP图片上传接口 - 内部使用，不需要在App协议中说明

## 5. 验证清单

更新完成后，请验证以下内容：

- [ ] 所有新增消息类型都有完整的字段说明
- [ ] 所有表格都已更新（消息类型汇总、协议对比）
- [ ] 版本号已更新到v2.5
- [ ] 版本历史已添加v2.5记录
- [ ] bolt_alarm事件说明已完善为"锁舌未到位报警"
- [ ] other意图类型说明已修正为"未列出的意图识别"
- [ ] 新增查询接口的参数和响应格式正确
- [ ] 文档格式一致（Markdown语法正确）
- [ ] 所有链接和引用正确
- [ ] 示例JSON格式正确

## 6. 数据库变更总结

### 6.1 新增表（v2.5）

1. **doorlock_visitor_intents** - 访客意图记录表
2. **doorlock_package_alerts** - 快递警报表
3. **doorlock_configs** - 门锁配置表

### 6.2 已有表（v2.5修改）

1. **persons** - 人员信息表（人脸识别）
   - **新增字段**：`is_owner` (BOOLEAN) - 是否为主人（可取走快递）
   - **修改字段**：`custom_greeting` (VARCHAR→TEXT) - 支持JSON格式分时段欢迎词
2. **access_permissions** - 访问权限表（开门权限管理）- 未修改
3. **visit_records** - 访问记录表（到访历史）- 未修改

> **重要说明**：
>
> - persons和access_permissions表是人脸识别功能的核心表，在v2.5之前已存在
> - 权限判断通过`check_permission()`方法实现，支持：
>   - 永久权限 vs 临时权限（可限制使用次数）
>   - 时段限制（如8:00-22:00）
>   - 日期限制（按周/按月）
>   - 有效期限制（valid_from到valid_until）
> - 这些表的查询接口在v2.4中已经存在（face_management相关接口）

### 6.3 新增查询方法（服务器端）

服务器端已实现：

- `save_visitor_intent(intent)` - 保存访客意图
- `get_visitor_intents(device_id, limit, offset, start_date, end_date)` - 查询访客意图
- `save_package_alert(alert)` - 保存快递警报
- `get_package_alerts(device_id, limit, offset, start_date, end_date)` - 查询快递警报
- `get_config(device_id)` - 获取设备配置
- `update_config(config)` - 更新设备配置

### 6.4 App协议新增查询接口（v2.5）

- `target=visitor_intents` - 查询访客意图历史（第9.8节）
- `target=package_alerts` - 查询快递警报历史（第9.9节）

> **注意**：现有的人员管理接口（face_management）需要支持 `is_owner` 字段的读写操作。

## 7. 相关文档

更新完成后，建议同步更新以下文档：

- `智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md`（参考对比）
- `CHANGELOG.md`（记录协议变更）
- `README.md`（更新协议版本号）
- App端开发文档（如果有）
- 数据库设计文档（记录新增表结构）

## 8. 注意事项

1. **向后兼容**：所有新增功能都是可选的，不影响现有功能
2. **数据一致性**：确保visit_id在不同消息和表中保持一致
3. **错误处理**：App端需要处理消息解析失败的情况
4. **性能考虑**：对话历史可能很长，注意内存占用和传输大小
5. **查询优化**：建议使用分页查询，避免一次性加载过多数据
6. **日期格式**：统一使用ISO 8601格式（YYYY-MM-DD）

## 9. 修正说明

相比初版更新清单，本版本修正了以下内容：

1. ✅ 修正 other 意图类型说明：从"无法识别的意图"改为"未列出的意图识别"
2. ✅ 删除 face_result 消息（不需要推送给App）
3. ✅ 删除 HTTP图片上传接口说明（内部使用，不需要在App协议中说明）
4. ✅ 新增数据库变更分析章节
5. ✅ 新增2个查询接口（visitor_intents、package_alerts）
6. ✅ 完善数据表结构说明
7. ✅ 补充已有表说明（persons、access_permissions、visit_records）
8. ✅ 说明权限判断逻辑（check_permission方法）
9. ✅ 补充 persons 表的 v2.5 变更（is_owner 字段新增、custom_greeting 类型修改）
10. ✅ 完善快递看护的权限判断机制说明（结合 is_owner 字段）

### 关于权限管理

**persons表和access_permissions表**是人脸识别功能的核心表，用于：

- 存储人员信息和人脸特征
- 管理开门权限（永久/临时、时段限制、日期限制）
- 判断访客是否有权限开门

**v2.5 新增功能**：

- **is_owner 字段**：标识主人身份，用于快递看护功能
  - 主人取走快递 = 低威胁（正常行为）
  - 非主人取走快递 = 高威胁（需要警报）
- **custom_greeting 字段升级**：支持 JSON 格式的分时段欢迎词

**权限判断流程**：

1. PIR/门铃事件触发人脸识别
2. 识别成功后调用`check_permission(person_id)`判断权限
3. 有权限：自动开门 + 播放欢迎词
4. 无权限：启动意图识别对话
5. 快递看护：根据 `is_owner` 字段判断威胁等级

这些表和逻辑在v2.5之前已存在，本次更新新增了 `is_owner` 字段和 `custom_greeting` 类型修改。

---

**清单生成时间**：2026年2月19日  
**生成人员**：Kiro AI  
**文档版本**：v2.0（最终版）
