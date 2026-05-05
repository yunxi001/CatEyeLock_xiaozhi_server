# 门锁VLLM统一模式设计方案

## 问题分析

### 当前问题

在看护模式激活期间，如果有新访客到访：

- ❌ 无法同时进行意图识别对话
- ❌ 访客体验差（无法与AI交互）
- ❌ 看护监控和访客对话互斥

### 根本原因

两种模式被设计为独立的、互斥的功能：

1. **看护监控模式**：持续循环拍照分析（每5秒）
2. **意图识别模式**：访客到访时的对话流程

### 用户期望

看护模式激活时，仍然能够：

- ✅ 与访客进行正常对话
- ✅ 识别访客意图
- ✅ 同时监控快递安全
- ✅ 无缝的用户体验

---

## 解决方案对比

### 方案一：并行运行两个独立模式 ⭐⭐⭐

**设计思路**：看护监控和意图识别同时运行，互不干扰。

#### 实现方式

```python
async def handle_visitor(self, device_id: str, conn=None, guard_active: bool = False):
    """处理访客到访"""

    # 1. 如果看护模式激活，确保监控循环在运行
    if guard_active:
        await self.guard_manager.ensure_monitoring_active(device_id)

    # 2. 正常执行意图识别流程（不受看护模式影响）
    result = await self.start_intent_dialogue(...)

    return result
```

#### 优点

- ✅ 实现简单，无需修改现有逻辑
- ✅ 两个模式完全独立，互不影响
- ✅ 易于理解和维护

#### 缺点

- ⚠️ VLLM调用频率高（看护5秒+对话实时）
- ⚠️ Token消耗大
- ⚠️ 可能有资源竞争

#### 适用场景

- VLLM服务性能充足
- Token成本可接受
- 访客到访频率低

---

### 方案二：智能暂停看护监控 ⭐⭐⭐⭐

**设计思路**：访客到访时暂停看护监控，对话结束后恢复。

#### 实现方式

```python
async def handle_visitor(self, device_id: str, conn=None, guard_active: bool = False):
    """处理访客到访"""

    # 1. 如果看护模式激活，暂停监控循环
    if guard_active:
        await self.guard_manager.pause_monitoring(device_id)
        logger.info("看护监控已暂停，开始访客对话")

    try:
        # 2. 执行意图识别流程
        result = await self.start_intent_dialogue(...)

        return result
    finally:
        # 3. 对话结束后恢复监控
        if guard_active:
            await self.guard_manager.resume_monitoring(device_id)
            logger.info("访客对话结束，恢复看护监控")
```

#### 优点

- ✅ 避免资源竞争
- ✅ Token消耗可控
- ✅ 用户体验好（对话优先）

#### 缺点

- ⚠️ 对话期间快递无监控（存在安全窗口期）
- ⚠️ 需要实现暂停/恢复机制

#### 适用场景

- 对话时间短（<2分钟）
- 访客到访频率低
- 安全窗口期可接受

---

### 方案三：统一为智能看护对话模式 ⭐⭐⭐⭐⭐（推荐）

**设计思路**：将两种模式融合为一个智能模式，AI同时处理访客对话和快递监控。

#### 核心理念

**AI同时具备两种能力**：

1. 与访客对话，识别意图
2. 监控门口快递，检测威胁

**关键创新**：

- 每次VLLM调用都传入访客照片+基准图片（如果有）
- AI根据场景自动选择关注点
- 统一的提示词指导AI处理两种任务

#### 实现架构

```python
async def handle_visitor_with_guard(
    self,
    device_id: str,
    visitor_image: bytes,
    baseline_image: Optional[bytes],
    dialogue_history: List[Dict],
    conn=None
) -> Dict[str, Any]:
    """统一的访客处理（支持看护模式）

    Args:
        device_id: 设备ID
        visitor_image: 访客照片
        baseline_image: 基准图片（看护模式激活时提供）
        dialogue_history: 对话历史
        conn: 连接对象

    Returns:
        处理结果（包含对话回复和威胁检测）
    """

    # 构建图片列表
    images = [visitor_image]
    if baseline_image:
        images.append(baseline_image)

    # 构建统一提示词
    system_prompt = self._build_unified_prompt(has_baseline=baseline_image is not None)

    # 构建问题文本
    if baseline_image:
        question = """
        你现在需要同时处理两个任务：
        1. 与访客对话，了解来访意图
        2. 对比基准图片（第2张）和当前门口状态，监控快递安全

        第1张图片：访客照片
        第2张图片：基准图片（快递初始状态）

        请根据对话内容回复访客，同时如果发现快递异常，调用相应工具报告。
        """
    else:
        question = "请与访客对话，了解来访意图。"

    # 调用VLLM
    result = await self.vllm.analyze(
        images=images,
        question=question,
        dialogue_history=dialogue_history,
        system_prompt=system_prompt
    )

    # 处理结果
    return {
        "ai_response": result["content"],  # 对话回复
        "tool_calls": result["tool_calls"],  # 工具调用（可能包含威胁报告）
        "token_usage": result["token_usage"]
    }
```

