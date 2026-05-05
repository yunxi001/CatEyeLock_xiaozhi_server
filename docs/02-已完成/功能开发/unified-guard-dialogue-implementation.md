# 统一智能看护对话模式 - 完整技术实现文档

## 文档概述

本文档详细说明"统一智能看护对话模式"的完整技术实现方案，包括：

- 提示词设计
- 代码实现方案
- 数据流程
- 测试方案

基于深度访谈的决策结果编写。

---

## 一、核心设计原则

### 1.1 设计目标

**主要目标**：在看护模式激活期间，访客仍能正常进行意图识别对话，无缝的用户体验。

**实现方式**：AI同时处理两个任务

- 主任务：与访客自然对话，识别意图
- 次任务：后台监控快递安全，发现异常才报告

### 1.2 关键决策

| 决策点     | 选择                 | 理由                        |
| ---------- | -------------------- | --------------------------- |
| 提示词架构 | 三层动态组合         | 灵活且Token可控             |
| 图片传递   | 仅第一轮传入基准图片 | 节省Token，依赖AI上下文理解 |
| 对话优先级 | 对话优先，监控次之   | 保证访客体验                |
| 威胁检测   | 基于行为触发         | 精准检测，减少噪音          |
| 对话结束   | 程序主动询问AI       | 更可控，返回格式化数据      |
| 工具函数   | 保留4个，移除1个     | 简化AI逻辑                  |

---

## 二、提示词设计

### 2.1 三层结构设计

#### 层级划分

```yaml
# config/doorlock_prompts.yaml

# 第一层：核心角色和风格（共享）
core_role_and_style: |
  【系统角色】
  你是一个智能门锁的AI门卫助手，负责管理门口的访客接待和安全监控。

  【对话风格指南】
  - 礼貌正式，但不失亲和力，让访客感到受欢迎
  - 根据访客身份调整语气：
    * 陌生人：保持礼貌距离，谨慎询问
    * 熟人/已注册访客：更加亲切友好
    * 可疑人员：保持警惕，必要时严肃警告
  - 使用简洁明了的语言，避免冗长和复杂表达
  - 语气自然，像真人对话一样
  - 对话保持简洁，每次回复不超过2-3句话

# 第二层：对话任务说明
dialogue_tasks: |
  【对话任务】
  你的主要任务是与访客进行自然对话，了解来访目的。

  - 主动引导对话，明确询问来访目的
  - 对重要信息（留言、预约、联系方式）进行二次确认
  - 识别推销意图时礼貌但坚定地拒绝
  - 当访客提到"快递"、"外卖"、"包裹"等关键词时，注意是否需要启用看护模式

  【对话策略】
  - 保持对话流畅自然，优先回复访客问题
  - 不要在对话中提及快递监控功能，除非访客主动询问
  - 对话结束由程序判断（沉默30秒或PIR无人体），你无需主动结束

# 第三层：看护任务说明（仅在看护模式激活时添加）
guard_tasks: |
  【看护任务】（后台任务，不影响对话）
  你同时负责监控门口快递的安全。在与访客对话的同时，后台观察访客的行为。

  **重要**：这是后台任务，不要在对话中提及监控功能。

  【监控要点】
  - 观察访客是否靠近、触碰、翻看快递
  - 判断访客行为是否可疑（长时间停留、多次往返）
  - 评估威胁等级（low/medium/high）

  【触发条件】
  仅在以下情况调用 report_package_status：
  - 访客靠近快递并触碰、翻看
  - 访客长时间停留在快递旁边（>10秒）
  - 访客试图拿走快递（非主人）
  - 访客破坏、踢踹快递

  【威胁等级判断】
  - low（低威胁）：路人经过、主人取快递
  - medium（中威胁）：翻看快递、长时间停留
  - high（高威胁）：非主人拿走快递、破坏快递

  **关键规则**：
  - 主人（is_owner=true）取走快递 = 低威胁（正常行为）
  - 非主人取走快递 = 高威胁（盗窃行为）
  - 仅在威胁等级 ≥ medium 时调用工具报告
  - 高威胁时，立即调用工具，可以打断对话

# 第四层：工具调用指南
tools_guide: |
  【工具调用说明】

  你可以调用以下4个工具函数：

  1. enable_package_guard(device_id, reason)
     使用时机：访客提到"快递放门口了"、"外卖在这"、"包裹送到了"
     
  2. disable_package_guard(device_id, reason)
     使用时机：判断快递已被主人（is_owner=true）取走
     
  3. update_package_baseline(device_id)
     使用时机：访客说"我把快递放这了"，立即调用更新基准图片
     
  4. report_package_status(device_id, session_id, action, threat_level, description)
     使用时机：检测到访客可疑行为（威胁等级 ≥ medium）
     参数：
       - action: taking/searching/damaging/normal/passing
       - threat_level: low/medium/high
       - description: 详细描述访客行为
```

