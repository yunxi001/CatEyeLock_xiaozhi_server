# App 端数据处理流程详细分析

本文档深入分析服务器接收 App 端命令的处理逻辑，包括连接认证、命令代理、数据查询、媒体下载和实时推送五个核心模块。

## 目录

1. [连接认证与管理](#1-连接认证与管理)
2. [命令代理处理](#2-命令代理处理)
3. [数据查询处理](#3-数据查询处理)
4. [媒体文件下载](#4-媒体文件下载)
5. [实时数据推送](#5-实时数据推送)

---

## 1. 连接认证与管理

### 1.1 连接建立与认证

**文件**: `core/app_connection.py` - `AppConnectionHandler` 类

**协议版本**: v2.2

**处理流程**:

#### 1.1.1 WebSocket 连接建立

```python
async def handle_connection(self, ws):
    self.websocket = ws
    # 等待 hello 消息进行认证（10 秒超时）
    hello_msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
```

**超时处理**:

- 10 秒内未收到 hello 消息，关闭连接
- 记录警告日志 "App 认证超时"

#### 1.1.2 Hello 消息认证

**消息格式**:

```json
{
  "type": "hello",
  "client_type": "app",
  "device_id": "ESP32_AABBCC",
  "app_id": "user_12345"
}
```

**字段验证**:

1. **type 验证**: 必须为 "hello"
2. **client_type 验证**: 必须为 "app"
3. **device_id 验证**: 必须存在且非空
4. **app_id 验证**: 必须存在且非空（用户标识）

**验证失败响应**:

```json
{
  "type": "hello",
  "status": "error",
  "message": "缺少 app_id"
}
```

**认证成功响应**:

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

#### 1.1.3 连接注册

**处理逻辑**:

```python
# 保存连接信息
self.device_id = device_id
self.app_id = app_id
self.authenticated = True

# 注册到 ConnectionManager
manager = ConnectionManager.get_instance()
manager.register_app(device_id, self)
```

**ConnectionManager 管理**:

- 维护 `device_id` → `[app_conn1, app_conn2, ...]` 映射
- 支持一个设备多个 App 同时连接
- 用于消息广播和状态推送

#### 1.1.4 初始状态推送

认证成功后，服务器主动推送设备状态：

**1. 设备在线/离线通知**:

```json
{
  "type": "device_status",
  "status": "online",
  "device_id": "ESP32_AABBCC",
  "ts": 1702234567890
}
```

**2. 完整设备状态**（设备在线时）:

```json
{
  "type": "device_state_full",
  "ts": 1702234567890,
  "device_id": "ESP32_AABBCC",
  "state": {
    "light": { "state": "on", "brightness": 80 },
    "door": { "state": "closed", "locked": true },
    "sensor": { "battery": 85, "lux": 300 }
  }
}
```

**流程图**:

```
App 连接 WebSocket
    ↓
等待 hello 消息（10 秒超时）
    ↓
解析并验证消息字段
    ├─ type != "hello" → 发送错误 → 关闭连接
    ├─ client_type != "app" → 发送错误 → 关闭连接
    ├─ 缺少 device_id → 发送错误 → 关闭连接
    └─ 缺少 app_id → 发送错误 → 关闭连接
    ↓
认证成功
    ├─ 保存 device_id, app_id
    ├─ 设置 authenticated = True
    └─ 注册到 ConnectionManager
    ↓
检查 ESP32 是否在线
    ↓
发送认证成功响应（含设备信息）
    ↓
推送初始设备状态
    ├─ 推送设备在线/离线通知
    └─ 推送完整设备状态（如果在线）
    ↓
开始处理消息
```

---

### 1.2 消息路由与防重放

**文件**: `core/app_connection.py` - `_handle_text_message` 方法

**协议版本**: v2.2

#### 1.2.1 seq_id 防重放机制

**消息格式**:

```json
{
  "type": "lock_control",
  "seq_id": "1702234567890_0",
  "command": "unlock"
}
```

**处理逻辑**:

```python
# 1. 提取 seq_id
seq_id = msg_json.get("seq_id")

# 2. 检查是否重复消息
if seq_id:
    if not self._seq_id_cache.check_and_add(self.app_id, seq_id):
        # 重复消息，发送 ACK 并忽略
        await self._send_server_ack(seq_id, code=9, msg="重复消息")
        return

    # 3. 发送 ACK 确认收到
    await self._send_server_ack(seq_id, code=0, msg="已接收")
```

**server_ack 响应**:

```json
{
  "type": "server_ack",
  "seq_id": "1702234567890_0",
  "code": 0,
  "msg": "已接收",
  "ts": 1702234567890
}
```

**状态码**:

- `0`: 成功
- `3`: 参数错误
- `8`: 未认证
- `9`: 重复消息

#### 1.2.2 SeqIdCache 实现

**特点**:

- 类级别共享缓存（所有 App 连接共享）
- 按 `app_id` 分组存储
- FIFO 淘汰策略（最大 100 条）
- 防止重放攻击

**缓存结构**:

```python
{
  "user_12345": ["seq_id_1", "seq_id_2", ...],
  "user_67890": ["seq_id_3", "seq_id_4", ...]
}
```

#### 1.2.3 消息分发

**处理逻辑**:

```python
# 处理特殊消息类型
if msg_type == "get_device_status":
    await self._handle_get_device_status(seq_id)
    return

# 统一使用 Handler 处理消息
await handleTextMessage(self, message)
```

**Handler 注册表**:

- `QueryHandler`: 数据查询
- `MediaDownloadHandler`: 媒体下载
- `LockControlProxyHandler`: 锁控命令
- `DevControlProxyHandler`: 设备控制
- `UserMgmtProxyHandler`: 用户管理

---

### 1.3 音频对讲处理

**文件**: `core/app_connection.py` - `_handle_binary_message` 方法

**处理逻辑**:

#### 1.3.1 接收 App 音频

**音频格式**:

- 编码: 16-bit PCM
- 采样率: 24kHz
- 声道: 单声道
- 传输: WebSocket 二进制消息

#### 1.3.2 编码转换

```python
# 初始化 OPUS 编码器（延迟初始化）
if self.opus_encoder is None:
    self.opus_encoder = OpusEncoderUtils(
        sample_rate=24000,
        channels=1,
        frame_size_ms=60
    )

# 编码 PCM 为 OPUS
def send_opus_callback(opus_data):
    asyncio.run_coroutine_threadsafe(
        esp32_conn.websocket.send(opus_data),
        asyncio.get_event_loop()
    )

self.opus_encoder.encode_pcm_to_opus_stream(
    message,
    end_of_stream=False,
    callback=send_opus_callback
)
```

#### 1.3.3 转发给 ESP32

**目标格式**:

- 编码: OPUS
- 采样率: 24kHz
- 声道: 单声道
- 帧长: 60ms

**流程图**:

```
App 发送 PCM 音频（二进制）
    ↓
检查 ESP32 连接是否可用
    ↓
否 → 记录警告 → 返回
    ↓
是 → 初始化 OPUS 编码器（延迟初始化）
    ↓
编码 PCM 为 OPUS
    ↓
通过回调发送给 ESP32
    ↓
完成
```

---

## 2. 命令代理处理

### 2.1 锁控命令代理

**文件**: `core/handle/textHandler/commandProxyHandler.py` - `LockControlProxyHandler`

**App 协议**: v2.4（App → Server）  
**ESP32 协议**: v5.2（Server → ESP32）

**说明**: Server 接收 App 的 v2.4 协议命令，记录日志后转发给 ESP32（v5.2 协议）

**支持的命令**:

- `unlock`: 远程开锁
- `lock`: 远程关锁
- `temp_code`: 设置临时密码

#### 2.1.1 消息格式

**请求**:

```json
{
  "type": "lock_control",
  "seq_id": "1702234567890_0",
  "command": "unlock"
}
```

**响应**（成功）:

```json
{
  "type": "lock_control",
  "status": "success"
}
```

**响应**（失败）:

```json
{
  "type": "lock_control",
  "status": "error",
  "code": 1,
  "message": "设备离线"
}
```

#### 2.1.2 处理流程

**1. 检查设备在线状态**:

```python
manager = ConnectionManager.get_instance()
esp32_conn = manager.get_esp32_conn(conn.device_id)

if not esp32_conn or not esp32_conn.websocket:
    await self._send_error(conn, "设备离线", code=ErrorCode.DEVICE_OFFLINE)
    return
```

**2. 记录开锁操作日志**（仅 unlock 命令）:

```python
if command == "unlock":
    db.save_unlock_log(
        device_id=conn.device_id,
        method="remote",
        user_id=0,
        result=True,
        fail_count=0
    )
```

**3. 缓存远程开锁信息**（供 logReportHandler 使用）:

```python
if command == "unlock":
    esp32_conn.last_remote_unlock = {
        "ts": int(time.time() * 1000),
        "app_id": conn.app_id,
        "seq_id": seq_id
    }
```

**有效期**: 30 秒

**用途**: ESP32 上报 `log_report` 时，如果 `method="remote"`，服务器从此缓存提取 `app_id` 填充到 `uid` 字段

#### 2.1.3 重试机制

**转发逻辑**:

```python
async def _forward_with_retry(self, conn, esp32_conn, msg_json) -> bool:
    seq_id = msg_json.get("seq_id")
    max_retries = 3

    for retry in range(max_retries):
        # 发送命令到 ESP32
        await esp32_conn.websocket.send(json.dumps(msg_json))

        # 等待 esp32_ack（2 秒超时）
        ack_received = await self._wait_for_esp32_ack(esp32_conn, seq_id, timeout=2.0)

        if ack_received:
            return True

    # 重试全部失败
    await self._send_error(conn, "设备无响应", code=ErrorCode.TIMEOUT)
    return False
```

**esp32_ack 等待机制**:

```python
async def _wait_for_esp32_ack(self, esp32_conn, seq_id, timeout) -> bool:
    # 创建 Future 对象
    future = asyncio.Future()

    # 注册到 ESP32 连接对象
    esp32_conn._pending_esp32_acks[seq_id] = future

    try:
        # 等待 esp32_ack（带超时）
        result = await asyncio.wait_for(future, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        return False
    finally:
        # 清理 Future
        esp32_conn._pending_esp32_acks.pop(seq_id, None)
```

**Future 触发**:

- ESP32 返回 `esp32_ack` 时，由 `Esp32AckHandler` 触发 Future
- 详见 `core/handle/textHandler/esp32AckHandler.py`

**流程图**:

```
App 发送 lock_control 命令
    ↓
检查设备在线状态
    ↓
离线 → 发送错误响应（code=1）→ 返回
    ↓
在线 → 记录开锁日志（仅 unlock）
    ↓
缓存远程开锁信息（仅 unlock，30秒有效期）
    ↓
转发命令到 ESP32（带重试）
    ├─ 第 1 次发送 → 等待 esp32_ack（2秒）
    ├─ 超时 → 第 2 次发送 → 等待 esp32_ack（2秒）
    ├─ 超时 → 第 3 次发送 → 等待 esp32_ack（2秒）
    └─ 超时 → 发送错误响应（code=10）→ 返回
    ↓
收到 esp32_ack → 成功
    ↓
完成
```

---

### 2.2 设备控制命令代理

**文件**: `core/handle/textHandler/commandProxyHandler.py` - `DevControlProxyHandler`

**支持的目标**:

- `beep`: 蜂鸣器控制
- `light`: 补光灯控制
- `oled`: OLED 显示控制

**消息格式**:

```json
{
  "type": "dev_control",
  "seq_id": "1702234567890_0",
  "target": "light",
  "action": "on",
  "params": {
    "brightness": 80
  }
}
```

**处理逻辑**:

- 与锁控命令类似，使用相同的重试机制
- 检查设备在线 → 转发命令 → 等待 esp32_ack
- 最多重试 3 次，每次超时 2 秒

---

### 2.3 用户管理命令代理

**文件**: `core/handle/textHandler/commandProxyHandler.py` - `UserMgmtProxyHandler`

**协议版本**: v2.4

**支持的类别**:

- `finger`: 指纹管理
- `nfc`: NFC 卡管理
- `password`: 密码管理

#### 2.3.1 消息格式

**请求**（添加用户）:

```json
{
  "type": "user_mgmt",
  "seq_id": "1702234567890_0",
  "category": "finger",
  "command": "add",
  "user_id": 0,
  "user_name": "张三的右手食指"
}
```

**字段说明**:

- `category`: 用户类型（finger/nfc/password）
- `command`: 操作命令（add/del/clear/query/set）
- `user_id`: 用户 ID（add 时为 0 表示自动分配，del 时必填）
- `user_name`: 用户备注名称（可选，v2.4 新增）

**响应**（成功）:

```json
{
  "type": "user_mgmt_result",
  "category": "finger",
  "command": "add",
  "result": true,
  "val": 5,
  "msg": "Success"
}
```

**响应**（失败）:

```json
{
  "type": "user_mgmt_result",
  "category": "finger",
  "command": "add",
  "result": false,
  "val": 7,
  "msg": "Storage full"
}
```

#### 2.3.2 user_name 缓存机制（v2.4 新增）

**处理逻辑**:

```python
# 1. 提取 user_name
user_name = msg_json.get("user_name")

# 2. 缓存到 ESP32 连接对象
if user_name:
    if not hasattr(esp32_conn, "_pending_user_names"):
        esp32_conn._pending_user_names = {}

    esp32_conn._pending_user_names[seq_id] = {
        "user_name": user_name,
        "app_id": conn.app_id,
        "category": msg_json.get("category"),
        "command": msg_json.get("command"),
        "user_id": msg_json.get("user_id")
    }

# 3. 转发时移除 user_name（ESP32 不需要）
msg_json_to_esp32 = msg_json.copy()
msg_json_to_esp32.pop("user_name", None)
```

**缓存结构**:

```python
esp32_conn._pending_user_names = {
    "1702234567890_0": {
        "user_name": "张三的右手食指",
        "app_id": "user_12345",
        "category": "finger",
        "command": "add",
        "user_id": 0
    }
}
```

**缓存用途**:

- ESP32 返回 `user_mgmt_result` 时，从缓存获取 `user_name`
- 由 `UserMgmtResultHandler` 保存到数据库
- 使用 `seq_id` 作为缓存键，避免并发冲突

#### 2.3.3 密码查询特殊处理

**处理逻辑**:

```python
# 密码查询已改为通过 query 接口
if category == "password" and command == "query":
    await self._send_error(
        conn,
        "密码查询请使用 query 接口（target=password）",
        code=ErrorCode.PARAM_ERROR
    )
    return
```

**原因**: 密码存储在服务器数据库，无需查询 ESP32

**正确用法**:

```json
{
  "type": "query",
  "target": "password"
}
```

#### 2.3.4 用户管理结果处理

**文件**: `core/handle/textHandler/userMgmtResultHandler.py` - `UserMgmtResultHandler`

**触发**: ESP32 发送 `user_mgmt_result`

**处理逻辑**:

```python
# 1. 从缓存获取 user_name 和 app_id
seq_id = msg_json.get("seq_id")
pending_info = None
if hasattr(conn, "_pending_user_names") and seq_id:
    pending_info = conn._pending_user_names.pop(seq_id, None)

# 2. 根据操作类型更新数据库
if command == "add" and result:
    # 添加成功，保存到数据库
    user_name = pending_info.get("user_name") if pending_info else None
    app_id = pending_info.get("app_id") if pending_info else None

    db.save_doorlock_user(
        device_id=conn.device_id,
        user_type=category,
        user_id=val,  # ESP32 分配的 ID
        user_name=user_name,
        created_by=app_id
    )

elif command == "del":
    # 删除成功，软删除数据库记录
    user_id = pending_info.get("user_id") if pending_info else msg_json.get("user_id")
    if user_id is not None:
        db.delete_doorlock_user(
            device_id=conn.device_id,
            user_type=category,
            user_id=user_id
        )

elif command == "clear":
    # 清空成功，批量软删除
    count = db.clear_doorlock_users(
        device_id=conn.device_id,
        user_type=category
    )
```

**数据库方法**:

- `save_doorlock_user()`: 保存用户（支持 INSERT/UPDATE）
- `delete_doorlock_user()`: 软删除用户（设置 status=0）
- `clear_doorlock_users()`: 批量软删除

**数据库表结构**（v2.4）:

```sql
CREATE TABLE doorlock_users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    user_type VARCHAR(16) NOT NULL,  -- finger/nfc/password
    user_id INT NOT NULL,             -- ESP32 分配的 ID
    user_name VARCHAR(64),            -- 用户备注
    user_data VARCHAR(255),           -- 额外数据（如 NFC 卡号）
    status TINYINT DEFAULT 1,         -- 0=已删除，1=正常
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(64),           -- 创建者 app_id
    UNIQUE KEY uk_device_type_userid (device_id, user_type, user_id)
)
```

#### 2.3.5 用户管理流程图

**添加用户流程**:

```
App 发送 user_mgmt (command=add, user_name="张三")
    ↓
服务器缓存 user_name 到 ESP32 连接对象
    ├─ 使用 seq_id 作为缓存键
    └─ 存储 user_name, app_id, category, command, user_id
    ↓
移除 user_name 字段（ESP32 不需要）
    ↓
转发命令到 ESP32（带重试机制）
    ├─ 最多重试 3 次
    └─ 每次等待 esp32_ack（2 秒超时）
    ↓
ESP32 执行添加操作
    ├─ 分配 user_id（如 5）
    └─ 返回 user_mgmt_result (result=true, val=5)
    ↓
服务器处理结果
    ├─ 从缓存获取 user_name 和 app_id
    ├─ 保存到数据库（device_id, user_type, user_id, user_name, created_by）
    └─ 清理缓存
    ↓
转发结果给 App
    ↓
完成
```

**删除用户流程**:

```
App 发送 user_mgmt (command=del, user_id=5)
    ↓
转发命令到 ESP32
    ↓
ESP32 执行删除操作
    └─ 返回 user_mgmt_result (result=true)
    ↓
服务器处理结果
    ├─ 软删除数据库记录（UPDATE status=0）
    └─ 保留历史记录
    ↓
转发结果给 App
    ↓
完成
```

**清空用户流程**:

```
App 发送 user_mgmt (command=clear, category=finger)
    ↓
转发命令到 ESP32
    ↓
ESP32 执行清空操作
    └─ 返回 user_mgmt_result (result=true)
    ↓
服务器处理结果
    ├─ 批量软删除数据库记录（UPDATE status=0）
    └─ 返回影响行数
    ↓
转发结果给 App
    ↓
完成
```

---

### 2.4 人脸管理命令处理

**文件**: `core/handle/textHandler/faceRecognitionHandler.py` - `FaceManagementHandler`

**协议版本**: v2.4

**说明**: 处理 App 发起的人脸管理请求，包括人脸录入、人员管理、权限管理和到访记录查询。

#### 2.4.1 支持的操作

| 操作                | 说明         | 数据源 |
| ------------------- | ------------ | ------ |
| `register`          | 人脸录入     | 数据库 |
| `get_persons`       | 获取人员列表 | 数据库 |
| `get_person`        | 获取人员详情 | 数据库 |
| `delete_person`     | 删除人员     | 数据库 |
| `update_permission` | 更新权限     | 数据库 |
| `get_visits`        | 获取到访记录 | 数据库 |

#### 2.4.2 人脸录入 (register)

**请求**:

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

**字段说明**:

- `name`: 人员姓名
- `relation_type`: 关系类型（family/friend/guest/other）
- `images`: base64 编码的 JPEG 图像数组（至少 1 张，建议 3-5 张）
- `permission`: 权限配置
  - `permission_type`: 权限类型（permanent/temporary/time_restricted）
  - `time_start`: 允许时间段开始（可选）
  - `time_end`: 允许时间段结束（可选）
  - `valid_from`: 有效期开始日期（temporary 类型必填）
  - `valid_until`: 有效期结束日期（temporary 类型必填）
  - `remaining_count`: 剩余次数（temporary 类型可选）

**处理逻辑**:

```python
# 1. 解码图像数据
images = []
for img_b64 in images_b64:
    images.append(base64.b64decode(img_b64))

# 2. 调用 FaceService 录入人脸
person_id, error = face_service.register_face(
    name=name,
    relation_type=relation_type,
    images=images,
    permission=permission
)

# 3. 返回结果
if error:
    return {"status": "error", "error": error}
else:
    return {"status": "success", "person_id": person_id}
```

**响应（成功）**:

```json
{
  "type": "face_management",
  "action": "register",
  "status": "success",
  "person_id": 5
}
```

**响应（失败）**:

```json
{
  "type": "face_management",
  "action": "register",
  "status": "error",
  "error": "invalid_images"
}
```

#### 2.4.3 获取人员列表 (get_persons)

**请求**:

```json
{
  "type": "face_management",
  "seq_id": "1702234567890_010",
  "action": "get_persons"
}
```

**响应**:

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
      "created_at": "2024-12-11T10:00:00",
      "permission": {
        "permission_type": "permanent"
      }
    },
    {
      "id": 2,
      "name": "李四",
      "relation_type": "friend",
      "created_at": "2024-12-11T11:00:00",
      "permission": {
        "permission_type": "temporary",
        "valid_from": "2024-12-11",
        "valid_until": "2024-12-31",
        "remaining_count": 10
      }
    }
  ]
}
```

#### 2.4.4 获取人员详情 (get_person)

**请求**:

```json
{
  "type": "face_management",
  "seq_id": "1702234567890_011",
  "action": "get_person",
  "data": {
    "person_id": 5
  }
}
```

**响应**:

```json
{
  "type": "face_management",
  "action": "get_person",
  "status": "success",
  "data": {
    "id": 5,
    "name": "张三",
    "relation_type": "family",
    "created_at": "2024-12-11T10:00:00",
    "permission": {
      "permission_type": "permanent",
      "time_start": "08:00:00",
      "time_end": "22:00:00"
    },
    "face_count": 3
  }
}
```

#### 2.4.5 删除人员 (delete_person)

**请求**:

```json
{
  "type": "face_management",
  "seq_id": "1702234567890_012",
  "action": "delete_person",
  "data": {
    "person_id": 5
  }
}
```

**响应（成功）**:

```json
{
  "type": "face_management",
  "action": "delete_person",
  "status": "success"
}
```

**响应（失败）**:

```json
{
  "type": "face_management",
  "action": "delete_person",
  "status": "error",
  "error": "person_not_found"
}
```

#### 2.4.6 更新权限 (update_permission)

**请求**:

```json
{
  "type": "face_management",
  "seq_id": "1702234567890_013",
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

**响应（成功）**:

```json
{
  "type": "face_management",
  "action": "update_permission",
  "status": "success"
}
```

#### 2.4.7 获取到访记录 (get_visits)

**请求**:

```json
{
  "type": "face_management",
  "seq_id": "1702234567890_014",
  "action": "get_visits",
  "data": {
    "page": 1,
    "page_size": 20,
    "date_from": "2024-12-01",
    "date_to": "2024-12-11"
  }
}
```

**参数说明**:

- `page`: 页码（从 1 开始）
- `page_size`: 每页数量（默认 20，最大 100）
- `date_from`: 开始日期（可选，格式 YYYY-MM-DD）
- `date_to`: 结束日期（可选，格式 YYYY-MM-DD）

**响应**:

```json
{
  "type": "face_management",
  "action": "get_visits",
  "status": "success",
  "data": {
    "records": [
      {
        "id": 123,
        "person_id": 5,
        "person_name": "张三",
        "relation_type": "family",
        "result": "known",
        "access_granted": true,
        "image_path": "faces/AA:BB:CC:DD:EE:FF/2024-12-11/face_1702234567890_5.jpg",
        "created_at": "2024-12-11T10:30:00"
      },
      {
        "id": 124,
        "person_id": null,
        "person_name": "陌生人",
        "relation_type": null,
        "result": "unknown",
        "access_granted": false,
        "image_path": "faces/AA:BB:CC:DD:EE:FF/2024-12-11/face_1702234567891_0.jpg",
        "created_at": "2024-12-11T10:35:00"
      }
    ],
    "total": 2,
    "page": 1,
    "page_size": 20
  }
}
```

#### 2.4.8 人脸管理流程图

**人脸录入流程**:

```
App 发送 face_management (action=register)
    ↓
服务器解码图像数据（base64 → JPEG）
    ↓
调用 FaceService.register_face()
    ├─ 提取人脸特征
    ├─ 保存到数据库
    └─ 保存人脸图像到文件系统
    ↓
返回 person_id
    ↓
发送成功响应给 App
    ↓
完成
```

**获取到访记录流程**:

```
App 发送 face_management (action=get_visits)
    ↓
服务器查询数据库
    ├─ 按日期范围过滤
    ├─ 分页查询
    └─ 关联人员信息
    ↓
返回到访记录列表
    ↓
发送响应给 App
    ↓
完成
```

---

### 2.5 系统命令处理

**文件**: `core/handle/textHandler/systemMessageHandler.py` - `SystemTextMessageHandler`

**协议版本**: v2.4

**说明**: 处理系统级命令，如启动/停止监控模式。

#### 2.5.1 支持的命令

| 命令            | 说明         | 参数                   |
| --------------- | ------------ | ---------------------- |
| `start_monitor` | 启动监控模式 | `record`: 是否启用录像 |
| `stop_monitor`  | 停止监控模式 | 无                     |

#### 2.5.2 启动监控模式 (start_monitor)

**请求**:

```json
{
  "type": "system",
  "seq_id": "1702234567890_015",
  "command": "start_monitor",
  "record": false
}
```

**参数说明**:

- `record`: 是否启用录像保存（默认 true）

**处理逻辑**:

```python
# 1. 判断连接类型
if conn.client_type == "app":
    # App 发起的命令，需要切换 ESP32 的模式
    esp32_conn = manager.get_esp32_conn(conn.device_id)
    if esp32_conn:
        # 设置 ESP32 为监控模式
        esp32_conn.current_mode = "monitor"

        # 启动录像（如果启用）
        if enable_recording:
            esp32_conn.video_recorder.start_recording(conn.device_id)

        # 停止 TTS 音频发送
        if hasattr(esp32_conn, "tts") and esp32_conn.tts:
            # 清空 TTS 队列
            while not esp32_conn.tts.tts_audio_queue.empty():
                esp32_conn.tts.tts_audio_queue.get_nowait()

        # 通知 ESP32 进入监控模式
        await esp32_conn.websocket.send(
            json.dumps({"type": "system", "command": "start_monitor"})
        )
```

**响应（成功）**:

```json
{
  "type": "system",
  "status": "success",
  "command": "start_monitor",
  "recording": false
}
```

**响应（失败）**:

```json
{
  "type": "system",
  "status": "error",
  "message": "ESP32 连接不可用"
}
```

#### 2.5.3 停止监控模式 (stop_monitor)

**请求**:

```json
{
  "type": "system",
  "seq_id": "1702234567890_016",
  "command": "stop_monitor"
}
```

**处理逻辑**:

```python
# 1. 判断连接类型
if conn.client_type == "app":
    # App 发起的命令，需要切换 ESP32 的模式
    esp32_conn = manager.get_esp32_conn(conn.device_id)
    if esp32_conn:
        # 设置 ESP32 为正常模式
        esp32_conn.current_mode = "normal"

        # 停止录像（如果正在录制）
        if esp32_conn.video_recorder.is_recording(conn.device_id):
            esp32_conn.video_recorder.stop_recording(conn.device_id)

        # 通知 ESP32 退出监控模式
        await esp32_conn.websocket.send(
            json.dumps({"type": "system", "command": "stop_monitor"})
        )
```

**响应（成功）**:

```json
{
  "type": "system",
  "status": "success",
  "command": "stop_monitor"
}
```

#### 2.5.4 监控模式流程图

**启动监控模式流程**:

```
App 发送 system (command=start_monitor, record=false)
    ↓
服务器获取 ESP32 连接
    ↓
ESP32 不在线 → 发送错误响应 → 返回
    ↓
ESP32 在线 → 设置 ESP32 为监控模式
    ├─ esp32_conn.current_mode = "monitor"
    ├─ 启动录像（如果 record=true）
    └─ 清空 TTS 队列
    ↓
通知 ESP32 进入监控模式
    ↓
发送成功响应给 App
    ↓
ESP32 开始推送音视频流
    ├─ 视频帧（JPEG）→ 服务器 → App
    └─ 音频帧（OPUS）→ 服务器解码 → App（PCM）
    ↓
完成
```

**停止监控模式流程**:

```
App 发送 system (command=stop_monitor)
    ↓
服务器获取 ESP32 连接
    ↓
设置 ESP32 为正常模式
    ├─ esp32_conn.current_mode = "normal"
    └─ 停止录像（如果正在录制）
    ↓
通知 ESP32 退出监控模式
    ↓
发送成功响应给 App
    ↓
ESP32 停止推送音视频流
    ↓
完成
```

---

## 3. 数据查询处理

**文件**: `core/handle/textHandler/queryHandler.py` - `QueryHandler`

**协议版本**: v2.2

### 3.1 查询目标

| 目标             | 说明         | 数据源              |
| ---------------- | ------------ | ------------------- |
| `status`         | 当前设备状态 | 内存缓存 / 数据库   |
| `status_history` | 历史状态     | 数据库              |
| `events`         | 事件历史     | 数据库              |
| `unlock_logs`    | 开锁日志     | 数据库              |
| `media_files`    | 媒体文件列表 | 数据库              |
| `password`       | 设备密码     | 数据库              |
| `doorlock_users` | 门锁用户列表 | 数据库（v2.4 新增） |

### 3.2 当前状态查询

**请求**:

```json
{
  "type": "query",
  "target": "status"
}
```

**处理逻辑**:

```python
# 1. 优先从内存缓存读取（ESP32 连接对象）
esp32_conn = manager.get_esp32_conn(conn.device_id)
if esp32_conn and hasattr(esp32_conn, "device_status"):
    status = esp32_conn.device_status
    # 返回缓存的状态

# 2. 缓存不存在，从数据库读取最新状态
else:
    status = db.get_latest_status(conn.device_id)
```

**响应**:

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

### 3.3 历史数据查询

**请求**（以历史状态为例）:

```json
{
  "type": "query",
  "target": "status_history",
  "data": {
    "limit": 100,
    "offset": 0
  }
}
```

**处理逻辑**:

```python
# 1. 提取分页参数
limit = min(data.get("limit", 100), 500)  # 最大 500 条
offset = data.get("offset", 0)

# 2. 查询数据库
records, total = db.get_status_history(
    device_id=conn.device_id,
    limit=limit,
    offset=offset
)

# 3. 返回结果（含分页信息）
```

**响应**:

```json
{
  "type": "query_result",
  "target": "status_history",
  "status": "success",
  "data": {
    "records": [...],
    "total": 1234,
    "limit": 100,
    "offset": 0
  }
}
```

### 3.4 密码查询

**请求**:

```json
{
  "type": "query",
  "target": "password"
}
```

**处理逻辑**:

```python
# 从数据库获取密码
password = db.get_device_password(conn.device_id)

if password:
    # 返回实际密码
    return {"password": password}
else:
    # 返回默认密码
    return {"password": "123456"}
```

**响应**:

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

**注意**: 密码存储在服务器数据库，不需要查询 ESP32

### 3.5 门锁用户查询（v2.4 新增）

**请求**:

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

**参数说明**:

- `user_type`: 用户类型过滤（可选）
  - `finger`: 指纹用户
  - `nfc`: NFC 卡用户
  - `password`: 密码用户
  - 不填则查询所有类型
- `limit`: 每页数量（默认 100，最大 500）
- `offset`: 偏移量（默认 0）

**处理逻辑**:

```python
# 1. 提取查询参数
user_type = data.get("user_type")  # 可选
limit = min(data.get("limit", 100), 500)
offset = data.get("offset", 0)

# 2. 查询数据库
records, total = db.query_doorlock_users(
    device_id=conn.device_id,
    user_type=user_type,
    limit=limit,
    offset=offset
)

# 3. 返回结果（含分页信息）
```

**响应**:

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
        "created_at": "2024-12-11 10:30:00",
        "updated_at": "2024-12-11 10:30:00",
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
        "created_at": "2024-12-11 11:00:00",
        "updated_at": "2024-12-11 11:00:00",
        "created_by": "user_12345"
      }
    ],
    "total": 2,
    "limit": 100,
    "offset": 0
  }
}
```

**字段说明**:

- `id`: 数据库记录 ID
- `device_id`: 设备 ID
- `user_type`: 用户类型（finger/nfc/password）
- `user_id`: ESP32 分配的用户 ID（指纹/NFC 的槽位 ID）
- `user_name`: 用户备注名称
- `user_data`: 额外数据（如 NFC 卡号）
- `status`: 状态（0=已删除，1=正常）
- `created_at`: 创建时间
- `updated_at`: 更新时间
- `created_by`: 创建者 app_id

**使用说明**:

- 用户数据存储在服务器数据库，不需要查询 ESP32
- 通过 `user_mgmt` 命令添加用户时，如果提供了 `user_name`，会自动保存到数据库
- 查询结果只返回 `status=1` 的记录（未删除的用户）
- 删除用户时会软删除（status=0），不会物理删除记录
- 清空用户时会批量软删除所有该类型的用户

**查询示例**:

1. **查询所有用户**:

```json
{
  "type": "query",
  "target": "doorlock_users",
  "data": {}
}
```

2. **查询指纹用户**:

```json
{
  "type": "query",
  "target": "doorlock_users",
  "data": {
    "user_type": "finger"
  }
}
```

3. **分页查询**:

```json
{
  "type": "query",
  "target": "doorlock_users",
  "data": {
    "limit": 20,
    "offset": 40
  }
}
```

---

## 4. 媒体文件下载

**文件**: `core/handle/textHandler/mediaDownloadHandler.py`

**协议版本**: v2.2

### 4.1 完整文件下载

**适用场景**: 文件小于 50MB

**请求**:

```json
{
  "type": "media_download",
  "file_id": 123
}
```

或

```json
{
  "type": "media_download",
  "file_path": "face/2024/01/image_001.jpg"
}
```

**处理逻辑**:

```python
# 1. 如果提供 file_id，从数据库查询文件路径
if file_id:
    file_info = db.get_media_file_by_id(file_id)
    file_path = file_info.get("file_path")

