# 设计文档

## 1. 架构设计

### 1.1 系统架构概述

统一智能看护对话模式采用分层架构设计，将对话处理和看护监控统一到一个智能流程中：

```
┌─────────────────────────────────────────────────────────────┐
│                      访客到访事件                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              DoorlockIntentHandler（意图处理器）               │
│  - 人脸识别                                                    │
│  - 权限检查                                                    │
│  - 统一模式对话流程控制                                         │
│  - 对话结束后处理                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│            DoorlockVLLMProvider（VLLM提供者）                 │
│  - analyze_unified()：统一模式分析                             │
│  - final_package_check()：快递状态检查                         │
│  - generate_intent_summary()：意图总结生成                     │
│  - 动态提示词组合                                              │
│  - Token优化管理                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    DoorlockTools（工具函数）                   │
│  - enable_package_guard                                       │
│  - disable_package_guard                                      │
│  - update_package_baseline                                    │
│  - report_package_status                                      │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心设计原则

1. **对话优先**：访客对话是主任务，快递监控是后台任务
2. **Token优化**：仅第一轮传入基准图片，后续依赖AI上下文理解
3. **程序控制**：对话结束后由程序主动询问AI，返回格式化数据
4. **行为触发**：基于访客行为触发威胁检测，而非定时检查
5. **高威胁打断**：检测到高威胁时立即打断对话并发出警告

## 2. 模块设计

### 2.1 VLLM提供者扩展

#### 2.1.1 analyze_unified方法

**功能**：统一模式分析，同时处理对话和监控任务

**方法签名**：

```python
async def analyze_unified(
    self,
    visitor_image: str,
    baseline_image: Optional[str],
    dialogue_history: List[Dict[str, str]],
    is_first_round: bool = False
) -> Dict[str, Any]
```

**参数说明**：

- `visitor_image`：访客照片（Base64编码）
- `baseline_image`：基准图片（Base64编码，仅第一轮传入）
- `dialogue_history`：对话历史列表
- `is_first_round`：是否第一轮对话

**返回值**：

```python
{
    "content": "AI回复文本",
    "tool_calls": [工具调用列表],
    "token_usage": {
        "prompt_tokens": 输入Token数,
        "completion_tokens": 输出Token数,
        "total_tokens": 总Token数
    },
    "response_time": 响应时间（秒）
}
```

**核心逻辑**：

1. 构建图片列表（第一轮包含访客图片+基准图片，后续仅访客图片）
2. 检查图片Token限制
3. 动态组合提示词（根据是否有基准图片）
4. 调用VLLM进行分析
5. 解析AI回复和工具调用
6. 统计Token使用量并检查警告

#### 2.1.2 final_package_check方法

**功能**：对话结束后的快递状态最终检查

**方法签名**：

```python
async def final_package_check(
    self,
    current_image: str,
    baseline_image: str
) -> Dict[str, Any]
```

**参数说明**：

- `current_image`：当前图片（重新拍照，Base64编码）
- `baseline_image`：基准图片（Base64编码）

**返回值**：

```python
{
    "threat_level": "low|medium|high",
    "action": "taking|searching|damaging|normal|passing",
    "description": "详细描述"
}
```

**核心逻辑**：

1. 检查图片Token限制（2张图片）
2. 加载专用提示词（final_package_check_prompt）
3. 调用VLLM对比分析
4. 解析纯JSON格式结果
5. 异常处理：解析失败返回默认低威胁结果

#### 2.1.3 generate_intent_summary方法

**功能**：生成访客意图总结

**方法签名**：

```python
async def generate_intent_summary(
    self,
    visitor_image: str,
    dialogue_history: List[Dict[str, str]]
) -> Dict[str, Any]
```

**参数说明**：

- `visitor_image`：访客照片（Base64编码）
- `dialogue_history`：完整对话历史

**返回值**：

```python
{
    "intent_type": "delivery|visit|sales|maintenance|other",
    "summary": "简洁总结",
    "important_notes": ["【留言】...", "【提醒】..."],
    "ai_analysis": "详细分析"
}
```

**核心逻辑**：

1. 检查图片Token限制（1张图片）
2. 加载专用提示词（intent_summary_prompt）
3. 调用VLLM生成总结
4. 解析混合格式JSON结果
5. 异常处理：解析失败返回默认总结

#### 2.1.4 \_build_unified_prompt方法

**功能**：动态组合统一模式提示词

**方法签名**：

```python
def _build_unified_prompt(self, has_baseline: bool) -> str
```

**参数说明**：

- `has_baseline`：是否有基准图片（看护模式是否激活）

**返回值**：组合后的完整提示词字符串

**核心逻辑**：

```python
# 基础部分（总是包含）
prompt_parts = [
    self.get_prompt("core_role_and_style"),
    self.get_prompt("dialogue_tasks")
]

