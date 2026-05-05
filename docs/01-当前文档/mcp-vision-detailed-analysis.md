# MCP Vision 拍照识物功能详细分析

## 概述

MCP Vision 是通过 MCP (Model Context Protocol) 协议实现的服务器主动调用 ESP32 拍照的功能。整个流程涉及 WebSocket 命令下发、HTTP 图片上传、VLLM 视觉分析三个核心环节。

---

## 问题 1：服务器端 HTTP 接口详细分析

### 1.1 接口基本信息

**是的，这个 HTTP 接口就是把图片和问题发送给视觉大语言模型（VLLM）的。**

```
端点：POST /mcp/vision/explain
端口：8003
协议：HTTP
格式：multipart/form-data
认证：Bearer Token
```

### 1.2 完整请求流程

#### 步骤 1：ESP32 发起 HTTP POST 请求

```http
POST /mcp/vision/explain HTTP/1.1
Host: 服务器IP:8003
Authorization: Bearer <token>
Device-Id: <设备ID>
Client-Id: <客户端ID>
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="question"

你看到了什么？
------WebKitFormBoundary
Content-Disposition: form-data; name="image"; filename="capture.jpg"
Content-Type: image/jpeg

<二进制图片数据>
------WebKitFormBoundary--
```

**字段说明：**

- `question`: 文本问题（如"你看到了什么"、"描述这张图片"）
- `image`: 图片文件（JPEG/PNG/GIF/BMP/TIFF/WEBP，最大 5MB）

#### 步骤 2：服务器验证和解析

```python
# 1. 验证 Bearer Token
is_valid, token_device_id = self._verify_auth_token(request)
if not is_valid:
    return 401 错误

# 2. 验证设备 ID 匹配
device_id = request.headers.get("Device-Id", "")
if device_id != token_device_id:
    raise ValueError("设备ID与token不匹配")

# 3. 解析 multipart/form-data
reader = await request.multipart()

# 读取问题字段
question_field = await reader.next()
question = await question_field.text()

# 读取图片文件
image_field = await reader.next()
image_data = await image_field.read()

# 4. 验证图片
if len(image_data) > MAX_FILE_SIZE:  # 5MB
    raise ValueError("图片大小超过限制")

if not is_valid_image_file(image_data):
    raise ValueError("不支持的文件格式")

# 5. 转换为 base64
image_base64 = base64.b64encode(image_data).decode("utf-8")
```

#### 步骤 3：调用 VLLM 进行视觉分析

```python
# 1. 获取 VLLM 配置
select_vllm_module = config["selected_module"].get("VLLM")  # 如 "ChatGLMVLLM"
vllm_type = config["VLLM"][select_vllm_module]["type"]

# 2. 创建 VLLM 实例
vllm = create_instance(vllm_type, config["VLLM"][select_vllm_module])

# 3. 调用 VLLM 的 response 方法
result = vllm.response(question, image_base64)
```

#### 步骤 4：VLLM 调用视觉大模型 API

以 OpenAI 兼容接口为例（如智谱 ChatGLM）：

```python
def response(self, question, base64_image):
    question = question + "(请使用中文回复)"

    # 构建消息
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    },
                },
            ],
        }
    ]

    # 调用 OpenAI API
    response = self.client.chat.completions.create(
        model=self.model_name,  # 如 "glm-4v-plus"
        messages=messages,
        stream=False
    )

    return response.choices[0].message.content
```

**实际 API 请求示例（发送给智谱 AI）：**

```json
POST https://open.bigmodel.cn/api/paas/v4/chat/completions
Authorization: Bearer <智谱API密钥>
Content-Type: application/json

{
  "model": "glm-4v-plus",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "你看到了什么？(请使用中文回复)"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA..."
          }
        }
      ]
    }
  ],
  "stream": false
}
```

#### 步骤 5：返回结果给 ESP32

```python
# 构建响应
return_json = {
    "success": True,
    "action": "RESPONSE",  # 表示直接返回结果，不需要二次 LLM 处理
    "response": result     # VLLM 的分析结果
}

response = web.Response(
    text=json.dumps(return_json),
    content_type="application/json"
)
```

