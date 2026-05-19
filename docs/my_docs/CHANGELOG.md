# 变更日志

## 2025-05-18 门锁用户 CRUD 适配实际数据库表结构

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/database.py`

### 修改位置
- `DoorlockDatabase` 类中的「门锁用户 CRUD」区域（约第 1014 行起）

### 变更内容
1. **重构 `save_doorlock_user` 方法**：参数从 `(device_id, user_id, name, role)` 改为 `(device_id, user_id, user_type, user_name, user_data, created_by)`，SQL 适配实际表结构 `doorlock_users(device_id, user_type, user_id, user_name, user_data, status, created_by)`，唯一键为 `uk_device_type_userid(device_id, user_type, user_id)`
2. **删除 `update_doorlock_user_finger` 方法**：不再需要单独的指纹 ID 列表更新
3. **删除 `update_doorlock_user_nfc` 方法**：不再需要单独的 NFC ID 列表更新
4. **新增 `delete_doorlock_user` 方法**：软删除门锁用户（将 status 设为 0）
5. **新增 `clear_doorlock_users` 方法**：按类型批量软删除门锁用户
6. **更新 `get_doorlock_users` 方法**：新增 `user_type` 过滤参数，仅返回 status=1 的有效用户，按创建时间倒序排列

### 实现功能
将门锁用户 CRUD 操作从旧的「按指纹/NFC 分别更新」模式，重构为基于 `user_type` 字段（finger/nfc/password）的统一管理模式，采用软删除策略（status 字段），与实际数据库表结构完全对齐。

## 2025-05-18 doorlock_users 表结构重构

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/database.py`

### 修改位置
- `database.py` 中 `doorlock_users` 表的 `CREATE TABLE` 语句（约第 195 行）

### 修改时间
- 2025-05-18

### 变更内容
重构 `doorlock_users` 表结构，从基于角色的用户管理模型改为基于用户类型的扁平化管理模型：

- **移除字段**：`role`、`finger_ids`（JSON）、`nfc_ids`（JSON）、`face_registered`
- **新增字段**：
  - `user_type VARCHAR(16)` — 用户类型（finger/nfc/password）
  - `user_data VARCHAR(255)` — 额外数据（如 NFC 卡号、密码哈希）
  - `status TINYINT` — 状态标记（0=已删除，1=正常）
  - `created_by VARCHAR(64)` — 创建者 app_id
- **字段重命名**：`name` → `user_name`
- **唯一键调整**：`uk_device_user(device_id, user_id)` → `uk_device_type_userid(device_id, user_type, user_id)`
- **新增索引**：`idx_device_id`、`idx_user_type`、`idx_status`
- **添加 COMMENT**：所有字段和表均添加了中文注释

### 实现功能
将门锁用户表从"一个用户绑定多种凭证"的聚合模型，改为"每条记录代表一个独立凭证"的扁平模型。每个指纹、NFC 卡、密码各自独立存储为一行记录，通过 `user_type + user_id` 组合唯一标识，便于 ESP32 端的槽位管理和 App 端的细粒度增删操作。同时新增软删除（status）和操作溯源（created_by）支持。

## 2025-07-15

### commandProxyHandler.py - 用户管理命令代理增强

- **文件**: `main/xiaozhi-server/core/handle/textHandler/commandProxyHandler.py`
- **位置**: 用户管理命令缓存构建逻辑（约第458行附近）
- **变更内容**:
  - 新增 `payload` 字段：支持 App 传递额外数据（如门锁用户的详细信息）
  - 新增 `app_id` 字段：记录执行操作的 App 用户标识，便于审计追踪
  - 调整 `user_name` 注释为"备注名（可选）"，语义更清晰
  - 更新调试日志，增加 payload 信息输出
- **实现功能**: 增强用户管理命令代理的数据完整性，支持 App 端在发送用户管理命令（如添加/删除门锁用户）时携带更多上下文信息（payload 额外数据、app_id 操作者标识），为后续门锁用户同步和操作审计提供数据基础。


## 2025-01-27

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/userMgmtResultHandler.py`

### 修改位置
- `_handle_user_mgmt_result` 函数中，获取缓存命令信息后提取 `user_name` 的逻辑（约第108-109行）

### 变更内容
- 移除了原来从 `last_cmd` 中分别获取 `user_name` 和 `payload` 两个字段的逻辑
- 改为直接从 `last_cmd.get("payload")` 获取 `user_name`
- 删除了不再使用的 `user_data` 变量

### 实现功能
- 修正用户管理结果处理中用户名的取值来源：`payload` 字段即为 App 端为该用户设置的备注名，无需额外的 `user_name` 字段
- 简化了数据结构，统一使用 `payload` 作为用户备注名的来源，与 App 端发送的命令格式保持一致

### 2025-05-18

#### `main/xiaozhi-server/core/handle/textHandler/ackHandler.py`
- **修改位置**：文件顶部 import 区域（第10行）
- **修改时间**：2025-05-18
- **变更内容**：新增 `from core.handle.textHandler.queryHandler import _get_base_database` 导入语句
- **功能说明**：为 AckHandler 引入数据库访问工具函数，支持 `_handle_user_mgmt_delete` 方法在收到用户管理删除/清空命令的成功 ACK 后，同步删除数据库中对应的用户记录

## 2025-05-18 新增 app_disconnect_log 表

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/database.py`

### 修改位置
- `DoorlockDatabase` 类的数据库表初始化方法中，在已有建表语句之后（第 226 行附近）新增建表 SQL

### 变更内容
- 新增 `app_disconnect_log` 表的 `CREATE TABLE IF NOT EXISTS` 语句
- 表结构：
  - `id` BIGINT 自增主键
  - `device_id` VARCHAR(64) 设备 ID
  - `app_id` VARCHAR(64) App 用户标识
  - `disconnect_time` DATETIME App 断开连接的时间
  - `created_at` DATETIME 记录创建时间
  - 唯一索引 `uk_device_app (device_id, app_id)`
  - 普通索引 `idx_device_id (device_id)`

### 实现功能
- 记录 App 端断开连接的时间，用于下次 App 重连时进行**增量数据推送**——服务器可根据 `disconnect_time` 判断 App 离线期间产生了哪些新数据，仅推送增量部分，避免每次连接都全量推送历史数据。

## 2025-05-18 App 连接增量推送支持

### 修改文件
- `main/xiaozhi-server/core/app_connection.py`

### 修改位置
- `AppConnectionHandler._authenticate()` 方法中，认证成功后、推送初始设备状态之前（约第140行）

### 变更内容
- 新增调用 `self._get_last_disconnect_time()` 获取 App 上次断开时间
- 将结果存储到 `self.last_disconnect_time` 属性
- 添加日志输出：如果有断开记录则提示"将进行增量推送"，否则提示"首次连接或无断开记录，将进行全量推送"

### 实现功能
- 支持增量推送机制：App 重新连接时读取上次断开时间，后续推送逻辑可据此仅推送断开期间的新数据，避免全量推送造成的带宽浪费和数据冗余

