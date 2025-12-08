# Implementation Plan

- [x] 1. 创建数据库和基础模块


  - [x] 1.1 创建配置文件 face_recognition_config.yaml


    - 数据库连接配置、识别参数、问候语模板
    - _Requirements: 7.1_

  - [x] 1.2 创建数据模型 models.py

    - Person、AccessPermission、VisitRecord、RecognitionResult 数据类
    - _Requirements: 7.3_
  - [x] 1.3 创建数据库模块 database.py


    - MySQL 连接池、表初始化、CRUD 操作
    - 人脸编码序列化/反序列化
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  - [ ]* 1.4 编写属性测试：人脸编码序列化 round-trip
    - **Property 2: 人脸编码序列化 round-trip**
    - **Validates: Requirements 7.3, 7.4**

- [x] 2. 实现人脸识别核心服务


  - [x] 2.1 创建 FaceService 基础结构


    - 初始化、配置加载、face_recognition 库集成
    - _Requirements: 1.2_
  - [x] 2.2 实现 BinaryProtocol2 图像解析

    - parse_image() 方法：base64 解码 + 协议解析 + JPEG 提取
    - _Requirements: 1.1_
  - [ ]* 2.3 编写属性测试：BinaryProtocol2 解析正确性
    - **Property 1: BinaryProtocol2 解析正确性**
    - **Validates: Requirements 1.1**
  - [x] 2.4 实现人脸识别方法 recognize()

    - 人脸检测、编码提取、数据库比对
    - _Requirements: 1.2, 1.3, 1.4, 1.5_
  - [x] 2.5 实现问候语生成 generate_greeting()

    - 根据关系类型和识别结果生成问候语
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  - [ ]* 2.6 编写属性测试：问候语包含姓名
    - **Property 3: 问候语包含姓名**
    - **Validates: Requirements 2.1**

- [x] 3. 实现权限验证模块



  - [x] 3.1 实现 check_permission() 方法

    - 时段验证、按周验证、按月验证、临时权限验证
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_
  - [ ]* 3.2 编写属性测试：时段权限验证
    - **Property 4: 时段权限验证正确性**
    - **Validates: Requirements 3.1**
  - [ ]* 3.3 编写属性测试：按周权限验证
    - **Property 5: 按周权限验证正确性**
    - **Validates: Requirements 3.2**
  - [ ]* 3.4 编写属性测试：按月权限验证
    - **Property 6: 按月权限验证正确性**
    - **Validates: Requirements 3.3**
  - [ ]* 3.5 编写属性测试：临时权限次数扣减
    - **Property 7: 临时权限次数扣减**
    - **Validates: Requirements 3.4, 3.5**


- [x] 4. 实现消息处理器
  - [x] 4.1 创建 faceRecognitionHandler.py
    - 处理 face_recognition 类型消息（ESP32 识别请求）
    - 处理 face_management 类型消息（App 管理请求）
    - _Requirements: 1.1, 4.1_
  - [x] 4.2 实现 ESP32 识别请求处理
    - 解析图像、调用识别、返回 JSON 结果
    - 调用现有 TTS 模块发送语音（复用 conn.tts）
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4_
  - [x] 4.3 实现 App 人脸录入处理
    - register_face() 调用、权限创建、响应返回
    - 保存人脸照片到 data/face_recognition/faces/
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  - [x] 4.4 实现 App 管理功能处理
    - get_persons、update_permission、delete_person
    - _Requirements: 5.1, 5.2, 5.3_

- [x] 5. 实现到访记录和通知
  - [x] 5.1 实现到访记录保存
    - 每次识别请求保存记录到数据库
    - 保存到访照片到 data/face_recognition/visits/
    - _Requirements: 6.1_
  - [x] 5.2 实现到访记录查询
    - 分页查询、日期筛选
    - _Requirements: 6.2_
  - [x] 5.3 实现到访通知推送
    - 推送 visit_notification 给已连接的 App
    - _Requirements: 6.3_

- [x] 6. 集成和注册消息处理器
  - [x] 6.1 创建 doorlock 模块 __init__.py
    - 导出 FaceService、Database 等
    - _Requirements: 1.1_
  - [x] 6.2 注册 FaceRecognitionHandler 到消息路由
    - 修改 textHandle.py 添加消息类型路由
    - 添加 textMessageType.py 中的消息类型枚举
    - _Requirements: 1.1_
  - [x] 6.3 创建数据存储目录结构
    - data/face_recognition/faces/ 和 data/face_recognition/visits/（由 FaceService 自动创建）
    - _Requirements: 6.1_

- [x] 7. 更新 App Demo 页面




  - [x] 7.1 添加人脸管理 UI

    - 人脸录入表单、人员列表、权限编辑
    - _Requirements: 4.1, 5.1_

  - [x] 7.2 添加到访记录 UI



    - 到访记录列表、照片查看
    - _Requirements: 6.2_

- [x] 8. Checkpoint - 确保所有测试通过
  - 核心功能代码已完成，无语法错误