**响应示例：**

```json
{
  "success": true,
  "action": "RESPONSE",
  "response": "我看到一个红色的苹果放在木桌上，旁边有一本打开的书。"
}
```

### 1.3 数据流图

```
ESP32 拍照
    ↓ (JPEG 二进制)
HTTP POST /mcp/vision/explain
    ↓
VisionHandler 接收
    ↓
验证 Token + 设备 ID
    ↓
解析 multipart/form-data
    ↓ (question + image_data)
转换为 base64
    ↓
创建 VLLM 实例
    ↓
调用 vllm.response(question, image_base64)
    ↓
构建 OpenAI 格式消息
    ↓ (HTTP POST)
智谱 AI / OpenAI API
    ↓
视觉大模型分析
    ↓ (JSON 响应)
提取分析结果
    ↓
返回给 ESP32
    ↓
ESP32 通过 TTS 播放
```

### 1.4 关键代码位置

| 组件          | 文件路径                        | 说明                                  |
| ------------- | ------------------------------- | ------------------------------------- |
| HTTP 服务器   | `core/http_server.py`           | 注册 `/mcp/vision/explain` 路由       |
| Vision 处理器 | `core/api/vision_handler.py`    | 处理图片上传和 VLLM 调用              |
| VLLM 基类     | `core/providers/vllm/base.py`   | 定义 `response(question, image)` 接口 |
| OpenAI VLLM   | `core/providers/vllm/openai.py` | 实现 OpenAI 兼容的视觉模型调用        |

---

## 问题 2：ESP32 端 MCP 工具调用格式详细分析

### 2.1 MCP 协议概述

MCP (Model Context Protocol) 是一个标准化的工具调用协议，基于 JSON-RPC 2.0 规范。

**核心概念：**

- **工具注册**：ESP32 启动时向服务器注册可用工具（如 `capture_image`）
- **工具调用**：服务器通过 WebSocket 发送 `tools/call` 请求
- **结果返回**：ESP32 执行工具后返回结果

### 2.2 完整调用流程

#### 阶段 1：MCP 初始化（ESP32 连接时）

**服务器 → ESP32：发送初始化消息**

```json
{
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {
        "roots": { "listChanged": true },
        "sampling": {},
        "vision": {
          "url": "http://服务器IP:8003/mcp/vision/explain",
          "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        }
      },
      "clientInfo": {
        "name": "XiaozhiClient",
        "version": "1.0.0"
      }
    }
  }
}
```

**关键字段说明：**

- `vision.url`: 告诉 ESP32 图片上传的 HTTP 接口地址
- `vision.token`: 用于 HTTP 请求认证的 Bearer Token

**ESP32 → 服务器：返回初始化响应**

```json
{
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "serverInfo": {
        "name": "ESP32-MCP-Server",
        "version": "1.0.0"
      }
    }
  }
}
```

#### 阶段 2：工具列表获取

**服务器 → ESP32：请求工具列表**

```json
{
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
  }
}
```

**ESP32 → 服务器：返回工具列表**

```json
{
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "id": 2,
    "result": {
      "tools": [
        {
          "name": "capture_image",
          "description": "拍摄一张照片并分析图片内容。参数question用于指定要问的问题，如'你看到了什么'",
          "inputSchema": {
            "type": "object",
            "properties": {
              "question": {
                "type": "string",
                "description": "要问的问题，例如：你看到了什么？描述这张图片"
              }
            },
            "required": ["question"]
          }
        },
        {
          "name": "get_device_status",
          "description": "获取设备当前状态信息",
          "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
          }
        }
      ]
    }
  }
}
```

**工具定义说明：**

| 字段          | 说明                         | 示例                    |
| ------------- | ---------------------------- | ----------------------- |
| `name`        | 工具名称（唯一标识）         | `capture_image`         |
| `description` | 工具功能描述（供 LLM 理解）  | "拍摄一张照片并分析..." |
| `inputSchema` | 参数定义（JSON Schema 格式） | 见下文                  |

