# 需求文档：服务器端协议简化重构

## 简介

本文档定义了 xiaozhi-server（ESP32 智能门锁系统的 Python 服务器端）从 v5.2 协议简化到 v6.0 协议的需求。核心目标是删除复杂的双重 ACK、seq_id 防重放、命令重试等机制，同时保留所有业务功能和数据完整性。

## 术语表

- **Server**：xiaozhi-server Python 服务器端
- **ESP32**：智能门锁设备端（C++）
- **App**：手机客户端应用
- **seq_id**：消息序列号，用于防重放和消息追踪
- **esp32_ack**：ESP32 第一级确认（"已收到命令"）
- **ack**：ESP32 第二级确认（"命令已执行完成"）
- **server_ack**：服务器确认（Server 收到 App 命令后的即时确认）
- **CommandProxyHandler**：命令代理处理器，负责转发 App 命令到 ESP32
- **SeqIdCache**：seq_id 防重放缓存
- **device_state**：设备状态缓存（电量、锁状态、光照等）
- **last_face_result**：最近一次人脸识别结果缓存
- **OPUS_Decoder**：OPUS 音频解码器（用于监控模式）

## 需求

### 需求 1：删除 ESP32 第一级确认机制

**用户故事：** 作为服务器开发者，我希望删除 esp32_ack 第一级确认机制，以简化协议流程。

#### 验收标准

1. THE Server SHALL 删除 `esp32AckHandler.py` 文件
2. THE Server SHALL 从消息处理器注册表中移除 esp32_ack 类型
3. THE CommandProxyHandler SHALL 删除等待 esp32_ack 的重试逻辑
4. THE CommandProxyHandler SHALL 删除 `_wait_for_esp32_ack()` 方法
5. THE CommandProxyHandler SHALL 删除 `_forward_with_retry()` 方法中的 esp32_ack 等待代码
6. THE ESP32Connection SHALL 删除 `_pending_esp32_acks` 字典属性

### 需求 2：删除 seq_id 防重放机制

**用户故事：** 作为服务器开发者，我希望删除 seq_id 防重放机制，以简化消息处理逻辑。

#### 验收标准

1. THE Server SHALL 删除 `core/utils/seq_id_cache.py` 文件
2. THE AppConnectionHandler SHALL 删除 `_seq_id_cache` 类属性
3. THE AppConnectionHandler SHALL 删除 `_handle_text_message()` 中的 seq_id 防重放检查
4. THE CommandProxyHandler SHALL 删除消息转发时的 seq_id 生成逻辑
5. THE CommandProxyHandler SHALL 原封不动转发 App 消息（不添加或修改任何字段）
6. THE AckHandler SHALL 删除 seq_id/msg_id 相关的追踪和验证逻辑

### 需求 3：删除 server_ack 服务器确认

**用户故事：** 作为服务器开发者，我希望删除 server_ack 机制，让 App 直接等待 ESP32 的 ack。

#### 验收标准

1. THE AppConnectionHandler SHALL 删除 `_send_server_ack()` 方法
2. THE AppConnectionHandler SHALL 删除 `_handle_text_message()` 中发送 server_ack 的代码
3. THE CommandProxyHandler SHALL 不发送 server_ack 给 App
4. WHEN App 发送命令时，THE Server SHALL 只记录日志并转发，不返回 server_ack
5. THE App SHALL 直接等待 ESP32 的 ack（由 Server 透传）

### 需求 4：删除命令重试机制

**用户故事：** 作为服务器开发者，我希望删除服务器端的命令重试机制，让用户手动重试。

#### 验收标准

1. THE CommandProxyHandler SHALL 删除 `_forward_with_retry()` 方法中的重试循环
2. THE CommandProxyHandler SHALL 发送命令到 ESP32 后立即返回（不等待确认）
3. WHEN 命令发送失败时，THE Server SHALL 记录错误日志
4. THE Server SHALL 不实现自动重传逻辑
5. IF ESP32 无响应，THE App SHALL 通过超时机制提示用户手动重试

### 需求 5：简化错误码体系

**用户故事：** 作为服务器开发者，我希望将错误码从 0-10 体系简化为 0/1 + msg 描述。

#### 验收标准

1. THE Server SHALL 删除 `core/constants/error_codes.py` 文件（如果存在）
2. THE AckHandler SHALL 接受并转发 ESP32 的 `{code: 0或1, msg: "描述"}` 格式
3. THE Server SHALL 不验证错误码范围（接受任意 code 值）
4. THE CommandProxyHandler SHALL 在设备离线时返回 `{type: "error", code: 1, msg: "设备离线"}`
5. THE Server SHALL 不映射或转换错误码（透传 ESP32 的原始 code 和 msg）

