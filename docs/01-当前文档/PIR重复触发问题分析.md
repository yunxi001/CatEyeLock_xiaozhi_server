# PIR重复触发问题分析

## 问题描述

**设备端行为：** ESP32在PIR传感器检测到人体时，**每秒上报一次**持续时间，直到人体离开。

**当前服务器端处理：** 每次收到 `pir_trigger` 事件都会触发完整的访客处理流程。

## 问题影响

### 1. 重复触发访客处理流程

当PIR检测到人体持续5秒时，服务器会收到5次 `event_report` 消息：

```
第1秒: {"type": "event_report", "event": "pir_trigger", "param": 1}
第2秒: {"type": "event_report", "event": "pir_trigger", "param": 2}
第3秒: {"type": "event_report", "event": "pir_trigger", "param": 3}
第4秒: {"type": "event_report", "event": "pir_trigger", "param": 4}
第5秒: {"type": "event_report", "event": "pir_trigger", "param": 5}
```

**当前代码行为：** 每次都会调用 `_trigger_face_recognition()` → `handle_visitor()`

### 2. 导致的具体问题

#### 问题1：重复拍照

```python
# 在 handle_visitor() 中
jpeg_data = await self._capture_visitor_photo(device_id, conn)
```

- 同一个访客会被拍照5次
- 浪费带宽和存储资源
- 可能导致MCP接口压力过大

#### 问题2：重复人脸识别

```python
# 在 handle_visitor() 中
recognition_result = await self.face_handler.recognize_with_retry(
    device_id=device_id,
    jpeg_data=jpeg_data,
    conn=conn
)
```

- 同一个访客会被识别5次（每次最多重试3次）
- 最坏情况：5 × 3 = 15次识别调用
- 严重浪费AI推理资源

#### 问题3：重复下发face_result消息

```python
# 在 handle_visitor() 中
await self._send_face_result(
    conn=conn,
    result="known",
    user_id=person.id,
    access_granted=True,
    reason="authorized_user"
)
```

- ESP32会收到5次开锁指令
- 可能导致重复开锁或状态混乱

#### 问题4：重复播放欢迎词

```python
# 在 handle_visitor() 中（有权限用户）
await self.greeting_handler.play_welcome_greeting(
    device_id=device_id,
    person_id=person.id,
    person_name=person.name,
    conn=conn
)
```

- 同一个访客会听到5次欢迎词
- 用户体验极差

#### 问题5：重复启动意图识别对话

```python
# 在 handle_visitor() 中（无权限或陌生人）
intent_result = await self.start_intent_dialogue(
    device_id=device_id,
    session_id=session_id,
    person_info=person_info,
    visitor_image=jpeg_data,
    conn=conn
)
```

- 会创建5个不同的会话
- 每个会话都会启动独立的对话流程
- 导致对话混乱、资源浪费

#### 问题6：重复保存访问记录

```python
# 在 handle_visitor() 中
visit_id = await self._save_visit_record(...)
```

- 同一次访问会生成5条数据库记录
- 数据冗余，影响统计分析

#### 问题7：重复发送App通知

```python
# 在 handle_visitor() 中
await self.notification_service.notify_visitor_intent(...)
```

- App会收到5次相同的通知
- 用户体验极差

## 当前代码缺陷

### 缺陷1：没有会话状态检查

在 `EventReportHandler._trigger_face_recognition()` 中：

```python
async def _trigger_face_recognition(
    self,
    conn,
    ts: int,
    param: int,
    trigger_type: str
):
    # ❌ 没有检查是否已有活跃会话
    # ❌ 没有检查是否正在处理访客

    # 直接调用处理器
    result = await intent_handler.handle_visitor(
        device_id=conn.device_id,
        conn=conn,
        guard_active=is_guard_active
    )
```

### 缺陷2：没有设备级别的处理状态标志

在 `ConnectionHandler` 中：

