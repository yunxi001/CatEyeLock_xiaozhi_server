# 统一模式迁移指南

## 概述

本文档指导如何从分离模式迁移到统一智能看护对话模式，包括迁移步骤、配置变更、API 变更、测试验证和降级方案。

## 迁移前准备

### 1. 了解两种模式的区别

| 特性           | 分离模式（旧版） | 统一模式（新版）  |
| -------------- | ---------------- | ----------------- |
| 对话和看护     | 分离处理         | 统一处理          |
| 看护激活时对话 | 不可用           | 可用              |
| Token 消耗     | 较高             | 优化约 30%        |
| 用户体验       | 不连贯           | 无缝              |
| 实时拍照       | 无               | 有（每 5 秒）     |
| 对话结束后处理 | 简单             | 完整（检查+总结） |

---

### 2. 评估迁移影响

**影响范围**：

- 配置文件需要更新
- 提示词需要重新组织
- 对话流程有变化
- API 调用方式有变化

**影响程度**：

- 低：仅使用对话功能
- 中：使用对话和看护功能
- 高：深度自定义提示词和流程

---

### 3. 备份现有配置

```bash
# 备份配置文件
cd main/xiaozhi-server
cp config/doorlock_config.yaml config/doorlock_config.yaml.old
cp config/doorlock_prompts.yaml config/doorlock_prompts.yaml.old

# 备份数据库
mysqldump -u root -p xiaozhi > backup_before_migration_$(date +%Y%m%d).sql

# 备份代码
git add .
git commit -m "备份：迁移到统一模式前"
git tag before-unified-mode
```

---

## 迁移步骤

### 步骤 1：更新配置文件

#### 1.1 更新 doorlock_config.yaml

**旧版配置**（分离模式）：

```yaml
# 旧版没有 unified_mode 配置
dialogue:
  max_rounds: 10
  timeout_seconds: 30

guard:
  enabled: true
  check_interval: 60 # 定时检查
```

**新版配置**（统一模式）：

```yaml
# 统一模式配置
unified_mode:
  enabled: true # 启用统一模式

  # 对话配置
  dialogue:
    max_rounds: 10 # 最大对话轮次
    timeout_seconds: 30 # 沉默超时时间（秒）

  # 看护配置
  guard:
    threat_detection: "behavior_based" # 基于行为触发
    report_threshold: "medium" # 威胁等级≥medium 时报告

  # Token 优化
  token_optimization:
    baseline_image_once: true # 仅第一轮传入基准图片
    reuse_context: true # 依赖 AI 上下文理解

# 照片缓存配置（新增）
photo_cache:
  interval_seconds: 5 # 拍照间隔（秒）
  max_cache_size: 10 # 最大缓存数量

# 性能配置（新增）
performance:
  vllm_limits:
    model_context_limit: 262144 # 模型上下文窗口
    max_input_tokens: 260096 # 最大输入 Token
    max_output_tokens: 32768 # 最大输出 Token
    max_image_tokens: 16384 # 最大图片 Token
    tokens_per_image: 7000 # 每张图片 Token 数
    input_warning_ratio: 0.8 # 输入 Token 警告阈值
    total_warning_ratio: 0.8 # 总 Token 警告阈值
```

**迁移脚本**：

```bash
#!/bin/bash
# migrate_config.sh - 配置迁移脚本

# 读取旧配置
OLD_MAX_ROUNDS=$(grep "max_rounds" config/doorlock_config.yaml | awk '{print $2}')
OLD_TIMEOUT=$(grep "timeout_seconds" config/doorlock_config.yaml | awk '{print $2}')

# 生成新配置
cat > config/doorlock_config.yaml << EOF
# 统一模式配置
unified_mode:
  enabled: true

  dialogue:
    max_rounds: ${OLD_MAX_ROUNDS:-10}
    timeout_seconds: ${OLD_TIMEOUT:-30}

  guard:
    threat_detection: "behavior_based"
    report_threshold: "medium"

  token_optimization:
    baseline_image_once: true
    reuse_context: true

photo_cache:
  interval_seconds: 5
  max_cache_size: 10

performance:
  vllm_limits:
    model_context_limit: 262144
    max_input_tokens: 260096
    max_output_tokens: 32768
    max_image_tokens: 16384
    tokens_per_image: 7000
    input_warning_ratio: 0.8
    total_warning_ratio: 0.8
EOF

echo "配置迁移完成"
```

---

#### 1.2 更新 doorlock_prompts.yaml

**旧版配置**（分离模式）：

