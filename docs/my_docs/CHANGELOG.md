# 变更日志

## 2025-12-12

### ESP32 协议功能实现检查完成

#### 检查结果
所有 ESP32 协议 v5.0 功能均已正确实现并注册到 Handler Registry。

#### 已验证的功能

**ESP32 上报消息处理（ESP32 → Server）：**
| 消息类型 | Handler | 状态 |
|----------|---------|------|
| `status_report` | StatusReportHandler | ✅ 存储 + 转发 App |
| `event_report` | EventReportHandler | ✅ 存储 + 转发 App |
| `log_report` | LogReportHandler | ✅ 存储 + 转发 App |
| `ack` | AckHandler | ✅ 转发 App |
| `user_mgmt_result` | UserMgmtResultHandler | ✅ 转发 App |
| `heartbeat` | HeartbeatHandler | ✅ 回复 heartbeat_ack |
| 二进制人脸图像 (type=2) | connection._handle_face_recognition_binary | ✅ 识别 + 推送 App |

**Server 下发命令处理（App → Server → ESP32）：**
| 消息类型 | Handler | 状态 |
|----------|---------|------|
| `lock_control` | LockControlProxyHandler | ✅ 添加 msg_id + 转发 |
| `dev_control` | DevControlProxyHandler | ✅ 添加 msg_id + 转发 |
| `user_mgmt` | UserMgmtProxyHandler | ✅ 添加 msg_id + 转发 |
| `system` (start/stop_monitor) | SystemTextMessageHandler | ✅ 模式切换 + 通知 ESP32 |

**App 数据查询处理：**
| 查询目标 | 状态 |
|----------|------|
| `status` | ✅ 内存缓存 / 数据库 |
| `status_history` | ✅ 分页查询 |
| `events` | ✅ 分页 + 类型过滤 |
| `unlock_logs` | ✅ 分页 + 方式/结果过滤 |
| `media_files` | ✅ 分页 + 日期过滤 |

**设备上下线通知：**
- ✅ ESP32 连接时通知 App `device_status: online`
- ✅ ESP32 断开时通知 App `device_status: offline` + reason

**App 协议 v2.2 机制：**
- ✅ `app_id` 身份标识
- ✅ `seq_id` 防重放缓存
- ✅ `server_ack` 消息确认

#### 文档重命名
- `智能猫眼门锁系统-通信协议规范-v5.0.md` → `智能猫眼门锁系统-服务器与ESP32通信协议规范-v5.0.md`
- `智能猫眼门锁系统-App通信协议规范-v2.2.md` → `智能猫眼门锁系统-服务器与App通信协议规范-v2.2.md`

---

## 2025-12-11

### 智能门锁协议 v5.0 适配

#### 修改文件
- `main/xiaozhi-server/core/handle/textMessageType.py`
- `main/xiaozhi-server/core/handle/textMessageHandlerRegistry.py`
- `main/xiaozhi-server/core/handle/textHandler/faceRecognitionHandler.py`
- `main/xiaozhi-server/core/connection.py`
- `main/xiaozhi-server/core/providers/doorlock/__init__.py`

#### 新增文件
- `main/xiaozhi-server/core/handle/textHandler/statusReportHandler.py` - 传感器状态上报处理器
- `main/xiaozhi-server/core/handle/textHandler/eventReportHandler.py` - 关键事件上报处理器
- `main/xiaozhi-server/core/handle/textHandler/logReportHandler.py` - 开锁日志上报处理器
- `main/xiaozhi-server/core/handle/textHandler/ackHandler.py` - ACK 响应处理器
- `main/xiaozhi-server/core/handle/textHandler/userMgmtResultHandler.py` - 用户管理结果处理器
- `main/xiaozhi-server/core/handle/textHandler/heartbeatHandler.py` - 心跳处理器（预留）
- `main/xiaozhi-server/core/providers/doorlock/lock_controller.py` - 锁控命令控制器
- `main/xiaozhi-server/core/providers/doorlock/device_controller.py` - 硬件外设控制器
- `main/xiaozhi-server/core/providers/doorlock/user_manager.py` - 用户管理命令控制器

#### 变更内容
1. **人脸识别响应格式变更**：
   - `type` 从 `face_recognition` 改为 `face_result`
   - 新增 `msg_id` 字段
   - `person.id` 改为顶层 `user_id`
   - 移除 `person.name`、`person.relation`、`access.action`
   - `access.reason` 始终存在

2. **新增消息类型枚举**：
   - `STATUS_REPORT` - 传感器状态上报
   - `EVENT_REPORT` - 关键事件上报
   - `LOG_REPORT` - 开锁日志上报
   - `ACK` - ACK 响应
   - `USER_MGMT_RESULT` - 用户管理结果
   - `HEARTBEAT` - 心跳请求

3. **新增服务器下发命令**：
   - `lock_control` - 远程开锁/关锁、临时密码
   - `dev_control` - 蜂鸣器/OLED/补光灯控制
   - `user_mgmt` - 指纹/NFC/密码管理

#### 功能说明
适配 ESP32 智能门锁协议 v5.0，实现与 STM32 协议对齐，支持完整的门锁控制和状态管理功能。

---

## 2025-12-09

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/face_service.py`

### 修改位置
- `FaceService` 类的 `parse_image` 方法

### 变更内容
- 将 `parse_image` 方法的参数类型从 `str` 改为 `bytes`
- 移除了 base64 解码步骤（`base64.b64decode`）
- 更新了方法文档注释

### 功能说明
修复图像数据解析逻辑，适配 ESP32 直接发送原始 bytes 格式的图像数据，无需 base64 编码/解码，简化数据处理流程。

---

## 2025-12-09 (更新)

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/face_service.py`

### 修改位置
- `FaceService` 类的 `parse_image` 方法

### 变更内容
- 修正 BinaryProtocol2 协议头解析格式
- 协议头从 8 字节改为 16 字节
- 字段定义更新为小端序（little-endian）：
  - `version`: uint16_t (2 bytes)
  - `type`: uint16_t (2 bytes)
  - `reserved`: uint32_t (4 bytes)
  - `timestamp`: uint32_t (4 bytes)
  - `payload_size`: uint32_t (4 bytes)
- 使用 `struct.unpack('<I', ...)` 解析 payload_size
- JPEG 数据提取改为根据 payload_size 精确截取

### 功能说明
修复 BinaryProtocol2 协议解析逻辑，与 ESP32 固件端的协议定义保持一致，确保正确提取 JPEG 图像数据。

---

## 2025-12-09 (更新 2)

### 修改文件
- `main/xiaozhi-server/core/connection.py`

### 修改位置
- 文件头部 import 区域（第 13 行）

### 变更内容
- 新增 `import opuslib_next` 导入语句

### 功能说明
添加 Opus 音频编解码库的导入，用于支持 Opus 格式音频数据的编解码处理。

---

## 2025-12-09 (更新 3)

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/face_service.py`

### 修改位置
- `FaceService` 类的 `parse_image` 方法

### 变更内容
- 将 `parse_image` 方法的参数类型从 `bytes` 改回 `str`
- 恢复 base64 解码步骤（`base64.b64decode(image_data)`）
- 更新方法文档注释，说明输入为 base64 编码的字符串

### 功能说明
回滚图像数据解析逻辑，适配 JSON 协议传输二进制数据的标准做法。ESP32 通过 WebSocket 发送的 JSON 消息中，图像数据以 base64 编码字符串形式传输，服务端需先解码再解析 BinaryProtocol2 协议。

---

## 2025-12-09 (更新 4)

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/face_service.py`

### 修改位置
- `FaceService` 类的 `parse_image` 方法

### 变更内容
- 将 `parse_image` 方法的参数类型从 `str` 改回 `bytes`
- 移除 base64 解码步骤（`base64.b64decode`）
- 更新方法文档注释，说明输入为原始 bytes 数据

### 功能说明
再次调整图像数据解析逻辑，适配 ESP32 直接通过 WebSocket 二进制帧发送原始 bytes 格式的图像数据。当 ESP32 使用 WebSocket 二进制消息（而非 JSON 文本消息）传输图像时，数据无需 base64 编码，服务端直接接收原始字节流进行 BinaryProtocol2 协议解析。

