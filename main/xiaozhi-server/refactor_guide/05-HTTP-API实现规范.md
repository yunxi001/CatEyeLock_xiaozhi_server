# HTTP API 实现规范 v6.0

> **版本：** v6.0（简化版，替代 WebSocket query 和 face_management）
> **日期：** 2026-05-05
> **状态：** 第一阶段已完成，第二阶段待实施
> **依赖：** 00-总体通信协议规范、03-Server-App-WebSocket协议规范、04-协议实施指南

---

## 1. 背景

根据文档03 §9，以下功能从 WebSocket 迁移到 HTTP API：

| 原 WebSocket 功能 | 原消息类型 | 新 HTTP API |
|---|---|---|
| 查询设备状态 | `query` (target=status) | `GET /api/doorlock/status` |
| 人脸列表/注册 | `face_management` (register/get_persons/...) | `GET/POST /api/doorlock/faces` |
| 查询事件历史 | `query` (target=events) | `GET /api/doorlock/events` |
| 查询开锁日志 | `query` (target=unlock_logs) | `GET /api/doorlock/unlock_logs` |
| 查询媒体文件 | `query` (target=media_files) | `GET /api/doorlock/media` |
| 下载媒体文件 | `media_download` / `media_download_chunk` | `GET /api/doorlock/media/<id>` |
| 删除人脸 | `face_management` (delete_person) | `DELETE /api/doorlock/faces/<id>` |
| 更新权限 | `face_management` (update_permission) | `PUT /api/doorlock/faces/<id>/permission` |
| 查询到访记录 | `face_management` (get_visits) | `GET /api/doorlock/visits` |
| 查询密码 | `query` (target=password) | `GET /api/doorlock/password` |

**迁移原因**（文档03 §9.1）：HTTP 天然是请求-响应模式，无需 seq_id 匹配；大体积响应（历史日志、图片）不阻塞 WebSocket 实时推送。

---

## 2. 实施优先级

### 2.1 第一阶段（已完成 ✅）

已实现 6 个端点，替代 `FaceManagementHandler` 的全部功能及 `QueryHandler` 的设备状态查询：

| 端点 | 方法 | 用途 | 状态 |
|------|------|------|:---:|
| `/api/doorlock/status` | GET | 查询设备当前状态 | ✅ |
| `/api/doorlock/faces` | GET | 查询人脸列表 | ✅ |
| `/api/doorlock/faces` | POST | 注册人脸（multipart） | ✅ |
| `/api/doorlock/faces/<id>` | DELETE | 删除人脸 | ✅ |
| `/api/doorlock/faces/<id>/permission` | PUT | 更新权限 | ✅ |
| `/api/doorlock/visits` | GET | 到访记录列表 | ✅ |

已删除：
- `FaceManagementHandler` 类（`faceRecognitionHandler.py`）
- `TextMessageType.FACE_MANAGEMENT` 枚举

### 2.2 第二阶段（待实施）

| # | 端点 | 方法 | 用途 | 所属文件 |
|---|------|------|------|------|
| 7 | `/api/doorlock/events` | GET | 查询事件历史 | `doorlock_api_handler.py` |
| 8 | `/api/doorlock/unlock_logs` | GET | 查询开锁日志 | `doorlock_api_handler.py` |
| 9 | `/api/doorlock/password` | GET | 查询设备密码 | `doorlock_api_handler.py` |
| 10 | `/api/doorlock/media` | GET | 查询媒体文件列表 | `doorlock_media_handler.py`（新文件） |
| 11 | `/api/doorlock/media/{id}` | GET | 按ID下载媒体文件 | `doorlock_media_handler.py`（新文件） |
| 12 | `/api/doorlock/media/download` | GET | 按路径下载图片（`?path=...`） | `doorlock_media_handler.py`（新文件） |

完成后可删除：
- `QueryHandler`（`queryHandler.py`，304 行）
- `MediaDownloadHandler`（`mediaDownloadHandler.py`，163 行）
- `MediaDownloadChunkHandler`（`mediaDownloadHandler.py`，100 行）
- `TextMessageType.QUERY`、`TextMessageType.MEDIA_DOWNLOAD`、`TextMessageType.MEDIA_DOWNLOAD_CHUNK` 枚举

---

## 3. 认证方式

所有 HTTP API 使用 **HTTP Header JWT 认证**：

```
Authorization: Bearer <token>
```

**Token 获取**：App 通过 WebSocket hello 认证后，服务器在 hello 响应中返回 `token` 字段（JWT 格式）。此功能已于勘误 E-4 实现（`app_connection.py` 第 115-118 行）。

**Token 生成**：使用 `core/utils/auth.py` 中的 `AuthToken` 类，`generate_token(device_id)` 方法生成包含 `{device_id, exp}` 的 AES-256-GCM 加密 JWT，有效期 1 小时。密钥来自 `config["server"]["auth_key"]`。

**认证流程**：
1. App 通过 WebSocket hello 获取 token
2. 后续所有 HTTP 请求携带 `Authorization: Bearer <token>` header
3. `DoorlockApiHandler._verify_auth()` 验证 token 有效性，提取 `device_id`

