# 门锁 VLLM Token 多层次监控实现文档

## 📋 修改概述

本次修改实现了门锁 VLLM 的多层次 Token 监控机制，通过 `doorlock_config.yaml` 配置 Token 限制，不修改系统配置文件 `config.yaml`。

## 🎯 修改目标

1. ✅ 修复原有的错误警告机制（总Token / 输出限制）
2. ✅ 实现多层次 Token 监控（输出、输入、总Token）
3. ✅ 通过 `doorlock_config.yaml` 配置所有 Token 限制
4. ✅ 不修改系统配置文件 `config.yaml`

---

## 📝 修改内容

### 1. `config/doorlock_config.yaml` 配置文件

#### 新增配置段

```yaml
# 性能配置
performance:
  # Token使用量警告阈值（0.0-1.0）
  # 当输出Token使用率超过此阈值时触发警告
  max_token_usage_ratio: 0.8

  # 会话清理延迟（秒）
  session_cleanup_delay: 0

  # VLLM模型Token限制（用于监控和警告）
  # 注意：这些限制基于通义千问视觉模型（qwen3-vl-flash/plus）
  vllm_limits:
    # 模型上下文窗口大小（输入+输出的总限制）
    model_context_limit: 262144 # 256K tokens

    # 最大输入Token数（提示词+对话历史+图片）
    max_input_tokens: 260096 # 约254K tokens

    # 最大输出Token数（AI生成的回复）
    max_output_tokens: 32768 # 32K tokens

    # 单张图片最大Token数
    max_image_tokens: 16384 # 16K tokens

    # 输入Token警告阈值（0.0-1.0）
    # 当输入Token超过 max_input_tokens * 此阈值时警告
    input_warning_ratio: 0.8 # 80%

    # 总Token警告阈值（0.0-1.0）
    # 当总Token超过 model_context_limit * 此阈值时警告
    total_warning_ratio: 0.8 # 80%
```

#### 配置说明

| 配置项                  | 默认值 | 说明                       |
| ----------------------- | ------ | -------------------------- |
| `max_token_usage_ratio` | 0.8    | 输出Token警告阈值（80%）   |
| `model_context_limit`   | 262144 | 模型上下文窗口（256K）     |
| `max_input_tokens`      | 260096 | 最大输入Token数            |
| `max_output_tokens`     | 32768  | 最大输出Token数（32K）     |
| `max_image_tokens`      | 16384  | 单张图片最大Token数（16K） |
| `input_warning_ratio`   | 0.8    | 输入Token警告阈值（80%）   |
| `total_warning_ratio`   | 0.8    | 总Token警告阈值（80%）     |

---

### 2. `core/providers/vllm/doorlock_vllm.py` 代码修改

#### 修改 1：`__init__` 方法 - 加载 Token 限制配置

```python
def __init__(self, config: dict, logger_instance=None):
    # ... 前面的代码保持不变 ...

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

    # ... 后面的代码保持不变 ...
```

**变更说明**：

- 从 `doorlock_config.yaml` 加载所有 Token 限制配置
- 提供默认值，确保配置缺失时也能正常运行
- 新增 6 个配置属性用于多层次监控

#### 修改 2：新增 `_check_token_usage` 方法 - 多层次监控