### 2.2 动态组合逻辑

```python
def build_unified_prompt(has_baseline_image: bool) -> str:
    """动态组合提示词

    Args:
        has_baseline_image: 是否有基准图片（看护模式是否激活）

    Returns:
        组合后的完整提示词
    """
    # 基础部分（总是包含）
    prompt_parts = [
        prompts["core_role_and_style"],
        prompts["dialogue_tasks"]
    ]

    # 如果看护模式激活，添加看护任务
    if has_baseline_image:
        prompt_parts.append(prompts["guard_tasks"])

    # 总是添加工具指南
    prompt_parts.append(prompts["tools_guide"])

    return "\n\n".join(prompt_parts)
```

### 2.3 对话结束后的专用提示词

#### 快递状态最终检查提示词

````yaml
final_package_check_prompt: |
  【任务】
  访客已离开，请对比基准图片和当前图片，判断快递的最终状态。

  【要求】
  - 对比两张图片，判断快递是否被移动、拿走或破坏
  - 评估威胁等级
  - 以纯JSON格式返回结果

  【输出格式】
  ```json
  {
    "threat_level": "low|medium|high",
    "action": "taking|searching|damaging|normal|passing",
    "description": "详细描述你看到的情况"
  }
````

【判断标准】

- 快递位置未变化 = low + normal
- 快递被移动但未拿走 = medium + searching
- 快递被拿走 = high + taking（除非是主人）
- 快递被破坏 = high + damaging

````

#### 访客意图总结提示词
```yaml
intent_summary_prompt: |
  【任务】
  根据完整的对话历史和访客照片，生成结构化的访客意图总结。

  【要求】
  - 识别访客意图类型
  - 提取重要信息（留言、提醒）
  - 生成完整总结
  - 提供AI分析

  【输出格式】
  ```json
  {
    "intent_type": "delivery|visit|sales|maintenance|other",
    "summary": "简洁的总结（一句话）",
    "important_notes": [
      "【留言】...",
      "【提醒】..."
    ],
    "ai_analysis": "详细的AI分析，包括访客特征、行为观察、建议等"
  }
````

【意图类型说明】

- delivery: 送快递/外卖
- visit: 拜访朋友/家人
- sales: 推销产品/服务
- maintenance: 维修/物业工作
- other: 其他情况

````

---

## 三、代码实现方案

### 3.1 VLLM提供者改造

#### 新增统一分析方法
```python
# main/xiaozhi-server/core/providers/vllm/doorlock_vllm.py