---

## 4. 统一响应格式

所有 API 响应使用统一格式：

```json
// 成功
{ "success": true, "data": { ... } }

// 失败
{ "success": false, "message": "错误描述" }
```

分页查询在 `data` 中额外包含 `total`、`page`、`page_size`。

---

## 5. 实现架构

### 5.1 文件组织

```
core/api/
  doorlock_api_handler.py       # ✅ 第一阶段已创建 — 需新增 3 个方法（events/unlock_logs/password）
  doorlock_media_handler.py     # ❌ 待创建 — 媒体文件下载（3 个端点）
```

### 5.2 已注册路由（http_server.py）

第一阶段已注册的 9 条路由（6 端点 + CORS）：

```python
# 门锁核心 API (v6.0 第一阶段) — 已实现
web.get("/api/doorlock/status", self.doorlock_api_handler.handle_get_status),
web.options("/api/doorlock/status", self.doorlock_api_handler.handle_options),
web.get("/api/doorlock/faces", self.doorlock_api_handler.handle_get_faces),
web.post("/api/doorlock/faces", self.doorlock_api_handler.handle_post_faces),
web.delete("/api/doorlock/faces/{face_id}", self.doorlock_api_handler.handle_delete_face),
web.put("/api/doorlock/faces/{face_id}/permission", self.doorlock_api_handler.handle_update_permission),
web.options("/api/doorlock/faces", self.doorlock_api_handler.handle_options),
web.get("/api/doorlock/visits", self.doorlock_api_handler.handle_get_visits),
web.options("/api/doorlock/visits", self.doorlock_api_handler.handle_options),
```

### 5.3 数据访问层

- `Database` 类（`core/providers/doorlock/database.py`）：提供 `get_events`、`get_unlock_logs`、`get_media_files`、`get_media_file_by_id`、`get_device_password`、`get_latest_status` 等方法
- `FaceService`（`core/providers/doorlock/face_service.py`）：提供 `get_persons`、`register_face`、`delete_person`、`update_permission`、`get_visits`
- 通过 `get_face_service()` 获取 FaceService 单例，再通过 `face_service.db` 访问数据库

---

## 6. 第二阶段 API 详细规范

### 6.1 GET /api/doorlock/events — 查询事件历史

**请求**：
```
GET /api/doorlock/events?device_id=AA:BB:CC:DD:EE:FF&event_type=bell&limit=50&offset=0
Authorization: Bearer <token>
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `device_id` | string | 是 | 设备 MAC 地址 |
| `event_type` | string | 否 | 事件类型过滤（bell/motion/sos等） |
| `limit` | int | 否 | 每页条数（默认 100，最大 500） |
| `offset` | int | 否 | 偏移量 |

**成功响应 (200)**：
```json
{
  "success": true,
  "data": {
    "records": [
      {
        "id": 1001,
        "device_id": "AA:BB:CC:DD:EE:FF",
        "event_type": "bell",
        "event_data": {},
        "ts": 1702234567890
      }
    ],
    "total": 50,
    "limit": 50,
    "offset": 0
  }
}
```

**实现**：调用 `face_service.db.get_events(device_id, event_type, limit, offset)`。

### 6.2 GET /api/doorlock/unlock_logs — 查询开锁日志

**请求**：
```
GET /api/doorlock/unlock_logs?device_id=AA:BB:CC:DD:EE:FF&method=finger&result=1&limit=50&offset=0
Authorization: Bearer <token>
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `device_id` | string | 是 | 设备 MAC 地址 |
| `method` | string | 否 | 开锁方式（finger/nfc/password/face/remote） |
| `result` | int | 否 | 结果过滤（1=成功, 0=失败） |
| `limit` | int | 否 | 每页条数（默认 100，最大 500） |
| `offset` | int | 否 | 偏移量 |

**成功响应 (200)**：
```json
{
  "success": true,
  "data": {
    "records": [
      {
        "id": 2001,
        "device_id": "AA:BB:CC:DD:EE:FF",
        "method": "face",
        "user_id": 5,
        "user_name": "张三",
        "result": 1,
        "ts": 1702234567890
      }
    ],
    "total": 120,
    "limit": 50,
    "offset": 0
  }
}
```

**实现**：调用 `face_service.db.get_unlock_logs(device_id, method, result, limit, offset)`。

### 6.3 GET /api/doorlock/password — 查询设备密码

**请求**：
```
GET /api/doorlock/password?device_id=AA:BB:CC:DD:EE:FF
Authorization: Bearer <token>
```

**成功响应 (200)**：
```json
{
  "success": true,
  "data": {
    "password": "123456"
  }
}
```

**实现**：调用 `face_service.db.get_device_password(device_id)`。

### 6.4 GET /api/doorlock/media — 媒体文件列表

