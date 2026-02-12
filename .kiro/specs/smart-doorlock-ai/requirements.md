# 需求文档

## 介绍

本文档定义了智能门锁AI功能的需求规格，包含两大核心功能：快递/外卖看护模式和访客意图识别。系统通过视觉AI监控门口，检测异常行为并实时警报，同时基于人脸识别和视觉对话自动识别访客意图并通知主人。

## 术语表

- **System**: 智能门锁AI系统（xiaozhi-server）
- **Device**: ESP32智能门锁设备
- **PIR**: 人体红外传感器
- **VLLM**: 视觉语言模型（Vision Language Model）
- **App**: 手机应用程序
- **Session**: 会话（从PIR触发到访客离开的完整交互过程）
- **Baseline_Image**: 基准图片（用于对比检测快递状态变化的参考图片）
- **Owner**: 主人（is_owner=true的用户，有权取走快递）
- **Visitor**: 访客（到访门口的人员）
- **Threat_Level**: 威胁等级（low/medium/high）
- **Intent_Type**: 意图类型（delivery/visit/sales/maintenance/other）
- **Guard_Mode**: 看护模式（监控门口快递的AI监控状态）
- **Face_Recognition**: 人脸识别服务
- **TTS**: 语音合成服务（Text-to-Speech）
- **ASR**: 语音识别服务（Automatic Speech Recognition）

## 需求

### 需求 1: 看护模式配置管理

**用户故事**: 作为用户，我希望能够配置看护模式的可用性，以便控制系统是否可以启用快递看护功能。

#### 验收标准

1. THE System SHALL 存储每个设备的看护模式配置（package_guard_available）
2. WHEN 用户通过App修改看护模式配置，THE System SHALL 更新数据库并立即生效
3. THE System SHALL 存储看护模式的激活状态（package_guard_active）
4. THE System SHALL 存储基准图片路径（package_baseline_image）
5. THE System SHALL 记录看护模式的启动时间（package_guard_start_time）

### 需求 2: 看护模式触发与激活

**用户故事**: 作为用户，我希望系统能够智能判断何时需要启用看护模式，以便自动保护门口的快递。

#### 验收标准

1. WHEN AI在对话中识别到"快递放门口了"等关键信息，THE System SHALL 自动激活看护模式
2. WHEN 用户通过App手动启动看护模式，THE System SHALL 激活看护模式
3. IF 看护模式可用开关未启用（package_guard_available=false），THEN THE System SHALL 拒绝激活看护模式
4. WHEN 看护模式激活成功，THE System SHALL 发送App通知告知用户
5. WHEN 看护模式激活，THE System SHALL 拍摄并保存基准图片

### 需求 3: 看护模式监控流程

**用户故事**: 作为用户，我希望系统能够持续监控门口快递，以便及时发现异常行为。

#### 验收标准

1. WHILE 看护模式已激活且PIR检测到人体，THE System SHALL 每5秒拍照一次
2. WHEN 拍照完成，THE System SHALL 将当前图片和基准图片一起发送给VLLM进行分析
3. WHEN VLLM返回分析结果，THE System SHALL 解析威胁等级和行为类型
4. WHEN PIR检测不到人体，THE System SHALL 停止拍照监控
5. THE System SHALL 为每张照片添加时间戳

### 需求 4: 威胁等级判断与响应

**用户故事**: 作为用户，我希望系统能够根据威胁等级采取不同的响应措施，以便有效保护快递安全。

#### 验收标准

1. WHEN 威胁等级为低（low），THE System SHALL 不播放语音警告且不发送App通知
2. WHEN 威胁等级为中（medium），THE System SHALL 播放语音提示"请问有什么可以帮您？"并发送App通知
3. WHEN 威胁等级为高（high），THE System SHALL 播放语音警告"您的行为已被记录，请立即停止"并发送App通知
4. WHEN 检测到主人（is_owner=true）拿走快递，THE System SHALL 判定为低威胁
5. THE System SHALL 将所有警报记录保存到数据库（doorlock_package_alerts表）

### 需求 5: 基准图片管理

**用户故事**: 作为用户，我希望系统能够自动更新基准图片，以便准确检测快递状态变化。

#### 验收标准

1. WHEN PIR检测不到人体（访客离开），THE System SHALL 拍摄新的基准图片
2. WHEN AI判断有新快递送达，THE System SHALL 更新基准图片
3. WHEN AI在对话中识别到"我把快递放这了"等信息，THE System SHALL 更新基准图片
4. THE System SHALL 将基准图片存储在文件系统的 `data/face_recognition/package_baseline/` 目录
5. THE System SHALL 使用命名规则 `device_{device_id}_baseline_{timestamp}.jpg` 命名基准图片

### 需求 6: 看护模式关闭

**用户故事**: 作为用户，我希望系统能够在快递被取走后自动关闭看护模式，以便节省资源。

