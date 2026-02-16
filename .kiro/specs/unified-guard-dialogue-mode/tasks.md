# Implementation Plan

- [x] 1. VLLM提供者核心方法扩展
  - [x] 1.1 实现analyze_unified方法
    - 在 `core/providers/vllm/doorlock_vllm.py` 中添加方法
    - 实现图片列表构建逻辑（第一轮传2张，后续传1张）
    - 实现图片Token限制检查
    - 实现动态提示词组合调用
    - 实现VLLM调用和结果解析
    - 实现Token使用量统计和警告
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4_

  - [x] 1.2 实现final_package_check方法
    - 在 `core/providers/vllm/doorlock_vllm.py` 中添加方法
    - 实现图片Token限制检查（2张图片）
    - 加载final_package_check_prompt提示词
    - 实现VLLM调用
    - 实现纯JSON格式解析
    - 实现异常处理（返回默认低威胁结果）
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 1.3 实现generate_intent_summary方法
    - 在 `core/providers/vllm/doorlock_vllm.py` 中添加方法
    - 实现图片Token限制检查（1张图片）
    - 加载intent_summary_prompt提示词
    - 实现VLLM调用
    - 实现混合JSON格式解析
    - 实现异常处理（返回默认总结结果）
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 1.4 实现\_build_unified_prompt方法
    - 在 `core/providers/vllm/doorlock_vllm.py` 中添加方法
    - 实现基础提示词组合（core + dialogue + tools）
    - 实现看护任务提示词条件添加
    - 实现提示词拼接逻辑
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 1.5 Checkpoint - 确保VLLM提供者测试通过
    - Ensure all tests pass, ask the user if questions arise.

- [x] 2. Token管理和优化
  - [x] 2.1 实现\_check_image_token_limit方法
    - 在 `core/providers/vllm/doorlock_vllm.py` 中添加方法
    - 检查图片数量是否超过Token限制
    - 记录警告日志
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 2.2 实现\_truncate_dialogue_history方法
    - 在 `core/providers/vllm/doorlock_vllm.py` 中添加方法
    - 从最新对话开始累加Token
    - 超出限制时停止添加
    - 记录截断日志
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 2.3 优化\_check_token_usage方法
    - 在 `core/providers/vllm/doorlock_vllm.py` 中修改方法
    - 实现多层次Token监控（输入/输出/总计）
    - 实现分级警告（输出>80%、输入>80%、总计>80%）
    - 记录详细统计信息
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 2.4 实现\_estimate_tokens方法
    - 在 `core/providers/vllm/doorlock_vllm.py` 中添加方法
    - 估算文本Token数量（中文1.5字符/Token，英文4字符/Token）
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 2.5 实现\_estimate_image_tokens方法
    - 在 `core/providers/vllm/doorlock_vllm.py` 中添加方法
    - 根据配置的tokens_per_image计算
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 2.6 Checkpoint - 确保Token管理测试通过
    - Ensure all tests pass, ask the user if questions arise.

- [x] 3. 照片缓存管理器
  - [x] 3.1 创建PhotoCacheManager类
    - 创建 `core/providers/doorlock/photo_cache_manager.py` 文件
    - 实现单例模式
    - 实现照片缓存字典（按session_id管理）
    - 实现最多保留10张照片的逻辑
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 3.2 实现add_photo方法
    - 添加照片到缓存
    - 自动清理超过10张的旧照片
    - 记录照片时间戳
    - _Requirements: 9.1, 9.2_

  - [x] 3.3 实现get_latest_photo方法
    - 获取最新的缓存照片
    - 返回Base64编码的照片
    - _Requirements: 9.3_

  - [x] 3.4 实现clear_cache方法
    - 清理指定session_id的所有缓存照片
    - 释放内存
    - _Requirements: 9.5_

  - [x] 3.5 Checkpoint - 确保照片缓存测试通过
    - Ensure all tests pass, ask the user if questions arise.