# 2. 构建完整路径
full_path = os.path.join(MEDIA_ROOT, file_path)

# 3. 安全检查（防止路径遍历攻击）
real_path = os.path.realpath(full_path)
real_root = os.path.realpath(MEDIA_ROOT)
if not real_path.startswith(real_root):
    return error("access_denied")

# 4. 检查文件大小
file_size = os.path.getsize(full_path)
if file_size > MAX_DOWNLOAD_SIZE:
    return error("file_too_large")

# 5. 读取并编码文件
with open(full_path, "rb") as f:
    content = base64.b64encode(f.read()).decode()
```

**响应**:

```json
{
  "type": "media_download",
  "status": "success",
  "data": {
    "file_id": 123,
    "file_type": "face",
    "file_name": "image_001.jpg",
    "file_size": 102400,
    "mime_type": "image/jpeg",
    "content": "base64_encoded_data..."
  }
}
```

---

### 4.2 分片下载

**适用场景**: 文件大于 50MB

**请求**:

```json
{
  "type": "media_download_chunk",
  "file_id": 456,
  "chunk_index": 0,
  "chunk_size": 1048576
}
```

**参数**:

- `chunk_index`: 分片索引（从 0 开始）
- `chunk_size`: 分片大小（默认 1MB，最大 5MB）

**处理逻辑**:

```python
# 1. 计算分片信息
file_size = os.path.getsize(full_path)
total_chunks = math.ceil(file_size / chunk_size)