```yaml
# 旧版：单一提示词
system_prompt: |
  你是一个智能门锁的AI助手。
  你的任务是与访客对话，了解来访目的。

guard_prompt: |
  你是一个智能门锁的AI安保系统。
  你的任务是监控门口快递的安全。
```

**新版配置**（统一模式）：

```yaml
# 新版：三层动态组合结构

# 第一层：核心角色和风格
core_role_and_style: |
  【系统角色】
  你是一个智能门锁的AI门卫助手，负责管理门口的访客接待和安全监控。

  【对话风格指南】
  - 礼貌正式，但不失亲和力
  - 根据访客身份调整语气
  - 使用简洁明了的语言
  - 对话保持简洁，每次回复不超过2-3句话

# 第二层：对话任务
dialogue_tasks: |
  【对话任务】
  你的主要任务是与访客进行自然对话，了解来访目的。

  - 主动引导对话，明确询问来访目的
  - 对重要信息进行二次确认
  - 识别推销意图时礼貌但坚定地拒绝
  - 不要在对话中提及快递监控功能

# 第三层：看护任务
guard_tasks: |
  【看护任务】（后台任务，不影响对话）
  你同时负责监控门口快递的安全。

  **重要**：这是后台任务，不要在对话中提及监控功能。

  【监控要点】
  - 观察访客是否靠近、触碰、翻看快递
  - 判断访客行为是否可疑
  - 评估威胁等级（low/medium/high）

  【触发条件】
  仅在以下情况调用 report_package_status：
  - 访客靠近快递并触碰、翻看
  - 访客长时间停留在快递旁边（>10秒）
  - 访客试图拿走快递（非主人）
  - 访客破坏、踢踹快递

  【威胁等级判断】
  - low：路人经过、主人取快递
  - medium：翻看快递、长时间停留
  - high：非主人拿走快递、破坏快递

# 第四层：工具调用指南
tools_guide: |
  【工具调用说明】
  你可以调用以下4个工具函数：

  1. enable_package_guard
  2. disable_package_guard
  3. update_package_baseline
  4. report_package_status

# 专用提示词（新增）
final_package_check_prompt: |
  【任务】
  访客已离开，请对比基准图片和当前图片，判断快递的最终状态。
  ...

intent_summary_prompt: |
  【任务】
  根据完整的对话历史和访客照片，生成结构化的访客意图总结。
  ...
```

**迁移建议**：

1. 将旧版 `system_prompt` 拆分为 `core_role_and_style` 和 `dialogue_tasks`
2. 将旧版 `guard_prompt` 改写为 `guard_tasks`
3. 添加 `tools_guide`、`final_package_check_prompt`、`intent_summary_prompt`

---

### 步骤 2：更新代码

#### 2.1 更新 VLLM 提供者调用

**旧版代码**（分离模式）：

```python
# 对话模式
result = await vllm.analyze_dialogue(
    visitor_image=visitor_img,
    dialogue_history=history
)

# 看护模式
result = await vllm.analyze_guard(
    current_image=current_img,
    baseline_image=baseline_img
)
```

**新版代码**（统一模式）：

```python
# 统一模式
result = await vllm.analyze_unified(
    visitor_image=visitor_img,
    baseline_image=baseline_img,  # 看护激活时传入
    dialogue_history=history,
    is_first_round=is_first_round
)

# 对话结束后检查
check_result = await vllm.final_package_check(
    current_image=current_img,
    baseline_image=baseline_img
)

# 生成意图总结
summary = await vllm.generate_intent_summary(
    visitor_image=visitor_img,
    dialogue_history=history
)
```

---

#### 2.2 更新意图处理器调用

**旧版代码**（分离模式）：

```python
# 对话模式
result = await intent_handler.start_dialogue(
    device_id=device_id,
    session_id=session_id,
    visitor_image=visitor_img
)

# 看护模式
result = await intent_handler.start_guard(
    device_id=device_id,
    baseline_image=baseline_img
)
```

**新版代码**（统一模式）：

```python
# 统一模式
result = await intent_handler.start_unified_dialogue(
    device_id=device_id,
    session_id=session_id,
    person_info=person_info,
    visitor_image=visitor_img,
    conn=conn
)
```

---

### 步骤 3：数据库迁移

#### 3.1 添加新字段

```sql
-- 添加照片缓存相关字段
ALTER TABLE doorlock_sessions
ADD COLUMN photo_cache_enabled BOOLEAN DEFAULT TRUE,
ADD COLUMN photo_cache_count INT DEFAULT 0;

-- 添加统一模式相关字段
ALTER TABLE doorlock_visits
ADD COLUMN dialogue_mode VARCHAR(20) DEFAULT 'unified',
ADD COLUMN token_consumption INT DEFAULT 0;
```

