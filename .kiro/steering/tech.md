---
inclusion: always
---

# xiaozhi-server 技术规范

## 基本信息

- **路径**：`main/xiaozhi-server/`
- **端口**：8000 (WebSocket)、8003 (HTTP)
- **语言**：Python 3.10

## 代码规范

**必须遵守：**
- 使用 `async/await` 编写异步代码
- 使用 `loguru` 记录日志
- 使用 `ruamel.yaml` 解析 YAML 配置
- 添加类型注解
- 配置项放入 `config.yaml`

**禁止：**
- 使用 `print` 或标准 `logging`
- 同步阻塞调用
- 硬编码配置值

## 数据存储

- **MySQL**：持久化存储
- **Redis**：缓存和会话
