# 需求文档 - 服务器端协议升级 v5.0 到 v5.2

## 简介

本文档定义了智能猫眼门锁系统服务器端从协议 v5.0 升级到 v5.2 的功能需求。ESP32 端已完成 v5.2 升级，服务器端需要适配新协议以保持兼容性。

## 术语表

- **Server**: xiaozhi-server，Python 后端服务，负责 ESP32 与 App 之间的消息转发和业务处理
- **ESP32**: 智能门锁设备端，通过 WebSocket 连接到 Server
- **App**: 移动应用端，通过 WebSocket 连接到 Server
- **seq_id**: 消息序列 ID，用于消息追踪和防重放，格式为 `时间戳_序号`
- **msg_id**: 旧版消息 ID 字段名，v5.2 中统一改为 seq_id
- **esp32_ack**: ESP32 收到命令后立即发送的第一级确认，表示"命令已收到，开始处理"
- **ack**: 命令执行完成后发送的第二级确认，表示"命令执行完成"，携带执行结果
- **统一错误码**: 所有层（Server、ESP32、STM32）共用的错误码体系（0-10）

## 需求

### 需求 1: 两级确认机制支持

**用户故事**: 作为服务器开发者，我希望支持 ESP32 的两级确认机制，以便 App 能够区分"命令已送达"和"命令已完成"两个状态。

#### 验收标准

1. WHEN ESP32 发送 `esp32_ack` 消息 THEN Server SHALL 解析该消息并转发给关联的 App
2. WHEN `esp32_ack` 消息包含 `seq_id` 字段 THEN Server SHALL 保留该字段并原样转发
3. WHEN `esp32_ack` 消息的 `code` 字段为 0 THEN Server SHALL 记录命令已被 ESP32 接收
4. WHEN `esp32_ack` 消息的 `code` 字段非 0 THEN Server SHALL 记录 ESP32 拒绝接收命令
5. WHEN ESP32 发送 `ack` 消息 THEN Server SHALL 解析该消息并转发给关联的 App
6. WHEN `ack` 消息包含 `seq_id` 和 `code` 字段 THEN Server SHALL 根据 code 判断命令执行结果

### 需求 2: 消息 ID 字段名统一

**用户故事**: 作为服务器开发者，我希望统一使用 `seq_id` 字段名，以便与 ESP32 v5.2 协议保持一致。

#### 验收标准

1. WHEN Server 下发命令到 ESP32 THEN Server SHALL 使用 `seq_id` 字段名
2. WHEN Server 接收 ESP32 上报消息 THEN Server SHALL 解析 `seq_id` 字段
3. WHEN Server 转发消息到 App THEN Server SHALL 保留 `seq_id` 字段名
4. WHEN Server 生成新消息 THEN Server SHALL 使用 `seq_id` 字段名
5. WHEN 消息缺少 `seq_id` 字段 THEN Server SHALL 记录错误日志并拒绝处理

### 需求 3: 统一错误码支持

**用户故事**: 作为服务器开发者，我希望使用统一的错误码体系（0-10），以便 App 端能够统一处理错误，无需关心错误来源。

#### 验收标准

1. WHEN Server 接收到 ESP32 的 `ack` 或 `esp32_ack` 消息 THEN Server SHALL 验证 `code` 字段在 0-10 范围内
2. WHEN Server 检测到设备离线 THEN Server SHALL 返回 code=1 的错误
3. WHEN Server 检测到参数错误 THEN Server SHALL 返回 code=3 的错误
4. WHEN Server 检测到用户未认证 THEN Server SHALL 返回 code=8 的错误
5. WHEN Server 检测到重复的 seq_id THEN Server SHALL 返回 code=9 的错误
6. WHEN Server 遇到未知错误 THEN Server SHALL 返回 code=10 的错误

### 需求 4: log_report 格式变更支持

**用户故事**: 作为服务器开发者，我希望支持新版 `log_report` 格式（status + lock_time），以便正确处理设备锁定状态。

#### 验收标准

1. WHEN Server 接收到 `log_report` THEN Server SHALL 解析 `status` 字段（success/fail/locked）
2. WHEN `status` 为 `locked` THEN Server SHALL 解析 `lock_time` 字段（剩余锁定时间，单位：分钟）
3. WHEN `status` 为 `success` 或 `fail` THEN Server SHALL 验证 `lock_time` 字段为 0
4. WHEN Server 存储开锁日志到数据库 THEN Server SHALL 同时存储 `status` 和 `lock_time` 字段
5. WHEN Server 转发 `log_report` 到 App THEN Server SHALL 保留完整的消息格式
6. WHEN `status` 字段缺失或无效 THEN Server SHALL 记录错误日志并拒绝处理

### 需求 5: 新增消息类型处理

**用户故事**: 作为服务器开发者，我希望支持 v5.2 新增的消息类型，以便提供完整的功能支持。

#### 验收标准

1. WHEN ESP32 发送 `esp32_ack` 消息 THEN Server SHALL 解析并转发给 App
2. WHEN ESP32 发送 `door_opened_report` 消息 THEN Server SHALL 解析 method 和 source 字段
3. WHEN Server 接收到 `door_opened_report` THEN Server SHALL 存储到数据库并转发给 App
4. WHEN ESP32 发送 `password_report` 消息 THEN Server SHALL 解析 password 字段
5. WHEN Server 接收到 `password_report` THEN Server SHALL 转发给请求查询的 App，但不存储到数据库
6. WHEN App 发送 `query` 命令 THEN Server SHALL 构建 query 消息并下发给 ESP32
7. WHEN `query` 命令的 command 为 `sensors` THEN Server SHALL 等待 ESP32 返回传感器数据
8. WHEN `query` 命令的 command 为 `status` THEN Server SHALL 等待 ESP32 返回设备状态