---

#### 3.2 迁移历史数据

```sql
-- 更新历史数据
UPDATE doorlock_visits
SET dialogue_mode = 'separated'
WHERE created_at < '2024-02-16';

UPDATE doorlock_visits
SET dialogue_mode = 'unified'
WHERE created_at >= '2024-02-16';
```

---

### 步骤 4：测试验证

#### 4.1 单元测试

```bash
# 运行单元测试
cd main/xiaozhi-server
python -m pytest test_prompt_composition.py
python -m pytest test_image_passing.py
python -m pytest test_token_management.py
```

---

#### 4.2 集成测试

```bash
# 运行集成测试
python -m pytest test_unified_dialogue.py
python -m pytest test_integration_unified_dialogue.py
```

---

#### 4.3 手动测试

**测试场景 1：仅对话模式**

```
1. 关闭看护模式
2. 模拟访客到访
3. 验证对话正常进行
4. 验证不传入基准图片
5. 验证意图总结正常生成
```

**测试场景 2：统一模式**

```
1. 启用看护模式
2. 模拟访客到访
3. 验证对话正常进行
4. 验证第一轮传入基准图片
5. 验证后续轮次不传入基准图片
6. 验证定时拍照正常运行
7. 验证对话结束后检查快递状态
8. 验证意图总结正常生成
```

---

### 步骤 5：灰度发布

#### 5.1 小范围测试

```yaml
# 仅在测试设备上启用统一模式
unified_mode:
  enabled: true
  test_devices:
    - "doorlock_test_001"
    - "doorlock_test_002"
```

---

#### 5.2 逐步扩大范围

```
第 1 周：10% 设备
第 2 周：30% 设备
第 3 周：50% 设备
第 4 周：100% 设备
```

---

#### 5.3 监控指标

| 指标       | 目标值      | 监控方法 |
| ---------- | ----------- | -------- |
| 对话成功率 | >95%        | 查看日志 |
| Token 消耗 | <120K/10 轮 | 查看日志 |
| 响应时间   | <5 秒/轮    | 查看日志 |
| 错误率     | <1%         | 查看日志 |
| 用户满意度 | >4.5/5      | 用户反馈 |

---

## 配置变更清单

### 新增配置项

| 配置项                                                | 默认值           | 说明                 |
| ----------------------------------------------------- | ---------------- | -------------------- |
| `unified_mode.enabled`                                | `true`           | 启用统一模式         |
| `unified_mode.dialogue.max_rounds`                    | `10`             | 最大对话轮次         |
| `unified_mode.dialogue.timeout_seconds`               | `30`             | 沉默超时时间         |
| `unified_mode.guard.threat_detection`                 | `behavior_based` | 威胁检测方式         |
| `unified_mode.guard.report_threshold`                 | `medium`         | 报告阈值             |
| `unified_mode.token_optimization.baseline_image_once` | `true`           | 仅第一轮传入基准图片 |
| `unified_mode.token_optimization.reuse_context`       | `true`           | 依赖上下文理解       |
| `photo_cache.interval_seconds`                        | `5`              | 拍照间隔             |
| `photo_cache.max_cache_size`                          | `10`             | 最大缓存数量         |
| `performance.vllm_limits.*`                           | 见配置           | VLLM 性能限制        |

---

### 废弃配置项

| 配置项                 | 替代方案               |
| ---------------------- | ---------------------- |
| `dialogue.enabled`     | `unified_mode.enabled` |
| `guard.check_interval` | 改为基于行为触发       |
| `guard.enabled`        | 统一到 `unified_mode`  |

---

## API 变更清单

### VLLM 提供者 API

#### 新增方法

| 方法                           | 说明                |
| ------------------------------ | ------------------- |
| `analyze_unified()`            | 统一模式分析        |
| `final_package_check()`        | 对话结束后快递检查  |
| `generate_intent_summary()`    | 生成意图总结        |
| `_build_unified_prompt()`      | 动态组合提示词      |
| `_check_image_token_limit()`   | 检查图片 Token 限制 |
| `_truncate_dialogue_history()` | 截断对话历史        |
| `_estimate_tokens()`           | 估算文本 Token      |
| `_estimate_image_tokens()`     | 估算图片 Token      |

#### 废弃方法