**inputSchema 结构：**

```json
{
  "type": "object",
  "properties": {
    "question": {
      "type": "string",
      "description": "要问的问题"
    }
  },
  "required": ["question"]
}
```

#### 阶段 3：LLM 调用工具（用户说"请打开摄像头"）

**用户语音 → LLM 识别意图 → 决定调用 `capture_image` 工具**

LLM 生成的 Function Call：

```json
{
  "name": "capture_image",
  "arguments": "{\"question\":\"你看到了什么？\"}"
}
```

**服务器处理流程：**

```python
# 1. LLM 返回 Function Call
tool_name = "capture_image"
arguments = {"question": "你看到了什么？"}

# 2. 服务器调用 call_mcp_tool
result = await call_mcp_tool(
    conn=esp32_conn,
    mcp_client=esp32_conn.mcp_client,
    tool_name="capture_image",
    args=json.dumps(arguments),
    timeout=30
)
```

**服务器 → ESP32：发送工具调用请求**

```json
{
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "capture_image",
      "arguments": {
        "question": "你看到了什么？"
      }
    }
  }
}
```

**关键字段说明：**

- `id`: 请求 ID（用于匹配响应）
- `method`: 固定为 `"tools/call"`
- `params.name`: 要调用的工具名称
- `params.arguments`: 工具参数（JSON 对象）

#### 阶段 4：ESP32 执行工具

**ESP32 端处理流程：**

```cpp
// 1. 接收 tools/call 请求
// 2. 解析参数
String question = arguments["question"];  // "你看到了什么？"

// 3. 调用摄像头拍照
uint8_t* jpeg_data;
size_t jpeg_size;
camera.CaptureJpeg(&jpeg_data, &jpeg_size, 80);

// 4. 构建 HTTP POST 请求
String vision_url = "http://服务器IP:8003/mcp/vision/explain";
String token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...";

HTTPClient http;
http.begin(vision_url);
http.addHeader("Authorization", "Bearer " + token);
http.addHeader("Device-Id", device_id);

// 5. 构建 multipart/form-data
String boundary = "----WebKitFormBoundary";
String body = "";
body += "--" + boundary + "\r\n";
body += "Content-Disposition: form-data; name=\"question\"\r\n\r\n";
body += question + "\r\n";
body += "--" + boundary + "\r\n";
body += "Content-Disposition: form-data; name=\"image\"; filename=\"capture.jpg\"\r\n";
body += "Content-Type: image/jpeg\r\n\r\n";
// 添加图片二进制数据
body += "--" + boundary + "--\r\n";

// 6. 发送 HTTP POST
int httpCode = http.POST(body);

// 7. 接收响应
String response = http.getString();
// {"success": true, "action": "RESPONSE", "response": "我看到..."}
```

**ESP32 → 服务器：返回工具调用结果**

```json
{
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "id": 3,
    "result": {
      "content": [
        {
          "type": "text",
          "text": "{\"success\":true,\"action\":\"RESPONSE\",\"response\":\"我看到一个红色的苹果放在木桌上，旁边有一本打开的书。\"}"
        }
      ]
    }
  }
}
```

**结果格式说明：**

- `result.content`: 数组格式，支持多种内容类型
- `content[0].type`: 内容类型（`"text"` 或 `"image"`）
- `content[0].text`: 文本内容（JSON 字符串）

#### 阶段 5：服务器处理结果

```python
# 1. 接收 ESP32 返回的结果
raw_result = await result_future  # 等待 ESP32 响应

# 2. 解析结果
if isinstance(raw_result, dict):
    content = raw_result.get("content")
    if isinstance(content, list) and len(content) > 0:
        if "text" in content[0]:
            result_text = content[0]["text"]
            # result_text = '{"success":true,"action":"RESPONSE","response":"我看到..."}'

# 3. 解析 JSON
result_json = json.loads(result_text)

# 4. 检查 action 字段
if result_json.get("action") == "RESPONSE":
    # 直接返回结果，不需要二次 LLM 处理
    return ActionResponse(
        action=Action.RESPONSE,
        response=result_json.get("response")
    )
```