### 需求 6: 新增事件类型支持

**用户故事**: 作为服务器开发者，我希望支持 v5.2 新增的事件类型，以便 App 能够接收到完整的设备事件。

#### 验收标准

1. WHEN ESP32 上报 `event_report` 且 event 为 `door_closed` THEN Server SHALL 解析并转发给 App
2. WHEN ESP32 上报 `event_report` 且 event 为 `lock_success` THEN Server SHALL 解析并转发给 App
3. WHEN ESP32 上报 `event_report` 且 event 为 `bolt_alarm` THEN Server SHALL 解析并转发给 App
4. WHEN Server 接收到新增事件类型 THEN Server SHALL 存储到数据库的 device_events 表
5. WHEN Server 转发新增事件到 App THEN Server SHALL 保留原始事件类型和参数

### 需求 7: user_mgmt_result 特殊成功场景支持

**用户故事**: 作为服务器开发者，我希望支持 `user_mgmt_result` 的特殊成功场景，以便 App 能够正确处理"已存在"和"自动分配 ID"的情况。

#### 验收标准

1. WHEN `user_mgmt_result` 的 result 为 true 且 msg 为 "Already exists" THEN Server SHALL 识别为"指纹/NFC 已存在"场景
2. WHEN `user_mgmt_result` 的 result 为 true 且 msg 为 "ID occupied, auto assigned" THEN Server SHALL 识别为"ID 被占用自动分配"场景
3. WHEN Server 识别到特殊成功场景 THEN Server SHALL 在转发给 App 时保留原始 msg 字段
4. WHEN Server 识别到特殊成功场景 THEN Server SHALL 记录日志以便调试

### 需求 8: 数据库表结构更新

**用户故事**: 作为服务器开发者，我希望更新数据库表结构以支持新协议的字段，以便完整存储设备数据。

#### 验收标准

1. WHEN Server 启动时 THEN Server SHALL 检查 unlock_logs 表是否包含 `status` 和 `lock_time` 字段
2. WHEN unlock_logs 表缺少新字段 THEN Server SHALL 执行数据库迁移脚本添加字段
3. WHEN Server 创建 door_opened_logs 表 THEN Server SHALL 包含 device_id、method、source、created_at 字段
4. WHEN Server 更新 device_events 表 THEN Server SHALL 支持新增的事件类型（door_closed、lock_success、bolt_alarm）
5. WHEN 数据库迁移失败 THEN Server SHALL 记录错误日志并继续运行（降级为仅转发模式）

### 需求 9: 消息处理健壮性

**用户故事**: 作为服务器开发者，我希望增强消息处理的健壮性，以便在遇到异常消息时能够优雅降级。

#### 验收标准

1. WHEN Server 接收到格式错误的 JSON 消息 THEN Server SHALL 记录错误日志并丢弃该消息
2. WHEN Server 接收到未知类型的消息 THEN Server SHALL 记录警告日志并丢弃该消息
3. WHEN Server 接收到缺少必需字段的消息 THEN Server SHALL 记录错误日志并拒绝处理
4. WHEN 数据库操作失败 THEN Server SHALL 记录错误日志但继续转发消息到 App
5. WHEN 转发消息到 App 失败 THEN Server SHALL 记录错误日志并重试最多 3 次

### 需求 10: 日志与监控增强

**用户故事**: 作为服务器运维人员，我希望增强日志记录和监控能力，以便快速定位协议升级相关的问题。

#### 验收标准

1. WHEN Server 接收到 `esp32_ack` THEN Server SHALL 记录日志包含 seq_id 和 code
2. WHEN Server 接收到新版 `log_report` THEN Server SHALL 记录日志包含 status 和 lock_time
3. WHEN Server 接收到新增消息类型 THEN Server SHALL 记录日志标注消息类型
4. WHEN Server 检测到协议版本不匹配 THEN Server SHALL 记录警告日志
5. WHEN Server 转发消息失败 THEN Server SHALL 记录错误日志包含失败原因和重试次数

## 非功能需求

### 性能需求

1. 消息处理延迟：Server 接收到消息后应在 50ms 内完成解析和转发
2. 并发连接数：Server 应支持至少 1000 个并发 ESP32 连接
3. 数据库写入性能：开锁日志写入应在 100ms 内完成

### 可靠性需求

1. 消息不丢失：Server 应确保所有消息都被正确转发或存储
2. 故障恢复：Server 重启后应能自动恢复连接状态
3. 数据一致性：数据库操作失败不应影响消息转发

### 安全需求

1. 防重放攻击：Server 应检测并拒绝重复的 seq_id
2. 权限验证：Server 应验证 App 和 ESP32 的身份
3. 敏感数据保护：密码查询结果不应存储到数据库

## 优先级

### P0 - 必须实现（核心功能）

1. 需求 1: 两级确认机制支持
2. 需求 2: 消息 ID 字段名统一
3. 需求 4: log_report 格式变更支持
4. 需求 5: 新增消息类型处理

### P1 - 建议实现（功能完整）

1. 需求 3: 统一错误码支持
2. 需求 6: 新增事件类型支持
3. 需求 8: 数据库表结构更新
4. 需求 9: 消息处理健壮性

### P2 - 可选实现（增强功能）

1. 需求 7: user_mgmt_result 特殊成功场景支持
2. 需求 10: 日志与监控增强

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-01-17 | 初始版本，基于协议升级需求文档 v1.0 |

---

**文档维护者**: 毕业设计项目组  
**最后更新**: 2026-01-17
