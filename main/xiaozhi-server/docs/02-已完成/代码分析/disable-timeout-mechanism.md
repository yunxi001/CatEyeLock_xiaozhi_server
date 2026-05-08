# 禁用 ESP32 连接超时机制 - 修改说明

## 修改概述

本次修改禁用了服务器端的 ESP32 连接超时检测机制，使 ESP32 设备可以保持永久在线状态，不会因为无语音活动而被服务器主动断开连接。

## 修改日期

2026-01-25

## 修改原因

- ESP32 设备需要保持长期在线状态
- 避免因超时导致的意外断线
- 简化连接管理逻辑

## 影响范围

- ESP32 连接不会因超时被服务器主动断开
- 只有在以下情况下连接才会断开：
  1. ESP32 主动断开连接
  2. 网络异常导致连接中断
  3. 服务器重启
  4. WebSocket 连接异常

## 修改文件清单

### 1. `main/xiaozhi-server/core/connection.py`

**修改位置 1：禁用超时检查任务启动**

```python
# 第 206-207 行（原代码）
# 启动超时检查任务
self.timeout_task = asyncio.create_task(self._check_timeout())
```

**修改为：**

```python
# 禁用超时检查任务（2026-01-25 修改）
# 如需恢复超时机制，取消下面一行的注释
# self.timeout_task = asyncio.create_task(self._check_timeout())
self.timeout_task = None
```

**修改位置 2：禁用第一道超时关闭**

```python
# 第 94-108 行（在 receiveAudioHandle.py 中引用）
# 原代码会在无语音活动超过配置时间后设置 close_after_chat = True
```

**说明：** 这部分逻辑在 `core/handle/receiveAudioHandle.py` 中，需要同步修改。

### 2. `main/xiaozhi-server/core/handle/receiveAudioHandle.py`

**修改位置：禁用无语音超时关闭**

```python
# 第 94-108 行（原代码）
async def no_voice_close_connect(conn, have_voice):
    if have_voice:
        conn.last_activity_time = time.time() * 1000
        return
    # 只有在已经初始化过时间戳的情况下才进行超时检查
    if conn.last_activity_time > 0.0:
        no_voice_time = time.time() * 1000 - conn.last_activity_time
        close_connection_no_voice_time = int(
            conn.config.get("close_connection_no_voice_time", 120)
        )
        if (
            not conn.close_after_chat
            and no_voice_time > 1000 * close_connection_no_voice_time
        ):
            conn.close_after_chat = True
```

**修改为：**

```python
async def no_voice_close_connect(conn, have_voice):
    if have_voice:
        conn.last_activity_time = time.time() * 1000
        return

    # 禁用无语音超时关闭机制（2026-01-25 修改）
    # 如需恢复超时机制，取消下面代码块的注释
    """
    # 只有在已经初始化过时间戳的情况下才进行超时检查
    if conn.last_activity_time > 0.0:
        no_voice_time = time.time() * 1000 - conn.last_activity_time
        close_connection_no_voice_time = int(
            conn.config.get("close_connection_no_voice_time", 120)
        )
        if (
            not conn.close_after_chat
            and no_voice_time > 1000 * close_connection_no_voice_time
        ):
            conn.close_after_chat = True
    """
    pass
```

## 原有超时机制说明

### 超时检测的两道关闭机制

#### 第一道：无语音活动超时（receiveAudioHandle.py）

- **触发条件**：无语音活动超过配置时间（默认 120 秒）
- **行为**：设置 `conn.close_after_chat = True`
- **位置**：`core/handle/receiveAudioHandle.py` 的 `no_voice_close_connect()` 函数
- **配置项**：`config.yaml` 中的 `close_connection_no_voice_time`

#### 第二道：连接总超时（connection.py）

- **触发条件**：无任何活动超过 `timeout_seconds`（默认 180 秒）
- **计算公式**：`timeout_seconds = close_connection_no_voice_time + 60`
- **行为**：主动调用 `await self.close(self.websocket)`
- **位置**：`core/connection.py` 的 `_check_timeout()` 方法
- **检查频率**：每 10 秒检查一次

### 活动时间戳更新时机

`last_activity_time` 会在以下情况更新：

1. **连接建立时**（connection.py 第 204 行）

   ```python
   self.last_activity_time = time.time() * 1000
   ```

2. **收到语音数据时**（receiveAudioHandle.py）

   ```python
   conn.last_activity_time = time.time() * 1000
   ```

3. **收到文本消息时**（listenMessageHandler.py）

   ```python
   conn.last_activity_time = time.time() * 1000
   ```

4. **发送音频时**（sendAudioHandle.py）

   ```python
   conn.last_activity_time = time.time() * 1000
   ```

5. **VAD 检测到语音时**（silero.py）
   ```python
   conn.last_activity_time = time.time() * 1000
   ```

## 配置文件说明

### config.yaml 相关配置项

```yaml
# 无语音活动超时时间（秒）
# 禁用超时机制后，此配置项不再生效
close_connection_no_voice_time: 120
```

