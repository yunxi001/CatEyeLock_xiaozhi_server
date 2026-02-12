# Implementation Plan

- [x] 1. 基础设施搭建
  - [x] 1.1 创建数据库迁移脚本
    - 创建 `migrations/add_doorlock_ai_tables.sql`
    - 扩展 persons 表添加 is_owner BOOLEAN 和修改 custom_greeting TEXT
    - 创建 doorlock_config 表（device_id, intent_recognition_enabled, package_guard_available, package_guard_active, package_baseline_image, package_guard_start_time）
    - 创建 doorlock_visitor_intents 表（id, visit_id, session_id, person_id, intent_type, intent_summary, dialogue_history）
    - 创建 doorlock_package_alerts 表（id, device_id, session_id, threat_level, action, description, photo_path, voice_warning_sent, notified）
    - 添加索引 idx_device_time (device_id, created_at) 到 doorlock_package_alerts
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 13.1, 13.2, 13.3, 14.1, 14.2, 14.3, 14.4, 14.5_

  - [x] 1.2 创建数据库迁移执行和验证脚本
    - 创建 `migrations/run_doorlock_ai_migration.py`
    - 创建 `migrations/verify_doorlock_ai_migration.py`
    - 实现表结构验证、索引验证、外键验证
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [x] 1.3 创建配置文件
    - 在 `config.yaml` 中添加 doorlock 配置段（package_guard, intent_recognition, face_recognition, performance）
    - 创建 `config/doorlock_prompts.yaml` 提示词配置文件
    - 创建 `config/doorlock_prompts.yaml.example` 模板文件
    - 配置看护模式参数（photo_interval: 5, baseline_dir）
    - 配置意图识别参数（dialogue_timeout: 30, max_dialogue_rounds: 10）
    - 配置人脸识别参数（max_retries: 3, retry_interval: 1）
    - 配置性能参数（max_token_usage_ratio: 0.8, session_cleanup_delay: 0）
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.2, 7.3, 7.4, 19.6_

  - [x] 1.4 创建数据模型
    - 创建 `core/providers/doorlock/models.py`
    - 定义 DoorlockConfig 数据类（device_id, intent_recognition_enabled, package_guard_available, package_guard_active, package_baseline_image, package_guard_start_time）
    - 定义 VisitorIntent 数据类（id, visit_id, session_id, person_id, intent_type, intent_summary, dialogue_history, created_at）
    - 定义 PackageAlert 数据类（id, device_id, session_id, threat_level, action, description, photo_path, voice_warning_sent, notified, created_at）
    - 定义 DoorlockSession 数据类（session_id, device_id, dialogue_history, photo_records, last_activity, created_at）
    - 添加 JSON 序列化/反序列化方法
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 10.1, 10.2, 10.3, 14.1, 14.2, 14.3, 14.4_

  - [x] 1.5 Checkpoint - 确保基础设施正常
    - 数据库表创建成功
    - 配置文件格式正确（YAML 语法验证）
    - 数据模型定义完整且通过类型检查

