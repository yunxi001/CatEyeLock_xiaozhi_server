# 门锁 VLLM 加载内容详细分析

## 📋 概述

门锁 VLLM (`DoorlockVLLMProvider`) 在初始化时加载以下内容：

1. **系统 VLLM 配置**（模型、API、参数）
2. **提示词配置**（意图识别、看护模式）
3. **工具函数 Schema**（5个工具函数）
4. **性能配置**（Token 警告阈值）

## 🔧 初始化流程

```python
DoorlockVLLMProvider.__init__(config, logger_instance)
  ├── 1. 加载系统 VLLM 配置（复用）
  ├── 2. 加载门锁业务配置（独立）
  ├── 3. 加载提示词配置
  ├── 4. 初始化 OpenAI 客户端
  └── 5. 工具函数延迟初始化（通过 set_doorlock_tools）
```

---

## 1️⃣ 系统 VLLM 配置（复用）

### 加载来源

- **配置文件**：`config.yaml` 或 manage-api
- **选择方式**：`selected_module.VLLM` 指定使用哪个 VLLM 配置

### 加载内容

```python
# 从系统配置提取
selected_vllm = config.get("selected_module", {}).get("VLLM", "")
# 例如：selected_vllm = "ChatGLMVLLM"

vllm_config = config.get("VLLM", {})[selected_vllm]

# 提取的配置项
self.model_name = vllm_config.get("model_name")        # 模型名称
self.api_key = vllm_config.get("api_key")              # API 密钥
self.base_url = vllm_config.get("base_url")            # API 地址
self.max_tokens = vllm_config.get("max_tokens", 500)   # 最大 Token 数
self.temperature = vllm_config.get("temperature", 0.7) # 温度参数
self.top_p = vllm_config.get("top_p", 1.0)             # 采样参数
```

### 配置示例

```yaml
# config.yaml
selected_module:
  VLLM: ChatGLMVLLM

VLLM:
  ChatGLMVLLM:
    type: openai
    model_name: glm-4v-flash
    api_key: sk-xxx
    base_url: https://open.bigmodel.cn/api/paas/v4/
    max_tokens: 500
    temperature: 0.7
    top_p: 1.0
```

### 日志输出

```
[INFO] 门锁VLLM提供者初始化完成: 复用系统配置 ChatGLMVLLM,
       model=glm-4v-flash, max_tokens=500, prompts_loaded=3
```

---

## 2️⃣ 提示词配置

### 加载来源

- **配置文件**：`config/doorlock_prompts.yaml`
- **加载方法**：`_load_prompts()`

### 加载内容

```python
self.prompts = {
    "intent_recognition_prompt": "意图识别提示词（约2000字）",
    "package_guard_prompt": "看护模式提示词（约3000字）",
    "welcome_templates": "欢迎词模板配置"
}
```

### 提示词详情

#### 2.1 意图识别提示词 (`intent_recognition_prompt`)

**长度**：约 2000 字

**核心内容**：

```yaml
intent_recognition_prompt: |
  【系统角色】
  你是一个智能门锁的AI门卫助手，负责管理门口的访客接待和安全监控。

  【职责说明】
  1. 识别访客身份并播放个性化欢迎词
  2. 与无权限访客进行礼貌的意图识别对话
  3. 看护门口的快递和外卖，防止被盗或破坏
  4. 记录所有访客信息并通知主人

  【对话风格指南】
  - 礼貌正式，但不失亲和力
  - 根据访客身份调整语气
  - 使用简洁明了的语言
  - 语气自然，像真人对话

  【对话策略】
  - 主动引导对话，明确询问来访目的
  - 对重要信息进行二次确认
  - 识别推销意图时礼貌但坚定地拒绝
  - 对话保持简洁，每次回复不超过2-3句话

  【工具调用说明】
  你可以调用以下5个工具函数：
  1. enable_package_guard(device_id, reason)
  2. disable_package_guard(device_id, reason)
  3. update_package_baseline(device_id)
  4. report_package_status(...)
  5. report_visitor_intent(...)

  【示例对话场景】
  场景1 - 快递员送货：...
  场景2 - 朋友拜访：...
  场景3 - 推销人员：...
```

