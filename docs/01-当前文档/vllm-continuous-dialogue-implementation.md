# VLLM 连续对话实现方案

## 概述

为 Qwen3-VL 等多模态大语言模型实现连续视觉对话功能，支持用户在拍照后进行多轮提问。

---

## 方案选择

### 方案对比

| 方案                       | 优点               | 缺点                         | 推荐度     |
| -------------------------- | ------------------ | ---------------------------- | ---------- |
| **方案 1：扩展 VLLM 接口** | 简单直接，改动最小 | 需要缓存图片，内存占用       | ⭐⭐⭐⭐⭐ |
| 方案 2：复用 LLM 机制      | 完全复用现有代码   | 架构改动大，可能影响其他功能 | ⭐⭐⭐     |
| 方案 3：独立多模态 LLM     | 架构清晰           | 需要重构大量代码             | ⭐⭐       |

**推荐：方案 1 - 扩展 VLLM 接口**

原因：

1. 改动最小，风险低
2. 不影响现有 LLM 对话机制
3. 可以逐步迁移到方案 3

---

## 方案 1：扩展 VLLM 接口（推荐）

### 1.1 核心思路

1. **扩展 VLLM 基类**：添加支持对话历史的接口
2. **缓存图片**：在连接对象中缓存最后一张图片
3. **智能判断**：根据用户问题判断是否需要图片
4. **向后兼容**：保留原有单轮接口

### 1.2 实现步骤

#### 步骤 1：扩展 VLLM 基类

```python
# main/xiaozhi-server/core/providers/vllm/base.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class VLLMProviderBase(ABC):
    @abstractmethod
    def response(self, question: str, base64_image: str) -> str:
        """单轮视觉问答（向后兼容）

        Args:
            question: 问题文本
            base64_image: 图片的 base64 编码

        Returns:
            回答文本
        """
        pass

    def response_with_dialogue(
        self,
        question: str,
        base64_image: str,
        dialogue: Optional[List[Dict]] = None
    ) -> str:
        """支持对话历史的视觉问答（新增）

        Args:
            question: 当前问题
            base64_image: 图片的 base64 编码
            dialogue: 对话历史（可选）
                格式：[
                    {"role": "system", "content": "..."},
                    {"role": "user", "content": "..."},
                    {"role": "assistant", "content": "..."}
                ]

        Returns:
            回答文本
        """
        # 默认实现：忽略对话历史，调用单轮接口
        logger.bind(tag=TAG).warning(
            f"{self.__class__.__name__} 不支持对话历史，将使用单轮模式"
        )
        return self.response(question, base64_image)
```

#### 步骤 2：实现 Qwen3-VL 支持对话历史

```python
# main/xiaozhi-server/core/providers/vllm/qwen.py

import openai
from typing import List, Dict, Optional
from config.logger import setup_logging
from core.utils.util import check_model_key
from core.providers.vllm.base import VLLMProviderBase

TAG = __name__
logger = setup_logging()


class QwenVLLMProvider(VLLMProviderBase):
    """Qwen3-VL 多模态大语言模型提供者

    支持连续对话的视觉问答
    """

    def __init__(self, config):
        self.model_name = config.get("model_name", "qwen-vl-plus")
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url") or config.get("url")

        # 参数配置
        param_defaults = {
            "max_tokens": (1000, int),
            "temperature": (0.7, lambda x: round(float(x), 1)),
            "top_p": (1.0, lambda x: round(float(x), 1)),
        }

        for param, (default, converter) in param_defaults.items():
            value = config.get(param)
            try:
                setattr(
                    self,
                    param,
                    converter(value) if value not in (None, "") else default,
                )
            except (ValueError, TypeError):
                setattr(self, param, default)

        model_key_msg = check_model_key("VLLM", self.api_key)
        if model_key_msg:
            logger.bind(tag=TAG).error(model_key_msg)

        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

    def response(self, question: str, base64_image: str) -> str:
        """单轮视觉问答（向后兼容）"""
        return self.response_with_dialogue(question, base64_image, dialogue=None)

    def response_with_dialogue(
        self,
        question: str,
        base64_image: str,
        dialogue: Optional[List[Dict]] = None
    ) -> str:
        """支持对话历史的视觉问答

        Args:
            question: 当前问题
            base64_image: 图片的 base64 编码
            dialogue: 对话历史（可选）

        Returns:
            回答文本
        """
        try:
            # 构建消息列表
            messages = []

            # 1. 添加历史对话（如果有）
            if dialogue:
                for msg in dialogue:
                    role = msg.get("role")
                    content = msg.get("content")

                    # 跳过 tool 角色的消息
                    if role == "tool":
                        continue

                    # 系统消息和普通消息直接添加
                    if role in ["system", "assistant"]:
                        messages.append({"role": role, "content": content})
                    elif role == "user":
                        # 用户消息可能包含图片，需要特殊处理
                        # 这里简化处理，只添加文本
                        messages.append({"role": "user", "content": content})

            # 2. 添加当前问题（包含图片）
            current_message = {
                "role": "user",
                "content": [
                    {"type": "text", "text": question + "(请使用中文回复)"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        },
                    },
                ],
            }
            messages.append(current_message)

            # 3. 调用 API
            logger.bind(tag=TAG).debug(
                f"调用 Qwen3-VL，消息数量: {len(messages)}, "
                f"包含历史: {dialogue is not None}"
            )

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                stream=False
            )

            result = response.choices[0].message.content
            logger.bind(tag=TAG).info(f"Qwen3-VL 响应成功，长度: {len(result)}")

            return result

        except Exception as e:
            logger.bind(tag=TAG).error(f"Qwen3-VL 调用失败: {e}")
            raise
```