# 2. 读取指定分片
offset = chunk_index * chunk_size
actual_chunk_size = min(chunk_size, file_size - offset)

with open(full_path, "rb") as f:
    f.seek(offset)
    chunk_data = f.read(actual_chunk_size)

# 3. 编码并返回
content = base64.b64encode(chunk_data).decode()
```

**响应**:

```json
{
  "type": "media_download_chunk",
  "status": "success",
  "data": {
    "file_id": 456,
    "chunk_index": 0,
    "total_chunks": 10,
    "file_size": 10485760,
    "chunk_size": 1048576,
    "content": "base64_encoded_chunk_data..."
  }
}
```

**下载流程**:

```
App 请求第 0 片
    ↓
服务器返回第 0 片（含 total_chunks=10）
    ↓
App 请求第 1 片
    ↓
服务器返回第 1 片
    ↓
...
    ↓
App 请求第 9 片
    ↓
服务器返回第 9 片
    ↓
App 合并所有分片
    ↓
完成
```

---

## 5. 实时数据推送

### 5.1 推送机制概述

**触发条件**:

- ESP32 上报状态/事件/日志
- 设备状态变化
- 人脸识别结果
- 监控模式数据

**推送目标**:

- 通过 `ConnectionManager` 获取所有关联的 App 连接
- 遍历发送给每个 App

**代码模式**:

```python
# 获取关联的 App 连接
manager = ConnectionManager.get_instance()
app_conns = manager.get_app_conns(device_id)