- [x] 4. 定时拍照任务
  - [x] 4.1 实现start_photo_capture_task方法
    - 在 `core/handle/doorlock_intent_handler.py` 中添加方法
    - 创建异步定时任务（每5秒拍照一次）
    - 调用ESP32拍照接口
    - 将照片添加到PhotoCacheManager
    - 记录任务ID用于后续停止
    - _Requirements: 9.1, 9.2_

  - [x] 4.2 实现stop_photo_capture_task方法
    - 在 `core/handle/doorlock_intent_handler.py` 中添加方法
    - 取消定时拍照任务
    - 清理任务引用
    - _Requirements: 9.4_

  - [x] 4.3 修改start_unified_dialogue方法集成定时拍照
    - 对话开始后启动定时拍照任务
    - 对话结束后停止定时拍照任务
    - 异常情况下确保任务被停止
    - _Requirements: 9.1, 9.4_

  - [x] 4.4 Checkpoint - 确保定时拍照测试通过
    - Ensure all tests pass, ask the user if questions arise.

- [x] 5. 意图处理器核心流程
  - [x] 5.1 实现start_unified_dialogue方法
    - 在 `core/handle/doorlock_intent_handler.py` 中添加方法
    - 实现看护模式状态检查
    - 实现基准图片加载逻辑
    - 实现初次访客照片保存（用于意图总结）
    - 启动定时拍照任务
    - 实现主动问候播放
    - 实现对话循环逻辑
    - 实现对话结束条件检查
    - 停止定时拍照任务
    - 调用对话结束后处理
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 5.2 实现对话循环核心逻辑
    - 等待访客语音回复（ASR识别）
    - 将访客语音文本添加到对话历史
    - 从PhotoCacheManager获取最新缓存照片
    - 调用VLLM统一分析（传入语音文本+照片）
    - 播放AI回复（TTS）
    - 处理工具调用
    - 检查对话结束条件
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 9.3_

  - [x] 5.3 实现\_post_dialogue_processing方法
    - 在 `core/handle/doorlock_intent_handler.py` 中添加方法
    - 步骤1：检查快递状态（如果看护激活）
    - 步骤2：生成访客意图总结
    - 步骤3：保存访问记录
    - 步骤4：发送App通知
    - 步骤5：清理会话
    - 步骤6：清理照片缓存
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 9.5_

  - [x] 5.4 实现\_handle_tool_calls方法
    - 在 `core/handle/doorlock_intent_handler.py` 中添加方法
    - 遍历工具调用列表
    - 补充必要参数（device_id, session_id）
    - 执行工具函数
    - 高威胁特殊处理（立即播放警告）
    - 异常处理和日志记录
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [x] 5.5 Checkpoint - 确保意图处理器测试通过
    - Ensure all tests pass, ask the user if questions arise.

- [x] 6. 配置文件和提示词
  - [x] 6.1 创建doorlock_config.yaml配置文件
    - 创建 `config/doorlock_config.yaml` 文件
    - 添加unified_mode配置节（enabled, dialogue, guard, token_optimization）
    - 添加performance配置节（vllm_limits）
    - 添加photo_cache配置（interval_seconds, max_cache_size）
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 9.1, 9.2_

  - [x] 6.2 更新doorlock_prompts.yaml提示词文件
    - 在 `config/doorlock_prompts.yaml` 中添加core_role_and_style提示词
    - 添加dialogue_tasks提示词
    - 添加guard_tasks提示词
    - 添加tools_guide提示词
    - 添加final_package_check_prompt提示词
    - 添加intent_summary_prompt提示词
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x] 6.3 验证配置文件格式
    - 使用ruamel.yaml验证YAML格式
    - 验证所有必需字段存在
    - 验证数值范围合理
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x] 6.4 Checkpoint - 确保配置加载测试通过
    - Ensure all tests pass, ask the user if questions arise.

- [x] 7. 工具函数调整
  - [x] 7.1 验证enable_package_guard工具Schema
    - 在 `core/providers/doorlock/doorlock_tools.py` 中验证Schema
    - 确保参数定义正确（device_id, reason）
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 7.2 验证disable_package_guard工具Schema
    - 在 `core/providers/doorlock/doorlock_tools.py` 中验证Schema
    - 确保参数定义正确（device_id, reason）
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 7.3 验证update_package_baseline工具Schema
    - 在 `core/providers/doorlock/doorlock_tools.py` 中验证Schema
    - 确保参数定义正确（device_id）
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 7.4 验证report_package_status工具Schema
    - 在 `core/providers/doorlock/doorlock_tools.py` 中验证Schema
    - 确保参数定义正确（device_id, session_id, action, threat_level, description）
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 7.5 移除report_visitor_intent工具
    - 从工具Schema中移除report_visitor_intent
    - 更新工具函数文档
    - 验证移除后不影响其他功能
    - _Requirements: 7.5_

  - [x] 7.6 Checkpoint - 确保工具函数测试通过
    - Ensure all tests pass, ask the user if questions arise.

