# 智能门锁 AI 功能 HTTP API 文档

## 概述

本文档描述智能门锁 AI 功能的 HTTP API 接口，包括设备配置管理、看护模式控制、欢迎词配置和历史记录查询。

### 基本信息

- **服务器地址**: `http://localhost:8003`
- **协议**: HTTP/1.1
- **数据格式**: JSON
- **字符编码**: UTF-8

### 认证说明

当前版本的 API 暂不需要认证。未来版本可能会添加 Bearer Token 认证机制。

### 通用响应格式

所有 API 接口返回统一的 JSON 格式：

**成功响应**:

```json
{
  "success": true,
  "data": { ... },
  "message": "操作成功"
}
```

**失败响应**:

```json
{
  "success": false,
  "message": "错误描述信息"
}
```

### 错误码说明

| HTTP 状态码 | 说明           | 常见原因                                 |
| ----------- | -------------- | ---------------------------------------- |
| 200         | 请求成功       | 操作正常完成                             |
| 400         | 请求参数错误   | 缺少必填参数、参数类型错误、参数格式错误 |
| 404         | 资源不存在     | 设备配置不存在、用户不存在               |
| 500         | 服务器内部错误 | 数据库连接失败、服务异常                 |

---

## 1. 设备配置 API

### 1.1 获取设备配置

获取指定设备的门锁 AI 功能配置。

**请求**

```
GET /api/doorlock/config?device_id={device_id}
```

**查询参数**

| 参数名    | 类型   | 必填 | 说明   |
| --------- | ------ | ---- | ------ |
| device_id | string | 是   | 设备ID |

**请求示例**

```bash
curl -X GET "http://localhost:8003/api/doorlock/config?device_id=device001"
```

**成功响应 (200)**

```json
{
  "success": true,
  "data": {
    "device_id": "device001",
    "intent_recognition_enabled": true,
    "package_guard_available": true,
    "package_guard_active": false,
    "package_baseline_image": null,
    "package_guard_start_time": null
  }
}
```

**响应字段说明**

| 字段名                     | 类型         | 说明                             |
| -------------------------- | ------------ | -------------------------------- |
| device_id                  | string       | 设备ID                           |
| intent_recognition_enabled | boolean      | 意图识别功能是否启用             |
| package_guard_available    | boolean      | 看护模式功能是否可用             |
| package_guard_active       | boolean      | 看护模式是否正在运行             |
| package_baseline_image     | string\|null | 基准图片路径                     |
| package_guard_start_time   | string\|null | 看护模式启动时间（ISO 8601格式） |

**错误响应**

```json
// 400 - 缺少参数
{
  "success": false,
  "message": "缺少必填参数: device_id"
}

// 404 - 设备不存在
{
  "success": false,
  "message": "设备配置不存在: device001"
}

// 500 - 服务器错误
{
  "success": false,
  "message": "服务器内部错误: 数据库连接失败"
}
```

---

### 1.2 更新设备配置

更新指定设备的门锁 AI 功能配置。

**请求**

```
POST /api/doorlock/config
Content-Type: application/json
```

**请求体参数**

| 参数名                     | 类型    | 必填 | 说明                 |
| -------------------------- | ------- | ---- | -------------------- |
| device_id                  | string  | 是   | 设备ID               |
| intent_recognition_enabled | boolean | 否   | 意图识别功能是否启用 |
| package_guard_available    | boolean | 否   | 看护模式功能是否可用 |

**请求示例**

```bash
curl -X POST "http://localhost:8003/api/doorlock/config" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "intent_recognition_enabled": true,
    "package_guard_available": true
  }'
```

**成功响应 (200)**

```json
{
  "success": true,
  "message": "配置更新成功"
}
```

**错误响应**