### 需求 6：删除 WebSocket query 接口

**用户故事：** 作为服务器开发者，我希望删除 WebSocket query 接口，改为使用 HTTP API。

#### 验收标准

1. THE Server SHALL 保留 `queryHandler.py` 文件但标记为废弃（添加日志警告）
2. WHEN App 发送 query 消息时，THE Server SHALL 返回错误 `{type: "error", msg: "query 接口已废弃，请使用 HTTP API"}`
3. THE Server SHALL 在文档中说明 query 接口的 HTTP API 替代方案
4. THE Server SHALL 保留现有的 HTTP API 端点（`/api/doorlock/*`）
5. THE Server SHALL 不删除 queryHandler.py（避免破坏现有代码引用）

### 需求 7：删除 WebSocket media_download 接口

**用户故事：** 作为服务器开发者，我希望删除 WebSocket media_download 接口，改为使用 HTTP 下载。

#### 验收标准

1. THE Server SHALL 保留 media_download 处理器但标记为废弃
2. WHEN App 发送 media_download 消息时，THE Server SHALL 返回错误 `{type: "error", msg: "media_download 已废弃，请使用 HTTP API 下载"}`
3. THE Server SHALL 提供 HTTP 端点 `/api/doorlock/media/<id>` 用于媒体文件下载
4. THE Server SHALL 在 visit_notification 中使用 `image_path` 字段替代 Base64 `image` 字段
5. THE Server SHALL 不删除 media_download 处理器（避免破坏现有代码引用）

### 需求 8：删除 device_state 缓存机制

**用户故事：** 作为服务器开发者，我希望删除 device_state 缓存，完全依赖 ESP32 推送。

#### 验收标准

1. THE ESP32Connection SHALL 删除 `device_state` 属性
2. THE AppConnectionHandler SHALL 删除 `_push_initial_device_status()` 中推送 device_state 的代码
3. THE AppConnectionHandler SHALL 删除 `_handle_get_device_status()` 中返回 device_state 的代码
4. WHEN App 连接时，THE Server SHALL 只推送设备在线/离线状态
5. THE App SHALL 通过订阅 ESP32 的 status_report 消息获取实时状态

### 需求 9：保留数据库操作日志

**用户故事：** 作为服务器开发者，我希望保留数据库操作日志功能，但改为收到 ESP32 ack 后记录。

#### 验收标准

1. THE CommandProxyHandler SHALL 保留 `_log_unlock_operation()` 方法
2. THE CommandProxyHandler SHALL 在收到 ESP32 ack（code=0）后调用日志记录
3. THE logReportHandler SHALL 继续记录 ESP32 上报的开锁日志到数据库
4. THE Server SHALL 记录操作日志时包含 app_id、命令内容、时间戳
5. THE Server SHALL 保持现有数据库表结构不变

### 需求 10：保留人脸识别缓存

**用户故事：** 作为服务器开发者，我希望保留 last_face_result 缓存，用于填充开锁日志的 uid。

#### 验收标准

1. THE ESP32Connection SHALL 保留 `last_face_result` 属性
2. THE faceRecognitionHandler SHALL 在人脸识别完成后更新 `last_face_result`
3. THE logReportHandler SHALL 使用 `last_face_result` 填充 face 方式开锁的 uid
4. THE Server SHALL 在 face_result 消息中缓存 `{user_id, timestamp}` 信息
5. THE Server SHALL 在 5 分钟后自动清除过期的 last_face_result

### 需求 11：保留监控模式 OPUS 解码器

**用户故事：** 作为服务器开发者，我希望保留监控模式的 OPUS 解码器功能。

#### 验收标准

1. THE AppConnectionHandler SHALL 保留 `opus_encoder` 属性
2. THE AppConnectionHandler SHALL 保留 `_handle_binary_message()` 方法
3. WHEN App 发送 PCM 音频时，THE Server SHALL 编码为 OPUS 后转发给 ESP32
4. THE Server SHALL 使用 24kHz 采样率、单声道、60ms 帧
5. THE Server SHALL 保持监控模式的音视频流处理逻辑不变

### 需求 12：保留所有业务逻辑

**用户故事：** 作为服务器开发者，我希望保留所有业务逻辑（人脸识别、访客意图、门锁控制等）。

#### 验收标准

1. THE Server SHALL 保留 faceRecognitionHandler 的完整功能
2. THE Server SHALL 保留 visitorIntentHandler 的完整功能
3. THE Server SHALL 保留所有 textHandler（除 esp32AckHandler 外）
4. THE Server SHALL 保留 BinaryProtocol2 音视频流处理
5. THE Server SHALL 保留所有 HTTP API 端点

### 需求 13：简化命令代理逻辑