---

## 2025-12-09 (更新 5)

### 修改文件
- `main/xiaozhi-server/core/connection.py`

### 修改位置
- `ConnectionHandler` 类的 `_route_message` 方法（约第 275-291 行）
- 新增 `_handle_face_recognition_binary` 方法（约第 294-418 行）

### 变更内容
1. **`_route_message` 方法增强**：
   - 新增对 BinaryProtocol2 格式人脸识别请求的检测逻辑
   - 解析二进制消息头部的 `type` 字段（小端序，偏移 2-4 字节）
   - 当 `type=2` 时，路由到人脸识别处理方法

2. **新增 `_handle_face_recognition_binary` 方法**：
   - 处理 ESP32 直接发送的 BinaryProtocol2 格式二进制人脸识别请求
   - 调用 `FaceService` 解析图像、执行人脸识别、验证权限
   - 生成问候语并通过 TTS 播放
   - 保存到访记录到数据库
   - 构建并发送 JSON 格式的识别结果响应
   - 推送到访通知给关联的 App 客户端

### 功能说明
实现 ESP32 二进制协议的人脸识别请求处理。ESP32 可直接通过 WebSocket 二进制帧发送 BinaryProtocol2 格式的图像数据（协议头 type=2），服务端自动识别并处理，完成人脸识别、权限验证、语音播报、到访记录保存和 App 通知推送的完整流程。相比 JSON+base64 方式，二进制传输减少约 33% 的数据量，提升传输效率。

---

## 2025-12-09 (更新 4)

### 修改文件
- `main/xiaozhi-server/core/connection.py`
- `main/xiaozhi-server/core/providers/doorlock/face_service.py`
- `main/xiaozhi-server/core/handle/textHandler/faceRecognitionHandler.py`

### 修改位置
- `connection.py`: `_route_message` 方法，新增 `_handle_face_recognition_binary` 方法
- `face_service.py`: `parse_image` 方法
- `faceRecognitionHandler.py`: `_handle_recognize` 和 `_handle_register` 方法

### 变更内容
1. **connection.py**:
   - 在 `_route_message` 中增加二进制消息的 BinaryProtocol2 协议头解析
   - 当 `type=2` 时识别为人脸识别请求，路由到新增的 `_handle_face_recognition_binary` 方法
   - 新增 `_handle_face_recognition_binary` 方法处理 ESP32 直接发送的二进制人脸识别数据

2. **face_service.py**:
   - `parse_image` 参数类型从 `str` 改为 `bytes`
   - 移除 base64 解码，直接处理原始二进制数据

3. **faceRecognitionHandler.py**:
   - ESP32 JSON 方式（兼容）改为直接 base64 解码
   - App 端录入人脸简化为直接 base64 解码

### 功能说明
解决 ESP32 通过 WebSocket 发送 base64 编码图像数据过大导致超时断连的问题。ESP32 现在直接发送 BinaryProtocol2 格式的二进制数据，服务器通过协议头 `type=2` 识别人脸识别请求，避免 base64 编码带来的约 33% 数据膨胀。

---

## 2025-12-09 (更新 6)

### 修改文件
- `main/xiaozhi-server/core/connection.py`

### 修改位置
- `ConnectionHandler` 类的 `_handle_face_recognition_binary` 方法（约第 358-360 行）

### 变更内容
- 在发送 JSON 响应后新增日志输出语句
- 添加 `self.logger.bind(tag=TAG).info(f"响应内容: {response}")` 打印响应内容

### 功能说明
增加人脸识别响应的调试日志，便于追踪和排查人脸识别请求的处理结果，方便开发调试和问题定位。

---

## 2025-12-09 (更新 7)

### 修改文件
- `main/xiaozhi-server/core/connection.py`

### 修改位置
- `ConnectionHandler` 类的 `_route_message` 方法（约第 279-288 行）

### 变更内容
- 在解析 BinaryProtocol2 协议头后新增 debug 级别日志，记录二进制消息的长度、类型和头部 hex 信息
- 在识别到人脸识别请求（type=2）时新增 info 级别日志，记录数据长度

### 功能说明
增强人脸识别二进制协议的调试能力，便于排查 ESP32 发送的人脸识别请求问题，可追踪收到的二进制消息详情和协议头解析结果。


---

## 2025-12-09 (更新 8)

### 修改文件
- `main/xiaozhi-server/core/connection.py`

### 修改位置
- `ConnectionHandler` 类的 `_route_message` 方法（第 279-282 行）

### 变更内容
- 将二进制消息接收时的日志级别从 `debug` 改为 `info`
- 原：`self.logger.bind(tag=TAG).debug(...)`
- 改：`self.logger.bind(tag=TAG).info(...)`

### 功能说明
提升人脸识别二进制消息日志的可见性。将接收二进制消息时的日志级别从 debug 提升为 info，使得在正常运行模式下也能看到二进制消息的接收情况（包括消息长度、类型、协议头信息），便于生产环境的监控和问题排查。


---

## 2025-12-09 (更新 9)

### 修改文件
- `main/xiaozhi-server/core/connection.py`

### 修改位置
- `ConnectionHandler` 类的 `_route_message` 方法（第 279-280 行）

### 变更内容
- 修正 BinaryProtocol2 协议头 `type` 字段的字节序解析
- 原：`int.from_bytes(message[2:4], 'little')` （小端序）
- 改：`int.from_bytes(message[2:4], 'big')` （大端序）
- 同步更新注释说明

### 功能说明
修复人脸识别二进制协议解析的字节序问题。BinaryProtocol2 协议头的 `type` 字段采用大端序（网络字节序），之前错误使用小端序导致无法正确识别 ESP32 发送的人脸识别请求（type=2）。修复后可正确解析协议头，确保人脸识别功能正常工作。


---

## 2025-12-09 (更新 10)

### 修改文件
- `main/xiaozhi-server/core/connection.py`

### 修改位置
- `ConnectionHandler` 类的 `_route_message` 方法（第 279-282 行）

### 变更内容
- 将二进制消息接收时的日志级别从 `info` 改为 `debug`
- 原：`self.logger.bind(tag=TAG).info(...)`
- 改：`self.logger.bind(tag=TAG).debug(...)`

### 功能说明
降低二进制消息接收日志的级别。由于每个音频帧都会触发此日志，使用 info 级别会产生大量日志输出，干扰重要信息的查看。改为 debug 级别后，正常运行时不会输出这些高频日志，需要调试时可通过调整日志级别查看。


---

## 2025-12-11

### 修改文件
- `main/xiaozhi-server/core/handle/textMessageType.py`

### 修改位置
- `TextMessageType` 枚举类末尾（第 15-22 行）

### 变更内容
- 新增 6 个 ESP32 智能门锁相关的消息类型枚举值：
  - `STATUS_REPORT = "status_report"` - 传感器状态上报
  - `EVENT_REPORT = "event_report"` - 关键事件上报
  - `LOG_REPORT = "log_report"` - 开锁日志上报
  - `ACK = "ack"` - ACK 响应
  - `USER_MGMT_RESULT = "user_mgmt_result"` - 用户管理结果
  - `HEARTBEAT = "heartbeat"` - 心跳请求（预留）

### 功能说明
扩展文本消息类型枚举，支持 ESP32 智能门锁设备的多种上报消息类型。这些类型用于门锁设备向服务器上报传感器状态、关键事件（如门铃按下、异常告警）、开锁日志、命令确认响应、用户管理操作结果等，为后续实现门锁消息处理器提供类型定义基础。


---

## 2025-12-11 (更新)

### 新增文件
- `main/xiaozhi-server/core/handle/textHandler/eventReportHandler.py`

### 新增位置
- `core/handle/textHandler/` 目录下新增 `EventReportHandler` 类

### 变更内容
- 新增 `EventReportHandler` 类，继承 `TextMessageHandler`
- 实现 `message_type` 属性，返回 `TextMessageType.EVENT_REPORT`
- 实现 `handle` 方法处理事件上报消息
- 实现 5 个事件处理方法：
  - `_handle_bell_event`: 门铃按下事件
  - `_handle_pir_event`: PIR 人体检测事件
  - `_handle_tamper_event`: 撬锁报警事件
  - `_handle_door_open_event`: 门未关超时事件
  - `_handle_low_battery_event`: 低电量警告事件