```python
class ConnectionHandler:
    def __init__(self, ...):
        # ❌ 没有 visitor_processing 标志
        # ❌ 没有 active_session_id 记录
        # ❌ 没有 last_pir_trigger_time 记录
```

### 缺陷3：会话管理器无法判断设备是否有活跃会话

在 `SessionManager` 中：

```python
class SessionManager:
    # ❌ 没有 get_active_session_by_device() 方法
    # ❌ 没有 has_active_session() 方法
    # ❌ 无法根据 device_id 查询活跃会话
```

## 解决方案

### 方案1：添加设备级别的处理状态标志（推荐）

#### 1.1 在 ConnectionHandler 中添加状态标志

```python
class ConnectionHandler:
    def __init__(self, ...):
        # 访客处理状态
        self.visitor_processing = False  # 是否正在处理访客
        self.active_session_id = None    # 当前活跃的会话ID
        self.last_pir_trigger_time = 0   # 最后一次PIR触发时间（毫秒）
```

#### 1.2 在 EventReportHandler 中检查状态

```python
async def _handle_pir_event(self, conn, ts: int, param):
    """处理 PIR 人体检测事件"""
    duration = param  # 持续时间（秒）
    conn.logger.bind(tag=TAG).info(f"PIR 检测到人体，持续 {duration} 秒")

    # ✅ 检查是否正在处理访客
    if conn.visitor_processing:
        conn.logger.bind(tag=TAG).debug(
            f"访客处理中，忽略重复的PIR事件 - 设备: {conn.device_id}, "
            f"active_session: {conn.active_session_id}"
        )
        return

    # ✅ 记录PIR触发时间
    conn.last_pir_trigger_time = ts

    # 触发人脸识别流程
    await self._trigger_face_recognition(
        conn=conn,
        ts=ts,
        param=param,
        trigger_type="pir"
    )
```

#### 1.3 在 handle_visitor 中设置和清除标志

```python
async def handle_visitor(
    self,
    device_id: str,
    conn=None,
    guard_active: bool = False,
    session_id: Optional[str] = None,
    jpeg_data: Optional[bytes] = None
) -> Dict[str, Any]:
    """处理访客到访主流程"""

    # ✅ 设置处理标志
    if conn:
        conn.visitor_processing = True

    try:
        # 生成会话ID
        if not session_id:
            session = self.session_manager.create_session(device_id)
            session_id = session.session_id

        # ✅ 记录活跃会话
        if conn:
            conn.active_session_id = session_id

        # ... 原有处理逻辑 ...

        return result

    except Exception as e:
        logger.bind(tag=TAG).error(f"处理访客到访异常: {e}")
        return {"success": False, "error": str(e)}

    finally:
        # ✅ 清除处理标志
        if conn:
            conn.visitor_processing = False
            conn.active_session_id = None
```

## 修改方法达成的效果说明

### 核心效果：**忽略处理中的重复PIR上报**

当PIR每秒上报一次时，修改后的行为如下：

```
时间轴：访客站在门口5秒

第1秒 PIR上报 → ✅ 触发处理流程（visitor_processing = True）
                 ├─ 拍照
                 ├─ 人脸识别
                 ├─ 下发face_result
                 └─ 播放欢迎词/启动对话

第2秒 PIR上报 → ❌ 检测到 visitor_processing=True，直接忽略
第3秒 PIR上报 → ❌ 检测到 visitor_processing=True，直接忽略
第4秒 PIR上报 → ❌ 检测到 visitor_processing=True，直接忽略
第5秒 PIR上报 → ❌ 检测到 visitor_processing=True，直接忽略

处理完成后 → visitor_processing = False（清除标志）
```

### 详细说明

#### 1. 有权限用户（快速流程）

**场景：** 识别成功 + 有开门权限

```
PIR触发（第1秒）
  ↓
拍照 + 人脸识别（约2-3秒）
  ↓
下发face_result（开锁）
  ↓
播放欢迎词（约3-5秒）
  ↓
清除 visitor_processing 标志
  ↓
总耗时：约5-8秒
```