# 遍历推送
for app_conn in app_conns:
    if app_conn.websocket:
        await app_conn.websocket.send(json.dumps(message))
```

---

### 5.2 状态上报推送

**文件**: `core/handle/textHandler/statusReportHandler.py`

**触发**: ESP32 发送 `status_report`

**推送消息**（原样转发）:

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

**处理流程**:

```
ESP32 发送 status_report
    ↓
服务器处理（更新缓存、数据库）
    ↓
获取关联的 App 连接
    ↓
遍历推送给所有 App（原样转发）
    ↓
完成
```

---

### 5.3 事件上报推送

**文件**: `core/handle/textHandler/eventReportHandler.py`

**触发**: ESP32 发送 `event_report`

**推送消息**（原样转发）:

```json
{
  "type": "event_report",
  "ts": 1702234567890,
  "event": "bell",
  "param": 1
}
```

**支持的事件**:

- `bell`: 门铃按下
- `pir_trigger`: PIR 人体检测
- `tamper`: 撬锁报警
- `door_open`: 门未关超时
- `low_battery`: 低电量警告
- `door_closed`: 门已关闭
- `lock_success`: 上锁成功
- `bolt_alarm`: 反锁报警

---

### 5.4 开锁日志推送

**文件**: `core/handle/textHandler/logReportHandler.py`

**触发**: ESP32 发送 `log_report`

**推送消息**（含服务器填充的 uid）:

```json
{
  "type": "log_report",
  "ts": 1702234567890,
  "data": {
    "method": "remote",
    "uid": 12345,
    "status": "success",
    "lock_time": 0,
    "fail_count": 0
  }
}
```

**uid 填充逻辑**:

- **人脸开锁**: 从 `conn.last_face_result` 获取（30 秒有效期）
- **远程开锁**: 从 `conn.last_remote_unlock` 获取（30 秒有效期）
- **其他方式**: 使用 ESP32 上传的 uid

**注意**: 推送给 App 的消息已包含服务器填充的 uid

---

### 5.5 人脸识别通知推送

**文件**: `core/connection.py` - `_handle_face_recognition_binary` 方法

**触发**: ESP32 发送人脸图像，服务器识别完成

**推送消息**:

```json
{
  "type": "visit_notification",
  "ts": 1702234567890,
  "data": {
    "visit_id": 789,
    "person_id": 5,
    "person_name": "张三",
    "relation": "family",
    "result": "known",
    "access_granted": true,
    "image": "base64_encoded_jpeg...",
    "image_path": null
  }
}
```

**字段说明**:

- `visit_id`: 到访记录 ID
- `person_id`: 人员 ID（陌生人为 null）
- `person_name`: 人员姓名
- `relation`: 关系类型（family/friend/guest/stranger）
- `result`: 识别结果（known/unknown/no_face/error）
- `access_granted`: 是否授权开门
- `image`: base64 编码的 JPEG 图像
- `image_path`: 图像存储路径（可选）

**处理流程**:

```
ESP32 发送人脸图像（BinaryProtocol2）
    ↓