**最终 TTS 播放：**

服务器将 `"我看到一个红色的苹果放在木桌上，旁边有一本打开的书。"` 通过 TTS 转换为语音，发送给 ESP32 播放。

### 2.3 完整时序图

```
用户                LLM              服务器              ESP32              VLLM API
 │                  │                 │                  │                   │
 │ "打开摄像头"      │                 │                  │                   │
 ├─────────────────>│                 │                  │                   │
 │                  │                 │                  │                   │
 │                  │ Function Call   │                  │                   │
 │                  │ capture_image   │                  │                   │
 │                  ├────────────────>│                  │                   │
 │                  │                 │                  │                   │
 │                  │                 │ tools/call       │                   │
 │                  │                 │ (WebSocket)      │                   │
 │                  │                 ├─────────────────>│                   │
 │                  │                 │                  │                   │
 │                  │                 │                  │ 拍照              │
 │                  │                 │                  │ CaptureJpeg()     │
 │                  │                 │                  │                   │
 │                  │                 │                  │ HTTP POST         │
 │                  │                 │                  │ /mcp/vision/explain
 │                  │                 │<─────────────────┤                   │
 │                  │                 │                  │                   │
 │                  │                 │ vllm.response()  │                   │
 │                  │                 ├──────────────────┼──────────────────>│
 │                  │                 │                  │                   │
 │                  │                 │                  │                   │ 视觉分析
 │                  │                 │                  │                   │
 │                  │                 │<─────────────────┼───────────────────┤
 │                  │                 │ 分析结果         │                   │
 │                  │                 │                  │                   │
 │                  │                 │ HTTP Response    │                   │
 │                  │                 ├─────────────────>│                   │
 │                  │                 │                  │                   │
 │                  │                 │ MCP Result       │                   │
 │                  │                 │ (WebSocket)      │                   │
 │                  │                 │<─────────────────┤                   │
 │                  │                 │                  │                   │
 │                  │ 工具执行结果    │                  │                   │
 │                  │<────────────────┤                  │                   │
 │                  │                 │                  │                   │
 │                  │ TTS 语音        │                  │                   │
 │                  ├────────────────>│                  │                   │
 │                  │                 │                  │                   │
 │                  │                 │ OPUS 音频        │                   │
 │                  │                 ├─────────────────>│                   │
 │                  │                 │                  │                   │
 │<─────────────────┼─────────────────┼──────────────────┤                   │
 │ 播放语音         │                 │                  │                   │
```

### 2.4 MCP 工具调用格式总结

#### 标准格式

```json
{
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "id": <唯一ID>,
    "method": "tools/call",
    "params": {
      "name": "<工具名称>",
      "arguments": {
        "<参数名1>": "<参数值1>",
        "<参数名2>": "<参数值2>"
      }
    }
  }
}
```

#### 拍照工具示例

```json
{
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "capture_image",
      "arguments": {
        "question": "你看到了什么？"
      }
    }
  }
}
```

#### 其他工具示例

**获取设备状态：**

```json
{
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "get_device_status",
      "arguments": {}
    }
  }
}
```

**控制 LED（假设有此工具）：**

```json
{
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "id": 5,
    "method": "tools/call",
    "params": {
      "name": "control_led",
      "arguments": {
        "color": "red",
        "brightness": 80
      }
    }
  }
}
```

---

## 3. 关键配置

### 3.1 服务器配置（data/.config.yaml）

```yaml
server:
  # 视觉分析接口地址（必须是 ESP32 可访问的地址）
  vision_explain: http://公网IP或域名:8003/mcp/vision/explain

  # 认证密钥（用于生成 Token）
  auth_key: your_secret_key

selected_module:
  VLLM: ChatGLMVLLM # 选择的视觉模型

VLLM:
  ChatGLMVLLM:
    api_key: your_api_key
    model_name: glm-4v-plus
    base_url: https://open.bigmodel.cn/api/paas/v4/
    max_tokens: 500
    temperature: 0.7
```

