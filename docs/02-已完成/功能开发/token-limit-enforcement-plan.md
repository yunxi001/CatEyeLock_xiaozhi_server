# Token 限制强制执行实施方案

## 📋 问题分析

### 当前状态

- ✅ 配置已设置（`doorlock_config.yaml` 中的 `vllm_limits`）
- ✅ 监控已实现（`_check_token_usage` 方法）
- ❌ **限制未应用**：配置只用于监控和警告，没有实际限制Token使用

### 需要实现的限制

| 限制类型  | 配置参数              | 当前值  | 应用位置    | 限制方式                |
| --------- | --------------------- | ------- | ----------- | ----------------------- |
| 输出Token | `max_output_tokens`   | 32,768  | API调用参数 | `max_tokens` 参数       |
| 输入Token | `max_input_tokens`    | 260,096 | 消息构建前  | 截断对话历史/优化提示词 |
| 图片Token | `max_image_tokens`    | 16,384  | 消息构建前  | 限制图片数量/降低分辨率 |
| 总Token   | `model_context_limit` | 262,144 | 消息构建前  | 综合控制输入+输出       |

---

## 🎯 实施方案

### 方案 1：输出Token限制（最简单，推荐优先实现）

#### 实现位置

`doorlock_vllm.py` 的 `analyze_with_tools` 方法

#### 实现方式

使用配置的 `max_output_tokens` 覆盖系统的 `max_tokens`

#### 代码修改

```python
# 在 analyze_with_tools 方法中
def analyze_with_tools(self, ...):
    # 使用门锁配置的输出Token限制（如果配置了）
    max_tokens = min(self.max_tokens, self.max_output_tokens)

    # 调用VLLM
    response = self.client.chat.completions.create(
        model=self.model_name,
        messages=messages,
        tools=tools if tools else None,
        temperature=self.temperature,
        top_p=self.top_p,
        max_tokens=max_tokens,  # 使用限制后的值
        stream=False
    )
```

#### 优点

- 实现简单，只需修改一行代码
- 直接限制模型输出，防止回复过长
- 不影响输入内容

#### 缺点

- 只限制输出，不限制输入
- 如果输入过大，仍可能超过模型上限

---

### 方案 2：输入Token限制（中等复杂度）

#### 实现位置

`doorlock_vllm.py` 的 `_build_messages` 方法

#### 实现方式

在构建消息前，估算Token数量并截断对话历史

#### 代码修改

##### 新增方法：估算Token数量

```python
def _estimate_tokens(self, text: str) -> int:
    """估算文本的Token数量（简化方法）

    Args:
        text: 文本内容

    Returns:
        估算的Token数量

    说明：
        - 中文：约 1.5 字符/Token
        - 英文：约 4 字符/Token
        - 这是粗略估算，实际Token数由模型决定
    """
    # 统计中英文字符
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars

    # 估算Token数
    estimated_tokens = int(chinese_chars / 1.5 + other_chars / 4)

    return estimated_tokens

def _estimate_image_tokens(self, image_count: int) -> int:
    """估算图片的Token数量

    Args:
        image_count: 图片数量

    Returns:
        估算的Token数量

    说明：
        - 假设每张图片约占用 8000-16000 Token
        - 实际取决于图片分辨率和内容复杂度
    """
    # 保守估计：每张图片 12000 Token
    return image_count * 12000
```

##### 修改 `_build_messages` 方法

