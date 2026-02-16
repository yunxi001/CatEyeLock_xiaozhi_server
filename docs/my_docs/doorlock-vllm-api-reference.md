# DoorlockVLLMProvider API 参考文档

## 概述

`DoorlockVLLMProvider` 是智能门锁系统的视觉语言模型提供者，负责处理多模态 AI 分析任务。该类位于 `core/providers/vllm/doorlock_vllm.py`，提供统一的对话和看护模式支持。

## 核心特性

- **统一模式分析**：同时处理访客对话和快递看护任务
- **动态提示词组合**：根据看护模式状态自动组合提示词
- **Token 优化管理**：智能控制图片传递和对话历史截断
- **多层次监控**：实时监控 Token 使用量和响应时间
- **格式化输出**：支持纯 JSON 和混合格式解析

## 主要方法

### analyze_unified

统一模式分析方法，同时处理对话和看护任务。

#### 方法签名

```python
async def analyze_unified(
    self,
    visitor_image: str,
    baseline_image: Optional[str],
    dialogue_history: List[Dict[str, str]],
    is_first_round: bool = False
) -> Dict[str, Any]
```

#### 参数说明

| 参数               | 类型                   | 必需 | 说明                                            |
| ------------------ | ---------------------- | ---- | ----------------------------------------------- |
| `visitor_image`    | `str`                  | 是   | 访客照片（Base64 编码）                         |
| `baseline_image`   | `Optional[str]`        | 否   | 基准图片（Base64 编码），仅在看护模式激活时传入 |
| `dialogue_history` | `List[Dict[str, str]]` | 是   | 对话历史列表，每个元素包含 `role` 和 `content`  |
| `is_first_round`   | `bool`                 | 否   | 是否第一轮对话，默认 `False`                    |

#### 返回值

```python
{
    "content": str,              # AI 回复文本
    "tool_calls": List[Dict],    # 工具调用列表
    "token_usage": {
        "prompt_tokens": int,    # 输入 Token 数
        "completion_tokens": int,# 输出 Token 数
        "total_tokens": int      # 总 Token 数
    },
    "response_time": float       # 响应时间（秒）
}
```

#### 核心逻辑

1. **图片列表构建**：
   - 第一轮且有基准图片：传入访客图片 + 基准图片（2 张）
   - 后续轮次：仅传入访客图片（1 张）

2. **Token 限制检查**：
   - 验证图片数量不超过限制（最多 2 张）
   - 超限时抛出 `ValueError` 异常

3. **提示词动态组合**：
   - 根据是否有基准图片决定是否添加看护任务提示词
   - 组合顺序：核心角色 → 对话任务 → 看护任务（可选）→ 工具指南

4. **对话历史截断**：
   - 估算对话历史 Token 消耗
   - 超出限制时保留最新的对话内容

5. **VLLM 调用**：
   - 构建多模态消息（文本 + 图片）
   - 调用 VLLM 进行分析
   - 解析 AI 回复和工具调用

6. **Token 使用量统计**：
   - 记录输入/输出/总计 Token 数
   - 检查是否接近限制并发出警告

#### 使用示例

```python
# 示例 1：第一轮对话（看护模式激活）
result = await vllm_provider.analyze_unified(
    visitor_image="base64_encoded_visitor_image",
    baseline_image="base64_encoded_baseline_image",
    dialogue_history=[],
    is_first_round=True
)

print(f"AI 回复: {result['content']}")
print(f"Token 消耗: {result['token_usage']['total_tokens']}")

# 示例 2：后续轮次对话
result = await vllm_provider.analyze_unified(
    visitor_image="base64_encoded_visitor_image",
    baseline_image="base64_encoded_baseline_image",  # 仍需传入但不会使用
    dialogue_history=[
        {"role": "assistant", "content": "您好，请问有什么可以帮您？"},
        {"role": "user", "content": "我是来送快递的"}
    ],
    is_first_round=False
)

# 示例 3：仅对话模式（看护未激活）
result = await vllm_provider.analyze_unified(
    visitor_image="base64_encoded_visitor_image",
    baseline_image=None,  # 看护未激活
    dialogue_history=[],
    is_first_round=True
)
```

#### Token 消耗参考

| 场景                 | 图片数量 | 预估 Token 消耗 |
| -------------------- | -------- | --------------- |
| 第一轮（看护激活）   | 2 张     | ~14K            |
| 后续轮次（看护激活） | 1 张     | ~7K             |
| 仅对话模式           | 1 张     | ~7K             |

---

### final_package_check

对话结束后的快递状态最终检查方法。

#### 方法签名

