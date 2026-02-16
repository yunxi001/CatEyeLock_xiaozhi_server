# VLLM 意图识别实现机制分析

## 概述

本文档详细分析智能门锁 VLLM 意图识别模块的实现机制，包括照片处理、提示词、工具调用等核心功能。

---

## 1. 照片给 AI 的机制

### 1.1 支持多张照片

**✅ 是的，支持一次给多张照片！**

从代码实现来看：

```python
# core/providers/vllm/doorlock_vllm.py

def analyze_with_tools(
    self,
    question: str,
    images: List[str],  # ← 注意这里是列表！
    dialogue_history: List[Dict[str, str]],
    system_prompt: Optional[str] = None
) -> Dict[str, Any]:
```

**支持的场景**：

1. **单图片模式**（意图识别）：

   ```python
   await vllm.analyze_intent(
       visitor_image="base64_image",  # 1张访客照片
       dialogue_history=[...],
       system_prompt="..."
   )
   ```

2. **双图片模式**（看护监控）：
   ```python
   await vllm.analyze_package_status(
       current_image="base64_current",   # 当前图片
       baseline_image="base64_baseline", # 基准图片
       dialogue_history=[...],
       system_prompt="..."
   )
   ```

### 1.2 图片格式和编码

**格式要求**：

- 编码：Base64 字符串
- 原始格式：JPEG
- 传输方式：嵌入在 JSON 消息的 `image_url` 字段中

**代码实现**：

```python
# 构建消息时添加图片
content = [{"type": "text", "text": question}]

# 添加多张图片
for image_base64 in images:
    content.append({
        "type": "image_url",
        "image_url": {
            "url": f"data:image/jpeg;base64,{image_base64}"
        }
    })
```

### 1.3 图片顺序说明

在看护模式下，图片顺序很重要：

```python
# 看护监控分析
return self.analyze_with_tools(
    question="请对比当前图片和基准图片...",
    images=[baseline_image, current_image],  # 基准图片在前，当前图片在后
    dialogue_history=dialogue_history,
    system_prompt=system_prompt
)
```

**提示词中的说明**：

```
第一张图片是基准图片（之前的状态）
第二张图片是当前图片（现在的状态）
```

---

## 2. 时间戳机制

### 2.1 是否附加时间戳？

**❌ 照片本身不附加时间戳**

从代码来看，照片只是 Base64 编码的 JPEG 数据，没有额外的时间戳字段。

**但是**，系统在其他地方记录了时间信息：

1. **对话历史中的时间戳**：

   ```python
   # 每条消息都有时间戳
   {
       "role": "user",
       "content": "有快递",
       "timestamp": 1702234567890  # 毫秒时间戳
   }
   ```

2. **数据库记录中的时间戳**：

   ```python
   # PackageAlert 模型
   class PackageAlert:
       created_at: datetime  # 创建时间
       photo_path: str       # 照片路径（包含时间信息）
   ```

3. **会话管理器中的时间戳**：
   ```python
   # SessionManager 记录会话时间
   session = {
       "session_id": "...",
       "start_time": datetime.now(),
       "last_activity": datetime.now()
   }
   ```

### 2.2 时间信息的使用

虽然照片本身没有时间戳，但系统通过以下方式关联时间：

1. **对话上下文**：AI 可以从对话历史中推断时间顺序
2. **文件命名**：照片保存时使用时间戳命名
3. **数据库关联**：通过 session_id 关联时间信息

---

## 3. Token 限制和管理

### 3.1 图片 Token 消耗

**每张图片的 Token 估算**：

```python
# 从配置文件加载
self.tokens_per_image = int(vllm_limits.get("tokens_per_image", 7000))

# 估算图片Token
def _estimate_image_tokens(self, image_count: int) -> int:
    return image_count * self.tokens_per_image
```

**默认值**：

- 单张图片：约 7000 tokens（VGA 分辨率 640×480）
- 双张图片：约 14000 tokens

