# 智能门锁提示词自定义指南

## 概述

本文档详细说明智能门锁系统的提示词结构、自定义方法、优化建议和测试方法。通过自定义提示词，可以调整 AI 的行为风格、对话策略和监控逻辑。

## 提示词架构

### 三层动态组合结构

智能门锁系统采用三层提示词结构，根据看护模式状态动态组合：

```
┌─────────────────────────────────────┐
│  第一层：核心角色和风格（共享）        │
│  - 系统角色定位                       │
│  - 对话风格指南                       │
│  - 语气和语言要求                     │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  第二层：对话任务（总是包含）          │
│  - 主要任务描述                       │
│  - 对话引导策略                       │
│  - 特殊情况处理                       │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  第三层：看护任务（条件添加）          │
│  - 监控要点                          │
│  - 触发条件                          │
│  - 威胁等级判断                       │
│  ⚠️ 仅在看护模式激活时添加             │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  第四层：工具调用指南（总是包含）      │
│  - 可用工具列表                       │
│  - 工具功能说明                       │
│  - 触发时机说明                       │
└─────────────────────────────────────┘
```

### 动态组合逻辑

```python
def build_unified_prompt(has_baseline_image: bool) -> str:
    """动态组合提示词"""
    prompt_parts = [
        prompts["core_role_and_style"],  # 第一层：总是包含
        prompts["dialogue_tasks"]        # 第二层：总是包含
    ]

    # 第三层：条件添加
    if has_baseline_image:
        prompt_parts.append(prompts["guard_tasks"])

    # 第四层：总是包含
    prompt_parts.append(prompts["tools_guide"])

    return "\n\n".join(prompt_parts)
```

---

## 提示词配置文件

### 文件位置

```
config/doorlock_prompts.yaml
```

### 文件结构

```yaml
# 第一层：核心角色和风格
core_role_and_style: |
  提示词内容...

# 第二层：对话任务
dialogue_tasks: |
  提示词内容...

# 第三层：看护任务
guard_tasks: |
  提示词内容...

# 第四层：工具调用指南
tools_guide: |
  提示词内容...

# 专用提示词
final_package_check_prompt: |
  提示词内容...

intent_summary_prompt: |
  提示词内容...
```

---

## 提示词详解

### 第一层：核心角色和风格

#### 默认配置

```yaml
core_role_and_style: |
  【系统角色】
  你是一个智能门锁的AI门卫助手，负责管理门口的访客接待和安全监控。

  【对话风格指南】
  - 礼貌正式，但不失亲和力
  - 根据访客身份调整语气
  - 使用简洁明了的语言
  - 对话保持简洁，每次回复不超过2-3句话
```

#### 自定义建议

**1. 调整角色定位**

```yaml
# 示例 1：更亲切的角色
core_role_and_style: |
  【系统角色】
  你是一个智能门锁的AI管家，像朋友一样热情接待每一位访客。

# 示例 2：更专业的角色
core_role_and_style: |
  【系统角色】
  你是一个智能门锁的AI安保系统，负责严格管理门口的访客和安全。
```

**2. 调整对话风格**

```yaml
# 示例 1：更简洁的风格
core_role_and_style: |
  【对话风格指南】
  - 简洁直接，不啰嗦
  - 每次回复不超过1句话
  - 使用口语化表达

# 示例 2：更详细的风格
core_role_and_style: |
  【对话风格指南】
  - 详细说明，确保访客理解
  - 每次回复可以3-5句话
  - 使用正式书面语
```

**3. 调整语气**

```yaml
# 示例 1：更热情的语气
core_role_and_style: |
  【对话风格指南】
  - 热情友好，使用感叹号
  - 多用"欢迎"、"很高兴"等词汇
  - 表达积极正面的态度

# 示例 2：更严肃的语气
core_role_and_style: |
  【对话风格指南】
  - 严肃认真，不使用感叹号
  - 多用"请"、"需要"等词汇
  - 保持专业距离感
```

---

### 第二层：对话任务

#### 默认配置

```yaml
dialogue_tasks: |
  【对话任务】
  你的主要任务是与访客进行自然对话，了解来访目的。

  - 主动引导对话，明确询问来访目的
  - 对重要信息进行二次确认
  - 识别推销意图时礼貌但坚定地拒绝
  - 不要在对话中提及快递监控功能
```

#### 自定义建议

**1. 调整对话策略**

```yaml
# 示例 1：更主动的策略
dialogue_tasks: |
  【对话任务】
  - 第一句话直接询问来访目的
  - 对模糊回答追问细节
  - 对可疑情况立即质疑
  - 对推销直接拒绝

# 示例 2：更被动的策略
dialogue_tasks: |
  【对话任务】
  - 等待访客主动说明来访目的
  - 对访客回答表示理解
  - 对可疑情况委婉询问
  - 对推销礼貌拒绝
```

