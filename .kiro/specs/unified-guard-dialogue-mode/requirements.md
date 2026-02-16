# 需求文档

## 介绍

本文档定义了"统一智能看护对话模式"功能的需求。该功能将门锁的意图识别对话模式和看护监控模式统一为一个智能模式，使得在看护模式激活期间，访客仍能正常进行意图识别对话，同时AI在后台监控快递安全，提供无缝的用户体验。

## 术语表

- **System**: xiaozhi-server AI引擎系统
- **VLLM_Provider**: 视觉语言模型提供者，负责处理图像和对话的AI分析
- **Intent_Handler**: 意图处理器，负责管理访客对话流程
- **Guard_Manager**: 看护管理器，负责管理快递看护模式
- **Baseline_Image**: 基准图片，记录快递初始状态的参考图片
- **Visitor_Image**: 访客图片，访客到访时拍摄的照片
- **Dialogue_History**: 对话历史，记录访客与AI的完整对话内容
- **Threat_Level**: 威胁等级，包括low（低）、medium（中）、high（高）三个级别
- **Unified_Mode**: 统一模式，同时处理对话和监控的智能模式
- **Tool_Call**: 工具调用，AI调用系统功能的机制

## 需求

### 需求 1: 统一模式对话处理

**用户故事**: 作为访客，我希望在看护模式激活期间仍能与门锁AI正常对话，以便表达我的来访意图。

#### 验收标准

1. WHEN 看护模式激活且访客到访 THEN THE System SHALL 启动统一模式对话流程
2. WHEN 统一模式对话启动 THEN THE System SHALL 同时加载访客图片和基准图片
3. WHEN 第一轮对话开始 THEN THE VLLM_Provider SHALL 接收访客图片和基准图片
4. WHEN 后续轮次对话进行 THEN THE VLLM_Provider SHALL 仅接收访客图片
5. WHEN 对话进行中 THEN THE System SHALL 优先处理访客对话，后台监控快递状态

### 需求 2: 动态提示词组合

**用户故事**: 作为系统开发者，我希望提示词能够根据看护模式状态动态组合，以便AI能够正确理解当前任务。

#### 验收标准

1. THE System SHALL 维护三层提示词结构（核心角色、对话任务、看护任务、工具指南）
2. WHEN 看护模式未激活 THEN THE System SHALL 组合核心角色、对话任务和工具指南提示词
3. WHEN 看护模式激活 THEN THE System SHALL 组合核心角色、对话任务、看护任务和工具指南提示词
4. THE System SHALL 确保提示词明确对话优先级高于监控任务
5. THE System SHALL 在提示词中说明监控是后台任务，不应在对话中提及

### 需求 3: Token优化策略

**用户故事**: 作为系统管理员，我希望优化Token消耗，以便降低运营成本。

#### 验收标准

1. WHEN 第一轮对话 THEN THE VLLM_Provider SHALL 传入访客图片和基准图片
2. WHEN 第二轮及后续对话 THEN THE VLLM_Provider SHALL 仅传入访客图片
3. THE System SHALL 依赖AI的上下文理解能力记忆基准图片状态
4. THE System SHALL 确保单次对话Token消耗不超过20K tokens

### 需求 4: 基于行为的威胁检测

**用户故事**: 作为房主，我希望系统能够智能检测访客的可疑行为，以便及时发现快递安全威胁。

#### 验收标准

1. WHEN 访客靠近并触碰快递 THEN THE System SHALL 评估威胁等级并可能触发报告
2. WHEN 访客长时间停留在快递旁边超过10秒 THEN THE System SHALL 评估威胁等级并可能触发报告
3. WHEN 访客试图拿走快递且非主人 THEN THE System SHALL 判定为高威胁并立即报告
4. WHEN 访客破坏或踢踹快递 THEN THE System SHALL 判定为高威胁并立即报告
5. WHEN 威胁等级为medium或high THEN THE System SHALL 调用report_package_status工具报告
6. WHEN 威胁等级为high THEN THE System SHALL 立即打断对话并播放警告语音
7. WHEN 访客是主人且取走快递 THEN THE System SHALL 判定为低威胁正常行为

### 需求 5: 对话结束后处理

**用户故事**: 作为系统，我需要在对话结束后执行完整的检查和总结流程，以便生成完整的访问记录。

#### 验收标准