**期间的PIR上报：** 全部忽略（第2-8秒的上报都被过滤）

**效果：** 访客只听到1次欢迎词，只开锁1次

#### 2. 无权限用户/陌生人（长流程）

**场景：** 识别失败或无权限，启动意图识别对话

```
PIR触发（第1秒）
  ↓
拍照 + 人脸识别（约2-3秒）
  ↓
下发face_result（拒绝开锁）
  ↓
启动意图识别对话（持续30秒或更长）
  ├─ 播放问候："您好，请问您找谁？"
  ├─ 等待访客回复（ASR识别）
  ├─ VLLM分析意图
  ├─ TTS播放AI回复
  └─ 循环对话...
  ↓
对话结束（沉默30秒或PIR无人体）
  ↓
生成意图总结 + 保存记录 + 发送通知
  ↓
清除 visitor_processing 标志
  ↓
总耗时：30秒-5分钟
```

**期间的PIR上报：** 全部忽略（整个对话期间的所有上报都被过滤）

**效果：** 只创建1个对话会话，不会重复启动对话

#### 3. 看护模式（最长流程）

**场景：** 看护模式激活，同时进行对话和监控

```
PIR触发（第1秒）
  ↓
拍照 + 人脸识别
  ↓
启动统一模式对话
  ├─ 启动定时拍照任务（每5秒拍一次）
  ├─ 播放问候
  ├─ 对话循环
  └─ 持续监控快递状态
  ↓
对话结束
  ├─ 停止定时拍照
  ├─ 最终快递状态检查
  ├─ 生成意图总结
  └─ 保存记录 + 发送通知
  ↓
清除 visitor_processing 标志
  ↓
总耗时：可能长达5-10分钟
```

**期间的PIR上报：** 全部忽略（整个看护期间的所有上报都被过滤）

**效果：** 只启动1次看护任务，不会重复创建监控

### 关键点说明

#### ✅ 会被忽略的情况

1. **处理流程进行中**
   - `visitor_processing = True` 时
   - 所有后续PIR上报都被忽略
   - 直到当前访客处理完成

2. **对话进行中**
   - 意图识别对话期间
   - 所有PIR上报都被忽略
   - 直到对话结束（沉默30秒或PIR无人体）

3. **看护监控中**
   - 统一模式对话期间
   - 所有PIR上报都被忽略
   - 直到看护任务结束

#### ✅ 不会被忽略的情况

1. **访客离开后再次到访**

   ```
   第一次访问：
   PIR触发 → 处理完成 → visitor_processing = False

   访客离开（PIR无人体）

   第二次访问：
   PIR触发 → ✅ visitor_processing = False，正常触发新流程
   ```

2. **处理流程异常结束**

   ```
   PIR触发 → 处理中出现异常
            ↓
            finally块确保清除标志
            ↓
            visitor_processing = False

   下次PIR触发 → ✅ 正常触发新流程
   ```

3. **会话超时自动结束**

   ```
   对话进行中 → 访客沉默30秒
                ↓
                对话自动结束
                ↓
                visitor_processing = False

   下次PIR触发 → ✅ 正常触发新流程
   ```

### 与PIR上报的关系

**重要：** 修改方法**不影响PIR上报本身**

- ✅ ESP32仍然每秒上报PIR事件
- ✅ 服务器仍然接收所有PIR消息
- ✅ PIR消息仍然被转发给App客户端
- ❌ 但**不会重复触发访客处理流程**

**代码层面：**

```python
async def _handle_pir_event(self, conn, ts: int, param):
    """处理 PIR 人体检测事件"""
    duration = param
    conn.logger.bind(tag=TAG).info(f"PIR 检测到人体，持续 {duration} 秒")

    # ✅ 检查是否正在处理访客
    if conn.visitor_processing:
        conn.logger.bind(tag=TAG).debug(
            f"访客处理中，忽略重复的PIR事件"  # ← 这里只是不触发处理流程
        )
        return  # ← 直接返回，不调用 _trigger_face_recognition()

    # ✅ 仍然会转发给App（在 _forward_to_apps 中）
    await self._forward_to_apps(conn, msg_json)

    # 触发人脸识别流程（只在第一次触发）
    await self._trigger_face_recognition(...)
```

            conn.active_session_id = None