**2. 添加特殊场景处理**

```yaml
dialogue_tasks: |
  【对话任务】
  你的主要任务是与访客进行自然对话，了解来访目的。

  【特殊场景处理】
  - 快递员：询问快递放置位置，提供看护服务
  - 外卖员：询问是否需要联系主人
  - 维修工：确认是否有预约，核实身份
  - 推销员：礼貌但坚定地拒绝
  - 陌生人：询问来访目的，必要时通知主人
```

**3. 添加对话引导技巧**

```yaml
dialogue_tasks: |
  【对话任务】
  你的主要任务是与访客进行自然对话，了解来访目的。

  【对话引导技巧】
  - 使用开放式问题引导访客说明意图
  - 对关键信息进行复述确认
  - 对矛盾信息提出质疑
  - 对重要事项提醒访客
```

---

### 第三层：看护任务

#### 默认配置

```yaml
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
```

#### 自定义建议

**1. 调整监控灵敏度**

```yaml
# 示例 1：更敏感的监控
guard_tasks: |
  【触发条件】
  在以下情况调用 report_package_status：
  - 访客靠近快递（距离<1米）
  - 访客停留在快递旁边（>5秒）
  - 访客看向快递
  - 访客触碰快递
  - 访客拿走快递

# 示例 2：更宽松的监控
guard_tasks: |
  【触发条件】
  仅在以下情况调用 report_package_status：
  - 访客试图拿走快递（非主人）
  - 访客破坏快递
```

**2. 调整威胁等级标准**

```yaml
# 示例 1：更严格的标准
guard_tasks: |
  【威胁等级判断】
  - low：路人经过（不靠近快递）
  - medium：靠近快递、看向快递
  - high：触碰快递、拿走快递、破坏快递

# 示例 2：更宽松的标准
guard_tasks: |
  【威胁等级判断】
  - low：路人经过、靠近快递、看向快递
  - medium：触碰快递、翻看快递
  - high：拿走快递、破坏快递
```

**3. 添加特殊情况处理**

```yaml
guard_tasks: |
  【特殊情况处理】
  - 主人取快递：判定为 low，不报告
  - 邻居帮忙取快递：询问是否有授权，判定为 medium
  - 快递员补送：判定为 low，不报告
  - 陌生人拿走快递：判定为 high，立即报告
```

---

### 第四层：工具调用指南

#### 默认配置

```yaml
tools_guide: |
  【工具调用说明】
  你可以调用以下4个工具函数：

  1. enable_package_guard
     - 功能：启用快递看护模式
     - 触发时机：访客提到"快递放门口了"
     - 参数：device_id, reason

  2. disable_package_guard
     - 功能：关闭快递看护模式
     - 触发时机：判断快递已被主人取走
     - 参数：device_id, reason

  3. update_package_baseline
     - 功能：更新看护基准图片
     - 触发时机：访客说"我把快递放这了"
     - 参数：device_id

  4. report_package_status
     - 功能：报告快递状态和威胁等级
     - 触发时机：检测到访客可疑行为（威胁等级≥medium）
     - 参数：device_id, session_id, action, threat_level, description
```

#### 自定义建议

**1. 调整触发时机**

```yaml
tools_guide: |
  1. enable_package_guard
     - 触发时机：
       * 访客提到"快递放门口了"
       * 访客提到"外卖放这了"
       * 访客提到"包裹在门口"

  2. disable_package_guard
     - 触发时机：
       * 主人明确说"快递已取走"
       * 主人说"不用看护了"
       * 主人说"关闭看护"
```

**2. 添加使用示例**

```yaml
tools_guide: |
  1. enable_package_guard
     - 使用示例：
       访客："我是快递员，快递放门口了"
       AI：调用 enable_package_guard(device_id="xxx", reason="快递员送快递")
       AI："好的，我会帮您看护快递"
```

**3. 添加注意事项**

```yaml
tools_guide: |
  【工具调用注意事项】
  - 每个工具只在必要时调用一次
  - 调用前确认参数完整
  - 调用后向访客确认
  - 调用失败时记录日志
```

---

### 专用提示词

#### final_package_check_prompt

**用途**：对话结束后的快递状态检查

**默认配置**：

