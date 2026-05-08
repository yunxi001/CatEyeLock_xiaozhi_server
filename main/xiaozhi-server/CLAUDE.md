# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

xiaozhi-server 是"小智"AI语音助手项目的服务端，负责与 ESP32 硬件设备通过 WebSocket 实时通信，实现 AI 语音交互流水线：**VAD（语音活动检测）→ ASR（语音识别）→ Intent（意图识别）→ LLM（大语言模型）→ TTS（语音合成）**。同时支持手机 App WebSocket 连接、MQTT 网关、HTTP OTA/视觉分析等协议。

## 启动与运行

```bash
# 安装依赖（推荐 Python 3.10）
pip install -r requirements.txt

# 启动服务器
python app.py

# 运行测试（全量）
pytest test/doorlock/ -v

# 运行单个测试文件
pytest test/doorlock/test_doorlock_api.py -v

# 运行特定测试函数
pytest test/doorlock/test_doorlock_api.py::test_function_name -v
```

## 配置系统

配置加载有三级优先级（高到低）：

1. **远程 API 配置** — 若 `data/.config.yaml` 中配置了 `manager-api.url`，则从 Java 管理后台获取配置
2. **用户自定义配置** — `data/.config.yaml`（仅包含需要覆盖的字段）
3. **默认配置** — `config.yaml`（1012 行完整默认配置）

合并方式：递归深度合并（`config/config_loader.py` 中的 `merge_configs()`）。`selected_module` 字段决定使用哪个 AI 提供商的实现（如 `selected_module.ASR: "fun_server"` 会选择 FunASR 提供商）。

用户只需在 `data/.config.yaml` 中填写要覆盖的配置项，无需修改 `config.yaml`。

## 核心架构

### 1. AI 流水线（`core/connection.py` 中的 `ConnectionHandler`）

一个 ESP32 客户端连接对应一个 `ConnectionHandler` 实例。核心对话流程是异步流式管道：

```
ESP32 WebSocket → OPUS音频帧 → VAD检测语音 → ASR转文字 → Intent判定意图 → LLM生成回复 → TTS合成语音 → OPUS音频帧 → ESP32
```

- LLM 回复是流式的，通过 `chat()` 方法逐 token 处理
- TTS 使用**生产者-消费者模式**：两个线程安全队列（`tts_text_queue` 和 `tts_audio_queue`）
- 文本在标点边界处分割后送入 TTS，实现自然断句
- 支持中断机制：`client_abort` 标志可立即停止当前 TTS 播放

### 2. 消息处理策略模式（`core/handle/`）

所有 ESP32/App 文本消息（23 种类型，定义在 `textMessageType.py`）通过策略模式分发：

- `TextMessageHandler` — 抽象基类，定义 `message_type` 属性和 `handle()` 方法
- `TextMessageHandlerRegistry` — 注册表，映射 `type` 字符串 → handler 实例
- `TextMessageProcessor.process_message()` — 解析 JSON → 检查 `forward` 字段（用于 App↔ESP32 消息转发）→ 按 `type` 分发到 handler
- 各 handler 实现在 `core/handle/textHandler/` 目录下

### 3. 提供商插件架构（`core/providers/`）

所有 AI 能力组件遵循统一模式：抽象基类 + 多实现 + 工厂创建：

- `core/providers/asr/` — 11 个 ASR 提供商
- `core/providers/tts/` — 22 个 TTS 提供商
- `core/providers/llm/` — 14 个 LLM 提供商
- `core/providers/vad/` — SileroVAD
- `core/providers/vllm/` — 视觉 LLM（OpenAI 兼容）
- `core/providers/intent/` — 3 种意图策略（nointent、intent_llm、function_call）
- `core/providers/memory/` — 3 种记忆策略（nomem、mem0ai、mem_local_short）

每个实现通过 `core/utils/<module>.py`（如 `llm.py`、`tts.py`）中的 `create_instance()` 工厂方法实例化。运行时可通过 `selected_module` 配置热切换，无需重启。

### 4. 统一工具系统（`core/providers/tools/`）

`UnifiedToolHandler` 编排五类工具执行器：

| 执行器 | 用途 |
|---|---|
| `ServerPluginExecutor` | 服务器端插件（天气、新闻、音乐等） |
| `ServerMCPExecutor` | 服务器端 MCP 工具 |
| `DeviceIoTExecutor` | ESP32 设备 IoT 控制 |
| `DeviceMCPExecutor` | ESP32 设备端 MCP 工具 |
| `MCPEndpointExecutor` | 外部 MCP 接入点 |

### 5. 插件系统（`plugins_func/`）

- `@register_function(name, desc, type)` 装饰器将函数注册到 `all_function_registry`
- `loadplugins.py` 自动导入 `plugins_func/functions/` 下所有模块
- `FunctionRegistry` 管理每个连接会话的函数注册/注销
- `ToolType` 枚举定义 6 种工具类型（NONE、WAIT、CHANGE_SYS_PROMPT、SYSTEM_CTL、IOT_CTL、MCP_CLIENT）
- `Action` 枚举定义 5 种动作（ERROR、NOTFOUND、NONE、RESPONSE、REQLLM）

### 6. 连接管理（Singleton 模式）

`ConnectionManager` 是全局单例，维护两个字典：
- `esp32_connections` — `{device_id: ConnectionHandler}`
- `app_connections` — `{device_id: [AppConnectionHandler, ...]}`

支持双向消息转发：App↔ESP32 通过消息中的 `forward` 字段透明路由。

### 7. 多协议支持

| 协议 | 入口 | 用途 |
|---|---|---|
| WebSocket (ESP32) | `ws://host:8000/xiaozhi/v1/` | ESP32 设备实时通信 |
| WebSocket (App) | `ws://host:8000/xiaozhi/v1/` | 手机 App（协议 v2.2，含 seq_id/ack 机制） |
| HTTP | `http://host:8003/xiaozhi/ota/` | OTA 固件升级 |
| HTTP | `http://host:8003/mcp/vision/explain` | 视觉分析 API |
| WebSocket (MQTT网关) | `ws://host:8000/xiaozhi/v1/?from=mqtt_gateway` | MQTT+UDP 转 WebSocket |

### 8. 对话与记忆管理

- `Dialogue` 类（`core/utils/dialogue.py`）管理对话历史，包含 `Message` 对象列表
- `PromptManager`（`core/utils/prompt_manager.py`）管理系统提示词，注入时间、天气、位置等上下文
- 对话历史在 function_call 模式的 LLM 调用中维护，支持多轮递归工具调用（最大深度 5 层）
- 支持声纹识别（`voiceprint_provider.py`）区分不同说话人

## 网络端口

| 端口 | 服务 |
|---|---|
| 8000 | WebSocket 主服务（ESP32 + App） |
| 8003 | HTTP 服务（OTA、视觉分析） |

## 日志系统

使用 `loguru` 库。通过 `setup_logging()` 创建 logger，使用 `logger.bind(tag=TAG)` 绑定额外的上下文字段。配置在 `config.yaml` 的 `log` 部分。

## 注意事项

- `app.py` 启动时必须确保 `ffmpeg` 已安装且在 PATH 中
- `data/.config.yaml` 由用户创建和维护，不应提交到版本控制
- 本地 AI 模型（SenseVoice、Silero-VAD）放置在 `models/` 目录，Docker 部署时需要挂载
- `requirements.txt` 中有注释标注不可升级的依赖（如 torch、numpy、websockets），升级前需确认兼容性
- OPUS 音频编解码是硬件要求的格式，不能改用其他编码
