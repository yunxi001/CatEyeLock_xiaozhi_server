# 门锁 VLLM Token 监控机制验证报告

## ✅ 实现状态

所有修改已完成并验证通过。

---

## 📋 修改清单

### 1. 配置文件修改

**文件**：`main/xiaozhi-server/config/doorlock_config.yaml`

**状态**：✅ 已完成

**内容**：

- 新增 `performance.vllm_limits` 配置段
- 包含 7 个 Token 限制参数
- 基于通义千问视觉模型（qwen3-vl-flash/plus）

```yaml
performance:
  max_token_usage_ratio: 0.8

  vllm_limits:
    model_context_limit: 262144 # 256K tokens
    max_input_tokens: 260096 # 约254K tokens
    max_output_tokens: 32768 # 32K tokens
    max_image_tokens: 16384 # 16K tokens
    input_warning_ratio: 0.8 # 80%
    total_warning_ratio: 0.8 # 80%
```

---

### 2. 代码修改

**文件**：`main/xiaozhi-server/core/providers/vllm/doorlock_vllm.py`

**状态**：✅ 已完成

**修改内容**：

#### 修改 1：`__init__` 方法加载配置

```python
# 从门锁独立配置加载性能参数和Token限制
doorlock_config = self._load_doorlock_config()
performance_config = doorlock_config.get("performance", {})

# Token使用量警告阈值（输出Token）
self.max_token_usage_ratio = float(
    performance_config.get("max_token_usage_ratio", 0.8)
)

# VLLM模型Token限制（用于多层次监控）
vllm_limits = performance_config.get("vllm_limits", {})
self.model_context_limit = int(vllm_limits.get("model_context_limit", 262144))
self.max_input_tokens = int(vllm_limits.get("max_input_tokens", 260096))
self.max_output_tokens = int(vllm_limits.get("max_output_tokens", 32768))
self.max_image_tokens = int(vllm_limits.get("max_image_tokens", 16384))
self.input_warning_ratio = float(vllm_limits.get("input_warning_ratio", 0.8))
self.total_warning_ratio = float(vllm_limits.get("total_warning_ratio", 0.8))
```

#### 修改 2：新增 `_check_token_usage` 方法

```python
def _check_token_usage(self, token_usage: dict, response_time: float, tool_calls_count: int):
    """多层次检查Token使用情况，提供详细的监控和警告"""

    # 计算各项使用率
    output_usage_ratio = completion_tokens / self.max_tokens
    input_usage_ratio = prompt_tokens / self.max_input_tokens
    total_usage_ratio = total_tokens / self.model_context_limit

    # 1. 输出Token监控（主要警告）
    # 2. 输入Token监控（次要警告）
    # 3. 总Token监控（严重警告）
    # 4. 详细统计记录（信息级别）
```

#### 修改 3：`analyze_with_tools` 方法调用监控

```python
# 多层次Token使用量检查和警告
self._check_token_usage(token_usage, response_time, len(tool_calls))
```

---

## 🔍 监控机制

### 四层监控体系

| 层次 | 监控对象  | 阈值 | 警告级别 | 触发条件                                   |
| ---- | --------- | ---- | -------- | ------------------------------------------ |
| 1    | 输出Token | 80%  | WARNING  | `completion_tokens / max_tokens > 0.8`     |
| 2    | 输入Token | 80%  | WARNING  | `prompt_tokens / max_input_tokens > 0.8`   |
| 3    | 总Token   | 80%  | WARNING  | `total_tokens / model_context_limit > 0.8` |
| 4    | 详细统计  | -    | INFO     | 每次调用都记录                             |

### 警告信息

#### 输出Token警告

```
[WARNING] ⚠️ 输出Token接近限制: 2600/3000 (86.7%)，
          AI回复可能被截断，建议增加 max_tokens
```

#### 输入Token警告

```
[WARNING] ⚠️ 输入Token较高: 220000/260096 (84.6%)，
          建议优化提示词、减少对话历史或降低图片分辨率
```

#### 总Token警告

```
[WARNING] ⚠️ 总Token接近上下文窗口: 220500/262144 (84.1%)，
          接近模型上限，可能影响性能
```

#### 详细统计

```
[INFO] VLLM调用统计 | 输入: 2550 (1.0%) | 输出: 150 (5.0%) |
       总计: 2700 (1.0%) | 响应时间: 2.50s | 工具调用: 1
```

---

## 📊 典型场景分析

### 场景 1：意图识别（正常）

```
输入：2,550 tokens (1.0%)
输出：150 tokens (5.0%)
总计：2,700 tokens (1.0%)

警告：无
```

### 场景 2：看护监控（双图片，正常）

```
输入：11,900 tokens (4.6%)
输出：280 tokens (9.3%)
总计：12,180 tokens (4.6%)

警告：无
```

### 场景 3：输出接近限制

```
输入：5,000 tokens (1.9%)
输出：2,600 tokens (86.7%) ⚠️
总计：7,600 tokens (2.9%)

警告：输出Token接近限制
```

### 场景 4：输入过高

```
输入：220,000 tokens (84.6%) ⚠️
输出：500 tokens (16.7%)
总计：220,500 tokens (84.1%) ⚠️

警告：输入Token较高 + 总Token接近上下文窗口
```

---

## 🎯 配置调优指南

### 当前配置（推荐）

```yaml
# doorlock_config.yaml
performance:
  max_token_usage_ratio: 0.8

  vllm_limits:
    model_context_limit: 262144
    max_input_tokens: 260096
    max_output_tokens: 32768
    max_image_tokens: 16384
    input_warning_ratio: 0.8
    total_warning_ratio: 0.8
```

### 调整建议

#### 频繁触发输出警告

```yaml
# 方案1：增加系统配置的 max_tokens（推荐）
# config.yaml
VLLM:
  QwenVLVLLM:
    max_tokens: 5000 # 从 3000 增加

# 方案2：提高警告阈值（不推荐）
performance:
  max_token_usage_ratio: 0.9
```

#### 频繁触发输入警告

```yaml
# 优化措施（按优先级）：
# 1. 优化提示词（减少冗余）
# 2. 限制对话历史轮次
# 3. 降低图片分辨率
# 4. 提高警告阈值
performance:
  vllm_limits:
    input_warning_ratio: 0.9
```

---

## ✅ 验证结果

### 配置验证

- ✅ `doorlock_config.yaml` 包含 `vllm_limits` 配置
- ✅ 所有 7 个参数已配置
- ✅ 默认值合理

### 代码验证

- ✅ `__init__` 方法加载配置
- ✅ `_check_token_usage` 方法已实现
- ✅ `analyze_with_tools` 方法调用监控
- ✅ 日志输出格式正确

### 功能验证

- ✅ 多层次监控机制
- ✅ 准确的警告触发
- ✅ 详细的统计记录
- ✅ 优化建议清晰

---

## 📝 总结

### 实现完成度：100%

所有计划的修改都已完成并验证通过：

1. ✅ 配置文件新增 `vllm_limits` 配置段
2. ✅ 代码实现多层次 Token 监控
3. ✅ 不修改系统配置文件 `config.yaml`
4. ✅ 修复原有的错误警告机制

### 核心优势

- **准确性**：不再误报，仅在真正需要时警告
- **全面性**：监控输出、输入、总Token三个维度
- **实用性**：提供详细的优化建议
- **灵活性**：通过配置文件轻松调整

### 预期效果

- 正常使用不会触发警告
- 接近限制时及时提醒
- 提供详细的Token使用统计
- 帮助优化提示词和配置

---

**验证时间**：2026-02-13  
**验证状态**：✅ 通过  
**文档版本**：v1.0