### 3.2 多层次 Token 限制

系统实现了三层 Token 限制：

```python
# 1. 模型上下文窗口限制
self.model_context_limit = 262144  # 总Token上限

# 2. 输入Token限制
self.max_input_tokens = 260096     # 输入Token上限

# 3. 输出Token限制
self.max_output_tokens = 32768     # 输出Token上限
self.max_tokens = 500              # 实际使用的输出限制

# 4. 图片Token限制
self.max_image_tokens = 16384      # 图片Token上限
```

### 3.3 对话历史自动截断

为了适应 Token 限制，系统会自动截断对话历史：

```python
def _truncate_dialogue_history(
    self,
    dialogue_history: List[Dict[str, str]],
    max_tokens: int
) -> List[Dict[str, str]]:
    """截断对话历史以满足Token限制

    保留最近的对话，从旧到新依次丢弃
    """
    # 从最新的对话开始累加
    truncated = []
    current_tokens = 0

    for msg in reversed(dialogue_history):
        content = msg.get("content", "")
        msg_tokens = self._estimate_tokens(content)

        if current_tokens + msg_tokens > max_tokens:
            break  # 超出限制，停止添加

        truncated.insert(0, msg)
        current_tokens += msg_tokens

    return truncated
```

**Token 分配策略**：

```python
# 计算各部分Token数
system_tokens = self._estimate_tokens(system_prompt)
question_tokens = self._estimate_tokens(question)
image_tokens = self._estimate_image_tokens(len(images))

# 固定部分Token数
fixed_tokens = system_tokens + question_tokens + image_tokens

# 对话历史可用Token数
available_for_history = min(
    self.max_input_tokens - fixed_tokens - self.max_tokens,  # 基于输入限制
    self.model_context_limit - fixed_tokens - self.max_tokens  # 基于总限制
)
```

---

## 4. 提示词机制

### 4.1 提示词加载

提示词从配置文件加载：

```python
# 配置文件路径
prompts_path = Path("config/doorlock_prompts.yaml")

# 加载提示词
with open(prompts_path, 'r', encoding='utf-8') as f:
    prompts = yaml.safe_load(f)

# 获取指定提示词
system_prompt = self.get_prompt("intent_recognition_prompt")
```

### 4.2 两种提示词

系统定义了两种核心提示词：

1. **意图识别提示词** (`intent_recognition_prompt`)：
   - 用于访客对话和意图分析
   - 包含对话策略、工具调用说明、示例场景
   - 长度：约 3000+ 字符

2. **看护模式提示词** (`package_guard_prompt`)：
   - 用于快递看护监控
   - 包含威胁等级判断标准、行为类型定义
   - 长度：约 4000+ 字符

### 4.3 提示词特点

**意图识别提示词的核心内容**：

```yaml
intent_recognition_prompt: |
  【系统角色】
  你是一个智能门锁的AI门卫助手

  【对话风格指南】
  - 礼貌正式，但不失亲和力
  - 根据访客身份调整语气
  - 使用简洁明了的语言

  【对话策略】
  - 主动引导对话，明确询问来访目的
  - 识别推销意图时礼貌但坚定地拒绝
  - 注意"快递"、"外卖"等关键词，启用看护模式

  【工具调用说明】
  你可以调用以下5个工具函数：
  1. enable_package_guard - 启用快递看护
  2. disable_package_guard - 关闭快递看护
  3. update_package_baseline - 更新基准图片
  4. report_package_status - 报告快递状态
  5. report_visitor_intent - 报告访客意图

  【示例对话场景】
  场景1 - 快递员送货：...
  场景2 - 朋友拜访：...
  场景3 - 推销人员：...
```

**看护模式提示词的核心内容**：

