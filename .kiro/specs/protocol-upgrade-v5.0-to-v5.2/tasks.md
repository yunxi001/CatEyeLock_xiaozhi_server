# 实现计划 - 服务器端协议升级 v5.0 到 v5.2

## 概述

本实现计划将 xiaozhi-server 从协议 v5.0 升级到 v5.2，主要包括：
1. 新增 3 个消息处理器（esp32_ack、door_opened_report、password_report）
2. 更新 3 个现有处理器（ack、log_report、event_report）
3. 实现命令下发重试机制
4. 数据库表结构更新
5. 错误码常量定义

## 任务列表

- [x] 1. 创建错误码常量定义
  - 创建 `core/constants/error_codes.py` 文件
  - 定义 ErrorCode 类和 ERROR_MESSAGES 字典
  - 实现 `is_valid_error_code()` 和 `get_error_message()` 辅助函数
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 2. 更新消息类型枚举
  - 在 `core/handle/textMessageType.py` 中新增枚举值
  - 添加 ESP32_ACK、DOOR_OPENED_REPORT、PASSWORD_REPORT
  - _Requirements: 1.1, 5.1, 5.4_

- [x] 3. 实现 Esp32AckHandler
  - [x] 3.1 创建 `core/handle/textHandler/esp32AckHandler.py`
    - 继承 TextMessageHandler 抽象基类
    - 实现 message_type 属性返回 ESP32_ACK
    - _Requirements: 1.1, 1.2_
  
  - [x] 3.2 实现 handle() 方法
    - 解析 seq_id、code、msg 字段
    - 验证错误码范围（使用 is_valid_error_code）
    - 记录 DEBUG 级别日志
    - _Requirements: 1.1, 1.2, 10.1_
  
  - [x] 3.3 实现 Future 触发逻辑
    - 检查 conn._pending_esp32_acks 是否存在对应的 Future
    - 如果存在且未完成，调用 future.set_result(code == 0)
    - 用于通知 CommandProxyHandler 停止重试
    - _Requirements: 1.2, 1.3_
  
  - [x] 3.4 注意：不转发给 App
    - esp32_ack 仅用于 Server 内部重试判断
    - 不调用 _forward_to_apps() 方法
    - _Requirements: 1.1, 1.2_

- [x] 4. 实现 DoorOpenedReportHandler
  - [x] 4.1 创建 `core/handle/textHandler/doorOpenedReportHandler.py`
    - 继承 TextMessageHandler 抽象基类
    - 实现 message_type 属性返回 DOOR_OPENED_REPORT
    - _Requirements: 5.1, 5.2_
  
  - [x] 4.2 实现 handle() 方法
    - 解析 ts、data.method、data.source 字段
    - 验证 method 和 source 取值范围
    - 记录 INFO 级别日志
    - _Requirements: 5.2, 5.3_
  
  - [x] 4.3 实现数据库存储
    - 调用 db.save_door_opened_log() 保存到 door_opened_logs 表
    - 数据库失败不影响转发（捕获异常，记录警告）
    - _Requirements: 5.3, 8.5_
  
  - [x] 4.4 实现消息转发
    - 调用 _forward_to_apps() 转发到所有关联的 App
    - _Requirements: 5.3_

- [x] 5. 实现 PasswordReportHandler
  - [x] 5.1 创建 `core/handle/textHandler/passwordReportHandler.py`
    - 继承 TextMessageHandler 抽象基类
    - 实现 message_type 属性返回 PASSWORD_REPORT
    - _Requirements: 5.4, 5.5_
  
  - [x] 5.2 实现 handle() 方法
    - 解析 ts、data.password 字段
    - 记录 INFO 级别日志（不记录密码明文）
    - _Requirements: 5.4, 5.5_
  
  - [x] 5.3 实现消息转发（不存储）
    - 调用 _forward_to_apps() 转发到请求查询的 App
    - 不调用数据库存储方法
    - _Requirements: 5.5_

- [x] 6. 更新 AckHandler
  - [x] 6.1 支持 seq_id 字段
    - 修改 handle() 方法，同时支持 seq_id 和 msg_id
    - 使用 `seq_id = msg_json.get("seq_id") or msg_json.get("msg_id")`
    - _Requirements: 2.1, 2.2, 2.3_
  
  - [x] 6.2 添加错误码验证
    - 导入 `is_valid_error_code` 和 `get_error_message`
    - 验证 code 是否在 0-10 范围内
    - 超出范围记录 WARNING 日志
    - _Requirements: 3.1_
  
  - [x] 6.3 增强日志输出
    - 成功时记录 DEBUG 日志（包含 seq_id）
    - 失败时记录 WARNING 日志（包含 seq_id、code、错误消息）
    - 使用 get_error_message() 获取友好的错误消息
    - _Requirements: 10.1_