- [x] 2. 核心服务实现
  - [x] 2.1 实现数据库服务
    - 创建 `core/providers/doorlock/doorlock_database.py`
    - 实现 DoorlockDatabase 类（使用 async/await）
    - 实现 get_config(device_id) - 获取设备配置
    - 实现 update_config(config) - 更新设备配置
    - 实现 save_visitor_intent(intent) - 保存访客意图记录
    - 实现 save_package_alert(alert) - 保存快递警报记录
    - 实现 get_visitor_intents(device_id, limit) - 查询意图识别历史
    - 实现 get_package_alerts(device_id, limit) - 查询快递警报历史
    - 实现 get_person_greeting(person_id) - 获取用户欢迎词配置
    - 实现 update_person_greeting(person_id, greeting) - 更新用户欢迎词配置
    - 添加数据库连接池管理和错误重试机制
    - 使用 loguru 记录所有数据库操作日志
    - _Requirements: 1.1, 1.2, 8.5, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 12.1, 12.2, 12.3, 13.1, 13.2, 13.3, 13.4, 13.5, 14.1, 14.2, 14.3, 14.4, 14.5_

  - [x] 2.2 实现会话管理器
    - 创建 `core/providers/doorlock/session_manager.py`
    - 实现 SessionManager 类（线程安全）
    - 实现 create_session(device_id) - 创建新会话（格式：device_id_timestamp）
    - 实现 get_session(session_id) - 获取会话
    - 实现 update_session(session_id, \*\*kwargs) - 更新会话状态
    - 实现 cleanup_session(session_id) - 清除会话
    - 实现 check_dialogue_end(session_id) - 检查对话是否结束（沉默30秒或PIR无人体）
    - 实现会话存储（内存字典）和并发访问锁
    - 实现对话历史管理（保留最近10轮）
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 2.3 实现看护模式管理器
    - 创建 `core/providers/doorlock/package_guard_manager.py`
    - 实现 PackageGuardManager 类
    - 实现 enable_guard(device_id, reason) - 启用看护模式（检查 package_guard_available）
    - 实现 disable_guard(device_id, reason) - 关闭看护模式
    - 实现 update_baseline(device_id) - 更新基准图片（保存到 data/face_recognition/package_baseline/）
    - 实现 start_monitoring(device_id, session_id) - 启动监控循环（每5秒拍照）
    - 实现 stop_monitoring(device_id) - 停止监控循环
    - 实现 is_active(device_id) - 检查看护模式是否激活
    - 实现基准图片加载和缓存机制
    - 实现 VLLM 调用集成（发送当前图片+基准图片）
    - 实现威胁等级响应逻辑（low: 无操作, medium: 语音提示+通知, high: 语音警告+通知）
    - 使用 asyncio.Task 管理监控任务
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 2.4 实现通知服务
    - 创建 `core/providers/doorlock/notification_service.py`
    - 实现 NotificationService 类
    - 实现 notify_visitor_intent(visit_id, session_id, person_info, intent_summary, dialogue_text) - 发送访客意图通知
    - 实现 notify_package_alert(alert_id, session_id, threat_level, action, description, photo_path, voice_warning_text) - 发送快递警报通知
    - 实现 notify_guard_status_change(device_id, active, reason, baseline_image, start_time) - 发送看护状态变化通知
    - 实现消息格式化（JSON 格式，符合 App 通信协议）
    - 集成现有 App 通信机制
    - 添加通知失败重试机制和历史记录
    - _Requirements: 2.4, 6.3, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8_

  - [x] 2.5 Checkpoint - 确保核心服务正常
    - 所有服务通过单元测试
    - 数据库操作正常（CRUD 测试）
    - 会话管理正常（创建、清除、超时判定测试）
    - 看护模式管理器可以启动和停止监控
    - 通知服务可以正确格式化消息

- [x] 3. AI工具函数实现
  - [x] 3.1 实现门锁工具函数
    - 创建 `core/providers/doorlock/doorlock_tools.py`
    - 实现 DoorlockTools 类
    - 实现 enable_package_guard(device_id, reason) - 启用快递看护模式
    - 实现 disable_package_guard(device_id, reason) - 关闭快递看护模式
    - 实现 update_package_baseline(device_id) - 更新看护基准图片
    - 实现 report_package_status(device_id, session_id, action, threat_level, description) - 报告快递状态
    - 实现 report_visitor_intent(device_id, session_id, intent_type, summary, important_notes) - 报告访客意图
    - 为每个工具定义完整的 JSON Schema（name, description, parameters）
    - 实现参数验证和错误处理
    - 实现工具调用日志记录
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7_

  - [x] 3.2 注册工具函数到VLLM
    - 修改 VLLM 提供者配置，添加门锁工具列表
    - 实现工具函数动态加载机制
    - 实现工具调用路由（根据 tool_name 分发到对应函数）
    - 实现工具调用结果处理和格式化
    - 添加工具调用错误处理和降级策略
    - 添加工具调用性能监控
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7_

  - [x] 3.3 Checkpoint - 确保工具函数可用
    - 工具函数可被 VLLM 正确识别
    - 工具调用正确执行并返回结果
    - 工具调用参数验证正确
    - 工具调用失败有明确错误信息