**注意：** 禁用超时机制后，此配置项仍然存在但不会被使用。

## 回退方案

### 方案 1：恢复完整超时机制

#### 步骤 1：恢复 connection.py

```python
# 第 206-207 行
# 取消注释以下代码
self.timeout_task = asyncio.create_task(self._check_timeout())
```

#### 步骤 2：恢复 receiveAudioHandle.py

```python
# 第 94-108 行
# 取消注释超时检查代码块
async def no_voice_close_connect(conn, have_voice):
    if have_voice:
        conn.last_activity_time = time.time() * 1000
        return
    # 只有在已经初始化过时间戳的情况下才进行超时检查
    if conn.last_activity_time > 0.0:
        no_voice_time = time.time() * 1000 - conn.last_activity_time
        close_connection_no_voice_time = int(
            conn.config.get("close_connection_no_voice_time", 120)
        )
        if (
            not conn.close_after_chat
            and no_voice_time > 1000 * close_connection_no_voice_time
        ):
            conn.close_after_chat = True
```

### 方案 2：仅恢复第二道超时（推荐用于调试）

只恢复 connection.py 中的超时检查任务，保持第一道关闭禁用：

```python
# connection.py 第 206-207 行
self.timeout_task = asyncio.create_task(self._check_timeout())
```

这样可以保留最后的安全保护，防止僵尸连接。

### 方案 3：调整超时时间（不禁用机制）

如果只是希望延长超时时间而不是完全禁用，可以修改 `config.yaml`：

```yaml
# 设置更长的超时时间（例如 1 小时 = 3600 秒）
close_connection_no_voice_time: 3600
```

## 测试建议

### 测试场景 1：长时间无活动连接

1. ESP32 连接服务器
2. 发送 hello 消息
3. 保持连接但不发送任何消息
4. 等待超过原超时时间（3 分钟）
5. **预期结果**：连接保持，不会被断开

### 测试场景 2：间歇性活动

1. ESP32 连接服务器
2. 每隔 5 分钟发送一次消息
3. 持续测试 1 小时
4. **预期结果**：连接始终保持

### 测试场景 3：网络异常恢复

1. ESP32 连接服务器
2. 模拟网络中断（拔网线）
3. 恢复网络
4. ESP32 重新连接
5. **预期结果**：能够正常重连

## 注意事项

### 潜在风险

1. **僵尸连接**
   - 如果 ESP32 异常断开但服务器未检测到，连接对象会一直占用内存
   - **缓解措施**：依赖 WebSocket 底层的 TCP keepalive 机制

2. **资源占用**
   - 长期保持的连接会持续占用服务器资源（内存、线程等）
   - **缓解措施**：监控服务器资源使用情况

3. **调试困难**
   - 无法通过超时日志判断连接是否正常
   - **缓解措施**：建议启用心跳机制进行监控

### 建议配合使用

**启用心跳机制**（推荐）

ESP32 端定期发送心跳消息：

```json
{
  "type": "heartbeat",
  "ts": 1702234567890,
  "uptime": 3600
}
```

服务器会响应：

```json
{
  "type": "heartbeat_ack",
  "ts": 1702234567891,
  "server_time": 1702234567891
}
```

这样可以在不使用超时机制的情况下，仍然能够监控连接健康状态。

## 日志变化

### 禁用前的日志

```
[INFO] 连接超时，准备关闭
[INFO] 超时检查任务已退出
[INFO] ESP32 连接已注销: device_001, 原因: timeout
```

### 禁用后的日志

不会再出现超时相关的日志，只有在真正断开时才会记录：

```
[INFO] 客户端断开连接
[INFO] ESP32 连接已注销: device_001, 原因: connection_lost
```

## 相关文件路径

- `main/xiaozhi-server/core/connection.py` - 连接处理器
- `main/xiaozhi-server/core/handle/receiveAudioHandle.py` - 音频接收处理
- `main/xiaozhi-server/core/handle/textHandler/heartbeatHandler.py` - 心跳处理器（可选启用）
- `main/xiaozhi-server/config.yaml` - 主配置文件

## 版本信息

- **修改版本**：v1.0
- **修改日期**：2026-01-25
- **修改人**：系统管理员
- **审核状态**：待测试

## 后续优化建议

1. **实现心跳机制**
   - ESP32 端每 30 秒发送一次心跳
   - 服务器端响应心跳并记录最后心跳时间
   - 可选：超过 N 次心跳未收到才断开连接

2. **添加连接监控**
   - 记录连接持续时间
   - 统计活跃连接数
   - 监控异常连接

3. **实现优雅关闭**
   - 服务器重启前通知 ESP32
   - ESP32 收到通知后主动断开并重连

4. **添加管理接口**
   - HTTP API 查看当前连接列表
   - 支持手动踢出指定连接
   - 查看连接详细信息

## 总结

本次修改通过禁用两道超时检查机制，实现了 ESP32 设备的永久在线。修改点明确，回退方案清晰，建议配合心跳机制使用以保证连接质量监控。