#### 验收标准

1. WHEN AI判断快递已被主人（is_owner=true）取走，THE System SHALL 自动关闭看护模式
2. WHEN 用户通过App手动停止看护模式，THE System SHALL 关闭看护模式
3. WHEN 看护模式关闭，THE System SHALL 发送App通知告知用户
4. WHEN 主人回家（有开门权限的用户识别成功），THE System SHALL 继续运行看护模式
5. THE System SHALL 在数据库中更新看护模式状态（package_guard_active=false）

### 需求 7: 人脸识别流程

**用户故事**: 作为用户，我希望系统能够准确识别访客身份，以便提供个性化服务。

#### 验收标准

1. WHEN PIR检测到人体，THE System SHALL 启动人脸识别流程
2. WHEN 人脸识别失败，THE System SHALL 最多重试3次
3. WHEN 第一次识别失败，THE System SHALL 播放语音提示"人脸识别失败，请正视摄像头重试"
4. WHEN 两次识别之间，THE System SHALL 等待1秒
5. WHEN 三次识别都失败，THE System SHALL 播放语音提示"人脸识别失败，请使用其他方式解锁"

### 需求 8: 有权限访客处理

**用户故事**: 作为有开门权限的用户，我希望系统能够识别我并播放个性化欢迎词，以便获得友好的体验。

#### 验收标准

1. WHEN 人脸识别成功且用户有开门权限，THE System SHALL 播放个性化欢迎词
2. THE System SHALL 根据当前时段选择对应的欢迎词（早晨6:00-12:00、下午12:00-18:00、晚上18:00-22:00、夜间22:00-6:00）
3. WHEN 用户未配置对应时段的欢迎词，THE System SHALL 使用默认欢迎词
4. WHEN 播放欢迎词后，THE System SHALL 自动开门
5. THE System SHALL 从数据库的 `persons.custom_greeting` 字段读取欢迎词配置（JSON格式）

### 需求 9: 无权限访客意图识别

**用户故事**: 作为用户，我希望系统能够与无权限访客进行对话并识别其意图，以便了解访客来访目的。

#### 验收标准

1. WHEN 人脸识别失败或识别为无权限访客，THE System SHALL 立即播放主动问候"您好，请问有什么可以帮您？"
2. WHEN 识别出陌生人，THE System SHALL 先询问"请问您找谁？"
3. WHEN 识别出已注册但无权限的人，THE System SHALL 根据身份调整对话策略
4. THE System SHALL 使用VLLM进行意图识别对话
5. THE System SHALL 保持对话直到访客沉默超过30秒或PIR检测不到人体

### 需求 10: 对话会话管理

**用户故事**: 作为系统，我需要管理对话会话的生命周期，以便正确处理访客交互。

#### 验收标准

1. WHEN PIR触发，THE System SHALL 生成唯一的会话ID（格式：device_id_timestamp）
2. THE System SHALL 在会话中记录对话历史
3. THE System SHALL 在会话中记录拍照记录
4. WHEN 访客沉默超过30秒，THE System SHALL 判定对话结束
5. WHEN PIR检测不到人体，THE System SHALL 立即清除会话

### 需求 11: 意图识别总结生成

**用户故事**: 作为用户，我希望系统能够生成结构化的对话总结，以便快速了解访客来访情况。

#### 验收标准

1. WHEN 对话结束，THE System SHALL 生成结构化总结（JSON格式）
2. THE System SHALL 在总结中包含重要信息列表（important_notes）
3. THE System SHALL 在总结中包含意图类型（intent_type: delivery/visit/sales/maintenance/other）
4. THE System SHALL 在总结中包含来访目的（purpose）
5. THE System SHALL 在总结中包含完整摘要（full_summary）
6. THE System SHALL 将重要信息（留言、提醒）标注为【留言】或【提醒】并放在开头
7. WHEN 访客不配合或沉默，THE System SHALL 生成总结说明情况

### 需求 12: App通知推送

**用户故事**: 作为用户，我希望能够及时收到访客和快递的通知，以便了解门口情况。

#### 验收标准

1. WHEN 意图识别对话结束，THE System SHALL 发送访客意图识别结果通知到App
2. WHEN 检测到中威胁或高威胁行为，THE System SHALL 发送快递异常警报通知到App
3. WHEN 看护模式状态变化，THE System SHALL 发送状态变化通知到App
4. THE System SHALL 在访客通知中包含人脸照片路径
5. THE System SHALL 在访客通知中包含对话文字
6. THE System SHALL 在访客通知中包含意图摘要
7. THE System SHALL 在警报通知中包含证据照片路径
8. THE System SHALL 在警报通知中包含威胁等级和行为描述

### 需求 13: 欢迎词配置

**用户故事**: 作为用户，我希望能够为每个家庭成员配置个性化欢迎词，以便提供温馨的回家体验。

