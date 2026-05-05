# Dialogue 类详细说明

## 概述

`Dialogue` 类是 xiaozhi-server 中用于管理 LLM 对话历史的核心组件，位于 `core/utils/dialogue.py`。它负责存储、组织和增强对话上下文，为 LLM 提供完整的对话历史和上下文信息。

---

## 一、类结构

### 1.1 Message 类（消息对象）

```python
class Message:
    def __init__(
        self,
        role: str,              # 角色：system/user/assistant/tool
        content: str = None,    # 消息内容
        uniq_id: str = None,    # 唯一标识符
        tool_calls=None,        # 工具调用信息
        tool_call_id=None,      # 工具调用 ID
    ):
        self.uniq_id = uniq_id if uniq_id is not None else str(uuid.uuid4())
        self.role = role
        self.content = content
        self.tool_calls = tool_calls
        self.tool_call_id = tool_call_id
```

**字段说明：**

| 字段           | 类型 | 说明         | 示例                                          |
| -------------- | ---- | ------------ | --------------------------------------------- |
| `role`         | str  | 消息角色     | `"system"`, `"user"`, `"assistant"`, `"tool"` |
| `content`      | str  | 消息内容     | `"你好"`, `"我是小智"`                        |
| `uniq_id`      | str  | 唯一标识符   | `"a1b2c3d4-..."`                              |
| `tool_calls`   | dict | 工具调用信息 | `[{"id": "call_1", "function": {...}}]`       |
| `tool_call_id` | str  | 工具调用 ID  | `"call_1"`                                    |

**角色类型：**

- **system**：系统提示词（定义 AI 的行为和能力）
- **user**：用户输入（语音识别结果或文本输入）
- **assistant**：AI 回复（LLM 生成的回答）
- **tool**：工具执行结果（插件函数的返回值）

### 1.2 Dialogue 类（对话管理器）

```python
class Dialogue:
    def __init__(self):
        self.dialogue: List[Message] = []  # 消息列表
        self.current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 创建时间
```

**核心属性：**

- `dialogue`：存储所有 `Message` 对象的列表
- `current_time`：对话创建时间

---

## 二、核心方法

### 2.1 put() - 添加消息

```python
def put(self, message: Message):
    """添加一条消息到对话历史"""
    self.dialogue.append(message)
```

**使用示例：**

```python
# 添加用户消息
conn.dialogue.put(Message(role="user", content="今天天气怎么样？"))

# 添加助手回复
conn.dialogue.put(Message(role="assistant", content="今天天气晴朗，温度 25 度"))

# 添加工具调用结果
conn.dialogue.put(Message(role="tool", content="温度: 25°C, 湿度: 60%"))
```

### 2.2 update_system_message() - 更新系统提示词

```python
def update_system_message(self, new_content: str):
    """更新或添加系统消息"""
    system_msg = next((msg for msg in self.dialogue if msg.role == "system"), None)
    if system_msg:
        system_msg.content = new_content  # 更新已有的系统消息
    else:
        self.put(Message(role="system", content=new_content))  # 添加新的系统消息
```

**使用场景：**

- 初始化系统提示词
- 动态更新 AI 能力（如添加 Home Assistant 设备列表）
- 切换 AI 角色或行为

**使用示例：**

```python
# 初始化系统提示词
conn.dialogue.update_system_message("你是一个智能助手，名叫小智")

# 动态添加设备信息
new_prompt = conn.prompt + "\n可控制设备：客厅灯、卧室空调"
conn.dialogue.update_system_message(new_prompt)
```

### 2.3 get_llm_dialogue() - 获取基础对话

```python
def get_llm_dialogue(self) -> List[Dict[str, str]]:
    """获取 LLM 格式的对话历史（不包含记忆和说话人信息）"""
    return self.get_llm_dialogue_with_memory(None, None)
```

**返回格式：**

```python
[
    {"role": "system", "content": "你是一个智能助手"},
    {"role": "user", "content": "今天天气怎么样？"},
    {"role": "assistant", "content": "今天天气晴朗"}
]
```

### 2.4 get_llm_dialogue_with_memory() - 获取增强对话

```python
def get_llm_dialogue_with_memory(
    self,
    memory_str: str = None,           # 长期记忆
    voiceprint_config: dict = None    # 声纹配置
) -> List[Dict[str, str]]:
    """获取增强的对话历史（包含记忆、说话人信息、时间等）"""
```