**使用场景**：

- 访客意图识别对话
- 单图片分析（访客照片）
- 对话历史上下文

#### 2.2 看护模式提示词 (`package_guard_prompt`)

**长度**：约 3000 字

**核心内容**：

```yaml
package_guard_prompt: |
  【看护任务说明】
  你正在看护门口的快递/外卖。通过对比当前图片和基准图片，判断是否有异常行为。

  【威胁等级判断标准】

  低威胁（low）- 正常情况：
  - 路人快速经过（停留时间<3秒）
  - 主人取走快递（is_owner=true）
  - 物业、保洁等工作人员正常工作

  中威胁（medium）- 可疑行为：
  - 在门口长时间停留（>10秒）
  - 翻看快递包装，查看地址信息
  - 多次往返门口，行为可疑

  高威胁（high）- 危险行为：
  - 非主人拿走快递（盗窃行为）
  - 破坏、踢踹快递包裹
  - 使用工具撬门、撬锁

  【重要判断规则】
  1. 主人（is_owner=true）取走快递 = 低威胁（正常行为）
  2. 非主人取走快递 = 高威胁（盗窃行为）
  3. 综合考虑：人物身份、停留时间、行为动作、快递状态变化

  【行为类型定义】
  - taking: 拿走快递
  - searching: 翻找、查看快递信息
  - damaging: 破坏、踢踹快递
  - normal: 正常活动
  - passing: 路过

  【工具调用说明】
  1. report_package_status(...) - 每次拍照分析后必须调用
  2. update_package_baseline(...) - 门口物品增多时调用
  3. enable_package_guard(...) - 有新快递需要看护
  4. disable_package_guard(...) - 主人取走快递

  【示例场景分析】
  场景1 - 路人经过（低威胁）：...
  场景2 - 主人取走快递（低威胁）：...
  场景3 - 陌生人翻看快递（中威胁）：...
  场景4 - 陌生人拿走快递（高威胁）：...
  场景5 - 破坏快递（高威胁）：...
```

**使用场景**：

- 看护模式监控分析
- 双图片对比（基准图片 + 当前图片）
- 威胁等级判断

#### 2.3 欢迎词模板 (`welcome_templates`)

**内容**：5种风格的欢迎词模板

```yaml
welcome_templates:
  - name: "温馨家庭"
    morning: "早上好，{name}，新的一天开始了"
    afternoon: "下午好，{name}，欢迎回家"
    evening: "晚上好，{name}，辛苦了一天"
    night: "夜深了，{name}，注意休息"
    default: "欢迎回家，{name}"

  - name: "简洁风格"
    default: "欢迎回家，{name}"

  - name: "正式风格"
    morning: "早安，{name}先生/女士"
    # ...

  - name: "活泼风格"
    morning: "早呀{name}，今天也要加油哦"
    # ...

  - name: "温暖关怀"
    morning: "早上好{name}，吃早餐了吗"
    # ...
```

**使用场景**：

- 用户回家时播放个性化欢迎词
- 根据时段（早晨/下午/晚上/夜间）选择不同欢迎词

### 提示词获取方法

```python
# 获取意图识别提示词
intent_prompt = vllm_provider.get_prompt("intent_recognition_prompt")

# 获取看护模式提示词
guard_prompt = vllm_provider.get_prompt("package_guard_prompt")

# 获取欢迎词模板
welcome_templates = vllm_provider.get_prompt("welcome_templates")
```

---

## 3️⃣ 工具函数 Schema

### 加载来源

- **定义位置**：`core/providers/doorlock/doorlock_tools.py`
- **加载方法**：`DoorlockTools.get_tools_schema()`

### 工具函数清单

门锁 VLLM 支持 **5 个工具函数**：

| 工具名称                  | 功能描述               | 使用场景               |
| ------------------------- | ---------------------- | ---------------------- |
| `enable_package_guard`    | 启用快递看护模式       | 访客提到"快递放门口了" |
| `disable_package_guard`   | 关闭快递看护模式       | 主人取走快递           |
| `update_package_baseline` | 更新看护基准图片       | 发现门口有新快递送达   |
| `report_package_status`   | 报告快递状态和威胁等级 | 看护模式下每次拍照分析 |
| `report_visitor_intent`   | 报告访客意图           | 对话结束时生成总结     |