# 如果看护模式激活，添加看护任务
if has_baseline:
    prompt_parts.append(self.get_prompt("guard_tasks"))

# 总是添加工具指南
prompt_parts.append(self.get_prompt("tools_guide"))

return "\n\n".join(prompt_parts)
```

### 2.2 意图处理器改造

#### 2.2.1 start_unified_dialogue方法

**功能**：启动统一模式对话（支持看护）

**方法签名**：

```python
async def start_unified_dialogue(
    self,
    device_id: str,
    session_id: str,
    person_info: Optional[Dict[str, Any]],
    visitor_image: bytes,
    conn=None
) -> Dict[str, Any]
```

**核心流程**：

1. 检查看护模式是否激活
2. 如果激活，加载基准图片
3. 转换访客图片为Base64
4. 播放主动问候
5. 进入对话循环：
   - 检查对话结束条件
   - 等待访客回复
   - 调用VLLM统一分析
   - 播放AI回复
   - 处理工具调用
   - 高威胁时立即警告
6. 对话结束后处理

#### 2.2.2 \_post_dialogue_processing方法

**功能**：对话结束后的处理流程

**方法签名**：

```python
async def _post_dialogue_processing(
    self,
    device_id: str,
    session_id: str,
    visitor_image: bytes,
    baseline_image: Optional[bytes],
    dialogue_history: List[Dict[str, str]]
) -> Dict[str, Any]
```

**核心流程**：

1. **步骤1：检查快递状态**（如果看护激活）
   - 重新拍照
   - 调用VLLM检查快递状态
   - 如果检测到威胁，保存警报

2. **步骤2：生成访客意图总结**
   - 调用VLLM生成总结
   - 解析结构化结果

3. **步骤3：保存访问记录**
   - 保存到数据库

4. **步骤4：发送App通知**
   - 通知房主访客信息

5. **步骤5：清理会话**
   - 清理会话数据

#### 2.2.3 \_handle_tool_calls方法

**功能**：处理工具调用

**核心逻辑**：

1. 遍历工具调用列表
2. 补充必要参数（device_id, session_id）
3. 执行工具调用
4. 特殊处理：高威胁时立即播放警告语音

### 2.3 工具函数配置

#### 2.3.1 保留的工具函数

1. **enable_package_guard**
   - 功能：启用看护模式
   - 参数：device_id, reason
   - 触发时机：访客提到"快递放门口了"

2. **disable_package_guard**
   - 功能：关闭看护模式
   - 参数：device_id, reason
   - 触发时机：判断快递已被主人取走

3. **update_package_baseline**
   - 功能：更新基准图片
   - 参数：device_id
   - 触发时机：访客说"我把快递放这了"

4. **report_package_status**
   - 功能：报告快递状态和威胁
   - 参数：device_id, session_id, action, threat_level, description
   - 触发时机：检测到访客可疑行为（威胁等级≥medium）

#### 2.3.2 移除的工具函数

- **report_visitor_intent**：改为对话结束后程序主动询问AI

## 3. 数据流设计

### 3.1 统一模式对话流程

```
访客到访
  ↓
PIR检测 + 初次拍照
  ↓
人脸识别 + 权限检查
  ↓
[无权限] → 启动统一模式对话
  ↓
检查看护模式状态
  ├─ 未激活 → 仅对话模式
  └─ 已激活 → 加载基准图片
       ↓
     启动定时拍照任务（每5秒拍照并缓存）
       ↓
     播放主动问候
       ↓
     第一轮对话
       ├─ 等待访客语音回复（ASR识别）
       ├─ 传入：访客语音文本 + 最新缓存照片 + 基准图片
       ├─ 提示词：core + dialogue + guard + tools
       ├─ VLLM分析
       ├─ 播放AI回复（TTS）
       └─ Token消耗：~14K
       ↓
     后续对话（2-10轮）
       ├─ 等待访客语音回复（ASR识别）
       ├─ 传入：访客语音文本 + 最新缓存照片
       ├─ 提示词：core + dialogue + guard + tools
       ├─ VLLM分析
       ├─ 播放AI回复（TTS）
       └─ Token消耗：~7K/轮
       ↓
     对话结束（沉默30秒或PIR无人体）
       ↓
     停止定时拍照任务
       ↓
     对话结束后处理
       ├─ 步骤1：检查快递状态（如果看护激活）
       │   ├─ 使用最后一张缓存照片
       │   ├─ 对比分析（基准图片 + 最后照片）
       │   └─ 返回纯JSON：threat_level, action, description
       ├─ 步骤2：生成意图总结
       │   ├─ 传入：初次访客照片 + 完整对话历史
       │   └─ 返回混合JSON：intent_type, summary, important_notes, ai_analysis
       ├─ 步骤3：保存访问记录
       ├─ 步骤4：发送App通知
       ├─ 步骤5：清理会话
       └─ 步骤6：清理照片缓存
