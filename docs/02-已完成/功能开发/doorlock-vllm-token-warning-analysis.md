# 门锁 VLLM Token 警告机制详细分析

## 🔍 核心问题

**Token 警告阈值 0.8 是如何工作的？模型的最大 Token 是从哪里来的？**

## 📊 Token 警告机制解析

### 1️⃣ 关键代码分析

```python
# doorlock_vllm.py 第 258-264 行
# Token使用量警告
usage_ratio = token_usage["total_tokens"] / self.max_tokens
if usage_ratio > self.max_token_usage_ratio:
    self.logger.bind(tag=TAG).warning(
        f"Token使用量已达 {token_usage['total_tokens']}/{self.max_tokens} "
        f"({usage_ratio:.1%})，接近上限"
    )
```

### 2️⃣ 两个关键参数

| 参数                         | 含义                            | 来源                             | 默认值 |
| ---------------------------- | ------------------------------- | -------------------------------- | ------ |
| `self.max_tokens`            | **单次请求的最大输出 Token 数** | 系统配置（config.yaml）          | 500    |
| `self.max_token_usage_ratio` | **警告阈值比例**                | 门锁配置（doorlock_config.yaml） | 0.8    |

---

## ⚠️ 重要发现：这是一个**误导性的警告机制**

### 问题分析

```python
# 当前实现（有问题）
usage_ratio = token_usage["total_tokens"] / self.max_tokens
#              ↑ 实际使用的总Token数      ↑ 单次请求的最大输出Token数
```

**问题所在**：

- `token_usage["total_tokens"]` = **输入Token + 输出Token**（实际总消耗）
- `self.max_tokens` = **单次请求的最大输出Token数**（仅限制输出）

**这两个数值不是同一个维度！**

---

## 📖 Token 概念详解

### OpenAI API 中的 Token 参数

#### 1. `max_tokens`（请求参数）

```python
response = self.client.chat.completions.create(
    model=self.model_name,
    messages=messages,
    max_tokens=500,  # ← 这是单次请求的最大输出Token数
    # ...
)
```

**含义**：

- 限制 **AI 生成的回复** 的最大 Token 数
- 仅控制 **输出（completion）** 部分
- **不包括输入（prompt）部分**

**示例**：

```
输入提示词：1000 tokens
max_tokens：500
实际输出：300 tokens
总消耗：1000 + 300 = 1300 tokens
```

#### 2. `token_usage`（响应数据）

```python
token_usage = {
    "prompt_tokens": 1200,      # 输入Token数（提示词 + 对话历史 + 图片）
    "completion_tokens": 50,    # 输出Token数（AI生成的回复）
    "total_tokens": 1250        # 总Token数 = prompt_tokens + completion_tokens
}
```

**含义**：

- `prompt_tokens`：输入部分的 Token 数
- `completion_tokens`：输出部分的 Token 数
- `total_tokens`：实际消耗的总 Token 数

---

## 🚨 当前警告机制的问题

### 错误的比较

```python
# 当前代码
usage_ratio = token_usage["total_tokens"] / self.max_tokens
#              1250 (实际总消耗)        /  500 (最大输出限制)
#              = 2.5 (250%)
```

**问题**：

1. **分子**：实际总消耗（输入 + 输出）
2. **分母**：最大输出限制（仅输出）
3. **结果**：比例可能 > 100%，失去意义

### 实际场景示例

#### 场景 1：意图识别（单图片）

```
输入Token：
  - 系统提示词：~800 tokens
  - 对话历史：~200 tokens
  - 图片：~200 tokens
  - 问题文本：~50 tokens
  总计：~1250 tokens

输出Token：
  - AI回复：~50 tokens

总消耗：1250 + 50 = 1300 tokens
max_tokens：500

usage_ratio = 1300 / 500 = 2.6 (260%)
```

**警告触发**：✅ 会触发（2.6 > 0.8）
**是否合理**：❌ 不合理（这是正常使用）

#### 场景 2：看护监控（双图片）

```
输入Token：
  - 系统提示词：~1200 tokens
  - 对话历史：~100 tokens
  - 基准图片：~200 tokens
  - 当前图片：~200 tokens
  - 问题文本：~100 tokens
  总计：~1800 tokens

输出Token：
  - AI回复：~80 tokens

总消耗：1800 + 80 = 1880 tokens
max_tokens：500

usage_ratio = 1880 / 500 = 3.76 (376%)
```

**警告触发**：✅ 会触发（3.76 > 0.8）
**是否合理**：❌ 不合理（这是正常使用）