#### 步骤 3：修改 VisionHandler 支持对话历史

```python
# main/xiaozhi-server/core/api/vision_handler.py

import json
import copy
import base64
from aiohttp import web
from typing import Tuple, Optional, List, Dict
from config.logger import setup_logging
from core.utils.util import get_vision_url, is_valid_image_file
from core.utils.vllm import create_instance
from config.config_loader import get_private_config_from_api
from core.utils.auth import AuthToken
from plugins_func.register import Action

TAG = __name__

# 设置最大文件大小为5MB
MAX_FILE_SIZE = 5 * 1024 * 1024


class VisionHandler:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()
        # 初始化认证工具
        self.auth = AuthToken(config["server"]["auth_key"])

    def _create_error_response(self, message: str) -> dict:
        """创建统一的错误响应格式"""
        return {"success": False, "message": message}

    def _verify_auth_token(self, request) -> Tuple[bool, Optional[str]]:
        """验证认证token"""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False, None

        token = auth_header[7:]  # 移除"Bearer "前缀
        return self.auth.verify_token(token)

    async def handle_post(self, request):
        """处理 MCP Vision POST 请求

        支持两种模式：
        1. 单轮模式：只传 question + image
        2. 连续对话模式：传 question + image + dialogue
        """
        response = None
        try:
            # 验证token
            is_valid, token_device_id = self._verify_auth_token(request)
            if not is_valid:
                response = web.Response(
                    text=json.dumps(
                        self._create_error_response("无效的认证token或token已过期")
                    ),
                    content_type="application/json",
                    status=401,
                )
                return response

            # 获取请求头信息
            device_id = request.headers.get("Device-Id", "")
            client_id = request.headers.get("Client-Id", "")
            if device_id != token_device_id:
                raise ValueError("设备ID与token不匹配")

            # 解析multipart/form-data请求
            reader = await request.multipart()

            # 读取question字段
            question_field = await reader.next()
            if question_field is None:
                raise ValueError("缺少问题字段")
            question = await question_field.text()
            self.logger.bind(tag=TAG).debug(f"Question: {question}")

            # 读取图片文件
            image_field = await reader.next()
            if image_field is None:
                raise ValueError("缺少图片文件")

            # 读取图片数据
            image_data = await image_field.read()
            if not image_data:
                raise ValueError("图片数据为空")

            # 检查文件大小
            if len(image_data) > MAX_FILE_SIZE:
                raise ValueError(
                    f"图片大小超过限制，最大允许{MAX_FILE_SIZE/1024/1024}MB"
                )

            # 检查文件格式
            if not is_valid_image_file(image_data):
                raise ValueError(
                    "不支持的文件格式，请上传有效的图片文件（支持JPEG、PNG、GIF、BMP、TIFF、WEBP格式）"
                )

            # 将图片转换为base64编码
            image_base64 = base64.b64encode(image_data).decode("utf-8")

            # 读取对话历史（可选字段）
            dialogue = None
            dialogue_field = await reader.next()
            if dialogue_field is not None:
                try:
                    dialogue_json = await dialogue_field.text()
                    dialogue = json.loads(dialogue_json)
                    self.logger.bind(tag=TAG).debug(
                        f"收到对话历史，消息数量: {len(dialogue)}"
                    )
                except Exception as e:
                    self.logger.bind(tag=TAG).warning(
                        f"解析对话历史失败: {e}，将使用单轮模式"
                    )
                    dialogue = None

            # 如果开启了智控台，则从智控台获取模型配置
            current_config = copy.deepcopy(self.config)
            read_config_from_api = current_config.get("read_config_from_api", False)
            if read_config_from_api:
                current_config = get_private_config_from_api(
                    current_config,
                    device_id,
                    client_id,
                )

            select_vllm_module = current_config["selected_module"].get("VLLM")
            if not select_vllm_module:
                raise ValueError("您还未设置默认的视觉分析模块")

            vllm_type = (
                select_vllm_module
                if "type" not in current_config["VLLM"][select_vllm_module]
                else current_config["VLLM"][select_vllm_module]["type"]
            )

            if not vllm_type:
                raise ValueError(f"无法找到VLLM模块对应的供应器{vllm_type}")

            vllm = create_instance(
                vllm_type, current_config["VLLM"][select_vllm_module]
            )

            # 调用 VLLM（支持对话历史）
            if dialogue and hasattr(vllm, 'response_with_dialogue'):
                result = vllm.response_with_dialogue(question, image_base64, dialogue)
                self.logger.bind(tag=TAG).info("使用连续对话模式")
            else:
                result = vllm.response(question, image_base64)
                self.logger.bind(tag=TAG).info("使用单轮模式")

            return_json = {
                "success": True,
                "action": Action.RESPONSE.name,
                "response": result,
            }

            response = web.Response(
                text=json.dumps(return_json, separators=(",", ":")),
                content_type="application/json",
            )
        except ValueError as e:
            self.logger.bind(tag=TAG).error(f"MCP Vision POST请求异常: {e}")
            return_json = self._create_error_response(str(e))
            response = web.Response(
                text=json.dumps(return_json, separators=(",", ":")),
                content_type="application/json",
            )
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"MCP Vision POST请求异常: {e}")
            return_json = self._create_error_response("处理请求时发生错误")
            response = web.Response(
                text=json.dumps(return_json, separators=(",", ":")),
                content_type="application/json",
            )
        finally:
            if response:
                self._add_cors_headers(response)
            return response

    async def handle_get(self, request):
        """处理 MCP Vision GET 请求"""
        try:
            vision_explain = get_vision_url(self.config)
            if vision_explain and len(vision_explain) > 0 and "null" != vision_explain:
                message = (
                    f"MCP Vision 接口运行正常，视觉解释接口地址是：{vision_explain}"
                )
            else:
                message = "MCP Vision 接口运行不正常，请打开data目录下的.config.yaml文件，找到【server.vision_explain】，设置好地址"

            response = web.Response(text=message, content_type="text/plain")
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"MCP Vision GET请求异常: {e}")
            return_json = self._create_error_response("服务器内部错误")
            response = web.Response(
                text=json.dumps(return_json, separators=(",", ":")),
                content_type="application/json",
            )
        finally:
            self._add_cors_headers(response)
            return response

    def _add_cors_headers(self, response):
        """添加CORS头信息"""
        response.headers["Access-Control-Allow-Headers"] = (
            "client-id, content-type, device-id"
        )
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Origin"] = "*"
```