**这是最重要的方法**，它会对对话历史进行以下增强：

#### 增强 1：时间占位符替换

```python
# 替换 {{current_time}} 为当前时间
enhanced_system_prompt = enhanced_system_prompt.replace(
    "{{current_time}}",
    datetime.now().strftime("%H:%M")
)
```

**示例：**

```
原始提示词：现在时间是 {{current_time}}
增强后：现在时间是 14:30
```

#### 增强 2：添加说话人信息

```python
# 从声纹配置中提取说话人信息
speakers = voiceprint_config.get("speakers", [])
if speakers:
    enhanced_system_prompt += "\n\n<speakers_info>"
    for speaker_str in speakers:
        parts = speaker_str.split(",", 2)
        name = parts[1].strip()
        description = parts[2].strip() if len(parts) >= 3 else ""
        enhanced_system_prompt += f"\n- {name}：{description}"
    enhanced_system_prompt += "\n\n</speakers_info>"
```

**示例：**

```
<speakers_info>
- 张三：家庭主人，喜欢听音乐
- 李四：张三的妻子，喜欢看新闻
</speakers_info>
```

**作用：** LLM 可以根据说话人身份提供个性化回复

#### 增强 3：注入长期记忆

```python
# 使用正则表达式替换 <memory> 标签内容
if memory_str is not None:
    enhanced_system_prompt = re.sub(
        r"<memory>.*?</memory>",
        f"<memory>\n{memory_str}\n</memory>",
        enhanced_system_prompt,
        flags=re.DOTALL,
    )
```

**示例：**

```
原始提示词：
你是小智。<memory></memory>

增强后：
你是小智。<memory>
- 用户喜欢听周杰伦的歌
- 用户每天早上 7 点起床
- 用户家里有 3 个智能灯
</memory>
```

**作用：** 提供跨会话的长期记忆，让 AI 记住用户偏好

#### 增强 4：处理工具调用

```python
def getMessages(self, m, dialogue):
    if m.tool_calls is not None:
        # 工具调用消息
        dialogue.append({"role": m.role, "tool_calls": m.tool_calls})
    elif m.role == "tool":
        # 工具执行结果
        dialogue.append({
            "role": m.role,
            "tool_call_id": m.tool_call_id,
            "content": m.content,
        })
    else:
        # 普通消息
        dialogue.append({"role": m.role, "content": m.content})
```

**示例：**

```python
# 工具调用消息
{
    "role": "assistant",
    "tool_calls": [
        {
            "id": "call_1",
            "function": {
                "name": "get_weather",
                "arguments": "{\"city\": \"北京\"}"
            }
        }
    ]
}

# 工具执行结果
{
    "role": "tool",
    "tool_call_id": "call_1",
    "content": "北京今天晴，温度 25°C"
}
```

---

## 三、完整的对话流程示例

### 3.1 初始化对话

```python
# 创建连接时初始化 Dialogue
conn.dialogue = Dialogue()

# 设置系统提示词
system_prompt = """你是小智，一个智能助手。
现在时间是 {{current_time}}。
<memory></memory>
"""
conn.dialogue.update_system_message(system_prompt)
```

### 3.2 用户提问

```python
# 用户说："今天天气怎么样？"
user_text = "今天天气怎么样？"
conn.dialogue.put(Message(role="user", content=user_text))
```

### 3.3 LLM 决定调用工具

```python
# LLM 返回工具调用
tool_calls = [
    {
        "id": "call_1",
        "function": {
            "name": "get_weather",
            "arguments": "{\"city\": \"北京\"}"
        }
    }
]
conn.dialogue.put(Message(role="assistant", tool_calls=tool_calls))
```

### 3.4 执行工具并返回结果

```python
# 执行 get_weather 函数
weather_result = "北京今天晴，温度 25°C，湿度 60%"
conn.dialogue.put(Message(
    role="tool",
    tool_call_id="call_1",
    content=weather_result
))
```

### 3.5 LLM 生成最终回复

