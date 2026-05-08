# ESP32 数据处理流程详细分析 - 核心模块

本文档深入分析智能门锁协议处理、人脸识别处理、监控模式处理和响应返回机制四个核心模块的详细处理逻辑。

## 目录

1. [智能门锁协议处理](#1-智能门锁协议处理)
2. [人脸识别处理](#2-人脸识别处理)
3. [监控模式处理](#3-监控模式处理)
4. [响应返回机制](#4-响应返回机制)

---

## 1. 智能门锁协议处理

### 1.1 状态上报处理 (status_report)

**文件**: `core/handle/textHandler/statusReportHandler.py`

**消息格式**:

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

1. **解析消息字段**
   - 提取时间戳 `ts`
   - 提取数据字段 `data` (battery, lux, lock_state, light_state)
   - 验证字段完整性

2. **更新内存缓存**

   ```python
   conn.iot_descriptors["smart_doorlock"] = {
       "battery": battery,
       "lux": lux,
       "lock_state": "open" if lock_state == 1 else "closed",
       "light_state": "on" if light_state == 1 else "off",
       "last_update": ts
   }
   ```

3. **持久化到数据库**
   - 调用 `db.save_device_status()` 保存状态
   - 包含设备 ID、电量、光照、锁状态、灯状态
   - 失败不影响后续流程，仅记录警告日志

4. **更新设备状态对象**
   - 更新灯状态: `conn.update_device_state("light", {...})`
   - 更新门锁状态: `conn.update_device_state("door", {...})`
   - 更新传感器数据: `conn.update_device_state("sensor", {...})`

5. **推送给关联的 App**
   - 通过 `ConnectionManager` 获取所有关联的 App 连接
   - 遍历 App 连接，发送原始 JSON 消息
   - 失败记录错误日志，不中断流程

**流程图**:

```
ESP32 发送 status_report
    ↓
解析消息字段 (bat, lux, lock, light)
    ↓
更新内存缓存 (conn.iot_descriptors)
    ↓
持久化到数据库 (db.save_device_status)
    ↓
更新设备状态对象 (conn.device_state)
    ↓
获取关联的 App 连接 (ConnectionManager)
    ↓
遍历推送给所有 App
    ↓
完成
```

---

### 1.2 事件上报处理 (event_report)

**文件**: `core/handle/textHandler/eventReportHandler.py`

**消息格式**:

```json
{
  "type": "event_report",
  "ts": 1702234567890,
  "event": "bell", // 事件类型
  "param": 1 // 事件参数
}
```

**支持的事件类型**:

- `bell`: 门铃按下
- `pir_trigger`: PIR 人体检测
- `tamper`: 撬锁报警
- `door_open`: 门未关超时
- `low_battery`: 低电量警告
- `door_closed`: 门已关闭 (v5.2 新增)
- `lock_success`: 上锁成功 (v5.2 新增)
- `bolt_alarm`: 反锁报警 (v5.2 新增)

**处理逻辑**:

1. **解析并验证事件类型**
   - 提取 `event` 和 `param` 字段
   - 验证事件类型是否在有效列表中
   - 未知事件记录警告但仍然转发

2. **持久化到数据库**
   - 调用 `db.save_device_event()` 保存事件记录
   - 包含设备 ID、事件类型、事件参数
   - 失败记录警告日志

3. **根据事件类型分发处理**

   ```python
   if event == "bell":
       await self._handle_bell_event(conn, ts, param)
   elif event == "pir_trigger":
       await self._handle_pir_event(conn, ts, param)
   elif event == "tamper":
       await self._handle_tamper_event(conn, ts, param)
   # ... 其他事件类型
   ```

4. **事件特定处理**
   - **门铃事件**: 记录日志 "门铃按下"
   - **PIR 事件**: 记录持续时间 "PIR 检测到人体，持续 X 秒"
   - **撬锁报警**: 记录报警级别 "撬锁报警！级别: X"
   - **门未关超时**: 记录超时时间 "门未关超时: X 分钟"
   - **低电量警告**: 记录电量 "低电量警告: X%"
   - **门已关闭**: 记录日志 "门已关闭"
   - **上锁成功**: 记录日志 "上锁成功"
   - **反锁报警**: 记录报警类型 "反锁报警！类型: X"

5. **转发给关联的 App**
   - 通过 `ConnectionManager` 获取所有关联的 App 连接
   - 遍历 App 连接，发送原始 JSON 消息
   - 失败记录错误日志

**流程图**:

```
ESP32 发送 event_report
    ↓
解析事件类型和参数
    ↓
验证事件类型有效性
    ↓
持久化到数据库 (db.save_device_event)
    ↓
根据事件类型分发处理
    ├─ bell → 记录门铃日志
    ├─ pir_trigger → 记录 PIR 检测日志
    ├─ tamper → 记录撬锁报警日志
    ├─ door_open → 记录门未关超时日志
    ├─ low_battery → 记录低电量警告日志
    ├─ door_closed → 记录门已关闭日志
    ├─ lock_success → 记录上锁成功日志
    └─ bolt_alarm → 记录反锁报警日志
    ↓
获取关联的 App 连接
    ↓
遍历推送给所有 App
    ↓
完成
```

---

### 1.3 开锁日志上报处理 (log_report)

**文件**: `core/handle/textHandler/logReportHandler.py`

**消息格式 (v5.2)**:

```json
{
  "type": "log_report",
  "ts": 1702234567890,
  "data": {
    "method": "finger", // 开锁方式
    "uid": 5, // 用户 ID
    "status": "success", // 开锁状态: success/fail/locked
    "lock_time": 0, // 剩余锁定时间（分钟）
    "fail_count": 0 // 连续失败次数
  }
}
```

**开锁方式 (method)**:

- `finger`: 指纹开锁
- `nfc`: NFC 开锁
- `face`: 人脸开锁（ESP32 不传 uid，服务器填充）
- `pwd`: 密码开锁
- `temp_pwd`: 临时密码开锁（uid 默认为 0）
- `key`: 机械钥匙
- `remote`: 远程开锁（ESP32 不传 uid，服务器填充）

**处理逻辑**:

1. **解析消息字段**
   - 提取 `method`, `uid`, `fail_count`
   - 支持 v5.2 新版 `status` 字段
   - 兼容 v5.0 旧版 `result` 字段（true/false）

   ```python
   if "status" in data:
       status = data["status"]  # v5.2 新版
       lock_time = data.get("lock_time", 0)
   elif "result" in data:
       result = data["result"]  # v5.0 旧版
       status = "success" if result else "fail"
       lock_time = 0
   ```

2. **验证字段取值**
   - 验证 `status` 必须是 `success`, `fail`, `locked` 之一
   - 验证 `locked` 状态时 `lock_time` 必须 > 0
   - 验证 `success/fail` 状态时 `lock_time` 应该为 0
   - 不符合规范记录警告日志

3. **填充用户 ID**
   - 调用 `_fill_user_id()` 方法
   - **人脸开锁 (face)**:
     - 从 `conn.last_face_result` 获取最近的人脸识别结果
     - 检查识别结果是否在 30 秒有效期内
     - 提取 `user_id` 填充到日志
     - 无有效结果记录警告，uid 为 0
   - **远程开锁 (remote)**:
     - 从 `conn.last_remote_unlock` 获取最近的远程开锁命令
     - 检查命令是否在 30 秒有效期内
     - 提取 `app_id` 填充到日志
     - 无有效命令记录警告，uid 为 0
   - **临时密码 (temp_pwd)**: uid 默认为 0
   - **其他方式**: 使用 ESP32 上传的 uid

4. **更新消息中的 uid**

   ```python
   msg_json["data"]["uid"] = uid
   ```

   确保转发给 App 时包含正确的 uid

5. **增强日志输出**
   - **成功**: `开锁成功: method=finger, uid=5, status=success`
   - **锁定**: `设备已锁定: method=pwd, uid=0, status=locked, lock_time=30分钟`
   - **失败**: `开锁失败: method=finger, uid=3, status=fail, fail_count=2`
   - **连续失败 ≥ 5 次**: `连续开锁失败 5 次，触发警报`

6. **持久化到数据库**
   - 调用 `db.save_unlock_log()` 保存开锁日志
   - 包含设备 ID、开锁方式、用户 ID、状态、锁定时间、失败次数
   - 失败记录警告日志

7. **转发给关联的 App**
   - 通过 `ConnectionManager` 获取所有关联的 App 连接
   - 遍历 App 连接，发送更新后的 JSON 消息（含填充的 uid）
   - 失败记录错误日志

**流程图**:

```
ESP32 发送 log_report
    ↓
解析消息字段 (method, uid, status, lock_time, fail_count)
    ↓
兼容旧版 result 字段 (v5.0)
    ↓
验证字段取值 (status, lock_time)
    ↓
填充用户 ID
    ├─ face → 从 last_face_result 获取
    ├─ remote → 从 last_remote_unlock 获取
    └─ 其他 → 使用原始 uid
    ↓
更新消息中的 uid
    ↓
增强日志输出 (根据 status)
    ├─ success → 记录成功日志
    ├─ locked → 记录锁定日志
    └─ fail → 记录失败日志 + 检查连续失败次数
    ↓
持久化到数据库 (db.save_unlock_log)
    ↓
获取关联的 App 连接
    ↓
遍历推送给所有 App (含填充的 uid)
    ↓
完成
```

---

### 1.4 开门日志上报处理 (door_opened_report)

**文件**: `core/handle/textHandler/doorOpenedReportHandler.py`

**消息格式**:

```json
{
  "type": "door_opened_report",
  "ts": 1702234567890,
  "data": {
    "method": "finger", // 开锁方式
    "source": "outside" // 开门来源: outside/inside/unknown
  }
}
```

**处理逻辑**:

1. **解析并验证消息字段**
   - 提取 `method` 和 `source` 字段
   - 验证 `method` 必须存在
   - 验证 `source` 必须存在
   - 缺少必需字段记录错误并返回

2. **验证字段取值范围**
   - **method 有效值**: `finger`, `nfc`, `face`, `pwd`, `temp_pwd`, `key`, `remote`
   - **source 有效值**: `outside`, `inside`, `unknown`
   - 无效值记录警告但继续处理

3. **记录日志**

   ```python
   conn.logger.info(f"开门日志: method={method}, source={source}, ts={ts}")
   ```

4. **持久化到数据库**
   - 调用 `db.save_door_opened_log()` 保存开门日志
   - 包含设备 ID、开锁方式、开门来源
   - 失败记录警告日志，不影响转发

5. **转发给关联的 App**
   - 通过 `ConnectionManager` 获取所有关联的 App 连接
   - 遍历 App 连接，发送原始 JSON 消息
   - 失败记录错误日志

**流程图**:

```
ESP32 发送 door_opened_report
    ↓
解析消息字段 (method, source)
    ↓
验证必需字段存在
    ↓
验证字段取值范围
    ↓
记录开门日志
    ↓
持久化到数据库 (db.save_door_opened_log)
    ↓
获取关联的 App 连接
    ↓
遍历推送给所有 App
    ↓
完成
```

---

## 2. 人脸识别处理

### 2.1 二进制格式人脸识别 (BinaryProtocol2)

**文件**: `core/connection.py` - `_handle_face_recognition_binary` 方法

**协议**: BinaryProtocol2 (type=2)

**消息格式**:

```
[16 字节头部] + [JPEG 图像数据]

头部结构:
- version (2 bytes): 协议版本
- type (2 bytes): 消息类型 (2 = 人脸识别)
- reserved (4 bytes): 保留字段
- timestamp (4 bytes): 时间戳
- payload_size (4 bytes): payload 大小
```

**处理逻辑**:

1. **解析图像数据**
   - 调用 `face_service.parse_image(message)` 解析二进制数据
   - 提取 JPEG 图像数据（跳过 16 字节头部）
   - 解析失败返回 `no_face` 错误响应

2. **执行人脸识别**

   ```python
   result = face_service.recognize(jpeg_data)
   ```

   - 调用人脸识别服务
   - 返回识别结果对象:
     - `result.result`: "known" | "unknown" | "no_face" | "error"
     - `result.person`: 人员对象（如果识别成功）
     - `result.confidence`: 置信度

3. **检查权限**

   ```python
   access_granted, deny_reason = face_service.check_permission(result.person.id)
   ```

   - 验证用户是否有开门权限
   - 检查时间限制、黑名单、访客过期等
   - 返回授权结果和拒绝原因

4. **生成问候语**

   ```python
   greeting = face_service.generate_greeting(result, access_granted, deny_reason)
   ```

   - 根据识别结果和权限生成个性化问候语
   - 示例: "欢迎回家，张三！" / "抱歉，您没有开门权限"

5. **保存到访记录**

   ```python
   visit_id = face_service.save_visit_record(result, access_granted, deny_reason, jpeg_data)
   ```

   - 保存到访记录到数据库
   - 包含人员 ID、识别结果、授权状态、时间戳
   - 返回记录 ID

6. **构建响应消息**

   ```python
   response = {
       "type": "face_result",
       "result": result.result,
       "user_id": result.person.id if result.person else None,
       "access": {
           "granted": access_granted,
           "reason": "authorized_user" | "unauthorized_user" | "time_restricted" | ...
       }
   }
   ```

7. **缓存识别结果**

   ```python
   conn.last_face_result = {
       "ts": int(time.time() * 1000),
       "result": result.result,
       "user_id": result.person.id,
       "person_name": result.person.name,
       "access_granted": access_granted
   }
   ```

   - 缓存到连接对象，供 `logReportHandler` 填充 uid 使用
   - 有效期 30 秒

8. **发送 JSON 响应**

   ```python
   await conn.websocket.send(json.dumps(response))
   ```

9. **播放 TTS 问候语（标准三段式流程）**
   - 如果有问候语，调用 TTS 模块合成语音
   - 生成 `sentence_id`
   - 放入 TTS 队列（标准三段式）:
     - `FIRST(ACTION)` - 开始标记，不包含文本
     - `MIDDLE(TEXT, content_detail=greeting)` - 实际问候语文本
     - `LAST(ACTION)` - 结束标记
   - 发送给 ESP32 播放

   > **注意**: 此流程与正常 TTS 流程（chat 方法）保持一致，确保 TTS 处理器能正确识别和处理消息

10. **推送通知给 App**

    ```python
    notification = {
        "type": "visit_notification",
        "ts": int(time.time() * 1000),
        "data": {
            "visit_id": visit_id,
            "person_id": result.person.id,
            "person_name": result.person.name,
            "relation": result.person.relation_type,
            "result": result.result,
            "access_granted": access_granted,
            "image": base64.b64encode(jpeg_data).decode(),
            "image_path": None
        }
    }
    ```

    - 通过 `ConnectionManager` 获取所有关联的 App 连接
    - 遍历 App 连接，发送通知（含 base64 编码的图片）
    - 失败记录错误日志

**流程图**:

```
ESP32 发送 BinaryProtocol2 (type=2, JPEG 图像)
    ↓
解析图像数据 (parse_image)
    ↓
执行人脸识别 (recognize)
    ↓
检查权限 (check_permission)
    ├─ 时间限制检查
    ├─ 黑名单检查
    └─ 访客过期检查
    ↓
生成问候语 (generate_greeting)
    ↓
保存到访记录 (save_visit_record)
    ↓
构建响应消息 (face_result)
    ↓
缓存识别结果 (last_face_result, 30秒有效期)
    ↓
发送 JSON 响应给 ESP32
    ↓
播放 TTS 问候语 (如果有)
    ├─ 生成 sentence_id
    ├─ 放入 TTS 队列（三段式）
    │   ├─ FIRST(ACTION)
    │   ├─ MIDDLE(TEXT, greeting)
    │   └─ LAST(ACTION)
    └─ 发送给 ESP32
    ↓
推送通知给 App (含图片)
    ├─ 获取关联的 App 连接
    ├─ 构建通知消息 (visit_notification)
    └─ 遍历发送给所有 App
    ↓
完成
```

---

### 2.2 JSON 格式人脸识别 (兼容)

**文件**: `core/handle/textHandler/faceRecognitionHandler.py`

**消息格式**:

```json
{
  "type": "face_recognition",
  "action": "recognize",
  "image": "base64_encoded_jpeg_data"
}
```

**处理逻辑**:

1. **解析图像数据**
   - 提取 `image` 字段（base64 编码）
   - 解码为 JPEG 二进制数据

   ```python
   jpeg_data = base64.b64decode(image_data)
   ```

   - 解析失败返回 `no_face` 错误响应

2. **执行人脸识别**
   - 调用 `face_service.recognize(jpeg_data)`
   - 后续流程与二进制格式相同（步骤 2-10）

**注意**: ESP32 现在推荐使用二进制格式（BinaryProtocol2），JSON 格式仅保留兼容性。

---

### 2.3 人脸管理 (App 端)

**文件**: `core/handle/textHandler/faceRecognitionHandler.py` - `FaceManagementHandler`

**支持的操作**:

#### 2.3.1 人脸录入 (register)

**消息格式**:

```json
{
  "type": "face_management",
  "action": "register",
  "data": {
    "name": "张三",
    "relation_type": "family",
    "images": ["base64_jpeg_1", "base64_jpeg_2", "base64_jpeg_3"],
    "permission": {
      "time_range": { "start": "00:00", "end": "23:59" },
      "valid_days": [1, 2, 3, 4, 5, 6, 7],
      "expire_date": null
    }
  }
}
```

**处理逻辑**:

1. 解析人员信息（姓名、关系类型、权限）
2. 解码图像数据（base64 → JPEG）
3. 调用 `face_service.register_face()` 录入人脸
4. 返回成功响应（含 person_id）或错误响应

#### 2.3.2 获取人员列表 (get_persons)

**处理逻辑**:

1. 调用 `face_service.get_persons()` 获取所有人员
2. 返回人员列表（含 ID、姓名、关系、权限）

#### 2.3.3 获取人员详情 (get_person)

**处理逻辑**:

1. 提取 `person_id`
2. 调用 `face_service.get_person(person_id)` 获取详情
3. 返回人员详情或 `person_not_found` 错误

#### 2.3.4 删除人员 (delete_person)

**处理逻辑**:

1. 提取 `person_id`
2. 调用 `face_service.delete_person(person_id)` 删除人员
3. 返回成功或失败响应

#### 2.3.5 更新权限 (update_permission)

**处理逻辑**:

1. 提取 `person_id` 和 `permission`
2. 调用 `face_service.update_permission()` 更新权限
3. 返回成功或失败响应

#### 2.3.6 获取到访记录 (get_visits)

**处理逻辑**:

1. 提取分页参数（page, page_size）和时间范围（date_from, date_to）
2. 调用 `face_service.get_visits()` 查询记录
3. 返回到访记录列表（含分页信息）

---

## 3. 监控模式处理

### 3.1 启动监控模式 (start_monitor)

**文件**: `core/handle/textHandler/systemMessageHandler.py`

**消息格式**:

```json
{
  "type": "system",
  "command": "start_monitor",
  "record": false // 是否启用录像（可选，默认 false）
}
```

**处理逻辑**:

1. **判断连接类型**
   - 检查 `conn.client_type` 是否为 "app"
   - 区分 App 发起的命令和 ESP32 自己发起的命令

2. **App 发起的命令**
   - 通过 `ConnectionManager` 获取 ESP32 连接

   ```python
   esp32_conn = manager.get_esp32_conn(conn.device_id)
   ```

   - 切换 ESP32 的工作模式

   ```python
   esp32_conn.current_mode = "monitor"
   ```

   - 启动录像（如果 `record=true`）

   ```python
   if enable_recording:
       self._start_recording(esp32_conn)
   ```

   - 停止 ESP32 的 TTS 音频发送

   ```python
   # 清空 TTS 队列
   while not esp32_conn.tts.tts_audio_queue.empty():
       esp32_conn.tts.tts_audio_queue.get_nowait()
   ```

   - 通知 ESP32 进入监控模式

   ```python
   await esp32_conn.websocket.send(json.dumps({
       "type": "system",
       "command": "start_monitor"
   }))
   ```

3. **ESP32 自己发起的命令**
   - 切换自己的工作模式

   ```python
   conn.current_mode = "monitor"
   ```

   - 启动录像（如果 `record=true`）
   - 停止 TTS 音频发送

4. **启动录像（可选）**

   ```python
   def _start_recording(self, conn):
       if hasattr(conn, "video_recorder") and conn.video_recorder:
           conn.video_recorder.start_recording(conn.device_id)
   ```

   - 检查是否有 `video_recorder` 实例
   - 调用 `start_recording()` 启动录像
   - 失败记录警告日志

5. **返回成功响应**
   ```python
   await conn.websocket.send(json.dumps({
       "type": "system",
       "status": "success",
       "command": "start_monitor",
       "recording": enable_recording
   }))
   ```

**流程图**:

```
App/ESP32 发送 start_monitor
    ↓
判断连接类型 (conn.client_type)
    ↓
    ├─────────────────┬─────────────────┐
    ↓                 ↓                 ↓
App 发起          ESP32 自己发起
    ↓                 ↓
获取 ESP32 连接    切换自己模式 (monitor)
    ↓                 ↓
切换 ESP32 模式    启动录像 (如果启用)
    ↓                 ↓
启动录像          停止 TTS 音频发送
    ↓                 ↓
停止 TTS 发送      返回成功响应
    ↓                 ↓
通知 ESP32        完成
    ↓
返回成功响应
    ↓
完成

注意：
- App 发起：需要通知 ESP32 进入监控模式
- ESP32 自己发起：不需要通知（已经在监控模式）
```

---

### 3.2 停止监控模式 (stop_monitor)

**消息格式**:

```json
{
  "type": "system",
  "command": "stop_monitor"
}
```

**处理逻辑**:

1. **判断连接类型**
   - 检查 `conn.client_type` 是否为 "app"

2. **App 发起的命令**
   - 通过 `ConnectionManager` 获取 ESP32 连接
   - 切换 ESP32 的工作模式

   ```python
   esp32_conn.current_mode = "normal"
   ```

   - 停止录像（如果正在录制）

   ```python
   self._stop_recording(esp32_conn)
   ```

   - 通知 ESP32 退出监控模式

   ```python
   await esp32_conn.websocket.send(json.dumps({
       "type": "system",
       "command": "stop_monitor"
   }))
   ```

3. **ESP32 自己发起的命令**
   - 切换自己的工作模式

   ```python
   conn.current_mode = "normal"
   ```

   - 停止录像（如果正在录制）

4. **停止录像**

   ```python
   def _stop_recording(self, conn):
       if hasattr(conn, "video_recorder") and conn.video_recorder:
           if conn.video_recorder.is_recording(conn.device_id):
               conn.video_recorder.stop_recording(conn.device_id)
   ```

   - 检查是否正在录制
   - 调用 `stop_recording()` 停止录像
   - 失败记录警告日志

5. **返回成功响应**
   ```python
   await conn.websocket.send(json.dumps({
       "type": "system",
       "status": "success",
       "command": "stop_monitor"
   }))
   ```

**流程图**:

```
App/ESP32 发送 stop_monitor
    ↓
判断连接类型 (conn.client_type)
    ↓
    ├─────────────────┬─────────────────┐
    ↓                 ↓                 ↓
App 发起          ESP32 自己发起
    ↓                 ↓
获取 ESP32 连接    切换自己模式 (normal)
    ↓                 ↓
切换 ESP32 模式    停止录像 (如果正在录制)
    ↓                 ↓
停止录像          返回成功响应
    ↓                 ↓
通知 ESP32        完成
    ↓
返回成功响应
    ↓
完成

注意：
- App 发起：需要通知 ESP32 退出监控模式
- ESP32 自己发起：不需要通知（已经退出监控模式）
```

---

### 3.3 监控数据处理

**文件**: `core/connection.py` - `_handle_monitor_data` 方法

**处理逻辑**:

1. **转发给 App**

   ```python
   await self._forward_to_apps(message)
   ```

   - 调用 `_forward_to_apps()` 方法
   - 解析 BinaryProtocol2 头部
   - 区分音频帧和视频帧
   - 转发给所有关联的 App

2. **添加到录像器（可选）**

   ```python
   if hasattr(self, "video_recorder") and self.video_recorder:
       if self.video_recorder.is_recording(self.device_id):
           # 添加帧到录像器
   ```

   - 检查是否启用录像
   - 检查是否正在录制
   - 解析帧类型（音频/视频）
   - 添加到录像器

**音频帧处理**:

1. 解析 BinaryProtocol2 头部（reserved=0 表示音频）
2. 提取 Opus payload
3. 解码为 PCM (16kHz, 单声道, 960 采样点)
   ```python
   pcm_data = self._opus_decoder_for_record.decode(payload, 960)
   ```
4. 添加到录像器
   ```python
   self.video_recorder.add_audio_frame(
       device_id=self.device_id,
       pcm_data=pcm_data,
       timestamp=timestamp
   )
   ```

**视频帧处理**:

1. 解析 BinaryProtocol2 头部（reserved≠0 表示视频）
2. 提取分辨率（width, height）
   ```python
   width = (reserved >> 16) & 0xFFFF
   height = reserved & 0xFFFF
   ```
3. 提取 JPEG payload
4. 添加到录像器
   ```python
   self.video_recorder.add_video_frame(
       device_id=self.device_id,
       jpeg_data=payload,
       timestamp=timestamp,
       width=width,
       height=height
   )
   ```

**流程图**:

```
ESP32 发送监控数据 (BinaryProtocol2)
    ↓
转发给 App (_forward_to_apps)
    ├─ 解析头部 (version, type, reserved, timestamp, payload_size)
    ├─ 区分音频/视频帧 (reserved=0 音频, ≠0 视频)
    ├─ 音频帧: Opus → PCM → 转发
    └─ 视频帧: JPEG → 直接转发
    ↓
检查是否启用录像
    ↓
是 → 添加到录像器
    ├─ 音频帧: Opus → PCM → add_audio_frame
    └─ 视频帧: JPEG → add_video_frame
    ↓
否 → 跳过
    ↓
完成
```

---

### 3.4 数据转发逻辑

**文件**: `core/connection.py` - `_forward_to_apps` 方法

**处理逻辑**:

1. **获取关联的 App 连接**

   ```python
   manager = ConnectionManager.get_instance()
   app_conns = manager.get_app_conns(self.device_id)
   ```

   - 无 App 连接直接返回

2. **解析 BinaryProtocol2 头部**

   ```python
   version = int.from_bytes(data[0:2], 'big')
   msg_type = int.from_bytes(data[2:4], 'big')
   reserved = int.from_bytes(data[4:8], 'big')
   timestamp = int.from_bytes(data[8:12], 'big')
   payload_size = int.from_bytes(data[12:16], 'big')
   ```

3. **区分音频和视频帧**

   ```python
   is_audio = (reserved == 0)
   is_video = (reserved != 0)
   ```

4. **处理视频帧**
   - 直接转发完整的 BinaryProtocol2 帧

   ```python
   for app_conn in app_conns:
       if app_conn.websocket:
           await app_conn.websocket.send(data)
   ```

   - 保持协议格式不变
   - 调试日志（只打印前 2 帧）

5. **处理音频帧**
   - 提取 Opus payload

   ```python
   opus_payload = data[16:16 + payload_size]
   ```

   - 初始化 Opus 解码器（延迟初始化）

   ```python
   if not hasattr(self, "_opus_decoder_for_app"):
       self._opus_decoder_for_app = opuslib_next.Decoder(16000, 1)
       self._opus_decode_error_count = 0  # 错误计数器
       self._opus_decode_last_error_time = 0  # 上次错误时间
   ```

   > **错误处理机制**：
   >
   > - 初始化解码器时同时初始化错误计数器和错误时间戳
   > - 用于限制错误日志频率，避免日志洪水
   > - 累计错误超过阈值时自动重置解码器
   - 解码为 PCM (16kHz, 单声道, 960 采样点)

   ```python
   pcm_data = self._opus_decoder_for_app.decode(opus_payload, 960)
   ```

   - 广播给所有 App

   ```python
   for app_conn in app_conns:
       if app_conn.websocket:
           await app_conn.websocket.send(pcm_data)
   ```

6. **错误处理机制**

   **Opus 解码错误处理**：
   - 解码失败时限制日志频率（每 5 秒或每 100 次错误打印一次）
   - 累计错误 > 10 次时自动重置解码器
   - 失败不中断流程，继续处理后续帧

   ```python
   try:
       pcm_data = self._opus_decoder_for_app.decode(opus_payload, 960)
   except opuslib_next.OpusError as e:
       self._opus_decode_error_count += 1
       current_time = time.time()

       # 限制日志频率
       if (current_time - self._opus_decode_last_error_time > 5.0 or
           self._opus_decode_error_count % 100 == 0):
           self.logger.bind(tag=TAG).warning(
               f"Opus 解码失败: {e}, 累计错误: {self._opus_decode_error_count}"
           )
           self._opus_decode_last_error_time = current_time

       # 累计错误过多时重置解码器
       if self._opus_decode_error_count > 10:
           self.logger.bind(tag=TAG).warning("重置 Opus 解码器")
           self._opus_decoder_for_app = opuslib_next.Decoder(16000, 1)
           self._opus_decode_error_count = 0

       return  # 跳过此帧
   ```

   **WebSocket 发送错误处理**：
   - 发送失败记录警告日志
   - 不中断其他 App 的转发流程

**流程图**:

```
接收监控数据 (BinaryProtocol2)
    ↓
获取关联的 App 连接
    ↓
无 App → 返回
    ↓
有 App → 解析头部
    ↓
区分音频/视频帧
    ↓
视频帧 (reserved ≠ 0)
    ├─ 提取分辨率 (width, height)
    ├─ 直接转发完整帧
    └─ 遍历发送给所有 App
    ↓
音频帧 (reserved = 0)
    ├─ 提取 Opus payload
    ├─ 初始化解码器 (延迟初始化)
    ├─ 解码为 PCM (16kHz, 960 采样点)
    ├─ 错误处理 (限制日志频率, 重置解码器)
    └─ 遍历发送给所有 App
    ↓
完成
```

---

## 4. 响应返回机制

### 4.1 TTS 音频返回

**文件**: `core/handle/sendAudioHandle.py`

#### 4.1.1 TTS 流程概览

**处理逻辑**:

1. **LLM 生成文本**
   - LLM 流式生成回复文本
   - 逐句放入 TTS 文本队列

   ```python
   conn.tts.tts_text_queue.put(TTSMessageDTO(
       sentence_id=sentence_id,
       sentence_type=SentenceType.MIDDLE,
       content_type=ContentType.TEXT,
       content_detail="你好，我是小智"
   ))
   ```

2. **TTS 合成音频**
   - TTS 线程从文本队列取出文本
   - 调用 TTS 服务合成 Opus 音频

   ```python
   opus_packets = await tts_provider.synthesize(text)
   ```

   - 放入音频队列

   ```python
   conn.tts.tts_audio_queue.put((SentenceType.MIDDLE, opus_packets, text))
   ```

3. **发送音频给 ESP32**
   - 音频发送线程从音频队列取出数据
   - 调用 `sendAudioMessage()` 发送
   - 根据句子类型发送不同的控制消息

**句子类型**:

- `FIRST`: 第一句（发送 "start" 和 "sentence_start"）
- `MIDDLE`: 中间句（只发送音频）
- `LAST`: 最后一句（发送 "stop"）

---

#### 4.1.2 发送 TTS 状态消息

**文件**: `core/handle/sendAudioHandle.py` - `send_tts_message` 方法

**处理逻辑**:

1. **构建状态消息**

   ```python
   message = {
       "type": "tts",
       "state": state,  # "start" | "sentence_start" | "stop"
       "session_id": conn.session_id
   }
   if text is not None:
       message["text"] = textUtils.check_emoji(text)
   ```

2. **发送 "start" 消息**
   - 表示 TTS 开始播放
   - 不包含文本内容

3. **发送 "sentence_start" 消息**
   - 表示新句子开始
   - 包含句子文本（用于字幕显示）
   - 文本经过 emoji 检查

4. **发送 "stop" 消息**
   - 表示 TTS 播放结束
   - 播放提示音（可选）

   ```python
   if tts_notify:
       audios = audio_to_data("config/assets/tts_notify.mp3")
       await sendAudio(conn, audios)
   ```

   - 清除服务端讲话状态

   ```python
   conn.clearSpeakStatus()
   ```

5. **发送消息到 ESP32**
   ```python
   await conn.websocket.send(json.dumps(message))
   ```

**流程图**:

```
LLM 生成文本
    ↓
放入 TTS 文本队列 (tts_text_queue)
    ↓
TTS 线程取出文本
    ↓
调用 TTS 服务合成 Opus 音频
    ↓
放入音频队列 (tts_audio_queue)
    ↓
音频发送线程取出数据
    ↓
发送 TTS 状态消息
    ├─ FIRST → "start" + "sentence_start"
    ├─ MIDDLE → 无状态消息
    └─ LAST → "stop" + 提示音（可选）
    ↓
发送音频数据 (sendAudio)
    ↓
完成
```

---

#### 4.1.3 发送音频数据

**文件**: `core/handle/sendAudioHandle.py` - `sendAudio` 方法

**处理逻辑**:

1. **初始化流控状态**

   ```python
   if not hasattr(conn, "audio_flow_control") or \
      conn.audio_flow_control.get("sentence_id") != conn.sentence_id:
       conn.audio_flow_control = {
           "last_send_time": 0,
           "packet_count": 0,
           "start_time": time.perf_counter(),
           "sequence": 0,
           "sentence_id": conn.sentence_id
       }
   ```

   - 每个句子独立的流控状态
   - 记录开始时间、包计数、序列号

2. **预缓冲机制**
   - 前 5 个包直接发送，不做延迟

   ```python
   pre_buffer_count = 5
   if flow_control["packet_count"] < pre_buffer_count:
       # 直接发送
   ```

   - 减少首包延迟，提升响应速度

3. **流控延迟计算**
   - **固定延迟模式** (send_delay > 0):
     ```python
     await asyncio.sleep(send_delay)
     ```
   - **动态延迟模式** (send_delay ≤ 0):
     ```python
     effective_packet = flow_control["packet_count"] - pre_buffer_count
     expected_time = flow_control["start_time"] + (effective_packet * frame_duration / 1000)
     delay = expected_time - current_time
     if delay > 0:
         await asyncio.sleep(delay)
     else:
         # 纠正误差
         flow_control["start_time"] += abs(delay)
     ```
   - 根据播放位置计算预期发送时间
   - 动态调整延迟，保持音频流畅

4. **MQTT 网关特殊处理**
   - 检查是否来自 MQTT 网关

   ```python
   if conn.conn_from_mqtt_gateway:
       # 添加 16 字节头部
       await _send_to_mqtt_gateway(conn, audios, timestamp, sequence)
   else:
       # 直接发送 Opus 数据包
       await conn.websocket.send(audios)
   ```

5. **添加 16 字节头部（MQTT）**

   ```python
   header = bytearray(16)
   header[0] = 1  # type
   header[2:4] = len(opus_packet).to_bytes(2, "big")  # payload length
   header[4:8] = sequence.to_bytes(4, "big")  # sequence
   header[8:12] = timestamp.to_bytes(4, "big")  # timestamp
   header[12:16] = len(opus_packet).to_bytes(4, "big")  # opus length

   complete_packet = bytes(header) + opus_packet
   await conn.websocket.send(complete_packet)
   ```

6. **更新流控状态**

   ```python
   flow_control["packet_count"] += 1
   flow_control["sequence"] += 1
   flow_control["last_send_time"] = time.perf_counter()
   ```

7. **更新活动时间戳**

   ```python
   conn.last_activity_time = time.time() * 1000
   ```

8. **设置讲话状态**
   ```python
   conn.client_is_speaking = True
   ```

**流程图**:

```
取出音频数据 (Opus packets)
    ↓
初始化流控状态 (首次或新句子)
    ↓
预缓冲 (前 5 个包)
    ├─ 直接发送，不延迟
    └─ 更新流控状态
    ↓
剩余包流控发送
    ├─ 固定延迟模式 → sleep(send_delay)
    └─ 动态延迟模式 → 计算预期时间 → 动态调整
    ↓
检查是否来自 MQTT 网关
    ├─ 是 → 添加 16 字节头部 → 发送
    └─ 否 → 直接发送 Opus 数据包
    ↓
更新流控状态 (packet_count, sequence, last_send_time)
    ↓
更新活动时间戳
    ↓
设置讲话状态 (client_is_speaking = True)
    ↓
完成
```

---

### 4.2 JSON 响应返回

#### 4.2.1 通用响应格式

**基本结构**:

```json
{
  "type": "response_type",
  "seq_id": 123,  // 如果是响应，携带请求的 seq_id
  "status": "success" | "error",
  "data": {...}
}
```

**响应类型**:

- 命令响应: 携带 `seq_id`，对应请求的序列号
- 主动上报: 不携带 `seq_id`，服务器主动推送

---

#### 4.2.2 锁控命令响应

**请求格式** (App → 服务器 → ESP32):

```json
{
  "type": "lock_control",
  "seq_id": 456,
  "action": "unlock", // "unlock" | "lock"
  "forward": true
}
```

**响应格式** (ESP32 → 服务器 → App):

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

**处理逻辑**:

1. **App 发送命令**
   - 携带 `forward: true` 标记
   - 服务器识别并转发给 ESP32

2. **ESP32 执行命令**
   - 执行开锁/上锁操作
   - 返回执行结果

3. **服务器转发响应**
   - 保持 `seq_id` 不变
   - 转发给发起命令的 App

---

#### 4.2.3 人脸识别响应

**响应格式** (服务器 → ESP32):

```json
{
  "type": "face_result",
  "result": "known",
  "user_id": 5,
  "access": {
    "granted": true,
    "reason": "authorized_user"
  }
}
```

**注意**: `face_result` 是主动上报，不携带 `seq_id`

**access.reason 取值及赋值优先级**:

字段赋值优先级逻辑：

1. 如果 `access_granted=True`，返回 `"authorized_user"`
2. 如果 `access_granted=False` 且 `deny_reason` 不为空，根据映射表返回对应原因
3. 如果 `result.result="unknown"`，返回 `"unauthorized_user"`
4. 其他情况返回 `"unauthorized_user"`

可能的取值：

- `authorized_user`: 授权用户（access_granted=True）
- `unauthorized_user`: 未授权用户（陌生人或无权限）
- `time_restricted`: 时间限制（deny_reason="time_restricted" 或 "not_in_time_range"）
- `blacklisted`: 黑名单（deny_reason="blacklisted"）
- `guest_expired`: 访客过期（deny_reason="expired"）

---

#### 4.2.4 状态上报响应

**ESP32 上报** (ESP32 → 服务器):

```json
{
  "type": "status_report",
  "ts": 1702234567890,
  "data": {...}
}
```

**服务器处理**:

- 不返回响应给 ESP32
- 直接转发给所有关联的 App

**App 接收** (服务器 → App):

```json
{
  "type": "status_report",
  "ts": 1702234567890,
  "data": {...}
}
```

---

### 4.3 上报机制

> **重要说明**：上报机制是原项目的语音对话功能，用于将 TTS/ASR 聊天记录上报到管理后台。
>
> - **功能定位**：聊天记录上报（用于聊天历史记录、用户行为分析、语音数据收集）
> - **实现位置**：已从 `reportHandle.py` 迁移到 `core/connection.py` 的 `ConnectionHandler` 类中
> - **与门锁的关系**：无关，智能门锁的状态、事件、日志数据通过独立的数据库存储机制保存
> - `reportHandle.py` 只保留了辅助函数（`report`、`opus_to_wav`、`enqueue_tts_report`、`enqueue_asr_report`）

**文件**:

- `core/handle/reportHandle.py` - 辅助函数
- `core/connection.py` - 实际实现（上报线程和队列）

#### 4.3.1 上报流程

**处理逻辑**:

1. **加入上报队列**

   ```python
   conn.report_queue.put((type, text, opus_data, report_time))
   ```

   - `type`: 1=用户（ASR），2=智能体（TTS）
   - `text`: 文本内容
   - `opus_data`: Opus 音频数据（可选）
   - `report_time`: 上报时间戳

2. **上报线程处理**

   > **注意**：上报线程的实际实现位于 `core/connection.py` 的 `ConnectionHandler` 类中，
   > 每个连接对象拥有自己的上报队列和处理线程，线程的生命周期与连接对象绑定。

   ```python
   def _report_worker(self):
       while not self.stop_event.is_set():
           item = self.report_queue.get(timeout=1)
           if item is None:  # 毒丸对象
               break
           self.executor.submit(self._process_report, *item)
   ```

   - 从队列取出上报任务
   - 提交到线程池执行
   - 避免阻塞主线程

3. **执行上报**

   ```python
   def _process_report(self, type, text, audio_data, report_time):
       # 转换 Opus → WAV
       wav_data = opus_to_wav(conn, opus_data)

       # 调用管理 API
       manage_report(
           mac_address=conn.device_id,
           session_id=conn.session_id,
           chat_type=type,
           content=text,
           audio=wav_data,
           report_time=report_time
       )
   ```

4. **Opus 转 WAV**

   ```python
   def opus_to_wav(conn, opus_data):
       decoder = opuslib_next.Decoder(16000, 1)  # 16kHz, 单声道
       pcm_data = []

       for opus_packet in opus_data:
           pcm_frame = decoder.decode(opus_packet, 960)
           pcm_data.append(pcm_frame)

       # 创建 WAV 文件头
       pcm_data_bytes = b"".join(pcm_data)
       wav_header = bytearray()
       # ... 构建 WAV 头部

       return bytes(wav_header) + pcm_data_bytes
   ```

5. **调用管理 API**
   - 发送 HTTP POST 请求到管理后台
   - 包含设备 ID、会话 ID、聊天类型、文本、音频
   - 失败记录错误日志

**流程图**:

```
ASR/TTS 生成数据
    ↓
加入上报队列 (report_queue)
    ├─ type: 1=用户, 2=智能体
    ├─ text: 文本内容
    ├─ opus_data: 音频数据（可选）
    └─ report_time: 时间戳
    ↓
上报线程取出任务
    ↓
提交到线程池执行
    ↓
转换 Opus → WAV
    ├─ 初始化解码器 (16kHz, 单声道)
    ├─ 逐包解码 (960 采样点)
    ├─ 拼接 PCM 数据
    └─ 添加 WAV 文件头
    ↓
调用管理 API (HTTP POST)
    ├─ mac_address: 设备 ID
    ├─ session_id: 会话 ID
    ├─ chat_type: 聊天类型
    ├─ content: 文本内容
    ├─ audio: WAV 音频数据
    └─ report_time: 时间戳
    ↓
完成
```

---

#### 4.3.2 ASR 上报

**触发时机**: ASR 识别完成后

**调用方式**:

```python
from core.handle.reportHandle import enqueue_asr_report

enqueue_asr_report(conn, text, opus_data)
```

**处理逻辑**:

1. 检查是否启用上报 (`report_asr_enable`)
2. 检查聊天历史配置 (`chat_history_conf`)
   - 0: 不上报
   - 1: 只上报文本
   - 2: 上报文本和音频
3. 加入上报队列

---

#### 4.3.3 TTS 上报

**触发时机**: TTS 合成完成后

**调用方式**:

```python
from core.handle.reportHandle import enqueue_tts_report

enqueue_tts_report(conn, text, opus_data)
```

**处理逻辑**:

1. 检查是否启用上报 (`report_tts_enable`)
2. 检查聊天历史配置 (`chat_history_conf`)
   - 0: 不上报
   - 1: 只上报文本
   - 2: 上报文本和音频
3. 加入上报队列

---

### 4.4 STT 消息返回

**文件**: `core/handle/sendAudioHandle.py` - `send_stt_message` 方法

**消息格式**:

```json
{
  "type": "stt",
  "text": "你好",
  "session_id": "abc123"
}
```

**处理逻辑**:

1. **解析 JSON 格式（如有）**

   ```python
   if text.strip().startswith("{") and text.strip().endswith("}"):
       parsed_data = json.loads(text)
       if "content" in parsed_data:
           display_text = parsed_data["content"]
           if "speaker" in parsed_data:
               conn.current_speaker = parsed_data["speaker"]
   ```

   - 支持包含说话人信息的 JSON 格式
   - 提取实际文本内容

2. **清理文本**

   ```python
   stt_text = textUtils.get_string_no_punctuation_or_emoji(display_text)
   ```

   - 移除标点符号和 emoji
   - 用于显示在 ESP32 屏幕上

3. **发送 STT 消息**

   ```python
   await conn.websocket.send(json.dumps({
       "type": "stt",
       "text": stt_text,
       "session_id": conn.session_id
   }))
   ```

4. **发送 TTS 开始消息**

   ```python
   await send_tts_message(conn, "start")
   ```

   - 通知 ESP32 准备接收 TTS 音频

**流程图**:

```
ASR 识别完成
    ↓
解析 JSON 格式（如有）
    ├─ 提取 content 字段
    └─ 保存 speaker 信息
    ↓
清理文本 (移除标点和 emoji)
    ↓
发送 STT 消息给 ESP32
    ↓
发送 TTS 开始消息
    ↓
完成
```

---

## 5. 总结

### 5.1 智能门锁协议处理

**核心流程**:

1. 解析消息字段
2. 持久化到数据库
3. 更新内存状态
4. 推送给关联的 App

**关键点**:

- 支持 v5.0 和 v5.2 协议兼容
- 自动填充用户 ID（人脸、远程开锁）
- 连续失败次数监控
- 事件特定处理逻辑

---

### 5.2 人脸识别处理

**核心流程**:

1. 解析图像数据（二进制/JSON）
2. 执行人脸识别
3. 检查权限
4. 生成问候语
5. 保存到访记录
6. 返回识别结果
7. 播放 TTS 问候语
8. 推送通知给 App

**关键点**:

- 支持二进制和 JSON 两种格式
- 权限验证（时间限制、黑名单、访客过期）
- 识别结果缓存（30 秒有效期）
- 图片 base64 编码推送给 App

---

### 5.3 监控模式处理

**核心流程**:

1. 判断连接类型（App/ESP32）
2. 切换工作模式（normal/monitor）
3. 启动/停止录像（可选）
4. 停止 TTS 音频发送
5. 通知 ESP32 模式切换
6. 转发音视频数据给 App

**关键点**:

- 音频帧: Opus → PCM → 转发
- 视频帧: JPEG → 直接转发
- 录像功能可选
- 错误处理和日志限流

---

### 5.4 响应返回机制

**核心流程**:

1. TTS 音频返回: 流控 + 预缓冲 + MQTT 头部
2. JSON 响应返回: 命令响应 + 主动上报
3. 上报机制: 队列 + 线程池 + Opus→WAV
4. STT 消息返回: 文本清理 + TTS 开始通知

**关键点**:

- 流控机制保证音频流畅
- 预缓冲减少首包延迟
- 上报异步处理不阻塞
- 支持 MQTT 网关特殊格式

---

**文档版本**: v1.0  
**最后更新**: 2026-01-30  
**作者**: Kiro AI Assistant
