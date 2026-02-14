# 图片 Token 估算值配置化说明

## ✅ 配置化完成

**实施时间**：2026-02-13  
**目标**：将图片Token估算值从硬编码改为配置化，方便根据实际情况调整

---

## 📝 修改内容

### 1. 配置文件修改

#### 文件位置

`main/xiaozhi-server/config/doorlock_config.yaml`

#### 新增配置项

```yaml
performance:
  vllm_limits:
    # ... 其他配置 ...

    # 单张图片Token估算值（用于输入Token计算）
    # 注意：实际Token消耗取决于图片分辨率和内容复杂度
    # - VGA (640×480): 约 6000-8000 tokens
    # - HD (1280×720): 约 10000-12000 tokens
    # - FHD (1920×1080): 约 14000-16000 tokens
    tokens_per_image: 7000 # 当前图片为VGA分辨率
```

---

### 2. 代码修改

#### 修改位置

`main/xiaozhi-server/core/providers/vllm/doorlock_vllm.py`

#### 修改1：`__init__` 方法 - 加载配置

```python
# 新增加载 tokens_per_image 配置
vllm_limits = performance_config.get("vllm_limits", {})
self.model_context_limit = int(vllm_limits.get("model_context_limit", 262144))
self.max_input_tokens = int(vllm_limits.get("max_input_tokens", 260096))
self.max_output_tokens = int(vllm_limits.get("max_output_tokens", 32768))
self.max_image_tokens = int(vllm_limits.get("max_image_tokens", 16384))
self.tokens_per_image = int(vllm_limits.get("tokens_per_image", 7000))  # 新增
self.input_warning_ratio = float(vllm_limits.get("input_warning_ratio", 0.8))
self.total_warning_ratio = float(vllm_limits.get("total_warning_ratio", 0.8))
```

#### 修改2：`_estimate_image_tokens` 方法 - 使用配置

```python
def _estimate_image_tokens(self, image_count: int) -> int:
    """估算图片的Token数量

    Args:
        image_count: 图片数量

    Returns:
        估算的Token数量

    说明：
        - 从配置文件加载 tokens_per_image 参数
        - 默认值：7000 tokens（VGA分辨率）
        - 可根据实际图片分辨率调整配置
    """
    return image_count * self.tokens_per_image  # 使用配置值
```

#### 修改3：初始化日志 - 显示配置

```python
self.logger.bind(tag=TAG).info(
    f"门锁VLLM提供者初始化完成: 复用系统配置 {selected_vllm}, "
    f"model={self.model_name}, max_tokens={self.max_tokens}, "
    f"context_limit={self.model_context_limit}, "
    f"tokens_per_image={self.tokens_per_image}, "  # 新增
    f"prompts_loaded={len(self.prompts)}"
)
```

---

## 🎯 优势

### 1. 灵活调整

```yaml
# 无需修改代码，只需修改配置文件
tokens_per_image: 7000  # VGA
tokens_per_image: 11000  # HD
tokens_per_image: 15000  # FHD
```

### 2. 环境适配

```yaml
# 开发环境（低分辨率）
tokens_per_image: 7000

# 生产环境（高分辨率）
tokens_per_image: 12000
```

### 3. 快速测试

```yaml
# 测试不同估算值的影响
tokens_per_image: 5000   # 低估
tokens_per_image: 7000   # 准确
tokens_per_image: 10000  # 高估
```

### 4. 向后兼容

```python
# 配置缺失时使用默认值
self.tokens_per_image = int(vllm_limits.get("tokens_per_image", 7000))
```

---

## 📊 配置示例

### 场景1：VGA分辨率（当前）

```yaml
vllm_limits:
  tokens_per_image: 7000 # 640×480
  max_image_tokens: 16384 # 支持双图片（2×7000=14000 < 16384）
```

**效果**：

- 单图片：7000 tokens
- 双图片：14000 tokens
- 检查：14000 < 16384 ✅ 通过

---

### 场景2：HD分辨率

```yaml
vllm_limits:
  tokens_per_image: 11000 # 1280×720
  max_image_tokens: 32768 # 需要增加限制（2×11000=22000 < 32768）
```

**效果**：

- 单图片：11000 tokens
- 双图片：22000 tokens
- 检查：22000 < 32768 ✅ 通过

**注意**：需要同时调整 `max_image_tokens`

---

### 场景3：FHD分辨率

```yaml
vllm_limits:
  tokens_per_image: 15000 # 1920×1080
  max_image_tokens: 32768 # 需要增加限制（2×15000=30000 < 32768）
```

**效果**：

- 单图片：15000 tokens
- 双图片：30000 tokens
- 检查：30000 < 32768 ✅ 通过