- [x] 4. 意图识别处理器实现
  - [x] 4.1 实现人脸识别重试逻辑
    - 创建 `core/providers/doorlock/face_recognition_handler.py`
    - 实现 FaceRecognitionHandler 类
    - 实现 recognize_with_retry(device_id, max_retries=3) - 人脸识别（支持重试）
    - 实现重试间隔控制（1秒）
    - 第一次失败时播放语音提示"人脸识别失败，请正视摄像头重试"
    - 三次都失败时播放语音提示"人脸识别失败，请使用其他方式解锁"
    - 第二、三次失败不播放语音
    - 集成现有人脸识别服务和 TTS 服务
    - 记录重试次数和结果到日志
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 19.1_

  - [x] 4.2 实现欢迎词播放逻辑
    - 创建 `core/providers/doorlock/greeting_handler.py`
    - 实现 GreetingHandler 类
    - 实现 select_greeting(custom_greeting, current_time) - 根据时段选择欢迎词
    - 实现时段判断逻辑（6-12早晨, 12-18下午, 18-22晚上, 22-6夜间）
    - 实现 play_welcome_greeting(device_id, person_id) - 播放欢迎词
    - 实现默认欢迎词回退机制（时段 → default → "欢迎回家"）
    - 集成 TTS 服务
    - 记录播放的欢迎词内容到日志
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 13.1, 13.2, 13.3, 13.4, 13.5_

  - [x] 4.3 实现意图识别对话处理器
    - 创建 `core/handle/doorlock_intent_handler.py`
    - 实现 DoorlockIntentHandler 类
    - 实现 handle_visitor(device_id, session_id) - 处理访客到访主流程
    - 实现 start_intent_dialogue(device_id, session_id, person_info) - 启动意图识别对话
    - 实现主动问候逻辑（立即播放"您好，请问有什么可以帮您？"或"请问您找谁？"）
    - 实现对话循环（持续到沉默30秒或PIR无人体）
    - 实现对话历史管理（保留最近10轮，超过时自动清理）
    - 实现 generate_intent_summary(dialogue_history) - 生成意图总结（JSON格式）
    - 集成 VLLM 服务、会话管理器、通知服务
    - 实现 Token 消耗监控（超过80%输出警告）
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 19.4, 19.6_

  - [x] 4.4 Checkpoint - 确保意图识别正常
    - 人脸识别重试正常工作（最多3次，间隔1秒）
    - 欢迎词正确播放（根据时段选择）
    - 意图识别对话流程完整（主动问候 → 对话 → 生成总结 → 通知App）
    - 对话历史管理正常（保留10轮）

- [x] 5. 提示词设计
  - [x] 5.1 设计意图识别提示词
    - 在 `config/doorlock_prompts.yaml` 中编写 intent_recognition_prompt
    - 编写系统角色定义（智能门锁的AI门卫助手）
    - 编写职责说明（识别访客、意图识别对话、看护快递、记录通知）
    - 编写对话风格指南（礼貌正式但亲和、根据访客身份调整语气、对可疑行为警惕）
    - 编写对话策略（主动引导、简洁明了、确认重要信息、礼貌拒绝推销）
    - 编写工具调用说明（5个工具函数的使用场景和参数）
    - 编写示例对话（至少3个场景：快递员、访客、推销）
    - 参考 agent-base-prompt.txt 的设计风格
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 16.1, 16.2, 16.3, 16.4, 16.5_

  - [x] 5.2 设计看护模式提示词
    - 在 `config/doorlock_prompts.yaml` 中编写 package_guard_prompt
    - 编写看护任务说明（对比图片判断异常行为）
    - 编写威胁等级判断标准（低：路人/主人取件/工作人员，中：长时间停留/翻看快递/多次往返，高：非主人拿走/破坏/撬门/多人可疑）
    - 明确主人（is_owner=true）取走快递为低威胁
    - 明确非主人取走快递为高威胁
    - 编写行为类型定义（taking, searching, damaging, normal, passing）
    - 编写工具调用说明（report_package_status, update_package_baseline, enable/disable_package_guard）
    - 编写基准图片更新时机（门口物品增多、对话中提到"放这了"）
    - 编写看护模式控制逻辑（主人取走时关闭、访客提到快递时启用）
    - 编写示例场景（至少5个：路人经过、主人取件、陌生人拿走、翻看快递、破坏快递）
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 16.1, 16.2, 16.3, 16.4_

  - [x] 5.3 设计欢迎词模板
    - 在 `config/doorlock_prompts.yaml` 中编写 welcome_templates
    - 设计"温馨家庭"风格模板（morning, afternoon, evening, night, default）
    - 设计"简洁风格"模板（default）
    - 设计"正式风格"模板（morning, afternoon, evening, night, default）
    - 添加变量占位符 {name} 支持姓名替换
    - 确保欢迎词简洁友好（<20字）
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

  - [x] 5.4 Checkpoint - 确保提示词有效
    - 提示词通过实际测试（使用 VLLM 测试响应）
    - AI 响应符合预期（礼貌、准确、简洁）
    - 威胁等级判断准确（测试5个示例场景）
    - 工具调用正确（测试所有工具函数）