### 工具函数详细 Schema

#### 3.1 `enable_package_guard`

```json
{
  "name": "enable_package_guard",
  "description": "启用快递看护模式。当访客提到'快递放门口了'、'外卖在这'等信息时调用。",
  "parameters": {
    "type": "object",
    "properties": {
      "device_id": {
        "type": "string",
        "description": "设备ID"
      },
      "reason": {
        "type": "string",
        "description": "启用看护的原因，例如：'有新快递需要看护'"
      }
    },
    "required": ["device_id", "reason"]
  }
}
```

**调用示例**：

```python
await tools.enable_package_guard(
    device_id="device001",
    reason="快递员送达新包裹"
)
```

#### 3.2 `disable_package_guard`

```json
{
  "name": "disable_package_guard",
  "description": "关闭快递看护模式。当判断快递已被主人（is_owner=true）取走时调用。",
  "parameters": {
    "type": "object",
    "properties": {
      "device_id": {
        "type": "string",
        "description": "设备ID"
      },
      "reason": {
        "type": "string",
        "description": "关闭看护的原因，例如：'主人已取走快递'"
      }
    },
    "required": ["device_id", "reason"]
  }
}
```

#### 3.3 `update_package_baseline`

```json
{
  "name": "update_package_baseline",
  "description": "更新看护基准图片。当发现门口有新快递送达时调用。",
  "parameters": {
    "type": "object",
    "properties": {
      "device_id": {
        "type": "string",
        "description": "设备ID"
      }
    },
    "required": ["device_id"]
  }
}
```

#### 3.4 `report_package_status`

```json
{
  "name": "report_package_status",
  "description": "报告快递状态和威胁等级。在看护模式下，每次拍照分析后调用此函数报告情况。",
  "parameters": {
    "type": "object",
    "properties": {
      "device_id": { "type": "string", "description": "设备ID" },
      "session_id": { "type": "string", "description": "会话ID" },
      "action": {
        "type": "string",
        "enum": ["taking", "searching", "damaging", "normal", "passing"],
        "description": "行为类型：taking(拿走)、searching(翻找)、damaging(破坏)、normal(正常)、passing(路过)"
      },
      "threat_level": {
        "type": "string",
        "enum": ["low", "medium", "high"],
        "description": "威胁等级：low(低威胁)、medium(中威胁)、high(高威胁)"
      },
      "description": {
        "type": "string",
        "description": "详细描述你看到的情况，包括人物行为、快递状态等"
      }
    },
    "required": [
      "device_id",
      "session_id",
      "action",
      "threat_level",
      "description"
    ]
  }
}
```

**调用示例**：

```python
await tools.report_package_status(
    device_id="device001",
    session_id="session123",
    action="taking",
    threat_level="high",
    description="陌生人拿走快递包裹，疑似盗窃行为"
)
```

#### 3.5 `report_visitor_intent`

```json
{
  "name": "report_visitor_intent",
  "description": "报告访客意图。在对话结束时调用此函数，生成结构化总结。",
  "parameters": {
    "type": "object",
    "properties": {
      "device_id": { "type": "string", "description": "设备ID" },
      "session_id": { "type": "string", "description": "会话ID" },
      "intent_type": {
        "type": "string",
        "enum": ["delivery", "visit", "sales", "maintenance", "other"],
        "description": "意图类型：delivery(送快递/外卖)、visit(拜访)、sales(推销)、maintenance(维修/物业)、other(其他)"
      },
      "summary": {
        "type": "string",
        "description": "完整的对话总结，简洁明了地概括访客来访目的和关键信息"
      },
      "important_notes": {
        "type": "array",
        "items": { "type": "string" },
        "description": "重要信息列表，每条以【留言】或【提醒】开头"
      }
    },
    "required": [
      "device_id",
      "session_id",
      "intent_type",
      "summary",
      "important_notes"
    ]
  }
}
```

**调用示例**：

```python
await tools.report_visitor_intent(
    device_id="device001",
    session_id="session124",
    intent_type="visit",
    summary="朋友张三来拜访，主人不在家，约定明天下午3点再来",
    important_notes=[
        "【留言】明天下午3点再来拜访",
        "【提醒】带了礼物放在门口"
    ]
)
```

