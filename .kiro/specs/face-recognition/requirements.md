# Requirements Document

## Introduction

智能门锁人脸识别模块，为 xiaozhi-esp32-server 项目扩展人脸识别功能。系统包含三端：ESP32 门锁端（拍照识别）、服务器端（人脸识别+权限验证+数据管理）、App 端（人脸录入+权限管理+到访记录）。

## Glossary

- **ESP32**: 门锁端硬件设备，负责拍照和发起人脸识别请求
- **FaceRecognitionService**: 服务器端人脸识别核心服务
- **Person**: 已录入的人员信息（姓名、关系、人脸编码）
- **AccessPermission**: 开门权限配置（时段、类型、有效期）
- **VisitRecord**: 到访记录（识别结果、时间、照片）
- **RelationType**: 关系类型枚举（家人、朋友、同事、物业、快递、外卖、家教、同学、其他）
- **TTS**: 文字转语音服务，用于生成语音问候

## Requirements

### Requirement 1

**User Story:** As a 门锁用户, I want ESP32 能够发起人脸识别请求, so that 系统可以识别来访者身份。

#### Acceptance Criteria

1. WHEN ESP32 发送包含 BinaryProtocol2 格式封装的 JPEG 图像的人脸识别请求 THEN FaceRecognitionService SHALL 解析协议并提取 JPEG 图像进行人脸检测
2. WHEN 图像中检测到人脸 THEN FaceRecognitionService SHALL 提取人脸编码并与数据库比对
3. WHEN 图像中未检测到人脸 THEN FaceRecognitionService SHALL 返回 result 为 "no_face" 的响应
4. WHEN 人脸比对成功匹配已知人员 THEN FaceRecognitionService SHALL 返回 result 为 "known" 及人员信息
5. WHEN 人脸比对未匹配任何已知人员 THEN FaceRecognitionService SHALL 返回 result 为 "unknown"

### Requirement 2

**User Story:** As a 门锁用户, I want 系统根据识别结果播放语音问候, so that 来访者能得到友好的语音反馈。

#### Acceptance Criteria

1. WHEN 识别结果为已知人员且有开门权限 THEN FaceRecognitionService SHALL 根据关系类型生成问候语并通过 TTS 发送语音
2. WHEN 识别结果为已知人员但无开门权限 THEN FaceRecognitionService SHALL 生成拒绝语音并通过 TTS 发送
3. WHEN 识别结果为陌生人 THEN FaceRecognitionService SHALL 发送预设的陌生人问候语音
4. WHEN 识别结果为无人脸 THEN FaceRecognitionService SHALL 不发送任何语音

### Requirement 3

**User Story:** As a 门锁用户, I want 系统验证来访者的开门权限, so that 只有授权人员才能开门。

#### Acceptance Criteria

1. WHEN 验证永久权限 THEN FaceRecognitionService SHALL 检查当前时间是否在允许时段内
2. WHEN 验证按周权限 THEN FaceRecognitionService SHALL 检查当前星期几是否在允许列表中
3. WHEN 验证按月权限 THEN FaceRecognitionService SHALL 检查当前日期是否在允许列表中
4. WHEN 验证临时权限 THEN FaceRecognitionService SHALL 检查剩余次数是否大于零
5. WHEN 临时权限验证通过 THEN FaceRecognitionService SHALL 扣减剩余次数一次
6. WHEN 权限验证通过 THEN FaceRecognitionService SHALL 返回 access.granted 为 true
7. WHEN 权限验证失败 THEN FaceRecognitionService SHALL 返回 access.granted 为 false 及拒绝原因

### Requirement 4

**User Story:** As a App 用户, I want 录入新的人脸信息, so that 系统能够识别该人员。

#### Acceptance Criteria

1. WHEN App 发送人脸录入请求包含姓名、关系类型和图像 THEN FaceRecognitionService SHALL 检测图像中的人脸
2. WHEN 录入图像中检测到人脸 THEN FaceRecognitionService SHALL 提取人脸编码并保存到数据库
3. WHEN 录入图像中未检测到人脸 THEN FaceRecognitionService SHALL 返回错误 "no_face_detected"
4. WHEN 人脸录入成功 THEN FaceRecognitionService SHALL 返回新创建的 person_id
5. WHEN 人脸录入请求包含权限配置 THEN FaceRecognitionService SHALL 同时创建对应的权限记录

### Requirement 5

**User Story:** As a App 用户, I want 管理已录入人员的权限, so that 我可以控制谁能在什么时间开门。

#### Acceptance Criteria

1. WHEN App 请求获取人员列表 THEN FaceRecognitionService SHALL 返回所有已录入人员及其权限信息
2. WHEN App 请求更新人员权限 THEN FaceRecognitionService SHALL 更新数据库中的权限记录
3. WHEN App 请求删除人员 THEN FaceRecognitionService SHALL 删除人员信息及关联的权限和照片

### Requirement 6

**User Story:** As a App 用户, I want 查看到访记录, so that 我可以了解谁来过门口。

#### Acceptance Criteria

1. WHEN 有人脸识别请求发生 THEN FaceRecognitionService SHALL 保存到访记录包含识别结果、时间和照片
2. WHEN App 请求获取到访记录 THEN FaceRecognitionService SHALL 返回分页的到访记录列表
3. WHEN 有新的到访发生 THEN FaceRecognitionService SHALL 推送通知给已连接的 App

### Requirement 7

**User Story:** As a 系统管理员, I want 数据库正确存储所有数据, so that 系统能够持久化人脸和权限信息。

#### Acceptance Criteria

1. WHEN 系统启动 THEN Database SHALL 连接到 MySQL 数据库 smart_doorlock
2. WHEN 数据库不存在 THEN Database SHALL 自动创建数据库和所需表结构
3. WHEN 保存人脸编码 THEN Database SHALL 将 128 维 numpy 数组序列化为 BLOB 存储
4. WHEN 读取人脸编码 THEN Database SHALL 将 BLOB 反序列化为 numpy 数组