```python
async def final_package_check(
    self,
    current_image: str,
    baseline_image: str
) -> Dict[str, Any]
```

#### 参数说明

| 参数             | 类型  | 必需 | 说明                                        |
| ---------------- | ----- | ---- | ------------------------------------------- |
| `current_image`  | `str` | 是   | 当前图片（Base64 编码），对话结束后重新拍照 |
| `baseline_image` | `str` | 是   | 基准图片（Base64 编码）                     |

#### 返回值

```python
{
    "threat_level": str,   # 威胁等级："low" | "medium" | "high"
    "action": str,         # 行为类型："taking" | "searching" | "damaging" | "normal" | "passing"
    "description": str     # 详细描述
}
```

#### 威胁等级说明

| 等级     | 说明   | 触发条件                             |
| -------- | ------ | ------------------------------------ |
| `low`    | 低威胁 | 快递位置未变化、主人取快递、路人经过 |
| `medium` | 中威胁 | 快递被移动但未拿走、访客翻看快递     |
| `high`   | 高威胁 | 快递被非主人拿走、快递被破坏         |

#### 行为类型说明

| 类型        | 说明                   |
| ----------- | ---------------------- |
| `normal`    | 正常状态，快递未被触碰 |
| `passing`   | 路人经过，未触碰快递   |
| `searching` | 翻看或移动快递         |
| `taking`    | 拿走快递               |
| `damaging`  | 破坏快递               |

#### 核心逻辑

1. **图片 Token 限制检查**：验证 2 张图片不超过限制
2. **加载专用提示词**：使用 `final_package_check_prompt`
3. **VLLM 调用**：对比分析基准图片和当前图片
4. **纯 JSON 解析**：提取 JSON 格式结果
5. **异常处理**：解析失败时返回默认低威胁结果

#### 使用示例

```python
# 对话结束后检查快递状态
result = await vllm_provider.final_package_check(
    current_image="base64_encoded_current_image",
    baseline_image="base64_encoded_baseline_image"
)

if result["threat_level"] == "high":
    print(f"⚠️ 高威胁警报: {result['description']}")
    # 发送警报通知
elif result["threat_level"] == "medium":
    print(f"⚠️ 中威胁提醒: {result['description']}")
    # 记录日志
else:
    print(f"✓ 快递安全: {result['description']}")
```

#### 默认返回值（异常情况）

```python
{
    "threat_level": "low",
    "action": "normal",
    "description": "无法解析检查结果，默认判定为低威胁"
}
```

---

### generate_intent_summary

生成访客意图总结方法。

#### 方法签名

```python
async def generate_intent_summary(
    self,
    visitor_image: str,
    dialogue_history: List[Dict[str, str]]
) -> Dict[str, Any]
```

#### 参数说明

| 参数               | 类型                   | 必需 | 说明                    |
| ------------------ | ---------------------- | ---- | ----------------------- |
| `visitor_image`    | `str`                  | 是   | 访客照片（Base64 编码） |
| `dialogue_history` | `List[Dict[str, str]]` | 是   | 完整对话历史            |

#### 返回值

```python
{
    "intent_type": str,           # 意图类型
    "summary": str,               # 简洁总结（一句话）
    "important_notes": List[str], # 重要信息列表
    "ai_analysis": str            # 详细 AI 分析
}
```

#### 意图类型说明

| 类型          | 说明          |
| ------------- | ------------- |
| `delivery`    | 送快递/外卖   |
| `visit`       | 拜访朋友/家人 |
| `sales`       | 推销产品/服务 |
| `maintenance` | 维修/物业工作 |
| `other`       | 其他情况      |

#### 核心逻辑

1. **图片 Token 限制检查**：验证 1 张图片不超过限制
2. **加载专用提示词**：使用 `intent_summary_prompt`
3. **VLLM 调用**：基于对话历史和访客图片生成总结
4. **混合格式解析**：提取 JSON 格式结果
5. **异常处理**：解析失败时返回默认总结

#### 使用示例

```python
# 生成访客意图总结
summary = await vllm_provider.generate_intent_summary(
    visitor_image="base64_encoded_visitor_image",
    dialogue_history=[
        {"role": "assistant", "content": "您好，请问有什么可以帮您？"},
        {"role": "user", "content": "我是来送快递的"},
        {"role": "assistant", "content": "好的，请问快递放在哪里？"},
        {"role": "user", "content": "我放门口了，麻烦签收一下"}
    ]
)

print(f"意图类型: {summary['intent_type']}")
print(f"总结: {summary['summary']}")
print(f"重要信息: {summary['important_notes']}")
print(f"AI 分析: {summary['ai_analysis']}")

# 保存到数据库
await db.save_visit_record(
    intent_type=summary['intent_type'],
    summary=summary['summary'],
    notes=summary['important_notes'],
    analysis=summary['ai_analysis']
)
```