- [x] 8. 单元测试
  - [x] 8.1 测试提示词动态组合
    - 测试无基准图片时的提示词组合
    - 测试有基准图片时的提示词组合
    - 验证看护任务提示词正确添加
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 8.2 测试图片传递逻辑
    - 测试第一轮传入2张图片
    - 测试后续轮次传入1张图片
    - 验证is_first_round标志正确使用
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 3.2, 3.3, 3.4_

  - [x] 8.3 测试图片Token限制检查
    - 测试1张图片通过检查
    - 测试2张图片通过检查
    - 测试3张图片失败检查
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 8.4 测试对话历史截断
    - 测试对话历史超出限制时截断
    - 验证保留最新对话
    - 验证Token估算准确性
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 8.5 测试Token使用量监控
    - 测试输出Token警告触发
    - 测试输入Token警告触发
    - 测试总Token警告触发
    - 验证日志记录正确
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 8.6 测试final_package_check JSON解析
    - 测试正常JSON解析
    - 测试JSON解析失败返回默认值
    - 测试markdown代码块中的JSON提取
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 8.7 测试generate_intent_summary JSON解析
    - 测试正常JSON解析
    - 测试JSON解析失败返回默认值
    - 测试markdown代码块中的JSON提取
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 8.8 测试照片缓存管理
    - 测试添加照片到缓存
    - 测试获取最新照片
    - 测试超过10张照片时自动清理
    - 测试清理缓存
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 8.9 Checkpoint - 确保所有单元测试通过
    - Ensure all tests pass, ask the user if questions arise.

- [x] 9. 集成测试
  - [x] 9.1 测试仅对话模式（看护未激活）
    - 模拟访客到达（看护未激活）
    - 验证不传入基准图片
    - 验证不启动定时拍照任务
    - 验证对话正常进行
    - 验证对话结束后不检查快递
    - 验证意图总结正常生成
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 9.2 测试统一模式（看护激活）
    - 启用看护模式
    - 模拟访客到达
    - 验证启动定时拍照任务
    - 验证第一轮传入基准图片
    - 验证后续轮次不传入基准图片
    - 验证每轮使用最新缓存照片
    - 模拟访客可疑行为
    - 验证AI调用report_package_status
    - 验证对话结束后检查快递状态
    - 验证返回格式化JSON结果
    - 验证停止定时拍照任务
    - 验证清理照片缓存
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 9.3 测试高威胁打断对话
    - 统一模式对话中
    - 模拟AI检测到高威胁
    - 验证立即调用report_package_status
    - 验证播放警告语音
    - 验证对话可以继续或结束
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [x] 9.4 测试访客语音文本传递
    - 验证ASR识别的语音文本正确传递给VLLM
    - 验证对话历史包含访客语音文本
    - 验证AI回复基于访客语音内容
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 9.5 Checkpoint - 确保所有集成测试通过
    - Ensure all tests pass, ask the user if questions arise.

- [x] 10. 边界情况测试
  - [x] 10.1 测试看护未激活时主人取快递
    - 看护模式未激活
    - 主人到访
    - 验证正常开门，不启动对话
    - 验证不检查快递状态
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 10.2 测试主人取快递但不关闭看护
    - 看护模式激活
    - 主人到访并取走快递
    - 验证判定为低威胁
    - 验证看护模式保持激活（不自动关闭）
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 10.3 测试JSON解析失败场景
    - 模拟VLLM返回非JSON格式
    - 验证返回默认结果
    - 验证不抛出异常
    - 验证记录错误日志
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 10.4 测试图片Token超限场景
    - 尝试传入3张图片
    - 验证抛出ValueError异常
    - 验证记录错误日志
    - 验证不调用VLLM
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 10.5 测试VLLM调用失败场景
    - 模拟VLLM服务不可用
    - 验证返回默认响应
    - 验证记录错误日志
    - 验证对话可以继续或优雅结束
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 10.6 测试工具调用执行失败场景
    - 模拟工具函数执行异常
    - 验证记录错误日志
    - 验证对话继续进行
    - 验证不影响其他功能
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 10.7 测试定时拍照任务异常
    - 模拟拍照失败
    - 验证任务继续运行
    - 验证记录错误日志
    - 验证对话不受影响
    - _Requirements: 9.1, 9.2, 9.4, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 10.8 测试照片缓存满时的处理
    - 添加超过10张照片
    - 验证自动清理最旧的照片
    - 验证最新照片保留
    - 验证内存不会无限增长
    - _Requirements: 9.1, 9.2, 9.5_

  - [x] 10.9 Checkpoint - 确保所有边界测试通过
    - Ensure all tests pass, ask the user if questions arise.