```json
// 400 - 缺少参数
{
  "success": false,
  "message": "缺少必填参数: device_id"
}

// 400 - 参数类型错误
{
  "success": false,
  "message": "参数类型错误: intent_recognition_enabled 必须是布尔值"
}

// 404 - 设备不存在
{
  "success": false,
  "message": "设备配置不存在: device001"
}

// 500 - 更新失败
{
  "success": false,
  "message": "配置更新失败"
}
```

---

## 2. 看护模式控制 API

### 2.1 启动看护模式

手动启动指定设备的快递看护模式。

**请求**

```
POST /api/doorlock/package_guard/start
Content-Type: application/json
```

**请求体参数**

| 参数名    | 类型   | 必填 | 说明                     |
| --------- | ------ | ---- | ------------------------ |
| device_id | string | 是   | 设备ID                   |
| reason    | string | 是   | 启动原因（用于日志记录） |

**请求示例**

```bash
curl -X POST "http://localhost:8003/api/doorlock/package_guard/start" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "reason": "手动启动看护"
  }'
```

**成功响应 (200)**

```json
{
  "success": true,
  "message": "看护模式已启动"
}
```

**错误响应**

```json
// 400 - 缺少参数
{
  "success": false,
  "message": "缺少必填参数: device_id"
}

// 400 - 功能未启用
{
  "success": false,
  "message": "看护模式功能未启用，请先在设备配置中启用"
}

// 404 - 设备不存在
{
  "success": false,
  "message": "设备配置不存在: device001"
}

// 500 - 启动失败
{
  "success": false,
  "message": "看护模式启动失败"
}
```

---

### 2.2 停止看护模式

手动停止指定设备的快递看护模式。

**请求**

```
POST /api/doorlock/package_guard/stop
Content-Type: application/json
```

**请求体参数**

| 参数名    | 类型   | 必填 | 说明                     |
| --------- | ------ | ---- | ------------------------ |
| device_id | string | 是   | 设备ID                   |
| reason    | string | 是   | 停止原因（用于日志记录） |

**请求示例**

```bash
curl -X POST "http://localhost:8003/api/doorlock/package_guard/stop" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "reason": "手动停止看护"
  }'
```

**成功响应 (200)**

```json
{
  "success": true,
  "message": "看护模式已停止"
}
```

**错误响应**

```json
// 400 - 缺少参数
{
  "success": false,
  "message": "缺少必填参数: reason"
}

// 404 - 设备不存在
{
  "success": false,
  "message": "设备配置不存在: device001"
}

// 500 - 停止失败
{
  "success": false,
  "message": "看护模式停止失败"
}
```

---

## 3. 欢迎词配置 API

### 3.1 配置欢迎词

为指定用户配置个性化欢迎词。

**请求**

```
POST /api/doorlock/welcome/config
Content-Type: application/json
```

**请求体参数**

| 参数名          | 类型    | 必填 | 说明           |
| --------------- | ------- | ---- | -------------- |
| person_id       | integer | 是   | 用户ID         |
| custom_greeting | object  | 是   | 欢迎词配置对象 |

**custom_greeting 对象结构**

| 字段名    | 类型   | 必填 | 说明                           |
| --------- | ------ | ---- | ------------------------------ |
| morning   | string | 否   | 早晨欢迎词（6:00-12:00）       |
| afternoon | string | 否   | 下午欢迎词（12:00-18:00）      |
| evening   | string | 否   | 晚上欢迎词（18:00-22:00）      |
| night     | string | 否   | 夜间欢迎词（22:00-6:00）       |
| default   | string | 否   | 默认欢迎词（未配置时段时使用） |

**请求示例**

```bash
curl -X POST "http://localhost:8003/api/doorlock/welcome/config" \
  -H "Content-Type: application/json" \
  -d '{
    "person_id": 5,
    "custom_greeting": {
      "morning": "早上好，张三",
      "afternoon": "下午好，张三",
      "evening": "晚上好，张三",
      "night": "夜深了，张三",
      "default": "欢迎回家"
    }
  }'
```

**成功响应 (200)**

```json
{
  "success": true,
  "message": "欢迎词配置成功"
}
```

