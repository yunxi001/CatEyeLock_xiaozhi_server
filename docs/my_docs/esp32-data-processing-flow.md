# ESP32 数据处理流程详细分析

## 概述

本文档详细分析 xiaozhi-server 接收 ESP32 设备数据后的完整处理流程，包括连接建立、消息路由、数据处理和响应返回等各个环节。

## 目录

1. [连接建立流程](#1-连接建立流程)
2. [消息接收与路由](#2-消息接收与路由)
3. [文本消息处理](#3-文本消息处理)
4. [二进制音频处理](#4-二进制音频处理)
5. [智能门锁协议处理](#5-智能门锁协议处理)
6. [人脸识别处理](#6-人脸识别处理)
7. [监控模式处理](#7-监控模式处理)
8. [响应返回机制](#8-响应返回机制)

---

## 1. 连接建立流程

### 1.1 服务启动

**入口文件**: `app.py`

```python
# 启动 WebSocket 服务器（端口 8000）
ws_server = WebSocketServer(config)
ws_task = asyncio.create_task(ws_server.start())

# 启动 HTTP 服务器（端口 8003）
ota_server = SimpleHttpServer(config)
ota_task = asyncio.create_task(ota_server.start())
```

**关键组件初始化**:

- VAD (语音活动检测)
- ASR (语音识别)
- LLM (大语言模型)
- Memory (对话记忆)
- Intent (意图识别)

### 1.2 WebSocket 连接处理

**文件**: `core/websocket_server.py`

```python
async def _handle_connection(self, websocket):
    request_path = websocket.request.path

    # 路由判断
    if request_path.startswith("/ws/app"):
        # App 端点 - 使用 AppConnectionHandler
        await self._handle_app_connection(websocket)
    else:
        # ESP32 端点 - 使用 ConnectionHandler
        await self._handle_esp32_connection(websocket)
```

**连接认证流程**:

1. 提取 `device-id` 和 `client-id` (从 header 或 query 参数)
2. 检查是否启用认证 (`auth_enable`)
3. 验证设备白名单或 JWT token
4. 认证通过后创建 `ConnectionHandler` 实例

### 1.3 ConnectionHandler 初始化

**文件**: `core/connection.py`

**核心属性**:

```python
self.device_id = None           # 设备 ID
self.session_id = str(uuid.uuid4())  # 会话 ID
self.websocket = None           # WebSocket 连接
self.current_mode = "normal"    # 工作模式: normal | monitor

# 组件实例
self.vad = None                 # 语音活动检测
self.asr = None                 # 语音识别
self.tts = None                 # 语音合成
self.llm = None                 # 大语言模型
self.memory = None              # 对话记忆
self.intent = None              # 意图识别

# 队列管理
self.asr_audio_queue = queue.Queue()  # ASR 音频队列
self.report_queue = queue.Queue()     # 上报队列
```

**初始化步骤**:

1. 获取差异化配置 (`_initialize_private_config`)
2. 初始化组件 (`_initialize_components`)
3. 注册到 ConnectionManager
4. 启动超时检查任务（可选）

---

## 2. 消息接收与路由

### 2.1 消息接收入口

**文件**: `core/connection.py` - `handle_connection` 方法

```python
async for message in self.websocket:
    await self._route_message(message)
```

### 2.2 消息路由逻辑

**文件**: `core/connection.py` - `_route_message` 方法

```python
async def _route_message(self, message):
    if isinstance(message, str):
        # 文本消息 -> 文本处理器
        await handleTextMessage(self, message)

    elif isinstance(message, bytes):
        # 二进制消息 -> 进一步判断
        if len(message) >= 16:
            # 解析 BinaryProtocol2 头部
            msg_type = int.from_bytes(message[2:4], 'big')

            if msg_type == 2:
                # type=2: 人脸识别请求
                await self._handle_face_recognition_binary(message)
                return

        # 根据工作模式处理
        if self.current_mode == "monitor":
            # 监控模式: 转发给 App + 录像
            await self._handle_monitor_data(message, msg_type)
        else:
            # 正常模式: 音频送入 ASR
            if self.vad and self.asr:
                self.asr_audio_queue.put(message)
```

**消息类型分类**:

- **文本消息** (JSON 格式): 控制命令、状态上报、查询请求等
- **二进制消息** (BinaryProtocol2): 音频流、视频流、人脸识别图像

---

## 3. 文本消息处理

### 3.1 文本消息处理器架构

**文件**: `core/handle/textHandle.py`

```python
# 全局处理器注册表
message_registry = TextMessageHandlerRegistry()

# 消息处理器
message_processor = TextMessageProcessor(message_registry)

async def handleTextMessage(conn, message):
    await message_processor.process_message(conn, message)
```

### 3.2 消息类型枚举

**文件**: `core/handle/textMessageType.py`

**支持的消息类型**:

| 类型                 | 说明           | 来源         |
| -------------------- | -------------- | ------------ |
| `hello`              | 连接握手       | ESP32        |
| `abort`              | 中断播放       | ESP32        |
| `listen`             | 监听模式控制   | ESP32        |
| `iot`                | IoT 设备控制   | ESP32        |
| `status_report`      | 传感器状态上报 | ESP32 (门锁) |
| `event_report`       | 关键事件上报   | ESP32 (门锁) |
| `log_report`         | 开锁日志上报   | ESP32 (门锁) |
| `door_opened_report` | 开门日志上报   | ESP32 (门锁) |
| `password_report`    | 密码查询结果   | ESP32 (门锁) |
| `esp32_ack`          | 命令确认       | ESP32        |
| `face_recognition`   | 人脸识别请求   | ESP32        |
| `query`              | 数据查询       | App          |
| `lock_control`       | 锁控命令       | App          |
| `user_mgmt`          | 用户管理命令   | App          |

### 3.3 消息处理流程

**文件**: `core/handle/textMessageProcessor.py`

```python
async def process_message(self, conn, message: str):
    # 1. 解析 JSON
    msg_json = json.loads(message)

    # 2. 检查是否需要转发
    if msg_json.get("forward") == True:
        await self._handle_forward(conn, msg_json)
        return

    # 3. 获取消息类型
    message_type = msg_json.get("type")

    # 4. 查找并执行对应的处理器
    handler = self.registry.get_handler(message_type)
    if handler:
        await handler.handle(conn, msg_json)
```

### 3.4 典型处理器示例

#### Hello 消息处理器

**文件**: `core/handle/textHandler/helloMessageHandler.py`

**功能**: 处理连接握手，返回欢迎消息和配置信息

```python
async def handle(self, conn, msg_json):
    # 解析客户端信息
    audio_format = msg_json.get("audio_format", "opus")
    features = msg_json.get("features", {})

    # 返回欢迎消息
    welcome_msg = {
        "type": "hello",
        "session_id": conn.session_id,
        "config": {...}
    }
    await conn.websocket.send(json.dumps(welcome_msg))
```

#### 状态上报处理器

**文件**: `core/handle/textHandler/statusReportHandler.py`

**功能**: 处理智能门锁的传感器状态上报

```python
async def handle(self, conn, msg_json):
    # 1. 解析消息字段
    ts = msg_json.get("ts")
    data = msg_json.get("data", {})
    battery = data.get("bat")
    lux = data.get("lux")
    lock_state = data.get("lock", 0)
    light_state = data.get("light", 0)

    # 2. 更新内存缓存
    conn.iot_descriptors["smart_doorlock"] = {
        "battery": battery,
        "lux": lux,
        "lock_state": "open" if lock_state == 1 else "closed",
        "light_state": "on" if light_state == 1 else "off",
        "last_update": ts
    }

    # 3. 持久化到数据库
    await self._save_to_database(conn, battery, lux, lock_state, light_state)

    # 4. 转发原始消息给 App（符合 App 协议 v2.3）
    await self._forward_to_apps(conn, msg_json)

    # 5. 使用新的状态更新机制推送给 App
    # 更新灯状态
    if light_state is not None:
        await conn.update_device_state("light", {
            "status": "on" if light_state == 1 else "off"
        })

    # 更新门锁状态
    if lock_state is not None:
        await conn.update_device_state("door", {
            "status": "open" if lock_state == 1 else "closed",
            "locked": lock_state == 0
        })

    # 更新传感器数据
    if battery is not None:
        await conn.update_device_state("sensor", {
            "name": "battery",
            "value": battery,
            "unit": "%"
        })

    if lux is not None:
        await conn.update_device_state("sensor", {
            "name": "lux",
            "value": lux,
            "unit": "lux"
        })
```

**推送机制**:

- **原始消息转发**: 直接转发 ESP32 的 `status_report` 消息给 App
- **分类状态推送**: 通过 `update_device_state()` 按类型（light/door/sensor）推送 `device_state_update` 消息

---

## 4. 二进制音频处理

### 4.1 音频接收流程

**文件**: `core/connection.py` - `_route_message` 方法

```python
# 正常模式下的音频处理
if self.vad and self.asr:
    self.asr_audio_queue.put(message)  # 放入队列
```

### 4.2 VAD (语音活动检测)

**文件**: `core/handle/receiveAudioHandle.py`

```python
async def handleAudioMessage(conn, audio):
    # 1. VAD 检测是否有人说话
    have_voice = conn.vad.is_vad(conn, audio)

    # 2. 如果检测到语音且正在播放，打断播放
    if have_voice and conn.client_is_speaking:
        await handleAbortMessage(conn)

    # 3. 更新活动时间戳
    await no_voice_close_connect(conn, have_voice)

    # 4. 将音频送入 ASR
    await conn.asr.receive_audio(conn, audio, have_voice)
```

### 4.3 ASR (语音识别)

**Provider 模式**: `core/providers/asr/`

**处理流程**:

1. **音频缓冲**: 累积音频数据直到检测到语音结束
2. **格式转换**: Opus → PCM (如需要)
3. **识别请求**: 调用 ASR 服务 (本地/云端)
4. **结果返回**: 识别文本 → `startToChat`

**关键方法**:

```python
async def receive_audio(self, conn, audio, have_voice):
    if have_voice:
        # 累积音频
        conn.asr_audio.append(audio)
    else:
        if len(conn.asr_audio) > 0:
            # 语音结束，开始识别
            result = await self.recognize(conn.asr_audio)
            await startToChat(conn, result)
            conn.asr_audio.clear()
```

### 4.4 对话处理

**文件**: `core/handle/receiveAudioHandle.py` - `startToChat` 方法

```python
async def startToChat(conn, text):
    # 1. 解析说话人信息（如有）
    speaker_name = None
    if text.startswith("{"):
        data = json.loads(text)
        speaker_name = data.get("speaker")
        actual_text = data.get("content")

    # 2. 检查设备绑定状态
    if conn.need_bind:
        await check_bind_device(conn)
        return

    # 3. 检查输出限额
    if check_device_output_limit(conn.device_id, conn.max_output_size):
        await max_out_size(conn)
        return

    # 4. 意图识别
    intent_handled = await handle_user_intent(conn, actual_text)
    if intent_handled:
        return

    # 5. 发送 STT 消息给 ESP32
    await send_stt_message(conn, actual_text)

    # 6. 调用 LLM 生成回复
    conn.executor.submit(conn.chat, actual_text)
```

### 4.5 LLM 对话处理

**文件**: `core/connection.py` - `chat` 方法

**流程**:

1. **创建会话**: 生成 `sentence_id`
2. **查询记忆**: 获取历史对话上下文
3. **意图识别**: 检测是否需要调用工具
4. **流式响应**: 逐句生成回复
5. **TTS 合成**: 将文本转为语音
6. **工具调用**: 处理 function call (如需要)

```python
def chat(self, query, depth=0):
    # 1. 初始化
    self.sentence_id = str(uuid.uuid4().hex)
    self.dialogue.put(Message(role="user", content=query))

    # 2. 查询记忆
    memory_str = await self.memory.query_memory(query)

    # 3. 调用 LLM
    if self.intent_type == "function_call":
        llm_responses = self.llm.response_with_functions(
            self.session_id,
            self.dialogue.get_llm_dialogue_with_memory(memory_str),
            functions=self.func_handler.get_functions()
        )
    else:
        llm_responses = self.llm.response(...)

    # 4. 处理流式响应
    for response in llm_responses:
        if tool_call_flag:
            # 工具调用
            await self.func_handler.handle_llm_function_call(...)
        else:
            # 普通文本 -> TTS
            self.tts.tts_text_queue.put(...)
```

---

## 5. 智能门锁协议处理

### 5.1 协议版本

- **ESP32 协议**: v5.2 (BinaryProtocol2 + JSON)
- **App 协议**: v2.3

### 5.2 状态上报处理

**消息类型**: `status_report`

**文件**: `core/handle/textHandler/statusReportHandler.py`

**数据结构**:

```json
{
  "type": "status_report",
  "ts": 1702234567890,
  "data": {
    "bat": 85, // 电量百分比
    "lux": 300, // 光照值
    "lock": 0, // 锁状态: 0=关闭, 1=打开
    "light": 1 // 补光灯: 0=灭, 1=亮
  }
}
```

**处理逻辑**:

1. **解析消息字段** - 提取电量、光照、锁状态、灯状态
2. **更新内存缓存** - 存储到 `conn.iot_descriptors["smart_doorlock"]`
3. **持久化到数据库** - 调用 `db.save_device_status()`
4. **转发原始消息给 App** - 调用 `_forward_to_apps()` 发送原始 `status_report`
5. **推送分类状态给 App** - 调用 `conn.update_device_state()` 发送 `device_state_update`

**推送机制**:

- **原始消息**: 直接转发 ESP32 的 `status_report` 消息（符合 App 协议 v2.3）
- **分类消息**: 按类型推送 `device_state_update` 消息（light/door/sensor）
- App 可以同时接收两种消息，提供更灵活的选择

### 5.3 事件上报处理

**消息类型**: `event_report`

**文件**: `core/handle/textHandler/eventReportHandler.py`

**事件类型**:

- `doorbell_pressed`: 门铃按下
- `motion_detected`: 人体感应
- `door_forced_open`: 门被撬
- `low_battery`: 电量低

**处理逻辑**:

1. 解析事件类型和参数
2. 触发对应的处理逻辑 (如报警、通知)
3. 推送给 App
4. 保存事件记录

### 5.4 开锁日志上报

**消息类型**: `door_opened_report`

**文件**: `core/handle/textHandler/doorOpenedReportHandler.py`

**数据结构**:

```json
{
  "type": "door_opened_report",
  "seq_id": 123,
  "ts": 1234567890,
  "method": "password",
  "uid": "user_001",
  "result": "success"
}
```

**处理逻辑**:

1. 保存开锁记录到数据库
2. 如果是人脸开锁，关联人脸识别结果
3. 推送通知给 App
4. 返回 ACK 给 ESP32

### 5.5 密码查询处理

**消息类型**: `password_report`

**文件**: `core/handle/textHandler/passwordReportHandler.py`

**流程**:

1. ESP32 发送 `password_report` (包含密码列表)
2. 服务器转发给请求的 App
3. App 显示密码列表

---

## 6. 人脸识别处理

### 6.1 二进制格式处理

**文件**: `core/connection.py` - `_handle_face_recognition_binary` 方法

**协议**: BinaryProtocol2 (type=2)

**流程**:

```python
async def _handle_face_recognition_binary(self, message: bytes):
    # 1. 解析图像数据
    jpeg_data = face_service.parse_image(message)

    # 2. 执行人脸识别
    result = face_service.recognize(jpeg_data)

    # 3. 检查权限
    access_granted, deny_reason = face_service.check_permission(result.person.id)

    # 4. 生成问候语
    greeting = face_service.generate_greeting(result, access_granted, deny_reason)

    # 5. 保存到访记录
    visit_id = face_service.save_visit_record(result, access_granted, deny_reason, jpeg_data)

    # 6. 返回识别结果
    response = {
        "type": "face_result",
        "result": result.result,  # "known" | "unknown" | "no_face"
        "user_id": result.person.id,
        "access": {
            "granted": access_granted,
            "reason": "authorized_user" | "unauthorized_user"
        }
    }
    await conn.websocket.send(json.dumps(response))

    # 7. 播放 TTS 问候语（标准三段式流程）
    if greeting:
        sentence_id = str(uuid.uuid4().hex)

        # FIRST(ACTION) - 开始标记
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=sentence_id,
                sentence_type=SentenceType.FIRST,
                content_type=ContentType.ACTION,
            )
        )

        # MIDDLE(TEXT, greeting) - 实际问候语
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.TEXT,
                content_detail=greeting
            )
        )

        # LAST(ACTION) - 结束标记
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=sentence_id,
                sentence_type=SentenceType.LAST,
                content_type=ContentType.ACTION,
            )
        )

    # 8. 推送通知给 App (含图片)
    notification = {
        "type": "visit_notification",
        "data": {
            "visit_id": visit_id,
            "person_name": result.person.name,
            "image": base64.b64encode(jpeg_data).decode()
        }
    }
```

### 6.2 人脸识别服务

**文件**: `core/handle/textHandler/faceRecognitionHandler.py`

**核心功能**:

- **人脸检测**: 检测图像中是否有人脸
- **特征提取**: 提取人脸特征向量
- **特征匹配**: 与数据库中的人脸特征比对
- **权限验证**: 检查用户是否有开门权限
- **记录保存**: 保存到访记录和图片

**配置文件**: `config/face_recognition_config.yaml`

---

## 7. 监控模式处理

### 7.1 模式切换

**触发方式**: App 发送 `{"type": "system", "action": "start_monitor"}`

**状态变化**:

```python
conn.current_mode = "monitor"  # normal → monitor
```

### 7.2 音视频转发

**文件**: `core/connection.py` - `_handle_monitor_data` 方法

**流程**:

```python
async def _handle_monitor_data(self, message: bytes, msg_type: int):
    # 1. 转发给 App
    await self._forward_to_apps(message)

    # 2. 如果启用录像，添加到录像器
    if self.video_recorder and self.video_recorder.is_recording(self.device_id):
        # 解析帧类型
        reserved = int.from_bytes(message[4:8], 'big')
        is_video = (reserved != 0)

        if is_video:
            # 视频帧 (JPEG)
            self.video_recorder.add_video_frame(...)
        else:
            # 音频帧 (Opus → PCM)
            pcm_data = self._opus_decoder.decode(payload, 960)
            self.video_recorder.add_audio_frame(...)
```

### 7.3 数据转发逻辑

**文件**: `core/connection.py` - `_forward_to_apps` 方法

**音频帧处理**:

1. 解析 BinaryProtocol2 头部
2. 提取 Opus payload
3. 初始化 Opus 解码器（延迟初始化，包含错误计数器和错误时间戳）
4. 解码为 PCM (16kHz, 单声道, 960 采样点)
5. 广播给所有 App

**视频帧处理**:

1. 解析 BinaryProtocol2 头部
2. 提取 JPEG 数据
3. 直接转发完整帧给所有 App (保持协议格式)

**错误处理**:

- Opus 解码失败时限制日志频率（每 5 秒或每 100 次错误）
- 累计错误 > 10 次时自动重置解码器
- WebSocket 发送失败记录警告日志，不中断其他 App 的转发

---

## 8. 响应返回机制

### 8.1 TTS 音频返回

**文件**: `core/handle/sendAudioHandle.py`

**流程**:

```python
# 1. LLM 生成文本
conn.tts.tts_text_queue.put(TTSMessageDTO(
    sentence_id=sentence_id,
    sentence_type=SentenceType.MIDDLE,
    content_type=ContentType.TEXT,
    content_detail="你好，我是小智"
))

# 2. TTS 合成音频
opus_packets = await tts_provider.synthesize(text)

# 3. 发送音频给 ESP32
conn.tts.tts_audio_queue.put((SentenceType.MIDDLE, opus_packets, text))

# 4. WebSocket 发送
await conn.websocket.send(opus_packet)
```

### 8.2 JSON 响应返回

**通用格式**:

```json
{
  "type": "response_type",
  "seq_id": 123,  // 如果是响应，携带请求的 seq_id
  "status": "success" | "error",
  "data": {...}
}
```

**示例 - 锁控命令响应**:

```json
{
  "type": "lock_control_response",
  "seq_id": 456,
  "status": "success",
  "data": {
    "action": "unlock",
    "result": "success"
  }
}
```

### 8.3 上报机制

**文件**: `core/handle/reportHandle.py`

**功能**: 将 ASR 和 TTS 数据上报到管理后台

**流程**:

```python
# 1. 加入上报队列
conn.report_queue.put((type, text, opus_data, report_time))

# 2. 上报线程处理
def _report_worker(self):
    while not self.stop_event.is_set():
        item = self.report_queue.get(timeout=1)
        self.executor.submit(self._process_report, *item)

# 3. 执行上报
def _process_report(self, type, text, audio_data, report_time):
    # 转换 Opus → WAV
    wav_data = opus_to_wav(conn, opus_data)

    # 调用管理 API
    manage_report(
        mac_address=conn.device_id,
        session_id=conn.session_id,
        chat_type=type,  # 1=用户, 2=智能体
        content=text,
        audio=wav_data,
        report_time=report_time
    )
```

---

## 9. 连接管理

### 9.1 ConnectionManager

**文件**: `core/connection_manager.py`

**功能**:

- 管理所有 ESP32 和 App 连接
- 提供连接查询接口
- 处理设备上下线通知

**核心方法**:

```python
class ConnectionManager:
    def register_esp32(self, device_id, conn):
        """注册 ESP32 连接"""

    def unregister_esp32(self, device_id, reason):
        """注销 ESP32 连接，并通知 App"""

    def get_esp32_conn(self, device_id):
        """获取 ESP32 连接"""

    def get_app_conns(self, device_id):
        """获取设备关联的所有 App 连接"""
```

### 9.2 连接生命周期

**建立连接**:

1. WebSocket 握手
2. 认证验证
3. 创建 ConnectionHandler
4. 注册到 ConnectionManager
5. 初始化组件

**维持连接**:

1. 心跳检测 (可选)
2. 超时检查 (可选，已禁用)
3. 消息处理

**断开连接**:

1. 触发 `close` 方法
2. 从 ConnectionManager 注销
3. 通知关联的 App
4. 保存对话记忆
5. 清理资源 (队列、线程池、WebSocket)

---

## 10. 数据流图

### 10.1 音频对话流程

```
ESP32 设备
    ↓ (Opus 音频流)
WebSocket 连接
    ↓
ConnectionHandler._route_message
    ↓
asr_audio_queue
    ↓
VAD 检测
    ↓
ASR 识别
    ↓
startToChat
    ↓
意图识别 → 工具调用
    ↓
LLM 生成回复
    ↓
TTS 合成
    ↓
tts_audio_queue
    ↓
WebSocket 发送
    ↓
ESP32 播放
```

### 10.2 智能门锁状态上报流程

```
ESP32 门锁
    ↓ (JSON: status_report)
WebSocket 连接
    ↓
handleTextMessage
    ↓
StatusReportHandler
    ├─ 解析消息字段 (bat, lux, lock, light)
    ├─ 更新内存缓存 (iot_descriptors)
    ├─ 持久化到数据库 (save_device_status)
    ├─ 转发原始消息给 App (_forward_to_apps)
    │   └─ 发送 status_report 消息
    └─ 推送分类状态给 App (update_device_state)
        ├─ 发送 device_state_update (light)
        ├─ 发送 device_state_update (door)
        └─ 发送 device_state_update (sensor × 2)
```

> **注意**: App 会同时接收原始 `status_report` 消息和分类后的 `device_state_update` 消息

### 10.3 人脸识别流程

```
ESP32 摄像头
    ↓ (BinaryProtocol2: type=2, JPEG 图像)
WebSocket 连接
    ↓
_handle_face_recognition_binary
    ↓
FaceRecognitionService
    ↓
人脸检测 → 特征提取 → 特征匹配
    ↓
权限验证 (时间限制、黑名单、访客过期)
    ↓
生成问候语
    ↓
保存到访记录
    ↓
构建响应消息 (face_result)
    ↓
缓存识别结果 (30秒有效期)
    ↓
发送 JSON 响应给 ESP32
    ↓
播放 TTS 问候语（标准三段式）
    ├─ FIRST(ACTION) - 开始标记
    ├─ MIDDLE(TEXT, greeting) - 实际问候语
    └─ LAST(ACTION) - 结束标记
    ↓
推送通知给 App (visit_notification)
    └─ 含 base64 编码的人脸图片
```

---

## 11. 关键配置

### 11.1 服务器配置

**文件**: `config.yaml`

```yaml
server:
  ip: "0.0.0.0"
  port: 8000 # WebSocket 端口
  http_port: 8003 # HTTP API 端口
  auth_key: "your_secret_key"
  auth:
    enabled: false # 是否启用认证
    allowed_devices: [] # 设备白名单
    expire_seconds: 3600 # Token 过期时间

selected_module:
  VAD: "VAD_silero"
  ASR: "ASR_funasr"
  LLM: "LLM_openai"
  TTS: "TTS_edge"
  Memory: "Memory_local_short"
  Intent: "Intent_llm"

# 超时配置
close_connection_no_voice_time: 120 # 无语音超时时间（秒）
```

### 11.2 人脸识别配置

**文件**: `config/face_recognition_config.yaml`

```yaml
face_recognition:
  enabled: true
  model_path: "models/face_recognition"
  threshold: 0.6 # 识别阈值
  max_faces: 5 # 最大人脸数
  save_images: true # 是否保存图片
  image_dir: "data/face_recognition/visits"
```

---

## 12. 错误处理

### 12.1 连接错误

**场景**: WebSocket 连接异常、认证失败

**处理**:

```python
try:
    await handler.handle_connection(websocket)
except AuthenticationError:
    await websocket.send("认证失败")
    await websocket.close()
except Exception as e:
    logger.error(f"连接错误: {e}")
finally:
    await self._save_and_close(ws)
```

### 12.2 消息处理错误

**场景**: JSON 解析失败、处理器异常

**处理**:

```python
try:
    msg_json = json.loads(message)
    handler = self.registry.get_handler(message_type)
    await handler.handle(conn, msg_json)
except json.JSONDecodeError:
    logger.error(f"JSON 解析失败: {message}")
except Exception as e:
    logger.error(f"消息处理失败: {e}")
```

### 12.3 组件错误

**场景**: ASR 识别失败、TTS 合成失败、LLM 调用失败

**处理**:

- 记录错误日志
- 返回友好的错误提示
- 不中断连接，继续处理后续消息

---

## 13. 性能优化

### 13.1 异步处理

- 使用 `asyncio` 处理并发连接
- 使用 `ThreadPoolExecutor` 处理 CPU 密集型任务
- 使用队列解耦生产者和消费者

### 13.2 资源管理

- 连接级别的组件实例 (ASR, TTS)
- 共享的全局组件 (VAD, LLM)
- 及时释放资源 (关闭连接时)

### 13.3 缓存机制

- 对话记忆缓存
- 人脸特征缓存
- 配置缓存

---

## 14. 安全机制

### 14.1 认证

- JWT Token 认证
- 设备白名单
- Token 过期时间

### 14.2 权限控制

- 人脸识别权限验证
- 开锁权限验证
- API 访问权限

### 14.3 数据保护

- 敏感信息过滤 (日志)
- 图片加密存储
- 通信加密 (WSS)

---

## 15. 监控与日志

### 15.1 日志系统

**使用**: `loguru`

**日志级别**:

- DEBUG: 详细调试信息
- INFO: 一般信息
- WARNING: 警告信息
- ERROR: 错误信息

**日志格式**:

```python
logger.bind(tag=TAG).info(f"收到消息: {message}")
```

### 15.2 性能监控

- 连接数统计
- 消息处理时延
- ASR/TTS 响应时间
- LLM 调用时延

---

## 16. 扩展点

### 16.1 Provider 模式

**新增 AI 服务商**:

1. 在 `core/providers/{type}/` 下创建新文件
2. 继承 `base.py` 中的抽象基类
3. 实现所有抽象方法
4. 在 `config.yaml` 中配置

### 16.2 插件系统

**新增插件**:

1. 在 `plugins_func/functions/` 下创建 Python 文件
2. 定义 `name`, `description`, `parameters` (JSON Schema)
3. 实现插件逻辑
4. 插件由 `loadplugins.py` 自动加载

### 16.3 消息处理器

**新增消息类型**:

1. 在 `TextMessageType` 枚举中添加新类型
2. 在 `core/handle/textHandler/` 下创建处理器
3. 继承 `TextMessageHandler` 基类
4. 实现 `handle` 方法
5. 注册到 `TextMessageHandlerRegistry`

---

## 17. 总结

xiaozhi-server 的数据处理流程采用了**分层架构**和**模块化设计**:

1. **连接层**: WebSocket 连接管理、认证、路由
2. **消息层**: 文本消息处理、二进制消息处理
3. **业务层**: 语音对话、智能门锁、人脸识别
4. **服务层**: ASR、TTS、LLM、VAD 等 AI 服务
5. **存储层**: 数据库、文件存储、缓存

**核心特点**:

- **异步处理**: 高并发支持
- **Provider 模式**: 灵活切换 AI 服务商
- **插件化**: 易于扩展功能
- **协议兼容**: 支持多版本协议
- **多端协同**: ESP32、App、服务器三端联动

**数据流向**:

```
ESP32 → WebSocket → ConnectionHandler → 消息路由 → 业务处理 → AI 服务 → 响应返回 → ESP32/App
```

这种架构设计使得系统具有良好的**可扩展性**、**可维护性**和**高性能**。

---

## 附录

### A. 相关文件索引

| 功能模块       | 核心文件                                            |
| -------------- | --------------------------------------------------- |
| 服务启动       | `app.py`                                            |
| WebSocket 服务 | `core/websocket_server.py`                          |
| 连接处理       | `core/connection.py`                                |
| 消息路由       | `core/handle/textMessageProcessor.py`               |
| 音频处理       | `core/handle/receiveAudioHandle.py`                 |
| 文本处理       | `core/handle/textHandle.py`                         |
| 人脸识别       | `core/handle/textHandler/faceRecognitionHandler.py` |
| 智能门锁       | `core/handle/textHandler/statusReportHandler.py`    |
| 连接管理       | `core/connection_manager.py`                        |
| 上报机制       | `core/handle/reportHandle.py`                       |

### B. 协议文档

- ESP32 协议 v5.2: `docs/my_docs/智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md`
- App 协议 v2.3: `docs/my_docs/智能猫眼门锁系统-服务器与App通信协议规范-v2.3.md`
- 服务器架构: `docs/my_docs/智能猫眼门锁系统-服务器端架构说明.md`

### C. 开发指南

- 项目分析: `docs/my_docs/project-analysis.md`
- 智能门锁测试: `docs/my_docs/smart-doorlock-test-guide.md`
- 智能门锁使用: `docs/my_docs/smart-doorlock-usage-guide.md`

---

**文档版本**: v1.0  
**最后更新**: 2026-01-30  
**作者**: Kiro AI Assistant
