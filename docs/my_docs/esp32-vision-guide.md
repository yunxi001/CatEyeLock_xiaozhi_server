# ESP32 视觉拍照功能使用指南

## 概述

本文档说明如何通过 MCP 协议让服务器主动调用 ESP32 拍照，以及如何实现视觉大模型的连续对话功能。

---

## 一、服务器调用 ESP32 拍照

服务器通过 WebSocket 发送 JSON-RPC 2.0 格式的 MCP 消息调用 ESP32 拍照工具。

**调用格式：**

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

**关键字段：**

- `method`: 固定为 `"tools/call"`
- `params.name`: 工具名称（如 `capture_image`）
- `params.arguments`: 工具参数（问题文本）

---

## 二、ESP32 拍照和上传

ESP32 收到 MCP 调用后，拍照并通过 HTTP POST 上传图片到服务器。

**HTTP 上传格式：**

```
POST /mcp/vision/explain
Host: 服务器IP:8003
Authorization: Bearer <token>
Device-Id: <设备ID>
Content-Type: multipart/form-data

字段：
- question: "你看到了什么？"
- image: <JPEG 图片数据>
- dialogue: [对话历史]（可选，用于连续对话）
```

**dialogue 字段格式（可选）：**

```json
[
  { "role": "user", "content": "你看到了什么？" },
  { "role": "assistant", "content": "我看到一个红色的苹果" }
]
```

---

## 三、服务器端处理和返回

服务器接收图片后，调用 VLLM 进行视觉分析，并将结果返回给 ESP32。

**ESP32 返回格式（MCP 协议）：**

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
          "text": "{\"success\":true,\"action\":\"RESPONSE\",\"response\":\"我看到一个红色的苹果\"}"
        }
      ]
    }
  }
}
```

**服务器 HTTP 响应格式：**

```json
{
  "success": true,
  "action": "RESPONSE",
  "response": "我看到一个红色的苹果"
}
```

---

## 四、实现连续对话和工具调用

### 4.1 问题描述

当前 VLLM 是单轮对话，无法理解上下文。例如：

```
用户："请拍照看看桌上是什么"
VLLM："我看到一个红色的苹果"

用户："它是什么颜色？"
LLM："根据刚才的识别，是红色的"  ← 只能根据文本回答，无法再看图片
```

### 4.2 解决思路

通过扩展 VLLM 接口，支持 **system + dialogue + tool** 三个功能：

#### 方案 1：System 支持（固定提示词）

- 创建 `config/vllm_config.yaml` 存储 VLLM 专用的 system prompt
- 在 `response_with_dialogue()` 中自动加载并插入到 messages 开头
- 支持时间占位符替换（如 `{{current_time}}`）

#### 方案 2：Dialogue 支持（对话历史）

- 扩展 VLLM 基类，添加 `response_with_dialogue()` 方法
- 实现 Qwen3-VL Provider，支持传入对话历史
- 修改 VisionHandler，解析 ESP32 上传的 `dialogue` 字段
- 在连接对象中缓存图片和对话历史（保留最近 10 轮）

#### 方案 3：Tool 支持（工具调用）

- 扩展 VLLM 基类，添加 `response_with_functions()` 方法（参考 LLM 模式）
- 实现 Qwen3-VL 的工具调用接口（流式返回）
- 修改 VisionHandler，解析 `functions` 字段并处理工具调用结果
- 在配置文件中定义可用工具（如人脸识别、物体检测）

**工作量评估：** 7 个文件，约 140 行代码，2.5 小时

### 4.3 效果对比

**改造后（支持 system + dialogue + tool）：**

```
用户："请拍照看看桌上是什么"
VLLM："我看到一个红色的苹果"

用户："它是什么颜色？"
VLLM："红色"  ← 可以理解"它"指的是苹果

用户："这个人是谁？"
VLLM 调用工具：detect_face(confidence_threshold=0.8)
工具返回："张三，置信度 0.95"
VLLM："这是张三"  ← 可以调用人脸识别工具
```

---

## 五、配置示例

```yaml
# data/.config.yaml

server:
  vision_explain: http://公网IP:8003/mcp/vision/explain
  auth_key: your_secret_key

selected_module:
  VLLM: QwenVLLM

VLLM:
  QwenVLLM:
    type: qwen
    api_key: your_qwen_api_key
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    model_name: qwen-vl-plus
    max_tokens: 1000
    temperature: 0.7
```

---

## 六、关键代码位置

| 组件          | 文件路径                                         | 说明            |
| ------------- | ------------------------------------------------ | --------------- |
| MCP 工具调用  | `core/providers/tools/device_mcp/mcp_handler.py` | 调用 ESP32 工具 |
| HTTP 接口     | `core/api/vision_handler.py`                     | 接收图片和问题  |
| VLLM 基类     | `core/providers/vllm/base.py`                    | 定义接口        |
| Qwen Provider | `core/providers/vllm/qwen.py`                    | 实现连续对话    |
| 对话缓存      | `core/connection.py`                             | 缓存图片和历史  |

---

## 七、注意事项

- **图片缓存时长**：5 分钟
- **对话历史长度**：建议保留最近 10 轮（20 条消息）
- **性能优化**：图片只传一次，后续复用
- **错误处理**：API 失败时降级到单轮模式

---

**文档维护者：** Kiro AI Assistant  
**最后更新：** 2026-02-08