```yaml
package_guard_prompt: |
  【威胁等级判断标准】

  低威胁（low）：
  - 路人快速经过（停留<3秒）
  - 主人取走快递（is_owner=true）← 正常行为
  - 快递员正常送货

  中威胁（medium）：
  - 长时间停留（>10秒）
  - 翻看快递包装
  - 多次往返门口

  高威胁（high）：
  - 非主人拿走快递 ← 盗窃行为
  - 破坏、踢踹快递
  - 使用工具撬门

  【重要判断规则】
  1. 主人（is_owner=true）取走快递 = 低威胁
  2. 非主人取走快递 = 高威胁
```

---

## 5. 工具函数调用机制

### 5.1 工具函数定义

系统定义了 5 个工具函数，每个都有完整的 JSON Schema：

```python
TOOLS_SCHEMA = [
    {
        "name": "enable_package_guard",
        "description": "启用快递看护模式",
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string"},
                "reason": {"type": "string"}
            },
            "required": ["device_id", "reason"]
        }
    },
    # ... 其他4个工具
]
```

### 5.2 工具调用流程

```
1. VLLM 分析对话和图片
   ↓
2. 决定调用哪个工具函数
   ↓
3. 生成工具调用参数（JSON格式）
   ↓
4. 服务器执行工具函数
   ↓
5. 返回执行结果
   ↓
6. VLLM 根据结果继续对话
```

**代码实现**：

```python
# 调用VLLM
response = self.client.chat.completions.create(
    model=self.model_name,
    messages=messages,
    tools=tools,  # ← 传入工具Schema
    temperature=self.temperature,
    max_tokens=max_tokens
)

# 解析工具调用
if hasattr(message, 'tool_calls') and message.tool_calls:
    for tool_call in message.tool_calls:
        tool_calls.append({
            "id": tool_call.id,
            "name": tool_call.function.name,
            "arguments": json.loads(tool_call.function.arguments)
        })

# 执行工具调用
results = await self.execute_tool_calls(tool_calls)
```

---

## 6. 性能监控

### 6.1 Token 使用量监控

系统实现了多层次的 Token 监控：

```python
def _check_token_usage(self, token_usage: dict, response_time: float, tool_calls_count: int):
    """多层次检查Token使用情况"""

    # 1. 检查输出Token使用率（主要警告）
    if output_usage_ratio > self.max_token_usage_ratio:
        logger.warning(f"⚠️ 输出Token接近限制: {completion_tokens}/{self.max_tokens}")

    # 2. 检查输入Token使用率（次要警告）
    if input_usage_ratio > self.input_warning_ratio:
        logger.warning(f"⚠️ 输入Token较高: {prompt_tokens}/{self.max_input_tokens}")

    # 3. 检查总Token使用率（严重警告）
    if total_usage_ratio > self.total_warning_ratio:
        logger.warning(f"⚠️ 总Token接近上下文窗口: {total_tokens}/{self.model_context_limit}")

    # 4. 记录详细统计
    logger.info(
        f"VLLM调用统计 | 输入: {prompt_tokens} | 输出: {completion_tokens} | "
        f"总计: {total_tokens} | 响应时间: {response_time:.2f}s | 工具调用: {tool_calls_count}"
    )
```

### 6.2 响应时间监控

```python
start_time = time.time()

# 调用VLLM
response = self.client.chat.completions.create(...)

# 计算响应时间
response_time = time.time() - start_time

logger.info(f"响应时间: {response_time:.2f}s")
```

---

## 7. 关键发现总结

### ✅ 支持的功能

1. **多图片输入**：支持 1-2 张图片同时输入
2. **对话历史**：支持多轮对话上下文
3. **工具调用**：支持 5 个工具函数
4. **Token 管理**：自动截断对话历史以适应限制
5. **性能监控**：多层次 Token 和响应时间监控

### ❌ 不支持的功能

1. **照片时间戳**：照片本身不携带时间戳（但系统其他地方记录）
2. **超过 2 张图片**：当前实现最多支持 2 张图片

### 🔧 测试需要注意的点