服务器执行人脸识别
    ↓
检查权限
    ↓
生成问候语
    ↓
保存到访记录
    ↓
发送 face_result 给 ESP32
    ↓
播放 TTS 问候语（如果有）
    ↓
推送 visit_notification 给所有 App
    ↓
完成
```

---

### 5.6 监控模式数据推送

**文件**: `core/connection.py` - `_forward_to_apps` 方法

**触发**: ESP32 发送监控数据（音频/视频帧）

#### 5.6.1 视频帧推送

**数据格式**: BinaryProtocol2（reserved ≠ 0）

**处理逻辑**:

```python
# 直接转发完整的 BinaryProtocol2 帧
for app_conn in app_conns:
    if app_conn.websocket:
        await app_conn.websocket.send(data)
```

**帧结构**:

```
[16 字节头部] + [JPEG 图像数据]

头部:
- version (2 bytes): 协议版本
- type (2 bytes): 消息类型
- reserved (4 bytes): 分辨率（width << 16 | height）
- timestamp (4 bytes): 时间戳
- payload_size (4 bytes): JPEG 大小
```

**App 端处理**:

- 解析头部提取分辨率
- 提取 JPEG 数据
- 显示视频画面

#### 5.6.2 音频帧推送

**数据格式**: BinaryProtocol2（reserved = 0）

**处理逻辑**:

```python
# 1. 提取 Opus payload
opus_payload = data[16:16 + payload_size]

# 2. 初始化 Opus 解码器（延迟初始化）
if not hasattr(self, "_opus_decoder_for_app"):
    self._opus_decoder_for_app = opuslib_next.Decoder(16000, 1)
    self._opus_decode_error_count = 0
    self._opus_decode_last_error_time = 0

# 3. 解码为 PCM (16kHz, 单声道, 960 采样点)
try:
    pcm_data = self._opus_decoder_for_app.decode(opus_payload, 960)
except opuslib_next.OpusError as e:
    # 错误处理机制
    self._opus_decode_error_count += 1

    # 限制日志频率（每 5 秒或每 100 次错误打印一次）
    if (current_time - self._opus_decode_last_error_time > 5.0 or
        self._opus_decode_error_count % 100 == 0):
        logger.warning(f"Opus 解码失败: {e}")
        self._opus_decode_last_error_time = current_time

    # 累计错误 > 10 次时重置解码器
    if self._opus_decode_error_count > 10:
        logger.warning("重置 Opus 解码器")
        self._opus_decoder_for_app = opuslib_next.Decoder(16000, 1)
        self._opus_decode_error_count = 0

    return

# 4. 广播给所有 App
for app_conn in app_conns:
    if app_conn.websocket:
        await app_conn.websocket.send(pcm_data)
```

**音频格式**:

- 编码: 16-bit PCM
- 采样率: 16kHz
- 声道: 单声道
- 帧长: 960 采样点（60ms）

**错误处理机制**:

- 限制日志频率，避免日志洪水
- 累计错误超过阈值时自动重置解码器
- 解码失败不中断流程，继续处理后续帧

**流程图**:

```
ESP32 发送监控数据（BinaryProtocol2）
    ↓
获取关联的 App 连接
    ↓
无 App → 返回
    ↓
有 App → 解析头部
    ↓
区分音频/视频帧（reserved）
    ↓
    ├─────────────────┬─────────────────┐
    ↓                 ↓                 ↓
视频帧            音频帧
    ↓                 ↓
直接转发          提取 Opus payload
    ↓                 ↓
遍历发送          初始化解码器（延迟）
    ↓                 ↓
完成              解码为 PCM
                      ↓
                  错误处理（限流、重置）
                      ↓
                  遍历发送
                      ↓
                  完成
```

---

### 5.7 设备状态变化推送

**触发**: ESP32 状态变化时

**推送消息**:

```json
{
  "type": "device_state_update",
  "ts": 1702234567890,
  "device_id": "ESP32_AABBCC",
  "state": {
    "light": {
      "state": "on",
      "brightness": 80
    }
  }
}
```

**更新机制**:

```python
# ESP32 连接对象维护设备状态
conn.device_state = {
    "light": {...},
    "door": {...},
    "sensor": {...}
}

# 状态变化时调用
conn.update_device_state("light", {"state": "on", "brightness": 80})

# 自动推送给所有 App
```

---

## 6. 总结

### 6.1 核心处理流程

```
App 连接 WebSocket
    ↓
Hello 认证（10 秒超时）
    ├─ 验证 client_type, device_id, app_id
    └─ 注册到 ConnectionManager
    ↓
推送初始设备状态
    ├─ 设备在线/离线通知
    └─ 完整设备状态（如果在线）
    ↓
开始处理消息
    ├─ 文本消息 → seq_id 防重放 → Handler 分发
    │   ├─ 锁控命令 → LockControlProxyHandler
    │   ├─ 设备控制 → DevControlProxyHandler
    │   ├─ 用户管理 → UserMgmtProxyHandler
    │   ├─ 系统命令 → SystemTextMessageHandler
    │   ├─ 人脸管理 → FaceManagementHandler
    │   ├─ 数据查询 → QueryHandler
    │   └─ 媒体下载 → MediaDownloadHandler
    └─ 二进制消息 → PCM 编码为 OPUS → 转发给 ESP32
    ↓
接收 ESP32 推送
    ├─ 状态上报 → 转发给所有 App
    ├─ 事件上报 → 转发给所有 App
    ├─ 开锁日志 → 填充 uid → 转发给所有 App
    ├─ 人脸识别 → 推送到访通知给所有 App
    └─ 监控数据 → 解码/转发给所有 App