## 2025-05-18 App 断开时间记录功能

### 修改文件
- `main/xiaozhi-server/core/app_connection.py`

### 修改位置
- `AppConnectionHandler` 类末尾，新增两个私有异步方法

### 变更内容

1. **新增 `_get_last_disconnect_time()` 方法**（第 800-843 行）
   - 从 `app_disconnect_log` 表查询指定 `device_id` + `app_id` 的上次断开时间
   - 返回 `datetime` 对象或 `None`（首次连接时）

2. **新增 `_save_disconnect_time()` 方法**（第 845-889 行）
   - 将当前时间写入 `app_disconnect_log` 表
   - 使用 `INSERT ... ON DUPLICATE KEY UPDATE` 实现 upsert，确保每对 `(device_id, app_id)` 只保留一条记录
   - 在连接清理（`_cleanup`）时调用，记录 App 断开的精确时间

### 实现功能
为 App 增量推送机制提供数据支撑：记录每次 App 断开连接的时间，下次连接时可据此判断断开期间产生的新数据，仅推送增量内容，减少不必要的全量数据传输。

### 2025-05-18 访客意图推送支持增量推送

- **修改文件**: `main/xiaozhi-server/core/app_connection.py`
- **修改位置**: `AppConnectionHandler._push_recent_visitor_intents()` 方法内，调用 `doorlock_db.get_visitor_intents()` 处
- **修改时间**: 2025-05-18
- **变更内容**: 在查询访客意图记录时，新增 `start_date=self.last_disconnect_time` 参数，当 `last_disconnect_time` 为 None 时查询全部记录
- **实现功能**: 访客意图通知推送支持增量推送机制——App 重新连接时，仅推送上次断开后产生的新访客意图记录，避免重复推送历史数据，与开锁日志和到访记录的增量推送逻辑保持一致

## 2025-01-XX - App 增量推送日志优化

### 修改文件
- `main/xiaozhi-server/core/app_connection.py`

### 修改位置
- `AppConnectionHandler._push_history_data_delayed()` 方法的文档字符串和日志输出

### 修改时间
- 2025-01-XX（当前）

### 变更内容
1. 更新了 `_push_history_data_delayed()` 方法的 docstring，明确描述两种推送模式：
   - 增量模式（有断开时间记录）：仅推送 App 断开期间的新数据
   - 全量模式（首次连接）：推送最近 5 条记录
2. 优化了日志输出，新增 `push_mode` 变量标识当前推送模式（增量/全量）
3. 日志中增加了 `since` 字段，显示上次断开时间，便于调试和追踪

### 实现功能
- 提升增量推送逻辑的可读性和可调试性，使开发者能快速判断当前推送策略及其依据

## 2025-05-18 新增 app_disconnect_log 建表脚本

### 变更文件
- **新增**: `main/xiaozhi-server/scripts/create_app_disconnect_table.py`

### 修改位置
- 新建文件，包含 `main()` 函数

### 变更内容
- 新增数据库建表脚本，用于创建 `app_disconnect_log` 表
- 表结构包含：`id`（自增主键）、`device_id`（设备 ID）、`app_id`（App 用户标识）、`disconnect_time`（断开时间）、`created_at`（创建时间）
- 设置了 `(device_id, app_id)` 唯一索引和 `device_id` 普通索引
- 脚本执行后会打印表结构进行验证

### 实现功能
- 为 App 增量推送功能提供数据支撑：记录每个 App 用户上次断开连接的时间
- 当 App 重新连接时，服务端可根据 `disconnect_time` 仅推送断开期间产生的新数据（开锁日志、到访记录、访客意图等），避免全量推送，提升效率和用户体验

## 2025-05-18 Person 数据类字段默认值调整

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/models.py`

### 修改位置
- `Person` 数据类（`@dataclass`）的字段定义

### 变更内容
- `name` 字段：从必填参数改为带默认值 `""` 的可选参数
- `relation_type` 字段：从必填参数改为带默认值 `""` 的可选参数
- `id` 字段：从必填的 `int` 类型改为 `Optional[int]`，默认值为 `None`，并移至默认值字段区域（避免 dataclass 字段顺序错误）

### 实现功能
允许在创建 `Person` 实例时不必提供所有必填字段，提升了灵活性。适用于人脸识别流程中尚未完全确认身份的场景（如陌生人到访时仅有部分信息），避免因缺少 `id` 或 `name` 而无法实例化对象。

## 2025-05-18 DoorlockPermission 模型增加时间策略字段序列化

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/models.py`

### 修改位置
- `DoorlockPermission` 类的 `to_dict()` 方法：新增 6 个字段的序列化输出
- `DoorlockPermission` 类的 `from_dict()` 类方法：新增 `time_start` 和 `time_end` 的反序列化处理

### 变更内容
1. `to_dict()` 方法新增以下字段的序列化：
   - `time_start`：时间段开始（ISO 格式）
   - `time_end`：时间段结束（ISO 格式）
   - `day_type`：日期类型
   - `week_days`：星期几限制
   - `month_days`：月份日期限制
   - `remaining_count`：剩余使用次数

2. `from_dict()` 方法新增：
   - `time_start` 字符串到 `time` 对象的反序列化
   - `time_end` 字符串到 `time` 对象的反序列化

### 实现功能
完善门锁权限模型的时间策略字段序列化/反序列化支持，使权限的时间段限制（每日可用时间段）、日期类型、星期/月份限制、剩余使用次数等信息能够正确地在字典与对象之间转换，支持 App 端展示和编辑权限的精细化时间控制策略。


## 2025-01-XX queryHandler 访客意图查询字段提取修复

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/queryHandler.py`

### 修改位置
- `queryHandler.py` 中访客意图记录转换为字典格式的循环逻辑（约第376-392行）

### 修改时间
- 2025-01（具体日期见 git log）

### 变更内容
- 修复 `important_notes` 和 `ai_analysis` 字段的提取方式
- 原逻辑直接从 `record` 对象的顶层属性获取 `important_notes` 和 `ai_analysis`
- 新逻辑改为从 `record.intent_summary` 字典中嵌套提取这两个字段
- 同时将 `intent_summary` 字段直接赋值为完整的字典对象

### 实现功能
- 修正了访客意图查询接口中字段提取路径错误的问题。`important_notes` 和 `ai_analysis` 实际嵌套在 `intent_summary` 字典内部，而非 record 对象的独立属性，此修复确保 App 端查询访客意图时能正确获取这些嵌套字段的值。

## 2025-05-18 persons 表 relation_type 新增 'owner' 枚举值

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/database.py`

### 修改位置
- `database.py` 中建表 SQL（`CREATE TABLE IF NOT EXISTS persons`）的 `relation_type` 字段 ENUM 定义

### 变更内容
- 在 `relation_type` 枚举列表最前面新增了 `'owner'`（业主/户主）类型
- 完整枚举变为：`'owner', 'family', 'friend', 'colleague', 'property', 'courier', 'delivery', 'tutor', 'classmate', 'other'`