```python
# 再次调用 LLM，传入完整对话历史
memory_str = "用户喜欢简洁的回答"
voiceprint_config = {
    "speakers": ["1,张三,家庭主人"]
}

dialogue = conn.dialogue.get_llm_dialogue_with_memory(
    memory_str,
    voiceprint_config
)

# dialogue 内容：
[
    {
        "role": "system",
        "content": """你是小智，一个智能助手。
现在时间是 14:30。
<memory>
用户喜欢简洁的回答
</memory>

<speakers_info>
- 张三：家庭主人
</speakers_info>
"""
    },
    {"role": "user", "content": "今天天气怎么样？"},
    {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_1",
                "function": {
                    "name": "get_weather",
                    "arguments": "{\"city\": \"北京\"}"
                }
            }
        ]
    },
    {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "北京今天晴，温度 25°C，湿度 60%"
    }
]

# LLM 生成回复
response = llm.response(session_id, dialogue)
# 输出："张三，北京今天晴，温度 25 度。"

# 保存回复到对话历史
conn.dialogue.put(Message(role="assistant", content=response))
```

---

## 四、Dialogue 类的核心作用

### 4.1 对话上下文管理

**作用：** 保存完整的对话历史，让 LLM 理解上下文

**示例：**

```
用户："今天天气怎么样？"
AI："北京今天晴，温度 25 度"

用户："那明天呢？"  ← LLM 需要知道"那"指的是天气
AI："明天多云，温度 22 度"
```

### 4.2 长期记忆注入

**作用：** 跨会话保留用户偏好和历史信息

**示例：**

```
第一次对话：
用户："我喜欢听周杰伦的歌"
AI："好的，我记住了"

第二次对话（新会话）：
用户："放首歌"
AI："为你播放周杰伦的《晴天》"  ← 从记忆中获取偏好
```

### 4.3 说话人识别

**作用：** 根据声纹识别提供个性化服务

**示例：**

```
张三（家庭主人）："打开灯"
AI："好的，已为您打开客厅灯"

李四（访客）："打开灯"
AI："抱歉，您没有权限控制设备"
```

### 4.4 工具调用管理

**作用：** 记录工具调用和结果，支持多轮工具调用

**示例：**

```
用户："北京和上海哪个城市今天更热？"

AI 调用工具 1：get_weather("北京") → "25°C"
AI 调用工具 2：get_weather("上海") → "28°C"

AI 回复："上海今天更热，温度 28 度，比北京高 3 度"
```

### 4.5 时间感知

**作用：** 让 AI 知道当前时间，提供时间相关的服务

**示例：**

```
早上 7:00：
用户："现在几点了？"
AI："现在是早上 7 点，该起床了"

晚上 22:00：
用户："现在几点了？"
AI："现在是晚上 10 点，该休息了"
```

---

## 五、与 VLLM 的对比

| 特性           | LLM Dialogue                     | VLLM（文档方案）     |
| -------------- | -------------------------------- | -------------------- |
| **数据结构**   | `Dialogue` 对象 + `Message` 对象 | 简单的字典列表       |
| **长期记忆**   | ✅ 支持（从数据库/Redis 加载）   | ❌ 不支持            |
| **说话人识别** | ✅ 支持（声纹配置）              | ❌ 不支持            |
| **工具调用**   | ✅ 支持（tool_calls）            | ❌ 不支持            |
| **时间感知**   | ✅ 支持（{{current_time}}）      | ❌ 不支持            |
| **存储位置**   | Redis/数据库（持久化）           | 连接对象内存（临时） |
| **生命周期**   | 跨会话（session_id）             | 仅当前连接（5 分钟） |
| **复杂度**     | 高（功能完整）                   | 低（简单够用）       |

---

## 六、使用建议

### 6.1 何时使用 Dialogue 类

- ✅ 需要多轮对话上下文
- ✅ 需要长期记忆
- ✅ 需要说话人识别
- ✅ 需要工具调用
- ✅ 需要跨会话保留信息

### 6.2 何时使用简单字典列表

- ✅ 只需要短期上下文（如 VLLM 视觉对话）
- ✅ 不需要持久化
- ✅ 不需要复杂功能
- ✅ 追求简单和性能

---

## 七、代码位置

| 组件        | 文件路径                                | 说明               |
| ----------- | --------------------------------------- | ------------------ |
| Dialogue 类 | `core/utils/dialogue.py`                | 对话管理器定义     |
| 使用示例    | `core/connection.py`                    | 连接处理器中的使用 |
| LLM 调用    | `core/connection.py` (chat 方法)        | 传递对话历史给 LLM |
| 记忆保存    | `core/connection.py` (\_save_and_close) | 保存对话到数据库   |
| 工具调用    | `core/handle/intentHandler.py`          | 处理工具调用结果   |

---

**文档维护者：** Kiro AI Assistant  
**最后更新：** 2026-02-08