```

### 6.2 关键技术点

#### 6.2.1 防重放机制

- 使用 `SeqIdCache` 类级别共享缓存
- 按 `app_id` 分组存储 `seq_id`
- FIFO 淘汰策略（最大 100 条）
- 重复消息返回 `server_ack` (code=9)

#### 6.2.2 命令重试机制

- 最多重试 3 次
- 每次等待 `esp32_ack` 超时 2 秒
- 使用 `asyncio.Future` 实现异步等待
- 重试失败返回错误（code=10）

#### 6.2.3 音频编解码

**App → ESP32**:

- 接收: 16-bit PCM (24kHz, 单声道)
- 编码: OPUS (24kHz, 单声道, 60ms)
- 转发: OPUS 数据包

**ESP32 → App**:

- 接收: OPUS (16kHz, 单声道, 60ms)
- 解码: 16-bit PCM (16kHz, 单声道, 960 采样点)
- 转发: PCM 数据

#### 6.2.4 数据推送

- 通过 `ConnectionManager` 管理连接
- 支持一个设备多个 App 同时连接
- 遍历推送给所有关联的 App
- 推送失败不影响其他 App

#### 6.2.5 人脸管理

- 人脸数据存储在服务器数据库
- 支持人脸录入、人员管理、权限管理
- 到访记录包含人脸图片（base64 编码）
- 支持分页查询到访记录

#### 6.2.6 监控模式

- 支持启动/停止监控模式
- 可选启用录像保存
- 监控模式下停止 TTS 音频发送
- 实时推送音视频流给 App

### 6.3 错误码规范（v2.4）

#### server_ack 错误码（简化版）

server_ack 只用于接收确认，使用简化的错误码：

| code | 含义     | 使用场景                          |
| ---- | -------- | --------------------------------- |
| 0    | 成功     | 消息已接收，将转发给 ESP32 或处理 |
| 3    | 参数错误 | 消息格式错误、缺少必填字段        |
| 8    | 未认证   | App 未完成 hello 认证             |
| 9    | 重复消息 | seq_id 重复（防重放）             |

#### 业务响应错误码（完整版）

业务响应（如 lock_control、dev_control 的 error 响应）使用完整的 0-10 错误码：

| code | 含义     | 使用场景              |
| ---- | -------- | --------------------- |
| 0    | 成功     | 操作成功完成          |
| 1    | 设备离线 | ESP32 未连接服务器    |
| 2    | 设备忙   | 正在执行其他操作      |
| 3    | 参数错误 | 命令格式或参数无效    |
| 4    | 不支持   | 不支持的命令或操作    |
| 5    | 超时     | 等待响应超时          |
| 6    | 硬件故障 | 硬件异常或不可用      |
| 7    | 资源已满 | 指纹/NFC 存储已满     |
| 8    | 未认证   | 用户未登录或权限不足  |
| 9    | 重复消息 | seq_id 重复（防重放） |
| 10   | 内部错误 | 未知内部异常          |

### 6.4 文件路径

**核心文件**:

| 文件                                                | 功能           |
| --------------------------------------------------- | -------------- |
| `core/app_connection.py`                            | App 连接处理器 |
| `core/connection_manager.py`                        | 连接管理器     |
| `core/handle/textMessageProcessor.py`               | 消息处理器主类 |
| `core/handle/textMessageHandlerRegistry.py`         | Handler 注册表 |
| `core/handle/textHandler/queryHandler.py`           | 数据查询处理器 |
| `core/handle/textHandler/commandProxyHandler.py`    | 命令代理处理器 |
| `core/handle/textHandler/mediaDownloadHandler.py`   | 媒体下载处理器 |
| `core/handle/textHandler/systemMessageHandler.py`   | 系统命令处理器 |
| `core/handle/textHandler/faceRecognitionHandler.py` | 人脸管理处理器 |
| `core/utils/seq_id_cache.py`                        | seq_id 缓存    |
| `core/constants/error_codes.py`                     | 错误码定义     |
| `core/providers/doorlock/database.py`               | 数据库操作     |
| `core/providers/doorlock/face_service.py`           | 人脸服务       |

### 6.5 协议版本

**App 协议**: v2.4

**主要特性**:

- 支持 `app_id` 身份标识
- 支持 `seq_id` 防重放机制
- 支持 `server_ack` 消息确认（简化错误码 0/3/8/9）
- 支持命令重试机制（等待 `esp32_ack`）
- 支持数据查询接口
- 支持媒体文件下载（完整/分片）
- 支持实时数据推送
- 支持人脸管理功能（v2.4 新增）
- 支持系统命令（监控模式）（v2.4 新增）
- 支持门锁用户管理（v2.4 新增）
- 统一错误码体系（0-10）

**ESP32 协议**: v5.2

**交互关系**:

- App 命令通过服务器转发给 ESP32
- ESP32 数据通过服务器推送给 App
- 服务器负责协议转换和数据增强（如填充 uid）

### 6.6 功能完整性

根据协议文档和代码实现，以下功能已全部实现：

**✅ 已实现的功能**:

1. **连接认证与管理**
   - Hello 认证机制
   - seq_id 防重放机制
   - server_ack 消息确认
   - 设备上下线通知

2. **命令代理处理**
   - 锁控命令代理（开锁/关锁/临时密码）
   - 设备控制代理（蜂鸣器/补光灯/OLED）
   - 用户管理代理（指纹/NFC/密码）
   - 命令重试机制（等待 esp32_ack）

3. **数据查询处理**
   - 当前状态查询
   - 历史状态查询
   - 事件历史查询
   - 开锁日志查询
   - 媒体文件列表查询
   - 设备密码查询
   - 门锁用户查询（v2.4 新增）

4. **媒体文件下载**
   - 完整文件下载（< 50MB）
   - 分片下载（> 50MB）
   - 路径遍历防护

5. **实时数据推送**
   - 状态上报推送
   - 事件上报推送
   - 开锁日志推送（含 uid 填充）
   - 到访通知推送（含人脸图片）
   - 监控模式音视频流推送

6. **人脸管理功能**（v2.4 新增）
   - 人脸录入
   - 获取人员列表
   - 获取人员详情
   - 删除人员
   - 更新权限
   - 获取到访记录

7. **系统命令功能**（v2.4 新增）
   - 启动监控模式
   - 停止监控模式
   - 录像控制

8. **门锁用户管理**（v2.4 新增）
   - user_name 缓存机制
   - 用户数据库存储
   - 软删除机制
   - 分页查询

**📝 未实现的功能**:

- 无（所有协议定义的功能均已实现）

---p_id` 身份标识

- 支持 `seq_id` 防重放机制
- 支持 `server_ack` 消息确认（简化错误码 0/3/8/9）
- 支持命令重试机制（等待 `esp32_ack`）
- 支持数据查询接口
- 支持媒体文件下载（完整/分片）
- 支持实时数据推送
- 统一错误码体系（0-10）

**ESP32 协议**: v5.2

**交互关系**:

- App 命令通过服务器转发给 ESP32
- ESP32 数据通过服务器推送给 App
- 服务器负责协议转换和数据增强（如填充 uid）

---

## 附录

### A. 消息类型速查表

| 消息类型               | 方向         | 说明                 |
| ---------------------- | ------------ | -------------------- |
| `hello`                | App → 服务器 | 认证消息             |
| `server_ack`           | 服务器 → App | 消息确认             |
| `lock_control`         | App ⇄ ESP32  | 锁控命令             |
| `dev_control`          | App ⇄ ESP32  | 设备控制             |
| `user_mgmt`            | App ⇄ ESP32  | 用户管理             |
| `user_mgmt_result`     | ESP32 → App  | 用户管理结果（v2.4） |
| `system`               | App ⇄ ESP32  | 系统命令（v2.4）     |
| `face_management`      | App → 服务器 | 人脸管理（v2.4）     |
| `query`                | App → 服务器 | 数据查询             |
| `query_result`         | 服务器 → App | 查询结果             |
| `media_download`       | App → 服务器 | 媒体下载             |
| `media_download_chunk` | App → 服务器 | 分片下载             |
| `status_report`        | ESP32 → App  | 状态上报             |
| `event_report`         | ESP32 → App  | 事件上报             |
| `log_report`           | ESP32 → App  | 开锁日志             |
| `visit_notification`   | 服务器 → App | 到访通知             |
| `device_status`        | 服务器 → App | 设备在线/离线        |
| `device_state_full`    | 服务器 → App | 完整设备状态         |
| `device_state_update`  | 服务器 → App | 状态变化             |

### B. Handler 注册表

**App 协议相关 Handler**:

| Handler                     | 消息类型               | 功能         |
| --------------------------- | ---------------------- | ------------ |
| `QueryHandler`              | `query`                | 数据查询     |
| `MediaDownloadHandler`      | `media_download`       | 完整文件下载 |
| `MediaDownloadChunkHandler` | `media_download_chunk` | 分片下载     |
| `LockControlProxyHandler`   | `lock_control`         | 锁控命令代理 |
| `DevControlProxyHandler`    | `dev_control`          | 设备控制代理 |
| `UserMgmtProxyHandler`      | `user_mgmt`            | 用户管理代理 |
| `SystemTextMessageHandler`  | `system`               | 系统命令     |
| `FaceManagementHandler`     | `face_management`      | 人脸管理     |

**ESP32 协议相关 Handler**:

| Handler                   | 消息类型             | 功能         |
| ------------------------- | -------------------- | ------------ |
| `StatusReportHandler`     | `status_report`      | 状态上报     |
| `EventReportHandler`      | `event_report`       | 事件上报     |
| `LogReportHandler`        | `log_report`         | 开锁日志     |
| `DoorOpenedReportHandler` | `door_opened_report` | 开门日志     |
| `PasswordReportHandler`   | `password_report`    | 密码上报     |
| `AckHandler`              | `ack`                | 确认消息     |
| `Esp32AckHandler`         | `esp32_ack`          | ESP32 确认   |
| `UserMgmtResultHandler`   | `user_mgmt_result`   | 用户管理结果 |
| `HeartbeatHandler`        | `heartbeat`          | 心跳消息     |
| `FaceRecognitionHandler`  | `face_recognition`   | 人脸识别     |

