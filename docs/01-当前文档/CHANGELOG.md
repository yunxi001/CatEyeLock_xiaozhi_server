# xiaozhi-server 变更日志

本文档记录 xiaozhi-server 项目的重要变更和更新。

---

## 2025-05-10 23:45

### 新增文件

- **文件**: `main/xiaozhi-server/check_doorlock_users.py`
- **位置**: 项目根目录下的数据库检查脚本

### 变更内容

新增了 `doorlock_users` 表数据检查脚本，包含以下功能：

1. 检查 `doorlock_users` 表是否存在
2. 统计表中的总记录数
3. 显示前 5 条记录的关键信息（device_id, user_id, name）
4. 查询特定设备（e8:f6:0a:83:8f:50）的用户数据
5. 检查相关表（persons 表）的记录数
6. 显示 `doorlock_users` 表的完整结构

### 实现功能

提供了一个独立的数据库诊断工具，用于：

- 验证门锁用户数据的完整性
- 排查用户数据缺失问题
- 检查数据库迁移是否成功
- 辅助开发调试和问题定位

### 技术细节

- 使用 `Database` 类连接 MySQL
- 通过 `information_schema` 检查表存在性
- 使用字典游标返回结构化数据
- 包含详细的输出格式化和错误提示

---

## 2026-05-10 23:45

### 修改文件

- `main/xiaozhi-server/core/handle/textHandler/commandProxyHandler.py`

### 修改位置

- `handleCommandProxy` 函数中，App 转发命令到 ESP32 的处理逻辑部分（第 453-467 行）

### 变更内容

在 App 转发用户管理命令（add/del/clear）到 ESP32 之前，新增命令信息缓存逻辑：

- 检测到用户管理命令时，将命令详情缓存到 `esp32_conn.last_user_mgmt_cmd` 属性
- 缓存信息包括：时间戳、命令类别、命令类型、用户名、用户ID、序列号
- 添加调试日志记录缓存操作

### 实现功能

**用户管理命令缓存机制**：为后续实现用户管理操作审计追踪奠定基础。当 App 发送用户管理命令（添加/删除/清空用户）时，先将命令信息缓存起来，等收到 ESP32 的响应后，可以将完整的操作记录（包括命令发起方、执行结果、时间戳等）保存到数据库，实现完整的操作审计链路。


---

## 2026-05-11 00:15

### 新增文件

- **文件**: `main/xiaozhi-server/check_visitor_intents.py`
- **位置**: 项目根目录下的访客意图数据检查脚本

### 变更内容

新增了访客意图数据检查和测试数据插入脚本，包含以下功能：

1. 检查数据库中现有的访客意图记录
2. 如果没有数据，自动插入 6 条真实场景的测试数据
3. 验证插入结果并显示详细信息

### 实现功能

提供了一个独立的测试工具，用于：

- **数据检查**：查询并显示现有访客意图记录（最多 10 条）
- **测试数据生成**：自动插入 6 种典型访客场景的测试数据
  - 快递员送快递（顺丰）
  - 外卖员送餐（美团）
  - 朋友来访约饭
  - 推销员推销净水器
  - 物业维修空调预约
  - 邻居借工具
- **数据验证**：插入后自动验证数据完整性

### 技术细节

- 使用 `DoorlockDatabase` 类进行数据库操作
- 使用 `VisitorIntent` 模型构建测试数据
- 每条测试数据包含完整的对话历史和意图分析
- 包含意图类型（delivery/visit/sales/maintenance）和重要备注
- 使用异步方式执行数据库操作
- 提供详细的控制台输出和进度提示

### 应用场景

- 开发阶段快速生成测试数据
- 验证访客意图识别功能
- 测试 App 端访客意图查询接口
- 演示访客意图分析能力


---

## 2026-05-11 23:45

### 修改文件
- `main/xiaozhi-server/core/app_connection.py`

### 修改位置
- `AppConnectionHandler._push_history_data_delayed()` 方法

### 变更内容
- 在延迟推送历史数据的文档注释中添加"最近 5 条访客意图通知"说明
- 在推送逻辑中新增 `await self._push_recent_visitor_intents(limit=5)` 调用

### 功能说明
完善 App 初始连接推送流程，增加访客意图通知的历史数据推送。现在 App 端在连接成功后会自动接收：
- P0（立即）：设备在线状态 + 传感器状态
- P1（延迟1秒）：最近 5 条开锁日志 + 最近 5 条到访记录 + **最近 5 条访客意图通知**

这使得 App 端能够在初始化时获得更完整的设备历史状态信息。


---

## 2025-01-XX 新增访客意图推送测试工具

### 新增文件
- `main/xiaozhi-server/test_visitor_intent_push.py`

### 修改位置
- 新增完整测试脚本文件

### 修改时间
- 2025-01-XX