### 实现功能
- 支持将人员标记为"业主/户主"身份，区分于普通家庭成员，便于门锁系统对不同身份人员执行差异化权限策略


---

### 2025-01-XX - 新增 persons 表 relation_type 字段 owner 选项

**文件**: `main/xiaozhi-server/alter_relation_type.py`（新增）

**位置**: 项目根目录下的临时数据库迁移脚本

**时间**: 2025年

**变更内容**:
- 新增临时 SQL 脚本，用于修改 `persons` 表的 `relation_type` 字段
- 将 `relation_type` 的 ENUM 类型添加 `owner`（业主）选项
- 完整枚举值：`owner`, `family`, `friend`, `colleague`, `property`, `courier`, `delivery`, `tutor`, `classmate`, `other`

**实现功能**:
- 支持在人员关系类型中标识"业主"身份，区分业主与其他家庭成员
- 为门锁权限管理提供更精确的身份分类


## 2025-01-XX faceRecognitionHandler 响应添加 seq_id 支持

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/faceRecognitionHandler.py`

### 修改位置
- `_send_response` 方法签名及方法体

### 修改时间
- 2025-01-XX（当前）

### 变更内容
- `_send_response` 方法新增 `seq_id` 可选参数
- 当 `seq_id` 存在时，将其包含在响应 JSON 中返回给客户端
- 补充了方法的 docstring，添加了 Args 参数说明

### 实现功能
- 支持 APP 端通过 `seq_id` 匹配请求与响应，实现消息确认机制
- 与协议 v2.2 的 `server_ack` 消息确认机制保持一致，确保 APP 端能正确关联异步响应

## 2025-05-18 faceRecognitionHandler 人脸管理接口添加 seq_id 支持

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/faceRecognitionHandler.py`

### 修改位置
- `_handle_register()` 方法：提取 seq_id 并传递给所有 `_send_response` 调用
- `_handle_get_persons()` 方法：同上
- `_handle_get_person()` 方法：同上
- `_handle_delete_person()` 方法：同上
- `_handle_update_permission()` 方法：同上
- `_handle_get_visits()` 方法：同上
- `handle_face_management()` 中未知动作的错误响应：补充 seq_id 参数

### 变更内容
为人脸管理所有 handler 方法的响应消息添加 `seq_id` 字段支持。每个 handler 在入口处从 `msg_json` 中提取 `seq_id`，并在调用 `_send_response()` 时传入，确保 App 端能够通过 `seq_id` 匹配请求与响应。

### 实现功能
完善协议 v2.2 的 `server_ack` 消息确认机制在人脸管理接口中的覆盖。此前人脸管理相关的响应缺少 `seq_id`，导致 App 端无法将响应与对应请求关联。修改后所有人脸管理操作（录入、查询、删除、权限更新、到访记录查询）的响应均携带 `seq_id`，支持 App 端的消息匹配和防重放校验。


## 2025-05-19 TTS 提供者工厂函数

### 修改文件
- `main/xiaozhi-server/core/providers/tts/base.py`

### 修改位置
- 文件末尾新增模块级函数 `get_tts_provider()`（在 `TTSProviderBase` 类定义之后）

### 变更内容
- 新增 `get_tts_provider(config, logger_instance=None)` 工厂函数
- 该函数根据系统配置（`selected_module.TTS`）动态创建对应的 TTS 提供者实例
- 内部调用 `core.utils.tts.create_instance()` 完成实例化

### 实现功能
- 为门锁模块（人脸识别、欢迎词播放等场景）提供统一的 TTS 实例获取接口
- 解耦门锁模块与具体 TTS 实现，通过配置驱动选择 TTS 服务商

## 2025-05-19 智能门锁AI模块导入日志级别调整

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/eventReportHandler.py`

### 修改位置
- `eventReportHandler.py` 第 320 行，`ImportError` 异常处理分支

### 变更内容
- 将智能门锁AI模块导入失败时的日志级别从 `debug` 提升为 `warning`
- 日志消息从 "智能门锁AI模块未安装" 改为 "智能门锁AI模块导入失败"

### 实现功能
- 提高模块导入失败时的日志可见性，便于运维排查问题。`debug` 级别在生产环境通常不输出，改为 `warning` 后能确保导入失败信息在常规日志中可见，帮助快速定位依赖缺失或配置错误。


---

### 2025-01-XX - 优化看护模式状态检查方式

**修改文件**: `main/xiaozhi-server/core/handle/textHandler/eventReportHandler.py`

**修改位置**: `eventReportHandler.py` 第 294-298 行附近，访客到访处理流程中检查看护模式状态的逻辑

**修改时间**: 2025-01-XX

**变更内容**:
- 移除了通过创建 `PackageGuardManager` 实例来检查看护模式状态的方式
- 改为直接从 `config.package_guard_active` 读取看护模式激活状态

**实现功能**:
- 简化看护模式状态检查逻辑，避免每次访客到访事件都创建完整的 `PackageGuardManager` 管理器实例
- 直接从配置对象中读取看护模式状态，减少不必要的对象创建开销，提升性能

## 2025-05-19 修复 ESP32 摄像头拍照工具名称匹配

- **修改文件**: `main/xiaozhi-server/core/providers/doorlock/esp32_camera.py`
- **修改位置**: `capture_image` 方法中检查 MCP 工具是否可用的逻辑（约第82行）
- **修改时间**: 2025-05-19
- **变更内容**:
  - 将硬编码的工具名 `capture_image` 改为 `self_camera_take_photo`
  - 原因：ESP32 端实际注册的工具名为 `self.camera.take_photo`，经过 sanitize 处理后变为 `self_camera_take_photo`
  - 更新了错误日志信息，显示实际检查的工具名以便调试
- **实现功能**: 修复了因工具名不匹配导致无法调用 ESP32 摄像头拍照功能的问题，使服务端能正确识别并调用设备端的拍照工具

## 2025-05-19 vision_handler 门锁拍照回调通知

### 修改文件
- `main/xiaozhi-server/core/api/vision_handler.py`

### 修改位置
- `VisionHandler` 类中图片上传处理逻辑，在图片格式验证通过后、base64 编码之前新增代码块

### 变更内容
- 新增门锁图片上传回调通知逻辑
- 当图片上传时，检查是否有等待中的门锁拍照请求（通过 `SimpleHttpServer` 的 `image_upload_handler` 中的 `upload_callbacks` 字典）
- 如果当前 `device_id` 存在对应的回调函数，则异步调用该回调，将图片数据传递给门锁模块

### 实现功能
- 打通视觉图片上传接口与门锁拍照请求的联动：当 ESP32 设备通过 HTTP 接口上传拍照图片时，自动通知门锁模块的等待回调，使门锁 AI 能够获取到实时拍摄的图片进行人脸识别或访客分析
- 该逻辑为非关键路径，失败时仅记录 debug 日志，不影响正常的图片上传流程

## 2025-05-19 ESP32 摄像头拍照请求改为异步非阻塞

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/esp32_camera.py`