### C. 数据流向图

```
┌─────────────────────────────────────────────────────────────────┐
│                         App 端                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 锁控命令 │  │ 数据查询 │  │ 媒体下载 │  │ 音频对讲 │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
└───────┼─────────────┼─────────────┼─────────────┼──────────────┘
        │             │             │             │
        │ WebSocket   │ WebSocket   │ WebSocket   │ WebSocket
        │ (JSON)      │ (JSON)      │ (JSON)      │ (Binary)
        ↓             ↓             ↓             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      xiaozhi-server                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              AppConnectionHandler                        │   │
│  │  • 认证管理 (hello)                                      │   │
│  │  • 防重放 (seq_id)                                       │   │
│  │  • 消息路由                                              │   │
│  │  • 音频编码 (PCM → OPUS)                                 │   │
│  └────┬──────────────────┬──────────────────┬───────────────┘   │
│       │                  │                  │                   │
│       ↓                  ↓                  ↓                   │
│  ┌─────────┐      ┌──────────┐      ┌──────────┐              │
│  │ Command │      │  Query   │      │  Media   │              │
│  │  Proxy  │      │ Handler  │      │ Download │              │
│  └────┬────┘      └────┬─────┘      └────┬─────┘              │
│       │                │                  │                   │
│       │ 转发           │ 数据库查询        │ 文件读取           │
│       ↓                ↓                  ↓                   │
│  ┌─────────────────────────────────────────────┐              │
│  │        ConnectionManager                    │              │
│  │  • ESP32 连接管理                           │              │
│  │  • App 连接管理                             │              │
│  │  • 消息广播                                 │              │
│  └────┬──────────────────────────────────┬─────┘              │
└───────┼──────────────────────────────────┼────────────────────┘
        │                                  │
        │ WebSocket                        │ WebSocket
        │ (JSON/Binary)                    │ (JSON/Binary)
        ↓                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│                       ESP32 设备                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 执行命令 │  │ 状态上报 │  │ 事件上报 │  │ 监控数据 │       │
│  └──────────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
└─────────────────────┼─────────────┼─────────────┼──────────────┘
                      │             │             │
                      │ 推送        │ 推送        │ 推送
                      ↓             ↓             ↓
                ┌─────────────────────────────────────┐
                │    服务器广播给所有关联的 App        │
                └─────────────────────────────────────┘
```

### D. 时序图示例

#### D.1 远程开锁流程

```
App                服务器              ESP32
 │                  │                  │
 │──lock_control──→│                  │
 │  (seq_id=123)    │                  │
 │                  │                  │
 │←─server_ack─────│                  │
 │  (code=0)        │                  │
 │                  │                  │
 │                  │──lock_control──→│
 │                  │  (seq_id=123)    │
 │                  │                  │
 │                  │←─esp32_ack──────│
 │                  │  (code=0)        │
 │                  │                  │
 │                  │                  │ 执行开锁
 │                  │                  │
 │                  │←─log_report─────│
 │                  │  (method=remote) │
 │                  │                  │
 │←─log_report─────│                  │
 │  (uid=12345)     │                  │
 │                  │                  │
```

**说明**:

1. App 发送开锁命令（携带 seq_id）
2. 服务器立即返回 server_ack（确认收到）
3. 服务器转发命令给 ESP32
4. ESP32 返回 esp32_ack（确认收到）
5. ESP32 执行开锁并上报日志
6. 服务器填充 uid 后推送给 App

#### D.2 数据查询流程

```
App                服务器              数据库
 │                  │                  │
 │──query─────────→│                  │
 │  (target=status) │                  │
 │                  │                  │
 │                  │──SELECT─────────→│
 │                  │                  │
 │                  │←─结果───────────│
 │                  │                  │
 │←─query_result───│                  │
 │  (status=success)│                  │
 │                  │                  │
```

#### D.3 人脸识别推送流程

```
ESP32              服务器              App
 │                  │                  │
 │──人脸图像───────→│                  │
 │  (BinaryProtocol2)│                 │
 │                  │                  │
 │                  │ 执行人脸识别      │
 │                  │ 检查权限          │
 │                  │ 保存到访记录      │
 │                  │                  │
 │←─face_result────│                  │
 │                  │                  │
 │                  │──visit_notify──→│
 │                  │  (含图像)        │
 │                  │                  │
 │ 播放 TTS 问候语  │                  │
 │                  │                  │
```

#### D.4 监控模式流程

```
App                服务器              ESP32
 │                  │                  │
 │──start_monitor─→│                  │
 │                  │                  │
 │                  │──start_monitor─→│
 │                  │                  │
 │                  │                  │ 进入监控模式
 │                  │                  │
 │                  │←─视频帧─────────│
 │                  │  (JPEG)          │
 │←─视频帧─────────│                  │
 │                  │                  │
 │                  │←─音频帧─────────│
 │                  │  (OPUS)          │
 │                  │ 解码为 PCM       │
 │←─音频帧─────────│                  │
 │  (PCM)           │                  │
 │                  │                  │
 │──stop_monitor──→│                  │
 │                  │                  │
 │                  │──stop_monitor──→│
 │                  │                  │
 │                  │                  │ 退出监控模式
 │                  │                  │
```

---

## 结语

本文档详细分析了服务器接收 App 端命令的完整处理流程，涵盖了连接认证、命令代理、数据查询、媒体下载和实时推送五个核心模块。

**关键要点**:

1. **安全机制**: seq_id 防重放、hello 认证、路径遍历防护
2. **可靠性**: 命令重试机制、错误处理、日志记录
3. **实时性**: WebSocket 双向通信、异步处理、消息广播
4. **扩展性**: Handler 注册表、ConnectionManager 管理、协议版本兼容

**参考文档**:

- `docs/my_docs/智能猫眼门锁系统-服务器与App通信协议规范-v2.4.md`
- `docs/my_docs/智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md`
- `docs/my_docs/esp32-data-processing-detailed-analysis.md`
- `docs/my_docs/doorlock-user-management-implementation.md`（v2.4 新增）

**相关代码文件**:

- `core/app_connection.py` - App 连接处理
- `core/connection_manager.py` - 连接管理
- `core/handle/textHandler/commandProxyHandler.py` - 命令代理
- `core/handle/textHandler/queryHandler.py` - 数据查询
- `core/handle/textHandler/mediaDownloadHandler.py` - 媒体下载
- `core/handle/textHandler/systemMessageHandler.py` - 系统命令
- `core/handle/textHandler/faceRecognitionHandler.py` - 人脸管理
- `core/handle/textHandler/userMgmtResultHandler.py` - 用户管理结果
- `core/providers/doorlock/database.py` - 数据库操作
- `core/providers/doorlock/face_service.py` - 人脸服务

---

## 附录 E. 门锁用户管理功能详解（v2.4 新增）

### E.1 功能概述

门锁用户管理功能允许 App 为指纹、NFC、密码用户添加备注信息，并将元数据存储在服务器数据库中。

**核心特性**:

1. **用户备注**: 为指纹/NFC 添加易读的名称（如"张三的右手食指"）
2. **元数据存储**: 服务器数据库统一管理用户信息
3. **软删除**: 删除用户时保留历史记录
4. **创建者追踪**: 记录操作来源（app_id）
5. **查询接口**: 支持分页查询用户列表

### E.2 数据库表结构

**表名**: `doorlock_users`

**字段说明**:

| 字段       | 类型         | 说明                                      |
| ---------- | ------------ | ----------------------------------------- |
| id         | BIGINT       | 自增主键                                  |
| device_id  | VARCHAR(64)  | 设备 ID                                   |
| user_type  | VARCHAR(16)  | 用户类型：finger/nfc/password             |
| user_id    | INT          | ESP32 分配的用户 ID（指纹/NFC 的槽位 ID） |
| user_name  | VARCHAR(64)  | 用户备注名称                              |
| user_data  | VARCHAR(255) | 额外数据（如 NFC 卡号）                   |
| status     | TINYINT      | 状态：0=已删除，1=正常                    |
| created_at | DATETIME     | 创建时间                                  |
| updated_at | DATETIME     | 更新时间                                  |
| created_by | VARCHAR(64)  | 创建者 app_id                             |

**索引**:

- 主键: `id`
- 唯一键: `uk_device_type_userid (device_id, user_type, user_id)`
- 普通索引: `device_id`, `user_type`, `status`, `created_at`

### E.3 完整数据流程

#### E.3.1 添加用户流程