---

## 🎯 模型的真实 Token 限制

### 不同模型的上下文窗口

| 模型                 | 上下文窗口  | 最大输出 Token | 说明                   |
| -------------------- | ----------- | -------------- | ---------------------- |
| **glm-4v-flash**     | 128K tokens | 4K tokens      | 智谱 AI 视觉模型       |
| **gpt-4o**           | 128K tokens | 16K tokens     | OpenAI 视觉模型        |
| **qwen-vl-plus**     | 32K tokens  | 8K tokens      | 阿里通义千问视觉模型   |
| **gemini-2.0-flash** | 1M tokens   | 8K tokens      | Google Gemini 视觉模型 |

**关键点**：

- **上下文窗口**：输入 + 输出的总限制
- **最大输出 Token**：单次生成的输出限制
- **配置中的 `max_tokens`**：用户自定义的输出限制（≤ 模型最大输出）

### 当前配置

```yaml
# config.yaml
VLLM:
  ChatGLMVLLM:
    model_name: glm-4v-flash
    max_tokens: 500 # ← 用户设置的最大输出Token数
```

**说明**：

- `max_tokens: 500` 是用户预设的限制
- **不是**从模型加载的
- **不是**模型的真实上限（glm-4v-flash 支持 4K 输出）
- 目的：控制成本和响应速度

---

## ✅ 正确的警告机制应该是什么？

### 方案 1：警告输出 Token 接近限制

```python
# 正确的实现
output_usage_ratio = token_usage["completion_tokens"] / self.max_tokens
if output_usage_ratio > self.max_token_usage_ratio:
    self.logger.bind(tag=TAG).warning(
        f"输出Token使用量已达 {token_usage['completion_tokens']}/{self.max_tokens} "
        f"({output_usage_ratio:.1%})，接近输出上限"
    )
```

**优点**：

- 比较的是同一维度（输出 vs 输出限制）
- 有实际意义（输出接近限制可能被截断）

**示例**：

```
completion_tokens: 450
max_tokens: 500
usage_ratio = 450 / 500 = 0.9 (90%)
警告：✅ 合理（输出接近限制，可能被截断）
```

### 方案 2：警告总 Token 接近模型上限

```python
# 需要知道模型的上下文窗口大小
MODEL_CONTEXT_LIMITS = {
    "glm-4v-flash": 128000,
    "gpt-4o": 128000,
    "qwen-vl-plus": 32000,
}

model_limit = MODEL_CONTEXT_LIMITS.get(self.model_name, 128000)
total_usage_ratio = token_usage["total_tokens"] / model_limit

if total_usage_ratio > self.max_token_usage_ratio:
    self.logger.bind(tag=TAG).warning(
        f"总Token使用量已达 {token_usage['total_tokens']}/{model_limit} "
        f"({total_usage_ratio:.1%})，接近模型上限"
    )
```

**优点**：

- 比较的是同一维度（总消耗 vs 模型上限）
- 真正反映是否接近模型限制

**缺点**：

- 需要维护模型上限映射表
- 不同模型上限不同

### 方案 3：同时监控两个指标

```python
# 监控输出Token
output_ratio = token_usage["completion_tokens"] / self.max_tokens
if output_ratio > 0.8:
    self.logger.warning(
        f"输出Token接近限制: {token_usage['completion_tokens']}/{self.max_tokens} "
        f"({output_ratio:.1%})"
    )

# 监控总Token（如果知道模型上限）
if self.model_name in MODEL_CONTEXT_LIMITS:
    model_limit = MODEL_CONTEXT_LIMITS[self.model_name]
    total_ratio = token_usage["total_tokens"] / model_limit
    if total_ratio > 0.8:
        self.logger.warning(
            f"总Token接近模型上限: {token_usage['total_tokens']}/{model_limit} "
            f"({total_ratio:.1%})"
        )
```

---

## 🔧 建议的修复方案

### 推荐：方案 1（监控输出 Token）

```python
# 修改 doorlock_vllm.py 第 258-264 行
# Token使用量警告（修正版）
output_usage_ratio = token_usage["completion_tokens"] / self.max_tokens
if output_usage_ratio > self.max_token_usage_ratio:
    self.logger.bind(tag=TAG).warning(
        f"输出Token使用量已达 {token_usage['completion_tokens']}/{self.max_tokens} "
        f"({output_usage_ratio:.1%})，接近输出上限，回复可能被截断"
    )

# 可选：同时记录总Token消耗（信息级别）
self.logger.bind(tag=TAG).info(
    f"VLLM调用统计 | 输入Token: {token_usage['prompt_tokens']} | "
    f"输出Token: {token_usage['completion_tokens']} | "
    f"总Token: {token_usage['total_tokens']} | "
    f"输出使用率: {output_usage_ratio:.1%} | "
    f"响应时间: {response_time:.2f}s | "
    f"工具调用: {len(tool_calls)}"
)
```