- 实现 `_forward_to_apps` 方法，将事件转发给关联的 App 客户端

### 功能说明
实现 ESP32 智能门锁关键事件上报处理器。支持处理门铃按下、PIR 人体检测、撬锁报警、门未关超时、低电量警告等事件类型，并将事件实时转发给关联的 App 客户端，实现门锁事件的实时推送通知功能。


---

## 2025-12-11 (更新 2)

### 新增文件
- `main/xiaozhi-server/core/handle/textHandler/ackHandler.py`

### 新增位置
- `core/handle/textHandler/` 目录下新增 `AckHandler` 类

### 变更内容
- 新增 `AckHandler` 类，继承 `TextMessageHandler`
- 实现 `message_type` 属性，返回 `TextMessageType.ACK`
- 实现 `handle` 方法处理 ACK 响应消息
- 支持解析 `msg_id`、`code`、`msg` 字段
- 定义错误码规范（0=成功, 1=设备忙碌, 2=参数错误, 3=硬件故障, 4=超时, 5=未授权, 6=资源不足, 7=不支持）
- 实现命令回调机制：当 `conn._pending_commands` 中存在对应 `msg_id` 的回调时自动执行

### 功能说明
实现 ESP32 智能门锁 ACK 响应处理器。当服务器向 ESP32 发送控制命令（如开锁、补光灯控制等）后，ESP32 会返回 ACK 消息确认执行结果。此处理器负责解析 ACK 响应，记录执行状态日志，并触发等待中的命令回调函数，实现异步命令的结果通知机制。


---

## 2025-12-11 (更新 3)

### 新增文件
- `main/xiaozhi-server/core/providers/doorlock/device_controller.py`

### 新增位置
- `core/providers/doorlock/` 目录下新增 `DeviceController` 类

### 变更内容
- 新增 `DeviceController` 类，提供硬件外设控制静态方法
- 实现 3 个核心控制方法：
  - `control_beep(conn, count, mode)`: 控制蜂鸣器，支持 short/long/alarm 模式
  - `control_oled(conn, icon)`: 控制 OLED 显示，支持 6 种图标状态（0-5）
  - `control_light(conn, action)`: 控制补光灯，支持 on/off/auto 动作
- 实现 5 个便捷方法：
  - `alarm(conn, count)`: 触发警报（蜂鸣器 alarm 模式）
  - `beep_short(conn, count)`: 短滴提示音
  - `light_on(conn)`: 开启补光灯
  - `light_off(conn)`: 关闭补光灯
  - `light_auto(conn)`: 恢复补光灯自动控制
- 所有方法返回 `msg_id` 用于命令追踪和 ACK 响应匹配

### 功能说明
实现 ESP32 智能门锁硬件外设控制器。通过 WebSocket 向设备发送 `dev_control` 类型的 JSON 消息，控制蜂鸣器响铃（提示音/警报）、OLED 屏幕显示状态图标、补光灯开关等外设。配合 `AckHandler` 可实现命令执行结果的异步确认。


---

## 2025-12-11 (更新 4)

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/__init__.py`

### 修改位置
- 文件头部 import 区域（第 5-7 行）
- `__all__` 导出列表（第 15-17 行）

### 变更内容
- 新增 3 个模块导入：
  - `from .lock_controller import LockController`
  - `from .device_controller import DeviceController`
  - `from .user_manager import UserManager`
- 将 `LockController`、`DeviceController`、`UserManager` 添加到 `__all__` 导出列表

### 功能说明
完善 doorlock 包的模块导出配置。将新增的锁控制器、硬件外设控制器、用户管理控制器纳入包的公开接口，使外部代码可以通过 `from core.providers.doorlock import LockController, DeviceController, UserManager` 的简洁方式导入这些类，提升代码的可用性和模块化程度。


---

## 2025-12-11 (更新 5)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/faceRecognitionHandler.py`

### 修改位置
- 文件头部 import 区域（第 4 行）

### 变更内容
- 新增 `import time` 导入语句

### 功能说明
引入 Python 标准库 time 模块，为人脸识别处理器提供时间相关功能支持，如生成时间戳、计时统计等。


---

## 2025-12-11 (更新 6)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/faceRecognitionHandler.py`

### 修改位置
- `FaceRecognitionHandler` 类中，`_handle_recognize` 方法之后（第 93-136 行）

### 变更内容
- 新增 `_build_face_result` 方法：构建符合 v5.0 协议的人脸识别响应
- 新增 `_get_access_reason` 方法：获取访问原因并映射到协议定义

### 功能说明
实现人脸识别响应的标准化构建。`_build_face_result` 方法生成包含 `type`（face_result）、`msg_id`、`result`、`user_id`、`access` 字段的 JSON 响应结构。`_get_access_reason` 方法将内部权限拒绝原因（如 `time_restricted`、`blacklisted`、`expired`、`not_in_time_range`）映射为协议规范定义的标准原因码，确保 ESP32 设备能正确解析和处理人脸识别结果。


---

## 2025-12-11 (更新 7)

### 修改文件
- `main/xiaozhi-server/core/connection.py`

### 修改位置
- `ConnectionHandler` 类的 `_handle_face_recognition_binary` 方法（约第 319-370 行）

### 变更内容
1. **错误响应格式统一**：
   - `type` 从 `face_recognition` 改为 `face_result`
   - 新增 `msg_id` 字段（格式：`face_{timestamp}`）
   - 新增 `user_id` 字段（值为 `None`）
   - 新增 `access` 对象，包含 `granted: false` 和 `reason: "unauthorized_user"`

2. **成功响应格式简化**：
   - `type` 从 `face_recognition` 改为 `face_result`
   - 移除嵌套的 `person` 对象结构
   - 改为扁平化的 `user_id` 字段（直接取 `result.person.id`）
   - 统一 `access.reason` 生成逻辑：授权时为 `authorized_user`，否则使用 `deny_reason` 或默认 `unauthorized_user`
   - 移除条件性的 `access.action` 字段

### 功能说明
统一二进制人脸识别请求的响应格式，使其完全符合 v5.0 协议规范。修改后的响应结构与 `FaceRecognitionHandler` 中 JSON 方式的响应保持一致，ESP32 设备可使用统一的解析逻辑处理所有人脸识别响应，简化固件端代码实现。


---

## 2025-12-11 (更新 8)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/logReportHandler.py`

### 修改位置
- `LogReportHandler` 类的 `handle` 方法文档注释（第 35-42 行）

### 变更内容
- 扩展 `method` 字段取值说明，与 v5.0 协议对齐：
  - 新增 `face`: 人脸开锁
  - 新增 `temp_pwd`: 临时密码开锁
  - 修正 `remote` 说明从"远程开锁(人脸)"改为"远程开锁(App)"

### 功能说明
完善开锁日志上报处理器的文档注释，补充 v5.0 协议新增的开锁方式（人脸识别、临时密码），并修正远程开锁的说明使其与协议规范一致。此变更仅涉及文档注释，不影响代码逻辑。


---

## 2025-12-11 (更新 9)

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/database.py`

### 修改位置
- `Database` 类的 `_init_database` 方法（第 111-188 行）

### 变更内容
- 新增 5 个数据库表的创建语句，与 v5.0 协议数据存储规范对齐：
  - `device_status`: 设备状态记录表（电量、光照、锁状态、补光灯状态）
  - `device_events`: 设备事件记录表（门铃、PIR、撬锁、门未关、低电量等事件）
  - `unlock_logs`: 开锁日志记录表（开锁方式、用户ID、结果、失败次数）
  - `doorlock_users`: 门锁用户信息表（指纹ID、NFC卡ID、人脸注册状态）
  - `media_files`: 媒体文件元数据表（人脸图片、监控录像）

### 功能说明
完善智能门锁数据存储架构，实现 v5.0 协议规范中定义的数据库表结构。新增的表用于持久化存储设备状态历史、关键事件记录、开锁日志、用户凭证信息和媒体文件元数据，为后续的状态上报处理器、事件上报处理器、开锁日志处理器提供数据存储支持。


---

## 2025-12-11 (更新 10)

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/database.py`

