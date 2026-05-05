# 通义千问视觉模型配置建议

## 📊 模型参数分析

### 使用的模型

| 模型                          | 上下文长度 | 最大输入 | 最大输出 | 单图Token  |
| ----------------------------- | ---------- | -------- | -------- | ---------- |
| **qwen3-vl-flash-2026-01-22** | 262,144    | 260,096  | 32,768   | 最大16,384 |
| **qwen3-vl-plus-2025-12-19**  | 262,144    | 260,096  | 32,768   | 最大16,384 |

### 关键参数说明

```
上下文长度：262,144 Token (256K)
  └─ 输入 + 输出的总限制

最大输入：260,096 Token
  └─ 提示词 + 对话历史 + 图片的总限制

最大输出：32,768 Token (32K)
  └─ AI 生成回复的最大长度

单图Token：最大 16,384 Token (16K)
  └─ 单张图片最多消耗的 Token 数
```

---

## 🎯 门锁场景 Token 消耗分析

### 场景 1：意图识别（单图片）

```
输入Token估算：
  ├─ 系统提示词（intent_recognition_prompt）：~800 tokens
  ├─ 对话历史（10轮）：~200 tokens
  ├─ 问题文本：~50 tokens
  ├─ 访客照片（1张）：~1,000-5,000 tokens（取决于分辨率）
  └─ 工具Schema（5个工具）：~500 tokens
  总计：~2,550-6,550 tokens

输出Token估算：
  ├─ AI回复文本：~50-200 tokens
  └─ 工具调用JSON：~50-100 tokens
  总计：~100-300 tokens

总消耗：~2,650-6,850 tokens
```

### 场景 2：看护监控（双图片）

```
输入Token估算：
  ├─ 系统提示词（package_guard_prompt）：~1,200 tokens
  ├─ 对话历史（少量）：~100 tokens
  ├─ 问题文本：~100 tokens
  ├─ 基准图片（1张）：~1,000-5,000 tokens
  ├─ 当前图片（1张）：~1,000-5,000 tokens
  └─ 工具Schema（5个工具）：~500 tokens
  总计：~3,900-11,900 tokens

输出Token估算：
  ├─ AI回复文本：~50-150 tokens
  └─ 工具调用JSON：~80-150 tokens
  总计：~130-300 tokens

总消耗：~4,030-12,200 tokens
```

### 场景 3：极端情况（高分辨率图片 + 长对话）

```
输入Token估算：
  ├─ 系统提示词：~1,200 tokens
  ├─ 对话历史（20轮）：~500 tokens
  ├─ 问题文本：~100 tokens
  ├─ 高分辨率图片（2张）：~10,000-16,000 tokens/张
  └─ 工具Schema：~500 tokens
  总计：~22,300-33,300 tokens

输出Token估算：
  ├─ AI详细回复：~200-500 tokens
  └─ 工具调用JSON：~100-200 tokens
  总计：~300-700 tokens

总消耗：~22,600-34,000 tokens
```

---

## ✅ 推荐配置方案

### 方案 1：保守配置（推荐用于生产环境）

```yaml
# config.yaml
VLLM:
  QwenVLVLLM:
    type: openai
    model_name: qwen3-vl-flash-2026-01-22 # 或 qwen3-vl-plus-2025-12-19
    url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key: 你的api_key

    # 推理参数
    max_tokens: 2000 # 最大输出Token数（保守设置）
    temperature: 0.7 # 温度参数
    top_p: 1.0 # 采样参数

# config/doorlock_config.yaml
performance:
  # Token警告阈值（输出Token使用率）
  max_token_usage_ratio: 0.8 # 输出达到 80% 时警告

  # 上下文窗口大小（用于监控总Token）
  model_context_limit: 262144 # 256K 上下文窗口

  # 最大输入Token限制
  max_input_tokens: 260096 # 最大输入限制

  # 最大输出Token限制
  max_output_tokens: 32768 # 模型支持的最大输出
```

**适用场景**：

- ✅ 日常使用，成本可控
- ✅ 输出内容简洁（2000 tokens 足够）
- ✅ 避免意外的高额费用

**Token 使用率**：

```
意图识别：输出 ~100-300 / 2000 = 5%-15%
看护监控：输出 ~130-300 / 2000 = 6.5%-15%
极端情况：输出 ~300-700 / 2000 = 15%-35%
```