---

## 📈 实际使用情况分析

### 当前配置下的 Token 消耗

#### 意图识别场景

```
输入Token：~1250
输出Token：~50
总Token：~1300

当前警告机制：
  usage_ratio = 1300 / 500 = 2.6 (260%)
  警告：✅ 触发（不合理）

修正后警告机制：
  output_ratio = 50 / 500 = 0.1 (10%)
  警告：❌ 不触发（合理）
```

#### 看护监控场景

```
输入Token：~1800
输出Token：~80
总Token：~1880

当前警告机制：
  usage_ratio = 1880 / 500 = 3.76 (376%)
  警告：✅ 触发（不合理）

修正后警告机制：
  output_ratio = 80 / 500 = 0.16 (16%)
  警告：❌ 不触发（合理）
```

#### 输出接近限制场景

```
输入Token：~1200
输出Token：~450
总Token：~1650

当前警告机制：
  usage_ratio = 1650 / 500 = 3.3 (330%)
  警告：✅ 触发（不合理）

修正后警告机制：
  output_ratio = 450 / 500 = 0.9 (90%)
  警告：✅ 触发（合理！回复可能被截断）
```

---

## 🎓 Token 计算规则

### 文本 Token 计算

- **中文**：约 1.5-2 字符 = 1 token
- **英文**：约 4 字符 = 1 token
- **代码**：约 3-4 字符 = 1 token

### 图片 Token 计算

不同模型的图片 Token 计算方式不同：

#### glm-4v-flash（智谱 AI）

```
固定消耗：约 200-300 tokens/图片
不受图片分辨率影响
```

#### gpt-4o（OpenAI）

```
低分辨率模式：85 tokens/图片
高分辨率模式：85 + (图片块数 × 170) tokens
图片块数 = ceil(宽度/512) × ceil(高度/512)
```

### 提示词 Token 估算

```
意图识别提示词：~800 tokens
看护模式提示词：~1200 tokens
对话历史（10轮）：~200 tokens
问题文本：~50 tokens
```

---

## 📝 配置建议

### 当前配置

```yaml
# config.yaml
VLLM:
  ChatGLMVLLM:
    max_tokens: 500 # 最大输出Token数

# doorlock_config.yaml
performance:
  max_token_usage_ratio: 0.8 # 警告阈值
```

### 建议配置

```yaml
# config.yaml
VLLM:
  ChatGLMVLLM:
    max_tokens: 1000 # 建议增加到 1000，给 AI 更多表达空间

# doorlock_config.yaml
performance:
  max_token_usage_ratio: 0.8 # 保持 0.8
  # 新增：模型上下文窗口大小（可选）
  model_context_limit: 128000 # glm-4v-flash 的上下文窗口
```

---

## 🔍 总结

### 当前问题

1. ❌ **警告机制有误**：比较的是 `总Token / 最大输出Token`，维度不一致
2. ❌ **频繁误报**：正常使用也会触发警告（260%-376%）
3. ❌ **失去意义**：比例可能远超 100%，无法反映真实情况

### 关键发现

1. ✅ `max_tokens` 是**用户预设**的最大输出 Token 数，不是从模型加载的
2. ✅ 模型真实上限是**上下文窗口**（glm-4v-flash 为 128K）
3. ✅ 当前配置 `max_tokens: 500` 远小于模型上限（4K）

### 修复建议

1. **修改警告逻辑**：监控 `completion_tokens / max_tokens`
2. **增加 max_tokens**：从 500 提升到 1000-2000
3. **优化日志输出**：同时记录输入、输出、总Token

### 实际影响

- **当前**：几乎每次调用都会触发警告（误报）
- **修复后**：仅在输出真正接近限制时警告（准确）

---

## 📚 参考资料

- [OpenAI API - Token 计算](https://platform.openai.com/docs/guides/vision)
- [智谱 AI - glm-4v 文档](https://open.bigmodel.cn/dev/api#glm-4v)
- [Token 计算工具](https://platform.openai.com/tokenizer)