1. **图片顺序**：看护模式下，基准图片在前，当前图片在后
2. **Token 限制**：单张图片约 7000 tokens，需要考虑对话历史长度
3. **工具调用**：测试时需要验证工具函数是否被正确调用
4. **提示词**：提示词很长（3000-4000字符），会占用大量 Token

---

**文档维护者**：Kiro AI Assistant  
**最后更新**：2026-02-15

---

## 8. 两种模式的对话流程详解

### 8.1 意图识别模式（单图片 + 多轮对话）

#### 流程概述

```
访客到访 → 拍照 → 人脸识别 → 判断权限 → 启动意图对话 → 生成总结 → 发送通知
```

#### 详细流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                     意图识别模式完整流程                          │
└─────────────────────────────────────────────────────────────────┘

1. 访客触发（PIR 检测到人体）
   │
   ├─→ ESP32 发送 event_report: {"type": "event_report", "event": "pir_trigger"}
   │
   └─→ 服务器收到事件

2. 拍摄访客照片
   │
   ├─→ 服务器调用 ESP32 MCP 工具：capture_image
   │
   ├─→ ESP32 拍照并返回 JPEG 数据（Base64）
   │
   └─→ 服务器收到照片：visitor_image

3. 人脸识别
   │
   ├─→ 调用人脸识别服务：recognize_face(visitor_image)
   │
   ├─→ 识别结果：
   │   ├─ known（已注册用户）→ 检查权限
   │   ├─ unknown（陌生人）→ 无权限
   │   └─ no_face/error → 无权限
   │
   └─→ 服务器下发 face_result 消息（无需 seq_id）

4. 判断权限
   │
   ├─→ 有权限：
   │   ├─ 下发 face_result: {"access": {"granted": true}}
   │   ├─ ESP32 自动开锁
   │   ├─ 播放欢迎词
   │   └─ 流程结束
   │
   └─→ 无权限：继续意图识别对话

5. 启动意图识别对话
   │
   ├─→ 创建会话：session_id = "session_xxx"
   │
   ├─→ 初始化对话历史：dialogue_history = []
   │
   ├─→ 播放主动问候：
   │   ├─ 陌生人："您好，请问您找谁？"
   │   └─ 已识别但无权限："您好，{name}，请问有什么可以帮您？"
   │
   └─→ 添加到对话历史：
       dialogue_history.append({
           "role": "assistant",
           "content": "您好，请问您找谁？"
       })

6. 对话循环（最多 10 轮）
   │
   ├─→ 等待访客回复（ASR 语音识别）
   │   │
   │   ├─→ 超时 30 秒无回复 → 结束对话
   │   │
   │   └─→ 收到访客回复：visitor_response
   │
   ├─→ 添加到对话历史：
   │   dialogue_history.append({
   │       "role": "user",
   │       "content": visitor_response
   │   })
   │
   ├─→ 调用 VLLM 进行意图识别：
   │   │
   │   │   vllm_result = await vllm.analyze_intent(
   │   │       visitor_image=visitor_image_base64,  # 访客照片（Base64）
   │   │       dialogue_history=dialogue_history,   # 对话历史
   │   │       system_prompt=intent_recognition_prompt  # 意图识别提示词
   │   │   )
   │   │
   │   └─→ VLLM 返回结果：
   │       {
   │           "content": "好的，能帮我把快递放在门口吗？",
   │           "tool_calls": [
   │               {
   │                   "name": "enable_package_guard",
   │                   "arguments": {
   │                       "device_id": "device001",
   │                       "reason": "有新快递需要看护"
   │                   }
   │               }
   │           ],
   │           "token_usage": {...},
   │           "response_time": 2.5
   │       }
   │
   ├─→ 处理 AI 回复：
   │   ├─ 添加到对话历史：
   │   │   dialogue_history.append({
   │   │       "role": "assistant",
   │   │       "content": "好的，能帮我把快递放在门口吗？"
   │   │   })
   │   │
   │   └─ 播放 AI 回复（TTS 语音合成）
   │
   ├─→ 执行工具调用（如果有）：
   │   │
   │   └─→ 调用 enable_package_guard(device_id, reason)
   │       ├─ 启用看护模式
   │       ├─ 开始定时拍照（每 30 秒）
   │       └─ 返回执行结果
   │
   └─→ 检查对话是否结束：
       ├─ 沉默超过 30 秒 → 结束
       ├─ PIR 无人体检测 → 结束
       ├─ 达到最大轮次（10 轮）→ 结束
       └─ 否则继续循环

