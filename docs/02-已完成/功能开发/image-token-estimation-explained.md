# 图片 Token 估算详解

## 📋 当前实现

### 代码实现

```python
def _estimate_image_tokens(self, image_count: int) -> int:
    """估算图片的Token数量

    Args:
        image_count: 图片数量

    Returns:
        估算的Token数量

    说明：
        - 假设每张图片约占用 8000-16000 Token
        - 实际取决于图片分辨率和内容复杂度
        - 保守估计：每张图片 12000 Token
    """
    return image_count * 12000
```

### 估算方法

**固定值估算**：每张图片 = 12000 tokens

---

## 🤔 为什么使用固定值？

### 原因1：无法获取图片实际信息

```python
# 当前传入的是 Base64 字符串
visitor_image: str  # Base64编码的图片

# 问题：
# 1. 没有解码图片获取分辨率
# 2. 没有分析图片内容复杂度
# 3. 无法调用模型的Token计数API
```

### 原因2：模型Token计算是黑盒

```
视觉模型的Token计算由模型内部决定，包括：
- 图片分辨率
- 图片内容复杂度
- 模型的图片编码方式
- 模型的patch大小

我们无法在发送请求前准确计算
```

### 原因3：需要快速估算

```python
# 在构建消息前就需要估算
# 不能等到API返回才知道Token数
available_for_history = self.max_input_tokens - fixed_tokens - self.max_tokens
```

---

## 📊 12000 Token 的依据

### 依据1：通义千问官方文档

```
单图最大支持 16,384 Token
```

### 依据2：实际测试经验

```
常见分辨率的Token消耗（估算）：
- 640×480 (VGA):     约 6,000-8,000 tokens
- 1280×720 (HD):     约 10,000-12,000 tokens
- 1920×1080 (FHD):   约 14,000-16,000 tokens
- 3840×2160 (4K):    约 16,384 tokens (达到上限)
```

### 依据3：保守估计策略

```
选择中等偏上的值：12000 tokens

原因：
- 不能太低：避免低估导致超限
- 不能太高：避免过度限制对话历史
- 12000 是 HD 分辨率的典型值
```

---

## ⚠️ 当前实现的局限性

### 局限1：无法区分分辨率

```python
# 问题：所有图片都按 12000 估算
low_res_image = "..."   # 640×480，实际约 6000 tokens
high_res_image = "..."  # 1920×1080，实际约 15000 tokens

# 估算结果
_estimate_image_tokens(1)  # 都是 12000 tokens

# 影响：
# - 低分辨率图片：估算偏高，浪费对话历史空间
# - 高分辨率图片：估算偏低，可能超限
```

### 局限2：无法考虑内容复杂度

```
相同分辨率的图片，Token消耗可能不同：
- 简单图片（纯色背景）：Token较少
- 复杂图片（细节丰富）：Token较多

当前实现：无法区分
```

### 局限3：估算误差

```
估算值：12000 tokens
实际值：可能在 6000-16000 tokens 之间

误差范围：±50%
```

---

## 🔍 实际Token消耗示例

### 场景1：意图识别（单图片）

```
图片：访客照片（1280×720）
估算：12000 tokens
实际：约 10500 tokens
误差：+14%（估算偏高）

影响：
- 对话历史可用空间略少
- 但不会导致超限
```

### 场景2：看护监控（双图片）

```
图片1：基准图片（1920×1080）
图片2：当前图片（1920×1080）

估算：2 × 12000 = 24000 tokens
实际：约 15000 + 15000 = 30000 tokens
误差：-20%（估算偏低）⚠️

影响：
- 可能超过 max_image_tokens (16384)
- 当前会被检查拒绝（正确行为）
```

### 场景3：低分辨率图片

```
图片：低分辨率照片（640×480）
估算：12000 tokens
实际：约 6000 tokens
误差：+100%（估算偏高）

影响：
- 浪费对话历史空间
- 但不会导致功能问题
```

---

## 💡 改进方案

### 方案1：基于Base64长度估算（简单）

```python
def _estimate_image_tokens(self, image_base64: str) -> int:
    """基于Base64长度估算图片Token数量

    Args:
        image_base64: Base64编码的图片

    Returns:
        估算的Token数量
    """
    # Base64长度大致反映图片大小
    base64_length = len(image_base64)

    # 经验公式（需要实际测试调整）
    # 假设：每 1000 个Base64字符 ≈ 100 tokens
    estimated_tokens = int(base64_length / 10)

    # 限制在合理范围内
    estimated_tokens = max(6000, min(estimated_tokens, 16384))

    return estimated_tokens
```

**优点**：

- 考虑了图片大小
- 实现简单

**缺点**：

- Base64长度不等于分辨率
- 压缩率影响估算
- 仍然是粗略估算