### 修改位置
- `Database` 类末尾（第 499-775 行），新增多组 CRUD 方法

### 变更内容
- 新增设备状态 CRUD 方法：
  - `save_device_status`: 保存设备状态记录（电量、光照、锁状态、补光灯状态）
  - `get_device_status_history`: 获取设备状态历史
- 新增设备事件 CRUD 方法：
  - `save_device_event`: 保存设备事件记录
  - `get_device_events`: 获取设备事件历史（支持按事件类型筛选）
- 新增开锁日志 CRUD 方法：
  - `save_unlock_log`: 保存开锁日志
  - `get_unlock_logs`: 获取开锁日志历史
- 新增门锁用户 CRUD 方法：
  - `save_doorlock_user`: 保存/更新门锁用户（支持 UPSERT）
  - `update_doorlock_user_finger`: 更新用户指纹 ID 列表
  - `update_doorlock_user_nfc`: 更新用户 NFC ID 列表
  - `get_doorlock_users`: 获取设备的所有用户
- 新增媒体文件 CRUD 方法：
  - `save_media_file`: 保存媒体文件元数据
  - `get_media_files`: 获取媒体文件列表（支持按类型筛选）
- 新增数据清理方法：
  - `cleanup_old_data`: 清理过期数据，支持配置各表保留天数，返回删除记录数和待删除文件路径

### 功能说明
为 v5.0 协议数据存储规范中定义的 5 个新增数据库表（device_status、device_events、unlock_logs、doorlock_users、media_files）提供完整的 CRUD 操作方法。这些方法供状态上报处理器、事件上报处理器、开锁日志处理器等调用，实现设备数据的持久化存储和查询。`cleanup_old_data` 方法支持定时清理过期数据，符合协议规范中的数据保留策略（状态 7 天、事件 30 天、日志 90 天、媒体 30 天）。


---

## 2025-12-11 (更新 11)

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/__init__.py`

### 修改位置
- 文件头部 import 区域（第 8 行）
- `__all__` 导出列表（第 20 行）

### 变更内容
- 新增 `from .media_storage import MediaStorage` 导入语句
- 将 `MediaStorage` 添加到 `__all__` 导出列表

### 功能说明
将 `MediaStorage` 媒体文件存储管理器纳入 doorlock 包的公开接口。外部代码可通过 `from core.providers.doorlock import MediaStorage` 的简洁方式导入该类，用于管理人脸图片和监控录像的本地存储，与 v5.0 协议数据存储规范中的媒体文件存储架构配合使用。


---

## 2025-12-11 (更新 12)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/statusReportHandler.py`

### 修改位置
- `StatusReportHandler` 类的 `handle` 方法（第 36-60 行）
- 新增 `_save_to_database` 方法（第 62-75 行）

### 变更内容
1. **代码重构**：
   - 将 `data.get()` 调用提取为局部变量（`battery`, `lux`, `lock_state`, `light_state`）
   - 优化日志输出，使用局部变量替代重复的 `data.get()` 调用

2. **新增数据库持久化**：
   - 新增 `_save_to_database` 异步方法
   - 在 `handle` 方法中调用 `_save_to_database` 保存状态到数据库
   - 通过 `conn.doorlock_db.save_device_status()` 调用 Database 模块的存储方法

### 功能说明
为状态上报处理器增加数据库持久化功能。当 ESP32 设备上报传感器状态（电量、光照、锁状态、补光灯状态）时，除了更新内存缓存和转发给 App 外，还会将状态记录保存到 MySQL 数据库的 `device_status` 表中，实现状态数据的持久化存储，便于后续查询历史状态和数据分析。


---

## 2025-12-11 (更新 13)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/logReportHandler.py`

### 修改位置
- `LogReportHandler` 类的 `handle` 方法（第 46-68 行）
- 新增 `_save_to_database` 方法（第 71-84 行）

### 变更内容
1. **修复 uid 默认值**：
   - 原：`uid = data.get("uid")`
   - 改：`uid = data.get("uid", 0)`
   - 避免 uid 为 None 时导致数据库写入异常

2. **新增数据库持久化**：
   - 新增 `_save_to_database` 异步方法
   - 在 `handle` 方法中调用 `_save_to_database` 保存开锁日志
   - 通过 `conn.doorlock_db.save_unlock_log()` 调用 Database 模块的存储方法

### 功能说明
为开锁日志上报处理器增加数据库持久化功能。当 ESP32 设备上报开锁日志（开锁方式、用户ID、结果、失败次数）时，除了记录日志和转发给 App 外，还会将记录保存到 MySQL 数据库的 `unlock_logs` 表中，实现开锁日志的持久化存储，便于后续查询历史记录和安全审计。


---

## 2025-12-11 (更新 14)

### 修改文件
- `docs/my_docs/智能猫眼门锁系统-通信协议规范-v5.0.md`

### 变更内容
1. **开锁方式扩展**（v5.0 → v5.1）：
   - 新增 `face`: 人脸开锁（STM32 D0=0x03）
   - 新增 `temp_pwd`: 临时密码开锁（STM32 D0=0x05）
   - 调整 `pwd` 密码开锁（STM32 D0=0x04）
   - 调整 `key` 机械钥匙（STM32 D0=0x06）
   - 调整 `remote` 远程开锁(App)（STM32 D0=0x07）

2. **新增数据存储规范章节**（第 10 章）：
   - 存储架构：MySQL + 文件系统
   - 数据库表设计：device_status、device_events、unlock_logs、doorlock_users、media_files
   - 媒体文件存储：目录结构、命名规范
   - 存储估算：单设备年存储量约 110GB
   - 清理策略：状态 7 天、事件 30 天、日志 90 天、媒体 30 天

### 功能说明
完善通信协议规范，扩展开锁方式以覆盖所有场景（指纹、NFC、人脸、密码、临时密码、钥匙、远程），并新增数据存储规范章节，定义服务器端数据持久化的完整方案。

---

## 2025-12-11 (更新 15)

### 新增文件
- `main/xiaozhi-server/core/providers/doorlock/media_storage.py`

### 变更内容
- 新增 `MediaStorage` 类，提供媒体文件本地存储管理功能
- 实现核心方法：
  - `save_face_image`: 保存人脸识别图片（按设备/日期分目录）
  - `save_recording`: 保存监控录像
  - `delete_file`: 删除单个文件
  - `cleanup_old_files`: 批量清理过期文件
  - `get_full_path`: 获取文件完整路径
  - `get_file_size`: 获取文件大小
- 目录结构：`data/media/faces/{device_id}/{date}/` 和 `data/media/recordings/{device_id}/{date}/`
- 文件命名：`face_{timestamp}_{user_id}.jpg` 和 `rec_{timestamp}.mp4`

### 功能说明
实现媒体文件本地存储服务，用于保存人脸识别图片和监控录像。采用按设备和日期分目录的组织方式，便于管理和清理。配合 Database 模块的 media_files 表记录元数据，实现文件存储与数据库记录的关联。

---

## 2025-12-11 (更新 16)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/eventReportHandler.py`

### 修改位置
- `EventReportHandler` 类的 `handle` 方法（第 40-55 行）
- 新增 `_save_to_database` 方法（第 58-68 行）

### 变更内容
- 新增数据库持久化功能
- 在处理事件前调用 `_save_to_database` 保存事件到数据库
- 通过 `conn.doorlock_db.save_device_event()` 调用 Database 模块的存储方法

### 功能说明
为事件上报处理器增加数据库持久化功能。当 ESP32 设备上报关键事件（门铃、PIR、撬锁、门未关、低电量）时，除了记录日志和转发给 App 外，还会将事件保存到 MySQL 数据库的 `device_events` 表中。

---

## 2025-12-11 (更新 17)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/faceRecognitionHandler.py`

### 修改位置
- `FaceRecognitionHandler` 类的 `_handle_recognize` 方法（第 75-78 行）
- 新增 `_save_face_image` 方法（第 140-162 行）

