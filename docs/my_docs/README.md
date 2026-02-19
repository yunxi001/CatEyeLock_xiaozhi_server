# xiaozhi-server 文档目录

本目录包含 xiaozhi-server 项目的核心文档，用于指导开发、测试和维护工作。

---

## 📋 文档分类

### 🔷 协议规范文档

#### 智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md

**用途**: ESP32 设备与服务器之间的 WebSocket 通信协议规范（当前版本）  
**包含内容**:

- 二进制流媒体协议（BinaryProtocol2）
- 文本消息协议（JSON）
- 智能门锁专用消息类型
- 两级确认机制（esp32_ack + ack）
- 统一错误码（0-10）

#### 智能猫眼门锁系统-服务器与App通信协议规范-v2.5.md

**用途**: App 与服务器之间的 WebSocket 通信协议规范（当前版本）  
**包含内容**:

- App 连接认证机制
- 命令下发与查询接口
- 设备状态推送机制
- 消息确认机制（seq_id + server_ack）
- 统一错误码规范（0-10）
- 密码查询接口
- 媒体文件下载规范
- 智能门锁AI功能消息类型（v2.5新增）
  - 访客意图通知（intent_notification）
  - 快递警报通知（package_alert）
  - 人脸识别结果推送（face_result）

---

### 🔷 协议升级文档

#### app-protocol-v2.4-update-analysis.md

**用途**: App 协议 v2.4 更新分析报告  
**包含内容**:

- 协议变更时间线
- 核心功能变更分析
- 智能门锁AI功能说明
- 数据库变更分析

#### app-protocol-v2.5-update-checklist.md

**用途**: App 协议 v2.5 更新检查清单  
**包含内容**:

- 协议更新任务清单
- 新增消息类型说明
- 数据库变更清单
- 验证清单

#### app-protocol-v2.5-update-checklist-final.md

**用途**: App 协议 v2.5 更新检查清单（最终版）  
**包含内容**:

- 完整的数据库变更分析
- 详细的消息类型说明
- 协议升级验证清单
- 相关文档更新指引

---

### 🔷 VLLM 实现文档

#### vllm-implementation-analysis.md

**用途**: VLLM 实现分析文档  
**包含内容**:

- VLLM 提供者实现分析
- 统一模式设计说明
- Token 管理机制
- 图片处理流程

#### vllm-intent-simulation-test-plan.md

**用途**: VLLM 意图模拟测试计划  
**包含内容**:

- 测试场景设计
- 测试用例说明
- 预期结果验证
- 测试执行指南

---

### 🔷 架构与设计文档

#### 智能猫眼门锁系统-服务器端架构说明.md

**用途**: 服务器端整体架构设计说明  
**包含内容**:

- 系统架构图
- 核心模块说明
- 数据流转机制
- 技术栈选型

#### xiaozhi-server-detailed-analysis.md

**用途**: xiaozhi-server 核心代码详细分析  
**包含内容**:

- 代码结构分析
- 关键模块实现细节
- 设计模式应用
- 扩展点说明

#### esp32-data-processing-flow.md

**用途**: ESP32 数据处理流程详细分析  
**包含内容**:

- 连接建立流程
- 消息接收与路由
- 文本消息处理
- 二进制音频处理
- 智能门锁协议处理
- 人脸识别处理
- 监控模式处理
- 响应返回机制

#### esp32-data-processing-detailed-analysis.md

**用途**: ESP32 数据处理各环节的深度分析  
**包含内容**:

- Handler 注册机制
- 消息分发逻辑
- 数据持久化流程
- App 推送机制

#### app-data-processing-detailed-analysis.md

**用途**: App 数据处理流程详细分析  
**包含内容**:

- 连接认证与管理
- 命令代理处理
- 数据查询处理
- 媒体文件下载
- 实时数据推送

#### project-analysis.md

**用途**: 项目整体分析文档  
**包含内容**:

- 项目背景
- 技术选型
- 模块划分
- 开发计划

---

### 🔷 功能实现文档

#### dialogue-class-explanation.md

**用途**: Dialogue 类详细使用说明  
**包含内容**:

- Dialogue 类结构
- 核心方法说明
- 对话上下文管理
- 长期记忆注入
- 说话人识别
- 工具调用管理

#### doorlock-api-documentation.md

**用途**: 智能门锁 AI 功能 HTTP API 接口文档  
**包含内容**:

- 设备配置 API
- 看护模式控制 API
- 欢迎词配置 API
- 历史记录查询 API

#### esp32-vision-guide.md

**用途**: ESP32 视觉拍照功能使用指南  
**包含内容**:

- 服务器调用 ESP32 拍照
- ESP32 拍照和上传
- 服务器端处理和返回
- 实现连续对话和工具调用

#### mcp-vision-detailed-analysis.md

**用途**: MCP Vision 拍照识物功能详细分析  
**包含内容**:

- 服务器端 HTTP 接口详细分析
- ESP32 端 MCP 工具调用格式详细分析
- 上下文处理机制分析

#### vllm-continuous-dialogue-implementation.md

**用途**: VLLM 连续对话实现方案  
**包含内容**:

- 方案选择和对比
- 扩展 VLLM 接口实现
- 缓存图片和对话历史
- 配置示例

---

### 🔷 规范与机制文档

#### seq_id使用规范与注意事项.md

**用途**: seq_id 消息 ID 机制的使用规范  
**包含内容**:

- seq_id 生成规则
- 防重放机制
- 使用注意事项
- 常见问题解答

#### 消息ID机制与工作流程.md

**用途**: 消息 ID 机制的详细说明  
**包含内容**:

- msg_id 与 seq_id 的区别
- 消息确认流程
- 超时重试机制
- 错误处理

---

### 🔷 App 连接相关文档

#### app-offline-connection-README.md

**用途**: App 离线连接功能说明  
**包含内容**:

- 离线连接机制
- 状态推送逻辑
- 日志输出说明
- 使用示例

---

### 🔷 智能门锁 AI 功能文档（开发中）

#### smart-doorlock-ai-requirements.md

**用途**: 智能门锁 AI 功能需求文档  
**包含内容**:

- 访客意图识别功能需求
- 快递看护模式功能需求
- 个性化欢迎词功能需求
- 数据存储需求

---

### 🔷 问题分析文档

#### 受影响文件最终报告.md

**用途**: Git checkout 影响文件报告  
**状态**: 问题尚未解决  
**包含内容**:

- 受影响文件列表
- 问题分析
- 待处理事项

---

### 🔷 变更日志

#### CHANGELOG.md

**用途**: 项目变更历史记录  
**包含内容**:

- 功能更新记录
- Bug 修复记录
- 协议变更记录
- 重要里程碑

---

## 📂 已归档文档

已完成的开发任务相关文档已归档到 `docs/completed/` 目录，按类别组织：

- **face-recognition/** - 人脸识别功能文档
- **smart-doorlock/** - 智能门锁基础功能文档
- **deprecated-protocols/** - 旧版本协议文档
- **protocol-upgrade/** - 协议升级过程文档
- **seq-id-fix/** - seq_id 机制修复文档
- **database-optimization/** - 数据库优化文档
- **bug-fixes/** - Bug 修复文档
- **task-summaries/** - 任务完成总结
- **code-analysis/** - 代码分析与修复文档

详见：[docs/completed/README.md](../completed/README.md)

---

## 🔍 快速查找指南

### 我想了解...

| 需求                   | 推荐文档                                             |
| ---------------------- | ---------------------------------------------------- |
| ESP32 如何与服务器通信 | `智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md` |
| App 如何与服务器通信   | `智能猫眼门锁系统-服务器与App通信协议规范-v2.5.md`   |
| App 协议升级指南       | `app-protocol-v2.5-update-checklist-final.md`        |
| App 协议变更分析       | `app-protocol-v2.4-update-analysis.md`               |
| 服务器架构设计         | `智能猫眼门锁系统-服务器端架构说明.md`               |
| ESP32 数据处理流程     | `esp32-data-processing-flow.md`                      |
| ESP32 数据处理详细分析 | `esp32-data-processing-detailed-analysis.md`         |
| App 数据处理流程       | `app-data-processing-detailed-analysis.md`           |
| 代码实现细节           | `xiaozhi-server-detailed-analysis.md`                |
| seq_id 如何使用        | `seq_id使用规范与注意事项.md`                        |
| App 离线连接机制       | `app-offline-connection-README.md`                   |
| 门锁 AI 功能 API       | `doorlock-api-documentation.md`                      |
| 门锁配置指南           | `doorlock-configuration-guide.md`                    |
| 门锁故障排查           | `doorlock-troubleshooting-guide.md`                  |
| 门锁提示词自定义       | `doorlock-prompt-customization-guide.md`             |
| 统一模式使用指南       | `unified-mode-user-guide.md`                         |
| 统一模式迁移指南       | `unified-mode-migration-guide.md`                    |
| 视觉拍照功能           | `esp32-vision-guide.md`                              |
| MCP Vision 详细分析    | `mcp-vision-detailed-analysis.md`                    |
| VLLM 连续对话          | `vllm-continuous-dialogue-implementation.md`         |
| VLLM 实现分析          | `vllm-implementation-analysis.md`                    |
| VLLM 测试计划          | `vllm-intent-simulation-test-plan.md`                |
| Dialogue 类使用        | `dialogue-class-explanation.md`                      |
| 项目变更历史           | `CHANGELOG.md`                                       |

---

## 📝 文档维护规范

### 文档更新原则

1. **协议文档**: 协议变更时必须同步更新，保持版本号一致
2. **架构文档**: 重大架构调整时更新
3. **功能文档**: 新增功能或流程变更时更新
4. **CHANGELOG**: 每次重要变更都要记录

### 文档归档规则

当文档对应的任务已完成且不再频繁修改时，应归档到 `docs/completed/` 目录：

- 协议升级过程文档
- Bug 修复报告
- 任务完成总结
- 代码分析报告
- 旧版本协议文档
- 已完成功能的需求和测试文档

### 文档命名规范

- 中文文档：使用中文命名，描述清晰
- 英文文档：使用小写字母和连字符，如 `smart-doorlock-test-guide.md`
- 版本号：在文件名或文档标题中明确标注版本号

---

## 🔧 工具脚本

工具脚本已移至 `main/xiaozhi-server/scripts/` 目录：

- `restore-timeout-mechanism.sh` / `restore-timeout-mechanism.bat` - 恢复 ESP32 连接超时机制

---

## 🆘 需要帮助？

- 查看 [CHANGELOG.md](CHANGELOG.md) 了解最新变更
- 查看 [docs/completed/README.md](../completed/README.md) 了解历史文档
- 联系项目维护者获取更多信息
