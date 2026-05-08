# xiaozhi-server 详细分析文档

## 目录

1. [整体架构分析](#1-整体架构分析)
2. [目录结构详解](#2-目录结构详解)
3. [数据流分析](#3-数据流分析)
4. [ESP32 通信机制详解](#4-esp32-通信机制详解)
5. [MCP 功能详解](#5-mcp-功能详解)

---

## 1. 整体架构分析

### 1.1 架构概述

xiaozhi-server 是一个基于 Python 的异步 AI 语音交互后端服务器，采用模块化、插件化的架构设计。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           xiaozhi-server 架构                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        入口层 (app.py)                               │   │
│  │  - 配置加载 (config_loader)                                          │   │
│  │  - 认证密钥生成 (auth_key)                                           │   │
│  │  - 服务启动 (WebSocket + HTTP)                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                    ┌───────────────┴───────────────┐                       │
│                    ▼                               ▼                        │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐          │
│  │   WebSocket Server          │  │   HTTP Server               │          │
│  │   (websocket_server.py)     │  │   (http_server.py)          │          │
│  │   - 端口: 8000              │  │   - 端口: 8003              │          │
│  │   - 设备连接管理            │  │   - OTA 更新接口            │          │
│  │   - 认证处理                │  │   - 视觉分析接口            │          │
│  └─────────────────────────────┘  └─────────────────────────────┘          │
│                    │                                                        │
│                    ▼                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    连接处理层 (connection.py)                        │   │
│  │  - ConnectionHandler: 每个设备连接的独立处理器                       │   │
│  │  - 消息路由: 文本消息 / 二进制音频                                   │   │
│  │  - 组件初始化: VAD, ASR, TTS, LLM, Memory, Intent                   │   │
│  │  - 对话管理: Dialogue 上下文维护                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                    │                                                        │
│      ┌─────────────┼─────────────┬─────────────┬─────────────┐             │
│      ▼             ▼             ▼             ▼             ▼              │
│  ┌────────┐  ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐            │
│  │ handle │  │providers│   │ tools  │   │plugins │   │ utils  │            │
│  │ 消息   │  │ AI服务  │   │ 工具   │   │ 插件   │   │ 工具   │            │
│  │ 处理器 │  │ 提供者  │   │ 系统   │   │ 系统   │   │ 模块   │            │
│  └────────┘  └────────┘   └────────┘   └────────┘   └────────┘            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```


### 1.2 核心设计模式

#### 1.2.1 Provider Pattern (提供者模式)

所有 AI 服务都采用统一的抽象基类设计，支持灵活切换不同的服务提供商：

```python
# 抽象基类示例 (core/providers/asr/base.py)
class ASRBase(ABC):
    @abstractmethod
    async def transcribe(self, audio_data: bytes) -> str:
        pass
    
    @abstractmethod
    async def open_audio_channels(self, conn):
        pass
```

#### 1.2.2 Handler Pattern (处理器模式)

消息处理采用策略模式，不同类型的消息由不同的 Handler 处理：

```
core/handle/
├── helloHandle.py        # 握手消息处理
├── receiveAudioHandle.py # 音频接收处理
├── sendAudioHandle.py    # 音频发送处理
├── textHandle.py         # 文本消息处理
├── intentHandler.py      # 意图识别处理
├── abortHandle.py        # 中断请求处理
└── reportHandle.py       # 状态报告处理
```

#### 1.2.3 Plugin Pattern (插件模式)

功能扩展通过插件系统实现，支持热加载：

```python
# 插件注册示例
@register_function(
    name="get_weather",
    description="获取天气信息",
    parameters={...}
)
async def get_weather(city: str) -> str:
    ...
```

---

## 2. 目录结构详解

```
xiaozhi-server/
├── app.py                      # 主入口文件
├── config.yaml                 # 主配置文件
├── mcp_server_settings.json    # MCP 服务配置
│
├── config/                     # 配置管理模块
│   ├── config_loader.py        # 配置加载器
│   ├── logger.py               # 日志配置 (loguru)
│   ├── manage_api_client.py    # manager-api 客户端
│   ├── settings.py             # 设置管理
│   └── assets/                 # 静态音频资源
│       ├── bind_code.wav       # 绑定提示音
│       └── error.wav           # 错误提示音
│
├── core/                       # 核心模块
│   ├── auth.py                 # JWT 认证管理
│   ├── connection.py           # WebSocket 连接处理 (核心)
│   ├── http_server.py          # HTTP 服务器
│   ├── websocket_server.py     # WebSocket 服务器
│   │
│   ├── api/                    # HTTP API 处理器
│   │   ├── ota_handler.py      # OTA 更新处理
│   │   └── vision_handler.py   # 视觉分析处理
│   │
│   ├── handle/                 # 消息处理器
│   │   ├── helloHandle.py      # 握手处理
│   │   ├── receiveAudioHandle.py # 音频接收
│   │   ├── sendAudioHandle.py  # 音频发送
│   │   ├── textHandle.py       # 文本消息
│   │   ├── intentHandler.py    # 意图识别
│   │   ├── abortHandle.py      # 中断处理
│   │   ├── reportHandle.py     # 状态报告
│   │   └── textHandler/        # 文本消息子处理器
│   │
│   ├── providers/              # AI 服务提供者
│   │   ├── asr/                # 语音识别 (14+ 实现)
│   │   ├── llm/                # 大语言模型 (10+ 实现)
│   │   ├── tts/                # 语音合成 (20+ 实现)
│   │   ├── vad/                # 语音活动检测
│   │   ├── vllm/               # 视觉大模型
│   │   ├── intent/             # 意图识别
│   │   ├── memory/             # 记忆管理
│   │   └── tools/              # 工具系统 (MCP/IoT)
│   │
│   └── utils/                  # 工具模块
│       ├── modules_initialize.py # 模块初始化工厂
│       ├── dialogue.py         # 对话管理
│       ├── prompt_manager.py   # 提示词管理
│       ├── voiceprint_provider.py # 声纹识别
│       └── util.py             # 通用工具
│
├── plugins_func/               # 插件功能模块
│   ├── loadplugins.py          # 插件加载器
│   ├── register.py             # 插件注册器
│   └── functions/              # 插件实现
│       ├── get_weather.py      # 天气查询
│       ├── get_time.py         # 时间查询
│       ├── play_music.py       # 音乐播放
│       ├── hass_*.py           # Home Assistant
│       └── ...
│
├── models/                     # 本地模型
│   ├── SenseVoiceSmall/        # ASR 模型
│   └── snakers4_silero-vad/    # VAD 模型
│
├── data/                       # 数据目录
│   ├── .config.yaml            # 私有配置
│   └── .wakeup_words.yaml      # 唤醒词配置
│
└── test/                       # 测试工具
    └── test_page.html          # WebSocket 测试页面
```


---

## 3. 数据流分析

### 3.1 整体数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           完整数据流                                         │
└─────────────────────────────────────────────────────────────────────────────┘

用户语音 ──► ESP32 设备 ──► WebSocket ──► xiaozhi-server
                                              │
                                              ▼
                                    ┌─────────────────┐
                                    │ ConnectionHandler│
                                    └────────┬────────┘
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              ▼                              ▼                              ▼
    ┌─────────────────┐           ┌─────────────────┐           ┌─────────────────┐
    │ receiveAudio    │           │ textHandle      │           │ helloHandle     │
    │ Handle          │           │                 │           │                 │
    └────────┬────────┘           └────────┬────────┘           └─────────────────┘
             │                             │
             ▼                             │
    ┌─────────────────┐                    │
    │ VAD 语音检测    │                    │
    │ (SileroVAD)     │                    │
    └────────┬────────┘                    │
             │ 有效语音片段                 │
             ▼                             │
    ┌─────────────────┐                    │
    │ ASR 语音识别    │                    │
    │ (FunASR/云端)   │                    │
    └────────┬────────┘                    │
             │ 识别文本                     │
             ▼                             ▼
    ┌─────────────────────────────────────────────────────┐
    │                  Intent 意图识别                     │
    │  - function_call: LLM 函数调用                       │
    │  - intent_llm: 独立 LLM 意图识别                     │
    │  - nointent: 直接对话                                │
    └────────────────────────┬────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │ LLM 大模型处理  │           │ 工具调用        │
    │ (对话生成)      │◄──────────│ (MCP/IoT/插件)  │
    └────────┬────────┘           └─────────────────┘
             │ 回复文本
             ▼
    ┌─────────────────┐
    │ TTS 语音合成    │
    │ (流式输出)      │
    └────────┬────────┘
             │ 音频流
             ▼
    ┌─────────────────┐
    │ sendAudioHandle │
    └────────┬────────┘
             │ WebSocket
             ▼
    ESP32 设备 ──► 扬声器播放
```

### 3.2 音频处理数据流

```python
# 音频数据流详细过程

1. 音频接收 (receiveAudioHandle.py)
   │
   │  ESP32 发送 Opus 编码的音频数据块
   │  ↓
   │  asr_audio_queue.put(message)  # 放入队列
   │
   ▼
2. VAD 检测 (vad/silero.py)
   │
   │  检测语音活动，识别语音起止点
   │  ↓
   │  client_have_voice = True/False
   │  client_voice_stop = True (语音结束)
   │
   ▼
3. ASR 识别 (asr/*.py)
   │
   │  将音频转换为文本
   │  ↓
   │  支持流式识别和非流式识别
   │  返回识别文本
   │
   ▼
4. LLM 处理 (connection.py -> chat())
   │
   │  def chat(self, query, depth=0):
   │      # 构建对话上下文
   │      dialogue.put(Message(role="user", content=query))
   │      
   │      # 调用 LLM
   │      if self.intent_type == "function_call":
   │          llm_responses = self.llm.response_with_functions(...)
   │      else:
   │          llm_responses = self.llm.response(...)
   │      
   │      # 处理流式响应
   │      for response in llm_responses:
   │          # 发送到 TTS 队列
   │          self.tts.tts_text_queue.put(TTSMessageDTO(...))
   │
   ▼
5. TTS 合成 (tts/*.py)
   │
   │  将文本转换为语音
   │  ↓
   │  支持流式合成，边生成边发送
   │
   ▼
6. 音频发送 (sendAudioHandle.py)
   │
   │  通过 WebSocket 发送音频数据
   │  ↓
   │  await websocket.send(audio_data)
```


---

## 4. ESP32 通信机制详解

### 4.1 通信协议概述

xiaozhi-server 与 ESP32 设备之间主要通过 WebSocket 协议进行通信，支持两种连接方式：

| 连接方式 | 协议 | 端口 | 特点 |
|---------|------|------|------|
| 直连 | WebSocket | 8000 | 低延迟，实时双向通信 |
| MQTT 网关 | WebSocket (via MQTT Gateway) | 8000 | 通过外部网关转发 |

### 4.2 WebSocket 连接建立流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        WebSocket 连接建立流程                                │
└─────────────────────────────────────────────────────────────────────────────┘

ESP32 设备                                          xiaozhi-server
    │                                                     │
    │  1. WebSocket 连接请求                               │
    │  ws://<server>:8000/xiaozhi/v1/                     │
    │  Headers:                                           │
    │    - device-id: <设备ID>                            │
    │    - client-id: <客户端ID>                          │
    │    - authorization: Bearer <token>                  │
    │ ─────────────────────────────────────────────────► │
    │                                                     │
    │                                    2. 认证检查       │
    │                                    _handle_auth()   │
    │                                    - 白名单检查      │
    │                                    - JWT 验证       │
    │                                                     │
    │                                    3. 创建连接处理器  │
    │                                    ConnectionHandler│
    │                                                     │
    │  4. 连接确认                                        │
    │ ◄───────────────────────────────────────────────── │
    │                                                     │
    │  5. Hello 消息                                      │
    │  {"type": "hello", ...}                            │
    │ ─────────────────────────────────────────────────► │
    │                                                     │
    │                                    6. 初始化组件     │
    │                                    - VAD, ASR, TTS  │
    │                                    - LLM, Memory    │
    │                                    - Intent, Tools  │
    │                                                     │
    │  7. 欢迎消息                                        │
    │  {"type": "xiaozhi", "session_id": "..."}          │
    │ ◄───────────────────────────────────────────────── │
    │                                                     │
    │  8. 开始音频/文本交互                               │
    │ ◄────────────────────────────────────────────────► │
```

### 4.3 消息类型与格式

#### 4.3.1 文本消息 (JSON 格式)

```json
// 1. Hello 消息 (ESP32 -> Server)
{
    "type": "hello",
    "version": "1.0",
    "transport": "websocket",
    "audio_params": {
        "format": "opus",
        "sample_rate": 16000,
        "channels": 1
    }
}

// 2. 欢迎响应 (Server -> ESP32)
{
    "type": "xiaozhi",
    "session_id": "uuid-xxx",
    "version": "1.0"
}

// 3. 监听控制 (双向)
{
    "type": "listen",
    "state": "start" | "stop" | "detect"
}

// 4. 文本消息 (ESP32 -> Server)
{
    "type": "text",
    "text": "用户输入的文本"
}

// 5. TTS 状态 (Server -> ESP32)
{
    "type": "tts",
    "state": "start" | "stop" | "sentence_start" | "sentence_end",
    "text": "正在播放的文本"
}

// 6. 中断请求 (ESP32 -> Server)
{
    "type": "abort"
}

// 7. IoT 设备描述 (ESP32 -> Server)
{
    "type": "iot",
    "descriptors": [
        {
            "name": "light",
            "description": "控制灯光",
            "properties": {...},
            "methods": [...]
        }
    ]
}

// 8. IoT 命令 (Server -> ESP32)
{
    "type": "iot",
    "commands": [
        {
            "name": "light",
            "method": "turn_on",
            "parameters": {}
        }
    ]
}
```

#### 4.3.2 二进制消息 (音频数据)

```
┌─────────────────────────────────────────────────────────────────┐
│                    音频数据格式                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  直连模式:                                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Opus 编码的音频数据块                        │   │
│  │              (无头部，直接是音频数据)                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  MQTT 网关模式 (16字节头部):                                     │
│  ┌────────┬────────┬────────┬────────┬─────────────────────┐   │
│  │ 保留   │ 保留   │时间戳  │音频长度│    音频数据          │   │
│  │ 8字节  │ 0字节  │ 4字节  │ 4字节  │    N字节            │   │
│  └────────┴────────┴────────┴────────┴─────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.4 消息路由机制

```python
# connection.py 中的消息路由

async def _route_message(self, message):
    """消息路由"""
    if isinstance(message, str):
        # 文本消息 -> JSON 解析 -> 分发到对应 Handler
        await handleTextMessage(self, message)
    elif isinstance(message, bytes):
        # 二进制消息 -> 音频处理
        if self.vad is None or self.asr is None:
            return
        
        # 处理 MQTT 网关的音频包 (带16字节头部)
        if self.conn_from_mqtt_gateway and len(message) >= 16:
            handled = await self._process_mqtt_audio_message(message)
            if handled:
                return
        
        # 直接处理原始音频
        self.asr_audio_queue.put(message)
```

### 4.5 认证机制

```python
# websocket_server.py 中的认证处理

async def _handle_auth(self, websocket):
    if self.auth_enable:
        headers = dict(websocket.request.headers)
        device_id = headers.get("device-id", None)
        
        # 1. 白名单检查
        if self.allowed_devices and device_id in self.allowed_devices:
            return  # 白名单设备直接放行
        
        # 2. JWT Token 验证
        token = headers.get("authorization", "")
        if token.startswith("Bearer "):
            token = token[7:]
        
        auth_success = self.auth.verify_token(
            token, 
            client_id=client_id, 
            username=device_id
        )
        if not auth_success:
            raise AuthenticationError("Invalid token")
```

### 4.6 连接生命周期管理

```
┌─────────────────────────────────────────────────────────────────┐
│                    连接生命周期                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 连接建立                                                     │
│     └─► handle_connection() 被调用                              │
│         └─► 创建 ConnectionHandler 实例                         │
│             └─► 初始化组件 (VAD, ASR, TTS, LLM...)             │
│                                                                 │
│  2. 活跃状态                                                     │
│     └─► 消息循环: async for message in websocket                │
│         └─► _route_message() 处理每条消息                       │
│         └─► last_activity_time 更新                             │
│                                                                 │
│  3. 超时检查                                                     │
│     └─► _check_timeout() 每10秒检查一次                         │
│         └─► 超过 timeout_seconds 则关闭连接                     │
│                                                                 │
│  4. 连接关闭                                                     │
│     └─► _save_and_close() 被调用                                │
│         └─► 保存对话记忆                                        │
│         └─► close() 清理资源                                    │
│             └─► 取消超时任务                                    │
│             └─► 清理工具处理器                                  │
│             └─► 清空任务队列                                    │
│             └─► 关闭 WebSocket                                  │
│             └─► 关闭线程池                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```


---

## 5. MCP 功能详解

### 5.1 MCP 概述

MCP (Model Context Protocol) 是一种标准化的协议，用于 LLM 与外部工具/服务之间的交互。xiaozhi-server 实现了完整的 MCP 支持，包括多种工具类型。

### 5.2 工具类型架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MCP 工具系统架构                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    UnifiedToolHandler (统一工具处理器)               │   │
│  │                    unified_tool_handler.py                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    ToolManager (工具管理器)                          │   │
│  │                    unified_tool_manager.py                          │   │
│  │  - 工具注册与缓存                                                    │   │
│  │  - 工具查找与执行                                                    │   │
│  │  - 函数描述生成 (OpenAI 格式)                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│      ┌─────────────┬───────────────┼───────────────┬─────────────┐         │
│      ▼             ▼               ▼               ▼             ▼          │
│  ┌────────┐  ┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐       │
│  │SERVER  │  │SERVER  │     │DEVICE  │     │DEVICE  │     │  MCP   │       │
│  │PLUGIN  │  │  MCP   │     │  IOT   │     │  MCP   │     │ENDPOINT│       │
│  │服务端  │  │服务端  │     │设备端  │     │设备端  │     │  MCP   │       │
│  │插件    │  │MCP服务 │     │IoT控制 │     │MCP工具 │     │接入点  │       │
│  └────────┘  └────────┘     └────────┘     └────────┘     └────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 工具类型详解

```python
# base/tool_types.py

class ToolType(Enum):
    """工具类型枚举"""
    SERVER_PLUGIN = "server_plugin"   # 服务端插件 (本地 Python 函数)
    SERVER_MCP = "server_mcp"         # 服务端 MCP (外部 MCP 服务)
    DEVICE_IOT = "device_iot"         # 设备端 IoT (ESP32 设备控制)
    DEVICE_MCP = "device_mcp"         # 设备端 MCP (ESP32 MCP 工具)
    MCP_ENDPOINT = "mcp_endpoint"     # MCP 接入点 (远程 MCP 服务)
```

| 工具类型 | 说明 | 执行位置 | 配置方式 |
|---------|------|---------|---------|
| SERVER_PLUGIN | 本地 Python 插件函数 | 服务器本地 | plugins_func/functions/ |
| SERVER_MCP | 服务端 MCP 服务 | 服务器本地/远程 | mcp_server_settings.json |
| DEVICE_IOT | ESP32 设备 IoT 控制 | ESP32 设备 | 设备上报描述符 |
| DEVICE_MCP | ESP32 设备 MCP 工具 | ESP32 设备 | 设备上报工具列表 |
| MCP_ENDPOINT | 远程 MCP 接入点 | 远程服务器 | config.yaml mcp_endpoint |

### 5.4 服务端 MCP (SERVER_MCP)

#### 5.4.1 配置文件

```json
// data/.mcp_server_settings.json
{
    "mcpServers": {
        "weather": {
            "command": "python",
            "args": ["-m", "weather_mcp_server"],
            "env": {
                "API_KEY": "xxx"
            }
        },
        "database": {
            "url": "ws://localhost:8080/mcp"
        }
    }
}
```

#### 5.4.2 初始化流程

```python
# server_mcp/mcp_manager.py

class ServerMCPManager:
    async def initialize_servers(self):
        config = self.load_config()
        for name, srv_config in config.items():
            # 创建 MCP 客户端
            client = ServerMCPClient(srv_config)
            await client.initialize(logging_callback=self.logging_callback)
            self.clients[name] = client
            
            # 获取工具列表
            client_tools = client.get_available_tools()
            self.tools.extend(client_tools)
```

#### 5.4.3 工具执行

```python
async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
    # 找到对应的客户端
    for name, client in self.clients.items():
        if client.has_tool(tool_name):
            target_client = client
            break
    
    # 带重试机制的工具调用
    for attempt in range(max_retries):
        try:
            return await target_client.call_tool(tool_name, arguments)
        except Exception as e:
            # 重新连接并重试
            await target_client.cleanup()
            client = ServerMCPClient(config[client_name])
            await client.initialize()
            self.clients[client_name] = client
```

### 5.5 MCP 接入点 (MCP_ENDPOINT)

#### 5.5.1 概述

MCP 接入点允许连接到远程 MCP 服务，通过 WebSocket 进行通信。

#### 5.5.2 连接流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    MCP 接入点连接流程                            │
└─────────────────────────────────────────────────────────────────┘

xiaozhi-server                                    MCP 接入点服务
      │                                                │
      │  1. WebSocket 连接                             │
      │ ─────────────────────────────────────────────► │
      │                                                │
      │  2. 初始化请求 (JSON-RPC)                      │
      │  {                                             │
      │    "jsonrpc": "2.0",                          │
      │    "id": 1,                                   │
      │    "method": "initialize",                   │
      │    "params": {                               │
      │      "protocolVersion": "2024-11-05",        │
      │      "clientInfo": {...}                     │
      │    }                                         │
      │  }                                            │
      │ ─────────────────────────────────────────────► │
      │                                                │
      │  3. 初始化响应                                 │
      │ ◄───────────────────────────────────────────── │
      │                                                │
      │  4. 初始化完成通知                             │
      │  {"method": "notifications/initialized"}      │
      │ ─────────────────────────────────────────────► │
      │                                                │
      │  5. 获取工具列表                               │
      │  {"method": "tools/list"}                     │
      │ ─────────────────────────────────────────────► │
      │                                                │
      │  6. 工具列表响应                               │
      │  {"result": {"tools": [...]}}                 │
      │ ◄───────────────────────────────────────────── │
      │                                                │
      │  7. 工具调用                                   │
      │  {"method": "tools/call", "params": {...}}   │
      │ ◄────────────────────────────────────────────► │
```

#### 5.5.3 工具调用实现

```python
# mcp_endpoint/mcp_endpoint_handler.py

async def call_mcp_endpoint_tool(
    mcp_client: MCPEndpointClient, 
    tool_name: str, 
    args: str = "{}", 
    timeout: int = 30
):
    # 检查客户端就绪状态
    if not await mcp_client.is_ready():
        raise RuntimeError("MCP接入点客户端尚未准备就绪")
    
    # 获取下一个请求 ID
    tool_call_id = await mcp_client.get_next_id()
    
    # 注册结果 Future
    result_future = asyncio.Future()
    await mcp_client.register_call_result_future(tool_call_id, result_future)
    
    # 构建请求
    payload = {
        "jsonrpc": "2.0",
        "id": tool_call_id,
        "method": "tools/call",
        "params": {
            "name": actual_name,
            "arguments": arguments
        }
    }
    
    # 发送请求
    await mcp_client.send_message(json.dumps(payload))
    
    # 等待响应
    raw_result = await asyncio.wait_for(result_future, timeout=timeout)
    return raw_result
```

### 5.6 设备端 IoT (DEVICE_IOT)

#### 5.6.1 设备描述符上报

```json
// ESP32 -> Server
{
    "type": "iot",
    "descriptors": [
        {
            "name": "bedroom_light",
            "description": "卧室灯光控制",
            "properties": {
                "power": {"type": "boolean", "description": "开关状态"},
                "brightness": {"type": "integer", "description": "亮度 0-100"}
            },
            "methods": [
                {
                    "name": "turn_on",
                    "description": "打开灯",
                    "parameters": {}
                },
                {
                    "name": "set_brightness",
                    "description": "设置亮度",
                    "parameters": {
                        "level": {"type": "integer", "required": true}
                    }
                }
            ]
        }
    ]
}
```

#### 5.6.2 命令下发

```json
// Server -> ESP32
{
    "type": "iot",
    "commands": [
        {
            "name": "bedroom_light",
            "method": "set_brightness",
            "parameters": {
                "level": 80
            }
        }
    ]
}
```

### 5.7 统一工具处理流程

```python
# unified_tool_handler.py

class UnifiedToolHandler:
    async def handle_llm_function_call(self, conn, function_call_data):
        """处理 LLM 函数调用"""
        function_name = function_call_data["name"]
        arguments = function_call_data.get("arguments", {})
        
        # 解析参数
        if isinstance(arguments, str):
            arguments = json.loads(arguments) if arguments else {}
        
        # 执行工具调用 (自动路由到正确的执行器)
        result = await self.tool_manager.execute_tool(function_name, arguments)
        return result
```

### 5.8 LLM Function Call 集成

```python
# connection.py 中的 chat() 方法

def chat(self, query, depth=0):
    # 获取可用函数列表
    functions = None
    if self.intent_type == "function_call" and hasattr(self, "func_handler"):
        functions = self.func_handler.get_functions()
    
    # 调用 LLM (带函数定义)
    if functions is not None:
        llm_responses = self.llm.response_with_functions(
            self.session_id,
            self.dialogue.get_llm_dialogue_with_memory(...),
            functions=functions
        )
    
    # 处理流式响应
    for response in llm_responses:
        content, tools_call = response
        
        if tools_call is not None:
            # 检测到工具调用
            tool_call_flag = True
            self._merge_tool_calls(tool_calls_list, tools_call)
    
    # 执行工具调用
    if tool_call_flag and len(tool_calls_list) > 0:
        for tool_call_data in tool_calls_list:
            future = asyncio.run_coroutine_threadsafe(
                self.func_handler.handle_llm_function_call(self, tool_call_data),
                self.loop
            )
            result = future.result()
        
        # 处理工具结果
        self._handle_function_result(tool_results, depth=depth)
```

### 5.9 工具结果处理

```python
def _handle_function_result(self, tool_results, depth):
    for result, tool_call_data in tool_results:
        if result.action in [Action.RESPONSE, Action.NOTFOUND, Action.ERROR]:
            # 直接回复用户
            text = result.response if result.response else result.result
            self.tts.tts_one_sentence(self, ContentType.TEXT, content_detail=text)
            
        elif result.action == Action.REQLLM:
            # 需要 LLM 进一步处理
            need_llm_tools.append((result, tool_call_data))
    
    if need_llm_tools:
        # 将工具结果添加到对话历史
        self.dialogue.put(Message(role="assistant", tool_calls=all_tool_calls))
        for result, tool_call_data in need_llm_tools:
            self.dialogue.put(Message(
                role="tool",
                tool_call_id=tool_call_data["id"],
                content=result.result
            ))
        
        # 递归调用 LLM
        self.chat(None, depth=depth + 1)
```

---

## 6. 总结

xiaozhi-server 是一个设计精良的 AI 语音交互后端系统：

1. **模块化架构**：Provider 模式支持灵活切换 AI 服务
2. **异步高性能**：基于 asyncio 的异步处理，支持高并发
3. **完整的 MCP 支持**：5 种工具类型，覆盖本地插件到远程服务
4. **灵活的通信**：WebSocket 直连 + MQTT 网关两种模式
5. **可扩展性**：插件系统支持功能热加载

---

*文档生成时间：2025年12月2日*