### 修改位置
- `capture_image` 方法中步骤 3（通过 MCP 调用拍照工具）的逻辑

### 变更内容
- 将 MCP 拍照请求从同步等待改为异步非阻塞方式
- 原逻辑：直接 `await call_mcp_tool()`，等待 MCP 工具返回结果后再继续
- 新逻辑：将 MCP 调用封装为内部异步函数 `_send_mcp_capture()`，通过 `asyncio.create_task()` 异步触发，不阻塞主流程
- MCP 调用异常降级为 debug 日志（不影响图片获取流程）
- 移除了 MCP 调用失败时的清理和提前返回逻辑

### 实现功能
- 优化拍照流程性能：MCP 拍照请求只需触发 ESP32 拍照动作，无需等待 MCP 工具的文本返回结果
- 主流程直接进入步骤 4（等待照片上传），减少不必要的阻塞等待时间
- 提高拍照响应速度，因为实际照片是通过 HTTP 上传回调获取的，与 MCP 返回值无关


## 2025-05-19 简化 PIR 触发处理逻辑（拍照优先）

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/eventReportHandler.py`

### 修改位置
- `EventReportHandler` 类中的 `_trigger_face_recognition` 方法（重构）
- 新增 `_forward_photo_to_apps` 方法

### 变更内容
1. **重构 `_trigger_face_recognition` 方法**：
   - 移除了完整的智能门锁 AI 处理流程（数据库配置检查、意图识别处理器创建、看护模式检查、访客处理等）
   - 简化为仅执行 PIR 触发拍照功能
   - 使用 `ESP32CameraService` 进行拍照
   - 拍照成功后保存照片到本地，并转发给关联的 App

2. **新增 `_forward_photo_to_apps` 方法**：
   - 将拍摄的照片通过 WebSocket 转发给所有关联的 App 客户端
   - 使用 base64 编码图片数据
   - 构造 `visitor_photo` 类型的通知消息

3. **移除的功能**：
   - 类级别缓存机制（`_db_instances`、`_intent_handlers`、定期清理逻辑）
   - `DoorlockDatabase` 配置查询
   - `DoorlockIntentHandler` 意图识别处理
   - 看护模式（`package_guard_active`）检查

### 实现功能
将 PIR（被动红外传感器）触发后的处理逻辑从"完整智能门锁 AI 流程"简化为"拍照 + 转发"模式。当前阶段仅实现拍照和照片推送功能，后续再集成人脸识别和意图对话，降低了模块耦合度和复杂度。


## 2025-05-19 eventReportHandler.py - PIR触发处理升级为智能门锁AI处理流程

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/eventReportHandler.py`

### 修改位置
- `EventReportHandler` 类中的 `_handle_pir_trigger_photo` 方法（重构）
- 删除了 `_forward_photo_to_apps` 方法

### 变更内容
1. **方法重构**：将 `_handle_pir_trigger_photo` 从单纯的"PIR触发拍照"升级为"统一的人脸识别触发方法"
2. **集成智能门锁AI功能**：
   - 新增设备配置检查（`face_recognition_enabled`, `intent_recognition_enabled`）
   - 新增看护模式状态检查（`package_guard_active`）
   - 集成 `DoorlockIntentHandler` 意图识别处理器
   - 如果看护模式激活，同时启动监控和对话
3. **性能优化**：
   - 使用类级别缓存（`_db_instances`, `_intent_handlers`）避免每次PIR事件重新加载配置和创建实例
   - 定期清理缓存（每小时一次），防止内存泄漏
4. **删除旧逻辑**：
   - 移除了直接调用 `ESP32CameraService` 拍照的逻辑
   - 移除了 `_forward_photo_to_apps` 方法（照片转发功能已由 `DoorlockIntentHandler` 内部处理）

### 实现功能
将PIR/门铃触发事件从简单的拍照转发，升级为完整的智能门锁AI处理流程：自动进行人脸识别、访客意图识别对话、快递看护监控等，实现了 smart-doorlock-ai spec 中定义的核心触发逻辑。

## 2025-05-19 门锁拍照模式跳过VLLM分析优化

### 修改文件
- `main/xiaozhi-server/core/api/vision_handler.py`

### 修改位置
- `vision_handler.py` 中图片上传处理逻辑（约第90-126行），门锁拍照回调通知部分

### 变更内容
1. 新增 `doorlock_capture_active` 标志变量，用于标识当前是否为门锁拍照请求
2. 将门锁拍照回调从 `asyncio.create_task` 异步触发改为 `await` 同步等待，确保回调完成后再继续
3. 当检测到门锁拍照回调活跃时，直接返回"拍照完成"成功响应，跳过后续的 VLLM 视觉分析流程
4. 提升日志级别：回调成功从 `debug` 改为 `info`，回调失败从 `debug` 改为 `warning`

### 实现功能
- **门锁拍照模式与VLLM分析解耦**：当设备处于门锁拍照模式时（有等待中的拍照回调），图片数据仅传递给门锁处理流程，不再额外调用 VLLM 进行视觉分析，避免不必要的 AI 推理开销和潜在的逻辑冲突
- **同步回调保证数据一致性**：使用 `await` 替代 `create_task`，确保图片数据完整传递给门锁回调后再返回响应

## 2025-05-19 PIR 超时判断时间基准统一修复

### 修改文件
- `main/xiaozhi-server/core/utils/pir_utils.py`

### 修改位置
- `is_pir_timeout()` 函数：超时计算逻辑
- `update_pir_state()` 函数：PIR 状态更新逻辑

### 变更内容
1. **`is_pir_timeout()`**：将时间计算从毫秒时间戳改为直接使用 `time.time()` 秒级时间戳，与 `last_pir_time` 存储格式保持一致
2. **`update_pir_state()`**：移除 `ts` 参数的默认值逻辑，改为始终使用服务器系统时间 `time.time()` 记录上报时刻；`ts` 参数仅作记录用途，不再参与超时判断

### 实现功能
统一 PIR（人体红外传感器）超时判断的时间基准，使用服务器系统时间替代 ESP32 设备时间戳。解决了因设备时间与服务器时间不一致可能导致的超时判断错误问题，确保 `update_pir_state` 记录时间和 `is_pir_timeout` 判断时间使用同一基准。