````

### 方案2：在会话管理器中添加设备级别查询（辅助）

#### 2.1 添加按设备查询方法

```python
class SessionManager:
    def get_active_session_by_device(self, device_id: str) -> Optional[DoorlockSession]:
        """获取设备的活跃会话

        Args:
            device_id: 设备ID

        Returns:
            活跃会话对象，如果不存在返回None
        """
        with self._lock:
            for session in self._sessions.values():
                if session.device_id == device_id:
                    # 检查会话是否仍然活跃（最近30秒内有活动）
                    silence_duration = (datetime.now() - session.last_activity).total_seconds()
                    if silence_duration < self.dialogue_timeout:
                        logger.bind(tag=TAG).debug(
                            f"找到活跃会话: device_id={device_id}, "
                            f"session_id={session.session_id}"
                        )
                        return session

            logger.bind(tag=TAG).debug(f"设备无活跃会话: device_id={device_id}")
            return None

    def has_active_session(self, device_id: str) -> bool:
        """检查设备是否有活跃会话

        Args:
            device_id: 设备ID

        Returns:
            是否有活跃会话
        """
        return self.get_active_session_by_device(device_id) is not None
````

#### 2.2 在 EventReportHandler 中使用

```python
async def _trigger_face_recognition(
    self,
    conn,
    ts: int,
    param: int,
    trigger_type: str
):
    """统一的人脸识别触发方法"""
    try:
        from core.handle.doorlock_intent_handler import DoorlockIntentHandler

        # 创建意图识别处理器
        intent_handler = await DoorlockIntentHandler.create_from_config(
            config=conn.config,
            logger_instance=conn.logger
        )

        # ✅ 检查是否已有活跃会话
        if intent_handler.session_manager.has_active_session(conn.device_id):
            conn.logger.bind(tag=TAG).debug(
                f"设备已有活跃会话，忽略重复的PIR事件 - 设备: {conn.device_id}"
            )
            return

        # 处理访客到访
        result = await intent_handler.handle_visitor(
            device_id=conn.device_id,
            conn=conn,
            guard_active=is_guard_active
        )

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"处理智能门锁AI功能失败: {e}")
```

### 方案3：基于时间窗口的去重（简单但不完美）

```python
async def _handle_pir_event(self, conn, ts: int, param):
    """处理 PIR 人体检测事件"""
    duration = param  # 持续时间（秒）

    # ✅ 检查是否在时间窗口内（5秒内只处理一次）
    if hasattr(conn, 'last_pir_trigger_time'):
        time_since_last = ts - conn.last_pir_trigger_time
        if time_since_last < 5000:  # 5秒 = 5000毫秒
            conn.logger.bind(tag=TAG).debug(
                f"PIR事件在时间窗口内，忽略 - 设备: {conn.device_id}, "
                f"time_since_last={time_since_last}ms"
            )
            return

    # 记录触发时间
    conn.last_pir_trigger_time = ts

    # 触发人脸识别流程
    await self._trigger_face_recognition(...)
```

**缺点：** 如果访客处理流程超过5秒，仍可能重复触发。

## 修改方法达成的效果说明

### 核心效果：**忽略处理中的重复PIR上报**

当PIR每秒上报一次时，修改后的行为如下：

```
时间轴：访客站在门口5秒

第1秒 PIR上报 → ✅ 触发处理流程（visitor_processing = True）
                 ├─ 拍照
                 ├─ 人脸识别
                 ├─ 下发face_result
                 └─ 播放欢迎词/启动对话