**请求**：
```
GET /api/doorlock/media?device_id=AA:BB:CC:DD:EE:FF&file_type=face&date_from=2024-12-01&limit=50&offset=0
Authorization: Bearer <token>
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `device_id` | string | 是 | 设备 MAC 地址 |
| `file_type` | string | 否 | 文件类型（face/recording） |
| `date_from` | string | 否 | 起始日期（YYYY-MM-DD） |
| `date_to` | string | 否 | 结束日期（YYYY-MM-DD） |
| `limit` | int | 否 | 每页条数（默认 100，最大 500） |
| `offset` | int | 否 | 偏移量 |

**成功响应 (200)**：
```json
{
  "success": true,
  "data": {
    "records": [
      {
        "id": 456,
        "device_id": "AA:BB:CC:DD:EE:FF",
        "file_type": "face",
        "file_path": "faces/AA:BB:CC:DD:EE:FF/2024-12-11/face_1702234567890_5.jpg",
        "file_size": 245678,
        "user_id": 5,
        "created_at": "2024-12-11T14:30:00"
      }
    ],
    "total": 30,
    "limit": 50,
    "offset": 0
  }
}
```

**实现**：调用 `face_service.db.get_media_files(device_id, file_type, date_from, date_to, limit, offset)`。

### 6.5 GET /api/doorlock/media/{file_id} — 按ID下载媒体文件

**请求**：
```
GET /api/doorlock/media/456
Authorization: Bearer <token>
```

**响应**：直接返回文件二进制流，`Content-Type` 根据文件扩展名设置（image/jpeg、image/png 等），`Content-Disposition: inline`。

与旧 WebSocket 方式的关键区别：**HTTP 直接返回原始二进制，不再 Base64 编码**。

### 6.6 GET /api/doorlock/media/download — 按路径下载图片

**请求**：
```
GET /api/doorlock/media/download?path=faces/AA:BB:CC:DD:EE:FF/2024-12-11/face_1702234567890_5.jpg
Authorization: Bearer <token>
```

用于 App 从 `visit_notification` 中的 `image_path` 直接下载人脸图片。

**安全检查**：`os.path.realpath(full_path)` 必须以 `os.path.realpath(MEDIA_ROOT)` 开头，防止路径遍历攻击。

**MEDIA_ROOT**：`data/media`（与 `mediaDownloadHandler.py` 中的定义一致）。

---

## 7. 实施顺序与依赖关系

```
第1步：doorlock_api_handler.py 新增3个方法
  ├── handle_get_events      → db.get_events()
  ├── handle_get_unlock_logs → db.get_unlock_logs()
  └── handle_get_password    → db.get_device_password()

第2步：创建 doorlock_media_handler.py（新文件）
  ├── handle_get_list        → db.get_media_files()
  ├── handle_download        → db.get_media_file_by_id() + 文件读取 + 二进制流响应
  └── handle_download_by_path → 路径安全检查 + 文件读取 + 二进制流响应

第3步：http_server.py 注册新路由（9 条 = 6 端点 + CORS 预检）

第4步：删除旧 WebSocket handler
  ├── queryHandler.py（整个文件）
  ├── mediaDownloadHandler.py（整个文件）
  ├── TextMessageType 枚举移除 QUERY/MEDIA_DOWNLOAD/MEDIA_DOWNLOAD_CHUNK
  └── TextMessageHandlerRegistry 移除对应导入和注册
```

---

## 8. 与现有 HTTP API 的一致性

新增 API 遵循现有 `doorlock_config_handler.py` 的代码风格：

1. 使用 `aiohttp.web.Request` / `web.Response`
2. JSON 响应使用 `web.json_response()`
3. 文件下载使用 `web.StreamResponse()`（二进制流，非 JSON）
4. 错误响应格式 `{success: false, message: "..."}` 
5. 每个端点提供 `handle_options()` 处理 CORS 预检
6. 使用 `from loguru import logger` 记录错误

---

## 9. 验证清单

### 第一阶段（已完成）

- [x] `GET /api/doorlock/status` 返回正确设备状态
- [x] `POST /api/doorlock/faces` 成功上传人脸图片并录入
- [x] `GET /api/doorlock/faces` 返回正确的人员列表
- [x] `DELETE /api/doorlock/faces/5` 成功删除人脸并返回成功
- [x] `PUT /api/doorlock/faces/5/permission` 成功更新权限
- [x] `GET /api/doorlock/visits` 返回正确的到访记录分页
- [x] 未认证请求返回 401
- [x] CORS 预检请求正常工作

### 第二阶段（待验证）

- [ ] `GET /api/doorlock/events` 返回正确的事件历史分页
- [ ] `GET /api/doorlock/unlock_logs` 返回正确的开锁日志分页
- [ ] `GET /api/doorlock/password` 返回正确的设备密码
- [ ] `GET /api/doorlock/media` 返回正确的媒体文件列表
- [ ] `GET /api/doorlock/media/{id}` 返回正确的文件二进制流
- [ ] `GET /api/doorlock/media/download?path=...` 返回正确的图片文件
- [ ] 路径遍历攻击被正确拦截（`../` 等）
- [ ] 不存在的文件返回 404
- [ ] 旧 WebSocket handler 已删除，导入无报错