async def analyze_unified(
    self,
    visitor_image: str,
    baseline_image: Optional[str],
    dialogue_history: List[Dict[str, str]],
    is_first_round: bool = False
) -> Dict[str, Any]:
    """统一模式分析（对话+看护）

    Args:
        visitor_image: 访客照片（Base64）
        baseline_image: 基准图片（Base64，仅第一轮传入）
        dialogue_history: 对话历史
        is_first_round: 是否第一轮对话

    Returns:
        {
            "content": AI回复文本,
            "tool_calls": 工具调用列表,
            "token_usage": Token统计,
            "response_time": 响应时间
        }
    """
    self.logger.bind(tag=TAG).debug(
        f"执行统一模式分析: is_first_round={is_first_round}, "
        f"has_baseline={baseline_image is not None}"
    )

    # 构建图片列表
    images = [visitor_image]

    # 仅第一轮传入基准图片
    if is_first_round and baseline_image:
        images.append(baseline_image)
        self.logger.bind(tag=TAG).info("第一轮对话，传入基准图片")

    # 检查图片Token限制
    if not self._check_image_token_limit(len(images)):
        raise ValueError(f"图片Token超出限制")

    # 动态组合提示词
    system_prompt = self._build_unified_prompt(
        has_baseline=baseline_image is not None
    )

    # 构建问题文本
    if baseline_image and is_first_round:
        question = """
        你现在需要同时处理两个任务：
        1. 与访客对话，了解来访意图（主要任务）
        2. 后台监控快递安全（次要任务）

        第1张图片：访客照片
        第2张图片：基准图片（快递初始状态）

        请自然地回复访客，同时在后台观察访客行为。
        """
    else:
        question = "请继续与访客对话，了解来访目的。"

    # 调用核心分析方法
    return self.analyze_with_tools(
        question=question,
        images=images,
        dialogue_history=dialogue_history,
        system_prompt=system_prompt
    )

def _build_unified_prompt(self, has_baseline: bool) -> str:
    """动态组合统一提示词"""
    prompt_parts = [
        self.get_prompt("core_role_and_style"),
        self.get_prompt("dialogue_tasks")
    ]

    if has_baseline:
        prompt_parts.append(self.get_prompt("guard_tasks"))

    prompt_parts.append(self.get_prompt("tools_guide"))

    return "\n\n".join(prompt_parts)
````

#### 对话结束后的检查方法

````python
async def final_package_check(
    self,
    current_image: str,
    baseline_image: str
) -> Dict[str, Any]:
    """对话结束后的快递状态最终检查

    Args:
        current_image: 当前图片（重新拍照）
        baseline_image: 基准图片

    Returns:
        {
            "threat_level": "low|medium|high",
            "action": "taking|searching|damaging|normal|passing",
            "description": "详细描述"
        }
    """
    self.logger.bind(tag=TAG).info("执行对话结束后的快递状态最终检查")

    # 检查图片Token限制
    if not self._check_image_token_limit(2):
        raise ValueError("图片Token超出限制")

    # 加载专用提示词
    system_prompt = self.get_prompt("final_package_check_prompt")

    question = """
    访客已离开，请对比基准图片和当前图片，判断快递的最终状态。

    第1张图片：基准图片（访客到达前）
    第2张图片：当前图片（访客离开后）

    请以纯JSON格式返回结果。
    """

    # 调用VLLM（不需要工具）
    result = self.analyze_with_tools(
        question=question,
        images=[baseline_image, current_image],
        dialogue_history=[],
        system_prompt=system_prompt
    )

    # 解析JSON结果
    try:
        import json
        content = result["content"]
        # 提取JSON（可能包含在markdown代码块中）
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()

        check_result = json.loads(json_str)

        self.logger.bind(tag=TAG).info(
            f"快递状态检查完成: threat_level={check_result.get('threat_level')}"
        )

        return check_result

    except Exception as e:
        self.logger.bind(tag=TAG).error(f"解析快递状态检查结果失败: {e}")
        # 返回默认结果
        return {
            "threat_level": "low",
            "action": "normal",
            "description": "无法解析检查结果"
        }

async def generate_intent_summary(
    self,
    visitor_image: str,
    dialogue_history: List[Dict[str, str]]
) -> Dict[str, Any]:
    """生成访客意图总结

    Args:
        visitor_image: 访客照片
        dialogue_history: 完整对话历史

    Returns:
        {
            "intent_type": "delivery|visit|sales|maintenance|other",
            "summary": "简洁总结",
            "important_notes": ["【留言】...", "【提醒】..."],
            "ai_analysis": "详细分析"
        }
    """
    self.logger.bind(tag=TAG).info("生成访客意图总结")

    # 检查图片Token限制
    if not self._check_image_token_limit(1):
        raise ValueError("图片Token超出限制")

    # 加载专用提示词
    system_prompt = self.get_prompt("intent_summary_prompt")

    question = "请根据完整的对话历史和访客照片，生成结构化的访客意图总结。"

    # 调用VLLM
    result = self.analyze_with_tools(
        question=question,
        images=[visitor_image],
        dialogue_history=dialogue_history,
        system_prompt=system_prompt
    )

    # 解析JSON结果
    try:
        import json
        content = result["content"]
        # 提取JSON
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()

        summary = json.loads(json_str)

        self.logger.bind(tag=TAG).info(
            f"意图总结生成完成: intent_type={summary.get('intent_type')}"
        )

        return summary

    except Exception as e:
        self.logger.bind(tag=TAG).error(f"解析意图总结失败: {e}")
        # 返回默认结果
        return {
            "intent_type": "other",
            "summary": "无法生成总结",
            "important_notes": [],
            "ai_analysis": f"解析失败: {str(e)}"
        }