#### 默认返回值（异常情况）

```python
{
    "intent_type": "other",
    "summary": "访客到访",
    "important_notes": [],
    "ai_analysis": "无法生成详细分析"
}
```

---

## 辅助方法

### \_build_unified_prompt

动态组合统一模式提示词。

#### 方法签名

```python
def _build_unified_prompt(self, has_baseline: bool) -> str
```

#### 参数说明

| 参数           | 类型   | 必需 | 说明                               |
| -------------- | ------ | ---- | ---------------------------------- |
| `has_baseline` | `bool` | 是   | 是否有基准图片（看护模式是否激活） |

#### 返回值

组合后的完整提示词字符串。

#### 组合逻辑

```python
# 基础部分（总是包含）
prompt_parts = [
    self.get_prompt("core_role_and_style"),  # 核心角色和风格
    self.get_prompt("dialogue_tasks")        # 对话任务
]

# 如果看护模式激活，添加看护任务
if has_baseline:
    prompt_parts.append(self.get_prompt("guard_tasks"))

# 总是添加工具指南
prompt_parts.append(self.get_prompt("tools_guide"))

return "\n\n".join(prompt_parts)
```

---

### \_check_image_token_limit

检查图片 Token 限制。

#### 方法签名

```python
def _check_image_token_limit(self, image_count: int) -> bool
```

#### 参数说明

| 参数          | 类型  | 必需 | 说明     |
| ------------- | ----- | ---- | -------- |
| `image_count` | `int` | 是   | 图片数量 |

#### 返回值

- `True`：未超限
- `False`：超限

#### 限制规则

- 最多支持 2 张图片
- 每张图片约消耗 7000 Token
- 超限时记录警告日志

---

### \_truncate_dialogue_history

截断对话历史以控制 Token 消耗。

#### 方法签名

```python
def _truncate_dialogue_history(
    self,
    dialogue_history: List[Dict[str, str]],
    max_tokens: int
) -> List[Dict[str, str]]
```

#### 参数说明

| 参数               | 类型                   | 必需 | 说明            |
| ------------------ | ---------------------- | ---- | --------------- |
| `dialogue_history` | `List[Dict[str, str]]` | 是   | 完整对话历史    |
| `max_tokens`       | `int`                  | 是   | 最大 Token 限制 |

#### 返回值

截断后的对话历史列表。

#### 截断策略

- 从最新的对话开始累加 Token
- 超出限制时停止添加
- 保留最近的对话内容
- 记录截断日志

---

### \_check_token_usage

多层次 Token 使用量监控。

#### 方法签名

```python
def _check_token_usage(
    self,
    token_usage: Dict[str, int],
    response_time: float,
    tool_calls_count: int
)
```

#### 参数说明

| 参数               | 类型             | 必需 | 说明             |
| ------------------ | ---------------- | ---- | ---------------- |
| `token_usage`      | `Dict[str, int]` | 是   | Token 使用量统计 |
| `response_time`    | `float`          | 是   | 响应时间（秒）   |
| `tool_calls_count` | `int`            | 是   | 工具调用次数     |

#### 监控指标

1. **输出 Token 警告**：超过 80% 时触发
2. **输入 Token 警告**：超过 80% 时触发
3. **总 Token 警告**：超过 80% 时触发
4. **详细统计日志**：记录所有指标

---

### \_estimate_tokens

估算文本 Token 数量。

#### 方法签名

```python
def _estimate_tokens(self, text: str) -> int
```

#### 参数说明

| 参数   | 类型  | 必需 | 说明     |
| ------ | ----- | ---- | -------- |
| `text` | `str` | 是   | 文本内容 |

#### 返回值

估算的 Token 数量。

#### 估算规则

- 中文：1.5 字符/Token
- 英文：4 字符/Token

---

### \_estimate_image_tokens

估算图片 Token 数量。

#### 方法签名

```python
def _estimate_image_tokens(self, image_count: int) -> int
```

#### 参数说明

| 参数          | 类型  | 必需 | 说明     |
| ------------- | ----- | ---- | -------- |
| `image_count` | `int` | 是   | 图片数量 |

#### 返回值

估算的 Token 数量。

#### 估算规则

- 每张图片约 7000 Token（可配置）

---

## 配置项

### doorlock_config.yaml

```yaml
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

### doorlock_prompts.yaml

```yaml
# 核心角色和风格
core_role_and_style: |
  【系统角色】
  你是一个智能门锁的AI门卫助手...