#### 步骤 4：在连接对象中缓存图片和对话

```python
# main/xiaozhi-server/core/connection.py

# 在 ConnectionHandler.__init__ 中添加：

# 视觉对话缓存
self.vision_dialogue = {
    "last_image": None,  # 最后一张图片的 base64
    "last_question": None,  # 最后一个问题
    "last_result": None,  # 最后一次识别结果
    "timestamp": 0,  # 时间戳
    "dialogue_history": []  # 视觉对话历史
}
```

#### 步骤 5：修改 MCP 工具执行器

```python
# main/xiaozhi-server/core/providers/tools/device_mcp/mcp_executor.py

class DeviceMCPExecutor(ToolExecutor):
    """设备端MCP工具执行器"""

    def __init__(self, conn):
        self.conn = conn

    async def execute(
        self, conn, tool_name: str, arguments: Dict[str, Any]
    ) -> ActionResponse:
        """执行设备端MCP工具"""
        if not hasattr(conn, "mcp_client") or not conn.mcp_client:
            return ActionResponse(
                action=Action.ERROR,
                response="设备端MCP客户端未初始化",
            )

        if not await conn.mcp_client.is_ready():
            return ActionResponse(
                action=Action.ERROR,
                response="设备端MCP客户端未准备就绪",
            )

        try:
            # 转换参数为JSON字符串
            import json

            args_str = json.dumps(arguments) if arguments else "{}"

            # 调用设备端MCP工具
            result = await call_mcp_tool(conn, conn.mcp_client, tool_name, args_str)

            resultJson = None
            if isinstance(result, str):
                try:
                    resultJson = json.loads(result)
                except Exception as e:
                    pass

            # 视觉大模型不经过二次LLM处理
            if (
                resultJson is not None
                and isinstance(resultJson, dict)
                and "action" in resultJson
            ):
                # 如果是视觉识别结果，缓存到连接对象
                if tool_name == "capture_image" and hasattr(conn, "vision_dialogue"):
                    import time
                    conn.vision_dialogue["last_question"] = arguments.get("question")
                    conn.vision_dialogue["last_result"] = resultJson.get("response")
                    conn.vision_dialogue["timestamp"] = time.time()

                    # 添加到对话历史
                    conn.vision_dialogue["dialogue_history"].append({
                        "role": "user",
                        "content": arguments.get("question")
                    })
                    conn.vision_dialogue["dialogue_history"].append({
                        "role": "assistant",
                        "content": resultJson.get("response")
                    })

                    # 限制历史长度（保留最近 10 轮对话）
                    if len(conn.vision_dialogue["dialogue_history"]) > 20:
                        conn.vision_dialogue["dialogue_history"] = \
                            conn.vision_dialogue["dialogue_history"][-20:]

                    conn.logger.bind(tag=TAG).debug(
                        f"缓存视觉对话，历史长度: "
                        f"{len(conn.vision_dialogue['dialogue_history'])}"
                    )

                return ActionResponse(
                    action=Action[resultJson["action"]],
                    response=resultJson.get("response", ""),
                )

            return ActionResponse(action=Action.REQLLM, result=str(result))

        except ValueError as e:
            return ActionResponse(action=Action.NOTFOUND, response=str(e))
        except Exception as e:
            return ActionResponse(action=Action.ERROR, response=str(e))

    # ... 其他方法保持不变
```