```python
def _build_messages(
    self,
    question: str,
    images: List[str],
    dialogue_history: List[Dict[str, str]],
    system_prompt: Optional[str] = None
) -> List[Dict[str, Any]]:
    """构建消息列表（带Token限制）

    Args:
        question: 问题文本
        images: 图片列表（Base64）
        dialogue_history: 对话历史
        system_prompt: 系统提示词

    Returns:
        消息列表
    """
    # 估算各部分Token数
    system_tokens = self._estimate_tokens(system_prompt) if system_prompt else 0
    question_tokens = self._estimate_tokens(question)
    image_tokens = self._estimate_image_tokens(len(images))

    # 计算固定部分Token数
    fixed_tokens = system_tokens + question_tokens + image_tokens

    # 计算对话历史可用Token数
    # 预留输出空间：使用 max_tokens（系统配置的输出限制）
    available_for_history = self.max_input_tokens - fixed_tokens - self.max_tokens

    if available_for_history < 0:
        self.logger.bind(tag=TAG).warning(
            f"⚠️ 固定内容已超出输入限制: "
            f"system={system_tokens}, question={question_tokens}, "
            f"images={image_tokens}, total={fixed_tokens}, "
            f"limit={self.max_input_tokens}"
        )
        # 如果固定内容已超限，清空对话历史
        dialogue_history = []
        available_for_history = 0

    # 截断对话历史
    truncated_history = self._truncate_dialogue_history(
        dialogue_history,
        max_tokens=available_for_history
    )

    if len(truncated_history) < len(dialogue_history):
        self.logger.bind(tag=TAG).info(
            f"对话历史已截断: {len(dialogue_history)} -> {len(truncated_history)} 轮"
        )

    # 构建消息
    messages = []

    # 添加系统提示词
    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })

    # 添加截断后的对话历史
    for msg in truncated_history:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })

    # 添加当前问题和图片
    content = [{"type": "text", "text": question}]

    # 添加图片
    for image_base64 in images:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{image_base64}"
            }
        })

    messages.append({
        "role": "user",
        "content": content
    })

    return messages

def _truncate_dialogue_history(
    self,
    dialogue_history: List[Dict[str, str]],
    max_tokens: int
) -> List[Dict[str, str]]:
    """截断对话历史以满足Token限制

    Args:
        dialogue_history: 完整对话历史
        max_tokens: 最大Token数

    Returns:
        截断后的对话历史（保留最近的对话）
    """
    if max_tokens <= 0:
        return []

    # 从最新的对话开始累加
    truncated = []
    current_tokens = 0

    for msg in reversed(dialogue_history):
        content = msg.get("content", "")
        msg_tokens = self._estimate_tokens(content)

        if current_tokens + msg_tokens > max_tokens:
            # 超出限制，停止添加
            break

        truncated.insert(0, msg)
        current_tokens += msg_tokens

    return truncated
```

#### 优点

- 主动控制输入Token数量
- 防止输入过大导致模型拒绝请求
- 保留最近的对话，丢弃较早的对话

#### 缺点

- Token估算不精确（实际Token数由模型决定）
- 实现较复杂
- 可能丢失重要的早期对话信息

---

### 方案 3：图片Token限制（中等复杂度）

#### 实现位置

`doorlock_vllm.py` 的 `analyze_intent` 和 `analyze_package_status` 方法

#### 实现方式

限制图片数量或降低图片分辨率

#### 代码修改

##### 新增方法：检查图片Token限制

```python
def _check_image_token_limit(self, image_count: int) -> bool:
    """检查图片数量是否超过Token限制

    Args:
        image_count: 图片数量

    Returns:
        是否在限制内
    """
    estimated_tokens = self._estimate_image_tokens(image_count)

    if estimated_tokens > self.max_image_tokens:
        self.logger.bind(tag=TAG).warning(
            f"⚠️ 图片Token超出限制: {estimated_tokens} > {self.max_image_tokens}, "
            f"图片数量: {image_count}"
        )
        return False

    return True
```

##### 修改 `analyze_package_status` 方法