- [x] 6. 集成与测试
  - [x] 6.1 集成PIR触发事件
  - 修改 `core/connection.py` 或相关 PIR 事件处理逻辑
  - 集成意图识别处理器（DoorlockIntentHandler）
  - 实现设备配置检查（intent_recognition_enabled）
  - 实现看护模式状态检查（package_guard_active）
  - 看护模式激活时同时启动监控和对话
  - 支持多个设备并发处理
  - 记录完整的事件处理流程到日志
  - _Requirements: 7.1, 9.1, 15.1, 15.2, 15.3, 15.4, 15.5_

  - [x] 6.2 集成VLLM服务
  - 修改 VLLM 提供者，支持多图片输入（单图片用于意图识别，双图片用于看护监控）
  - 实现意图识别对话模式（单图片+对话历史）
  - 实现看护监控分析模式（当前图片+基准图片+对话历史）
  - 实现提示词动态加载（从 doorlock_prompts.yaml）
  - 实现工具调用处理（解析 tool_calls 并执行）
  - 实现 Token 消耗统计（记录 prompt_tokens, completion_tokens, total_tokens）
  - Token 超过80%时输出警告日志
  - 添加性能监控（记录响应时间）
  - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 19.2, 19.4, 19.6_

  - [x] 6.3 集成ESP32拍照功能
  - 实现 MCP 协议调用 ESP32 的 capture_image 工具
  - 在拍照请求中包含 question 参数（如"判断门口快递状态"）
  - 实现图片上传接收（HTTP POST，分辨率640x480）
  - 实现图片保存到文件系统（data/face_recognition/package_baseline/ 和 visits/）
  - 实现时间戳处理（从上传请求中接收或生成）
  - 使用命名规则 device*{device_id}\_baseline*{timestamp}.jpg
  - 添加拍照失败处理（记录错误并跳过本次监控）
  - 参考 esp32-vision-guide.md 的实现方式
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 5.4, 5.5, 17.1, 17.2, 17.3, 17.4, 17.5, 20.3_

  - [x] 6.4 集成App通信协议
  - 定义消息类型常量（doorlock_visitor_intent, doorlock_package_alert, doorlock_package_guard_status）
  - 实现访客意图通知消息格式化（包含 visit_id, session_id, person_info, intent_summary, dialogue_text）
  - 实现快递警报通知消息格式化（包含 alert_id, session_id, threat_level, action, description, photo_path, voice_warning_text）
  - 实现看护状态变化通知消息格式化（包含 device_id, active, reason, baseline_image, start_time）
  - 集成现有 App 通信机制（WebSocket 或 HTTP）
  - 添加消息发送日志
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8_

  - [x] 6.5 编写单元测试
  - 创建测试目录结构 `test/doorlock/`
  - 创建 `test/doorlock/conftest.py`（测试配置和 fixtures）
  - 编写 `test/doorlock/test_database.py`（数据库服务测试）
  - 编写 `test/doorlock/test_session_manager.py`（会话管理器测试）
  - 编写 `test/doorlock/test_package_guard.py`（看护模式管理器测试）
  - 编写 `test/doorlock/test_tools.py`（工具函数测试）
  - 编写 `test/doorlock/test_face_recognition.py`（人脸识别处理器测试）
  - 编写 `test/doorlock/test_greeting.py`（欢迎词处理器测试）
  - 编写 `test/doorlock/test_intent_handler.py`（意图识别处理器测试）
  - 使用 pytest 框架和 pytest-asyncio
  - 使用 mock 模拟外部依赖（数据库、VLLM、TTS等）
  - 测试覆盖率目标 > 80%
  - _Requirements: 所有需求_

  - [x] 6.6 编写集成测试
  - 创建 `test/integration/test_visitor_flow.py`（完整访客流程测试）
  - 创建 `test/integration/test_package_guard_flow.py`（看护模式流程测试）
  - 创建 `test/integration/test_face_recognition_retry.py`（人脸识别重试测试）
  - 创建 `test/integration/test_concurrent_visitors.py`（并发访客测试）
  - 创建 `test/integration/conftest.py`（集成测试配置）
  - 使用真实数据库（测试库）
  - 模拟 ESP32 设备和 VLLM 服务
  - 准备测试数据（人脸照片、基准图片等）
  - _Requirements: 所有需求_

  - [x] 6.7 Checkpoint - 确保所有测试通过
  - 单元测试覆盖率 > 80%
  - 所有单元测试通过
  - 所有集成测试通过
  - 完整流程可正常运行（PIR触发 → 人脸识别 → 意图识别 → 通知App）
  - 看护模式可正常启动和停止