7. 生成意图总结
   │
   ├─→ 调用 VLLM 生成总结（或使用规则提取）：
   │   │
   │   └─→ intent_summary = {
   │           "intent_type": "delivery",
   │           "purpose": "送快递",
   │           "important_notes": ["【留言】京东快递，手机"],
   │           "full_summary": "访客是快递员，送来京东快递（手机）"
   │       }
   │
   └─→ 或者 AI 主动调用工具：
       report_visitor_intent(
           device_id="device001",
           session_id="session_xxx",
           intent_type="delivery",
           summary="快递员送达包裹",
           important_notes=["【提醒】有新快递送达"]
       )

8. 保存到数据库
   │
   ├─→ 保存访客意图记录：visitor_intents 表
   │   ├─ session_id
   │   ├─ intent_type
   │   ├─ intent_summary
   │   └─ dialogue_history
   │
   └─→ 保存访问记录：visit_records 表
       ├─ person_id（如果识别到）
       ├─ visit_time
       └─ photo_path

9. 发送 App 通知
   │
   └─→ 推送通知到主人手机：
       {
           "type": "visitor_intent",
           "intent_type": "delivery",
           "summary": "快递员送达包裹",
           "important_notes": ["【提醒】有新快递送达"],
           "photo_url": "https://...",
           "timestamp": 1702234567890
       }

10. 清理会话
    │
    └─→ 删除会话数据，释放资源