````yaml
final_package_check_prompt: |
  【任务】
  访客已离开，请对比基准图片和当前图片，判断快递的最终状态。

  【要求】
  - 对比两张图片，判断快递是否被移动、拿走或破坏
  - 评估威胁等级
  - 以纯JSON格式返回结果

  【输出格式】
  ```json
  {
    "threat_level": "low|medium|high",
    "action": "taking|searching|damaging|normal|passing",
    "description": "详细描述你看到的情况"
  }
````

【判断标准】

- 快递位置未变化 = low + normal
- 快递被移动但未拿走 = medium + searching
- 快递被拿走 = high + taking（除非是主人）
- 快递被破坏 = high + damaging

````

**自定义建议**：

```yaml
# 示例：更详细的判断标准
final_package_check_prompt: |
  【判断标准】
  1. 快递位置对比
     - 位置完全一致 = normal
     - 位置略有偏移（<10cm）= normal
     - 位置明显偏移（>10cm）= searching
     - 快递消失 = taking

  2. 快递状态对比
     - 包装完好 = normal
     - 包装有轻微损坏 = searching
     - 包装严重损坏 = damaging
     - 快递被打开 = damaging

  3. 威胁等级评估
     - 所有指标正常 = low
     - 任一指标异常 = medium
     - 快递消失或严重损坏 = high
````

---

#### intent_summary_prompt

**用途**：生成访客意图总结

**默认配置**：

````yaml
intent_summary_prompt: |
  【任务】
  根据完整的对话历史和访客照片，生成结构化的访客意图总结。

  【要求】
  - 识别访客意图类型
  - 提取重要信息（留言、提醒）
  - 生成完整总结
  - 提供AI分析

  【输出格式】
  ```json
  {
    "intent_type": "delivery|visit|sales|maintenance|other",
    "summary": "简洁的总结（一句话）",
    "important_notes": [
      "【留言】...",
      "【提醒】..."
    ],
    "ai_analysis": "详细的AI分析，包括访客特征、行为观察、建议等"
  }
````

【意图类型说明】

- delivery: 送快递/外卖
- visit: 拜访朋友/家人
- sales: 推销产品/服务
- maintenance: 维修/物业工作
- other: 其他情况

````

**自定义建议**：

```yaml
# 示例：扩展意图类型
intent_summary_prompt: |
  【意图类型说明】
  - delivery: 送快递/外卖
  - visit: 拜访朋友/家人
  - sales: 推销产品/服务
  - maintenance: 维修/物业工作
  - survey: 问卷调查
  - charity: 慈善募捐
  - neighbor: 邻居串门
  - emergency: 紧急情况
  - other: 其他情况
````

---

## 提示词优化建议

### 1. 明确性原则

**不好的示例**：

```yaml
dialogue_tasks: |
  与访客对话，了解情况。
```

**好的示例**：

```yaml
dialogue_tasks: |
  【对话任务】
  你的主要任务是与访客进行自然对话，了解来访目的。

  【具体要求】
  - 第一句话询问来访目的
  - 对模糊回答追问细节
  - 对重要信息进行二次确认
  - 识别推销意图时礼貌拒绝
```

---

### 2. 结构化原则

**不好的示例**：

```yaml
guard_tasks: |
  监控快递，发现可疑行为报告，判断威胁等级。
```

**好的示例**：

```yaml
guard_tasks: |
  【监控要点】
  - 观察访客是否靠近快递
  - 判断访客行为是否可疑

  【触发条件】
  - 访客触碰快递
  - 访客拿走快递

  【威胁等级】
  - low：路人经过
  - medium：翻看快递
  - high：拿走快递
```

---

### 3. 示例化原则

**不好的示例**：

```yaml
tools_guide: |
  调用工具函数完成任务。
```

**好的示例**：

```yaml
tools_guide: |
  【工具调用示例】
  访客："我是快递员，快递放门口了"
  AI：调用 enable_package_guard(device_id="xxx", reason="快递员送快递")
  AI："好的，我会帮您看护快递"
```

---

### 4. 优先级原则

**不好的示例**：

```yaml
dialogue_tasks: |
  了解来访目的，监控快递安全。
```

**好的示例**：

```yaml
dialogue_tasks: |
  【主要任务】
  与访客进行自然对话，了解来访目的。

  【次要任务】
  在后台监控快递安全（不要在对话中提及）。

  **重要**：对话优先级高于监控任务。
```

---

### 5. 约束性原则

**不好的示例**：

```yaml
core_role_and_style: |
  你是一个AI助手。
```

**好的示例**：

```yaml
core_role_and_style: |
  【系统角色】
  你是一个智能门锁的AI门卫助手。

  【对话约束】
  - 每次回复不超过2-3句话
  - 不要提及监控功能
  - 不要泄露主人隐私
  - 不要承诺无法实现的功能
```

---

## 提示词测试方法

### 1. 单元测试

**测试目标**：验证提示词动态组合逻辑

**测试代码**：