### 工具函数设置

```python
# 在 PackageGuardManager 初始化时设置
vllm_provider.set_doorlock_tools(doorlock_tools)

# 日志输出
[INFO] 门锁工具函数已设置
```

---

## 4️⃣ 性能配置

### 加载来源

- **配置文件**：`config/doorlock_config.yaml`
- **配置段**：`performance`

### 加载内容

```python
# 从门锁独立配置读取
doorlock_config = self._load_doorlock_config()
performance_config = doorlock_config.get("performance", {})

self.max_token_usage_ratio = float(
    performance_config.get("max_token_usage_ratio", 0.8)
)
```

### 配置示例

```yaml
# config/doorlock_config.yaml
performance:
  # Token使用量警告阈值（0.0-1.0）
  max_token_usage_ratio: 0.8
  # 会话清理延迟（秒）
  session_cleanup_delay: 0
```

### 使用场景

```python
# 在 analyze_with_tools 方法中检查 Token 使用量
usage_ratio = token_usage["total_tokens"] / self.max_tokens
if usage_ratio > self.max_token_usage_ratio:
    self.logger.warning(
        f"Token使用量已达 {token_usage['total_tokens']}/{self.max_tokens} "
        f"({usage_ratio:.1%})，接近上限"
    )
```

---

## 5️⃣ VLLM 调用流程

### 意图识别分析

```python
# 调用流程
result = await vllm_provider.analyze_intent(
    visitor_image="base64_image_data",
    dialogue_history=[
        {"role": "user", "content": "我是快递员"},
        {"role": "assistant", "content": "您好，请问有什么可以帮您？"}
    ],
    system_prompt=None  # 自动从配置加载
)

# 返回结果
{
    "content": "好的，您可以把快递放在门口，我会帮您看护。",
    "tool_calls": [
        {
            "id": "call_123",
            "name": "enable_package_guard",
            "arguments": {
                "device_id": "device001",
                "reason": "快递员送达新包裹"
            }
        }
    ],
    "token_usage": {
        "prompt_tokens": 1200,
        "completion_tokens": 50,
        "total_tokens": 1250
    },
    "response_time": 2.5
}
```

### 看护监控分析

```python
# 调用流程
result = await vllm_provider.analyze_package_status(
    current_image="base64_current_image",
    baseline_image="base64_baseline_image",
    dialogue_history=[],
    system_prompt=None  # 自动从配置加载
)

# 返回结果
{
    "content": "",
    "tool_calls": [
        {
            "id": "call_456",
            "name": "report_package_status",
            "arguments": {
                "device_id": "device001",
                "session_id": "session123",
                "action": "taking",
                "threat_level": "high",
                "description": "陌生人拿走快递包裹，疑似盗窃行为"
            }
        }
    ],
    "token_usage": {
        "prompt_tokens": 2500,
        "completion_tokens": 80,
        "total_tokens": 2580
    },
    "response_time": 3.2
}
```

### 工具调用执行

```python
# 执行工具调用
tool_results = await vllm_provider.execute_tool_calls(
    tool_calls=result["tool_calls"]
)

# 返回结果
[
    {
        "tool_call_id": "call_456",
        "tool_name": "report_package_status",
        "result": {
            "success": True,
            "message": "快递状态已记录: 陌生人拿走快递包裹，疑似盗窃行为",
            "alert_id": 123,
            "threat_level": "high"
        }
    }
]
```

---

## 6️⃣ 消息构建机制

### 消息结构

```python
messages = [
    # 1. 系统提示词
    {
        "role": "system",
        "content": "你是一个智能门锁的AI门卫助手..."
    },

    # 2. 对话历史
    {
        "role": "user",
        "content": "我是快递员"
    },
    {
        "role": "assistant",
        "content": "您好，请问有什么可以帮您？"
    },

    # 3. 当前问题 + 图片
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "请根据对话历史和访客照片，识别访客意图。"},
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
                }
            }
        ]
    }
]
```

### 多图片支持

