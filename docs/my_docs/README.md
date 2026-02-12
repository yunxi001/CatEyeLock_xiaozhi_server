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

#### 智能猫眼门锁系统-服务器与App通信协议规范-v2.4.md

**用途**: App 与服务器之间的 WebSocket 通信协议规范（当前版本）  
**包含内容**:

- App 连接认证机制
- 命令下发与查询接口
- 设备状态推送机制
- 消息确认机制（seq_id + server_ack）
- 统一错误码规范（0-10）
- 密码查询接口
- 媒体文件下载规范

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

---

### 🔷 开发指南文档

#### 智能门锁项目开发文档.md

**用途**: 智能门锁功能开发指南  
**包含内容**:

- 功能模块说明
- 开发规范
- 接口说明
- 测试方法

#### project-analysis.md

**用途**: 项目整体分析文档  
**包含内容**:

- 项目背景
- 技术选型
- 模块划分
- 开发计划

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

#### database_empty_tables_explanation.md

**用途**: 数据库空表设计说明文档  
**包含内容**:

- 空表的设计目的
- 字段含义说明
- 使用场景示例
- 数据来源说明

---

### 🔷 功能扩展文档

#### smart-doorlock-protocol-extension.md

**用途**: 智能门锁协议扩展说明  
**包含内容**:

- 新增消息类型
- 扩展字段说明
- 向后兼容性
- 实现建议

#### face-recognition-requirements.md

**用途**: 人脸识别功能需求文档  
**包含内容**:

- 功能需求
- 技术方案
- 接口设计
- 性能要求

---

### 🔷 测试与使用指南

#### smart-doorlock-test-guide.md

**用途**: 智能门锁功能测试指南  
**包含内容**:

- 测试环境搭建
- 测试用例
- 测试工具使用
- 问题排查

#### smart-doorlock-usage-guide.md

**用途**: 智能门锁功能使用指南  
**包含内容**:

- 功能介绍
- 使用流程
- 配置说明
- 常见问题

---

### 🔷 App 连接相关文档

#### app-offline-connection-README.md

**用途**: App 离线连接功能说明  
**包含内容**:

- 离线连接机制
- 状态推送逻辑
- 日志输出说明
- 使用示例

#### app-connection-example.html

**用途**: App WebSocket 连接测试页面  
**包含内容**:

- 连接示例代码
- 消息发送测试
- 响应接收展示
- 调试工具

---

### 🔷 工具脚本

#### restore-timeout-mechanism.sh / restore-timeout-mechanism.bat

**用途**: 恢复 ESP32 连接超时机制的脚本  
**说明**: 用于在需要时快速恢复超时检测功能

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
| App 如何与服务器通信   | `智能猫眼门锁系统-服务器与App通信协议规范-v2.4.md`   |
| 服务器架构设计         | `智能猫眼门锁系统-服务器端架构说明.md`               |
| ESP32 数据处理流程     | `esp32-data-processing-flow.md`                      |
| ESP32 数据处理详细分析 | `esp32-data-processing-detailed-analysis.md`         |
| App 数据处理流程       | `app-data-processing-detailed-analysis.md`           |
| 代码实现细节           | `xiaozhi-server-detailed-analysis.md`                |
| seq_id 如何使用        | `seq_id使用规范与注意事项.md`                        |
| 如何测试门锁功能       | `smart-doorlock-test-guide.md`                       |
| 如何使用门锁功能       | `smart-doorlock-usage-guide.md`                      |
| App 离线连接机制       | `app-offline-connection-README.md`                   |
| 项目变更历史           | `CHANGELOG.md`                                       |

---

## 📝 文档维护规范

### 文档更新原则

1. **协议文档**: 协议变更时必须同步更新，保持版本号一致
2. **架构文档**: 重大架构调整时更新
3. **开发指南**: 新增功能或流程变更时更新
4. **CHANGELOG**: 每次重要变更都要记录

### 文档归档规则

当文档对应的任务已完成且不再频繁修改时，应归档到 `docs/completed/` 目录：

- 协议升级过程文档
- Bug 修复报告
- 任务完成总结
- 代码分析报告
- 旧版本协议文档

### 文档命名规范

- 中文文档：使用中文命名，描述清晰
- 英文文档：使用小写字母和连字符，如 `smart-doorlock-test-guide.md`
- 版本号：在文件名或文档标题中明确标注版本号

---

## 🆘 需要帮助？

- 查看 [CHANGELOG.md](CHANGELOG.md) 了解最新变更
- 查看 [docs/completed/README.md](../completed/README.md) 了解历史文档
- 联系项目维护者获取更多信息