```

### 3.2 图片传递策略

#### 定时拍照机制

**拍照策略**：

- 对话开始后启动定时拍照任务（每5秒拍照一次）
- 照片缓存在内存中（最多保留最近10张）
- 每轮对话使用最新的缓存照片
- 对话结束后清理所有缓存照片

**优势**：

- 避免对话中等待拍照，提高响应速度
- 实时捕捉访客行为变化
- 对话结束时有最新照片用于最终检查

#### Token消耗策略

| 对话轮次     | 传入内容                               | Token消耗 | 说明             |
| ------------ | -------------------------------------- | --------- | ---------------- |
| 第1轮        | 访客语音文本 + 最新缓存照片 + 基准图片 | ~14K      | 建立基准状态     |
| 第2-10轮     | 访客语音文本 + 最新缓存照片            | ~7K/轮    | 依赖AI上下文理解 |
| 对话结束检查 | 基准图片 + 最后缓存照片                | ~15K      | 最终状态对比     |
| 意图总结     | 初次访客照片 + 完整对话历史            | ~8K       | 生成结构化总结   |

**Token优化效果**：

- 10轮对话总消耗：14K + 9×7K + 15K + 8K = 100K tokens
- 相比每轮都传基准图片节省：约30%
- 使用缓存照片避免对话中等待拍照

### 3.3 威胁检测流程

```
对话进行中
  ↓
AI分析访客行为（基于访客图片和对话）
  ↓
判断威胁等级
  ├─ low（低威胁）
  │   ├─ 路人经过
  │   ├─ 主人取快递
  │   └─ 不触发工具调用
  ├─ medium（中威胁）
  │   ├─ 翻看快递
  │   ├─ 长时间停留
  │   ├─ 调用 report_package_status
  │   └─ 继续对话
  └─ high（高威胁）
      ├─ 非主人拿走快递
      ├─ 破坏快递
      ├─ 调用 report_package_status
      ├─ 立即播放警告语音
      └─ 可以打断对话
```

### 3.4 对话结束后处理流程

```
对话结束
  ↓
[看护模式激活？]
  ├─ 是 → 步骤1：检查快递状态
  │        ├─ 重新拍照
  │        ├─ 调用 final_package_check()
  │        ├─ 传入：基准图片 + 当前图片
  │        ├─ 返回：纯JSON格式
  │        └─ 如果威胁≠low，保存警报
  └─ 否 → 跳过步骤1
       ↓
步骤2：生成意图总结
  ├─ 调用 generate_intent_summary()
  ├─ 传入：访客图片 + 完整对话历史
  └─ 返回：混合JSON格式
       ↓
步骤3：保存访问记录
  └─ 保存到数据库
       ↓
步骤4：发送App通知
  └─ 通知房主
       ↓
步骤5：清理会话
  └─ 清理会话数据
```

## 4. 接口设计

### 4.1 VLLM提供者接口

#### analyze_unified

```python
async def analyze_unified(
    self,
    visitor_image: str,              # 访客照片（Base64）
    baseline_image: Optional[str],   # 基准图片（Base64，可选）
    dialogue_history: List[Dict[str, str]],  # 对话历史
    is_first_round: bool = False     # 是否第一轮
) -> Dict[str, Any]:
    """统一模式分析

    Returns:
        {
            "content": str,           # AI回复文本
            "tool_calls": List[Dict], # 工具调用列表
            "token_usage": Dict,      # Token统计
            "response_time": float    # 响应时间（秒）
        }
    """
```

#### final_package_check

```python
async def final_package_check(
    self,
    current_image: str,    # 当前图片（Base64）
    baseline_image: str    # 基准图片（Base64）
) -> Dict[str, Any]:
    """对话结束后的快递状态检查

    Returns:
        {
            "threat_level": str,   # "low"|"medium"|"high"
            "action": str,         # "taking"|"searching"|"damaging"|"normal"|"passing"
            "description": str     # 详细描述
        }
    """
```

#### generate_intent_summary

```python
async def generate_intent_summary(
    self,
    visitor_image: str,                      # 访客照片（Base64）
    dialogue_history: List[Dict[str, str]]  # 完整对话历史
) -> Dict[str, Any]:
    """生成访客意图总结

    Returns:
        {
            "intent_type": str,        # "delivery"|"visit"|"sales"|"maintenance"|"other"
            "summary": str,            # 简洁总结
            "important_notes": List[str],  # 重要信息列表
            "ai_analysis": str         # 详细分析
        }
    """
```

### 4.2 意图处理器接口

#### start_unified_dialogue

```python
async def start_unified_dialogue(
    self,
    device_id: str,                    # 设备ID
    session_id: str,                   # 会话ID
    person_info: Optional[Dict[str, Any]],  # 人员信息
    visitor_image: bytes,              # 访客照片
    conn=None                          # 连接对象
) -> Dict[str, Any]:
    """启动统一模式对话

    Returns:
        {
            "success": bool,
            "action": str,              # "intent_recognized"
            "visit_id": int,
            "intent_summary": Dict,
            "dialogue_count": int
        }
    """