#### 统一提示词设计

```yaml
# config/doorlock_prompts.yaml
unified_guard_dialogue_prompt: |
  你是智能门锁的AI助手，具备以下能力：

  ## 核心任务
  1. **访客对话**：与访客进行自然对话，了解来访目的
  2. **快递看护**：监控门口快递安全（如果提供了基准图片）

  ## 对话任务
  - 识别访客意图类型（delivery/visit/sales/maintenance/other）
  - 提取重要信息（留言、提醒）
  - 保持礼貌友好的对话风格
  - 如果访客提到"快递放门口了"，调用 enable_package_guard
  - 对话结束时调用 report_visitor_intent 生成总结

  ## 看护任务（仅当提供基准图片时）
  - 对比基准图片（第2张）和当前门口状态
  - 判断快递是否被移动、翻找或破坏
  - 评估威胁等级（low/medium/high）
  - 如果发现异常，调用 report_package_status 报告

  ## 重要规则
  1. **对话优先**：首先关注与访客的对话，自然回复访客问题
  2. **后台监控**：同时在后台检查快递状态，发现异常才报告
  3. **不要混淆**：不要在对话中提及快递监控，除非访客主动询问
  4. **智能判断**：如果访客是主人（is_owner=true），快递被拿走是正常的

  ## 工具调用时机
  - enable_package_guard: 访客提到快递放门口
  - disable_package_guard: 主人取走快递
  - report_package_status: 发现快递异常（非主人拿走/破坏）
  - report_visitor_intent: 对话结束时生成总结
```

#### 优点

- ✅ 完美的用户体验（对话和监控同时进行）
- ✅ AI智能决策（自动判断关注点）
- ✅ 代码简洁（统一的处理流程）
- ✅ Token优化（一次调用完成两个任务）

#### 缺点

- ⚠️ 提示词复杂（需要AI理解双重任务）
- ⚠️ Token消耗高（每次对话都传2张图片）
- ⚠️ AI可能混淆任务（需要精心设计提示词）

#### 适用场景

- VLLM模型能力强（如GPT-4V、Qwen2-VL）
- 追求最佳用户体验
- Token成本可接受

---

### 方案四：事件驱动的混合模式 ⭐⭐⭐⭐

**设计思路**：看护监控降频，访客对话时触发额外的威胁检测。

#### 实现方式

```python
class HybridGuardManager:
    """混合看护管理器"""

    def __init__(self):
        self.monitoring_interval = 10  # 降低到10秒
        self.visitor_check_enabled = True  # 访客到访时额外检查

    async def on_visitor_arrival(self, device_id: str, visitor_image: bytes):
        """访客到访事件处理"""

        # 1. 立即进行一次威胁检测
        if self.is_guard_active(device_id):
            baseline_image = await self.load_baseline(device_id)
            threat_result = await self.quick_threat_check(
                current_image=visitor_image,
                baseline_image=baseline_image
            )

            if threat_result["threat_level"] != "low":
                # 发现威胁，立即通知
                await self.handle_threat(threat_result)

        # 2. 正常进行意图识别对话
        intent_result = await self.intent_handler.start_dialogue(...)

        return intent_result

    async def quick_threat_check(self, current_image: bytes, baseline_image: bytes):
        """快速威胁检测（简化版，不包含对话）"""

        result = await self.vllm.analyze(
            images=[baseline_image, current_image],
            question="快速判断：门口快递是否有异常？仅回答威胁等级。",
            dialogue_history=[],
            system_prompt=self.get_prompt("quick_threat_check_prompt")
        )

        return result
```

#### 监控策略

| 场景     | 监控频率 | 说明                   |
| -------- | -------- | ---------------------- |
| 无访客   | 10秒/次  | 降低频率，节省资源     |
| 访客到访 | 立即检测 | 访客到达时额外检测一次 |
| 对话中   | 暂停     | 对话期间暂停定时监控   |
| 对话结束 | 立即检测 | 对话结束后立即检测一次 |

#### 优点

- ✅ 平衡性能和体验
- ✅ 关键时刻不漏检
- ✅ Token消耗可控
- ✅ 实现相对简单

#### 缺点

- ⚠️ 对话期间仍有监控盲区
- ⚠️ 需要协调多个检测时机

---

## 推荐方案选择

### 场景一：性能优先 → 方案二（智能暂停）

**适用条件**：

- VLLM服务性能有限
- Token成本敏感
- 访客对话时间短（<2分钟）
- 可接受短暂的监控盲区