- [x] 7. 更新 LogReportHandler
  - [x] 7.1 支持 status 字段
    - 检查 data 中是否包含 status 字段
    - 如果包含，解析 status 和 lock_time
    - _Requirements: 4.1, 4.2, 4.3_
  
  - [x] 7.2 兼容旧版 result 字段
    - 如果没有 status 但有 result，进行转换
    - result=true → status="success", result=false → status="fail"
    - lock_time 默认为 0
    - _Requirements: 4.1_
  
  - [x] 7.3 验证字段取值
    - status 必须是 "success"、"fail" 或 "locked" 之一
    - locked 状态时 lock_time 必须 > 0
    - success/fail 状态时 lock_time 应该为 0
    - _Requirements: 4.1, 4.2, 4.3_
  
  - [x] 7.4 更新数据库存储
    - 调用 db.save_unlock_log() 时传入 status 和 lock_time 参数
    - _Requirements: 4.4_
  
  - [x] 7.5 增强日志输出
    - 记录 INFO 级别日志，包含 status 和 lock_time
    - _Requirements: 10.2_

- [x] 8. 更新 EventReportHandler
  - [x] 8.1 支持新增事件类型
    - 在 valid_events 列表中添加 "door_closed"、"lock_success"、"bolt_alarm"
    - _Requirements: 6.1, 6.2, 6.3_
  
  - [x] 8.2 实现新增事件处理方法
    - 实现 _handle_door_closed_event() 方法
    - 实现 _handle_lock_success_event() 方法
    - 实现 _handle_bolt_alarm_event() 方法
    - _Requirements: 6.1, 6.2, 6.3_
  
  - [x] 8.3 更新数据库存储
    - 调用 db.save_device_event() 保存新增事件类型
    - _Requirements: 6.4_

- [x] 9. 实现命令下发重试机制
  - [x] 9.1 更新 LockControlProxyHandler
    - 修改 _forward_to_esp32() 方法，调用 _forward_with_retry()
    - _Requirements: 1.3, 1.4_
  
  - [x] 9.2 实现 _forward_with_retry() 方法
    - 循环最多 3 次重试
    - 每次发送命令后调用 _wait_for_esp32_ack()
    - 如果收到 esp32_ack，返回 True 并停止重试
    - 如果 3 次都超时，调用 _send_error() 发送 code=5 错误
    - _Requirements: 1.3, 1.4_
  
  - [x] 9.3 实现 _wait_for_esp32_ack() 方法
    - 创建 asyncio.Future 对象
    - 将 Future 存储到 esp32_conn._pending_esp32_acks[seq_id]
    - 使用 asyncio.wait_for() 等待 2 秒超时
    - 超时返回 False，收到响应返回 True
    - 清理 _pending_esp32_acks 中的 Future
    - _Requirements: 1.3, 1.4_
  
  - [x] 9.4 更新 _send_error() 方法
    - 支持 code 参数（统一错误码）
    - 发送包含 code 字段的错误响应
    - _Requirements: 1.4, 3.2_
  
  - [x] 9.5 复制到其他 ProxyHandler
    - 将重试机制复制到 DevControlProxyHandler
    - 将重试机制复制到 UserMgmtProxyHandler
    - _Requirements: 1.3, 1.4_

- [x] 10. 注册新增处理器
  - 在 `core/handle/textMessageHandlerRegistry.py` 中导入新增处理器
  - 在 _register_default_handlers() 中注册 Esp32AckHandler
  - 在 _register_default_handlers() 中注册 DoorOpenedReportHandler
  - 在 _register_default_handlers() 中注册 PasswordReportHandler
  - _Requirements: 1.1, 5.1, 5.4_

- [x] 11. 数据库迁移
  - [x] 11.1 创建迁移脚本
    - 创建 `migrations/upgrade_v5.0_to_v5.2.sql` 文件
    - _Requirements: 8.1, 8.2, 8.3, 8.4_
  
  - [x] 11.2 更新 unlock_logs 表
    - 添加 status VARCHAR(16) 字段，默认值 'success'
    - 添加 lock_time INT 字段，默认值 0
    - 迁移旧数据：result=1 → status='success', result=0 → status='fail'
    - 添加 idx_status 索引
    - _Requirements: 8.1, 8.2_
  
  - [x] 11.3 创建 door_opened_logs 表
    - 创建表结构（id, device_id, method, source, created_at）
    - 添加 idx_device_time 索引
    - _Requirements: 8.3_
  
  - [x] 11.4 更新 device_events 表
    - 如果使用 ENUM 类型，修改枚举值添加新事件类型
    - 如果使用 VARCHAR 类型，无需修改
    - _Requirements: 8.4_