### 变更内容
1. **新增测试脚本**：创建 `test_visitor_intent_push.py` 测试工具
2. **实现功能**：
   - 模拟 App 客户端 WebSocket 连接
   - 实现完整的认证流程（hello 消息）
   - 接收并分类显示所有推送消息类型：
     - `hello`：认证响应
     - `device_status`：设备在线/离线状态
     - `status_report`：传感器状态（电池、光照、门锁、灯光）
     - `log_report`：开锁日志
     - `visit_notification`：到访记录
     - `visitor_intent_notification`：访客意图通知（重点测试）
   - 支持超时控制（10秒）
   - 统计并显示接收到的消息数量

### 功能说明
此测试工具用于验证 `app_connection.py` 中实现的初始推送功能，特别是 `_push_recent_visitor_intents()` 方法推送的访客意图通知。通过运行此脚本，可以：
- 验证 App 连接认证流程是否正常
- 检查服务器是否正确推送历史数据（P0/P1 优先级）
- 确认访客意图通知的数据结构和内容完整性
- 调试推送消息的时序和格式

### 使用方法
```bash
cd main/xiaozhi-server
python test_visitor_intent_push.py
```

### 相关文件
- `core/app_connection.py`：App 连接处理器，实现推送逻辑
- `core/providers/doorlock/doorlock_database.py`：访客意图数据查询


---

## 2026-05-11 23:45 - 完善访客意图通知推送逻辑

**修改文件**：`main/xiaozhi-server/core/app_connection.py`

**修改位置**：`AppConnectionHandler._push_recent_visitor_intents()` 方法

**变更内容**：
1. 按协议 v2.5 规范完善访客意图通知消息结构
2. 为 `intent_summary` 添加默认值处理（包含 intent_type, summary, important_notes, ai_analysis）
3. 为 `dialogue_history` 添加空列表默认值
4. 新增快递警报（package_check）查询逻辑：
   - 通过 `doorlock_db.get_package_alerts()` 查询警报
   - 根据 `session_id` 匹配关联的快递警报
   - 将匹配的警报信息（threat_level, action, description）添加到通知中
5. 增强日志输出：
   - 记录 intent_type
   - 记录是否包含人员信息（has_person_info）
   - 记录是否包含快递检查（has_package_check）

**实现功能**：
- 确保 App 端接收到的访客意图通知消息结构完整，避免因空值导致的解析错误
- 支持推送关联的快递看护警报信息，实现快递安全监控功能
- 提升数据推送的健壮性和可观测性，便于问题排查

**影响范围**：
- App 端初始连接时的历史数据推送
- 访客意图通知的消息格式
- 快递看护功能的数据展示


---

## 2026-05-11 23:45

### 修复 PIR 事件重复触发问题

**修改文件**：`core/handle/textHandler/eventReportHandler.py`

**修改位置**：`EventReportHandler._handle_pir_event()` 方法

**变更内容**：
1. 新增 `pir_triggered` 标志检查机制，防止 PIR 事件达到阈值后重复触发
2. 在步骤 5 设置双重标志：`conn.pir_triggered = True` 和 `conn.visitor_processing = True`
3. 在步骤 6 使用 `try-finally` 结构包裹人脸识别触发逻辑
4. 在 `finally` 块中清除 `visitor_processing` 标志，确保下次访客可以正常触发
5. 添加调试日志记录标志状态变化

**实现功能**：
- 修复访客在门前停留时 PIR 事件重复触发人脸识别的问题
- 确保每次访客停留只触发一次人脸识别流程（首次达到阈值时）
- 通过 `try-finally` 保证异常情况下标志也能被正确清除
- 避免资源浪费和重复的访客处理流程

**影响范围**：PIR 事件处理逻辑，访客检测流程


---

## 2026-05-11 23:50

### 简化访客意图处理清理逻辑

**修改文件**：`core/handle/doorlock_intent_handler.py`

**修改位置**：`DoorlockIntentHandler.handle_visitor_intent()` 方法的 `finally` 块

**变更内容**：
- 删除了 `finally` 块中清除访客处理标志的代码
- 移除了 `conn.visitor_processing = False` 的设置逻辑
- 移除了相关的调试日志输出

**实现功能**：
- 简化访客意图处理的清理逻辑
- 将访客处理标志的生命周期管理统一到 PIR 事件处理器中
- 避免多处清除标志导致的状态管理混乱
- 确保访客处理标志由触发方（PIR 事件处理器）负责清除，遵循"谁设置谁清除"的原则

**影响范围**：访客意图处理流程，访客处理标志管理

## 2025-05-18 禁用无语音超时断开连接

### 修改文件
- `main/xiaozhi-server/core/handle/receiveAudioHandle.py`

### 修改位置
- `receiveAudioHandle.py` 中音频接收处理逻辑，无语音超时检查部分（约第97-103行）

### 变更内容
- 将 `close_connection_no_voice_time` 从配置文件读取（默认120秒）改为固定值 `999999` 秒（约11.5天）
- 移除了 `conn.config.get("close_connection_no_voice_time", 120)` 的配置读取逻辑

### 实现功能
- 禁用无语音超时自动断开连接的机制，使设备连接在长时间无语音输入时不会被自动断开，适用于需要保持长连接的场景（如门锁设备持续监听）