#### 验收标准

1. THE System SHALL 支持为每个用户配置分时段欢迎词（morning/afternoon/evening/night/default）
2. WHEN 用户通过App配置欢迎词，THE System SHALL 将配置保存到数据库的 `persons.custom_greeting` 字段
3. THE System SHALL 使用JSON格式存储欢迎词配置
4. THE System SHALL 提供预设模板供用户选择
5. THE System SHALL 支持用户自定义欢迎词文本

### 需求 14: 数据持久化

**用户故事**: 作为系统管理员，我需要持久化存储所有访客和警报记录，以便后续查询和分析。

#### 验收标准

1. THE System SHALL 将所有意图识别记录保存到 `doorlock_visitor_intents` 表
2. THE System SHALL 将所有快递警报记录保存到 `doorlock_package_alerts` 表
3. THE System SHALL 将设备配置保存到 `doorlock_config` 表
4. THE System SHALL 在 `persons` 表中存储用户的 `is_owner` 标识和 `custom_greeting` 配置
5. THE System SHALL 永久保存所有记录，不自动删除

### 需求 15: 看护模式与意图识别协同

**用户故事**: 作为用户，我希望系统能够同时进行意图识别对话和看护监控，以便全面了解门口情况。

#### 验收标准

1. WHEN 看护模式已激活且有访客到访，THE System SHALL 同时启动意图识别对话和看护监控
2. THE System SHALL 在同一会话中并行执行对话和拍照监控
3. WHEN 对话结束且PIR检测不到人体，THE System SHALL 生成意图总结并拍摄基准图片
4. THE System SHALL 确保对话和监控使用相同的会话ID
5. THE System SHALL 在对话过程中继续执行看护监控（每5秒拍照）

### 需求 16: AI工具调用

**用户故事**: 作为AI系统，我需要能够调用工具函数来控制看护模式和报告状态，以便实现智能决策。

#### 验收标准

1. THE System SHALL 提供 `enable_package_guard` 工具供AI调用以启用看护模式
2. THE System SHALL 提供 `disable_package_guard` 工具供AI调用以关闭看护模式
3. THE System SHALL 提供 `update_package_baseline` 工具供AI调用以更新基准图片
4. THE System SHALL 提供 `report_package_status` 工具供AI调用以报告快递状态
5. THE System SHALL 提供 `report_visitor_intent` 工具供AI调用以报告访客意图
6. THE System SHALL 为每个工具定义清晰的JSON Schema
7. WHEN AI调用工具，THE System SHALL 验证参数并执行相应操作

### 需求 17: 图片拍摄与上传

**用户故事**: 作为系统，我需要通过ESP32设备拍摄照片并上传，以便进行视觉分析。

#### 验收标准

1. THE System SHALL 通过MCP协议调用ESP32的 `capture_image` 工具
2. WHEN 拍照请求发送，THE System SHALL 在请求中包含问题描述（question参数）
3. THE System SHALL 接收ESP32通过HTTP POST上传的图片（分辨率640x480）
4. THE System SHALL 在上传请求中接收图片时间戳
5. THE System SHALL 将图片保存到文件系统并记录路径

### 需求 18: VLLM视觉分析

**用户故事**: 作为系统，我需要使用VLLM进行视觉分析，以便判断访客意图和快递状态。

#### 验收标准

1. WHEN 进行意图识别，THE System SHALL 将访客照片和对话历史发送给VLLM
2. WHEN 进行看护监控，THE System SHALL 将当前图片和基准图片一起发送给VLLM
3. THE System SHALL 使用专门的提示词指导VLLM进行威胁等级判断
4. THE System SHALL 解析VLLM返回的工具调用（tool_calls）
5. THE System SHALL 记录VLLM调用的Token消耗

### 需求 19: 性能监控

**用户故事**: 作为系统管理员，我需要监控系统性能指标，以便优化系统运行。

#### 验收标准

1. THE System SHALL 记录人脸识别耗时
2. THE System SHALL 记录VLLM响应时间
3. THE System SHALL 记录拍照上传耗时
4. THE System SHALL 记录对话轮次和Token消耗
5. THE System SHALL 记录看护模式拍照频率
6. WHEN Token使用量超过模型上限的80%，THE System SHALL 输出警告日志

### 需求 20: 错误处理

**用户故事**: 作为系统，我需要优雅地处理各种错误情况，以便保证系统稳定运行。

#### 验收标准

1. WHEN VLLM服务不可用，THE System SHALL 输出错误日志并继续运行其他功能
2. WHEN 数据库连接异常，THE System SHALL 尝试重连
3. WHEN 拍照失败，THE System SHALL 记录错误并跳过本次监控
4. WHEN App通知推送失败，THE System SHALL 记录错误但不影响主流程
5. THE System SHALL 确保任何单个功能的失败不会导致整个系统崩溃
