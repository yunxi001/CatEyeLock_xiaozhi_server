# Requirements Document

## Introduction

本需求文档描述智能猫眼门锁服务器端功能扩展，基于现有 xiaozhi-server 通信协议进行最小化修改，实现 ESP32 门锁设备与 App 客户端之间的实时通信、监控和控制功能。

## Glossary

- **Server**: xiaozhi-server 服务端，负责消息路由、状态管理和模式控制
- **ESP32**: 智能门锁硬件设备端，运行在 ESP32 芯片上
- **App**: 用户手机客户端应用
- **Normal_Mode**: 正常模式，ESP32 音频经 ASR→LLM→TTS 处理后返回
- **Monitor_Mode**: 监控模式，ESP32 音视频实时转发给 App，支持双向对讲
- **BinaryProtocol2**: 16字节头部的二进制协议，用于传输音频和视频数据
- **device_id**: 设备唯一标识符，用于 ESP32 和 App 的配对关联

## Requirements

### Requirement 1: App 端 WebSocket 连接

**User Story:** As a 用户, I want to 通过 App 连接到服务器, so that I can 远程监控和控制门锁设备。

#### Acceptance Criteria

1. WHEN App 客户端连接 `/ws/app` 端点 THEN Server SHALL 创建独立的 App 连接处理器
2. WHEN App 发送包含 device_id 的 hello 消息 THEN Server SHALL 验证对应 ESP32 设备是否在线
3. WHEN device_id 对应的 ESP32 在线 THEN Server SHALL 返回成功响应并建立设备关联
4. WHEN device_id 对应的 ESP32 不在线 THEN Server SHALL 返回错误响应并说明原因
5. WHEN 多个 App 连接同一 device_id THEN Server SHALL 允许连接并支持广播模式

### Requirement 2: 连接管理器

**User Story:** As a 系统, I want to 统一管理所有连接, so that I can 实现 ESP32 和 App 之间的消息路由。

#### Acceptance Criteria

1. WHEN ESP32 设备连接成功 THEN Server SHALL 将连接注册到 ConnectionManager 的 esp32_connections 字典
2. WHEN App 客户端连接成功 THEN Server SHALL 将连接注册到 ConnectionManager 的 app_connections 字典
3. WHEN 连接断开 THEN Server SHALL 从对应字典中移除该连接
4. WHEN 需要转发消息 THEN Server SHALL 通过 device_id 查找目标连接并发送

### Requirement 3: 模式切换功能

**User Story:** As a 用户, I want to 在正常模式和监控模式之间切换, so that I can 根据需要选择语音助手或实时监控功能。

#### Acceptance Criteria

1. WHEN App 发送 `{"type": "system", "command": "start_monitor"}` THEN Server SHALL 切换到监控模式并通知 ESP32
2. WHEN App 发送 `{"type": "system", "command": "stop_monitor"}` THEN Server SHALL 切换到正常模式并通知 ESP32
3. WHEN 切换到监控模式时存在正在播放的 TTS 音频 THEN Server SHALL 停止向 ESP32 发送 TTS 音频数据
4. WHEN 处于监控模式 THEN Server SHALL 将 ESP32 的音视频数据转发给 App 而非送入 ASR 处理

### Requirement 4: 二进制协议扩展（BinaryProtocol2）

**User Story:** As a 系统, I want to 解析扩展的二进制协议, so that I can 区分并处理音频和视频数据。

#### Acceptance Criteria

1. WHEN 收到二进制消息且长度大于等于16字节 THEN Server SHALL 按 BinaryProtocol2 格式解析头部
2. WHEN 协议头 version=2, type=0, reserved=0 THEN Server SHALL 将负载识别为 OPUS 音频数据
3. WHEN 协议头 version=2, type=0, reserved≠0 THEN Server SHALL 将负载识别为 JPEG 视频数据，并从 reserved 字段提取宽高信息
4. WHEN 处于正常模式收到音频数据 THEN Server SHALL 将音频送入 ASR 处理流程
5. WHEN 处于监控模式收到音频或视频数据 THEN Server SHALL 将数据转发给关联的 App 连接

### Requirement 5: 监控模式音视频转发

**User Story:** As a 用户, I want to 在监控模式下实时查看门锁摄像头画面和听到声音, so that I can 远程了解门外情况。

#### Acceptance Criteria

1. WHEN 处于监控模式且 ESP32 发送音频数据 THEN Server SHALL 将音频数据转发给所有关联的 App
2. WHEN 处于监控模式且 ESP32 发送视频数据 THEN Server SHALL 将视频数据转发给所有关联的 App
3. WHEN 处于监控模式且 App 发送音频数据 THEN Server SHALL 将音频数据转发给 ESP32（双向对讲）

### Requirement 6: 文本消息转发机制

**User Story:** As a 系统, I want to 根据 forward 字段决定消息处理方式, so that I can 灵活控制消息的本地处理或远程转发。

#### Acceptance Criteria

1. WHEN TextMessageProcessor 收到文本消息 THEN Server SHALL 优先检查 forward 字段，再进行 type 分发处理
2. WHEN 收到包含 `"forward": true` 的文本消息 THEN Server SHALL 删除 forward 字段后转发给目标端
3. WHEN ESP32 发送带 forward 标记的消息 THEN Server SHALL 转发给关联的 App 连接
4. WHEN App 发送带 forward 标记的消息 THEN Server SHALL 转发给关联的 ESP32 连接
5. WHEN 收到不包含 forward 字段的消息 THEN Server SHALL 按现有逻辑进行 type 分发处理

### Requirement 7: 设备状态存储

**User Story:** As a 用户, I want to 查询门锁的当前状态, so that I can 了解电量、锁状态等信息。

#### Acceptance Criteria

1. WHEN ESP32 上报状态数据（锁状态、电量、门状态等） THEN Server SHALL 存储到设备状态存储中
2. WHEN App 请求设备状态 THEN Server SHALL 返回最新的状态数据
3. WHEN 状态数据更新 THEN Server SHALL 基于现有 iot_descriptors 机制进行存储

### Requirement 8: system 消息类型处理

**User Story:** As a 系统, I want to 处理 system 类型的文本消息, so that I can 响应模式切换等系统级命令。

#### Acceptance Criteria

1. WHEN 收到 `{"type": "system", "command": "start_monitor"}` THEN Server SHALL 调用模式切换逻辑进入监控模式
2. WHEN 收到 `{"type": "system", "command": "stop_monitor"}` THEN Server SHALL 调用模式切换逻辑退出监控模式
3. WHEN 模式切换成功 THEN Server SHALL 返回成功响应给请求方
4. WHEN 模式切换失败 THEN Server SHALL 返回错误响应并说明原因
