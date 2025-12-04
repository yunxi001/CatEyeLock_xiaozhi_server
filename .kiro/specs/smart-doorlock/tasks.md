# Implementation Plan

## 1. 基础设施搭建

- [ ] 1.1 创建 ConnectionManager 连接管理器
  - 创建 `core/connection_manager.py` 文件
  - 实现单例模式
  - 实现 esp32_connections 和 app_connections 字典管理
  - 实现 register/unregister/get 方法
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ]* 1.2 编写 ConnectionManager 属性测试
  - **Property 2: 连接注册一致性**
  - **Validates: Requirements 2.1, 2.2, 2.3**

- [ ] 1.3 修改 ConnectionHandler 注册到 ConnectionManager
  - 在 `handle_connection` 中注册连接
  - 在 `close` 中注销连接
  - 新增 `current_mode` 属性，默认为 "normal"
  - _Requirements: 2.1, 2.3_

## 2. App 端连接支持

- [ ] 2.1 创建 AppConnectionHandler
  - 创建 `core/app_connection.py` 文件
  - 实现 WebSocket 连接处理
  - 实现 hello 消息认证（验证 device_id 对应的 ESP32 是否在线）
  - 实现消息路由（文本/二进制）
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ]* 2.2 编写 App 认证属性测试
  - **Property 1: App 认证验证**
  - **Validates: Requirements 1.2, 1.3**

- [ ] 2.3 修改 WebSocket 服务器添加 App 端点路由
  - 在 `websocket_server.py` 中添加 `/ws/app` 路由
  - ESP32 连接使用现有 ConnectionHandler
  - App 连接使用新的 AppConnectionHandler
  - _Requirements: 1.1_

- [ ] 2.4 Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

## 3. 文本消息处理扩展

- [ ] 3.1 新增 SYSTEM 消息类型
  - 在 `textMessageType.py` 中添加 SYSTEM 枚举值
  - _Requirements: 8.1, 8.2_

- [ ] 3.2 创建 SystemTextMessageHandler
  - 创建 `core/handle/textHandler/systemMessageHandler.py`
  - 实现 start_monitor 命令处理
  - 实现 stop_monitor 命令处理
  - 模式切换时停止 TTS 音频发送
  - _Requirements: 3.1, 3.2, 3.3, 8.1, 8.2, 8.3, 8.4_

- [ ]* 3.3 编写模式切换属性测试
  - **Property 4: 模式切换状态一致性**
  - **Validates: Requirements 3.1, 3.2, 8.1, 8.2**

- [ ] 3.4 注册 SystemTextMessageHandler
  - 在 `textMessageHandlerRegistry.py` 中注册新处理器
  - _Requirements: 8.1, 8.2_

- [ ] 3.5 修改 TextMessageProcessor 支持 forward 字段
  - 优先检查 forward 字段
  - 实现消息转发逻辑（删除 forward 字段后转发）
  - 无 forward 字段时按 type 分发
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ]* 3.6 编写消息转发属性测试
  - **Property 8: 消息转发字段处理**
  - **Property 9: 无 forward 字段消息处理**
  - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

- [ ] 3.7 Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

## 4. 二进制协议扩展

- [ ] 4.1 实现 BinaryProtocol2 解析
  - 在 ConnectionHandler 中添加 `_process_binary_protocol2` 方法
  - 解析16字节头部（version, type, reserved, timestamp, payload_size）
  - 根据 reserved 字段区分音频/视频
  - 从 reserved 提取视频宽高信息
  - _Requirements: 4.1, 4.2, 4.3_

- [ ]* 4.2 编写 BinaryProtocol2 解析属性测试
  - **Property 7: BinaryProtocol2 解析正确性**
  - **Validates: Requirements 4.1, 4.2, 4.3**

- [ ] 4.3 实现音频数据处理分流
  - 正常模式：送入 ASR 处理
  - 监控模式：转发给 App
  - _Requirements: 4.4, 4.5_

- [ ] 4.4 实现视频数据处理
  - 监控模式：转发给 App
  - 正常模式：忽略
  - _Requirements: 4.5_

- [ ]* 4.5 编写监控模式转发属性测试
  - **Property 5: 监控模式数据转发**
  - **Validates: Requirements 3.4, 4.5, 5.1, 5.2**

- [ ] 4.6 Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

## 5. 监控模式功能完善

- [ ] 5.1 实现多 App 广播
  - 在 ConnectionHandler 中实现 `_forward_to_apps` 方法
  - 获取所有关联的 App 连接并发送数据
  - _Requirements: 1.5, 5.1, 5.2_

- [ ]* 5.2 编写多 App 广播属性测试
  - **Property 3: 多 App 广播**
  - **Validates: Requirements 1.5, 5.1, 5.2**

- [ ] 5.3 实现双向对讲（App → ESP32）
  - 在 AppConnectionHandler 中处理音频数据
  - 转发给关联的 ESP32
  - _Requirements: 5.3_

- [ ]* 5.4 编写双向对讲属性测试
  - **Property 6: 双向对讲转发**
  - **Validates: Requirements 5.3**

## 6. 设备状态管理

- [ ] 6.1 扩展 IoT 状态存储支持门锁设备
  - 复用现有 iot_descriptors 机制
  - 支持锁状态、电量、门状态等属性
  - _Requirements: 7.1, 7.3_

- [ ] 6.2 实现状态查询接口
  - App 可查询设备最新状态
  - _Requirements: 7.2_

- [ ]* 6.3 编写状态存储查询属性测试
  - **Property 10: 设备状态存储查询一致性**
  - **Validates: Requirements 7.1, 7.2**

- [ ] 6.4 Final Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.