```

### 4.3 工具函数接口

#### enable_package_guard

```python
{
    "name": "enable_package_guard",
    "description": "启用快递看护模式",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string", "description": "设备ID"},
            "reason": {"type": "string", "description": "启用原因"}
        },
        "required": ["device_id", "reason"]
    }
}
```

#### disable_package_guard

```python
{
    "name": "disable_package_guard",
    "description": "关闭快递看护模式",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string", "description": "设备ID"},
            "reason": {"type": "string", "description": "关闭原因"}
        },
        "required": ["device_id", "reason"]
    }
}
```

#### update_package_baseline

```python
{
    "name": "update_package_baseline",
    "description": "更新看护基准图片",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string", "description": "设备ID"}
        },
        "required": ["device_id"]
    }
}
```

#### report_package_status

```python
{
    "name": "report_package_status",
    "description": "报告快递状态和威胁等级",
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
```

## 5. 提示词设计

### 5.1 三层动态组合结构

提示词采用三层结构，根据看护模式状态动态组合：

```yaml
# 第一层：核心角色和风格（共享，总是包含）
core_role_and_style: |
  【系统角色】
  你是一个智能门锁的AI门卫助手，负责管理门口的访客接待和安全监控。

  【对话风格指南】
  - 礼貌正式，但不失亲和力
  - 根据访客身份调整语气
  - 使用简洁明了的语言
  - 对话保持简洁，每次回复不超过2-3句话

# 第二层：对话任务说明（总是包含）
dialogue_tasks: |
  【对话任务】
  你的主要任务是与访客进行自然对话，了解来访目的。

  - 主动引导对话，明确询问来访目的
  - 对重要信息进行二次确认
  - 识别推销意图时礼貌但坚定地拒绝
  - 不要在对话中提及快递监控功能

# 第三层：看护任务说明（仅在看护模式激活时添加）
guard_tasks: |
  【看护任务】（后台任务，不影响对话）
  你同时负责监控门口快递的安全。

  **重要**：这是后台任务，不要在对话中提及监控功能。

  【监控要点】
  - 观察访客是否靠近、触碰、翻看快递
  - 判断访客行为是否可疑
  - 评估威胁等级（low/medium/high）

  【触发条件】
  仅在以下情况调用 report_package_status：
  - 访客靠近快递并触碰、翻看
  - 访客长时间停留在快递旁边（>10秒）
  - 访客试图拿走快递（非主人）
  - 访客破坏、踢踹快递

  【威胁等级判断】
  - low：路人经过、主人取快递
  - medium：翻看快递、长时间停留
  - high：非主人拿走快递、破坏快递

# 第四层：工具调用指南（总是包含）
tools_guide: |
  【工具调用说明】
  你可以调用以下4个工具函数：
  1. enable_package_guard
  2. disable_package_guard
  3. update_package_baseline
  4. report_package_status
```

### 5.2 动态组合逻辑

```python
def build_unified_prompt(has_baseline_image: bool) -> str:
    """动态组合提示词"""
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

### 5.3 对话结束后的专用提示词

#### final_package_check_prompt

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

#### intent_summary_prompt

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

```

```

## 6. 配置设计

### 6.1 门锁配置文件

```yaml
# config/doorlock_config.yaml

# 统一模式配置
unified_mode:
  enabled: true # 启用统一模式

  # 对话配置
  dialogue:
    max_rounds: 10 # 最大对话轮次
    timeout_seconds: 30 # 沉默超时时间（秒）

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
    model_context_limit: 262144 # 模型上下文窗口
    max_input_tokens: 260096 # 最大输入Token
    max_output_tokens: 32768 # 最大输出Token
    max_image_tokens: 16384 # 最大图片Token
    tokens_per_image: 7000 # 每张图片Token数
    input_warning_ratio: 0.8 # 输入Token警告阈值
    total_warning_ratio: 0.8 # 总Token警告阈值
```

### 6.2 提示词配置文件

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

### 6.3 配置加载逻辑

```python
# 加载门锁配置
doorlock_config = load_yaml("config/doorlock_config.yaml")

# 加载提示词配置
prompts = load_yaml("config/doorlock_prompts.yaml")

# 检查统一模式是否启用
unified_mode_enabled = doorlock_config.get("unified_mode", {}).get("enabled", False)

# 获取对话配置
max_rounds = doorlock_config.get("unified_mode", {}).get("dialogue", {}).get("max_rounds", 10)
timeout_seconds = doorlock_config.get("unified_mode", {}).get("dialogue", {}).get("timeout_seconds", 30)
```

## 7. 测试策略

### 7.1 单元测试

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

#### 测试用例3：Token限制检查

```python
def test_check_image_token_limit():
    """测试图片Token限制检查"""
    vllm = DoorlockVLLMProvider(config, logger)

    # 测试1张图片（应通过）
    assert vllm._check_image_token_limit(1) == True

    # 测试2张图片（应通过）
    assert vllm._check_image_token_limit(2) == True

    # 测试3张图片（应失败，超出限制）
    assert vllm._check_image_token_limit(3) == False
```

### 7.2 集成测试

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

### 7.3 性能测试

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

### 7.4 边界情况测试

#### 测试用例1：看护未激活时主人取快递

```python
async def test_owner_takes_package_without_guard():
    """测试看护未激活时主人取快递"""
    # 1. 看护模式未激活
    # 2. 主人到访
    # 3. 验证：正常开门，不启动对话
    # 4. 验证：不检查快递状态
```

#### 测试用例2：主人取快递但不关闭看护

```python
async def test_owner_takes_package_keep_guard():
    """测试主人取快递但不关闭看护"""
    # 1. 看护模式激活
    # 2. 主人到访并取走快递
    # 3. 验证：判定为低威胁
    # 4. 验证：看护模式保持激活（不自动关闭）
```

#### 测试用例3：JSON解析失败

```python
async def test_json_parse_failure():
    """测试JSON解析失败"""
    # 1. 模拟VLLM返回非JSON格式
    # 2. 验证：返回默认结果
    # 3. 验证：不抛出异常
    # 4. 验证：记录错误日志
```

#### 测试用例4：图片Token超限

```python
async def test_image_token_exceeded():
    """测试图片Token超限"""
    # 1. 尝试传入3张图片
    # 2. 验证：抛出ValueError异常
    # 3. 验证：记录错误日志
    # 4. 验证：不调用VLLM
```

## 8. 错误处理和降级策略

### 8.1 错误处理

#### VLLM调用失败

```python
try:
    result = await vllm.analyze_unified(...)
except Exception as e:
    logger.error(f"VLLM调用失败: {e}")
    # 返回默认响应
    return {
        "content": "抱歉，我暂时无法理解，请稍后再试",
        "tool_calls": [],
        "token_usage": {},
        "response_time": 0
    }
```

#### JSON解析失败

```python
try:
    result = json.loads(content)
except json.JSONDecodeError as e:
    logger.error(f"JSON解析失败: {e}")
    # 返回默认结果
    return {
        "threat_level": "low",
        "action": "normal",
        "description": "无法解析检查结果"
    }
```

#### 图片Token超限

```python
if not self._check_image_token_limit(image_count):
    error_msg = f"图片Token超出限制: {image_count}张图片"
    logger.error(error_msg)
    raise ValueError(error_msg)
```

#### 工具调用执行失败

```python
try:
    result = await self.doorlock_tools.call_tool(tool_name, arguments)
except Exception as e:
    logger.error(f"工具调用执行异常: {tool_name}, error={e}")
    # 记录错误但继续对话
    result = {
        "success": False,
        "message": f"工具调用异常: {str(e)}"
    }
```

### 8.2 降级策略

#### 降级方案1：关闭统一模式

```yaml
# config/doorlock_config.yaml
unified_mode:
  enabled: false # 关闭统一模式，回退到分离模式
```

**效果**：

- 对话和看护分离处理
- 看护模式下无法进行对话
- 系统稳定性提高

#### 降级方案2：禁用看护功能

```yaml
# config/doorlock_config.yaml
unified_mode:
  enabled: true
  guard:
    enabled: false # 禁用看护功能，仅保留对话
```

**效果**：

- 仅进行意图识别对话
- 不进行快递监控
- Token消耗降低

#### 降级方案3：减少对话轮次

```yaml
# config/doorlock_config.yaml
unified_mode:
  enabled: true
  dialogue:
    max_rounds: 5 # 从10轮减少到5轮
```

**效果**：

- 对话时间缩短
- Token消耗降低
- 可能影响意图识别准确性

## 9. 性能优化

### 9.1 Token优化

#### 优化策略1：仅第一轮传入基准图片

**效果**：

- 节省约30% Token消耗
- 10轮对话从140K降低到100K

**实现**：

```python
if is_first_round and baseline_image:
    images = [visitor_image, baseline_image]
else:
    images = [visitor_image]
```

#### 优化策略2：对话历史截断

**效果**：

- 防止对话历史过长导致Token超限
- 保留最近的对话内容

**实现**：

```python
def _truncate_dialogue_history(
    dialogue_history: List[Dict],
    max_tokens: int
) -> List[Dict]:
    """从最新的对话开始累加，超出限制则停止"""
    truncated = []
    current_tokens = 0

    for msg in reversed(dialogue_history):
        msg_tokens = estimate_tokens(msg["content"])
        if current_tokens + msg_tokens > max_tokens:
            break
        truncated.insert(0, msg)
        current_tokens += msg_tokens

    return truncated
```

#### 优化策略3：提示词精简

**效果**：

- 减少系统提示词长度
- 为对话历史留出更多空间

**实现**：

- 移除冗余说明
- 使用简洁的表达
- 合并相似的指导内容

### 9.2 响应时间优化

#### 优化策略1：异步并发处理

```python
# 对话结束后的并发处理
async def _post_dialogue_processing(...):
    # 并发执行快递检查和意图总结
    tasks = []

    if baseline_image:
        tasks.append(vllm.final_package_check(...))

    tasks.append(vllm.generate_intent_summary(...))

    results = await asyncio.gather(*tasks, return_exceptions=True)
```

#### 优化策略2：缓存提示词

```python
class DoorlockVLLMProvider:
    def __init__(self, ...):
        # 启动时加载并缓存提示词
        self.prompts = self._load_prompts()
        self._prompt_cache = {}

    def _build_unified_prompt(self, has_baseline: bool) -> str:
        cache_key = f"unified_{has_baseline}"
        if cache_key not in self._prompt_cache:
            self._prompt_cache[cache_key] = self._do_build_prompt(has_baseline)
        return self._prompt_cache[cache_key]
```

### 9.3 内存优化

#### 优化策略1：及时清理会话数据

```python
async def cleanup_session(session_id: str):
    """对话结束后立即清理会话数据"""
    # 清理对话历史
    session_manager.clear_dialogue(session_id)

    # 清理图片缓存
    session_manager.clear_images(session_id)

    # 清理会话状态
    session_manager.remove_session(session_id)
```

#### 优化策略2：图片压缩

```python
def compress_image(image_bytes: bytes, max_size: int = 1024) -> bytes:
    """压缩图片以减少Token消耗"""
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(image_bytes))

    # 调整尺寸
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = tuple(int(dim * ratio) for dim in img.size)
        img = img.resize(new_size, Image.LANCZOS)

    # 保存为JPEG
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=85)
    return output.getvalue()
```

## 10. 安全性设计

### 10.1 数据安全

#### 图片数据处理

```python
# 图片数据仅在内存中处理，不持久化到磁盘
visitor_image_base64 = base64.b64encode(visitor_image).decode()

# 对话结束后立即清理图片数据
await session_manager.clear_images(session_id)
```

#### 敏感信息保护

```python
# 日志中不记录完整的图片数据
logger.info(f"拍照成功 - 大小: {len(jpeg_data)} bytes")  # ✓
# logger.info(f"图片数据: {jpeg_data}")  # ✗ 禁止

# 日志中不记录完整的对话内容（仅记录摘要）
logger.info(f"对话轮次: {dialogue_count}")  # ✓
# logger.info(f"对话内容: {dialogue_history}")  # ✗ 禁止
```

### 10.2 权限控制

#### 访问权限检查

```python
async def _check_access_permission(person_id: int) -> bool:
    """检查开门权限"""
    # 查询数据库获取权限信息
    person = await db.get_person(person_id)

    # 检查权限状态
    if not person or not person.has_permission:
        return False

    # 检查权限有效期
    if person.permission_expired:
        return False

    return True
```

#### 工具调用权限

```python
# 工具函数仅允许AI调用，不对外暴露
ALLOWED_TOOLS = [
    "enable_package_guard",
    "disable_package_guard",
    "update_package_baseline",
    "report_package_status"
]

async def call_tool(tool_name: str, arguments: dict):
    """执行工具调用（带权限检查）"""
    if tool_name not in ALLOWED_TOOLS:
        raise ValueError(f"不允许的工具调用: {tool_name}")

    # 执行工具函数
    ...
```

### 10.3 异常处理

#### 防御性编程

```python
# 所有外部调用都要try-catch
try:
    result = await vllm.analyze_unified(...)
except Exception as e:
    logger.error(f"VLLM调用失败: {e}")
    # 返回安全的默认值
    return default_response

# 所有JSON解析都要try-catch
try:
    data = json.loads(content)
except json.JSONDecodeError as e:
    logger.error(f"JSON解析失败: {e}")
    # 返回安全的默认值
    return default_data
```

#### 超时保护

```python
# 设置VLLM调用超时
try:
    result = await asyncio.wait_for(
        vllm.analyze_unified(...),
        timeout=30.0  # 30秒超时
    )
except asyncio.TimeoutError:
    logger.error("VLLM调用超时")
    return default_response
```

## 11. 监控和日志

### 11.1 关键指标监控

#### Token使用量监控

```python
def _check_token_usage(token_usage: dict, response_time: float, tool_calls_count: int):
    """多层次Token使用量监控"""
    prompt_tokens = token_usage["prompt_tokens"]
    completion_tokens = token_usage["completion_tokens"]
    total_tokens = token_usage["total_tokens"]

    # 计算使用率
    output_usage_ratio = completion_tokens / self.max_tokens
    input_usage_ratio = prompt_tokens / self.max_input_tokens
    total_usage_ratio = total_tokens / self.model_context_limit

    # 输出Token警告
    if output_usage_ratio > 0.8:
        logger.warning(f"⚠️ 输出Token接近限制: {completion_tokens}/{self.max_tokens}")

    # 输入Token警告
    if input_usage_ratio > 0.8:
        logger.warning(f"⚠️ 输入Token较高: {prompt_tokens}/{self.max_input_tokens}")

    # 总Token警告
    if total_usage_ratio > 0.8:
        logger.warning(f"⚠️ 总Token接近上限: {total_tokens}/{self.model_context_limit}")

    # 记录详细统计
    logger.info(
        f"VLLM调用统计 | "
        f"输入: {prompt_tokens} | "
        f"输出: {completion_tokens} | "
        f"总计: {total_tokens} | "
        f"响应时间: {response_time:.2f}s | "
        f"工具调用: {tool_calls_count}"
    )
```

#### 响应时间监控

```python
import time

start_time = time.time()
result = await vllm.analyze_unified(...)
response_time = time.time() - start_time

# 记录响应时间
logger.info(f"VLLM响应时间: {response_time:.2f}s")

# 响应时间警告
if response_time > 5.0:
    logger.warning(f"⚠️ VLLM响应时间过长: {response_time:.2f}s")
```

### 11.2 日志规范

#### 日志级别使用

```python
# DEBUG：调试信息
logger.bind(tag=TAG).debug("执行统一模式分析")

# INFO：正常流程信息
logger.bind(tag=TAG).info(f"对话结束 - 会话: {session_id}, 轮次: {dialogue_count}")

# WARNING：警告信息（不影响功能但需要关注）
logger.bind(tag=TAG).warning(f"Token使用量已达 {usage_ratio:.1%}，接近上限")

# ERROR：错误信息（功能异常）
logger.bind(tag=TAG).error(f"VLLM调用失败: {e}")
```

#### 日志格式规范

```python
# 统一使用TAG标识模块
TAG = "DoorlockVLLM"
logger.bind(tag=TAG).info("消息内容")

# 关键信息使用结构化日志
logger.bind(tag=TAG).info(
    f"统一模式对话完成 - "
    f"设备: {device_id}, "
    f"会话: {session_id}, "
    f"轮次: {dialogue_count}, "
    f"意图: {intent_type}"
)

# 异常日志包含堆栈信息
try:
    ...
except Exception as e:
    logger.bind(tag=TAG).error(f"处理异常: {e}")
    import traceback
    logger.bind(tag=TAG).error(traceback.format_exc())
```

### 11.3 性能指标

#### 关键性能指标（KPI）

| 指标                  | 目标值 | 监控方式     |
| --------------------- | ------ | ------------ |
| VLLM响应时间          | <3秒   | 每次调用记录 |
| 对话结束后处理时间    | <10秒  | 每次处理记录 |
| Token消耗（10轮对话） | <120K  | 累计统计     |
| 第一轮Token消耗       | ~14K   | 单次记录     |
| 后续轮次Token消耗     | ~7K    | 单次记录     |
| 对话结束检查Token     | ~15K   | 单次记录     |
| 意图总结Token         | ~8K    | 单次记录     |

#### 性能数据收集

```python
class PerformanceMetrics:
    """性能指标收集器"""

    def __init__(self):
        self.vllm_response_times = []
        self.token_consumptions = []
        self.dialogue_counts = []

    def record_vllm_call(self, response_time: float, token_usage: dict):
        """记录VLLM调用"""
        self.vllm_response_times.append(response_time)
        self.token_consumptions.append(token_usage["total_tokens"])

    def get_statistics(self) -> dict:
        """获取统计数据"""
        import statistics

        return {
            "avg_response_time": statistics.mean(self.vllm_response_times),
            "max_response_time": max(self.vllm_response_times),
            "avg_token_consumption": statistics.mean(self.token_consumptions),
            "max_token_consumption": max(self.token_consumptions),
            "total_calls": len(self.vllm_response_times)
        }
```

## 12. 实施计划

### 12.1 开发阶段

#### 阶段1：VLLM提供者扩展（2天）

**任务清单**：

- [ ] 实现 `analyze_unified()` 方法
- [ ] 实现 `final_package_check()` 方法
- [ ] 实现 `generate_intent_summary()` 方法
- [ ] 实现 `_build_unified_prompt()` 方法
- [ ] 添加图片Token限制检查
- [ ] 添加对话历史截断逻辑
- [ ] 编写单元测试

#### 阶段2：意图处理器改造（2天）

**任务清单**：

- [ ] 实现 `start_unified_dialogue()` 方法
- [ ] 实现 `_post_dialogue_processing()` 方法
- [ ] 实现 `_handle_tool_calls()` 方法
- [ ] 实现 `_play_threat_warning()` 方法
- [ ] 集成看护管理器
- [ ] 编写单元测试

#### 阶段3：配置和提示词（1天）

**任务清单**：

- [ ] 创建 `doorlock_config.yaml` 配置文件
- [ ] 更新 `doorlock_prompts.yaml` 提示词
- [ ] 添加 `core_role_and_style` 提示词
- [ ] 添加 `dialogue_tasks` 提示词
- [ ] 添加 `guard_tasks` 提示词
- [ ] 添加 `tools_guide` 提示词
- [ ] 添加 `final_package_check_prompt` 提示词
- [ ] 添加 `intent_summary_prompt` 提示词

#### 阶段4：工具函数调整（1天）

**任务清单**：

- [ ] 更新工具函数Schema
- [ ] 移除 `report_visitor_intent` 工具
- [ ] 验证4个保留工具的功能
- [ ] 编写工具函数测试

### 12.2 测试阶段（2天）

**任务清单**：

- [ ] 单元测试：提示词动态组合
- [ ] 单元测试：图片传递逻辑
- [ ] 单元测试：Token限制检查
- [ ] 集成测试：仅对话模式
- [ ] 集成测试：统一模式
- [ ] 集成测试：高威胁打断
- [ ] 性能测试：Token消耗
- [ ] 性能测试：响应时间
- [ ] 边界情况测试

### 12.3 部署阶段（1天）

**任务清单**：

- [ ] 代码审查
- [ ] 更新API文档
- [ ] 更新用户手册
- [ ] 编写迁移指南
- [ ] 小规模试运行
- [ ] 收集反馈
- [ ] 正式部署

### 12.4 总时间估算

- 开发阶段：6天
- 测试阶段：2天
- 部署阶段：1天
- **总计：9个工作日**

## 13. 风险评估

### 13.1 技术风险

| 风险                 | 影响 | 概率 | 缓解措施                           |
| -------------------- | ---- | ---- | ---------------------------------- |
| AI混淆对话和监控任务 | 高   | 中   | 提示词明确优先级，充分测试         |
| Token消耗超预期      | 中   | 低   | 仅第一轮传基准图片，监控Token使用  |
| AI遗忘基准状态       | 中   | 中   | 依赖上下文理解，对话结束后补充检查 |
| 高威胁打断对话体验差 | 低   | 低   | 安全优先，可接受                   |
| JSON解析失败         | 中   | 低   | 添加异常处理，返回默认值           |
| VLLM响应时间过长     | 中   | 中   | 设置超时保护，优化提示词           |
| 图片Token超限        | 高   | 低   | 严格检查图片数量，压缩图片         |

### 13.2 业务风险

| 风险             | 影响 | 概率 | 缓解措施                     |
| ---------------- | ---- | ---- | ---------------------------- |
| 用户不适应新模式 | 中   | 低   | 提供配置开关，支持降级       |
| 误报威胁过多     | 中   | 中   | 调整威胁等级阈值，优化提示词 |
| 漏报真实威胁     | 高   | 低   | 对话结束后补充检查，双重保障 |
| 对话体验下降     | 中   | 低   | 充分测试，收集用户反馈       |

### 13.3 运维风险

| 风险                 | 影响 | 概率 | 缓解措施               |
| -------------------- | ---- | ---- | ---------------------- |
| 配置错误导致功能异常 | 高   | 中   | 配置验证，提供默认值   |
| 日志过多占用存储     | 中   | 中   | 日志分级，定期清理     |
| 性能监控不足         | 中   | 低   | 完善监控指标，定期分析 |

## 14. 总结

### 14.1 核心优势

1. **用户体验提升**：看护模式下仍可正常对话，无缝体验
2. **Token优化**：仅第一轮传基准图片，节省约30% Token
3. **架构优雅**：统一的处理流程，易于维护
4. **可控性强**：程序主动询问AI，返回格式化数据
5. **安全优先**：高威胁立即打断，实时+最终双重检查

### 14.2 关键创新

1. **三层动态提示词**：灵活组合，适应不同场景
2. **基于行为的威胁检测**：精准触发，减少噪音
3. **程序控制的结构化询问**：替代工具调用，更可控
4. **对话优先原则**：保证访客体验，监控在后台

### 14.3 技术亮点

1. **异步并发处理**：提高响应速度
2. **Token智能管理**：多层次监控和优化
3. **防御性编程**：完善的异常处理和降级策略
4. **性能监控**：关键指标实时监控

### 14.4 后续优化方向

1. **AI模型优化**：训练专用模型，提高准确性
2. **提示词优化**：根据实际使用情况持续优化
3. **性能优化**：进一步降低Token消耗和响应时间
4. **功能扩展**：支持更多场景和工具函数

---

**文档版本**：v1.0  
**最后更新**：2024年  
**状态**：设计完成，待实施
