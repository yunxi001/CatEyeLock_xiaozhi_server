---
inclusion: always
---

# xiaozhi-server 项目结构

Python AI 引擎，位于 `main/xiaozhi-server/`。

## 目录结构

```
main/xiaozhi-server/
├── app.py                    # 主入口，启动 WebSocket/HTTP 服务
├── config.yaml               # 主配置，AI 服务选择在此配置
├── core/
│   ├── websocket_server.py   # WebSocket 服务器
│   ├── http_server.py        # HTTP API 服务器
│   ├── connection.py         # 设备连接处理
│   ├── providers/            # AI 服务提供者（扩展点）
│   │   ├── asr/              # 语音识别
│   │   ├── tts/              # 语音合成
│   │   ├── llm/              # 大语言模型
│   │   ├── vllm/             # 视觉语言模型
│   │   ├── vad/              # 语音活动检测
│   │   ├── memory/           # 对话记忆
│   │   └── intent/           # 意图识别
│   ├── handle/               # 消息处理器
│   └── utils/                # 工具函数
├── plugins_func/functions/   # 插件目录（扩展点）
├── config/                   # 配置加载模块
└── data/                     # 运行时数据
```

## 文件定位速查

| 任务 | 目标路径 | 注意事项 |
|------|----------|----------|
| 新增 AI Provider | `core/providers/{type}/` | 继承 `base.py` 抽象类 |
| 新增插件功能 | `plugins_func/functions/` | 需定义 LLM schema |
| 修改服务配置 | `config.yaml` | 通过 `selected_module` 切换 |
| 消息处理逻辑 | `core/handle/` | 音频、文本、意图等 |
| 工具函数 | `core/utils/` | 共享工具方法 |

## 核心架构模式

### Provider 模式

新增 AI 服务商必须：
1. 在 `core/providers/{type}/` 下创建新文件
2. 继承 `base.py` 中的抽象基类
3. 实现所有抽象方法
4. 在 `config.yaml` 中通过 `selected_module` 启用

### 插件系统

新增插件必须：
1. 在 `plugins_func/functions/` 下创建 Python 文件
2. 定义 `name`（函数名）、`description`（功能描述）、`parameters`（JSON Schema）
3. 插件由 `loadplugins.py` 自动加载

### 异步编程

- 使用 `asyncio` 处理并发连接
- WebSocket 和 HTTP 服务均为异步实现
- Provider 方法应支持异步调用