## 2025-05-19 PIR 人脸识别流程改为后台任务

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/eventReportHandler.py`

### 修改位置
- `EventReportHandler` 类中处理 PIR 事件的逻辑（步骤 6：触发人脸识别流程）

### 变更内容
- 将 `_trigger_face_recognition` 的调用从同步等待（`await`）改为通过 `asyncio.create_task()` 创建后台任务执行
- 将原来的 `try-finally` 块封装到内部异步函数 `_run_face_recognition()` 中
- 访客处理标志 `conn.visitor_processing` 的清除逻辑保持不变，仍在 `finally` 中执行

### 实现功能
- **解除消息处理循环阻塞**：人脸识别流程不再阻塞主消息处理循环，后续的 PIR 事件仍能被正常接收和处理
- **PIR 状态持续更新**：`update_pir_state` 能在人脸识别进行期间继续更新，避免因识别耗时导致 PIR 状态丢失
- **提升并发处理能力**：设备在人脸识别期间仍可响应其他事件上报



## 2025-01-XX doorlock_intent_handler 发送方式修复

- **文件**: `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`
- **位置**: 第 828 行附近，发送 `face_result` 消息的代码
- **时间**: 2025-01-XX
- **变更内容**: 将 `await conn.send_json(face_result_msg)` 修改为 `await conn.websocket.send(json.dumps(face_result_msg))`
- **功能说明**: 修复了 face_result 消息发送方式，改用底层 WebSocket 直接发送 JSON 序列化后的消息，而非调用连接对象的 `send_json` 方法。这可能是因为 `conn` 对象（ESP32 连接）没有 `send_json` 方法，或者需要绕过该方法的额外处理逻辑，直接通过 WebSocket 发送原始 JSON 字符串以确保消息能正确送达设备端。

### 2025-05-19 SessionManager 构造函数参数简化

- **修改文件**: `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`
- **修改位置**: `doorlock_intent_handler.py` 第 107 行，`SessionManager` 实例化处
- **修改时间**: 2025-05-19
- **变更内容**: 移除 `SessionManager()` 构造时传入的 `logger_instance` 参数，由 `SessionManager(logger_instance)` 改为 `SessionManager()`
- **实现功能**: 简化 `SessionManager` 的初始化方式，使其不再依赖外部传入的 logger 实例（可能改为内部自行初始化日志，或已不再需要该参数）

## 2025-05-19 人脸识别重试拍照优化

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/face_recognition_handler.py`

### 修改位置
- `FaceRecognitionHandler` 类中的人脸识别重试逻辑（约第 81-120 行）

### 变更内容
1. **重试时重新拍照**：第一次识别使用传入的照片，后续重试时通过 `ESP32CameraService.capture_image()` 重新拍照
2. **日志级别提升**：将人脸识别尝试的日志从 `debug` 提升为 `info`，并增加照片大小信息
3. **容错处理**：重试拍照失败时回退使用上一张照片，不中断识别流程
4. **使用 `current_jpeg` 变量**：替代原来固定使用 `jpeg_data`，支持每次重试使用最新拍摄的照片

### 实现功能
优化人脸识别的重试机制——当首次识别失败需要重试时，不再重复使用同一张可能质量不佳的照片，而是重新调用 ESP32 摄像头拍摄新照片进行识别，提高重试成功率。同时增加了完善的异常处理，确保拍照失败时不影响整体识别流程。

## 2025-05-19 人脸识别照片保存功能

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/face_recognition_handler.py`

### 修改位置
- `face_recognition_handler.py` 中人脸识别流程，在调用人脸识别服务之前（约第 116 行之后）新增照片保存逻辑

### 修改时间
- 2025-05-19

### 变更内容
- 在 PIR 触发人脸识别流程中，于调用 `face_service.recognize()` 之前，新增将当前抓拍的 JPEG 照片保存到磁盘的逻辑
- 保存路径为 `data/face_recognition/visits/YYYY-MM/` 目录，文件名格式为 `pir_{device_id}_{时间戳}_attempt{次数}.jpg`
- 使用 `pathlib.Path` 自动创建目录结构
- 保存失败时仅记录警告日志，不影响主流程

### 实现功能
- 为人脸识别过程提供照片持久化存储，便于后续调试和回溯分析
- 按月份分目录存储，文件名包含设备 ID、时间戳和尝试次数，方便定位问题

## 2025-05-19

### 新增文件：`main/xiaozhi-server/test_face_recognition.py`

- **修改时间**：2025-05-19
- **变更位置**：新增独立测试脚本文件
- **变更内容**：
  - 新增人脸识别测试脚本，包含三个测试函数：
    1. `test_face_detection()`：遍历 `data/face_recognition/faces` 目录，检测每张注册照片中是否能识别到人脸，输出图片大小、尺寸、检测到的人脸数量和编码维度
    2. `test_self_recognition()`：加载所有注册人脸编码，进行两两距离比对（tolerance=0.6），验证同一人的照片能否匹配
    3. `test_with_database()`：通过 `FaceService` 完整流程测试识别，验证从 JPEG 数据到人员匹配的端到端功能
  - 使用 `face_recognition` 库的 `hog` 模型进行人脸检测
  - 使用 `PIL` 加载图片并转为 numpy 数组
- **实现功能**：提供人脸识别功能的本地验证工具，用于测试已注册照片能否被正确检测和识别，便于调试人脸识别服务的准确性

## 2025-07-15

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/face_service.py`

### 修改位置
- `FaceService` 类的 `_jpeg_to_numpy` 方法

### 变更内容
- 在将 JPEG 图片转换为 numpy 数组时，增加了 `image.rotate(180)` 旋转操作
- 更新了方法的 docstring，说明猫眼摄像头拍摄的图片是倒置的

### 实现功能
- 修复猫眼摄像头图片倒置问题：猫眼摄像头拍摄的照片是上下颠倒的，导致人脸识别无法正确检测到人脸。通过旋转 180° 将图片恢复正常方向，使 face_recognition 库能够正确检测和识别人脸。

## 2025-05-19 人脸识别图片方向自适应优化

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/face_service.py`

### 修改位置
- `FaceService` 类的 `_jpeg_to_numpy` 方法

### 修改时间
- 2025-05-19

### 变更内容
- 将原来固定旋转180°的逻辑改为自适应检测策略
- 先用原图进行人脸检测，如果能检测到人脸则直接使用原图
- 如果原图检测不到人脸，再旋转180°后重试

### 实现功能
- 解决猫眼摄像头图片方向不确定的问题：之前假设所有图片都是倒置的并固定旋转180°，但实际上部分图片可能是正向的，固定旋转反而导致人脸检测失败
- 通过"先原图检测、检测不到再旋转"的策略，兼容正向和倒置两种情况，提高人脸识别成功率


## 2025-05-19 简化人脸图像预处理逻辑

- **修改文件**：`main/xiaozhi-server/core/providers/doorlock/face_service.py`
- **修改位置**：`FaceService` 类的 `_jpeg_to_numpy` 方法
- **修改时间**：2025-05-19
- **变更内容**：移除了"先尝试原图检测人脸，检测不到再旋转180°"的双重检测逻辑，改为直接旋转180°后返回图像数组。原先的实现会先用原图调用 `face_recognition.face_locations()` 检测，如果检测不到人脸才旋转；现在统一旋转180°，不再做额外的检测尝试。
- **实现功能**：因为猫眼摄像头拍摄的图片始终是倒置的，无需先尝试原图检测，直接旋转180°即可。此修改减少了不必要的人脸检测调用，提升了识别流程的性能，同时简化了代码逻辑。

## 2025-05-19

### 修改文件
- `main/xiaozhi-server/core/connection.py`

### 修改位置
- 视频帧处理逻辑（约第 480 行），监控视频转发部分（`is_video` 分支内）

### 变更内容
- 将原来直接转发完整 BinaryProtocol2 视频帧的逻辑，改为先对 JPEG payload 进行 180° 旋转，再重新组装帧头后转发
- 使用 PIL (Pillow) 库解码 JPEG → 旋转 180° → 重新编码为 JPEG（quality=85）
- 重新组装 BinaryProtocol2 帧头（保留 version、msg_type、reserved、timestamp，更新 payload_size）
- 添加异常处理：旋转失败时回退到转发原始帧

### 实现功能
- 修复猫眼摄像头图像倒置问题：猫眼摄像头安装后采集的画面是上下颠倒的，服务端在转发视频流给 App 前自动旋转 180°，使 App 端显示正确方向的画面

## 2025-05-19 人脸识别重试提示语音统一化

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/face_recognition_handler.py`