# 对话任务
dialogue_tasks: |
  【对话任务】
  你的主要任务是与访客进行自然对话...

# 看护任务
guard_tasks: |
  【看护任务】（后台任务，不影响对话）
  你同时负责监控门口快递的安全...

# 工具调用指南
tools_guide: |
  【工具调用说明】
  你可以调用以下4个工具函数...

# 对话结束后的专用提示词
final_package_check_prompt: |
  【任务】
  访客已离开，请对比基准图片和当前图片...

intent_summary_prompt: |
  【任务】
  根据完整的对话历史和访客照片...
```

---

## 错误处理

### 常见异常

| 异常类型               | 触发条件         | 处理方式                   |
| ---------------------- | ---------------- | -------------------------- |
| `ValueError`           | 图片数量超过限制 | 抛出异常，记录错误日志     |
| `json.JSONDecodeError` | JSON 解析失败    | 返回默认值，记录错误日志   |
| `Exception`            | VLLM 调用失败    | 返回默认响应，记录错误日志 |
| `asyncio.TimeoutError` | 调用超时         | 返回默认响应，记录错误日志 |

### 降级策略

1. **VLLM 调用失败**：返回默认响应，对话可以继续
2. **JSON 解析失败**：返回默认结果，不影响后续流程
3. **Token 超限**：截断对话历史，保留最新内容
4. **图片超限**：抛出异常，终止处理

---

## 性能指标

### Token 消耗参考

| 场景                   | Token 消耗 | 说明                |
| ---------------------- | ---------- | ------------------- |
| 第一轮对话（看护激活） | ~14K       | 2 张图片 + 提示词   |
| 后续轮次（看护激活）   | ~7K        | 1 张图片 + 对话历史 |
| 对话结束检查           | ~15K       | 2 张图片对比        |
| 意图总结               | ~8K        | 1 张图片 + 完整对话 |
| 10 轮对话总计          | ~100K      | 优化后的消耗        |

### 响应时间参考

| 操作                    | 目标时间 | 说明           |
| ----------------------- | -------- | -------------- |
| analyze_unified         | <3 秒    | 单次对话分析   |
| final_package_check     | <3 秒    | 快递状态检查   |
| generate_intent_summary | <3 秒    | 意图总结生成   |
| 对话结束后处理          | <10 秒   | 包含检查和总结 |

---

## 最佳实践

### 1. Token 优化

```python
# ✓ 推荐：仅第一轮传入基准图片
result = await vllm.analyze_unified(
    visitor_image=visitor_img,
    baseline_image=baseline_img if is_first_round else None,
    dialogue_history=history,
    is_first_round=is_first_round
)

# ✗ 不推荐：每轮都传入基准图片
result = await vllm.analyze_unified(
    visitor_image=visitor_img,
    baseline_image=baseline_img,  # 浪费 Token
    dialogue_history=history,
    is_first_round=False
)
```

### 2. 对话历史管理

```python
# ✓ 推荐：定期截断对话历史
if len(dialogue_history) > 10:
    dialogue_history = vllm._truncate_dialogue_history(
        dialogue_history,
        max_tokens=50000
    )

# ✗ 不推荐：无限累积对话历史
dialogue_history.append(new_message)  # 可能导致 Token 超限
```

### 3. 异常处理

```python
# ✓ 推荐：捕获异常并返回默认值
try:
    result = await vllm.analyze_unified(...)
except ValueError as e:
    logger.error(f"图片超限: {e}")
    return default_response
except Exception as e:
    logger.error(f"VLLM 调用失败: {e}")
    return default_response

# ✗ 不推荐：不处理异常
result = await vllm.analyze_unified(...)  # 可能导致程序崩溃
```

### 4. 日志记录

```python
# ✓ 推荐：记录关键指标
logger.info(
    f"VLLM 调用完成 - "
    f"Token: {total_tokens}, "
    f"响应时间: {response_time:.2f}s, "
    f"工具调用: {len(tool_calls)}"
)

# ✗ 不推荐：记录敏感数据
logger.info(f"图片数据: {visitor_image}")  # 泄露隐私
```

---

## 相关文档

- [统一模式设计文档](./unified-guard-dialogue-implementation.md)
- [Token 管理实现总结](./token-management-implementation-summary.md)
- [意图处理器 API 参考](./doorlock-intent-handler-api-reference.md)
- [配置指南](./doorlock-configuration-guide.md)

---

## 更新日志

| 版本  | 日期       | 说明                           |
| ----- | ---------- | ------------------------------ |
| 1.0.0 | 2024-02-16 | 初始版本，包含统一模式核心方法 |