````

### 3.2 意图处理器改造

```python
# main/xiaozhi-server/core/handle/doorlock_intent_handler.py

async def start_unified_dialogue(
    self,
    device_id: str,
    session_id: str,
    person_info: Optional[Dict[str, Any]],
    visitor_image: bytes,
    conn=None
) -> Dict[str, Any]:
    """启动统一模式对话（支持看护）

    Args:
        device_id: 设备ID
        session_id: 会话ID
        person_info: 人员信息
        visitor_image: 访客照片
        conn: 连接对象

    Returns:
        对话结果
    """
    logger.bind(tag=TAG).info(
        f"启动统一模式对话 - 设备: {device_id}, 会话: {session_id}"
    )

    try:
        # 检查看护模式是否激活
        guard_active = await self.guard_manager.is_active(device_id)
        baseline_image = None

        if guard_active:
            # 加载基准图片
            baseline_image_bytes = await self.guard_manager.load_baseline(device_id)
            if baseline_image_bytes:
                baseline_image = base64.b64encode(baseline_image_bytes).decode()
                logger.bind(tag=TAG).info("看护模式激活，已加载基准图片")

        # 转换访客图片为Base64
        visitor_image_base64 = base64.b64encode(visitor_image).decode()

        # 播放主动问候
        greeting = await self._play_initial_greeting(device_id, person_info)
        self.session_manager.add_dialogue(session_id, "assistant", greeting)

        # 对话循环
        dialogue_count = 0
        max_rounds = self.max_dialogue_rounds
        is_first_round = True

        while dialogue_count < max_rounds:
            # 检查对话是否应该结束
            should_end = await self.session_manager.check_dialogue_end(
                session_id=session_id,
                pir_detected=await self._check_pir_status(device_id)
            )

            if should_end:
                logger.bind(tag=TAG).info(f"对话结束 - 会话: {session_id}")
                break

            # 等待访客回复
            visitor_response = await self._wait_for_visitor_response(device_id)

            if not visitor_response:
                await asyncio.sleep(1)
                continue

            # 添加访客回复到对话历史
            self.session_manager.add_dialogue(session_id, "user", visitor_response)

            # 获取对话历史
            dialogue_history = self.session_manager.get_dialogue_history(session_id)

            # 调用VLLM统一分析
            vllm_result = await self.vllm.analyze_unified(
                visitor_image=visitor_image_base64,
                baseline_image=baseline_image if is_first_round else None,
                dialogue_history=dialogue_history,
                is_first_round=is_first_round
            )

            # 处理AI回复
            ai_response = vllm_result.get("content", "")
            if ai_response:
                self.session_manager.add_dialogue(session_id, "assistant", ai_response)
                await self._play_ai_response(device_id, ai_response)

            # 处理工具调用
            tool_calls = vllm_result.get("tool_calls", [])
            if tool_calls:
                await self._handle_tool_calls(tool_calls, device_id, session_id)

            dialogue_count += 1
            is_first_round = False

        # 对话结束后的处理
        result = await self._post_dialogue_processing(
            device_id=device_id,
            session_id=session_id,
            visitor_image=visitor_image,
            baseline_image=baseline_image_bytes if guard_active else None,
            dialogue_history=self.session_manager.get_dialogue_history(session_id)
        )

        return result

    except Exception as e:
        logger.bind(tag=TAG).error(f"统一模式对话异常: {e}")
        import traceback
        logger.bind(tag=TAG).error(traceback.format_exc())
        return {"success": False, "error": str(e)}

async def _post_dialogue_processing(
    self,
    device_id: str,
    session_id: str,
    visitor_image: bytes,
    baseline_image: Optional[bytes],
    dialogue_history: List[Dict[str, str]]
) -> Dict[str, Any]:
    """对话结束后的处理流程

    Args:
        device_id: 设备ID
        session_id: 会话ID
        visitor_image: 访客照片
        baseline_image: 基准图片（如果看护激活）
        dialogue_history: 对话历史

    Returns:
        处理结果
    """
    logger.bind(tag=TAG).info("开始对话结束后的处理流程")

    # 步骤1: 如果看护模式激活，检查快递状态
    package_check_result = None
    if baseline_image:
        try:
            # 重新拍照
            current_image_bytes = await self._capture_visitor_photo(device_id, None)
            if current_image_bytes:
                current_image = base64.b64encode(current_image_bytes).decode()
                baseline_image_b64 = base64.b64encode(baseline_image).decode()

                # 调用VLLM检查
                package_check_result = await self.vllm.final_package_check(
                    current_image=current_image,
                    baseline_image=baseline_image_b64
                )

                logger.bind(tag=TAG).info(
                    f"快递状态检查完成: {package_check_result}"
                )

                # 如果检测到威胁，保存警报
                if package_check_result.get("threat_level") != "low":
                    await self._save_package_alert(
                        device_id=device_id,
                        session_id=session_id,
                        check_result=package_check_result
                    )
        except Exception as e:
            logger.bind(tag=TAG).error(f"快递状态检查失败: {e}")

    # 步骤2: 生成访客意图总结
    try:
        visitor_image_b64 = base64.b64encode(visitor_image).decode()
        intent_summary = await self.vllm.generate_intent_summary(
            visitor_image=visitor_image_b64,
            dialogue_history=dialogue_history
        )

        logger.bind(tag=TAG).info(
            f"意图总结生成完成: {intent_summary.get('intent_type')}"
        )
    except Exception as e:
        logger.bind(tag=TAG).error(f"生成意图总结失败: {e}")
        intent_summary = {
            "intent_type": "other",
            "summary": "生成失败",
            "important_notes": [],
            "ai_analysis": str(e)
        }

    # 步骤3: 保存访问记录
    visit_id = await self._save_visit_record(
        session_id=session_id,
        person_info=None,  # TODO: 获取人员信息
        intent_summary=intent_summary,
        dialogue_history=dialogue_history,
        visitor_image=visitor_image
    )

    # 步骤4: 发送App通知
    await self.notification_service.notify_visitor_intent(
        visit_id=visit_id,
        session_id=session_id,
        person_info={},
        intent_summary=intent_summary,
        dialogue_text=dialogue_history
    )

    # 步骤5: 清理会话
    await self.session_manager.cleanup_session(session_id)

    logger.bind(tag=TAG).info("对话结束后的处理流程完成")

    return {
        "success": True,
        "visit_id": visit_id,
        "intent_summary": intent_summary,
        "package_check": package_check_result,
        "dialogue_count": len(dialogue_history)
    }

async def _handle_tool_calls(
    self,
    tool_calls: List[Dict[str, Any]],
    device_id: str,
    session_id: str
):
    """处理工具调用

    Args:
        tool_calls: 工具调用列表
        device_id: 设备ID
        session_id: 会话ID
    """
    for tool_call in tool_calls:
        tool_name = tool_call.get("name")
        arguments = tool_call.get("arguments", {})

        # 补充必要参数
        if "device_id" not in arguments:
            arguments["device_id"] = device_id
        if "session_id" not in arguments:
            arguments["session_id"] = session_id

        try:
            # 执行工具调用
            result = await self.vllm.execute_tool_calls([tool_call])

            logger.bind(tag=TAG).info(
                f"工具调用完成: {tool_name}, result={result}"
            )

            # 特殊处理：高威胁时立即发出警告
            if tool_name == "report_package_status":
                threat_level = arguments.get("threat_level")
                if threat_level == "high":
                    # 立即播放警告语音
                    await self._play_threat_warning(device_id, threat_level)

        except Exception as e:
            logger.bind(tag=TAG).error(
                f"工具调用失败: {tool_name}, error={e}"
            )

async def _play_threat_warning(self, device_id: str, threat_level: str):
    """播放威胁警告

    Args:
        device_id: 设备ID
        threat_level: 威胁等级
    """
    if threat_level == "high":
        warning_text = "您的行为已被记录，请立即停止"
    else:
        warning_text = "请问有什么可以帮您？"

    logger.bind(tag=TAG).warning(
        f"播放威胁警告 - 设备: {device_id}, 等级: {threat_level}"
    )

    # TODO: 调用TTS服务播放语音
```