**注意**：需要同时调整 `max_image_tokens`

---

### 场景4：混合分辨率（保守估算）

```yaml
vllm_limits:
  tokens_per_image: 12000 # 中等偏上的保守估算
  max_image_tokens: 32768 # 支持双图片
```

**效果**：

- 适用于不确定图片分辨率的场景
- 保守估算，避免低估

---

## 🔧 配置调整指南

### 步骤1：确定图片分辨率

```bash
# 查看图片分辨率
# 方法1：使用图片查看器
# 方法2：使用Python
from PIL import Image
img = Image.open("visitor.jpg")
print(img.size)  # (width, height)
```

### 步骤2：选择估算值

```
VGA (640×480):     tokens_per_image: 7000
HD (1280×720):     tokens_per_image: 11000
FHD (1920×1080):   tokens_per_image: 15000
4K (3840×2160):    tokens_per_image: 16000（接近上限）
```

### 步骤3：调整配置

```yaml
# 编辑 doorlock_config.yaml
vllm_limits:
  tokens_per_image: 11000 # 根据实际分辨率调整
```

### 步骤4：调整限制（如果需要）

```yaml
# 如果双图片超过 max_image_tokens，需要增加限制
vllm_limits:
  tokens_per_image: 11000
  max_image_tokens: 32768 # 从 16384 增加到 32768
```

### 步骤5：重启服务

```bash
# 重启服务以加载新配置
python app.py
```

### 步骤6：验证日志

```
查看初始化日志：
[INFO] 门锁VLLM提供者初始化完成: ..., tokens_per_image=11000, ...
```

---

## 📈 实际影响分析

### 配置：tokens_per_image: 7000（VGA）

#### 意图识别（单图片）

```
图片Token：7000
固定Token：系统提示词(500) + 问题(50) + 图片(7000) = 7550
可用对话历史：260096 - 7550 - 3000 = 249546 tokens
```

#### 看护监控（双图片）

```
图片Token：14000
固定Token：系统提示词(800) + 问题(100) + 图片(14000) = 14900
可用对话历史：260096 - 14900 - 3000 = 242196 tokens
图片检查：14000 < 16384 ✅ 通过
```

---

### 配置：tokens_per_image: 11000（HD）

#### 意图识别（单图片）

```
图片Token：11000
固定Token：系统提示词(500) + 问题(50) + 图片(11000) = 11550
可用对话历史：260096 - 11550 - 3000 = 245546 tokens
```

#### 看护监控（双图片）

```
图片Token：22000
固定Token：系统提示词(800) + 问题(100) + 图片(22000) = 22900
可用对话历史：260096 - 22900 - 3000 = 234196 tokens
图片检查：22000 > 16384 ❌ 拒绝（需要调整 max_image_tokens）
```

**解决方案**：

```yaml
vllm_limits:
  tokens_per_image: 11000
  max_image_tokens: 32768 # 增加限制
```

---

## ✅ 验证结果

### 代码验证

- ✅ 语法检查通过
- ✅ 配置加载正确
- ✅ 默认值设置合理
- ✅ 日志输出完整

### 功能验证

- ✅ 配置文件修改生效
- ✅ 代码读取配置正确
- ✅ 估算值可调整
- ✅ 向后兼容（配置缺失时使用默认值）

---

## 📚 相关配置

### 完整配置示例

```yaml
# doorlock_config.yaml
performance:
  max_token_usage_ratio: 0.8
  session_cleanup_delay: 0

  vllm_limits:
    model_context_limit: 262144 # 256K tokens
    max_input_tokens: 260096 # 254K tokens
    max_output_tokens: 32768 # 32K tokens
    max_image_tokens: 16384 # 16K tokens
    tokens_per_image: 7000 # VGA分辨率（可调整）
    input_warning_ratio: 0.8 # 80%
    total_warning_ratio: 0.8 # 80%
```

---

## 📝 总结

### 实施内容

1. ✅ 配置文件新增 `tokens_per_image` 参数
2. ✅ 代码加载配置参数
3. ✅ `_estimate_image_tokens` 方法使用配置值
4. ✅ 初始化日志显示配置值

### 核心优势

1. **灵活调整**：无需修改代码，只需修改配置
2. **环境适配**：不同环境使用不同配置
3. **快速测试**：方便测试不同估算值的影响
4. **向后兼容**：配置缺失时使用默认值

### 使用建议

1. 根据实际图片分辨率调整 `tokens_per_image`
2. 如果双图片超限，同时调整 `max_image_tokens`
3. 修改配置后重启服务
4. 查看初始化日志验证配置加载

---

**文档版本**：v1.0  
**创建时间**：2026-02-13  
**状态**：✅ 已完成