**错误响应**

```json
// 400 - 缺少参数
{
  "success": false,
  "message": "缺少必填参数: person_id"
}

// 400 - 参数类型错误
{
  "success": false,
  "message": "参数类型错误: person_id 必须是整数"
}

// 400 - 格式错误
{
  "success": false,
  "message": "欢迎词格式错误: 包含无效的时段键: invalid_key"
}

// 404 - 用户不存在
{
  "success": false,
  "message": "欢迎词配置失败，用户可能不存在"
}
```

---

### 3.2 查询欢迎词配置

查询指定用户的欢迎词配置。

**请求**

```
GET /api/doorlock/welcome/config?person_id={person_id}
```

**查询参数**

| 参数名    | 类型    | 必填 | 说明   |
| --------- | ------- | ---- | ------ |
| person_id | integer | 是   | 用户ID |

**请求示例**

```bash
curl -X GET "http://localhost:8003/api/doorlock/welcome/config?person_id=5"
```

**成功响应 (200)**

```json
{
  "success": true,
  "data": {
    "person_id": 5,
    "custom_greeting": {
      "morning": "早上好，张三",
      "afternoon": "下午好，张三",
      "evening": "晚上好，张三",
      "night": "夜深了，张三",
      "default": "欢迎回家"
    }
  }
}
```

**错误响应**

```json
// 400 - 缺少参数
{
  "success": false,
  "message": "缺少必填参数: person_id"
}

// 400 - 参数类型错误
{
  "success": false,
  "message": "参数类型错误: person_id 必须是整数"
}

// 404 - 用户不存在
{
  "success": false,
  "message": "用户不存在: person_id=5"
}
```

---

### 3.3 获取预设模板

获取系统提供的欢迎词预设模板列表。

**请求**

```
GET /api/doorlock/welcome/templates
```

**请求示例**

```bash
curl -X GET "http://localhost:8003/api/doorlock/welcome/templates"
```

**成功响应 (200)**

```json
{
  "success": true,
  "data": {
    "templates": [
      {
        "name": "温馨家庭",
        "morning": "早上好，{name}",
        "afternoon": "下午好，{name}",
        "evening": "晚上好，{name}",
        "night": "夜深了，{name}",
        "default": "欢迎回家"
      },
      {
        "name": "简洁风格",
        "default": "欢迎回家，{name}"
      },
      {
        "name": "正式风格",
        "morning": "早安，{name}先生/女士",
        "afternoon": "午安，{name}先生/女士",
        "evening": "晚安，{name}先生/女士",
        "night": "夜深了，{name}先生/女士，请注意休息",
        "default": "欢迎回家，{name}先生/女士"
      }
    ]
  }
}
```

**响应说明**

- 模板中的 `{name}` 占位符会在实际使用时被替换为用户姓名
- 用户可以基于这些模板进行修改，或完全自定义

**错误响应**

```json
// 500 - 配置文件不存在
{
  "success": false,
  "message": "欢迎词模板配置文件不存在"
}
```

---

## 4. 历史记录查询 API

### 4.1 查询意图识别历史

查询指定设备的访客意图识别历史记录。

**请求**

```
GET /api/doorlock/intents/history?device_id={device_id}&limit={limit}&offset={offset}&start_date={start_date}&end_date={end_date}
```

**查询参数**

| 参数名     | 类型    | 必填 | 默认值 | 说明                                                |
| ---------- | ------- | ---- | ------ | --------------------------------------------------- |
| device_id  | string  | 是   | -      | 设备ID                                              |
| limit      | integer | 否   | 20     | 每页记录数（1-100）                                 |
| offset     | integer | 否   | 0      | 偏移量（用于分页）                                  |
| start_date | string  | 否   | -      | 开始日期（格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS） |
| end_date   | string  | 否   | -      | 结束日期（格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS） |

**请求示例**