### 方案 2：平衡配置（推荐用于复杂场景）

```yaml
# config.yaml
VLLM:
  QwenVLVLLM:
    max_tokens: 4000 # 增加到 4000，给 AI 更多表达空间
    temperature: 0.7
    top_p: 1.0

# config/doorlock_config.yaml
performance:
  max_token_usage_ratio: 0.8 # 输出达到 80% 时警告
  model_context_limit: 262144
  max_input_tokens: 260096
  max_output_tokens: 32768
```

**适用场景**：

- ✅ 需要详细的分析和描述
- ✅ 复杂的对话场景
- ✅ 多轮对话历史

**Token 使用率**：

```
意图识别：输出 ~100-300 / 4000 = 2.5%-7.5%
看护监控：输出 ~130-300 / 4000 = 3.25%-7.5%
极端情况：输出 ~300-700 / 4000 = 7.5%-17.5%
```

### 方案 3：激进配置（仅用于特殊需求）

```yaml
# config.yaml
VLLM:
  QwenVLVLLM:
    max_tokens: 8000 # 大幅增加输出空间
    temperature: 0.7
    top_p: 1.0

# config/doorlock_config.yaml
performance:
  max_token_usage_ratio: 0.9 # 提高到 90%
  model_context_limit: 262144
  max_input_tokens: 260096
  max_output_tokens: 32768
```

**适用场景**：

- ⚠️ 需要非常详细的分析报告
- ⚠️ 成本不敏感
- ⚠️ 特殊测试场景

---

## 🔧 修复 Token 警告机制

### 当前代码问题

```python
# doorlock_vllm.py 第 258-264 行（有问题）
usage_ratio = token_usage["total_tokens"] / self.max_tokens
if usage_ratio > self.max_token_usage_ratio:
    self.logger.warning(
        f"Token使用量已达 {token_usage['total_tokens']}/{self.max_tokens} "
        f"({usage_ratio:.1%})，接近上限"
    )
```

### 修复方案：多层次监控

```python
# 修复后的代码
def _check_token_usage(self, token_usage: dict, response_time: float):
    """检查Token使用情况，提供多层次警告

    Args:
        token_usage: Token使用统计
        response_time: 响应时间
    """
    prompt_tokens = token_usage["prompt_tokens"]
    completion_tokens = token_usage["completion_tokens"]
    total_tokens = token_usage["total_tokens"]

    # 1. 检查输出Token使用率（主要警告）
    output_usage_ratio = completion_tokens / self.max_tokens
    if output_usage_ratio > self.max_token_usage_ratio:
        self.logger.bind(tag=TAG).warning(
            f"⚠️ 输出Token接近限制: {completion_tokens}/{self.max_tokens} "
            f"({output_usage_ratio:.1%})，AI回复可能被截断"
        )

    # 2. 检查输入Token（信息提示）
    max_input_tokens = getattr(self, 'max_input_tokens', 260096)
    if prompt_tokens > max_input_tokens * 0.8:
        self.logger.bind(tag=TAG).warning(
            f"⚠️ 输入Token较高: {prompt_tokens}/{max_input_tokens} "
            f"({prompt_tokens/max_input_tokens:.1%})，建议优化提示词或减少对话历史"
        )

    # 3. 检查总Token（接近上下文窗口）
    model_context_limit = getattr(self, 'model_context_limit', 262144)
    if total_tokens > model_context_limit * 0.8:
        self.logger.bind(tag=TAG).warning(
            f"⚠️ 总Token接近上下文窗口: {total_tokens}/{model_context_limit} "
            f"({total_tokens/model_context_limit:.1%})，接近模型上限"
        )

    # 4. 记录详细统计（信息级别）
    self.logger.bind(tag=TAG).info(
        f"VLLM调用统计 | "
        f"输入: {prompt_tokens} ({prompt_tokens/max_input_tokens:.1%}) | "
        f"输出: {completion_tokens} ({output_usage_ratio:.1%}) | "
        f"总计: {total_tokens} ({total_tokens/model_context_limit:.1%}) | "
        f"响应时间: {response_time:.2f}s"
    )
```

### 在 analyze_with_tools 中调用