- [x] 11. 性能测试
  - [x] 11.1 测试Token消耗
    - 模拟10轮对话
    - 记录每轮Token消耗
    - 验证总消耗在预期范围内（<120K）
    - 验证第一轮消耗最高（~14K）
    - 验证后续轮次消耗稳定（~7K）
    - 验证对话结束检查消耗（~15K）
    - 验证意图总结消耗（~8K）
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 11.2 测试响应时间
    - 测试VLLM调用响应时间
    - 验证响应时间<3秒
    - 测试对话结束后处理时间
    - 验证处理时间<10秒
    - 测试完整对话流程时间
    - 识别性能瓶颈
    - _Requirements: 所有需求_

  - [x] 11.3 测试定时拍照性能影响
    - 验证定时拍照不阻塞对话
    - 验证照片缓存不影响响应速度
    - 测试内存使用情况
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 11.4 Final Checkpoint - 确保所有性能测试通过
    - Ensure all tests pass, ask the user if questions arise.

- [x] 12. 文档更新
  - [x] 12.1 更新VLLM提供者API文档
    - 在 `docs/my_docs/` 中更新API文档
    - 添加analyze_unified方法文档
    - 添加final_package_check方法文档
    - 添加generate_intent_summary方法文档
    - 添加使用示例
    - _Requirements: 所有需求_

  - [x] 12.2 更新意图处理器API文档
    - 在 `docs/my_docs/` 中更新API文档
    - 添加start_unified_dialogue方法文档
    - 添加定时拍照机制说明
    - 添加照片缓存管理说明
    - 添加使用示例
    - _Requirements: 所有需求_

  - [x] 12.3 编写统一模式使用说明
    - 创建用户手册文档
    - 说明统一模式的优势
    - 说明如何启用/禁用统一模式
    - 提供配置示例
    - _Requirements: 所有需求_

  - [x] 12.4 编写配置指南
    - 说明doorlock_config.yaml配置项
    - 说明doorlock_prompts.yaml提示词配置
    - 提供配置最佳实践
    - 说明性能调优参数
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x] 12.5 编写提示词自定义指南
    - 说明三层提示词结构
    - 说明如何自定义提示词
    - 提供提示词优化建议
    - 说明提示词测试方法
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x] 12.6 编写故障排查指南
    - 列出常见问题和解决方案
    - 说明日志查看方法
    - 说明性能监控方法
    - 提供降级方案
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 12.7 编写迁移指南
    - 说明从分离模式迁移到统一模式的步骤
    - 说明配置变更
    - 说明API变更
    - 提供迁移检查清单
    - 说明降级方案
    - _Requirements: 所有需求_

  - [x] 12.8 Checkpoint - 确保文档完整性
    - Ensure all documentation is complete, ask the user if questions arise.

- [ ] 13. 部署准备
  - [ ] 13.1 代码审查
    - 审查VLLM提供者代码
    - 审查意图处理器代码
    - 审查照片缓存管理器代码
    - 审查配置文件
    - 审查提示词内容
    - 审查测试代码
    - 审查文档
    - _Requirements: 所有需求_

  - [ ] 13.2 小规模试运行
    - 选择测试设备
    - 部署到测试环境
    - 执行功能测试
    - 执行性能测试
    - 收集日志和指标
    - 分析问题和优化
    - _Requirements: 所有需求_

  - [ ] 13.3 正式部署
    - 准备部署脚本
    - 备份现有配置
    - 部署新代码
    - 更新配置文件
    - 重启服务
    - 验证功能正常
    - 监控系统运行状态
    - _Requirements: 所有需求_

  - [ ] 13.4 Final Checkpoint - 部署完成验证
    - Ensure deployment is successful, ask the user if questions arise.