---

## 四、数据流程

### 4.1 完整流程图（文字描述）

```
访客到访
  ↓
PIR检测到人体
  ↓
拍摄访客照片
  ↓
人脸识别
  ↓
判断权限
  ├─ 有权限 → 播放欢迎词 → 结束
  └─ 无权限 → 启动统一模式对话
       ↓
     检查看护模式
       ├─ 未激活 → 仅对话模式
       └─ 已激活 → 加载基准图片
            ↓
          第一轮对话（传入访客照片+基准图片）
            ↓
          对话循环
            ├─ 等待访客语音
            ├─ ASR识别
            ├─ 调用VLLM统一分析
            │    ├─ 生成对话回复
            │    └─ 后台监控快递（基于行为触发）
            ├─ TTS播放回复
            ├─ 处理工具调用
            │    ├─ enable_package_guard
            │    ├─ disable_package_guard
            │    ├─ update_package_baseline
            │    └─ report_package_status（威胁≥medium）
            └─ 检查结束条件
                 ├─ 沉默30秒 → 结束
                 ├─ PIR无人体 → 结束
                 └─ 达到最大轮次 → 结束
                      ↓
                对话结束后处理
                  ├─ 步骤1: 检查快递状态（如果看护激活）
                  │    ├─ 重新拍照
                  │    ├─ 调用VLLM对比分析
                  │    └─ 返回纯JSON结果
                  ├─ 步骤2: 生成访客意图总结
                  │    ├─ 传入完整对话历史+访客照片
                  │    ├─ 调用VLLM生成总结
                  │    └─ 返回混合格式JSON
                  ├─ 步骤3: 保存访问记录
                  ├─ 步骤4: 发送App通知
                  └─ 步骤5: 清理会话
                       ↓
                     流程结束
```

