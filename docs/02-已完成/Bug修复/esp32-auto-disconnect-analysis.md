# ESP32 自动断开连接机制分析

## 问题

查找当前代码中是否有服务器主动断开 ESP32 连接的逻辑，以及如何禁用该功能。

---

## 分析结果

### ✅ 存在自动断开机制

当前代码中**确实存在**服务器主动断开 ESP32 连接的机制。

---

## 自动断开机制详解

### 1. 核心实现位置

**文件**: `main/xiaozhi-server/core/connection.py`

**相关方法**:

- `_check_timeout()` - 超时检查任务（第 1478 行）
- `handle_connection()` - 启动超时检查（第 206 行）

### 2. 工作原理

#### 2.1 超时检查任务启动

在 ESP32 连接建立时，会自动启动一个超时检查任务：

```python
# connection.py 第 203-206 行
# 初始化活动时间戳
self.last_activity_time = time.time() * 1000

# 启动超时检查任务
self.timeout_task = asyncio.create_task(self._check_timeout())
```

#### 2.2 超时时间计算

```python
# connection.py 第 159-162 行
self.timeout_seconds = (
    int(self.config.get("close_connection_no_voice_time", 120)) + 60
)  # 在原来第一道关闭的基础上加60秒，进行二道关闭
```

**计算公式**: `超时时间 = close_connection_no_voice_time + 60 秒`

**默认值**: `120 + 60 = 180 秒（3 分钟）`

#### 2.3 超时检查逻辑

```python
# connection.py 第 1478-1505 行
async def _check_timeout(self):
    """检查连接超时"""
    try:
        while not self.stop_event.is_set():
            # 检查是否超时（只有在时间戳已初始化的情况下）
            if self.last_activity_time > 0.0:
                current_time = time.time() * 1000
                if (
                    current_time - self.last_activity_time
                    > self.timeout_seconds * 1000
                ):
                    if not self.stop_event.is_set():
                        self.logger.bind(tag=TAG).info("连接超时，准备关闭")
                        # 设置停止事件，防止重复处理
                        self.stop_event.set()
                        # 使用 try-except 包装关闭操作，确保不会因为异常而阻塞
                        try:
                            await self.close(self.websocket)
                        except Exception as close_error:
                            self.logger.bind(tag=TAG).error(
                                f"超时关闭连接时出错: {close_error}"
                            )
                    break
            # 每10秒检查一次，避免过于频繁
            await asyncio.sleep(10)
    except Exception as e:
        self.logger.bind(tag=TAG).error(f"超时检查任务出错: {e}")
    finally:
        self.logger.bind(tag=TAG).info("超时检查任务已退出")
```

**检查频率**: 每 10 秒检查一次

**触发条件**: `当前时间 - 最后活动时间 > 超时时间`

#### 2.4 活动时间更新机制

`last_activity_time` 会在以下情况下更新：

1. **连接建立时** (`connection.py` 第 203 行)
2. **收到语音消息时** (`textHandler/listenMessageHandler.py` 第 38 行)
3. **发送音频时** (`sendAudioHandle.py` 第 110, 181 行)
4. **VAD 检测到语音时** (`providers/vad/silero.py` 第 84 行)

---

## 配置项说明

### 配置文件位置

`main/xiaozhi-server/config.yaml`

### 相关配置项

```yaml
# 没有语音输入多久后断开连接(秒)，默认2分钟，即120秒
close_connection_no_voice_time: 120
```

**说明**:

- 这是第一道超时检查（在其他地方使用）
- 实际的连接超时时间 = `close_connection_no_voice_time + 60` 秒
- 默认值 120 秒，实际超时时间为 180 秒（3 分钟）

---

## 如何禁用自动断开功能

### 方案 1: 设置超大超时时间（推荐）

修改 `config.yaml`:

```yaml
# 设置为一个非常大的值（例如 24 小时 = 86400 秒）
close_connection_no_voice_time: 86400
```

**优点**:

- 简单，只需修改配置
- 不需要修改代码
- 保留了超时机制，避免僵尸连接

**缺点**:

- 仍然会在超时后断开（只是时间很长）
- 可能导致僵尸连接占用资源