**实施要点**：

```python
# 1. 添加暂停/恢复方法
class PackageGuardManager:
    async def pause_monitoring(self, device_id: str):
        """暂停监控"""
        if device_id in self._monitoring_tasks:
            self._paused_devices.add(device_id)
            logger.info(f"看护监控已暂停: {device_id}")

    async def resume_monitoring(self, device_id: str):
        """恢复监控"""
        if device_id in self._paused_devices:
            self._paused_devices.remove(device_id)
            logger.info(f"看护监控已恢复: {device_id}")

# 2. 监控循环检查暂停状态
async def _monitoring_loop(self, device_id: str, session_id: str):
    while True:
        # 检查是否暂停
        if device_id in self._paused_devices:
            await asyncio.sleep(1)
            continue

        # 正常监控逻辑
        await asyncio.sleep(self.photo_interval)
        await self._capture_and_analyze(device_id, session_id)
```

---

### 场景二：体验优先 → 方案三（统一模式）⭐

**适用条件**：

- VLLM模型能力强（GPT-4V、Qwen2-VL-72B）
- 追求最佳用户体验
- Token成本可接受
- 希望AI智能处理复杂场景

**实施要点**：

#### 1. 修改VLLM提供者

```python
class DoorlockVLLMProvider:
    async def analyze_with_guard(
        self,
        visitor_image: str,
        baseline_image: Optional[str],
        dialogue_history: List[Dict],
        system_prompt: str
    ) -> Dict[str, Any]:
        """统一分析（支持看护模式）"""

        # 构建图片列表
        images = [visitor_image]
        if baseline_image:
            images.append(baseline_image)

        # 构建问题
        if baseline_image:
            question = """
            同时处理两个任务：
            1. 与访客对话（第1张图片）
            2. 监控快递安全（对比第1、2张图片）
            """
        else:
            question = "与访客对话，了解来访意图。"

        return await self.analyze(
            images=images,
            question=question,
            dialogue_history=dialogue_history,
            system_prompt=system_prompt
        )
```

#### 2. 修改意图处理器

```python
class DoorlockIntentHandler:
    async def start_intent_dialogue(
        self,
        device_id: str,
        session_id: str,
        person_info: Optional[Dict],
        visitor_image: bytes,
        conn=None
    ):
        """启动意图识别对话（支持看护模式）"""

        # 检查看护模式
        guard_active = await self.guard_manager.is_active(device_id)
        baseline_image = None

        if guard_active:
            # 加载基准图片
            baseline_image = await self.guard_manager.load_baseline(device_id)
            logger.info("看护模式激活，将同时监控快递")

        # 对话循环
        while dialogue_count < max_rounds:
            # 等待访客回复
            visitor_response = await self._wait_for_visitor_response(device_id)

            # 添加到对话历史
            self.session_manager.add_dialogue(session_id, "user", visitor_response)

            # 调用VLLM（统一模式）
            dialogue_history = self.session_manager.get_dialogue_history(session_id)

            vllm_result = await self.vllm.analyze_with_guard(
                visitor_image=base64.b64encode(visitor_image).decode(),
                baseline_image=base64.b64encode(baseline_image).decode() if baseline_image else None,
                dialogue_history=dialogue_history,
                system_prompt=self.get_unified_prompt()
            )

            # 处理AI回复
            ai_response = vllm_result["content"]
            if ai_response:
                await self._play_ai_response(device_id, ai_response)

            # 处理工具调用（可能包含威胁报告）
            tool_calls = vllm_result["tool_calls"]
            await self._handle_tool_calls(tool_calls)

            dialogue_count += 1
```

#### 3. 设计统一提示词

```yaml
unified_guard_dialogue_prompt: |
  你是智能门锁的AI助手，同时负责访客对话和快递看护。

  ## 当前场景
  - 第1张图片：访客照片
  - 第2张图片：基准图片（快递初始状态，如果提供）

  ## 任务优先级
  1. **主要任务**：与访客自然对话
     - 了解来访目的
     - 识别意图类型
     - 提取重要信息

  2. **次要任务**：监控快递（如果提供基准图片）
     - 对比第1、2张图片
     - 判断快递是否被移动/破坏
     - 仅在发现异常时报告

  ## 工具调用规则
  - 对话中：正常回复访客，不提及监控
  - 发现异常：调用 report_package_status（威胁等级medium/high）
  - 访客提到快递：调用 enable_package_guard
  - 主人取快递：调用 disable_package_guard
  - 对话结束：调用 report_visitor_intent

  ## 智能判断
  - 如果访客是主人（is_owner=true），快递被拿走是正常的
  - 如果访客说"我来取快递"，这是正常行为
  - 只有可疑行为才报告威胁
```

---

### 场景三：平衡方案 → 方案四（事件驱动）

**适用条件**：