```bash
# 基本查询
curl -X GET "http://localhost:8003/api/doorlock/intents/history?device_id=device001"

# 分页查询
curl -X GET "http://localhost:8003/api/doorlock/intents/history?device_id=device001&limit=10&offset=20"

# 时间范围查询
curl -X GET "http://localhost:8003/api/doorlock/intents/history?device_id=device001&start_date=2026-02-01&end_date=2026-02-28"
```

**成功响应 (200)**

```json
{
  "success": true,
  "data": [
    {
      "id": 123,
      "visit_id": 456,
      "session_id": "device001_1707379822000",
      "person_id": 5,
      "intent_type": "visit",
      "intent_summary": {
        "important_notes": [
          "【留言】明天下午3点再来拜访",
          "【提醒】带了一份礼物放在门口"
        ],
        "intent_type": "visit",
        "purpose": "拜访朋友，约定明天见面",
        "full_summary": "访客张三来拜访，主人不在家。访客表示明天下午3点会再来，并留下了一份礼物在门口。"
      },
      "dialogue_history": [
        {
          "role": "assistant",
          "content": "您好，请问您找谁？"
        },
        {
          "role": "user",
          "content": "我找李四，他在家吗？"
        }
      ],
      "created_at": "2026-02-08T14:30:22"
    }
  ],
  "total": 100,
  "limit": 20,
  "offset": 0
}
```

**响应字段说明**

| 字段名           | 类型          | 说明                                               |
| ---------------- | ------------- | -------------------------------------------------- |
| id               | integer       | 记录ID                                             |
| visit_id         | integer       | 访问记录ID                                         |
| session_id       | string        | 会话ID                                             |
| person_id        | integer\|null | 访客用户ID（陌生人为null）                         |
| intent_type      | string        | 意图类型（delivery/visit/sales/maintenance/other） |
| intent_summary   | object        | 意图总结对象                                       |
| dialogue_history | array         | 对话历史数组                                       |
| created_at       | string        | 创建时间（ISO 8601格式）                           |
| total            | integer       | 总记录数                                           |
| limit            | integer       | 每页记录数                                         |
| offset           | integer       | 当前偏移量                                         |

**错误响应**

```json
// 400 - 缺少参数
{
  "success": false,
  "message": "缺少必填参数: device_id"
}

// 400 - 参数范围错误
{
  "success": false,
  "message": "参数范围错误: limit 必须在 1-100 之间"
}

// 400 - 日期格式错误
{
  "success": false,
  "message": "参数格式错误: start_date 必须是日期格式 (YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS)"
}
```

---

### 4.2 查询快递警报历史

查询指定设备的快递异常警报历史记录。

**请求**

```
GET /api/doorlock/alerts/history?device_id={device_id}&limit={limit}&offset={offset}&start_date={start_date}&end_date={end_date}
```

**查询参数**

| 参数名     | 类型    | 必填 | 默认值 | 说明                                                |
| ---------- | ------- | ---- | ------ | --------------------------------------------------- |
| device_id  | string  | 是   | -      | 设备ID                                              |
| limit      | integer | 否   | 20     | 每页记录数（1-100）                                 |
| offset     | integer | 否   | 0      | 偏移量（用于分页）                                  |
| start_date | string  | 否   | -      | 开始日期（格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS） |
| end_date   | string  | 否   | -      | 结束日期（格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS） |

**请求示例**

```bash
# 基本查询
curl -X GET "http://localhost:8003/api/doorlock/alerts/history?device_id=device001"

# 分页查询
curl -X GET "http://localhost:8003/api/doorlock/alerts/history?device_id=device001&limit=10&offset=0"

# 时间范围查询
curl -X GET "http://localhost:8003/api/doorlock/alerts/history?device_id=device001&start_date=2026-02-01&end_date=2026-02-28"
```

**成功响应 (200)**