| 方法                 | 替代方案                |
| -------------------- | ----------------------- |
| `analyze_dialogue()` | `analyze_unified()`     |
| `analyze_guard()`    | `final_package_check()` |

---

### 意图处理器 API

#### 新增方法

| 方法                          | 说明             |
| ----------------------------- | ---------------- |
| `start_unified_dialogue()`    | 启动统一模式对话 |
| `start_photo_capture_task()`  | 启动定时拍照任务 |
| `stop_photo_capture_task()`   | 停止定时拍照任务 |
| `_post_dialogue_processing()` | 对话结束后处理   |
| `_handle_tool_calls()`        | 处理工具调用     |

#### 废弃方法

| 方法               | 替代方案                          |
| ------------------ | --------------------------------- |
| `start_dialogue()` | `start_unified_dialogue()`        |
| `start_guard()`    | 统一到 `start_unified_dialogue()` |

---

### 工具函数 API

#### 移除工具

| 工具                    | 原因                       |
| ----------------------- | -------------------------- |
| `report_visitor_intent` | 改为对话结束后程序主动询问 |

---

## 迁移检查清单

### 迁移前检查

- [ ] 备份配置文件
- [ ] 备份数据库
- [ ] 备份代码
- [ ] 阅读迁移指南
- [ ] 了解新旧模式区别
- [ ] 评估迁移影响

---

### 迁移中检查

- [ ] 更新 doorlock_config.yaml
- [ ] 更新 doorlock_prompts.yaml
- [ ] 更新 VLLM 提供者调用
- [ ] 更新意图处理器调用
- [ ] 执行数据库迁移
- [ ] 运行单元测试
- [ ] 运行集成测试
- [ ] 执行手动测试

---

### 迁移后检查

- [ ] 验证对话功能正常
- [ ] 验证看护功能正常
- [ ] 验证定时拍照正常
- [ ] 验证 Token 消耗符合预期
- [ ] 验证响应时间符合预期
- [ ] 验证日志记录正常
- [ ] 验证错误处理正常
- [ ] 收集用户反馈

---

## 降级方案

### 方案 1：禁用统一模式

**适用场景**：统一模式不稳定，需要回退

**操作步骤**：

```yaml
# config/doorlock_config.yaml
unified_mode:
  enabled: false # 禁用统一模式
```

**效果**：

- 回退到分离模式
- 看护模式激活时无法对话
- 系统稳定性提高

---

### 方案 2：恢复旧版配置

**适用场景**：新配置导致问题

**操作步骤**：

```bash
# 恢复旧版配置
cp config/doorlock_config.yaml.old config/doorlock_config.yaml
cp config/doorlock_prompts.yaml.old config/doorlock_prompts.yaml

# 重启服务
python app.py
```

---

### 方案 3：回滚代码

**适用场景**：代码变更导致问题

**操作步骤**：

```bash
# 回滚到迁移前版本
git reset --hard before-unified-mode

# 恢复数据库
mysql -u root -p xiaozhi < backup_before_migration_20240216.sql

# 重启服务
python app.py
```

---

## 常见问题

### Q1：迁移需要多长时间？

**答**：取决于系统规模和自定义程度

- 小规模（<10 设备）：1-2 小时
- 中规模（10-100 设备）：半天
- 大规模（>100 设备）：1-2 天

---

### Q2：迁移会影响现有功能吗？

**答**：不会。统一模式向后兼容

- 对话功能保持不变
- 看护功能保持不变
- 仅增强了两者的集成

---

### Q3：迁移失败如何处理？

**答**：使用降级方案

1. 禁用统一模式
2. 恢复旧版配置
3. 回滚代码
4. 查看日志分析原因

---

### Q4：迁移后 Token 消耗会增加吗？

**答**：不会，反而会降低

- 统一模式优化了 Token 消耗
- 仅第一轮传入基准图片
- 节省约 30% Token

---

### Q5：迁移后需要重新训练模型吗？

**答**：不需要

- 使用相同的 VLLM 模型
- 仅改变提示词组合方式
- 不影响模型本身

---

## 相关文档

- [统一模式用户手册](./unified-mode-user-guide.md)
- [配置指南](./doorlock-configuration-guide.md)
- [VLLM 提供者 API 参考](./doorlock-vllm-api-reference.md)
- [意图处理器 API 参考](./doorlock-intent-handler-api-reference.md)
- [故障排查指南](./doorlock-troubleshooting-guide.md)

---

## 更新日志

| 版本  | 日期       | 说明               |
| ----- | ---------- | ------------------ |
| 1.0.0 | 2024-02-16 | 初始版本，迁移指南 |