1. WHEN 对话结束 THEN THE System SHALL 执行对话结束后处理流程
2. WHEN 看护模式激活 THEN THE System SHALL 重新拍照并检查快递最终状态
3. WHEN 执行快递状态检查 THEN THE VLLM_Provider SHALL 对比基准图片和当前图片并返回纯JSON格式结果
4. WHEN 快递状态检查完成 THEN THE System SHALL 生成访客意图总结
5. WHEN 生成意图总结 THEN THE VLLM_Provider SHALL 基于完整对话历史和访客图片返回结构化JSON结果
6. WHEN 意图总结生成完成 THEN THE System SHALL 保存访问记录到数据库
7. WHEN 访问记录保存完成 THEN THE System SHALL 发送App通知给房主
8. WHEN 所有处理完成 THEN THE System SHALL 清理会话数据

### 需求 6: VLLM提供者方法扩展

**用户故事**: 作为系统开发者，我需要VLLM提供者支持统一模式的分析方法，以便实现新的对话流程。

#### 验收标准

1. THE VLLM_Provider SHALL 提供analyze_unified方法支持统一模式分析
2. WHEN 调用analyze_unified方法 THEN THE VLLM_Provider SHALL 接收访客图片、可选的基准图片、对话历史和是否第一轮标志
3. THE VLLM_Provider SHALL 提供final_package_check方法支持对话结束后的快递状态检查
4. WHEN 调用final_package_check方法 THEN THE VLLM_Provider SHALL 接收当前图片和基准图片并返回纯JSON格式结果
5. THE VLLM_Provider SHALL 提供generate_intent_summary方法支持意图总结生成
6. WHEN 调用generate_intent_summary方法 THEN THE VLLM_Provider SHALL 接收访客图片和完整对话历史并返回结构化JSON结果

### 需求 7: 工具函数配置

**用户故事**: 作为AI，我需要调用系统工具函数来执行特定操作，以便完成对话和监控任务。

#### 验收标准

1. THE System SHALL 提供enable_package_guard工具函数用于启用看护模式
2. THE System SHALL 提供disable_package_guard工具函数用于关闭看护模式
3. THE System SHALL 提供update_package_baseline工具函数用于更新基准图片
4. THE System SHALL 提供report_package_status工具函数用于报告快递状态和威胁
5. THE System SHALL 移除report_visitor_intent工具函数
6. WHEN AI需要报告访客意图 THEN THE System SHALL 在对话结束后主动询问AI生成总结

### 需求 8: 提示词配置管理

**用户故事**: 作为系统配置管理员，我需要管理统一模式的提示词配置，以便调整AI的行为。

#### 验收标准

1. THE System SHALL 在配置文件中定义core_role_and_style提示词片段
2. THE System SHALL 在配置文件中定义dialogue_tasks提示词片段
3. THE System SHALL 在配置文件中定义guard_tasks提示词片段
4. THE System SHALL 在配置文件中定义tools_guide提示词片段
5. THE System SHALL 在配置文件中定义final_package_check_prompt提示词
6. THE System SHALL 在配置文件中定义intent_summary_prompt提示词
7. THE System SHALL 支持通过配置文件修改提示词内容而无需修改代码

### 需求 9: 对话流程控制

**用户故事**: 作为系统，我需要控制对话流程的开始、进行和结束，以便提供良好的用户体验。

#### 验收标准

1. WHEN 访客到访 THEN THE Intent_Handler SHALL 检查看护模式状态
2. WHEN 看护模式激活 THEN THE Intent_Handler SHALL 加载基准图片
3. THE Intent_Handler SHALL 播放主动问候语音
4. WHEN 对话进行中 THEN THE Intent_Handler SHALL 等待访客语音回复
5. WHEN 收到访客回复 THEN THE Intent_Handler SHALL 调用VLLM统一分析
6. WHEN 收到AI回复 THEN THE Intent_Handler SHALL 播放AI语音回复
7. WHEN AI调用工具 THEN THE Intent_Handler SHALL 执行工具调用
8. WHEN 沉默超过30秒且PIR无人体检测 THEN THE Intent_Handler SHALL 结束对话

### 需求 10: 错误处理和降级

**用户故事**: 作为系统，我需要处理各种异常情况，以便保证系统稳定运行。

#### 验收标准

1. WHEN VLLM调用失败 THEN THE System SHALL 记录错误日志并返回默认响应
2. WHEN 快递状态检查JSON解析失败 THEN THE System SHALL 返回默认低威胁结果
3. WHEN 意图总结JSON解析失败 THEN THE System SHALL 返回默认总结结果
4. WHEN 图片Token超出限制 THEN THE System SHALL 抛出异常并终止处理
5. WHEN 工具调用执行失败 THEN THE System SHALL 记录错误日志并继续对话
6. THE System SHALL 支持通过配置关闭统一模式回退到分离模式