```python
def test_prompt_composition():
    """测试提示词动态组合"""
    vllm = DoorlockVLLMProvider(config, logger)

    # 测试无基准图片
    prompt_no_baseline = vllm._build_unified_prompt(has_baseline=False)
    assert "看护任务" not in prompt_no_baseline
    assert "对话任务" in prompt_no_baseline

    # 测试有基准图片
    prompt_with_baseline = vllm._build_unified_prompt(has_baseline=True)
    assert "看护任务" in prompt_with_baseline
    assert "对话任务" in prompt_with_baseline
```

---

### 2. 集成测试

**测试目标**：验证提示词在实际对话中的效果

**测试步骤**：

1. 启动统一模式对话
2. 模拟访客输入
3. 检查 AI 回复是否符合预期
4. 检查工具调用是否正确

**测试代码**：

```python
async def test_prompt_in_dialogue():
    """测试提示词在对话中的效果"""
    # 模拟访客输入
    visitor_input = "我是来送快递的"

    # 调用 VLLM
    result = await vllm.analyze_unified(
        visitor_image=visitor_img,
        baseline_image=None,
        dialogue_history=[{"role": "user", "content": visitor_input}],
        is_first_round=True
    )

    # 验证 AI 回复
    assert "快递" in result["content"]
    assert len(result["content"]) < 100  # 简洁性

    # 验证工具调用
    assert len(result["tool_calls"]) > 0
    assert result["tool_calls"][0]["name"] == "enable_package_guard"
```

---

### 3. A/B 测试

**测试目标**：对比不同提示词的效果

**测试步骤**：

1. 准备两个版本的提示词（A 版本和 B 版本）
2. 使用相同的测试用例
3. 对比 AI 回复质量
4. 选择更好的版本

**测试指标**：

- 回复准确性
- 回复简洁性
- 工具调用正确性
- Token 消耗
- 响应时间

---

### 4. 人工评估

**测试目标**：评估提示词的实际效果

**评估维度**：

1. **准确性**：AI 是否正确理解访客意图
2. **简洁性**：AI 回复是否简洁明了
3. **礼貌性**：AI 语气是否礼貌友好
4. **安全性**：AI 是否正确识别威胁
5. **一致性**：AI 行为是否一致

**评估方法**：

- 收集真实对话记录
- 人工评分（1-5 分）
- 计算平均分
- 识别问题并优化

---

## 常见问题

### Q1：修改提示词后需要重启服务吗？

**是的**。提示词在服务启动时加载，修改后需要重启服务生效。

```bash
cd main/xiaozhi-server
python app.py
```

---

### Q2：如何测试提示词效果？

**方式 1：单元测试**

```bash
cd main/xiaozhi-server
python test_prompt_composition.py
```

**方式 2：集成测试**

```bash
cd main/xiaozhi-server
python test_unified_dialogue.py
```

**方式 3：手动测试**

- 启动服务
- 模拟访客对话
- 观察 AI 回复

---

### Q3：提示词过长会影响性能吗？

**会**。提示词越长，Token 消耗越多，响应时间越长。

**优化建议**：

- 删除冗余内容
- 使用简洁表达
- 合并相似说明

---

### Q4：如何恢复默认提示词？

**方式 1：从备份恢复**

```bash
cp config/doorlock_prompts.yaml.bak config/doorlock_prompts.yaml
```

**方式 2：从文档复制**

- 打开配置指南文档
- 复制默认配置
- 粘贴到配置文件

---

## 最佳实践

### 1. 版本管理

```bash
# 修改前备份
cp config/doorlock_prompts.yaml config/doorlock_prompts.yaml.bak

# 修改后测试
python test_prompt_composition.py

# 测试通过后提交
git add config/doorlock_prompts.yaml
git commit -m "优化提示词：调整对话风格"
```

---

### 2. 渐进式优化

```
1. 识别问题
   ↓
2. 小范围修改
   ↓
3. 测试验证
   ↓
4. 收集反馈
   ↓
5. 继续优化
```

---

### 3. 文档记录

```yaml
# 在提示词中添加注释
core_role_and_style: |
  # 版本：v1.1
  # 修改日期：2024-02-16
  # 修改内容：调整语气为更友好
  # 修改原因：用户反馈语气过于严肃

  【系统角色】
  你是一个智能门锁的AI管家...
```

---

## 相关文档

- [配置指南](./doorlock-configuration-guide.md)
- [VLLM 提供者 API 参考](./doorlock-vllm-api-reference.md)
- [意图处理器 API 参考](./doorlock-intent-handler-api-reference.md)
- [统一模式用户手册](./unified-mode-user-guide.md)
- [故障排查指南](./doorlock-troubleshooting-guide.md)

---

## 更新日志

| 版本  | 日期       | 说明                       |
| ----- | ---------- | -------------------------- |
| 1.0.0 | 2024-02-16 | 初始版本，提示词自定义指南 |