### 4.2 关键时序

| 时间点 | 操作           | 图片传递          | Token消耗 |
| ------ | -------------- | ----------------- | --------- |
| T0     | 访客到达，拍照 | -                 | 0         |
| T1     | 第一轮对话     | 访客照片+基准图片 | ~14K      |
| T2-T10 | 后续对话       | 仅访客照片        | ~7K/轮    |
| T11    | 对话结束检查   | 基准图片+当前图片 | ~15K      |
| T12    | 生成意图总结   | 访客照片          | ~8K       |

**总Token消耗估算**：

- 10轮对话：14K + 9×7K + 15K + 8K = 100K tokens
- 相比分离模式增加：约10%（可接受）

---

## 五、工具函数配置

### 5.1 保留的工具函数

```python
# main/xiaozhi-server/core/providers/doorlock/doorlock_tools.py

TOOLS_SCHEMA = [
    {
        "name": "enable_package_guard",
        "description": "启用快递看护模式。当访客提到'快递放门口了'、'外卖在这'等信息时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "设备ID"},
                "reason": {"type": "string", "description": "启用原因"}
            },
            "required": ["device_id", "reason"]
        }
    },
    {
        "name": "disable_package_guard",
        "description": "关闭快递看护模式。当判断快递已被主人（is_owner=true）取走时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "设备ID"},
                "reason": {"type": "string", "description": "关闭原因"}
            },
            "required": ["device_id", "reason"]
        }
    },
    {
        "name": "update_package_baseline",
        "description": "更新看护基准图片。当访客说'我把快递放这了'时立即调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "设备ID"}
            },
            "required": ["device_id"]
        }
    },
    {
        "name": "report_package_status",
        "description": "报告快递状态和威胁等级。仅在检测到访客可疑行为（威胁等级≥medium）时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "设备ID"},
                "session_id": {"type": "string", "description": "会话ID"},
                "action": {
                    "type": "string",
                    "enum": ["taking", "searching", "damaging", "normal", "passing"],
                    "description": "行为类型"
                },
                "threat_level": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "威胁等级"
                },
                "description": {"type": "string", "description": "详细描述"}
            },
            "required": ["device_id", "session_id", "action", "threat_level", "description"]
        }
    }
]
```