### 修改位置
- `face_recognition_handler.py` 中人脸识别重试逻辑（约第 163 行和第 173 行）

### 变更内容
1. 第一次识别失败时的语音提示：将 `self._play_retry_prompt(device_id)` 替换为 `self._play_tts(conn, "人脸识别失败，请正视摄像头重试")`
2. 三次识别全部失败时的语音提示：将 `self._play_final_failure_prompt(device_id)` 替换为 `self._play_tts(conn, "人脸识别失败，请使用其他方式解锁")`

### 实现功能
统一人脸识别失败时的语音播报方式，使用通用的 `_play_tts(conn, text)` 方法替代原有的专用提示方法（`_play_retry_prompt` 和 `_play_final_failure_prompt`），简化代码结构，同时通过直接传入连接对象 `conn` 确保 TTS 播报能正确发送到对应设备。

## 2025-05-19 主动问候 TTS 播放实现

### 修改文件
- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

### 修改位置
- `doorlock_intent_handler.py` 中播放主动问候的逻辑（约第 666 行附近）

### 变更内容
- 将原来的 TODO 注释替换为实际的 TTS 播放调用
- 通过设备连接对象的 `tts` 属性调用 `tts_one_sentence` 方法
- 引入 `ContentType.TEXT` 指定内容类型为文本

### 实现功能
- 当门锁识别到访客并生成主动问候语后，现在能够通过 TTS 服务将问候语实际播放出来（之前仅有 TODO 占位，未真正播放语音）

## 2025-05-19

### 修改文件
- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

### 修改位置
- `_start_intent_dialogue` 方法内，第398行，调用 `_play_initial_greeting` 处

### 变更内容
- 将 `_play_initial_greeting(device_id, person_info)` 调用补充了第三个参数 `conn`，改为 `_play_initial_greeting(device_id, person_info, conn)`

### 实现功能
- 修复意图识别对话启动时，主动问候播放缺少连接对象的问题。`conn` 参数用于 TTS 服务，传递后可确保问候语音能通过正确的连接通道发送给设备端播放。此前缺少该参数会导致 TTS 播放时无法获取连接上下文，可能造成问候语音无法正常下发。


## 2025-05-19 greeting_handler.py 欢迎词播放方式重构

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/greeting_handler.py`

### 修改位置
- `play_greeting` 方法：函数签名新增 `conn` 参数；方法体中替换了 TTS 语音生成与播放逻辑

### 变更内容
1. `play_greeting` 方法新增 `conn` 参数，用于接收设备连接对象
2. 移除原有的 `_generate_tts` 调用和 TODO 占位逻辑
3. 改为通过 `conn.tts.tts_one_sentence()` 直接调用连接对象上的 TTS 实例播放欢迎词
4. 当连接对象无 TTS 实例时，降级为 warning 日志（原为 error）

### 实现功能
将欢迎词播放从"生成音频数据后手动发送"改为直接利用设备连接自带的 TTS 服务进行播放，完成了欢迎词 TTS 播放的实际集成，消除了之前的 TODO 占位代码。

## 2025-05-19

### 修改文件
- `main/xiaozhi-server/core/providers/tts/huoshan_double_stream.py`

### 修改位置
- `HuoshanDoubleStreamTTS` 类的 `text_to_speak` 方法，WebSocket 连接检查逻辑处

### 修改时间
- 2025-05-19

### 变更内容
- 当 `self.ws` 为 `None` 时，新增调用 `_ensure_connection()` 尝试重新建立 WebSocket 连接
- 仅在重连失败后（`self.ws` 仍为 `None`）才终止文本发送
- 日志信息从"WebSocket连接不存在"改为"WebSocket连接建立失败"

### 实现功能
- 火山引擎双流 TTS 的 WebSocket 自动重连机制：当连接意外断开时，`text_to_speak` 方法会自动尝试重建连接，而非直接放弃，提高了 TTS 服务的稳定性和容错能力

### 2025-07-15

#### 修改文件
- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

#### 修改位置
- `doorlock_intent_handler.py` 中组件初始化区域（约第 106 行），`GreetingHandler` 实例化语句

#### 变更内容
- 将 `GreetingHandler` 的构造参数从 `(config, logger_instance)` 改为 `(doorlock_database, tts_provider)`
- 调整初始化顺序：`greeting_handler` 移至 `doorlock_database` 创建之后

#### 实现功能
- 重构 `GreetingHandler` 依赖注入，使其直接持有数据库实例和 TTS 提供者，支持问候处理器直接查询用户信息并合成语音回复


## 2025-05-19 doorlock_intent_handler.py 文件保存（无实质变更）

### 修改文件
- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

### 修改位置
- 无具体修改位置（文件被保存但 diff 为空）

### 修改时间
- 2025-05-19

### 变更内容
- 文件触发了编辑事件但无实际内容变更（空 diff），可能为编辑器自动保存或格式化操作

### 实现功能
- 无功能变更。文件当前包含完整的智能门锁意图识别对话处理器，支持：访客到访主流程处理、人脸识别（含重试）、意图识别对话循环、统一看护对话模式、定时拍照任务管理、对话结束后处理（快递检查+意图总结+数据库保存+App通知）、工具调用处理等功能

---

### 2025-05-19 门锁意图对话结束后停止麦克风录制

**修改文件**: `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

**修改位置**: `handle_visitor_arrival` 方法中，`start_intent_dialogue` 调用完成后、`cleanup_session` 之前（约第 280 行）

**变更内容**: 新增一行调用 `await self._send_stop_listening(conn)`，在意图对话结束后通知 ESP32 停止麦克风录制。

**实现功能**: 当门锁访客意图对话流程结束后，主动向 ESP32 设备发送停止监听指令，确保设备在对话完成后不再持续录音，释放麦克风资源，避免不必要的音频采集。

## 2025-05-19 新增 `_send_stop_listening` 方法