```json
{
  "success": true,
  "data": [
    {
      "id": 456,
      "device_id": "device001",
      "session_id": "device001_1707380410000",
      "threat_level": "high",
      "action": "taking",
      "description": "检测到陌生人拿走快递包裹",
      "photo_path": "visits/2026-02/alert_456.jpg",
      "voice_warning_sent": true,
      "notified": true,
      "created_at": "2026-02-08T15:20:10"
    }
  ],
  "total": 50,
  "limit": 20,
  "offset": 0
}
```

**响应字段说明**

| 字段名             | 类型    | 说明                                                 |
| ------------------ | ------- | ---------------------------------------------------- |
| id                 | integer | 警报ID                                               |
| device_id          | string  | 设备ID                                               |
| session_id         | string  | 会话ID                                               |
| threat_level       | string  | 威胁等级（low/medium/high）                          |
| action             | string  | 行为类型（taking/searching/damaging/normal/passing） |
| description        | string  | 详细描述                                             |
| photo_path         | string  | 证据照片路径                                         |
| voice_warning_sent | boolean | 是否已发送语音警告                                   |
| notified           | boolean | 是否已通知App                                        |
| created_at         | string  | 创建时间（ISO 8601格式）                             |
| total              | integer | 总记录数                                             |
| limit              | integer | 每页记录数                                           |
| offset             | integer | 当前偏移量                                           |

**错误响应**

```json
// 400 - 缺少参数
{
  "success": false,
  "message": "缺少必填参数: device_id"
}

// 400 - 参数范围错误
{
  "success": false,
  "message": "参数范围错误: offset 必须大于等于 0"
}
```

---

## 5. CORS 支持

所有 API 接口都支持 CORS（跨域资源共享），允许从任何域名访问。

**预检请求**

```
OPTIONS /api/doorlock/*
```

**响应头**

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

---

## 6. 使用示例

### 6.1 完整配置流程

```bash
# 1. 获取设备当前配置
curl -X GET "http://localhost:8003/api/doorlock/config?device_id=device001"

# 2. 启用意图识别和看护模式功能
curl -X POST "http://localhost:8003/api/doorlock/config" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "intent_recognition_enabled": true,
    "package_guard_available": true
  }'

# 3. 配置用户欢迎词
curl -X POST "http://localhost:8003/api/doorlock/welcome/config" \
  -H "Content-Type: application/json" \
  -d '{
    "person_id": 5,
    "custom_greeting": {
      "morning": "早上好，张三",
      "default": "欢迎回家"
    }
  }'

# 4. 手动启动看护模式
curl -X POST "http://localhost:8003/api/doorlock/package_guard/start" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "reason": "有快递需要看护"
  }'
```

### 6.2 查询历史记录

```bash
# 查询最近20条意图识别记录
curl -X GET "http://localhost:8003/api/doorlock/intents/history?device_id=device001&limit=20"

# 查询本月的快递警报记录
curl -X GET "http://localhost:8003/api/doorlock/alerts/history?device_id=device001&start_date=2026-02-01&end_date=2026-02-28"

# 分页查询（第2页，每页10条）
curl -X GET "http://localhost:8003/api/doorlock/intents/history?device_id=device001&limit=10&offset=10"
```

---

## 7. 注意事项

1. **设备ID**: 所有 API 都需要提供有效的 device_id，请确保设备已在系统中注册
2. **看护模式**: 启动看护模式前，必须先在设备配置中启用 `package_guard_available`
3. **欢迎词配置**: 欢迎词配置只对有开门权限的用户生效
4. **分页查询**: 建议使用分页参数避免一次性查询过多数据
5. **时间格式**: 所有时间字段使用 ISO 8601 格式（YYYY-MM-DDTHH:MM:SS）
6. **错误处理**: 客户端应根据 HTTP 状态码和响应中的 `success` 字段判断请求是否成功

---

## 8. 更新日志

### v1.0.0 (2026-02-09)

- 初始版本发布
- 实现设备配置管理 API
- 实现看护模式控制 API
- 实现欢迎词配置 API
- 实现历史记录查询 API