### 5.2 移除的工具函数

```python
# 移除 report_visitor_intent
# 原因：改为对话结束后程序主动询问AI，返回格式化JSON
```

---

## 六、测试方案

### 6.1 单元测试

#### 测试用例1：提示词动态组合

```python
def test_build_unified_prompt():
    """测试提示词动态组合"""
    vllm = DoorlockVLLMProvider(config, logger)

    # 测试无基准图片
    prompt_no_baseline = vllm._build_unified_prompt(has_baseline=False)
    assert "看护任务" not in prompt_no_baseline
    assert "对话任务" in prompt_no_baseline

    # 测试有基准图片
    prompt_with_baseline = vllm._build_unified_prompt(has_baseline=True)
    assert "看护任务" in prompt_with_baseline
    assert "对话任务" in prompt_with_baseline
```

#### 测试用例2：图片传递逻辑

```python
async def test_image_passing():
    """测试图片传递逻辑"""
    vllm = DoorlockVLLMProvider(config, logger)

    # 第一轮：应传入2张图片
    result1 = await vllm.analyze_unified(
        visitor_image="img1",
        baseline_image="baseline",
        dialogue_history=[],
        is_first_round=True
    )
    # 验证传入了2张图片

    # 第二轮：应仅传入1张图片
    result2 = await vllm.analyze_unified(
        visitor_image="img1",
        baseline_image="baseline",
        dialogue_history=[{"role": "user", "content": "test"}],
        is_first_round=False
    )
    # 验证仅传入1张图片
```

### 6.2 集成测试

#### 测试场景1：仅对话模式

```python
async def test_dialogue_only_mode():
    """测试仅对话模式（看护未激活）"""
    # 1. 模拟访客到达
    # 2. 看护模式未激活
    # 3. 启动对话
    # 4. 验证：不传入基准图片
    # 5. 验证：对话正常进行
    # 6. 验证：对话结束后不检查快递
```

#### 测试场景2：统一模式（看护激活）

```python
async def test_unified_mode():
    """测试统一模式（看护激活）"""
    # 1. 启用看护模式
    # 2. 模拟访客到达
    # 3. 第一轮传入基准图片
    # 4. 后续轮次不传入基准图片
    # 5. 模拟访客可疑行为
    # 6. 验证：AI调用report_package_status
    # 7. 对话结束后检查快递状态
    # 8. 验证：返回格式化JSON
```

#### 测试场景3：高威胁打断对话

```python
async def test_high_threat_interrupt():
    """测试高威胁时打断对话"""
    # 1. 统一模式对话中
    # 2. AI检测到高威胁（有人偷快递）
    # 3. 验证：立即调用report_package_status
    # 4. 验证：播放警告语音
    # 5. 验证：对话可以继续或结束
```

### 6.3 性能测试

#### Token消耗测试

```python
async def test_token_consumption():
    """测试Token消耗"""
    # 模拟10轮对话
    # 记录每轮Token消耗
    # 验证：总消耗在预期范围内（<120K）
    # 验证：第一轮消耗最高（~14K）
    # 验证：后续轮次消耗稳定（~7K）
```

#### 响应时间测试

```python
async def test_response_time():
    """测试响应时间"""
    # 测试VLLM调用响应时间
    # 验证：<3秒（可接受）
    # 测试对话结束后处理时间
    # 验证：<10秒（可接受）
```

---

## 七、配置示例

### 7.1 门锁配置

