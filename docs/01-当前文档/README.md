# 📖 当前文档

> 这里是 xiaozhi-server 当前正在维护的核心文档

## 📋 文档分类

### 🏗️ 架构与协议

- [服务器端架构说明](智能猫眼门锁系统-服务器端架构说明.md)
- [xiaozhi-server详细分析](xiaozhi-server-detailed-analysis.md)
- [项目分析](project-analysis.md)

### 📡 通信协议

- [ESP32与服务器通信协议规范 v5.2](智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md)
- [服务器与App通信协议规范 v2.5](智能猫眼门锁系统-服务器与App通信协议规范-v2.5.md)
- [消息ID机制与工作流程](消息ID机制与工作流程.md)
- [seq_id使用规范与注意事项](seq_id使用规范与注意事项.md)

### 🔧 API文档

- [门锁API文档](doorlock-api-documentation.md)
- [门锁VLLM API参考](doorlock-vllm-api-reference.md)
- [门锁意图处理器API参考](doorlock-intent-handler-api-reference.md)

### ⚙️ 配置指南

- [门锁配置指南](doorlock-configuration-guide.md)
- [门锁Prompt自定义指南](doorlock-prompt-customization-guide.md)
- [门锁故障排查指南](doorlock-troubleshooting-guide.md)

### 📱 数据处理分析

- [App数据处理详细分析](app-data-processing-detailed-analysis.md)
- [ESP32数据处理详细分析](esp32-data-processing-detailed-analysis.md)
- [ESP32数据处理流程](esp32-data-processing-flow.md)
- [MCP视觉详细分析](mcp-vision-detailed-analysis.md)

### 🎯 功能实现

- [ESP32视觉指南](esp32-vision-guide.md)
- [VLLM实现分析](vllm-implementation-analysis.md)
- [VLLM连续对话实现](vllm-continuous-dialogue-implementation.md)
- [VLLM意图模拟测试计划](vllm-intent-simulation-test-plan.md)
- [Dialogue类说明](dialogue-class-explanation.md)

### 🔄 迁移与升级

- [统一模式迁移指南](unified-mode-migration-guide.md)
- [统一模式用户指南](unified-mode-user-guide.md)
- [App协议v2.4更新分析](app-protocol-v2.4-update-analysis.md)
- [App协议v2.5更新检查清单](app-protocol-v2.5-update-checklist-final.md)

### 📝 其他

- [App离线连接README](app-offline-connection-README.md)
- [智能门锁AI需求](smart-doorlock-ai-requirements.md)
- [CHANGELOG](CHANGELOG.md)

## 🔄 文档更新流程

1. **新增文档**：直接添加到本目录
2. **更新文档**：修改后更新文档头部的日期
3. **归档文档**：任务完成后移至 `../02-已完成/` 对应分类
4. **同步索引**：更新本 README 和上级 README

## 📌 注意事项

- 本目录文档应保持最新状态
- 过时或已完成的文档应及时归档
- 协议文档更新需同步版本号
- 重要变更需在 CHANGELOG.md 中记录