```python
def _check_token_usage(self, token_usage: dict, response_time: float, tool_calls_count: int):
    """多层次检查Token使用情况，提供详细的监控和警告

    Args:
        token_usage: Token使用统计字典
        response_time: 响应时间（秒）
        tool_calls_count: 工具调用次数
    """
    prompt_tokens = token_usage["prompt_tokens"]
    completion_tokens = token_usage["completion_tokens"]
    total_tokens = token_usage["total_tokens"]

    # 计算各项使用率
    output_usage_ratio = completion_tokens / self.max_tokens
    input_usage_ratio = prompt_tokens / self.max_input_tokens
    total_usage_ratio = total_tokens / self.model_context_limit

    # 1. 检查输出Token使用率（主要警告 - 影响回复完整性）
    if output_usage_ratio > self.max_token_usage_ratio:
        self.logger.bind(tag=TAG).warning(
            f"⚠️ 输出Token接近限制: {completion_tokens}/{self.max_tokens} "
            f"({output_usage_ratio:.1%})，AI回复可能被截断，建议增加 max_tokens"
        )

    # 2. 检查输入Token使用率（次要警告 - 影响上下文容量）
    if input_usage_ratio > self.input_warning_ratio:
        self.logger.bind(tag=TAG).warning(
            f"⚠️ 输入Token较高: {prompt_tokens}/{self.max_input_tokens} "
            f"({input_usage_ratio:.1%})，建议优化提示词、减少对话历史或降低图片分辨率"
        )

    # 3. 检查总Token使用率（严重警告 - 接近模型上限）
    if total_usage_ratio > self.total_warning_ratio:
        self.logger.bind(tag=TAG).warning(
            f"⚠️ 总Token接近上下文窗口: {total_tokens}/{self.model_context_limit} "
            f"({total_usage_ratio:.1%})，接近模型上限，可能影响性能"
        )

    # 4. 记录详细统计（信息级别 - 用于监控和分析）
    self.logger.bind(tag=TAG).info(
        f"VLLM调用统计 | "
        f"输入: {prompt_tokens} ({input_usage_ratio:.1%}) | "
        f"输出: {completion_tokens} ({output_usage_ratio:.1%}) | "
        f"总计: {total_tokens} ({total_usage_ratio:.1%}) | "
        f"响应时间: {response_time:.2f}s | "
        f"工具调用: {tool_calls_count}"
    )
```

**监控层次**：

1. **输出Token监控**（主要）：防止回复被截断
2. **输入Token监控**（次要）：提示优化空间
3. **总Token监控**（严重）：接近模型上限
4. **详细统计记录**（信息）：用于分析和优化

#### 修改 3：`analyze_with_tools` 方法 - 调用监控

```python
# 替换原有的警告代码
# Token统计
token_usage = {
    "prompt_tokens": response.usage.prompt_tokens,
    "completion_tokens": response.usage.completion_tokens,
    "total_tokens": response.usage.total_tokens
}

# 多层次Token使用量检查和警告
self._check_token_usage(token_usage, response_time, len(tool_calls))
```

**变更说明**：

- 移除原有的错误警告逻辑
- 调用新的多层次监控方法
- 传入工具调用次数用于统计

---

## 🔍 监控机制对比

### 修改前（错误的警告机制）

```python
# ❌ 错误：比较总Token和输出限制
usage_ratio = token_usage["total_tokens"] / self.max_tokens
#              1300 (实际总消耗)        /  500 (最大输出限制)
#              = 2.6 (260%)

if usage_ratio > 0.8:
    logger.warning("Token使用量已达 260%，接近上限")  # 误报
```

**问题**：

- 比较维度不一致（总Token vs 输出限制）
- 几乎每次调用都会触发警告
- 比例可能远超 100%，失去意义

### 修改后（正确的多层次监控）

```python
# ✅ 正确：分别监控输出、输入、总Token

# 1. 输出Token监控
output_ratio = completion_tokens / max_tokens
#              300                / 3000 = 0.1 (10%)
if output_ratio > 0.8:
    logger.warning("输出Token接近限制")  # 仅在真正接近时警告

# 2. 输入Token监控
input_ratio = prompt_tokens / max_input_tokens
#             6000           / 260096 = 0.023 (2.3%)
if input_ratio > 0.8:
    logger.warning("输入Token较高")  # 提示优化空间

# 3. 总Token监控
total_ratio = total_tokens / model_context_limit
#             6300         / 262144 = 0.024 (2.4%)
if total_ratio > 0.8:
    logger.warning("总Token接近上下文窗口")  # 接近模型上限
```

**优点**：

- 比较维度一致
- 仅在真正需要时警告
- 提供详细的优化建议

---

## 📊 实际场景分析

### 场景 1：意图识别（正常使用）