```yaml
# config/doorlock_config.yaml

# 统一模式配置
unified_mode:
  enabled: true

  # 对话配置
  dialogue:
    max_rounds: 10
    timeout_seconds: 30

  # 看护配置
  guard:
    threat_detection: "behavior_based" # 基于行为触发
    report_threshold: "medium" # 威胁等级≥medium时报告

  # Token优化
  token_optimization:
    baseline_image_once: true # 仅第一轮传入基准图片
    reuse_context: true # 依赖AI上下文理解

# 性能配置
performance:
  vllm_limits:
    model_context_limit: 262144
    max_input_tokens: 260096
    max_output_tokens: 32768
    max_image_tokens: 16384
    tokens_per_image: 7000
```

### 7.2 提示词配置

```yaml
# config/doorlock_prompts.yaml

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

## 八、实施检查清单

### 8.1 代码修改

- [ ] VLLM提供者：添加`analyze_unified()`方法
- [ ] VLLM提供者：添加`final_package_check()`方法
- [ ] VLLM提供者：添加`generate_intent_summary()`方法
- [ ] VLLM提供者：添加`_build_unified_prompt()`方法
- [ ] 意图处理器：添加`start_unified_dialogue()`方法
- [ ] 意图处理器：添加`_post_dialogue_processing()`方法
- [ ] 意图处理器：添加`_handle_tool_calls()`方法
- [ ] 工具函数：移除`report_visitor_intent`工具

### 8.2 配置文件

- [ ] 添加`core_role_and_style`提示词
- [ ] 添加`dialogue_tasks`提示词
- [ ] 添加`guard_tasks`提示词
- [ ] 添加`tools_guide`提示词
- [ ] 添加`final_package_check_prompt`提示词
- [ ] 添加`intent_summary_prompt`提示词
- [ ] 更新`doorlock_config.yaml`配置

### 8.3 测试

- [ ] 单元测试：提示词动态组合
- [ ] 单元测试：图片传递逻辑
- [ ] 集成测试：仅对话模式
- [ ] 集成测试：统一模式
- [ ] 集成测试：高威胁打断
- [ ] 性能测试：Token消耗
- [ ] 性能测试：响应时间

### 8.4 文档

- [ ] 更新API文档
- [ ] 更新用户手册
- [ ] 编写迁移指南

---

## 九、风险和缓解措施

### 9.1 已识别风险

| 风险                 | 影响 | 概率 | 缓解措施                           |
| -------------------- | ---- | ---- | ---------------------------------- |
| AI混淆对话和监控任务 | 高   | 中   | 提示词明确优先级，充分测试         |
| Token消耗超预期      | 中   | 低   | 仅第一轮传基准图片，监控Token使用  |
| AI遗忘基准状态       | 中   | 中   | 依赖上下文理解，对话结束后补充检查 |
| 高威胁打断对话体验差 | 低   | 低   | 安全优先，可接受                   |
| JSON解析失败         | 中   | 低   | 添加异常处理，返回默认值           |

### 9.2 降级方案

如果统一模式出现问题，可以快速降级到分离模式：

```yaml
# config/doorlock_config.yaml
unified_mode:
  enabled: false # 关闭统一模式，回退到分离模式
```

---

## 十、总结

### 10.1 核心优势

1. **用户体验提升**：看护模式下仍可正常对话
2. **Token优化**：仅第一轮传基准图片，节省约30% Token
3. **架构优雅**：统一的处理流程，易于维护
4. **可控性强**：程序主动询问AI，返回格式化数据
5. **安全优先**：高威胁立即打断，实时+最终双重检查

### 10.2 关键创新

1. **三层动态提示词**：灵活组合，适应不同场景
2. **基于行为的威胁检测**：精准触发，减少噪音
3. **程序控制的结构化询问**：替代工具调用，更可控
4. **对话优先原则**：保证访客体验，监控在后台

### 10.3 下一步行动

1. 实施代码修改（预计2-3天）
2. 编写和运行测试（预计1-2天）
3. 小规模试运行（预计1周）
4. 收集反馈并优化（持续）

---

**文档版本**：v1.0  
**最后更新**：2024年（基于深度访谈结果）  
**状态**：待实施