```python
# 替换原来的警告代码
# Token统计和警告
token_usage = {
    "prompt_tokens": response.usage.prompt_tokens,
    "completion_tokens": response.usage.completion_tokens,
    "total_tokens": response.usage.total_tokens
}

# 调用多层次检查
self._check_token_usage(token_usage, response_time)
```

---

## 📈 成本分析

### qwen3-vl-flash-2026-01-22（推荐）

#### 方案 1：保守配置（max_tokens=2000）

```
单次调用成本估算：

意图识别场景：
  输入：~2,550-6,550 tokens × 0.367元/百万 = 0.00094-0.0024元
  输出：~100-300 tokens × 2.936元/百万 = 0.00029-0.00088元
  总计：~0.00123-0.00328元/次

看护监控场景：
  输入：~3,900-11,900 tokens × 0.367元/百万 = 0.00143-0.00437元
  输出：~130-300 tokens × 2.936元/百万 = 0.00038-0.00088元
  总计：~0.00181-0.00525元/次

日均成本估算（假设每天100次调用）：
  意图识别（80次）：0.10-0.26元
  看护监控（20次）：0.04-0.11元
  总计：0.14-0.37元/天
  月成本：4.2-11.1元/月
```

#### 方案 2：平衡配置（max_tokens=4000）

```
单次调用成本估算：

意图识别场景：
  输入：~2,550-6,550 tokens × 0.367元/百万 = 0.00094-0.0024元
  输出：~100-300 tokens × 2.936元/百万 = 0.00029-0.00088元
  总计：~0.00123-0.00328元/次（与方案1相同，因为实际输出未增加）

看护监控场景：
  输入：~3,900-11,900 tokens × 0.367元/百万 = 0.00143-0.00437元
  输出：~130-300 tokens × 2.936元/百万 = 0.00038-0.00088元
  总计：~0.00181-0.00525元/次（与方案1相同）

月成本：4.2-11.1元/月（实际输出未增加，成本相同）
```

**说明**：增加 `max_tokens` 不会增加成本，只是给 AI 更多输出空间。实际成本取决于 AI 实际生成的 Token 数。

### qwen3-vl-plus-2025-12-19（性能更强）

```
单次调用成本估算：

意图识别场景：
  输入：~2,550-6,550 tokens × 1.541元/百万 = 0.00393-0.01009元
  输出：~100-300 tokens × 4.624元/百万 = 0.00046-0.00139元
  总计：~0.00439-0.01148元/次

看护监控场景：
  输入：~3,900-11,900 tokens × 1.541元/百万 = 0.00601-0.01834元
  输出：~130-300 tokens × 4.624元/百万 = 0.00060-0.00139元
  总计：~0.00661-0.01973元/次

月成本：13.2-35.1元/月（约为 flash 版本的 3-4 倍）
```

---

## 🎯 最终推荐配置

### 生产环境推荐

```yaml
# config.yaml
selected_module:
  VLLM: QwenVLVLLM

VLLM:
  QwenVLVLLM:
    type: openai
    model_name: qwen3-vl-flash-2026-01-22 # 速度快、成本低
    url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key: 你的api_key

    # 推理参数（平衡配置）
    max_tokens: 3000 # 给 AI 足够的表达空间
    temperature: 0.7 # 保持创造性
    top_p: 1.0 # 采样参数

# config/doorlock_config.yaml
performance:
  # Token警告阈值
  max_token_usage_ratio: 0.8 # 输出达到 80% 时警告

  # 模型限制（用于监控）
  model_context_limit: 262144 # 256K 上下文窗口
  max_input_tokens: 260096 # 最大输入限制
  max_output_tokens: 32768 # 最大输出限制

  # 会话清理延迟
  session_cleanup_delay: 0
```

### 配置说明

| 参数                    | 值     | 说明                        |
| ----------------------- | ------ | --------------------------- |
| `max_tokens`            | 3000   | 平衡输出质量和成本          |
| `max_token_usage_ratio` | 0.8    | 输出达到 2400 tokens 时警告 |
| `model_context_limit`   | 262144 | 用于监控总Token是否接近上限 |
| `max_input_tokens`      | 260096 | 用于监控输入Token           |
| `max_output_tokens`     | 32768  | 模型支持的最大输出          |

### 预期效果