**用户故事：** 作为服务器开发者，我希望简化 CommandProxyHandler，使其成为透明代理。

#### 验收标准

1. THE CommandProxyHandler SHALL 验证 App 已认证
2. THE CommandProxyHandler SHALL 检查 ESP32 是否在线
3. THE CommandProxyHandler SHALL 记录操作日志到数据库
4. THE CommandProxyHandler SHALL 原封不动转发 JSON 消息给 ESP32
5. THE CommandProxyHandler SHALL 不修改、不添加、不删除消息字段

### 需求 14：简化 AckHandler 逻辑

**用户故事：** 作为服务器开发者，我希望简化 AckHandler，使其只做消息转发。

#### 验收标准

1. THE AckHandler SHALL 接收 ESP32 的 ack 消息
2. THE AckHandler SHALL 原封不动转发 ack 给所有关联的 App
3. THE AckHandler SHALL 不验证 seq_id/msg_id
4. THE AckHandler SHALL 不验证错误码范围
5. THE AckHandler SHALL 记录 DEBUG 级别日志（成功）或 WARNING 级别日志（失败）

### 需求 15：保持协议兼容性

**用户故事：** 作为服务器开发者，我希望保持与 ESP32 端和 App 端的协议兼容。

#### 验收标准

1. THE Server SHALL 接受 ESP32 发送的所有原始消息类型（hello、tts、stt、llm、mcp、system、alert、custom）
2. THE Server SHALL 接受 ESP32 发送的新门锁消息类型（ack、status_report、event_report、log_report、door_opened_report、user_mgmt_result）
3. THE Server SHALL 接受 App 发送的命令消息（lock_control、dev_control、user_mgmt、system）
4. THE Server SHALL 转发 ESP32 上报给所有关联的 App
5. THE Server SHALL 不修改消息格式（保持 JSON 结构不变）

### 需求 16：保持数据库表结构不变

**用户故事：** 作为服务器开发者，我希望保持现有数据库表结构不变。

#### 验收标准

1. THE Server SHALL 不修改任何数据库表结构
2. THE Server SHALL 继续使用现有的 ORM 模型
3. THE Server SHALL 保持日志记录的字段不变
4. THE Server SHALL 保持人脸数据存储的字段不变
5. THE Server SHALL 保持访客记录的字段不变

### 需求 17：保持日志记录完整性

**用户故事：** 作为服务器开发者，我希望保持日志记录的完整性。

#### 验收标准

1. THE Server SHALL 记录所有 App 命令操作（app_id、命令类型、时间戳）
2. THE Server SHALL 记录所有 ESP32 上报事件（设备 ID、事件类型、时间戳）
3. THE Server SHALL 记录所有开锁日志（方法、用户 ID、结果、时间戳）
4. THE Server SHALL 记录所有人脸识别结果（person_id、结果、图片路径、时间戳）
5. THE Server SHALL 使用 loguru 记录所有错误和警告

### 需求 18：实现 HTTP API 替代方案

**用户故事：** 作为服务器开发者，我希望提供 HTTP API 替代 WebSocket query 和 media_download。

#### 验收标准

1. THE Server SHALL 提供 HTTP 端点 `/api/doorlock/status` 查询设备状态
2. THE Server SHALL 提供 HTTP 端点 `/api/doorlock/events` 查询事件历史
3. THE Server SHALL 提供 HTTP 端点 `/api/doorlock/unlock_logs` 查询开锁日志
4. THE Server SHALL 提供 HTTP 端点 `/api/doorlock/media` 查询媒体文件列表
5. THE Server SHALL 提供 HTTP 端点 `/api/doorlock/media/<id>` 下载媒体文件

### 需求 19：更新协议文档

**用户故事：** 作为服务器开发者，我希望更新协议文档以反映 v6.0 的变化。

#### 验收标准

1. THE Server SHALL 在 `docs/01-当前文档/` 中创建 v6.0 协议文档
2. THE Server SHALL 标记 v5.2 协议文档为已废弃
3. THE Server SHALL 在文档中说明所有删除的功能
4. THE Server SHALL 在文档中说明所有保留的功能
5. THE Server SHALL 提供迁移指南（从 v5.2 到 v6.0）

### 需求 20：实现渐进式迁移

**用户故事：** 作为服务器开发者，我希望实现渐进式迁移，避免一次性破坏所有功能。

#### 验收标准

1. THE Server SHALL 先实现 HTTP API 端点
2. THE Server SHALL 再废弃 WebSocket query 和 media_download
3. THE Server SHALL 再删除 esp32_ack 和 seq_id 机制
4. THE Server SHALL 再删除 server_ack 机制
5. THE Server SHALL 在每个阶段完成后进行功能验证