- 需要平衡性能和体验
- 不希望完全暂停监控
- 关键时刻不能漏检
- Token成本中等

**实施要点**：

```python
class HybridGuardManager:
    """混合看护管理器"""

    def __init__(self):
        self.normal_interval = 10  # 正常间隔10秒
        self.visitor_events = {}  # 访客事件记录

    async def on_visitor_arrival(self, device_id: str, visitor_image: bytes):
        """访客到达事件"""

        # 记录事件
        self.visitor_events[device_id] = {
            "timestamp": time.time(),
            "in_dialogue": True
        }

        # 立即检测一次
        if self.is_guard_active(device_id):
            await self._immediate_check(device_id, visitor_image)

    async def on_dialogue_end(self, device_id: str):
        """对话结束事件"""

        # 更新状态
        if device_id in self.visitor_events:
            self.visitor_events[device_id]["in_dialogue"] = False

        # 立即检测一次
        if self.is_guard_active(device_id):
            await self._immediate_check(device_id)

    async def _monitoring_loop(self, device_id: str, session_id: str):
        """监控循环（智能调整间隔）"""

        while True:
            # 检查是否在对话中
            if device_id in self.visitor_events:
                event = self.visitor_events[device_id]
                if event["in_dialogue"]:
                    # 对话中，暂停定时监控
                    await asyncio.sleep(1)
                    continue

            # 正常监控
            await asyncio.sleep(self.normal_interval)
            await self._capture_and_analyze(device_id, session_id)
```

---

## 实施建议

### 第一阶段：快速实现（方案二）

**目标**：解决当前问题，提升用户体验

**工作量**：2-3小时

**步骤**：

1. 在 `PackageGuardManager` 添加 `pause_monitoring()` 和 `resume_monitoring()`
2. 在 `DoorlockIntentHandler.handle_visitor()` 中调用暂停/恢复
3. 测试验证

### 第二阶段：优化体验（方案三或方案四）

**目标**：实现更好的用户体验

**工作量**：1-2天

**步骤**：

1. 设计统一提示词
2. 修改VLLM调用逻辑
3. 充分测试AI的双重任务处理能力
4. 根据测试结果调整提示词

---

## Token成本分析

### 方案二：智能暂停

**对话期间**：

- 意图识别：~10K tokens/次
- 看护监控：暂停（0 tokens）
- 总计：~10K tokens/次对话

**非对话期间**：

- 看护监控：~15K tokens/次（每5秒）
- 总计：~10.8M tokens/小时

### 方案三：统一模式

**对话期间**：

- 统一分析：~17K tokens/次（2张图片+对话历史）
- 看护监控：停止定时监控
- 总计：~17K tokens/次对话

**非对话期间**：

- 看护监控：~15K tokens/次（每5秒）
- 总计：~10.8M tokens/小时

**对比**：

- 方案三每次对话多消耗 ~7K tokens（多一张基准图片）
- 如果每小时5次访客，额外成本：35K tokens
- 相比总消耗（10.8M），增加约0.3%

**结论**：Token成本增加可忽略不计。

---

## 最终推荐

### 推荐方案：方案三（统一模式）⭐⭐⭐⭐⭐

**理由**：

1. ✅ 用户体验最佳（无缝的对话和监控）
2. ✅ Token成本增加可忽略（仅0.3%）
3. ✅ 架构优雅（统一的处理流程）
4. ✅ AI能力充分利用（多模态理解）
5. ✅ 未来扩展性强（易于添加新功能）

**实施路径**：

1. **第一步**（1小时）：实现方案二作为临时方案
2. **第二步**（1天）：设计和测试统一提示词
3. **第三步**（半天）：重构代码实现方案三
4. **第四步**（半天）：充分测试和优化

**风险控制**：

- 保留方案二的代码作为降级方案
- 通过配置开关控制使用哪种方案
- 监控AI的双重任务处理效果

---

## 配置示例

```yaml
# config/doorlock_config.yaml
package_guard:
  mode: "unified" # unified/paused/hybrid

  # 统一模式配置
  unified_mode:
    enabled: true
    use_baseline_in_dialogue: true # 对话时是否传入基准图片

  # 暂停模式配置
  paused_mode:
    enabled: false
    auto_resume: true # 对话结束后自动恢复

  # 混合模式配置
  hybrid_mode:
    enabled: false
    normal_interval: 10 # 正常监控间隔
    visitor_check: true # 访客到达时立即检查
```

---

## 总结

针对"看护模式期间无法进行意图识别对话"的问题，最佳解决方案是：

**将两种模式统一为智能看护对话模式**，让AI同时处理访客对话和快递监控，通过精心设计的提示词指导AI在对话中后台监控快递安全。

这个方案在用户体验、技术实现和成本控制之间达到了最佳平衡。