### 变更内容
1. **人脸图片保存**：
   - 在识别成功（result=known）时保存人脸图片到文件系统
   - 调用 `conn.media_storage.save_face_image()` 保存图片
   - 调用 `conn.doorlock_db.save_media_file()` 记录元数据

2. **新增 `_save_face_image` 方法**：
   - 异步保存人脸图片
   - 记录文件路径和大小到数据库

### 功能说明
为人脸识别处理器增加图片保存功能。当成功识别到已注册用户时，将人脸图片保存到本地文件系统，并在数据库中记录元数据，便于后续查看识别历史和审计。


---

## 2025-12-11 (更新 18)

### 新增文件
- `main/xiaozhi-server/core/providers/doorlock/video_recorder.py`

### 新增位置
- `core/providers/doorlock/` 目录下新增 `VideoRecorder` 类及相关数据类

### 变更内容
1. **新增数据类**：
   - `VideoFrame`: 视频帧数据（时间戳、JPEG 数据、宽高）
   - `AudioFrame`: 音频帧数据（时间戳、PCM 数据）
   - `RecordingSession`: 录像会话（设备ID、开始时间、帧列表、录制状态）

2. **新增 `VideoRecorder` 类**：
   - `start_recording(device_id)`: 开始录制
   - `add_video_frame(device_id, jpeg_data, ...)`: 添加视频帧
   - `add_audio_frame(device_id, pcm_data, ...)`: 添加音频帧
   - `stop_recording(device_id)`: 停止录制并触发后台合成
   - `_auto_segment(device_id)`: 缓存满时自动分段
   - `_do_synthesis(session)`: 执行视频合成
   - `_synthesize_with_opencv(session, output_path)`: 使用 OpenCV 合成 MP4
   - `_save_jpeg_sequence(session, output_path)`: 降级方案，保存 JPEG 序列
   - `is_recording(device_id)`: 检查录制状态
   - `get_recording_info(device_id)`: 获取录制信息
   - `shutdown()`: 关闭录像记录器

3. **后台合成机制**：
   - 使用独立线程处理视频合成，不阻塞主消息循环
   - 通过 Queue 实现任务队列
   - 支持自动分段（MAX_BUFFER_FRAMES = 6000 帧）

### 功能说明
实现监控模式下的录像功能。当 ESP32 进入监控模式时，服务器可缓存音视频帧数据，并在停止监控时后台合成 MP4 文件。采用异步设计避免阻塞主循环，支持 OpenCV 合成视频（无音频），当 OpenCV 不可用时降级为保存 JPEG 序列。录像文件保存到 `data/media/recordings/{device_id}/{date}/` 目录，并在数据库中记录元数据。


---

## 2025-12-11 (更新 19)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/systemMessageHandler.py`

### 修改位置
- `SystemTextMessageHandler` 类的 `_start_monitor` 方法（第 33-93 行）

### 变更内容
1. **新增 `enable_recording` 参数**：
   - `_start_monitor` 方法签名从 `_start_monitor(self, conn)` 改为 `_start_monitor(self, conn, enable_recording: bool = False)`
   - 新增方法文档注释说明参数用途

2. **新增录像启动逻辑**：
   - App 发起监控时：若 `enable_recording=True`，调用 `self._start_recording(esp32_conn)` 启动录像
   - ESP32 自发起监控时：同样支持录像启动

3. **响应消息扩展**：
   - 成功响应中新增 `recording` 字段，返回录像启用状态

### 功能说明
为监控模式增加可选的录像保存功能。App 或 ESP32 启动监控时可通过 `record` 参数指定是否同时启用录像，服务器会在响应中返回录像启用状态。此功能配合 `VideoRecorder` 模块实现监控视频的后台录制和 MP4 合成。


---

## 2025-12-11 (更新 20)

### 修改文件
- `main/xiaozhi-server/core/connection.py`

### 修改位置
- `ConnectionHandler` 类的 `_route_message` 方法（第 290-294 行）

### 变更内容
- 监控模式下的二进制数据处理逻辑变更
- 原：`await self._forward_to_apps(message)` - 仅转发给 App
- 改：`await self._handle_monitor_data(message, msg_type)` - 转发给 App 并支持录像
- 新增 `msg_type` 参数传递，用于区分音频帧和视频帧

### 功能说明
增强监控模式的数据处理能力。原实现仅将 ESP32 发送的音视频数据转发给 App 客户端，修改后调用 `_handle_monitor_data` 方法，在转发的同时支持将数据写入 `VideoRecorder` 进行录像保存。此变更配合 `systemMessageHandler.py` 中的录像启动逻辑，实现监控模式下的可选录像功能。


---

## 2025-12-11 (更新 21)

### 修改文件
- `main/xiaozhi-server/core/connection.py`

### 修改位置
- `ConnectionHandler` 类中，`_forward_to_apps` 方法之后（约第 456-507 行）

### 变更内容
- 新增 `_handle_monitor_data` 异步方法，处理监控模式下的音视频数据
- 解析 BinaryProtocol2 协议头部：
  - `reserved`: 4 字节，视频帧时包含分辨率（width << 16 | height）
  - `timestamp`: 4 字节，时间戳
  - `payload_size`: 4 字节，负载大小
- 根据 `reserved` 字段区分数据类型：
  - `reserved != 0`: 视频帧，提取宽高并调用 `video_recorder.add_video_frame()`
  - `reserved == 0`: 音频帧，使用 opus 解码器解码为 PCM 后调用 `video_recorder.add_audio_frame()`
- 音频解码器延迟初始化（`_opus_decoder_for_record`）

### 功能说明
实现监控模式下的录像数据处理。当 ESP32 进入监控模式并启用录像时，服务器接收到的音视频二进制数据会被解析并写入 `VideoRecorder`。视频帧（JPEG）直接存储，音频帧（OPUS）先解码为 PCM 再存储。此方法配合 `systemMessageHandler.py` 中的录像启动逻辑和 `VideoRecorder` 模块，实现完整的监控录像功能链路。


---

## 2025-12-11 (更新 18)

### 新增文件
- `main/xiaozhi-server/core/providers/doorlock/video_recorder.py`

### 变更内容
- 新增 `VideoRecorder` 类，实现监控录像保存功能
- 核心特性：
  - **异步设计**：录像合成在独立后台线程执行，不阻塞主消息循环
  - **内存缓冲**：监控期间将视频帧缓存到内存队列
  - **自动分段**：每 5 分钟或缓存满 6000 帧时自动分段
  - **OpenCV 合成**：使用 OpenCV 将 JPEG 序列合成 MP4
  - **降级方案**：OpenCV 不可用时保存 JPEG 序列
- 主要方法：
  - `start_recording(device_id)`: 开始录制
  - `add_video_frame(device_id, jpeg_data, ...)`: 添加视频帧
  - `add_audio_frame(device_id, pcm_data, ...)`: 添加音频帧
  - `stop_recording(device_id)`: 停止录制并触发后台合成

### 功能说明
实现监控模式下的录像保存功能。采用生产者-消费者模式，主线程负责接收和缓存帧数据，后台线程负责视频合成，确保不影响实时监控的性能。

---

## 2025-12-11 (更新 19)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/systemMessageHandler.py`

### 变更内容
1. **启动监控命令扩展**：
   - 新增 `record` 参数，控制是否启用录像保存
   - 默认 `record=false`，避免性能影响
2. **新增录像控制方法**：
   - `_start_recording(conn)`: 启动录像
   - `_stop_recording(conn)`: 停止录像
3. **停止监控时自动停止录像**

### 功能说明
在监控模式的启动/停止命令中集成录像功能。App 可通过 `{"type": "system", "command": "start_monitor", "record": true}` 启用录像保存。

---

## 2025-12-11 (更新 20)

### 修改文件
- `main/xiaozhi-server/core/connection.py`

### 变更内容
1. **修改 `_route_message` 方法**：
   - 监控模式下调用 `_handle_monitor_data` 替代直接转发
2. **新增 `_handle_monitor_data` 方法**：
   - 转发数据给 App
   - 解析 BinaryProtocol2 头部，区分视频帧和音频帧
   - 将帧数据添加到 `VideoRecorder`