---

### 方案 2: 修改代码完全禁用（不推荐）

#### 2.1 方案 A: 不启动超时检查任务

修改 `main/xiaozhi-server/core/connection.py` 第 206 行：

```python
# 修改前
self.timeout_task = asyncio.create_task(self._check_timeout())

# 修改后（注释掉）
# self.timeout_task = asyncio.create_task(self._check_timeout())
```

#### 2.2 方案 B: 在超时检查中直接返回

修改 `main/xiaozhi-server/core/connection.py` 第 1478 行：

```python
async def _check_timeout(self):
    """检查连接超时"""
    # 禁用超时检查
    return

    # 原有代码...
```

#### 2.3 方案 C: 添加配置开关

在 `config.yaml` 中添加新配置项：

```yaml
# 是否启用连接超时检查
enable_connection_timeout: false
```

然后修改 `connection.py`:

```python
# 在 __init__ 中读取配置
self.enable_timeout = self.config.get("enable_connection_timeout", True)

# 在 handle_connection 中条件启动
if self.enable_timeout:
    self.timeout_task = asyncio.create_task(self._check_timeout())
```

**优点**:

- 灵活，可通过配置控制
- 不影响其他功能

**缺点**:

- 需要修改代码
- 可能导致僵尸连接永久占用资源

---

## 其他相关机制

### 1. 第一道超时检查

**文件**: `main/xiaozhi-server/core/handle/receiveAudioHandle.py`

**方法**: `no_voice_close_connect()` (第 94 行)

```python
async def no_voice_close_connect(conn, have_voice):
    if have_voice:
        conn.last_activity_time = time.time() * 1000
        return
    # 只有在已经初始化过时间戳的情况下才进行超时检查
    if conn.last_activity_time > 0.0:
        no_voice_time = time.time() * 1000 - conn.last_activity_time
        close_connection_no_voice_time = int(
            conn.config.get("close_connection_no_voice_time", 120)
```

这是第一道超时检查，使用 `close_connection_no_voice_time` 配置（120 秒）。

### 2. ConnectionManager 通知机制

**文件**: `main/xiaozhi-server/core/connection_manager.py`

当 ESP32 断开连接时，会通知所有关联的 App：

```python
def unregister_esp32(self, device_id: str, reason: str = "connection_lost") -> None:
    """注销 ESP32 连接

    Args:
        device_id: 设备唯一标识符
        reason: 断开原因（connection_lost/device_disconnect/server_kick/timeout）
    """
    if device_id in self.esp32_connections:
        del self.esp32_connections[device_id]
        self.logger.bind(tag=TAG).info(f"ESP32 连接已注销: {device_id}, 原因: {reason}")

        # 通知关联的 App 设备下线
        asyncio.create_task(self.notify_apps_device_status(device_id, "offline", reason))
```

**断开原因类型**:

- `connection_lost` - 连接丢失
- `device_disconnect` - 设备主动断开
- `server_kick` - 服务器踢出
- `timeout` - 超时断开

---

## 建议

### 对于门锁场景

如果是门锁监控场景，需要保持长连接，建议：

1. **方案 1（推荐）**: 设置较大的超时时间

   ```yaml
   close_connection_no_voice_time: 3600 # 1 小时
   ```

2. **方案 2**: 定期发送心跳包
   - 在 ESP32 端每隔 1-2 分钟发送一个心跳消息
   - 服务器收到心跳后更新 `last_activity_time`

3. **方案 3**: 添加配置开关（需要修改代码）
   - 为门锁设备单独配置，禁用超时检查
   - 其他设备保持原有超时机制

### 对于普通语音交互场景

保持现有的超时机制，避免僵尸连接占用资源。

---

## 总结

1. ✅ 当前代码**存在**服务器主动断开 ESP32 连接的机制
2. 超时时间 = `close_connection_no_voice_time + 60` 秒（默认 180 秒）
3. 可以通过修改 `config.yaml` 中的 `close_connection_no_voice_time` 来调整超时时间
4. 如需完全禁用，建议添加配置开关而非直接注释代码
5. 对于门锁监控场景，建议设置较大的超时时间或实现心跳机制