```

#### 关键数据结构

**对话历史格式**：

```python
dialogue_history = [
    {
        "role": "assistant",
        "content": "您好，请问您找谁？"
    },
    {
        "role": "user",
        "content": "我是快递员，有个包裹"
    },
    {
        "role": "assistant",
        "content": "好的，能帮我把快递放在门口吗？"
    },
    {
        "role": "user",
        "content": "行，放这儿了"
    }
]
```

**VLLM 调用消息格式**：

```python
messages = [
    {
        "role": "system",
        "content": "【系统角色】你是一个智能门锁的AI门卫助手..."  # 提示词
    },
    {
        "role": "assistant",
        "content": "您好，请问您找谁？"
    },
    {
        "role": "user",
        "content": "我是快递员，有个包裹"
    },
    {
        "role": "assistant",
        "content": "好的，能帮我把快递放在门口吗？"
    },
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "行，放这儿了"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
        ]
    }
]
```

**注意**：图片只在最后一条用户消息中附加，不会在每条消息中重复发送。

---

### 8.2 看护监控模式（双图片 + 定时分析）

#### 流程概述

```
启用看护 → 拍摄基准图片 → 定时拍照 → 对比分析 → 判断威胁 → 语音警告/通知
```

#### 详细流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                     看护监控模式完整流程                          │
└─────────────────────────────────────────────────────────────────┘

1. 启用看护模式（两种触发方式）
   │
   ├─→ 方式1：意图对话中 AI 主动调用工具
   │   │
   │   └─→ enable_package_guard(device_id, reason)
   │       ├─ 访客提到"快递放门口了"
   │       ├─ 访客提到"外卖在这"
   │       └─ 访客提到"包裹送到了"
   │
   └─→ 方式2：用户在 App 中手动启用
       │
       └─→ App 发送 HTTP 请求到服务器

2. 拍摄基准图片
   │
   ├─→ 调用 ESP32 MCP 工具：capture_image
   │
   ├─→ ESP32 拍照并返回 JPEG 数据
   │
   ├─→ 保存基准图片：
   │   ├─ 路径：data/doorlock/baselines/{device_id}_baseline.jpg
   │   └─ Base64：baseline_image_base64
   │
   └─→ 记录基准图片时间戳：baseline_timestamp

3. 启动定时拍照任务
   │
   ├─→ 创建异步任务：asyncio.create_task(monitor_loop())
   │
   └─→ 定时器配置：
       ├─ 拍照间隔：30 秒（可配置）
       ├─ 最大监控时长：2 小时（可配置）
       └─ 超时自动关闭

4. 定时拍照循环
   │
   ├─→ 每 30 秒执行一次：
   │   │
   │   ├─→ 检查看护模式是否仍然激活
   │   │   ├─ 已关闭 → 退出循环
   │   │   └─ 仍激活 → 继续
   │   │
   │   ├─→ 拍摄当前图片：
   │   │   ├─ 调用 ESP32 MCP 工具：capture_image
   │   │   └─ 收到 JPEG 数据：current_image
   │   │
   │   └─→ 进入图片对比分析
   │
   └─→ 循环直到：
       ├─ 看护模式被关闭
       ├─ 超过最大监控时长
       └─ 发生错误

5. 图片对比分析（核心步骤）
   │
   ├─→ 准备数据：
   │   ├─ baseline_image_base64（基准图片）
   │   ├─ current_image_base64（当前图片）
   │   └─ dialogue_history（对话历史，可能为空）
   │
   ├─→ 调用 VLLM 进行对比分析：
   │   │
   │   │   vllm_result = await vllm.analyze_package_status(
   │   │       current_image=current_image_base64,    # 当前图片
   │   │       baseline_image=baseline_image_base64,  # 基准图片
   │   │       dialogue_history=dialogue_history,     # 对话历史
   │   │       system_prompt=package_guard_prompt     # 看护提示词
   │   │   )
   │   │
   │   └─→ VLLM 返回结果：
   │       {
   │           "content": "陌生人正在翻看快递包装，查看收件人信息",
   │           "tool_calls": [
   │               {
   │                   "name": "report_package_status",
   │                   "arguments": {
   │                       "device_id": "device001",
   │                       "session_id": "guard_session_xxx",
   │                       "action": "searching",
   │                       "threat_level": "medium",
   │                       "description": "陌生人翻看快递包装，查看收件人信息，行为可疑"
   │                   }
   │               }
   │           ],
   │           "token_usage": {...},
   │           "response_time": 3.2
   │       }
   │
   └─→ 注意：图片顺序很重要！
       messages = [
           {"role": "system", "content": "【看护任务说明】..."},
           {
               "role": "user",
               "content": [
                   {"type": "text", "text": "请对比当前图片和基准图片..."},
                   {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,{baseline}"}},  # 基准在前
                   {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,{current}"}}    # 当前在后
               ]
           }
       ]

6. 处理分析结果
   │
   ├─→ 提取 AI 的描述：
   │   content = "陌生人正在翻看快递包装..."
   │
   └─→ 执行工具调用：
       │
       └─→ report_package_status(
               device_id="device001",
               session_id="guard_session_xxx",
               action="searching",
               threat_level="medium",
               description="陌生人翻看快递包装，查看收件人信息，行为可疑"
           )

7. 判断威胁等级并采取行动
   │
   ├─→ 低威胁（low）：
   │   ├─ 路人快速经过
   │   ├─ 主人取走快递（is_owner=true）
   │   ├─ 快递员正常送货
   │   │
   │   └─→ 行动：
   │       ├─ 记录日志
   │       ├─ 不发送通知
   │       └─ 继续监控
   │
   ├─→ 中威胁（medium）：
   │   ├─ 长时间停留（>10秒）
   │   ├─ 翻看快递包装
   │   ├─ 多次往返门口
   │   │
   │   └─→ 行动：
   │       ├─ 记录日志
   │       ├─ 播放语音提示："请问有什么可以帮您？"
   │       ├─ 发送 App 通知（普通优先级）
   │       ├─ 保存当前照片
   │       └─ 继续监控
   │
   └─→ 高威胁（high）：
       ├─ 非主人拿走快递（盗窃）
       ├─ 破坏、踢踹快递
       ├─ 使用工具撬门
       │
       └─→ 行动：
           ├─ 记录日志
           ├─ 播放语音警告："您的行为已被记录，请立即停止"
           ├─ 发送 App 通知（高优先级，震动+声音）
           ├─ 保存当前照片
           ├─ 可选：触发报警
           └─ 继续监控

8. 保存警报记录
   │
   └─→ 保存到数据库：package_alerts 表
       {
           "device_id": "device001",
           "session_id": "guard_session_xxx",
           "threat_level": "medium",
           "action": "searching",
           "description": "陌生人翻看快递包装...",
           "photo_path": "data/doorlock/alerts/xxx.jpg",
           "voice_warning_sent": true,
           "notified": true,
           "created_at": "2026-02-15 14:30:00"
       }

9. 发送 App 通知
   │
   └─→ 推送通知到主人手机：
       {
           "type": "package_alert",
           "threat_level": "medium",
           "action": "searching",
           "description": "陌生人翻看快递包装，查看收件人信息",
           "photo_url": "https://...",
           "timestamp": 1702234567890,
           "priority": "high"  # 中威胁以上使用高优先级
       }

10. 特殊情况处理
    │
    ├─→ 主人取走快递（低威胁）：
    │   │
    │   └─→ AI 调用工具：
    │       disable_package_guard(
    │           device_id="device001",
    │           reason="主人已取走快递"
    │       )
    │       ├─ 关闭看护模式
    │       ├─ 停止定时拍照
    │       └─ 清理会话数据
    │
    ├─→ 门口物品增多（新快递送达）：
    │   │
    │   └─→ AI 调用工具：
    │       update_package_baseline(device_id="device001")
    │       ├─ 拍摄新的基准图片
    │       ├─ 更新 baseline_image
    │       └─ 继续监控
    │
    └─→ 超时或手动关闭：
        │
        └─→ 关闭看护模式
            ├─ 停止定时拍照任务
            ├─ 清理会话数据
            └─ 记录关闭日志

11. 循环回到步骤 4
    │
    └─→ 等待 30 秒后继续下一次拍照分析
```