### 3.2 ESP32 固件要求

- 固件版本：≥ 1.6.6
- 必须支持 MCP 协议
- 必须有摄像头硬件
- 必须实现 `capture_image` 工具

---

## 4. 错误处理

### 4.1 常见错误

| 错误                | 原因               | 解决方案                     |
| ------------------- | ------------------ | ---------------------------- |
| 401 Unauthorized    | Token 无效或过期   | 检查 auth_key 配置           |
| 设备ID与token不匹配 | Device-Id 头不匹配 | 确保 ESP32 发送正确的设备 ID |
| 图片大小超过限制    | 图片 > 5MB         | 降低 JPEG 质量或分辨率       |
| 不支持的文件格式    | 图片格式错误       | 确保发送 JPEG/PNG 等支持格式 |
| MCP客户端未准备就绪 | ESP32 未完成初始化 | 等待 MCP 初始化完成          |
| 工具调用超时        | ESP32 无响应       | 检查网络连接和 ESP32 状态    |

### 4.2 调试建议

1. **查看服务器日志**：

   ```bash
   tail -f logs/xiaozhi-esp32-api.log
   ```

2. **测试 HTTP 接口**：

   ```bash
   curl http://服务器IP:8003/mcp/vision/explain
   ```

3. **检查 MCP 工具列表**：
   在服务器日志中搜索 "客户端设备支持的工具数量"

4. **验证 Token**：
   确保 ESP32 使用的 Token 与服务器生成的一致

---

## 5. 总结

### 核心要点

1. **HTTP 接口**：`/mcp/vision/explain` 是 ESP32 上传图片的入口，服务器接收后调用 VLLM 进行分析
2. **MCP 工具调用**：通过 WebSocket 发送 `tools/call` 请求，格式遵循 JSON-RPC 2.0 规范
3. **双向通信**：WebSocket 用于命令下发，HTTP 用于大文件（图片）上传
4. **Token 认证**：服务器在 MCP 初始化时下发 Token，ESP32 用于 HTTP 请求认证

### 数据流总结

```
语音指令 → LLM 识别 → 调用 MCP 工具 → ESP32 拍照 → HTTP 上传图片
→ VLLM 分析 → 返回结果 → TTS 播放
```

### 关键文件

| 组件       | 文件路径                                          |
| ---------- | ------------------------------------------------- |
| HTTP 接口  | `core/api/vision_handler.py`                      |
| MCP 处理器 | `core/providers/tools/device_mcp/mcp_handler.py`  |
| MCP 执行器 | `core/providers/tools/device_mcp/mcp_executor.py` |
| VLLM 实现  | `core/providers/vllm/openai.py`                   |
| 配置文档   | `docs/mcp-vision-integration.md`                  |

---

**文档维护者：** Kiro AI Assistant  
**最后更新：** 2026-02-08

---

## 5. 上下文处理机制分析

### 5.1 关键发现：拍照工具是**无上下文**的

**答案：是的，MCP Vision 拍照工具调用是没有对话上下文的。**

#### 证据 1：VLLM 接口定义

```python
# core/providers/vllm/base.py
class VLLMProviderBase(ABC):
    @abstractmethod
    def response(self, question, base64_image):
        """VLLM response generator"""
        pass
```

**VLLM 只接收两个参数：**

- `question`: 单个问题文本
- `base64_image`: 图片的 base64 编码

**没有传递：**

- 对话历史（dialogue）
- 会话 ID（session_id）
- 记忆信息（memory）

#### 证据 2：VisionHandler 调用方式

```python
# core/api/vision_handler.py
async def handle_post(self, request):
    # 1. 解析请求
    question = await question_field.text()  # 只有问题
    image_data = await image_field.read()   # 只有图片

    # 2. 转换图片
    image_base64 = base64.b64encode(image_data).decode("utf-8")

    # 3. 调用 VLLM（没有传递任何上下文）
    result = vllm.response(question, image_base64)
```