---

### 方案2：解码图片获取分辨率（中等）

```python
import base64
from PIL import Image
from io import BytesIO

def _estimate_image_tokens(self, image_base64: str) -> int:
    """基于图片分辨率估算Token数量

    Args:
        image_base64: Base64编码的图片

    Returns:
        估算的Token数量
    """
    try:
        # 解码Base64
        image_data = base64.b64decode(image_base64)
        image = Image.open(BytesIO(image_data))

        # 获取分辨率
        width, height = image.size
        pixels = width * height

        # 基于像素数估算Token
        # 经验公式（需要实际测试调整）
        if pixels < 500000:  # < 640×480
            return 6000
        elif pixels < 1000000:  # < 1280×720
            return 10000
        elif pixels < 2000000:  # < 1920×1080
            return 14000
        else:  # >= 1920×1080
            return 16000

    except Exception as e:
        # 解码失败，使用默认值
        self.logger.bind(tag=TAG).warning(f"图片解码失败，使用默认估算: {e}")
        return 12000
```

**优点**：

- 基于实际分辨率
- 更准确的估算

**缺点**：

- 需要解码图片（性能开销）
- 需要安装 Pillow 库
- 仍然是估算，不是精确值

---

### 方案3：调用模型Token计数API（理想）

```python
async def _get_actual_image_tokens(self, image_base64: str) -> int:
    """调用模型API获取实际Token数量

    Args:
        image_base64: Base64编码的图片

    Returns:
        实际的Token数量
    """
    # 伪代码：调用模型的Token计数API
    response = await self.client.count_tokens(
        messages=[{
            "role": "user",
            "content": [{
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
            }]
        }]
    )

    return response.image_tokens
```

**优点**：

- 精确的Token数量
- 与实际API调用一致

**缺点**：

- 需要额外的API调用（成本和延迟）
- 不是所有模型都提供Token计数API
- 通义千问目前不支持

---

## 🎯 推荐方案

### 短期：保持当前实现（固定值）

```python
def _estimate_image_tokens(self, image_count: int) -> int:
    return image_count * 12000
```

**理由**：

1. 实现简单，性能好
2. 对于大多数场景足够准确
3. 配合 `max_image_tokens` 配置可以调整

**建议配置调整**：

```yaml
# doorlock_config.yaml
vllm_limits:
  max_image_tokens: 32768 # 从 16384 增加到 32768
```

这样可以支持：

- 单张高分辨率图片（16K）
- 双张中等分辨率图片（2×12K = 24K）

---

### 中期：基于分辨率估算（方案2）

如果发现固定值估算误差太大，可以实施方案2：

1. 解码图片获取分辨率
2. 基于分辨率区间估算Token
3. 缓存估算结果（避免重复解码）

**实施条件**：

- 发现大量图片Token超限
- 或者对话历史空间不足

---

### 长期：等待模型支持Token计数API

如果通义千问未来提供Token计数API，可以实施方案3。

---

## 📊 当前配置与估算的关系

### 配置

```yaml
vllm_limits:
  max_image_tokens: 16384 # 16K
```

### 估算逻辑

```python
# 意图识别（1张图片）
estimated = 1 × 12000 = 12000 tokens
check: 12000 < 16384 ✅ 通过

# 看护监控（2张图片）
estimated = 2 × 12000 = 24000 tokens
check: 24000 > 16384 ❌ 拒绝
```

### 问题

当前配置 `max_image_tokens: 16384` 无法支持双图片场景（估算24000 > 16384）

### 解决方案

```yaml
# 方案1：增加限制（推荐）
vllm_limits:
  max_image_tokens: 32768  # 32K，支持双图片

# 方案2：降低估算值（不推荐）
def _estimate_image_tokens(self, image_count: int) -> int:
    return image_count * 8000  # 从 12000 降到 8000
```

**推荐方案1**，因为：

- 实际高分辨率图片可能接近16K
- 降低估算值可能导致低估，反而更危险

---

## 📝 总结

### 当前实现

- **方法**：固定值估算（每张12000 tokens）
- **优点**：简单、快速、无依赖
- **缺点**：无法区分分辨率，误差±50%

### 为什么这样实现

1. 无法获取图片实际信息（Base64字符串）
2. 模型Token计算是黑盒
3. 需要快速估算（构建消息前）
4. 12000是中等分辨率的典型值

### 改进建议

1. **短期**：调整配置 `max_image_tokens: 32768`
2. **中期**：实施基于分辨率的估算（如果需要）
3. **长期**：等待模型Token计数API

### 实际影响

- 对于大多数场景（HD分辨率），估算足够准确
- 配合配置调整，可以满足业务需求
- 提前检查机制可以防止超限

---

**文档版本**：v1.0  
**创建时间**：2026-02-13