#### 关键数据结构

**看护会话数据**：

```python
guard_session = {
    "session_id": "guard_session_xxx",
    "device_id": "device001",
    "baseline_image": "base64_string",
    "baseline_timestamp": 1702234567890,
    "start_time": datetime.now(),
    "last_check_time": datetime.now(),
    "alert_count": 0,
    "status": "active"  # active/paused/stopped
}
```

**VLLM 调用消息格式（看护模式）**：

```python
messages = [
    {
        "role": "system",
        "content": """
        【看护任务说明】
        你正在看护门口的快递/外卖...

        【威胁等级判断标准】
        低威胁（low）：路人快速经过、主人取走快递...
        中威胁（medium）：长时间停留、翻看快递...
        高威胁（high）：非主人拿走快递、破坏快递...
        """
    },
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": """
                请对比当前图片和基准图片，判断门口快递的状态变化和威胁等级。

                第一张图片是基准图片（之前的状态）
                第二张图片是当前图片（现在的状态）

                请调用 report_package_status 工具报告情况。
                """
            },
            {
                "type": "image_url",
                "image_url": {"url": "data:image/jpeg;base64,{baseline_image}"}  # 基准图片
            },
            {
                "type": "image_url",
                "image_url": {"url": "data:image/jpeg;base64,{current_image}"}   # 当前图片
            }
        ]
    }
]
```