第2秒 PIR上报 → ❌ 检测到 visitor_processing=True，直接忽略
第3秒 PIR上报 → ❌ 检测到 visitor_processing=True，直接忽略
第4秒 PIR上报 → ❌ 检测到 visitor_processing=True，直接忽略
第5秒 PIR上报 → ❌ 检测到 visitor_processing=True，直接忽略

处理完成后 → visitor_processing = False（清除标志）
```

### 详细说明

#### 1. 有权限用户（快速流程）

**场景：** 识别成功 + 有开门权限

```
PIR触发（第1秒）
  ↓
拍照 + 人脸识别（约2-3秒）
  ↓
下发face_result（开锁）
  ↓
播放欢迎词（约3-5秒）
  ↓
清除 visitor_processing 标志
  ↓
总耗时：约5-8秒
```

**期间的PIR上报：** 全部忽略（第2-8秒的上报都被过滤）

**效果：** 访客只听到1次欢迎词，只开锁1次

#### 2. 无权限用户/陌生人（长流程）

**场景：** 识别失败或无权限，启动意图识别对话

```
PIR触发（第1秒）
  ↓
拍照 + 人脸识别（约2-3秒）
  ↓
下发face_result（拒绝开锁）
  ↓
启动意图识别对话（持续30秒或更长）
  ├─ 播放问候："您好，请问您找谁？"
  ├─ 等待访客回复（ASR识别）
  ├─ VLLM分析意图
  ├─ TTS播放AI回复
  └─ 循环对话...
  ↓
对话结束（沉默30秒或PIR无人体）
  ↓
生成意图总结 + 保存记录 + 发送通知
  ↓
清除 visitor_processing 标志
  ↓
总耗时：30秒-5分钟
```

**期间的PIR上报：** 全部忽略（整个对话期间的所有上报都被过滤）

**效果：** 只创建1个对话会话，不会重复启动对话

#### 3. 看护模式（最长流程）

**场景：** 看护模式激活，同时进行对话和监控

```
PIR触发（第1秒）
  ↓
拍照 + 人脸识别
  ↓
启动统一模式对话
  ├─ 启动定时拍照任务（每5秒拍一次）
  ├─ 播放问候
  ├─ 对话循环
  └─ 持续监控快递状态
  ↓
对话结束
  ├─ 停止定时拍照
  ├─ 最终快递状态检查
  ├─ 生成意图总结
  └─ 保存记录 + 发送通知
  ↓
清除 visitor_processing 标志
  ↓
总耗时：可能长达5-10分钟
```

**期间的PIR上报：** 全部忽略（整个看护期间的所有上报都被过滤）

**效果：** 只启动1次看护任务，不会重复创建监控

### 关键点说明

#### ✅ 会被忽略的情况

1. **处理流程进行中**
   - `visitor_processing = True` 时
   - 所有后续PIR上报都被忽略
   - 直到当前访客处理完成

2. **对话进行中**
   - 意图识别对话期间
   - 所有PIR上报都被忽略
   - 直到对话结束（沉默30秒或PIR无人体）

3. **看护监控中**
   - 统一模式对话期间
   - 所有PIR上报都被忽略
   - 直到看护任务结束

#### ✅ 不会被忽略的情况

1. **访客离开后再次到访**

   ```
   第一次访问：
   PIR触发 → 处理完成 → visitor_processing = False

   访客离开（PIR无人体）

   第二次访问：
   PIR触发 → ✅ visitor_processing = False，正常触发新流程
   ```

2. **处理流程异常结束**

   ```
   PIR触发 → 处理中出现异常
            ↓
            finally块确保清除标志
            ↓
            visitor_processing = False

   下次PIR触发 → ✅ 正常触发新流程
   ```

3. **会话超时自动结束**

   ```
   对话进行中 → 访客沉默30秒
                ↓
                对话自动结束
                ↓
                visitor_processing = False

   下次PIR触发 → ✅ 正常触发新流程
   ```

### 与PIR上报的关系

**重要：** 修改方法**不影响PIR上报本身**

- ✅ ESP32仍然每秒上报PIR事件
- ✅ 服务器仍然接收所有PIR消息
- ✅ PIR消息仍然被转发给App客户端
- ❌ 但**不会重复触发访客处理流程**

**代码层面：**

```python
async def _handle_pir_event(self, conn, ts: int, param):
    """处理 PIR 人体检测事件"""
    duration = param
    conn.logger.bind(tag=TAG).info(f"PIR 检测到人体，持续 {duration} 秒")

    # ✅ 检查是否正在处理访客
    if conn.visitor_processing:
        conn.logger.bind(tag=TAG).debug(
            f"访客处理中，忽略重复的PIR事件"  # ← 这里只是不触发处理流程
        )
        return  # ← 直接返回，不调用 _trigger_face_recognition()

    # ✅ 仍然会转发给App（在 _forward_to_apps 中）
    await self._forward_to_apps(conn, msg_json)

    # 触发人脸识别流程（只在第一次触发）
    await self._trigger_face_recognition(...)