#### 步骤 6：ESP32 端修改（伪代码）

```cpp
// ESP32 端需要修改 HTTP POST 请求，添加对话历史字段

void sendVisionRequest(String question, uint8_t* jpeg_data, size_t jpeg_size) {
    HTTPClient http;
    http.begin(vision_url);
    http.addHeader("Authorization", "Bearer " + token);
    http.addHeader("Device-Id", device_id);

    // 构建 multipart/form-data
    String boundary = "----WebKitFormBoundary";
    String body = "";

    // 1. 添加 question 字段
    body += "--" + boundary + "\r\n";
    body += "Content-Disposition: form-data; name=\"question\"\r\n\r\n";
    body += question + "\r\n";

    // 2. 添加 image 字段
    body += "--" + boundary + "\r\n";
    body += "Content-Disposition: form-data; name=\"image\"; filename=\"capture.jpg\"\r\n";
    body += "Content-Type: image/jpeg\r\n\r\n";
    // 添加图片二进制数据
    body += "\r\n";

    // 3. 添加 dialogue 字段（新增）
    if (hasDialogueHistory()) {
        body += "--" + boundary + "\r\n";
        body += "Content-Disposition: form-data; name=\"dialogue\"\r\n\r\n";
        body += getDialogueHistoryJSON() + "\r\n";
    }

    body += "--" + boundary + "--\r\n";

    // 发送请求
    int httpCode = http.POST(body);
    String response = http.getString();

    // 解析响应并缓存
    parseAndCacheResponse(response);
}

// 缓存对话历史
String getDialogueHistoryJSON() {
    // 返回 JSON 格式的对话历史
    // [{"role":"user","content":"..."},{"role":"assistant","content":"..."}]
    return dialogueHistoryJSON;
}
```