---

### 8.3 两种模式的对比

| 特性           | 意图识别模式              | 看护监控模式                   |
| -------------- | ------------------------- | ------------------------------ |
| **触发方式**   | PIR 检测到人体            | 意图对话中启用或手动启用       |
| **图片数量**   | 1 张（访客照片）          | 2 张（基准 + 当前）            |
| **对话方式**   | 多轮交互对话              | 单次分析（无交互）             |
| **执行频率**   | 一次性                    | 定时循环（每 30 秒）           |
| **提示词**     | intent_recognition_prompt | package_guard_prompt           |
| **工具调用**   | 5 个工具都可能调用        | 主要调用 report_package_status |
| **Token 消耗** | 约 10000-15000 tokens/次  | 约 17000-20000 tokens/次       |
| **响应时间**   | 2-3 秒/轮                 | 3-5 秒/次                      |
| **持续时长**   | 几分钟（对话结束）        | 几小时（直到关闭）             |
| **主要目标**   | 识别访客意图              | 监控快递安全                   |

---

### 8.4 两种模式的切换

```
意图识别模式 ──────────────────────→ 看护监控模式
                AI 调用工具：
                enable_package_guard()

                触发条件：
                - 访客提到"快递放门口了"
                - 访客提到"外卖在这"
                - 访客提到"包裹送到了"


看护监控模式 ──────────────────────→ 意图识别模式
                AI 调用工具：
                disable_package_guard()

                触发条件：
                - 主人取走快递
                - 门口已无快递
                - 超时自动关闭
```

---

### 8.5 实际案例演示

#### 案例 1：快递员送货（两种模式结合）

```
1. PIR 检测到人体
   ↓
2. 拍照 → 人脸识别 → 陌生人
   ↓
3. 启动意图识别对话：
   AI: "您好，请问您找谁？"
   访客: "我是快递员，有个包裹"
   AI: "好的，能帮我把快递放在门口吗？"
   访客: "行，放这儿了"
   ↓
4. AI 调用工具：
   - enable_package_guard(reason="有新快递需要看护")
   - update_package_baseline()
   - report_visitor_intent(intent_type="delivery")
   ↓
5. 切换到看护监控模式：
   - 拍摄基准图片（门口有 1 个快递）
   - 启动定时拍照（每 30 秒）
   ↓
6. 定时监控循环：
   30秒后 → 拍照 → 对比分析 → 低威胁（无人）→ 继续
   60秒后 → 拍照 → 对比分析 → 低威胁（无人）→ 继续
   90秒后 → 拍照 → 对比分析 → 中威胁（有人翻看）→ 语音提示 + 通知
   120秒后 → 拍照 → 对比分析 → 低威胁（人已离开）→ 继续
   ...
   ↓
7. 主人回家取走快递：
   - 拍照 → 对比分析 → 识别到主人（is_owner=true）
   - AI 调用工具：disable_package_guard(reason="主人已取走快递")
   - 关闭看护模式
```

#### 案例 2：朋友拜访（仅意图识别）

```
1. PIR 检测到人体
   ↓
2. 拍照 → 人脸识别 → 已注册但无权限
   ↓
3. 启动意图识别对话：
   AI: "您好，李明，请问有什么可以帮您？"
   访客: "张哥在吗？"
   AI: "主人目前不在家，请问您有什么话要留给主人吗？"
   访客: "告诉他我明天下午3点再来"
   AI: "好的，我已记录。我会通知主人的。"
   ↓
4. AI 调用工具：
   - report_visitor_intent(
       intent_type="visit",
       summary="朋友李明来拜访，约定明天下午3点再来",
       important_notes=["【留言】明天下午3点再来拜访"]
     )
   ↓
5. 发送 App 通知
   ↓
6. 对话结束（不启用看护模式）
```

---

**文档维护者**：Kiro AI Assistant  
**最后更新**：2026-02-15