### 功能说明
在监控模式下，除了转发数据给 App 外，还会将视频帧添加到录像器进行缓存。视频帧通过 `reserved` 字段（非 0）识别，音频帧通过 `reserved=0` 识别。

---

## 2025-12-11 (更新 21)

### 修改文件
- `docs/my_docs/智能猫眼门锁系统-通信协议规范-v5.0.md`

### 变更内容
- 更新监控模式章节（3.3）：
  - 启动监控命令新增 `record` 参数
  - 新增监控响应格式说明
  - 新增录像保存章节（3.3.5），说明录像机制和性能特性

### 功能说明
完善协议文档，记录监控录像保存功能的使用方式和技术细节。


---

## 2025-12-11 (更新 22)

### 新增文件
- `main/xiaozhi-server/core/utils/seq_id_cache.py`

### 新增位置
- `core/utils/` 目录下新增 `SeqIdCache` 类

### 变更内容
- 新增 `SeqIdCache` 类，实现按 `app_id` 分组的 seq_id 防重放缓存
- 采用 `OrderedDict` 实现 FIFO 淘汰策略
- 每个 app_id 最多缓存 100 条 seq_id
- 实现核心方法：
  - `check_and_add(app_id, seq_id)`: 检查 seq_id 是否重复，不重复则添加到缓存
  - `clear(app_id)`: 清除指定用户或所有缓存
  - `get_cache_size(app_id)`: 获取缓存大小

### 功能说明
实现 App 协议 v2.2 的消息确认机制中的防重放功能。由于 WebSocket 基于 TCP，TCP 自动重传可能导致消息重复执行，通过维护 seq_id 缓存可检测并忽略重复消息。此模块供 `AppConnectionHandler` 在处理 App 消息时调用，当检测到重复的 seq_id 时返回 `code=5` 的 server_ack 响应，避免命令重复执行。


---

## 2025-12-11 (更新 23)

### 修改文件
- `main/xiaozhi-server/core/connection_manager.py`

### 修改位置
- 文件头部 import 区域（第 1-9 行）
- `ConnectionManager` 类中新增 `notify_apps_device_status` 方法（第 32-63 行）
- `register_esp32` 方法末尾（第 73-75 行）

### 变更内容
1. **新增导入**：
   - `import json` - JSON 序列化
   - `import time` - 时间戳生成
   - `import asyncio` - 异步任务创建

2. **新增 `notify_apps_device_status` 方法**：
   - 异步方法，通知所有关联的 App 设备状态变化
   - 支持 `online` 和 `offline` 两种状态
   - `offline` 状态时可附带 `reason` 下线原因
   - 构建符合 App 协议 v2.2 的 `device_status` 通知消息

3. **修改 `register_esp32` 方法**：
   - 在 ESP32 连接注册后，调用 `asyncio.create_task()` 异步通知 App 设备上线

### 功能说明
实现 App 协议 v2.2 中的设备上下线通知功能。当 ESP32 设备连接到服务器时，服务器会自动向所有关联该设备的 App 客户端推送 `device_status` 消息，通知设备已上线。此功能使 App 能够实时感知设备连接状态，提升用户体验。后续还需在 `unregister_esp32` 方法中添加设备下线通知的调用。


---

## 2025-12-11 (更新 24)

### 修改文件
- `main/xiaozhi-server/core/app_connection.py`

### 修改位置
- `AppConnectionHandler` 类的 `_authenticate` 方法（第 102-110 行）

### 变更内容
- 在认证流程中新增 `app_id` 字段的提取和验证
- 新增代码：
  ```python
  app_id = msg_json.get("app_id")
  if not app_id:
      await self._send_error("缺少 app_id")
      return False
  ```
- 认证成功后将 `app_id` 保存到实例属性：`self.app_id = app_id`

### 功能说明
实现 App 协议 v2.2 中的 `app_id` 身份标识支持。App 客户端在发送 hello 消息时必须携带 `app_id` 字段（用户唯一标识），服务器会验证该字段是否存在，并在认证成功后保存到连接实例中。`app_id` 用于后续操作日志记录（如远程开锁时记录操作者身份）和审计追踪，是 App 协议 v2.2 命令代理机制的基础。


---

## 2025-12-11 (更新 25)

### 修改文件
- `main/xiaozhi-server/core/app_connection.py`

### 修改位置
- `AppConnectionHandler` 类中，删除 `_forward_to_esp32` 方法，新增 `_send_server_ack` 方法（第 237-252 行）

### 变更内容
1. **删除 `_forward_to_esp32` 方法**：
   - 移除旧的消息转发机制
   - 该方法原用于将 App 消息直接转发给 ESP32

2. **新增 `_send_server_ack` 方法**：
   - 实现服务器 ACK 确认机制
   - 参数：`seq_id`（消息序列号）、`code`（状态码）、`msg`（状态描述）
   - 状态码定义：0=成功, 1=设备离线, 2=参数错误, 3=未认证, 4=内部错误, 5=重复消息
   - 响应格式：`{"type": "server_ack", "seq_id": "...", "code": 0, "msg": "...", "ts": 时间戳}`

### 功能说明
实现 App 协议 v2.2 的服务器 ACK 机制。移除旧的 forward 转发模式，改为统一通过 Handler 处理消息。新增的 `_send_server_ack` 方法用于向 App 确认消息已收到，配合 `_handle_text_message` 中的 seq_id 检查逻辑，实现完整的消息确认和防重放机制。此变更是 App 协议 v2.2 代码修改计划中"移除 forward 转发机制"和"新增服务器 ACK 机制"两项任务的核心实现。


---

## 2025-12-11 (更新 26)

### 新增文件
- `main/xiaozhi-server/core/handle/textHandler/mediaDownloadHandler.py`

### 新增位置
- `core/handle/textHandler/` 目录下新增 `MediaDownloadHandler` 和 `MediaDownloadChunkHandler` 两个类

### 变更内容
1. **新增 `MediaDownloadHandler` 类**：
   - 继承 `TextMessageHandler`，消息类型为 `MEDIA_DOWNLOAD`
   - 仅处理 App 客户端（`client_type == "app"`）的请求
   - 支持通过 `file_id`（数据库查询）或 `file_path`（直接路径）定位文件
   - 实现路径安全检查，防止路径遍历攻击（`../` 等）
   - 文件大小限制 50MB，超过需使用分片下载
   - 返回 Base64 编码的文件内容及元数据（file_type、mime_type、file_size 等）

2. **新增 `MediaDownloadChunkHandler` 类**：
   - 继承 `TextMessageHandler`，消息类型为 `MEDIA_DOWNLOAD_CHUNK`
   - 支持大文件分片下载，默认分片大小 1MB，最大 5MB
   - 返回分片信息（chunk_index、total_chunks、file_size）和 Base64 编码的分片内容

3. **常量定义**：
   - `MEDIA_ROOT = "data/media"` - 媒体文件根目录
   - `MAX_DOWNLOAD_SIZE = 50MB` - 完整下载大小限制
   - `MAX_CHUNK_SIZE = 5MB` - 最大分片大小
   - `DEFAULT_CHUNK_SIZE = 1MB` - 默认分片大小

4. **MIME 类型支持**：
   - 图片：jpg、jpeg、png、gif
   - 视频：mp4、avi、mkv、webm

### 功能说明
实现 App 协议 v2.2 中的媒体文件下载功能。App 客户端可通过 WebSocket 请求下载服务器存储的人脸识别图片和监控录像文件。小文件（<50MB）使用 `media_download` 一次性下载，大文件使用 `media_download_chunk` 分片下载。此功能配合 `queryHandler.py` 中的 `media_files` 查询接口，实现完整的媒体文件浏览和下载能力。


---

## 2025-12-11 (更新 27)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/faceRecognitionHandler.py`

### 修改位置
- `FaceRecognitionHandler` 类的 `_handle_recognize` 方法（第 77-92 行）

### 变更内容
1. **图片路径变量初始化**：
   - 在保存人脸图片前新增 `image_path = None` 初始化
   - 修改 `_save_face_image` 调用以接收返回的图片存储路径