```
┌─────────────────────────────────────────────────────────────────┐
│ 步骤 1: App 发送添加命令                                         │
└─────────────────────────────────────────────────────────────────┘
App → Server:
{
  "type": "user_mgmt",
  "seq_id": "1702234567890_001",
  "category": "finger",
  "command": "add",
  "user_id": 0,
  "user_name": "张三的右手食指"
}

┌─────────────────────────────────────────────────────────────────┐
│ 步骤 2: Server 缓存 user_name                                    │
└─────────────────────────────────────────────────────────────────┘
esp32_conn._pending_user_names["1702234567890_001"] = {
  "user_name": "张三的右手食指",
  "app_id": "user_12345",
  "category": "finger",
  "command": "add",
  "user_id": 0
}

┌─────────────────────────────────────────────────────────────────┐
│ 步骤 3: Server 转发命令到 ESP32（移除 user_name）               │
└─────────────────────────────────────────────────────────────────┘
Server → ESP32:
{
  "type": "user_mgmt",
  "seq_id": "1702234567890_001",
  "category": "finger",
  "command": "add",
  "user_id": 0
}

┌─────────────────────────────────────────────────────────────────┐
│ 步骤 4: ESP32 执行添加并返回结果                                 │
└─────────────────────────────────────────────────────────────────┘
ESP32 → Server:
{
  "type": "user_mgmt_result",
  "seq_id": "1702234567890_001",
  "category": "finger",
  "command": "add",
  "result": true,
  "val": 5,  // ESP32 分配的 user_id
  "msg": "Success"
}

┌─────────────────────────────────────────────────────────────────┐
│ 步骤 5: Server 保存到数据库                                      │
└─────────────────────────────────────────────────────────────────┘
db.save_doorlock_user(
  device_id="AA:BB:CC:DD:EE:FF",
  user_type="finger",
  user_id=5,
  user_name="张三的右手食指",
  created_by="user_12345"
)

INSERT INTO doorlock_users
(device_id, user_type, user_id, user_name, status, created_by)
VALUES
('AA:BB:CC:DD:EE:FF', 'finger', 5, '张三的右手食指', 1, 'user_12345')

┌─────────────────────────────────────────────────────────────────┐
│ 步骤 6: Server 转发结果给 App                                    │
└─────────────────────────────────────────────────────────────────┘
Server → App:
{
  "type": "user_mgmt_result",
  "category": "finger",
  "command": "add",
  "result": true,
  "val": 5,
  "msg": "Success"
}
```

#### E.3.2 查询用户流程

```
┌─────────────────────────────────────────────────────────────────┐
│ 步骤 1: App 发送查询请求                                         │
└─────────────────────────────────────────────────────────────────┘
App → Server:
{
  "type": "query",
  "seq_id": "1702234567890_002",
  "target": "doorlock_users",
  "data": {
    "user_type": "finger",
    "limit": 100,
    "offset": 0
  }
}

┌─────────────────────────────────────────────────────────────────┐
│ 步骤 2: Server 查询数据库                                        │
└─────────────────────────────────────────────────────────────────┘
SELECT id, device_id, user_type, user_id, user_name, user_data,
       status, created_at, updated_at, created_by
FROM doorlock_users
WHERE device_id = 'AA:BB:CC:DD:EE:FF'
  AND user_type = 'finger'
  AND status = 1
ORDER BY user_type ASC, user_id ASC
LIMIT 100 OFFSET 0

┌─────────────────────────────────────────────────────────────────┐
│ 步骤 3: Server 返回查询结果                                      │
└─────────────────────────────────────────────────────────────────┘
Server → App:
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
        "created_at": "2024-12-11 10:30:00",
        "updated_at": "2024-12-11 10:30:00",
        "created_by": "user_12345"
      }
    ],
    "total": 1,
    "limit": 100,
    "offset": 0
  }
}
```

#### E.3.3 删除用户流程

```
┌─────────────────────────────────────────────────────────────────┐
│ 步骤 1: App 发送删除命令                                         │
└─────────────────────────────────────────────────────────────────┘
App → Server:
{
  "type": "user_mgmt",
  "seq_id": "1702234567890_003",
  "category": "finger",
  "command": "del",
  "user_id": 5
}

┌─────────────────────────────────────────────────────────────────┐
│ 步骤 2: Server 转发命令到 ESP32                                  │
└─────────────────────────────────────────────────────────────────┘
Server → ESP32:
{
  "type": "user_mgmt",
  "seq_id": "1702234567890_003",
  "category": "finger",
  "command": "del",
  "user_id": 5
}

┌─────────────────────────────────────────────────────────────────┐
│ 步骤 3: ESP32 执行删除并返回结果                                 │
└─────────────────────────────────────────────────────────────────┘
ESP32 → Server:
{
  "type": "user_mgmt_result",
  "seq_id": "1702234567890_003",
  "category": "finger",
  "command": "del",
  "result": true,
  "val": 0,
  "msg": "Success"
}

┌─────────────────────────────────────────────────────────────────┐
│ 步骤 4: Server 软删除数据库记录                                  │
└─────────────────────────────────────────────────────────────────┘
db.delete_doorlock_user(
  device_id="AA:BB:CC:DD:EE:FF",
  user_type="finger",
  user_id=5
)

UPDATE doorlock_users
SET status = 0, updated_at = CURRENT_TIMESTAMP
WHERE device_id = 'AA:BB:CC:DD:EE:FF'
  AND user_type = 'finger'
  AND user_id = 5

┌─────────────────────────────────────────────────────────────────┐
│ 步骤 5: Server 转发结果给 App                                    │
└─────────────────────────────────────────────────────────────────┘
Server → App:
{
  "type": "user_mgmt_result",
  "category": "finger",
  "command": "del",
  "result": true,
  "val": 0,
  "msg": "Success"
}
```

### E.4 数据库操作方法

**文件**: `core/providers/doorlock/database.py`

#### E.4.1 save_doorlock_user()

**功能**: 保存门锁用户（支持 INSERT/UPDATE）

**参数**:

- `device_id`: 设备 ID
- `user_type`: 用户类型（finger/nfc/password）
- `user_id`: ESP32 分配的用户 ID
- `user_name`: 用户备注名称（可选）
- `user_data`: 额外数据（可选）
- `created_by`: 创建者 app_id（可选）

**返回**: 插入的记录 ID

**SQL**:

```sql
INSERT INTO doorlock_users
(device_id, user_type, user_id, user_name, user_data, status, created_by)
VALUES (%s, %s, %s, %s, %s, 1, %s)
ON DUPLICATE KEY UPDATE
    user_name = VALUES(user_name),
    user_data = VALUES(user_data),
    status = 1,
    updated_at = CURRENT_TIMESTAMP
```

#### E.4.2 delete_doorlock_user()

**功能**: 删除门锁用户（软删除）

**参数**:

- `device_id`: 设备 ID
- `user_type`: 用户类型
- `user_id`: 用户 ID

**返回**: 是否删除成功

**SQL**:

```sql
UPDATE doorlock_users
SET status = 0, updated_at = CURRENT_TIMESTAMP
WHERE device_id = %s AND user_type = %s AND user_id = %s
```

#### E.4.3 get_doorlock_user()

**功能**: 获取单个门锁用户

**参数**:

- `device_id`: 设备 ID
- `user_type`: 用户类型
- `user_id`: 用户 ID

**返回**: 用户信息字典，不存在则返回 None

**SQL**:

```sql
SELECT id, device_id, user_type, user_id, user_name, user_data,
       status, created_at, updated_at, created_by
FROM doorlock_users
WHERE device_id = %s AND user_type = %s AND user_id = %s AND status = 1
```

#### E.4.4 query_doorlock_users()

**功能**: 查询门锁用户列表（带分页）

**参数**:

- `device_id`: 设备 ID
- `user_type`: 用户类型过滤（可选）
- `limit`: 每页数量（默认 100）
- `offset`: 偏移量（默认 0）

**返回**: (记录列表, 总数)

**SQL**:

```sql
-- 查询总数
SELECT COUNT(*) as total FROM doorlock_users
WHERE device_id = %s AND status = 1 [AND user_type = %s]

-- 查询记录
SELECT id, device_id, user_type, user_id, user_name, user_data,
       status, created_at, updated_at, created_by
FROM doorlock_users
WHERE device_id = %s AND status = 1 [AND user_type = %s]
ORDER BY user_type ASC, user_id ASC
LIMIT %s OFFSET %s
```

#### E.4.5 clear_doorlock_users()

**功能**: 清空指定类型的所有门锁用户（软删除）

**参数**:

- `device_id`: 设备 ID
- `user_type`: 用户类型

**返回**: 删除的记录数

**SQL**:

```sql
UPDATE doorlock_users
SET status = 0, updated_at = CURRENT_TIMESTAMP
WHERE device_id = %s AND user_type = %s AND status = 1
```

### E.5 注意事项

#### E.5.1 数据一致性

- ESP32 和数据库的用户数据可能不一致
- 建议定期同步（可选功能，未实现）
- 删除操作采用软删除，保留历史记录

#### E.5.2 并发处理

- 使用 `seq_id` 作为缓存键，避免并发冲突
- 数据库使用唯一键约束，防止重复插入
- 缓存在处理完成后应清理（当前实现未清理）

#### E.5.3 错误处理

- 数据库操作失败时记录日志
- 不影响 ESP32 命令执行
- App 端可通过查询接口验证结果

#### E.5.4 性能优化

- 查询接口支持分页，避免一次返回大量数据
- 使用索引优化查询性能
- 软删除记录定期归档（可选功能，未实现）

### E.6 相关文件

| 文件                                                      | 功能                |
| --------------------------------------------------------- | ------------------- |
| `core/handle/textHandler/commandProxyHandler.py`          | 用户管理命令代理    |
| `core/handle/textHandler/userMgmtResultHandler.py`        | 用户管理结果处理    |
| `core/handle/textHandler/queryHandler.py`                 | 门锁用户查询处理    |
| `core/providers/doorlock/database.py`                     | 数据库操作方法      |
| `migrations/add_doorlock_users_table.sql`                 | 数据库迁移 SQL 脚本 |
| `migrations/run_add_doorlock_users.py`                    | 数据库迁移执行脚本  |
| `docs/my_docs/doorlock-user-management-implementation.md` | 功能实现文档        |

---

**文档版本**: v2.4  
**最后更新**: 2026-02-01