```
输入Token：2,550
输出Token：150
总Token：2,700

监控结果：
  输出使用率：150 / 3000 = 5%
  输入使用率：2,550 / 260,096 = 0.98%
  总使用率：2,700 / 262,144 = 1.03%

警告触发：
  ❌ 输出Token警告（5% < 80%）
  ❌ 输入Token警告（0.98% < 80%）
  ❌ 总Token警告（1.03% < 80%）

日志输出：
  [INFO] VLLM调用统计 | 输入: 2550 (1.0%) | 输出: 150 (5.0%) |
         总计: 2700 (1.0%) | 响应时间: 2.50s | 工具调用: 1
```

### 场景 2：看护监控（双图片）

```
输入Token：11,900
输出Token：280
总Token：12,180

监控结果：
  输出使用率：280 / 3000 = 9.3%
  输入使用率：11,900 / 260,096 = 4.6%
  总使用率：12,180 / 262,144 = 4.6%

警告触发：
  ❌ 输出Token警告（9.3% < 80%）
  ❌ 输入Token警告（4.6% < 80%）
  ❌ 总Token警告（4.6% < 80%）

日志输出：
  [INFO] VLLM调用统计 | 输入: 11900 (4.6%) | 输出: 280 (9.3%) |
         总计: 12180 (4.6%) | 响应时间: 3.20s | 工具调用: 1
```

### 场景 3：输出接近限制

```
输入Token：5,000
输出Token：2,600
总Token：7,600

监控结果：
  输出使用率：2,600 / 3000 = 86.7%
  输入使用率：5,000 / 260,096 = 1.9%
  总使用率：7,600 / 262,144 = 2.9%

警告触发：
  ✅ 输出Token警告（86.7% > 80%）
  ❌ 输入Token警告（1.9% < 80%）
  ❌ 总Token警告（2.9% < 80%）

日志输出：
  [WARNING] ⚠️ 输出Token接近限制: 2600/3000 (86.7%)，
            AI回复可能被截断，建议增加 max_tokens
  [INFO] VLLM调用统计 | 输入: 5000 (1.9%) | 输出: 2600 (86.7%) |
         总计: 7600 (2.9%) | 响应时间: 4.50s | 工具调用: 2
```

### 场景 4：输入Token过高

```
输入Token：220,000
输出Token：500
总Token：220,500

监控结果：
  输出使用率：500 / 3000 = 16.7%
  输入使用率：220,000 / 260,096 = 84.6%
  总使用率：220,500 / 262,144 = 84.1%

警告触发：
  ❌ 输出Token警告（16.7% < 80%）
  ✅ 输入Token警告（84.6% > 80%）
  ✅ 总Token警告（84.1% > 80%）

日志输出：
  [WARNING] ⚠️ 输入Token较高: 220000/260096 (84.6%)，
            建议优化提示词、减少对话历史或降低图片分辨率
  [WARNING] ⚠️ 总Token接近上下文窗口: 220500/262144 (84.1%)，
            接近模型上限，可能影响性能
  [INFO] VLLM调用统计 | 输入: 220000 (84.6%) | 输出: 500 (16.7%) |
         总计: 220500 (84.1%) | 响应时间: 5.80s | 工具调用: 0
```

---

## 🎯 配置调优建议

### 推荐配置（生产环境）

```yaml
# config/doorlock_config.yaml
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

### 配置调整场景

#### 场景 1：频繁触发输出警告

**现象**：

```
[WARNING] ⚠️ 输出Token接近限制: 2500/3000 (83.3%)
```

**解决方案**：

```yaml
# 方案1：增加系统配置的 max_tokens（推荐）
# config.yaml
VLLM:
  QwenVLVLLM:
    max_tokens: 5000 # 从 3000 增加到 5000

# 方案2：提高警告阈值（不推荐）
# doorlock_config.yaml
performance:
  max_token_usage_ratio: 0.9 # 从 0.8 提高到 0.9
```

#### 场景 2：频繁触发输入警告

**现象**：

```
[WARNING] ⚠️ 输入Token较高: 215000/260096 (82.7%)
```

**解决方案**：

```yaml
# 优化措施（按优先级）：
# 1. 优化提示词（减少冗余描述）
# 2. 限制对话历史轮次（从 20 轮减少到 10 轮）
# 3. 降低图片分辨率（从 1920×1080 降到 1280×720）
# 4. 提高警告阈值
performance:
  vllm_limits:
    input_warning_ratio: 0.9 # 从 0.8 提高到 0.9