- **文件**: `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`
- **位置**: `DoorlockIntentHandler` 类中，`_wait_for_visitor_response` 方法之前（约第 692 行）
- **时间**: 2025-05-19
- **变更内容**: 新增 `_send_stop_listening(self, conn)` 异步方法
- **功能说明**: 对话结束后通知 ESP32 停止麦克风录制，让设备退出唤醒状态。通过 WebSocket 发送 `{"type": "system", "command": "stop_listening"}` 消息给 ESP32，包含连接可用性检查和异常处理。

## 2025-05-19 访客对话 ASR 集成

### 修改文件
- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

### 修改位置
- `_wait_for_visitor_response` 方法（约第714行）

### 变更内容
- 移除了原有的 TODO 占位逻辑（简单 sleep 后返回 None）
- 实现了基于 `asyncio.Queue` 的 ASR 结果接收机制
- 新增 `conn._doorlock_asr_queue` 队列，用于接收 ASR 识别结果
- 新增 `conn._doorlock_dialogue_active` 标志，标记门锁对话模式激活状态
- 使用 `asyncio.wait_for` 实现超时等待

### 实现功能
实现了门锁访客对话场景下的真实语音识别集成。通过在连接对象上挂载 asyncio.Queue，拦截 ESP32 持续发送的音频流经 VAD 检测和 ASR 转写后的文本结果，使门锁意图处理器能够获取访客的实际语音回复，替代了之前的空实现占位代码。设置 `_doorlock_dialogue_active` 标志让 `startToChat` 流程将 ASR 结果重定向到此队列，实现对话流程的正确拦截。

## 2025-05-19 门锁对话模式标志清除

### 修改文件
- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

### 修改位置
- `_notify_stop_listening` 方法内部，在发送 stop_listening 之前新增逻辑

### 变更内容
- 在 `_notify_stop_listening` 方法中增加了清除门锁对话模式标志（`_doorlock_dialogue_active`）的逻辑
- 对话结束通知 ESP32 停止麦克风录制时，同时将连接对象上的 `_doorlock_dialogue_active` 属性设为 `False`

### 实现功能
- 确保门锁对话结束后，连接对象上的对话模式标志被正确清除，避免后续逻辑误判设备仍处于门锁对话状态

## 2025-05-19

### 修改文件
- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

### 修改位置
- `start_intent_dialogue` 方法内，`try` 块开头（步骤1之前新增步骤0）

### 修改时间
- 2025-05-19

### 变更内容
- 在意图识别对话启动流程中，在播放主动问候（步骤1）之前，新增步骤0：调用 `_send_start_listening(conn)` 通知 ESP32 进入唤醒状态（开始录音）

### 实现功能
- 确保 ESP32 在门锁意图识别对话开始前先进入录音状态，避免问候语播放后 ESP32 尚未准备好接收访客语音回复的时序问题


## 2025-05-19 VLLM 意图识别优化：后续轮次不传图片

### 修改文件
- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

### 修改位置
- `doorlock_intent_handler.py` 中意图识别调用 VLLM 的逻辑（约第 456 行附近）

### 变更内容
- 将原来每轮对话都传递图片给 VLLM 的逻辑，改为仅第一轮（`dialogue_count == 0`）传递 Base64 图片
- 后续轮次（`dialogue_count > 0`）调用 `analyze_intent` 时 `visitor_image` 传 `None`，不再携带图片

### 实现功能
- **节省 Token 开销**：多轮对话中，只有首轮需要图片进行视觉分析，后续轮次为纯文本意图识别，避免重复传输图片浪费 Token
- 保持首轮带图片的完整视觉分析能力不变


## 2025-05-19 临时禁用首轮图片传递

- **修改文件**：`main/xiaozhi-server/core/handle/doorlock_intent_handler.py`
- **修改位置**：`doorlock_intent_handler.py` 中意图识别对话循环内，VLLM 调用逻辑（约第457-472行）
- **修改时间**：2025-05-19
- **变更内容**：移除了根据 `dialogue_count` 判断是否传递图片的分支逻辑，改为所有轮次统一不传递 `visitor_image`（设为 `None`）。原先第一轮对话会将访客图片 base64 编码后传给 VLLM 进行带图分析，后续轮次不传图片；现在所有轮次均不传图片。
- **实现功能**：临时规避图片格式问题，避免因图片传递导致 VLLM 调用异常。后续待图片格式问题修复后可恢复首轮传图逻辑。


## 2025-05-19 VLLM 意图识别首轮传图优化

### 修改文件
- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

### 修改位置
- `doorlock_intent_handler.py` 中 VLLM 意图识别调用逻辑（约第 456-478 行）

### 变更内容
- **之前**：所有对话轮次都不传图片给 VLLM（`visitor_image=None`），注释说明是为了避免图片格式问题
- **之后**：区分首轮和后续轮次：
  - 第一轮（`dialogue_count == 0`）：将访客图片编码为 `data:image/jpeg;base64,...` 格式后传给 VLLM 进行带图意图分析
  - 后续轮次：不传图片，仅用纯文本对话，节省 Token 消耗

### 实现功能
启用了 VLLM 视觉语言模型在首轮对话中的图片分析能力。访客到访时，第一轮意图识别会携带访客照片，让 VLLM 能够结合视觉信息（如访客外貌、是否携带物品等）进行更准确的意图判断；后续轮次则切换为纯文本模式以降低 Token 开销。

## 2025-05-19 修复 VLLM 图片 base64 前缀重复问题

### 修改文件
- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

### 修改位置
- `doorlock_intent_handler.py` 第 458-463 行附近，访客意图对话第一轮图片传递逻辑

### 变更内容
- 移除了手动添加的 `data:image/jpeg;base64,` 前缀
- 改为只传递纯 base64 编码字符串，由下游 `analyze_with_tools` 方法内部自行添加前缀

### 实现功能
- 修复了 VLLM 图片分析时 base64 前缀重复的问题（`analyze_with_tools` 内部已经会添加 `data:image/jpeg;base64,` 前缀，外部再加一次会导致格式错误）

## 2025-05-19 doorlock_intent_handler TTS 播放实现

### 修改文件
- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

### 修改位置
- `_play_ai_response` 方法（约第798行）

### 变更内容
- 将日志级别从 `debug` 提升为 `info`
- 移除原有的 TODO 注释和被注释掉的代码
- 新增实际的 TTS 播放逻辑：检查连接对象是否有 `tts` 实例，若有则调用 `tts_one_sentence` 播放语音回复；若无则输出警告日志

### 实现功能
- 实现了门锁意图处理器中 AI 回复的语音播放功能，使设备在门锁对话场景下能够通过 TTS 服务将 AI 生成的文本回复转为语音播放给用户

### 2025-07-15

#### `core/handle/doorlock_intent_handler.py`
- **修改位置**: `DoorlockIntentHandler._check_pir_status` 方法
- **变更内容**: 
  - 方法签名新增 `conn` 可选参数
  - 移除 TODO 占位逻辑（原先硬编码返回 True）
  - 当传入 conn 时，调用 `core.utils.pir_utils.check_pir_status(conn, timeout=5.0)` 进行实际 PIR 传感器状态检测
  - 无 conn 时保持向后兼容，仍返回 True