- [x] 7. HTTP API实现
  - [x] 7.1 实现设备配置API
  - 在 `core/http_server.py` 中添加路由
  - 实现 GET /api/doorlock/config?device_id={device_id} - 获取设备配置
  - 实现 POST /api/doorlock/config - 更新设备配置（intent_recognition_enabled, package_guard_available）
  - 实现请求参数验证（device_id 必填）
  - 实现响应格式化（JSON 格式，包含 success, data/message）
  - 添加错误处理（404, 400, 500）
  - 添加 API 文档注释
  - _Requirements: 1.1, 1.2_

  - [x] 7.2 实现看护模式控制API
  - 实现 POST /api/doorlock/package_guard/start - 启动看护模式
  - 实现 POST /api/doorlock/package_guard/stop - 停止看护模式
  - 实现请求参数验证（device_id, reason）
  - 验证 package_guard_available 开关
  - 记录启动/停止原因
  - 发送状态变化通知到 App
  - 实现响应格式化
  - 添加权限验证（可选）
  - _Requirements: 2.2, 6.2_

  - [x] 7.3 实现欢迎词配置API
  - 实现 POST /api/doorlock/welcome/config - 配置欢迎词
  - 实现 GET /api/doorlock/welcome/config?person_id={person_id} - 查询欢迎词配置
  - 实现 GET /api/doorlock/welcome/templates - 获取预设模板
  - 实现 JSON 格式验证（morning, afternoon, evening, night, default）
  - 实现响应格式化
  - 添加错误处理
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

  - [x] 7.4 实现历史记录查询API
  - 实现 GET /api/doorlock/intents/history?device_id={device_id}&limit=20&offset=0 - 查询意图识别历史
  - 实现 GET /api/doorlock/alerts/history?device_id={device_id}&limit=20&offset=0 - 查询快递警报历史
  - 实现分页参数（limit, offset）
  - 实现时间范围过滤（start_date, end_date，可选）
  - 返回总记录数（total）
  - 实现响应格式化
  - 查询性能优化（使用索引）
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [x] 7.5 Checkpoint - 确保API正常工作
  - 所有 API 接口正常响应
  - 参数验证正确（必填项、类型、格式）
  - 错误处理完善（返回明确错误信息）
  - 响应格式符合规范
  - 通过 API 测试（使用 curl 或 Postman）

- [x] 8. 文档与部署
  - [x] 8.1 编写API文档
  - 创建 `docs/my_docs/doorlock-api-documentation.md`
  - 编写设备配置 API 文档（GET/POST /api/doorlock/config）
  - 编写看护模式控制 API 文档（POST /api/doorlock/package_guard/start, stop）
  - 编写欢迎词配置 API 文档（GET/POST /api/doorlock/welcome/config, GET templates）
  - 编写历史记录查询 API 文档（GET /api/doorlock/intents/history, alerts/history）
  - 添加请求/响应示例（至少每个接口1个示例）
  - 添加错误码说明（400, 404, 500）
  - 添加认证说明（如需要）
  - _Requirements: 所有需求_

  - [x] 8.2 编写使用指南
  - 创建 `docs/my_docs/smart-doorlock-usage-guide.md`
  - 编写功能概述（意图识别、看护模式）
  - 编写配置步骤（数据库迁移、配置文件、提示词）
  - 编写意图识别使用说明（如何配置、如何查看记录）
  - 编写看护模式使用说明（如何启用、如何查看警报）
  - 编写欢迎词配置说明（如何配置、预设模板）
  - 编写常见问题解答（至少5个问题）
  - 添加配置示例
  - _Requirements: 所有需求_

  - [x] 8.3 编写测试指南
  - 创建 `docs/my_docs/smart-doorlock-test-guide.md`
  - 编写测试环境配置说明（Python 环境、数据库、依赖安装）
  - 编写单元测试运行说明（pytest 命令、覆盖率查看）
  - 编写集成测试运行说明（测试数据准备、运行命令）
  - 编写测试编写指南（测试结构、mock 使用、断言方式）
  - 说明测试覆盖率要求（> 80%）
  - _Requirements: 所有需求_

  - [x] 8.4 编写部署脚本
  - 创建 `migrations/deploy_doorlock_ai.sh`
  - 实现数据库迁移执行（调用 run_doorlock_ai_migration.py）
  - 实现配置文件检查（config.yaml, doorlock_prompts.yaml）
  - 实现依赖安装检查（requirements.txt）
  - 实现服务重启（可选）
  - 实现部署验证（调用 verify_doorlock_ai_migration.py）
  - 添加回滚机制（创建 rollback_doorlock_ai.sh）
  - 添加日志输出（清晰的部署步骤和结果）
  - _Requirements: 所有需求_

  - [x] 8.5 Final Checkpoint - 确保所有文档完整
  - 文档完整清晰（API 文档、使用指南、测试指南）
  - 部署脚本可用（测试部署流程）
  - CHANGELOG 更新（版本号、日期、变更内容）
  - 所有文档使用中文编写
  - 文档格式规范（Markdown）