2. **到访通知参数扩展**：
   - `_notify_apps` 方法调用新增 `jpeg_data` 和 `image_path` 两个参数
   - 注释更新为"推送通知给 App（含人脸图片）"

### 功能说明
完善人脸识别到访通知的图片推送功能。修改后，当人脸识别完成时，`_notify_apps` 方法会接收到原始 JPEG 图片数据和服务器存储路径，从而能够在 `visit_notification` 消息中包含 Base64 编码的图片数据和 `image_path` 字段，使 App 客户端能够立即显示人脸抓拍图片或后续通过媒体下载接口获取原图。此变更是 App 协议 v2.2 中"到访通知推送人脸图片"功能的完整实现。


---

## 2025-12-11 (更新 28)

### 修改文件
- `main/xiaozhi-server/core/handle/textMessageHandlerRegistry.py`

### 修改位置
- 文件头部 import 区域（第 19-26 行）
- `TextMessageHandlerRegistry` 类的 `_register_default_handlers` 方法（第 57-63 行）

### 变更内容
1. **新增导入语句**：
   - `from core.handle.textHandler.queryHandler import QueryHandler`
   - `from core.handle.textHandler.mediaDownloadHandler import MediaDownloadHandler, MediaDownloadChunkHandler`
   - `from core.handle.textHandler.commandProxyHandler import LockControlProxyHandler, DevControlProxyHandler, UserMgmtProxyHandler`

2. **注册新 Handler**：
   - `QueryHandler()` - 数据查询处理器
   - `MediaDownloadHandler()` - 媒体文件下载处理器
   - `MediaDownloadChunkHandler()` - 大文件分片下载处理器
   - `LockControlProxyHandler()` - 锁控命令代理处理器
   - `DevControlProxyHandler()` - 设备控制命令代理处理器
   - `UserMgmtProxyHandler()` - 用户管理命令代理处理器

### 功能说明
完成 App 协议 v2.2 新增处理器的注册。将数据查询、媒体下载、命令代理等 6 个新 Handler 注册到消息处理器注册表中，使服务器能够处理 App 客户端发送的 `query`、`media_download`、`media_download_chunk`、`lock_control`、`dev_control`、`user_mgmt` 类型的消息。此变更是 App 协议 v2.2 代码修改计划中"注册新 Handler"任务的完成，标志着 App 协议 v2.2 的核心功能已全部实现。


---

## 2025-12-11 (更新 29)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/ackHandler.py`

### 修改位置
- 文件头部 import 区域（第 4、7 行）
- `AckHandler` 类的 `handle` 方法末尾（第 58-59 行）
- 新增 `_forward_to_apps` 方法（第 64-80 行）

### 变更内容
1. **新增导入语句**：
   - `import json` - JSON 序列化
   - `from core.connection_manager import ConnectionManager` - 连接管理器

2. **handle 方法扩展**：
   - 在处理完 ACK 响应后，调用 `_forward_to_apps` 方法转发给关联的 App

3. **新增 `_forward_to_apps` 方法**：
   - 获取 `ConnectionManager` 单例实例
   - 通过 `manager.get_app_conns(conn.device_id)` 获取所有关联的 App 连接
   - 将 ACK 消息 JSON 序列化后发送给每个 App 客户端
   - 记录转发日志

### 功能说明
实现 App 协议 v2.2 中的 ACK 转发功能。当 ESP32 设备返回 ACK 响应（确认命令执行结果）时，服务器会将该响应转发给所有关联的 App 客户端。这使得 App 能够知道通过命令代理发送的控制命令（如远程开锁、补光灯控制等）是否被 ESP32 成功执行，完善了 App → Server → ESP32 → Server → App 的完整命令执行反馈链路。


---

## 2025-12-11 (更新 30)

### 修改文件
- `main/xiaozhi-server/core/connection.py`

### 修改位置
- `ConnectionHandler` 类的 `close` 方法（约第 1230-1240 行）

### 变更内容
1. **方法签名扩展**：
   - 原：`async def close(self, ws=None)`
   - 改：`async def close(self, ws=None, reason: str = "connection_closed")`
   - 新增 `reason` 参数，用于指定断开原因

2. **调用参数传递**：
   - 原：`manager.unregister_esp32(self.device_id)`
   - 改：`manager.unregister_esp32(self.device_id, reason=reason)`
   - 将断开原因传递给 ConnectionManager

3. **文档注释更新**：
   - 新增 Args 说明，描述 `reason` 参数的用途和可选值

### 功能说明
完善设备下线通知机制。当 ESP32 设备断开连接时，`close` 方法会将断开原因（如 `connection_closed`、`timeout`、`error`）传递给 `ConnectionManager.unregister_esp32()` 方法，后者会将原因包含在 `device_status` 通知消息中推送给所有关联的 App 客户端。此变更配合 App 协议 v2.2 中的设备上下线通知功能，使 App 能够了解设备下线的具体原因，提升用户体验和问题排查能力。


---

## 2025-12-11 (更新 30)

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/database.py`

### 修改位置
- `Database` 类的 `get_unlock_logs` 方法（第 673-709 行）

### 变更内容
1. **方法签名扩展**：
   - 新增 `method: str = None` 参数：按开锁方式过滤
   - 新增 `result: int = None` 参数：按结果过滤（1=成功，0=失败）
   - 新增 `offset: int = 0` 参数：分页偏移量

2. **返回值变更**：
   - 原：`List[dict]` - 仅返回记录列表
   - 改：`Tuple[List[dict], int]` - 返回 (记录列表, 总数)

3. **查询逻辑增强**：
   - 动态构建 WHERE 条件，支持多条件组合过滤
   - 新增 COUNT 查询获取总记录数
   - 明确指定返回字段（id, method, user_id, result, fail_count, created_at）
   - datetime 字段转换为 ISO 格式字符串

### 功能说明
增强开锁日志查询接口，支持分页和多条件过滤。此变更与 App 协议 v2.2 中 `query` 接口的 `unlock_logs` 查询对齐，使 App 客户端能够按开锁方式（finger/nfc/face/pwd 等）和结果（成功/失败）筛选开锁记录，并支持分页浏览历史日志。


---

## 2025-12-11 (更新 31)

### 修改文件
- `main/xiaozhi-server/core/providers/doorlock/database.py`

### 修改位置
- `Database` 类中，`get_unlock_logs` 方法之后（第 723-753 行）

### 变更内容
- 新增 `get_media_file_by_id` 方法
- 参数：`file_id: int` - 媒体文件 ID
- 返回：`Optional[dict]` - 文件信息字典或 None
- 查询字段：id, device_id, file_type, file_path, file_size, duration, user_id, created_at
- datetime 字段自动转换为 ISO 格式字符串

### 功能说明
实现根据 ID 查询单个媒体文件元数据的功能。此方法供 `MediaDownloadHandler` 调用，当 App 客户端通过 `file_id` 请求下载媒体文件时，服务器需要先查询文件的存储路径、类型、大小等元数据，再读取文件内容返回。此变更完善了 App 协议 v2.2 中媒体文件下载功能的数据库查询支持。


---

## 2025-12-11 (更新 32)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/queryHandler.py`

### 修改位置
- 文件头部 import 区域（第 17 行）
- 新增 `_get_database` 辅助函数（第 21-30 行）

### 变更内容
1. **新增导入语句**：
   - `from core.handle.textHandler.faceRecognitionHandler import get_face_service`

2. **新增 `_get_database` 函数**：
   - 参数：`conn` - 连接对象
   - 返回：数据库实例或 None
   - 优先从 FaceService 获取数据库连接池
   - 异常时返回 None

### 功能说明
为 QueryHandler 提供统一的数据库实例获取方式。通过复用 FaceService 中已初始化的数据库连接池，避免创建多个连接池导致资源浪费，确保整个应用使用同一个数据库连接池，提升资源利用效率和连接管理的一致性。


---

## 2025-12-11 (更新 30)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/mediaDownloadHandler.py`

### 修改位置
- 文件头部 import 区域（第 16 行）
- 新增 `_get_database` 辅助函数（第 19-26 行）

### 变更内容
1. **新增导入语句**：
   - `from core.handle.textHandler.faceRecognitionHandler import get_face_service`