### 1.3 配置示例

```yaml
# data/.config.yaml

selected_module:
  VLLM: QwenVLLM # 使用 Qwen3-VL

VLLM:
  QwenVLLM:
    type: qwen # 对应 qwen.py
    api_key: your_qwen_api_key
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    model_name: qwen-vl-plus
    max_tokens: 1000
    temperature: 0.7
    top_p: 1.0
```

### 1.4 使用示例

#### 单轮对话（向后兼容）

```python
vllm = QwenVLLMProvider(config)
result = vllm.response("你看到了什么？", image_base64)
# 输出："我看到一个红色的苹果"
```

#### 连续对话（新功能）

```python
# 第一轮
dialogue = []
result1 = vllm.response_with_dialogue("你看到了什么？", image_base64, dialogue)
# 输出："我看到一个红色的苹果"

# 更新对话历史
dialogue.append({"role": "user", "content": "你看到了什么？"})
dialogue.append({"role": "assistant", "content": result1})

# 第二轮（复用图片）
result2 = vllm.response_with_dialogue("它是什么颜色？", image_base64, dialogue)
# 输出："红色"（模型理解"它"指的是苹果）
```

---

## 方案 2：完全复用 LLM 机制（备选）

### 2.1 核心思路

将 VLLM 视为特殊的 LLM，完全复用现有的对话管理机制。

### 2.2 优缺点

**优点：**

- 完全复用现有代码
- 对话历史、记忆、声纹等功能自动支持

**缺点：**

- 架构改动大
- 可能影响现有 LLM 功能
- 图片需要特殊处理

### 2.3 实现概要（不推荐）

```python
# 创建一个特殊的 LLM Provider
class MultimodalLLMProvider(LLMProviderBase):
    def response(self, session_id, dialogue):
        # 从对话历史中提取图片
        # 调用多模态 API
        pass
```

---

## 测试方案

### 测试用例 1：单轮对话

```
用户："请拍照看看桌上是什么"
助手："我看到一个红色的苹果"
```

### 测试用例 2：连续对话

```
用户："请拍照看看桌上是什么"
助手："我看到一个红色的苹果"

用户："它是什么颜色？"
助手："红色"

用户："它大概多重？"
助手："根据图片判断，这个苹果大约200-250克"
```

### 测试用例 3：超时清理

```
用户："请拍照看看桌上是什么"
助手："我看到一个红色的苹果"

（等待 5 分钟）

用户："它是什么颜色？"
助手："抱歉，图片已过期，请重新拍照"
```

---

## 实施计划

### 阶段 1：基础实现（1-2 天）

- [ ] 扩展 VLLM 基类
- [ ] 实现 Qwen3-VL Provider
- [ ] 修改 VisionHandler
- [ ] 添加图片缓存

### 阶段 2：ESP32 端适配（1 天）

- [ ] 修改 HTTP 请求格式
- [ ] 实现对话历史缓存
- [ ] 测试连续对话

### 阶段 3：优化和测试（1 天）

- [ ] 添加超时清理
- [ ] 性能优化
- [ ] 完整测试

---

## 注意事项

### 1. 图片缓存策略

- **缓存时长**：建议 5 分钟
- **缓存位置**：连接对象（内存）
- **清理策略**：超时自动清理

### 2. 对话历史长度

- **建议长度**：10 轮（20 条消息）
- **超出处理**：保留最近的消息

### 3. 性能考虑

- **图片大小**：base64 编码后约 20KB
- **内存占用**：每个连接约 100KB
- **API 成本**：每次调用包含完整对话历史

### 4. 错误处理

- 图片过期：提示用户重新拍照
- API 失败：降级到单轮模式
- 解析失败：忽略对话历史

---

## 总结

**推荐方案：方案 1 - 扩展 VLLM 接口**

优势：

1. ✅ 改动最小，风险低
2. ✅ 向后兼容，不影响现有功能
3. ✅ 实现简单，易于维护
4. ✅ 支持 Qwen3-VL 等多模态模型

实施步骤：

1. 扩展 VLLM 基类添加 `response_with_dialogue` 方法
2. 实现 Qwen3-VL Provider
3. 修改 VisionHandler 支持对话历史
4. ESP32 端添加对话历史字段
5. 测试和优化

---

**文档维护者：** Kiro AI Assistant  
**最后更新：** 2026-02-08