#### 证据 3：OpenAI VLLM 实现

```python
# core/providers/vllm/openai.py
def response(self, question, base64_image):
    question = question + "(请使用中文回复)"

    # 构建消息（只有单轮对话）
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    },
                },
            ],
        }
    ]

    # 调用 API（没有历史消息）
    response = self.client.chat.completions.create(
        model=self.model_name,
        messages=messages,  # 只有当前这一条消息
        stream=False
    )
```

### 5.2 对比：LLM 对话是**有上下文**的

#### LLM 接口定义

```python
# core/providers/llm/base.py
class LLMProviderBase(ABC):
    @abstractmethod
    def response(self, session_id, dialogue):
        """LLM response generator"""
        pass
```

**LLM 接收完整对话历史：**

- `session_id`: 会话标识
- `dialogue`: 完整的对话历史列表

#### LLM 调用方式

```python
# core/connection.py
llm_responses = self.llm.response(
    self.session_id,
    self.dialogue.get_llm_dialogue_with_memory(
        memory_str,  # 记忆信息
        self.config.get("voiceprint", {})  # 声纹配置
    ),
)
```

#### 对话历史结构

```python
# core/utils/dialogue.py
def get_llm_dialogue_with_memory(self, memory_str=None, voiceprint_config=None):
    dialogue = []

    # 1. 系统提示（包含记忆和说话人信息）
    dialogue.append({"role": "system", "content": enhanced_system_prompt})

    # 2. 完整的对话历史
    for m in self.dialogue:
        if m.role != "system":
            dialogue.append({"role": m.role, "content": m.content})

    return dialogue
```

**LLM 对话历史示例：**

```json
[
  {
    "role": "system",
    "content": "你是小智助手...\n<memory>\n上次对话：用户问了天气\n</memory>"
  },
  {
    "role": "user",
    "content": "今天天气怎么样？"
  },
  {
    "role": "assistant",
    "content": "今天北京晴天，温度15-25度"
  },
  {
    "role": "user",
    "content": "那明天呢？" // LLM 知道"明天"指的是天气
  }
]
```

### 5.3 为什么拍照工具没有上下文？

#### 设计原因

1. **独立性**：视觉分析是独立任务，不依赖对话历史
2. **性能**：避免传递大量上下文数据到视觉模型
3. **简洁性**：问题已经由 LLM 生成，包含了必要信息
4. **成本**：视觉模型 API 调用成本高，减少 token 消耗

#### 工作流程

```
用户："这是什么？"（指着桌上的物品）
    ↓
LLM（有上下文）：理解用户意图 → 决定调用 capture_image
    ↓
LLM 生成问题："你看到了什么？"
    ↓
ESP32 拍照 → 上传图片 + 问题
    ↓
VLLM（无上下文）：只看图片 + 问题 → "我看到一个红色的苹果"
    ↓
返回结果 → LLM（有上下文）：整合结果 → TTS 播放
```

### 5.4 上下文对比表

| 特性           | LLM 对话                         | VLLM 拍照                   |
| -------------- | -------------------------------- | --------------------------- |
| **接口参数**   | `response(session_id, dialogue)` | `response(question, image)` |
| **对话历史**   | ✅ 完整历史                      | ❌ 无历史                   |
| **记忆信息**   | ✅ 包含记忆                      | ❌ 无记忆                   |
| **会话 ID**    | ✅ 有会话标识                    | ❌ 无会话                   |
| **系统提示**   | ✅ 包含系统提示                  | ⚠️ 只有固定后缀             |
| **多轮对话**   | ✅ 支持                          | ❌ 单轮                     |
| **上下文理解** | ✅ 可理解"那个"、"它"            | ❌ 无法理解代词             |

### 5.5 实际影响示例

#### 场景 1：连续提问（LLM 有上下文）

```
用户："今天天气怎么样？"
LLM："今天北京晴天，15-25度"

用户："那明天呢？"
LLM：（理解"明天"指天气）"明天多云，18-28度"
```

#### 场景 2：拍照识物（VLLM 无上下文）