```python
# 看护模式：双图片对比
content = [
    {"type": "text", "text": "请对比当前图片和基准图片..."},
    {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{baseline_image}"}
    },
    {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{current_image}"}
    }
]
```

---

## 7️⃣ Token 统计与监控

### Token 统计

```python
token_usage = {
    "prompt_tokens": 1200,      # 输入 Token 数
    "completion_tokens": 50,    # 输出 Token 数
    "total_tokens": 1250        # 总 Token 数
}
```

### 警告机制

```python
# 计算使用率
usage_ratio = token_usage["total_tokens"] / self.max_tokens

# 超过阈值时警告
if usage_ratio > self.max_token_usage_ratio:  # 默认 0.8
    logger.warning(
        f"Token使用量已达 {token_usage['total_tokens']}/{self.max_tokens} "
        f"({usage_ratio:.1%})，接近上限"
    )
```

### 日志输出

```
[INFO] VLLM调用统计 | 输入Token: 1200 | 输出Token: 50 |
       总Token: 1250 | 响应时间: 2.50s | 工具调用: 1
```

---

## 8️⃣ 加载内容总结

| 类别          | 内容                         | 来源                  | 数量/大小                |
| ------------- | ---------------------------- | --------------------- | ------------------------ |
| **VLLM 配置** | 模型名称、API 密钥、参数     | 系统配置（复用）      | 6 个配置项               |
| **提示词**    | 意图识别、看护模式、欢迎词   | doorlock_prompts.yaml | 3 个提示词（约 5000 字） |
| **工具函数**  | 看护控制、状态报告、意图总结 | doorlock_tools.py     | 5 个工具函数             |
| **性能配置**  | Token 警告阈值               | doorlock_config.yaml  | 1 个配置项               |

### 内存占用估算

- **VLLM 配置**：< 1 KB
- **提示词配置**：约 15 KB（3 个提示词）
- **工具函数 Schema**：约 5 KB（5 个工具）
- **OpenAI 客户端**：约 10 KB
- **总计**：约 31 KB

---

## 9️⃣ 使用示例

### 完整调用流程

```python
# 1. 初始化 VLLM 提供者（复用系统配置）
vllm_provider = DoorlockVLLMProvider(config, logger)

# 2. 设置工具函数
vllm_provider.set_doorlock_tools(doorlock_tools)

# 3. 意图识别分析
result = await vllm_provider.analyze_intent(
    visitor_image="base64_image",
    dialogue_history=[
        {"role": "user", "content": "我是快递员，有个包裹要送"}
    ]
)

# 4. 执行工具调用
if result["tool_calls"]:
    tool_results = await vllm_provider.execute_tool_calls(
        tool_calls=result["tool_calls"]
    )

# 5. 看护监控分析
guard_result = await vllm_provider.analyze_package_status(
    current_image="base64_current",
    baseline_image="base64_baseline",
    dialogue_history=[]
)
```

---

## 🔟 配置文件清单

### 必需的配置文件

1. **`config.yaml`** 或 **manage-api 配置**
   - 提供系统 VLLM 配置
   - 门锁复用此配置

2. **`config/doorlock_config.yaml`**
   - 门锁业务配置
   - 性能参数配置

3. **`config/doorlock_prompts.yaml`**
   - 意图识别提示词
   - 看护模式提示词
   - 欢迎词模板

### 配置文件关系

```
config.yaml（系统配置）
  └── VLLM.ChatGLMVLLM ──┐
                         ├─> DoorlockVLLMProvider（复用）
doorlock_config.yaml     │
  └── performance ───────┘

doorlock_prompts.yaml
  ├── intent_recognition_prompt ──> analyze_intent()
  ├── package_guard_prompt ──────> analyze_package_status()
  └── welcome_templates ─────────> 欢迎词播放
```

---

## 总结

门锁 VLLM 加载的内容包括：

1. ✅ **系统 VLLM 配置**（完全复用，不独立配置）
2. ✅ **3 个提示词**（意图识别、看护模式、欢迎词）
3. ✅ **5 个工具函数**（看护控制、状态报告、意图总结）
4. ✅ **性能配置**（Token 警告阈值）

所有配置在初始化时一次性加载，工具函数通过 `set_doorlock_tools()` 延迟设置。