```

## 推荐实施方案

**组合使用方案1 + 方案2：**

1. **主要防护：** 在 `ConnectionHandler` 中添加 `visitor_processing` 标志（方案1）
2. **辅助防护：** 在 `SessionManager` 中添加设备级别查询（方案2）
3. **双重检查：** 在 `EventReportHandler` 中同时检查两个条件

### 实施步骤

1. **修改 ConnectionHandler**（`core/connection.py`）
   - 添加 `visitor_processing`、`active_session_id`、`last_pir_trigger_time` 属性

2. **修改 SessionManager**（`core/providers/doorlock/session_manager.py`）
   - 添加 `get_active_session_by_device()` 方法
   - 添加 `has_active_session()` 方法

3. **修改 EventReportHandler**（`core/handle/textHandler/eventReportHandler.py`）
   - 在 `_handle_pir_event()` 中添加状态检查
   - 在 `_trigger_face_recognition()` 中添加会话检查

4. **修改 DoorlockIntentHandler**（`core/handle/doorlock_intent_handler.py`）
   - 在 `handle_visitor()` 开始时设置 `visitor_processing = True`
   - 在 `handle_visitor()` 结束时（finally块）清除标志

## 测试验证

### 测试场景1：PIR持续检测5秒

**预期行为：**

- 第1秒：触发访客处理流程
- 第2-5秒：检测到处理中，忽略后续PIR事件
- 只拍照1次、识别1次、播放1次欢迎词

### 测试场景2：访客离开后再次到访

**预期行为：**

- 第一次访问：正常处理
- 访客离开：清除 `visitor_processing` 标志
- 第二次访问：正常触发新的处理流程

### 测试场景3：对话进行中PIR持续上报

**预期行为：**

- 对话期间：`visitor_processing = True`
- PIR持续上报：全部忽略
- 对话结束：清除标志

## 性能影响评估

### 修复前（有问题）

- PIR持续5秒 → 5次完整处理流程
- 拍照：5次
- 人脸识别：5次（最坏15次）
- 数据库写入：5次
- App通知：5次

### 修复后（正常）

- PIR持续5秒 → 1次完整处理流程
- 拍照：1次
- 人脸识别：1次（最坏3次）
- 数据库写入：1次
- App通知：1次

**性能提升：** 减少80%的资源消耗

## 相关文件

- `core/connection.py` - 连接处理器（需添加状态标志）
- `core/handle/textHandler/eventReportHandler.py` - 事件处理器（需添加检查逻辑）
- `core/handle/doorlock_intent_handler.py` - 意图处理器（需设置/清除标志）
- `core/providers/doorlock/session_manager.py` - 会话管理器（需添加查询方法）

## 总结

当前代码**没有处理PIR每秒上报的情况**，会导致严重的重复处理问题。必须添加状态管理机制来防止重复触发。推荐使用"设备级别处理标志 + 会话管理器查询"的组合方案，既简单又可靠。
