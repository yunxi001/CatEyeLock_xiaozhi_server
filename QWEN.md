# 小智后端服务 (xiaozhi-esp32-server) 项目说明

## 项目概述

小智后端服务 (xiaozhi-esp32-server) 是一个基于人机共生智能理论和技术研发的智能终端软硬件体系的后端服务。本项目为开源智能硬件项目 [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) 提供后端支持，根据[小智通信协议](https://ccnphfhqs21z.feishu.cn/wiki/M0XiwldO9iJwHikpXD5cEx71nKh) 使用 Python、Java、Vue 实现。

该项目支持多种通信协议和技术，包括：
- MQTT+UDP 协议
- WebSocket 协议
- MCP 接入点
- 声纹识别
- 知识库

## 核心架构

### 服务组件
1. **HTTP 服务器**：处理 OTA（固件更新）请求和视觉分析接口
2. **WebSocket 服务器**：处理实时语音和文本通信
3. **认证管理器**：处理设备认证和 JWT 令牌验证
4. **模块化组件系统**：包括 VAD、ASR、TTS、LLM、VLLM、Memory、Intent 等

### 核心技术栈
- **Python 3.10**：主要开发语言
- **AsyncIO**：异步 I/O 框架
- **AIOHTTP**：HTTP 服务器和客户端
- **WebSockets**：WebSocket 通信
- **多种 AI/ML 框架**：FunASR、Silero VAD、多种 LLM 和 TTS 服务

### 主要功能模块
1. **语音交互**：流式 ASR (语音识别)、流式 TTS (语音合成)、VAD (语音活动检测)
2. **声纹识别**：多用户声纹注册、管理和识别
3. **智能对话**：支持多种 LLM (大语言模型)
4. **视觉感知**：支持多种 VLLM (视觉大模型)
5. **意图识别**：支持外挂大模型意图识别、大模型自主函数调用
6. **记忆系统**：支持本地短期记忆、mem0ai 接口记忆
7. **知识库**：支持 RAGFlow 知识库
8. **工具调用**：支持客户端 IOT 协议、MCP 协议、服务端 MCP 协议

## 项目结构

```
xiaozhi-esp32-server/
├── main/
│   ├── xiaozhi-server/          # 核心后端服务
│   │   ├── app.py               # 应用主入口
│   │   ├── config/              # 配置相关模块
│   │   ├── core/                # 核心功能模块
│   │   │   ├── api/             # API 处理器 (OTA, Vision)
│   │   │   ├── handle/          # 消息处理器
│   │   │   ├── providers/       # 服务提供商 (ASR, TTS, LLM 等)
│   │   │   └── utils/           # 工具函数
│   │   ├── models/              # AI 模型文件目录
│   │   ├── plugins_func/        # 插件功能
│   │   ├── test/                # 测试文件
│   │   ├── config.yaml          # 默认配置文件
│   │   └── requirements.txt     # Python 依赖
│   ├── manager-api/             # 管理 API
│   ├── manager-mobile/          # 移动端管理
│   └── manager-web/             # Web 管理界面
├── docs/                        # 文档
├── docker-compose.yml           # Docker 配置文件
├── Dockerfile-server            # 服务器 Dockerfile
└── README.md                    # 主要说明文档
```

## 配置文件

- `config.yaml`：主要配置文件，包含服务器配置、AI 服务配置、插件配置等
- `data/.config.yaml`：用户自定义配置文件，优先级高于 config.yaml
- `config_from_api.yaml`：从 API 读取配置的备份文件

## 构建和运行

### 本地运行
```bash
# 1. 安装依赖
pip install -r main/xiaozhi-server/requirements.txt

# 2. 配置文件
# 在项目根目录创建 data 目录，然后创建 .config.yaml 文件进行自定义配置

# 3. 启动服务
cd main/xiaozhi-server
python app.py
```

### Docker 运行
```bash
# 单模块运行
docker-compose -f main/xiaozhi-server/docker-compose.yml up -d

# 全模块运行
docker-compose -f main/xiaozhi-server/docker-compose_all.yml up -d
```

### 环境要求
- Python 3.10 (推荐)
- FFmpeg (用于音频处理)
- GPU (推荐，用于本地 AI 模型推理)

## 开发约定

### 代码结构
- 核心功能在 `core/` 目录下，按功能模块组织
- API 接口在 `core/api/` 下实现
- AI 服务提供商在 `core/providers/` 下实现
- 工具函数在 `core/utils/` 下实现

### 配置管理
- 使用分层配置：默认配置、用户配置、API 配置
- 敏感信息应放在 `data/.config.yaml` 文件中，该文件不会被提交到版本控制

### 日志记录
- 使用 `config.logger` 模块进行统一的日志记录
- 日志格式和级别在配置文件中定义

## API 接口

### WebSocket 接口
- 地址: `ws://<server>:<port>/xiaozhi/v1/`
- 用于实时语音和文本通信
- 支持设备 ID 和认证令牌验证

### HTTP 接口
- OTA 接口: `GET/POST /xiaozhi/ota/`
  - 用于设备固件更新配置
  - 支持 MQTT 网关配置或 WebSocket 配置下发
- 视觉分析接口: `GET/POST /mcp/vision/explain`
  - 用于图像识别和分析
  - 需要认证令牌

## 主要依赖

- `websockets`：WebSocket 通信
- `aiohttp`：HTTP 服务和客户端
- `funasr`：语音识别
- `silero_vad`：语音活动检测
- `openai`：OpenAI API 接口
- `edge_tts`：Edge TTS 语音合成
- `loguru`：日志记录

## 特殊功能

### 声纹识别
- 支持多用户声纹识别
- 在 ASR 处理的同时进行声纹识别
- 识别结果传递给 LLM 进行个性化回应

### 插件系统
- 支持功能插件扩展
- 支持自定义插件开发
- 支持插件热加载

### 记忆系统
- 支持本地短期记忆
- 支持 mem0ai 接口记忆
- 具备记忆总结功能

## 部署说明

本项目提供两种部署方式：
1. **最简化安装**：智能对话、IOT、MCP、视觉感知，数据存储在配置文件，无需数据库
2. **全模块安装**：完整功能体验，数据存储在数据库，包括声纹识别、OTA、智控台等

## 维护者

由华南理工大学刘思源教授团队主导研发。

## 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。