```
意图识别场景：
  输出Token：~100-300
  输出使用率：3.3%-10%
  警告触发：❌ 不会触发（正常使用）

看护监控场景：
  输出Token：~130-300
  输出使用率：4.3%-10%
  警告触发：❌ 不会触发（正常使用）

输出接近限制：
  输出Token：~2500
  输出使用率：83%
  警告触发：✅ 会触发（合理警告）

月成本估算：
  日均100次调用：~0.14-0.37元/天
  月成本：~4.2-11.1元/月
```

---

## 🔍 图片 Token 优化建议

### 图片分辨率控制

通义千问视觉模型的图片 Token 消耗与分辨率相关：

```
低分辨率（640×480）：~1,000-2,000 tokens
中分辨率（1280×720）：~3,000-5,000 tokens
高分辨率（1920×1080）：~8,000-12,000 tokens
超高分辨率（4K）：~15,000-16,384 tokens（接近上限）
```

### 优化建议

1. **意图识别场景**：使用中等分辨率（1280×720）
   - Token 消耗：~3,000-5,000
   - 足够识别人脸和基本场景

2. **看护监控场景**：使用中等分辨率（1280×720）
   - Token 消耗：~3,000-5,000 × 2 = 6,000-10,000
   - 足够对比快递状态变化

3. **避免使用 4K 图片**：
   - Token 消耗过高（~15K/张）
   - 成本增加 3-5 倍
   - 对识别效果提升有限

### 图片压缩配置

```python
# 在图片上传时进行压缩
from PIL import Image

def compress_image(image_data, max_width=1280, max_height=720, quality=85):
    """压缩图片到合适的分辨率

    Args:
        image_data: 原始图片数据
        max_width: 最大宽度
        max_height: 最大高度
        quality: JPEG质量（1-100）

    Returns:
        压缩后的图片数据
    """
    img = Image.open(image_data)

    # 计算缩放比例
    ratio = min(max_width / img.width, max_height / img.height)
    if ratio < 1:
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # 保存为JPEG
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=quality)
    return output.getvalue()
```

---

## 📝 实施步骤

### 1. 更新配置文件

```bash
# 编辑 config.yaml
vim main/xiaozhi-server/config.yaml

# 编辑 doorlock_config.yaml
vim main/xiaozhi-server/config/doorlock_config.yaml
```

### 2. 修改 doorlock_vllm.py

```python
# 在 __init__ 方法中添加新参数
self.model_context_limit = 262144  # 256K
self.max_input_tokens = 260096
self.max_output_tokens = 32768

# 添加 _check_token_usage 方法
def _check_token_usage(self, token_usage: dict, response_time: float):
    # ... (见上文完整代码)

# 在 analyze_with_tools 中调用
self._check_token_usage(token_usage, response_time)
```

### 3. 测试验证

```bash
# 启动服务
python app.py

# 测试意图识别
curl -X POST http://localhost:8003/api/doorlock/test/intent \
  -H "Content-Type: application/json" \
  -d '{"device_id": "test001", "image": "base64_data"}'

# 查看日志，确认警告机制正常
tail -f tmp/server.log | grep "Token"
```

---

## 🎓 总结

### 关键配置

| 配置项                  | 推荐值                    | 说明                |
| ----------------------- | ------------------------- | ------------------- |
| `model_name`            | qwen3-vl-flash-2026-01-22 | 速度快、成本低      |
| `max_tokens`            | 3000                      | 平衡质量和成本      |
| `max_token_usage_ratio` | 0.8                       | 输出达到 80% 时警告 |
| `model_context_limit`   | 262144                    | 256K 上下文窗口     |

### 预期效果

- ✅ 正常使用不会触发警告
- ✅ 输出接近限制时及时警告
- ✅ 月成本控制在 5-15 元
- ✅ 支持复杂场景（双图片对比）

### 优化建议

1. **图片分辨率**：控制在 1280×720
2. **对话历史**：保留最近 10 轮
3. **提示词**：定期优化，减少冗余
4. **监控成本**：定期查看 API 使用情况

---

## 📚 参考资料

- [通义千问 API 文档](https://help.aliyun.com/zh/dashscope/developer-reference/api-details)
- [Qwen-VL 模型介绍](https://github.com/QwenLM/Qwen-VL)
- [Token 计算规则](https://help.aliyun.com/zh/dashscope/developer-reference/tongyi-qianwen-vl-plus-api)
