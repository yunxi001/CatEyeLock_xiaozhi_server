# App 与服务器通信协议文档

## 概述

App 通过 WebSocket 与服务器通信，使用专用的 App 端点。

## 连接信息

- **协议**: WebSocket
- **端口**: 8000
- **路径**: `/ws/app`
- **完整地址**: `ws://{服务器IP}:8000/ws/app`

---

## 1. 连接认证

### 1.1 App 发送 Hello 消息

App 连接后必须在 10 秒内发送 hello 消息进行认证。

**请求格式**:
```json
{
    "type": "hello",
    "client_type": "app",
    "device_id": "设备唯一标识符"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 是 | 固定为 `hello` |
| client_type | string | 是 | 固定为 `app` |
| device_id | string | 是 | 要关联的 ESP32 设备 ID（如 `AA:BB:CC:DD:EE:FF`） |

### 1.2 服务器响应

**成功响应**:
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

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定为 `hello` |
| status | string | `ok` 表示成功 |
| device_info.online | boolean | 设备是否在线 |
| device_info.mode | string | 当前模式：`normal` 或 `monitor` |

**失败响应**:
```json
{
    "type": "hello",
    "status": "error",
    "message": "错误信息"
}
```

**可能的错误**:
- `期望收到 hello 消息`
- `client_type 必须为 app`
- `缺少 device_id`
- `设备 {device_id} 不在线`

---

## 2. 系统命令

### 2.1 启动监控模式

App 可以请求 ESP32 进入监控模式，此模式下 ESP32 的音频会转发给 App。

**请求格式**:
```json
{
    "type": "system",
    "command": "start_monitor"
}
```

**成功响应**:
```json
{
    "type": "system",
    "status": "success",
    "command": "start_monitor"
}
```

**失败响应**:
```json
{
    "type": "system",
    "status": "error",
    "message": "错误信息"
}
```

### 2.2 停止监控模式

**请求格式**:
```json
{
    "type": "system",
    "command": "stop_monitor"
}
```

**成功响应**:
```json
{
    "type": "system",
    "status": "success",
    "command": "stop_monitor"
}
```

---

## 3. 消息转发

### 3.1 App 转发消息到 ESP32

App 可以通过添加 `forward: true` 字段将消息转发给 ESP32。

**请求格式**:
```json
{
    "forward": true,
    "type": "任意类型",
    "...": "其他字段"
}
```

服务器会移除 `forward` 字段后转发给 ESP32。

---

## 4. 音频通信

### 4.1 监控模式下接收音频（服务器 → App）

当 ESP32 处于监控模式时，服务器会将 ESP32 的音频转发给 App。

**数据格式**: 二进制 PCM 数据

| 参数 | 值 |
|------|------|
| 采样率 | 16000 Hz |
| 声道数 | 1（单声道） |
| 位深度 | 16-bit |
| 帧大小 | 960 采样点（60ms） |
| 每帧字节数 | 1920 bytes |

### 4.2 App 发送音频（App → 服务器 → ESP32）

App 可以发送 PCM 音频给服务器，服务器会编码为 OPUS 后转发给 ESP32（用于对讲功能）。

**数据格式**: 二进制 PCM 数据

| 参数 | 值 |
|------|------|
| 采样率 | 24000 Hz |
| 声道数 | 1（单声道） |
| 位深度 | 16-bit |
| 帧大小 | 60ms |

---

## 5. 人脸管理接口

### 5.1 人脸录入

**请求格式**:
```json
{
    "type": "face_management",
    "action": "register",
    "data": {
        "name": "张三",
        "relation_type": "family",
        "images": ["base64编码的图片1", "base64编码的图片2"],
        "permission": {
            "always_allow": true,
            "time_ranges": null
        }
    }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 人员姓名 |
| relation_type | string | 否 | 关系类型：`family`/`friend`/`other`，默认 `other` |
| images | array | 是 | Base64 编码的人脸图片数组（建议 3-5 张） |
| permission | object | 否 | 权限配置 |
| permission.always_allow | boolean | 否 | 是否始终允许 |
| permission.time_ranges | array | 否 | 允许的时间段 |

**成功响应**:
```json
{
    "type": "face_management",
    "action": "register",
    "status": "success",
    "person_id": 123
}
```

**失败响应**:
```json
{
    "type": "face_management",
    "action": "register",
    "status": "error",
    "error": "missing_data"
}
```

**可能的错误**:
- `missing_data` - 缺少必要数据
- `invalid_images` - 图片无效
- `no_face_detected` - 未检测到人脸
- `face_already_exists` - 人脸已存在

### 5.2 获取人员列表

**请求格式**:
```json
{
    "type": "face_management",
    "action": "get_persons"
}
```

**成功响应**:
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
            "created_at": "2025-01-01 12:00:00"
        },
        {
            "id": 2,
            "name": "李四",
            "relation_type": "friend",
            "created_at": "2025-01-02 14:30:00"
        }
    ]
}
```

### 5.3 获取人员详情

**请求格式**:
```json
{
    "type": "face_management",
    "action": "get_person",
    "data": {
        "person_id": 1
    }
}
```

**成功响应**:
```json
{
    "type": "face_management",
    "action": "get_person",
    "status": "success",
    "data": {
        "id": 1,
        "name": "张三",
        "relation_type": "family",
        "permission": {
            "always_allow": true,
            "time_ranges": null
        },
        "created_at": "2025-01-01 12:00:00"
    }
}
```

**失败响应**:
```json
{
    "type": "face_management",
    "action": "get_person",
    "status": "error",
    "error": "person_not_found"
}
```

### 5.4 删除人员

**请求格式**:
```json
{
    "type": "face_management",
    "action": "delete_person",
    "data": {
        "person_id": 1
    }
}
```

**成功响应**:
```json
{
    "type": "face_management",
    "action": "delete_person",
    "status": "success"
}
```

**失败响应**:
```json
{
    "type": "face_management",
    "action": "delete_person",
    "status": "error",
    "error": "delete_failed"
}
```

### 5.5 更新权限

**请求格式**:
```json
{
    "type": "face_management",
    "action": "update_permission",
    "data": {
        "person_id": 1,
        "permission": {
            "always_allow": false,
            "time_ranges": [
                {
                    "start_time": "09:00",
                    "end_time": "18:00",
                    "weekdays": [1, 2, 3, 4, 5]
                }
            ]
        }
    }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| always_allow | boolean | 是否始终允许 |
| time_ranges | array | 允许的时间段列表 |
| time_ranges[].start_time | string | 开始时间（HH:MM） |
| time_ranges[].end_time | string | 结束时间（HH:MM） |
| time_ranges[].weekdays | array | 允许的星期（1-7，1=周一） |

**成功响应**:
```json
{
    "type": "face_management",
    "action": "update_permission",
    "status": "success"
}
```

### 5.6 获取到访记录

**请求格式**:
```json
{
    "type": "face_management",
    "action": "get_visits",
    "data": {
        "page": 1,
        "page_size": 20,
        "date_from": "2025-01-01",
        "date_to": "2025-01-31"
    }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 20 |
| date_from | string | 否 | 开始日期（YYYY-MM-DD） |
| date_to | string | 否 | 结束日期（YYYY-MM-DD） |

**成功响应**:
```json
{
    "type": "face_management",
    "action": "get_visits",
    "status": "success",
    "data": {
        "total": 100,
        "page": 1,
        "page_size": 20,
        "records": [
            {
                "id": 1,
                "person_id": 1,
                "person_name": "张三",
                "result": "known",
                "access_granted": true,
                "visit_time": "2025-01-15 10:30:00"
            },
            {
                "id": 2,
                "person_id": null,
                "person_name": null,
                "result": "unknown",
                "access_granted": false,
                "visit_time": "2025-01-15 11:00:00"
            }
        ]
    }
}
```

---

## 6. 服务器推送通知

### 6.1 到访通知（人脸识别）

当有人脸识别事件时，服务器会主动推送通知给 App。

**推送格式**:
```json
{
    "type": "visit_notification",
    "data": {
        "visit_id": 123,
        "person_id": 1,
        "person_name": "张三",
        "relation": "family",
        "result": "known",
        "access_granted": true
    }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定为 `visit_notification` |
| data.visit_id | int | 到访记录 ID |
| data.person_id | int/null | 人员 ID（陌生人为 null） |
| data.person_name | string/null | 人员姓名（陌生人为 null） |
| data.relation | string/null | 关系类型：`family`/`friend`/`other`（陌生人为 null） |
| data.result | string | 识别结果：`known`/`unknown`/`no_face` |
| data.access_granted | boolean | 是否允许通行 |

---

## 7. 完整通信流程示例

### 7.1 建立连接并启动监控

```
1. App 建立 WebSocket 连接到 ws://服务器:8000/ws/app
2. App → 服务器: {"type": "hello", "client_type": "app", "device_id": "AA:BB:CC:DD:EE:FF"}
3. 服务器 → App: {"type": "hello", "status": "ok", "device_info": {...}}
4. App → 服务器: {"type": "system", "command": "start_monitor"}
5. 服务器 → App: {"type": "system", "status": "success", "command": "start_monitor"}
6. 服务器 → App: [PCM 音频数据流...]
```

### 7.2 对讲功能

```
1. 连接已建立
2. App → 服务器: [PCM 音频数据 (24kHz, 单声道, 16-bit)]
3. 服务器编码为 OPUS 后转发给 ESP32
```

### 7.3 人脸录入流程

```
1. 连接已建立
2. App → 服务器: {"type": "face_management", "action": "register", "data": {...}}
3. 服务器 → App: {"type": "face_management", "action": "register", "status": "success", "person_id": 1}
```

### 7.4 接收到访通知

```
1. 连接已建立
2. ESP32 检测到人脸，发送识别请求
3. 服务器处理识别
4. 服务器 → App: {"type": "visit_notification", "data": {...}}
```

---

## 8. 错误处理

- 认证超时（10秒）：服务器主动关闭连接
- 设备离线：返回错误响应
- 消息格式错误：记录日志，不响应

---

## 9. 注意事项

1. **连接路径必须是 `/ws/app`**
2. **认证必须在 10 秒内完成**，否则连接会被关闭
3. **device_id 必须对应一个在线的 ESP32**
4. **监控模式下的音频是 PCM 格式**（16kHz），App 无需解码
5. **App 发送的音频必须是 24kHz PCM**，服务器会自动编码为 OPUS
6. **一个 ESP32 可以关联多个 App**，音频和通知会广播给所有 App
7. **人脸图片建议使用 JPEG 格式**，Base64 编码后发送