- [x] 12. 实现数据库访问方法
  - [x] 12.1 更新 save_unlock_log() 方法
    - 在 `faceRecognitionHandler.py` 的 Database 类中
    - 添加 status 和 lock_time 参数（可选，默认值）
    - 如果 status 为 None，根据 result 转换
    - _Requirements: 8.1, 8.2_
  
  - [x] 12.2 实现 save_door_opened_log() 方法
    - 在 Database 类中新增方法
    - 插入 door_opened_logs 表
    - _Requirements: 8.3_
  
  - [x] 12.3 更新 save_device_event() 方法
    - 支持新增事件类型
    - _Requirements: 8.4_

- [x] 13. Checkpoint - 核心功能验证
  - 确保所有新增和更新的 Handler 已实现
  - 确保消息路由正确注册
  - 确保错误码常量定义正确
  - 运行基本的消息处理测试
  - 如有问题，询问用户

- [ ]* 14. 编写单元测试
  - [ ]* 14.1 测试 Esp32AckHandler
    - 测试正常消息解析
    - 测试缺少 seq_id 的错误处理
    - 测试 code 超出范围的警告
    - 测试 Future 触发逻辑
    - _Requirements: 1.1, 1.2, 9.1_
  
  - [ ]* 14.2 测试 DoorOpenedReportHandler
    - 测试正常消息处理
    - 测试无效 source 的错误处理
    - 测试数据库存储
    - 测试消息转发
    - _Requirements: 5.2, 5.3, 9.1_
  
  - [ ]* 14.3 测试 PasswordReportHandler
    - 测试正常消息处理
    - 测试仅转发不存储
    - _Requirements: 5.4, 5.5, 9.1_
  
  - [ ]* 14.4 测试 AckHandler 更新
    - 测试 seq_id 支持
    - 测试错误码验证
    - 测试错误转发
    - _Requirements: 2.1, 2.2, 3.1, 9.1_
  
  - [ ]* 14.5 测试 LogReportHandler 更新
    - 测试 status 字段解析
    - 测试旧版 result 兼容
    - 测试 locked 状态的 lock_time
    - _Requirements: 4.1, 4.2, 4.3, 9.1_
  
  - [ ]* 14.6 测试 EventReportHandler 更新
    - 测试新增事件类型识别
    - 测试数据库存储
    - _Requirements: 6.1, 6.2, 6.3, 9.1_
  
  - [ ]* 14.7 测试命令重试机制
    - 测试 esp32_ack 超时重试
    - 测试重试成功场景
    - 测试重试全部失败场景
    - 测试错误响应格式
    - _Requirements: 1.3, 1.4, 9.4_

- [ ]* 15. 编写集成测试
  - [ ]* 15.1 测试端到端消息流
    - 模拟 ESP32 → Server → App 完整流程
    - 测试两级确认机制（esp32_ack + ack）
    - _Requirements: 1.1, 1.5, 1.6_
  
  - [ ]* 15.2 测试数据库集成
    - 测试 unlock_logs 新字段存储
    - 测试 door_opened_logs 创建和查询
    - 测试数据库失败不影响转发
    - _Requirements: 8.1, 8.2, 8.3, 8.5_
  
  - [ ]* 15.3 测试错误处理流程
    - 测试 ESP32 离线场景
    - 测试命令超时场景
    - 测试 STM32 执行错误场景
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 16. 最终验证
  - 运行所有测试确保通过
  - 检查日志输出是否符合要求
  - 验证数据库表结构正确
  - 验证消息转发逻辑正确
  - 如有问题，询问用户

## 注意事项

1. **测试任务标记为可选**：标记 `*` 的任务为可选任务，可以根据项目进度决定是否实施
2. **数据库操作**：所有数据库操作失败不应影响消息转发
3. **错误码**：ESP32 已完成错误码映射，服务器端只需验证范围
4. **esp32_ack**：不转发给 App，仅用于 Server 内部重试判断
5. **日志级别**：
   - DEBUG：esp32_ack、成功的 ack
   - INFO：log_report、door_opened_report、password_report
   - WARNING：失败的 ack、无效的字段值
   - ERROR：JSON 解析失败、缺少必需字段
6. **异步编程**：所有 Handler 方法都是异步的，使用 async/await
7. **类型注解**：添加类型注解提高代码可读性

## 实施顺序建议

1. **第一阶段**（P0）：任务 1-10
   - 创建基础设施（错误码、枚举）
   - 实现所有 Handler
   - 注册处理器

2. **第二阶段**（P1）：任务 11-13
   - 数据库迁移
   - 核心功能验证

3. **第三阶段**（P2，可选）：任务 14-16
   - 编写测试
   - 最终验证

---

**文档版本**: v1.0  
**创建日期**: 2026-01-17  
**最后更新**: 2026-01-17