```python
async def analyze_package_status(
    self,
    current_image: str,
    baseline_image: str,
    dialogue_history: List[Dict[str, str]],
    system_prompt: Optional[str] = None
) -> Dict[str, Any]:
    """看护监控分析（双图片对比+对话历史）

    Args:
        current_image: 当前图片（Base64）
        baseline_image: 基准图片（Base64）
        dialogue_history: 对话历史
        system_prompt: 看护模式提示词（可选，如果不提供则从配置加载）

    Returns:
        分析结果
    """
    self.logger.bind(tag=TAG).debug("执行看护监控分析")

    # 检查图片Token限制
    if not self._check_image_token_limit(2):
        self.logger.bind(tag=TAG).error("图片Token超出限制，无法执行分析")
        raise ValueError("图片Token超出限制")

    # 如果没有提供提示词，从配置加载
    if not system_prompt:
        system_prompt = self.get_prompt("package_guard_prompt")

    # 构建问题文本，说明两张图片的含义
    question = """
    请对比当前图片和基准图片，判断门口快递的状态变化和威胁等级。

    第一张图片是基准图片（之前的状态）
    第二张图片是当前图片（现在的状态）

    请调用 report_package_status 工具报告情况。
    """

    return self.analyze_with_tools(
        question=question,
        images=[baseline_image, current_image],
        dialogue_history=dialogue_history,
        system_prompt=system_prompt
    )
```

#### 优点

- 防止图片过多导致Token超限
- 提前检查，避免无效API调用

#### 缺点

- 估算不精确
- 当前场景下图片数量固定（1张或2张），限制意义不大

---

### 方案 4：总Token限制（最复杂，综合方案）

#### 实现位置

`doorlock_vllm.py` 的 `_build_messages` 方法

#### 实现方式

综合考虑输入+输出，确保总Token不超过模型上限

#### 代码修改

```python
def _build_messages(
    self,
    question: str,
    images: List[str],
    dialogue_history: List[Dict[str, str]],
    system_prompt: Optional[str] = None
) -> List[Dict[str, Any]]:
    """构建消息列表（带总Token限制）

    Args:
        question: 问题文本
        images: 图片列表（Base64）
        dialogue_history: 对话历史
        system_prompt: 系统提示词

    Returns:
        消息列表
    """
    # 估算各部分Token数
    system_tokens = self._estimate_tokens(system_prompt) if system_prompt else 0
    question_tokens = self._estimate_tokens(question)
    image_tokens = self._estimate_image_tokens(len(images))

    # 计算固定部分Token数
    fixed_tokens = system_tokens + question_tokens + image_tokens

    # 计算可用Token数
    # 总限制 = 模型上下文窗口
    # 可用 = 总限制 - 固定输入 - 预留输出
    available_for_history = self.model_context_limit - fixed_tokens - self.max_tokens

    # 同时检查输入限制
    max_input_for_history = self.max_input_tokens - fixed_tokens

    # 取两者的最小值
    available_for_history = min(available_for_history, max_input_for_history)

    if available_for_history < 0:
        self.logger.bind(tag=TAG).warning(
            f"⚠️ 固定内容已超出限制: "
            f"system={system_tokens}, question={question_tokens}, "
            f"images={image_tokens}, total={fixed_tokens}, "
            f"max_input={self.max_input_tokens}, "
            f"context_limit={self.model_context_limit}"
        )
        dialogue_history = []
        available_for_history = 0

    # 截断对话历史
    truncated_history = self._truncate_dialogue_history(
        dialogue_history,
        max_tokens=available_for_history
    )

    if len(truncated_history) < len(dialogue_history):
        self.logger.bind(tag=TAG).info(
            f"对话历史已截断: {len(dialogue_history)} -> {len(truncated_history)} 轮, "
            f"可用Token: {available_for_history}"
        )

    # 构建消息（同方案2）
    # ...
```

#### 优点

- 综合考虑所有限制
- 最大程度防止超限
- 提供详细的限制信息

#### 缺点

- 实现最复杂
- Token估算误差可能累积

---

## 📊 推荐实施顺序

### 阶段 1：输出Token限制（立即实施）

- **优先级**：⭐⭐⭐⭐⭐
- **复杂度**：低
- **影响**：防止回复被截断
- **实施时间**：5分钟

```python
# 修改 analyze_with_tools 方法
max_tokens = min(self.max_tokens, self.max_output_tokens)
```

