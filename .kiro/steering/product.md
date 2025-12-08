---
inclusion: always
---

# xiaozhi-server

为 ESP32 智能硬件设备提供语音 AI 后端服务的 Python 核心引擎。

## 产品定位

- 处理设备连接、语音流和 AI 推理

## 核心能力

| 能力 | 说明 |
|------|------|
| 语音交互 | ASR 语音识别、TTS 语音合成、VAD 语音活动检测 |
| 智能对话 | LLM 大语言模型集成 |
| 多模态 | VLLM 视觉语言模型支持 |
| 身份识别 | 声纹识别说话人 |
| 物联网控制 | 插件系统扩展（天气、新闻、Home Assistant、音乐） |
| 协议支持 | WebSocket（端口 8000）、HTTP API（端口 8003）、MCP |

## 开发原则

1. **Provider 模式**：AI 服务（ASR/LLM/TTS/VLLM/VAD）通过 `core/providers/*/base.py` 抽象基类实现，新增服务商需继承对应基类
2. **配置驱动**：服务选择通过 config.yaml 的 `selected_module` 配置，避免硬编码
3. **插件化扩展**：新功能优先通过 `plugins_func/functions/` 插件实现，需定义 LLM 可理解的 name、description、parameters schema
4. **异步优先**：使用 asyncio 处理并发连接，WebSocket 和 HTTP 服务均为异步实现

## 关键路径

- `app.py`：主入口
- `config.yaml`：主配置文件
- `core/websocket_server.py`：WebSocket 服务器
- `core/connection.py`：连接处理器
- `core/handle/`：消息处理器（音频、文本、意图等）
- `core/providers/`：AI 服务提供者
- `plugins_func/functions/`：插件目录
