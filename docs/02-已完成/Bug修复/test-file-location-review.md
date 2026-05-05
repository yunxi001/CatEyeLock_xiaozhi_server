# 暂存文件位置审查报告

## 概述

本报告分析所有暂存的非 md 文件，评估它们的用途、是否需要提交以及存放位置是否合理。

---

## 1. 核心代码文件（✓ 必须提交）

### 1.1 配置文件

| 文件          | 位置                   | 用途       | 评估                 |
| ------------- | ---------------------- | ---------- | -------------------- |
| `config.yaml` | `main/xiaozhi-server/` | 主配置文件 | ✓ 位置正确，必须提交 |

**说明**：主配置文件，包含服务器、日志等基础配置，是项目运行的核心配置。

### 1.2 业务逻辑代码

| 文件                         | 位置                       | 用途               | 评估                 |
| ---------------------------- | -------------------------- | ------------------ | -------------------- |
| `doorlock_intent_handler.py` | `core/handle/`             | 意图识别对话处理器 | ✓ 位置正确，必须提交 |
| `eventReportHandler.py`      | `core/handle/textHandler/` | 事件报告处理器     | ✓ 位置正确，必须提交 |
| `http_server.py`             | `core/`                    | HTTP API 服务器    | ✓ 位置正确，必须提交 |
| `__init__.py`                | `core/providers/doorlock/` | 模块导出定义       | ✓ 位置正确，必须提交 |
| `models.py`                  | `core/providers/doorlock/` | 数据模型定义       | ✓ 位置正确，必须提交 |

**说明**：这些是智能门锁 AI 功能的核心业务代码，遵循项目架构规范。

---

## 2. 数据库迁移文件（✓ 应该提交）

| 文件                              | 位置          | 用途           | 评估                 |
| --------------------------------- | ------------- | -------------- | -------------------- |
| `run_doorlock_ai_migration.py`    | `migrations/` | 执行数据库迁移 | ✓ 位置正确，应该提交 |
| `verify_doorlock_ai_migration.py` | `migrations/` | 验证迁移结果   | ✓ 位置正确，应该提交 |

**说明**：

- 数据库迁移脚本是项目部署的重要组成部分
- 验证脚本帮助确保迁移成功执行
- 这些文件应该和 SQL 迁移文件一起提交

---

## 3. 运维脚本（✓ 可以提交）

| 文件                                | 位置       | 用途                | 评估                 |
| ----------------------------------- | ---------- | ------------------- | -------------------- |
| `verify_doorlock_infrastructure.py` | `scripts/` | 验证基础设施完整性  | ✓ 位置正确，可以提交 |
| `verify_doorlock_prompts.py`        | `scripts/` | 验证提示词配置      | ✓ 位置正确，可以提交 |
| `verify_task7_files.py`             | `scripts/` | 验证任务7文件完整性 | ⚠ 临时脚本，建议移除 |

**说明**：

- 前两个是通用的运维验证工具，可以保留
- `verify_task7_files.py` 是特定任务的临时验证脚本，建议移到文档目录或删除

---

## 4. 测试文件（✓ 必须提交）

### 4.1 单元测试（test/ 目录）

| 文件                       | 位置             | 用途           | 评估       |
| -------------------------- | ---------------- | -------------- | ---------- |
| `test_database.py`         | `test/doorlock/` | 数据库服务测试 | ✓ 位置正确 |
| `test_face_recognition.py` | `test/doorlock/` | 人脸识别测试   | ✓ 位置正确 |
| `test_greeting.py`         | `test/doorlock/` | 欢迎词测试     | ✓ 位置正确 |
| `test_intent_handler.py`   | `test/doorlock/` | 意图处理器测试 | ✓ 位置正确 |
| `test_package_guard.py`    | `test/doorlock/` | 看护模式测试   | ✓ 位置正确 |
| `test_session_manager.py`  | `test/doorlock/` | 会话管理器测试 | ✓ 位置正确 |
| `test_tools.py`            | `test/doorlock/` | 工具函数测试   | ✓ 位置正确 |

### 4.2 集成测试（test/integration/ 目录）

| 文件                             | 位置                | 用途                   | 评估       |
| -------------------------------- | ------------------- | ---------------------- | ---------- |
| `conftest.py`                    | `test/integration/` | pytest 配置和 fixtures | ✓ 位置正确 |
| `test_concurrent_visitors.py`    | `test/integration/` | 并发访客测试           | ✓ 位置正确 |
| `test_face_recognition_retry.py` | `test/integration/` | 人脸识别重试测试       | ✓ 位置正确 |
| `test_package_guard_flow.py`     | `test/integration/` | 看护流程测试           | ✓ 位置正确 |
| `test_visitor_flow.py`           | `test/integration/` | 访客流程测试           | ✓ 位置正确 |

### 4.3 根目录测试文件（⚠ 位置不当）

| 文件                                | 位置                   | 用途         | 评估                |
| ----------------------------------- | ---------------------- | ------------ | ------------------- |
| `test_doorlock_integration.py`      | `main/xiaozhi-server/` | 集成测试脚本 | ⚠ 应移到 test/ 目录 |
| `test_doorlock_deep_integration.py` | `main/xiaozhi-server/` | 深度集成测试 | ⚠ 应移到 test/ 目录 |

**说明**：

- `test/` 目录下的测试文件位置正确，遵循 pytest 标准结构
- 根目录的两个测试文件应该移到 `test/integration/` 目录

---

## 5. 文档文件（已排除 md 文件）

所有 `.md` 文档文件已在 git 命令中排除，不在本次审查范围内。

---

## 建议操作

### 立即操作

1. **移动根目录测试文件**

   ```bash
   git mv main/xiaozhi-server/test_doorlock_integration.py main/xiaozhi-server/test/integration/
   git mv main/xiaozhi-server/test_doorlock_deep_integration.py main/xiaozhi-server/test/integration/
   ```

2. **移除临时验证脚本**
   ```bash
   git reset HEAD main/xiaozhi-server/scripts/verify_task7_files.py
   # 可选：移到文档目录
   mv main/xiaozhi-server/scripts/verify_task7_files.py docs/completed/task-summaries/
   ```

### 可选操作

3. **检查 STAGED_FILES_ANALYSIS.md**
   - 这个文件看起来是临时分析文件
   - 建议移到 `docs/` 目录或删除

---

## 文件分类统计

| 类别       | 数量 | 是否提交              |
| ---------- | ---- | --------------------- |
| 核心代码   | 6    | ✓ 必须                |
| 数据库迁移 | 2    | ✓ 应该                |
| 运维脚本   | 3    | ✓ 可以（1个建议移除） |
| 单元测试   | 7    | ✓ 必须                |
| 集成测试   | 5    | ✓ 必须                |
| 根目录测试 | 2    | ⚠ 需要移动位置        |

---

## 总结

### 位置正确的文件（23个）

- 核心业务代码：6个
- 数据库迁移：2个
- 运维脚本：2个（排除临时脚本）
- test/ 目录测试：12个

### 需要调整的文件（3个）

1. `test_doorlock_integration.py` → 移到 `test/integration/`
2. `test_doorlock_deep_integration.py` → 移到 `test/integration/`
3. `verify_task7_files.py` → 移除或移到文档目录

### 代码质量评估

- ✓ 遵循项目架构规范（Provider 模式、异步编程）
- ✓ 使用类型注解
- ✓ 测试覆盖完整（单元测试 + 集成测试）
- ✓ 配置文件结构清晰
- ⚠ 部分测试文件位置需要调整

---

生成时间：2026-02-13