```

#### 场景 3：频繁触发总Token警告

**现象**：

```
[WARNING] ⚠️ 总Token接近上下文窗口: 215000/262144 (82.0%)
```

**解决方案**：

```yaml
# 这是严重警告，需要优化输入
# 1. 减少对话历史
# 2. 优化提示词
# 3. 降低图片分辨率
# 4. 考虑使用更大上下文窗口的模型（如果可用）
```

---

## 📈 日志输出示例

### 正常使用（无警告）

```
[INFO] VLLM调用统计 | 输入: 2550 (1.0%) | 输出: 150 (5.0%) |
       总计: 2700 (1.0%) | 响应时间: 2.50s | 工具调用: 1
```

### 输出接近限制（警告）

```
[WARNING] ⚠️ 输出Token接近限制: 2600/3000 (86.7%)，
          AI回复可能被截断，建议增加 max_tokens
[INFO] VLLM调用统计 | 输入: 5000 (1.9%) | 输出: 2600 (86.7%) |
       总计: 7600 (2.9%) | 响应时间: 4.50s | 工具调用: 2
```

### 输入过高（警告）

```
[WARNING] ⚠️ 输入Token较高: 220000/260096 (84.6%)，
          建议优化提示词、减少对话历史或降低图片分辨率
[WARNING] ⚠️ 总Token接近上下文窗口: 220500/262144 (84.1%)，
          接近模型上限，可能影响性能
[INFO] VLLM调用统计 | 输入: 220000 (84.6%) | 输出: 500 (16.7%) |
       总计: 220500 (84.1%) | 响应时间: 5.80s | 工具调用: 0
```

---

## ✅ 验证步骤

### 1. 检查配置加载

```bash
# 启动服务
python app.py

# 查看初始化日志
tail -f tmp/server.log | grep "门锁VLLM提供者初始化完成"

# 预期输出：
# [INFO] 门锁VLLM提供者初始化完成: 复用系统配置 QwenVLVLLM,
#        model=qwen3-vl-flash-2026-01-22, max_tokens=3000,
#        context_limit=262144, prompts_loaded=3
```

### 2. 测试意图识别

```bash
# 调用意图识别API
curl -X POST http://localhost:8003/api/doorlock/test/intent \
  -H "Content-Type: application/json" \
  -d '{"device_id": "test001", "image": "base64_data"}'

# 查看日志
tail -f tmp/server.log | grep "VLLM调用统计"

# 预期输出：
# [INFO] VLLM调用统计 | 输入: 2550 (1.0%) | 输出: 150 (5.0%) |
#        总计: 2700 (1.0%) | 响应时间: 2.50s | 工具调用: 1
```

### 3. 测试警告触发

```python
# 创建测试脚本 test_token_warning.py
import asyncio
from core.providers.vllm.doorlock_vllm import DoorlockVLLMProvider
from config.settings import load_config

async def test_warning():
    config = load_config()
    vllm = DoorlockVLLMProvider(config)

    # 模拟高Token使用场景
    # ... 测试代码 ...

asyncio.run(test_warning())
```

---

## 📝 总结

### 修改内容

1. ✅ **配置文件**：在 `doorlock_config.yaml` 中添加 `vllm_limits` 配置段
2. ✅ **代码修改**：修改 `doorlock_vllm.py` 实现多层次监控
3. ✅ **不修改系统配置**：保持 `config.yaml` 不变

### 监控层次

1. **输出Token监控**：防止回复被截断（主要警告）
2. **输入Token监控**：提示优化空间（次要警告）
3. **总Token监控**：接近模型上限（严重警告）
4. **详细统计**：用于分析和优化（信息记录）

### 优势

- ✅ 准确的警告机制（不再误报）
- ✅ 多层次监控（全面了解Token使用情况）
- ✅ 详细的优化建议（帮助定位问题）
- ✅ 灵活的配置（通过 doorlock_config.yaml 调整）
- ✅ 不影响系统配置（独立管理）

### 预期效果

- 正常使用不会触发警告
- 仅在真正需要时提供警告
- 提供详细的Token使用统计
- 帮助优化提示词和配置
