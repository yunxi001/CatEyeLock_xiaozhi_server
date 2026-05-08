# Token管理和优化功能实现总结

## 实现日期

2026-02-16

## 概述

为统一智能看护对话模式实现了完整的Token管理和优化功能，包括Token估算、限制检查、对话历史截断和多层次使用量监控。

## 实现的功能

### 1. \_estimate_tokens方法

**位置**: `core/providers/vllm/doorlock_vllm.py`

**功能**: 估算文本的Token数量

**实现细节**:

- 中文字符: 约1.5字符/Token
- 英文字符: 约4字符/Token
- 自动识别中英文混合文本
- 返回估算的Token数量

**测试结果**: ✓ 通过

- 空字符串: 0 tokens
- 纯英文: 2 tokens
- 纯中文: 2 tokens
- 中英混合: 5 tokens
- 长中文文本: 17 tokens

### 2. \_estimate_image_tokens方法

**位置**: `core/providers/vllm/doorlock_vllm.py`

**功能**: 估算图片的Token数量

**实现细节**:

- 从配置文件读取`tokens_per_image`参数（默认7000）
- 计算公式: `image_count × tokens_per_image`
- 支持通过配置调整不同分辨率的Token消耗

**测试结果**: ✓ 通过

- 0张图片: 0 tokens
- 1张图片: 7000 tokens
- 2张图片: 14000 tokens
- 3张图片: 21000 tokens

### 3. \_check_image_token_limit方法

**位置**: `core/providers/vllm/doorlock_vllm.py`

**功能**: 检查图片数量是否超过Token限制

**实现细节**:

- 调用`_estimate_image_tokens`估算Token数
- 与`max_image_tokens`（默认16384）比较
- 超限时记录错误日志并返回False
- 在限制内返回True

**测试结果**: ✓ 通过

- 1张图片: 通过（7000 < 16384）
- 2张图片: 通过（14000 < 16384）
- 3张图片: 失败（21000 > 16384）

**使用场景**:

- `analyze_unified`: 检查访客图片+基准图片
- `final_package_check`: 检查2张图片
- `generate_intent_summary`: 检查1张图片
- `analyze_intent`: 检查1张图片
- `analyze_package_status`: 检查2张图片

### 4. \_truncate_dialogue_history方法

**位置**: `core/providers/vllm/doorlock_vllm.py`

**功能**: 截断对话历史以满足Token限制

**实现细节**:

- 从最新对话开始累加Token
- 超出`max_tokens`限制时停止添加
- 保留最近的对话内容
- 记录截断日志

**测试结果**: ✓ 通过

- max_tokens=0: 保留0轮
- max_tokens=10: 保留1轮
- max_tokens=20: 保留2轮
- max_tokens=1000: 保留全部5轮
- 验证保留最新对话: 通过

**使用场景**:

- `_build_messages`: 构建消息时自动截断对话历史

### 5. \_check_token_usage方法（优化）

**位置**: `core/providers/vllm/doorlock_vllm.py`

**功能**: 多层次Token使用量监控和警告

**实现细节**:

1. **输出Token监控**（主要警告）
   - 计算使用率: `completion_tokens / max_tokens`
   - 超过80%时警告: "AI回复可能被截断"
2. **输入Token监控**（次要警告）
   - 计算使用率: `prompt_tokens / max_input_tokens`
   - 超过80%时警告: "建议优化提示词、减少对话历史"
3. **总Token监控**（严重警告）
   - 计算使用率: `total_tokens / model_context_limit`
   - 超过80%时警告: "接近模型上限，可能影响性能"
4. **详细统计记录**
   - 记录输入/输出/总Token数及使用率
   - 记录响应时间
   - 记录工具调用次数

**测试结果**: ✓ 通过

- 正常使用量: 无警告，记录统计信息
- 输出Token接近限制: 触发输出Token警告
- 输入Token较高: 触发输入Token和总Token警告

**使用场景**:

- `analyze_with_tools`: 每次VLLM调用后检查
- `final_package_check`: 快递状态检查后检查
- `generate_intent_summary`: 意图总结生成后检查

## 配置参数

### doorlock_config.yaml

```yaml
performance:
  max_token_usage_ratio: 0.8 # 输出Token警告阈值
  vllm_limits:
    model_context_limit: 262144 # 模型上下文窗口
    max_input_tokens: 260096 # 最大输入Token
    max_output_tokens: 32768 # 最大输出Token
    max_image_tokens: 16384 # 最大图片Token
    tokens_per_image: 7000 # 每张图片Token数
    input_warning_ratio: 0.8 # 输入Token警告阈值
    total_warning_ratio: 0.8 # 总Token警告阈值
```

## Token优化效果

### 统一模式对话Token消耗

| 对话轮次     | 传入内容            | Token消耗 | 优化效果          |
| ------------ | ------------------- | --------- | ----------------- |
| 第1轮        | 访客图片 + 基准图片 | ~14K      | 建立基准状态      |
| 第2-10轮     | 访客图片            | ~7K/轮    | 节省基准图片Token |
| 对话结束检查 | 基准图片 + 当前图片 | ~15K      | 最终状态对比      |
| 意图总结     | 访客图片 + 对话历史 | ~8K       | 生成结构化总结    |

**10轮对话总消耗**: 14K + 9×7K + 15K + 8K = 100K tokens

**优化效果**: 相比每轮都传基准图片节省约30% Token

## 测试验证

### 测试脚本

`main/xiaozhi-server/test_token_management.py`

### 测试结果

```
✓ 通过: 文本Token估算
✓ 通过: 图片Token估算
✓ 通过: 图片Token限制检查
✓ 通过: 对话历史截断
✓ 通过: Token使用量监控

✓ 所有测试通过！
```

## 关键特性

### 1. 智能Token估算

- 区分中英文字符，提供准确的Token估算
- 支持图片Token估算，可配置不同分辨率

### 2. 多层次限制检查

- 图片Token限制（防止超出图片处理能力）
- 输入Token限制（防止超出模型输入窗口）
- 输出Token限制（确保回复完整性）
- 总Token限制（防止超出模型上下文窗口）

### 3. 自动对话历史截断

- 从最新对话开始保留
- 自动计算可用Token空间
- 综合考虑输入限制和总限制

### 4. 分级警告机制

- 输出Token警告（影响回复完整性）
- 输入Token警告（影响上下文容量）
- 总Token警告（接近模型上限）
- 详细统计信息（用于监控和分析）

## 日志示例

### 正常使用

```
[DoorlockVLLM]-INFO-VLLM调用统计 | 输入: 1000 (0.4%) | 输出: 200 (40.0%) | 总计: 1200 (0.5%) | 响应时间: 2.50s | 工具调用: 0
```

### 输出Token警告

```
[DoorlockVLLM]-WARNING-⚠️ 输出Token接近限制: 450/500 (90.0%)，AI回复可能被截断，建议增加 max_tokens
```

### 输入Token警告

```
[DoorlockVLLM]-WARNING-⚠️ 输入Token较高: 220000/260096 (84.6%)，建议优化提示词、减少对话历史或降低图片分辨率
```

### 总Token警告

```
[DoorlockVLLM]-WARNING-⚠️ 总Token接近上下文窗口: 220200/262144 (84.0%)，接近模型上限，可能影响性能
```

### 图片Token超限

```
[DoorlockVLLM]-ERROR-❌ 图片Token超出限制: 21000 > 16384, 图片数量: 3
```

### 对话历史截断

```
[DoorlockVLLM]-INFO-对话历史已截断: 10 -> 7 轮, 可用Token: 50000 (受限于输入限制)
```

## 相关需求

- 需求3.1: Token优化策略
- 需求3.2: 对话历史管理
- 需求3.3: 图片Token限制
- 需求3.4: 多层次Token监控

## 下一步

所有Token管理和优化功能已实现并测试通过，可以继续实现任务3（照片缓存管理器）。