```
用户："请拍照看看桌上是什么"
LLM：调用 capture_image，问题="你看到了什么？"
VLLM："我看到一个红色的苹果"

用户："它是什么颜色？"
LLM：（无法调用 VLLM，因为没有图片）
     "根据刚才的识别，是红色的"
```

**注意：** 第二次提问时，LLM 只能根据第一次的文本结果回答，无法再次查看图片。

### 5.6 如何实现"连续视觉对话"？

如果需要支持连续的视觉问答，需要：

#### 方案 1：缓存图片（推荐）

```python
# 在 ESP32 连接对象中缓存最后一张图片
esp32_conn.last_captured_image = {
    "timestamp": time.time(),
    "image_base64": image_base64,
    "question": question,
    "result": result
}

# 后续调用时可以复用
if "它" in new_question or "这个" in new_question:
    # 使用缓存的图片
    result = vllm.response(new_question, cached_image)
```

#### 方案 2：扩展 VLLM 接口支持上下文

```python
# 修改 VLLM 基类
class VLLMProviderBase(ABC):
    @abstractmethod
    def response(self, question, base64_image, dialogue=None):
        """VLLM response with optional dialogue history"""
        pass

# 调用时传递对话历史
result = vllm.response(
    question=question,
    base64_image=image_base64,
    dialogue=conn.dialogue.get_llm_dialogue()  # 传递上下文
)
```

#### 方案 3：多模态 LLM（未来方向）

使用原生支持多模态的 LLM（如 GPT-4V、Claude 3），直接在对话历史中包含图片：

```json
[
  {
    "role": "user",
    "content": [
      { "type": "text", "text": "这是什么？" },
      {
        "type": "image_url",
        "image_url": { "url": "data:image/jpeg;base64,..." }
      }
    ]
  },
  { "role": "assistant", "content": "这是一个红色的苹果" },
  { "role": "user", "content": "它是什么颜色？" },
  { "role": "assistant", "content": "红色" }
]
```

---

## 6. 更新后的总结

### 核心要点

1. **HTTP 接口**：`/mcp/vision/explain` 是 ESP32 上传图片的入口，服务器接收后调用 VLLM 进行分析
2. **MCP 工具调用**：通过 WebSocket 发送 `tools/call` 请求，格式遵循 JSON-RPC 2.0 规范
3. **双向通信**：WebSocket 用于命令下发，HTTP 用于大文件（图片）上传
4. **Token 认证**：服务器在 MCP 初始化时下发 Token，ESP32 用于 HTTP 请求认证
5. **无上下文设计**：VLLM 拍照工具是单轮对话，不保留对话历史和记忆

### 数据流总结

```
语音指令 → LLM 识别（有上下文） → 调用 MCP 工具 → ESP32 拍照 → HTTP 上传图片
→ VLLM 分析（无上下文） → 返回结果 → LLM 整合（有上下文） → TTS 播放
```

### 上下文对比

| 组件      | 上下文 | 记忆  | 多轮对话 |
| --------- | ------ | ----- | -------- |
| LLM 对话  | ✅ 有  | ✅ 有 | ✅ 支持  |
| VLLM 拍照 | ❌ 无  | ❌ 无 | ❌ 单轮  |

### 关键文件

| 组件       | 文件路径                                          |
| ---------- | ------------------------------------------------- |
| HTTP 接口  | `core/api/vision_handler.py`                      |
| MCP 处理器 | `core/providers/tools/device_mcp/mcp_handler.py`  |
| MCP 执行器 | `core/providers/tools/device_mcp/mcp_executor.py` |
| VLLM 基类  | `core/providers/vllm/base.py`                     |
| VLLM 实现  | `core/providers/vllm/openai.py`                   |
| LLM 基类   | `core/providers/llm/base.py`                      |
| 对话管理   | `core/utils/dialogue.py`                          |
| 配置文档   | `docs/mcp-vision-integration.md`                  |

---

**文档维护者：** Kiro AI Assistant  
**最后更新：** 2026-02-08