2. **新增 `_get_database` 辅助函数**：
   - 通过 `get_face_service(conn.logger)` 获取 FaceService 实例
   - 返回 `face_service.db` 数据库实例
   - 异常时返回 `None`

### 功能说明
为媒体下载处理器增加数据库访问能力。通过复用 FaceService 中的数据库连接池，使 `MediaDownloadHandler` 能够查询 `media_files` 表获取文件元数据（如通过 `file_id` 查询文件路径）。此实现与 `queryHandler.py` 中的 `_get_database` 函数保持一致，确保整个系统使用统一的数据库连接管理方式。


---

## 2025-12-11 (更新 33)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/statusReportHandler.py`

### 修改位置
- 文件头部 import 区域（第 9 行）
- 新增 `_get_database` 辅助函数（第 13-19 行）

### 变更内容
1. **新增导入语句**：
   - `from core.handle.textHandler.faceRecognitionHandler import get_face_service`

2. **新增 `_get_database` 辅助函数**：
   - 参数：`conn` - 连接对象
   - 返回：数据库实例或 None
   - 通过 `get_face_service(conn.logger)` 获取 FaceService 实例
   - 返回 `face_service.db` 数据库实例
   - 异常时返回 `None`

### 功能说明
为 StatusReportHandler 增加数据库访问能力。通过复用 FaceService 中已初始化的数据库连接池，使状态上报处理器能够将设备状态数据持久化到 `device_status` 表中。此实现与 `queryHandler.py`、`mediaDownloadHandler.py` 中的 `_get_database` 函数保持一致，确保整个系统使用统一的数据库连接管理方式，避免创建多个连接池导致资源浪费。


---

## 2025-12-11 (更新 34)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/logReportHandler.py`

### 修改位置
- `LogReportHandler` 类的 `_save_to_database` 方法（第 88-95 行）

### 变更内容
- 将数据库获取方式从直接访问 `conn.doorlock_db` 改为使用 `_get_database(conn)` 辅助函数
- 原：`if hasattr(conn, "doorlock_db") and conn.doorlock_db:`
- 改：`db = _get_database(conn)` + `if db:`

### 功能说明
统一数据库获取方式。通过 `_get_database()` 辅助函数从 FaceService 获取数据库实例，确保使用同一个数据库连接池。此变更与 `queryHandler.py`、`statusReportHandler.py`、`mediaDownloadHandler.py` 等处理器中的数据库获取方式保持一致，提高代码一致性和可维护性，避免因连接对象属性不存在导致的潜在错误。


---

## 2025-12-11 (更新 35)

### 修改文件
- `main/xiaozhi-server/core/connection.py`

### 修改位置
- `ConnectionHandler` 类的 `_handle_face_recognition_binary` 方法中，推送通知给 App 的代码块（约第 383-408 行）

### 变更内容
1. **新增导入**：
   - `import base64` - 用于图片数据编码

2. **通知消息格式完善**：
   - 新增 `ts` 字段：时间戳（毫秒）
   - `person_name` 字段：陌生人时从 `None` 改为 `"陌生人"`
   - 新增 `image` 字段：Base64 编码的 JPEG 图片数据
   - 新增 `image_path` 字段：暂设为 `None`（二进制接口暂不保存图片）

3. **代码优化**：
   - 将 `json.dumps(notification)` 提取为变量 `msg`，避免循环内重复序列化

### 功能说明
完善二进制人脸识别请求的到访通知推送，使其完全符合 App 协议 v2.2 的 `visit_notification` 消息格式。修改后，App 客户端在收到到访通知时可直接通过 `image` 字段获取 Base64 编码的人脸抓拍图片并立即显示，无需额外请求下载。此变更使二进制人脸识别接口与 JSON 接口的通知格式保持一致，提升 App 端的用户体验。


---

## 2025-12-12

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/logReportHandler.py`

### 修改位置
- `LogReportHandler` 类的 `_fill_user_id` 方法（第 113-136 行）
- 新增 `_save_to_database` 方法（第 138-151 行）
- 新增 `_forward_to_apps` 方法（第 153-168 行）

### 变更内容
1. **完善 `_fill_user_id` 方法**：
   - 实现人脸开锁（`method="face"`）的 uid 自动填充逻辑
   - 从 `conn.last_face_result` 缓存获取最近的人脸识别结果
   - 设置 30 秒有效期，超时则返回 0
   - 临时密码开锁（`method="temp_pwd"`）保持 uid 为 0

2. **新增 `_save_to_database` 方法**：
   - 异步保存开锁日志到数据库
   - 调用 `db.save_unlock_log()` 持久化存储

3. **新增 `_forward_to_apps` 方法**：
   - 将开锁日志实时转发给所有关联的 App 客户端
   - 通过 `ConnectionManager` 获取 App 连接列表

### 功能说明
完善开锁日志上报处理器的核心功能：
- 人脸开锁日志的 uid 自动填充：ESP32 上报人脸开锁日志时不携带 uid，服务器从最近的人脸识别结果缓存中获取并填充
- 开锁日志持久化：将日志保存到 MySQL 数据库的 `unlock_logs` 表
- 实时推送：将开锁日志转发给关联的 App 客户端，实现开锁事件的实时通知


---

## 2025-12-12 (更新)

### 修改文件
- `main/xiaozhi-server/core/connection.py`

### 修改位置
- `ConnectionHandler` 类的 `_handle_face_recognition_binary` 方法（约第 356-370 行）

### 变更内容
1. **新增人脸识别结果缓存**：
   - 在发送 JSON 响应之前，将识别结果缓存到 `self.last_face_result` 属性
   - 缓存内容包括：时间戳（ts）、识别结果（result）、用户ID（user_id）、人员姓名（person_name）、是否授权（access_granted）

2. **代码清理**：
   - 移除多余的注释 `#打印响应`

### 功能说明
为二进制人脸识别请求处理增加结果缓存功能。当 ESP32 通过二进制协议（BinaryProtocol2, type=2）发送人脸识别请求时，服务器在返回识别结果后会将结果缓存到连接对象的 `last_face_result` 属性中。此缓存供 `logReportHandler.py` 在处理 `face` 开锁日志时使用——由于 ESP32 上报人脸开锁日志时不携带 uid，服务器需要从最近的人脸识别结果中获取并填充。此变更使二进制人脸识别接口与 JSON 接口（`faceRecognitionHandler.py` 中的 `_cache_face_result` 方法）的缓存行为保持一致，确保无论使用哪种接口进行人脸识别，后续的开锁日志都能正确填充用户 ID。


---

## 2025-12-12 (更新 2)

### 修改文件
- `main/xiaozhi-server/core/handle/textHandler/logReportHandler.py`

### 修改位置
- `LogReportHandler` 类的 `_fill_user_id` 方法（第 95-160 行）

### 变更内容
1. **文档注释更新**：
   - 明确 `remote` 开锁方式也需要服务器填充 uid
   - 原："ESP32 上传 face 和 temp_pwd 开锁日志时不附带 uid"
   - 改："ESP32 上传 face 和 remote 开锁日志时不附带 uid"

2. **新增 `remote` 开锁方式的 uid 填充逻辑**（第 133-152 行）：
   - 从 `conn.last_remote_unlock` 缓存获取最近的远程开锁命令
   - 提取 `app_id` 作为 uid 填充到日志中
   - 设置 30 秒有效期，超时则返回 0 并记录警告日志

3. **注释优化**：
   - 原："其他方式返回原始 uid"
   - 改："temp_pwd 和其他方式返回原始 uid（temp_pwd 默认为 0）"

### 功能说明
完善远程开锁日志的用户追踪功能。当 App 通过命令代理发送 `lock_control` 远程开锁命令时，服务器会将 `app_id` 缓存到 `conn.last_remote_unlock`。当 ESP32 随后上报 `remote` 开锁日志时，服务器从缓存中提取 `app_id` 填充到日志的 `uid` 字段，实现远程开锁操作的用户身份追踪和审计。此变更配合 `commandProxyHandler.py` 中的缓存逻辑，完成了 App 协议 v2.2 中"通过 app_id 记录操作来源"的功能实现。