- **实现功能**: 实现了真实的 PIR（被动红外）人体传感器状态检查，使门锁意图处理器能够通过设备连接获取实际的人体检测结果，而非始终假设有人在场


## 2025-05-19

### 修改文件
- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

### 修改位置
- `doorlock_intent_handler.py` 第 427 行附近，`_check_pir_status` 方法调用处

### 变更内容
- 将 `self._check_pir_status(device_id)` 调用改为 `self._check_pir_status(device_id, conn)`，新增传入 `conn` 参数

### 实现功能
- 修复 PIR 状态检查时缺少数据库连接参数的问题，确保 `_check_pir_status` 方法能复用已有的数据库连接，避免重复创建连接或因缺少连接导致查询失败


## 2025-05-19 修复门锁意图处理器 TTS 播放流程

### 修改文件
- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

### 修改位置
- `doorlock_intent_handler.py` 中 TTS 播放逻辑部分（约第 806 行起）

### 变更内容
- **移除**：原先使用 `tts_one_sentence()` 单句播放方式
- **新增**：改用 `tts_text_queue` 队列方式发送 TTS 消息，按照 FIRST → MIDDLE → LAST 三段式流程：
  1. 发送 `SentenceType.FIRST` 消息（触发 `tts_audio_first_sentence = True`，确保发送 `tts:start` 信号）
  2. 发送 `SentenceType.MIDDLE` 消息（携带实际文本内容）
  3. 发送 `SentenceType.LAST` 消息（触发 `tts:stop`，ESP32 恢复录音）
- 新增 `uuid` 生成 `sentence_id`，并设置到 `conn.sentence_id`

### 实现功能
修复门锁 AI 回复播放时 ESP32 端无法正确接收 TTS 开始/结束信号的问题。通过标准的三段式 TTS 队列流程，确保 ESP32 能收到 `tts:start` 和 `tts:stop` 控制信号，从而正确管理录音状态（播放时停止录音，播放结束后恢复录音）。


## 2025-05-19 修复主动问候 TTS 播放方式

### 修改文件
- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

### 修改位置
- `_play_greeting` 方法（约第 687 行），修改 TTS 播放调用方式

### 变更内容
- 移除了直接调用 `conn.tts.tts_one_sentence()` 的方式
- 改为调用 `self._send_tts_complete(conn, greeting)`，遵循正常对话流程（FIRST → MIDDLE → LAST）

### 实现功能
- 主动问候的 TTS 播放现在遵循完整的对话流程（FIRST → MIDDLE → LAST 分段发送），与系统其他 TTS 播放保持一致，避免因直接调用单句 TTS 导致的播放异常或状态不同步问题。


## 2025-05-19

### 重构：`_play_ai_response` 方法 TTS 调用简化

- **文件**：`main/xiaozhi-server/core/handle/doorlock_intent_handler.py`
- **位置**：`DoorlockIntentHandler._play_ai_response()` 方法（约第 840 行）
- **时间**：2025-05-19
- **变更内容**：将 `_play_ai_response` 中手动构建 TTS 三段式消息（FIRST → MIDDLE → LAST）的 30 行重复代码，替换为调用已有的 `_send_tts_complete(conn, response)` 方法（单行调用）
- **实现功能**：消除重复代码，统一 TTS 播放逻辑。`_send_tts_complete` 已封装了完整的 TTS 会话流程（生成 sentence_id、发送 FIRST/MIDDLE/LAST 消息），此次重构让 `_play_ai_response` 复用该方法，提高代码可维护性


## 2025-05-19 修复 doorlock_intent_handler TTS 消息类型

### 修改文件
- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

### 修改位置
- `_speak_to_visitor` 方法（或类似的 TTS 播放方法）中，FIRST / LAST 消息的构造逻辑（约第 705-732 行）

### 修改时间
- 2025-05-19

### 变更内容
1. **FIRST 消息**：`content_type` 从 `ContentType.TEXT` 改为 `ContentType.ACTION`，并移除了空字符串 `content_detail=""`
2. **LAST 消息**：`content_type` 从 `ContentType.TEXT` 改为 `ContentType.ACTION`，并移除了空字符串 `content_detail=""`
3. **MIDDLE 消息**：保持不变，仍为 `ContentType.TEXT` 携带实际文本内容
4. 注释更新：更清晰地标注了每个消息的用途（ACTION 用于状态切换，TEXT 用于实际内容）

### 实现功能
修正 TTS 队列中 FIRST 和 LAST 帧的消息类型。FIRST 和 LAST 帧的作用是触发 ESP32 的播放/录音模式切换（属于控制动作），不携带实际文本内容，因此应使用 `ContentType.ACTION` 而非 `ContentType.TEXT`。这样可以避免 TTS 引擎对空文本进行不必要的合成处理，使语义更准确、流程更高效。

## 2025-05-19 优化 `_send_tts_complete` 方法注释

**修改文件**：`main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

**修改位置**：`_send_tts_complete` 方法的 docstring 及内部注释

**修改时间**：2025-05-19

**变更内容**：
- 重写了 `_send_tts_complete` 方法的文档字符串，补充了正常对话中的消息序列说明（tts:start → sentence_start → 音频 → tts:stop）
- 明确了门锁场景中每次 AI 回复作为完整会话的流程：FIRST(ACTION) → MIDDLE(TEXT) → LAST(ACTION)
- 新增了连续播放多句时通过 `tts_audio_queue` 阻塞机制自动排队的说明
- 精简了 FIRST 和 LAST 步骤的行内注释，使其更准确：
  - FIRST: "初始化 TTS 状态"（去掉了"触发 tts:start"）
  - LAST: "结束当前会话，触发 tts:stop"（原为"处理剩余文本，触发 tts:stop"）

**实现功能**：提升代码可读性，让开发者更清晰地理解门锁场景下 TTS 播放的完整流程和排队机制，便于后续维护和调试。


## 2025-05-19 人脸识别失败时移除 TTS 语音播放

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/face_recognition_handler.py`

### 修改位置
- `face_recognition_handler.py` 中人脸识别重试逻辑部分（约第 158-180 行）

### 变更内容
1. **第一次识别失败时**：移除了 `await self._play_tts(conn, "人脸识别失败，请正视摄像头重试")` 调用，改为仅记录日志。原因是此时 ESP32 尚未唤醒，无法播放语音。
2. **三次识别全部失败时**：移除了 `await self._play_tts(conn, "人脸识别失败，请使用其他方式解锁")` 调用，改为记录日志。语音提示改由后续 `start_listening` 之后的对话流程统一处理。

### 实现功能
优化人脸识别失败时的交互逻辑：在 ESP32 未唤醒阶段不再尝试播放 TTS 语音（避免无效调用或报错），将语音提示的职责延后到设备唤醒并进入意图对话流程后统一处理，使流程更加合理。