### 阶段 2：输入Token限制（短期实施）

- **优先级**：⭐⭐⭐⭐
- **复杂度**：中
- **影响**：防止输入过大
- **实施时间**：30分钟

实现：

1. 新增 `_estimate_tokens` 方法
2. 新增 `_truncate_dialogue_history` 方法
3. 修改 `_build_messages` 方法

### 阶段 3：图片Token限制（可选）

- **优先级**：⭐⭐
- **复杂度**：低
- **影响**：当前场景意义不大（图片数量固定）
- **实施时间**：10分钟

### 阶段 4：总Token限制（长期优化）

- **优先级**：⭐⭐⭐
- **复杂度**：中
- **影响**：综合防护
- **实施时间**：20分钟

---

## 🔧 配置调整建议

### 当前配置（保守）

```yaml
vllm_limits:
  model_context_limit: 262144 # 256K
  max_input_tokens: 260096 # 254K
  max_output_tokens: 32768 # 32K
  max_image_tokens: 16384 # 16K
```

### 推荐配置（平衡）

```yaml
vllm_limits:
  model_context_limit: 262144 # 256K（不变）
  max_input_tokens: 200000 # 195K（降低，为输出预留更多空间）
  max_output_tokens: 3000 # 3K（实际使用，与系统配置一致）
  max_image_tokens: 32768 # 32K（2张图片，每张16K）
```

### 激进配置（成本优先）

```yaml
vllm_limits:
  model_context_limit: 262144 # 256K（不变）
  max_input_tokens: 100000 # 98K（大幅降低）
  max_output_tokens: 2000 # 2K（降低输出）
  max_image_tokens: 16384 # 16K（单张图片）
```

---

## 📝 实施检查清单

### 阶段 1：输出Token限制

- [ ] 修改 `analyze_with_tools` 方法
- [ ] 使用 `min(self.max_tokens, self.max_output_tokens)`
- [ ] 测试意图识别场景
- [ ] 测试看护监控场景
- [ ] 验证日志输出

### 阶段 2：输入Token限制

- [ ] 实现 `_estimate_tokens` 方法
- [ ] 实现 `_estimate_image_tokens` 方法
- [ ] 实现 `_truncate_dialogue_history` 方法
- [ ] 修改 `_build_messages` 方法
- [ ] 测试对话历史截断
- [ ] 测试长对话场景
- [ ] 验证日志输出

### 阶段 3：图片Token限制

- [ ] 实现 `_check_image_token_limit` 方法
- [ ] 修改 `analyze_package_status` 方法
- [ ] 测试双图片场景
- [ ] 验证日志输出

### 阶段 4：总Token限制

- [ ] 修改 `_build_messages` 方法（综合限制）
- [ ] 测试极限场景
- [ ] 验证所有限制生效
- [ ] 性能测试

---

## 🎯 预期效果

### 实施前

```
输入：220,000 tokens（无限制）
输出：500 tokens（系统限制）
总计：220,500 tokens（可能超限）

警告：⚠️ 输入Token较高 (84.6%)
警告：⚠️ 总Token接近上下文窗口 (84.1%)
```

### 实施后（阶段1+2）

```
输入：50,000 tokens（截断对话历史）
输出：500 tokens（限制生效）
总计：50,500 tokens（安全范围）

日志：对话历史已截断: 20 -> 8 轮, 可用Token: 50000
日志：VLLM调用统计 | 输入: 50000 (19.2%) | 输出: 500 (16.7%) | 总计: 50500 (19.3%)
```

---

## 📚 相关文档

- `doorlock_config.yaml` - Token限制配置
- `doorlock_vllm.py` - VLLM提供者实现
- `doorlock-token-monitoring-implementation.md` - 监控机制文档
- `qwen-vllm-config-recommendations.md` - 配置建议文档

---

**文档版本**：v1.0  
**创建时间**：2026-02-13  
**状态**：待实施
