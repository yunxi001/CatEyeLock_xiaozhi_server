# connection.py 关闭连接相关提交分析

## 分析目标

查找最近四次提交中是否有修改服务器主动断开 ESP32 连接的逻辑。

## 提交列表（从新到旧）

1. **98d28cb3** - 修改了部分通信协议 (2026-01-25)
2. **adfbe951** - 修改协议前的保存 (2026-01-17)
3. **7dc3fdde** - 先提交一下，写到了人脸识别，还没测试 (2025-12-08)
4. **adcc06ed** - 计划完成，开始执行，已经做了第1部分计划 (2025-12-04)

---

## 详细分析

### 1. 提交 98d28cb3 (2026-01-25)

**提交信息**: 修改了部分通信协议

**主要变更**:

- 新增设备状态信息字段 `device_state`（灯、门、传感器状态）
- 修改人脸识别响应格式（移除 `msg_id`，符合 v5.2 协议）
- 优化监控模式音视频转发逻辑（区分音频/视频帧）
- 新增 `update_device_state()` 方法用于推送设备状态给 App
- 优化 opus 解码错误处理（限制日志频率，自动重置解码器）

**关于连接关闭**: ❌ **无相关修改**

- 未修改 `close()` 方法
- 未修改连接超时逻辑
- 未修改主动断开连接的代码

---

### 2. 提交 adfbe951 (2026-01-17)

**提交信息**: 修改协议前的保存

**主要变更**:

- 新增二进制人脸识别处理 `_handle_face_recognition_binary()`
- 修改 `_forward_to_apps()` 方法：将 opus 解码为 PCM 后转发
- 新增 `_handle_monitor_data()` 方法处理监控模式音视频
- **修改 `close()` 方法签名**：新增 `reason` 参数

**关于连接关闭**: ⚠️ **有修改，但不是主动断开逻辑**

```python
# 修改前
async def close(self, ws=None):
    """资源清理方法"""
    if self.device_id:
        manager = ConnectionManager.get_instance()
        manager.unregister_esp32(self.device_id)

# 修改后
async def close(self, ws=None, reason: str = "connection_closed"):
    """资源清理方法

    Args:
        ws: WebSocket 连接
        reason: 断开原因（connection_closed/timeout/error）
    """
    if self.device_id:
        manager = ConnectionManager.get_instance()
        manager.unregister_esp32(self.device_id, reason=reason)
```

**分析**:

- 仅增加了 `reason` 参数用于记录断开原因
- 将 `reason` 传递给 `ConnectionManager.unregister_esp32()`
- **没有修改主动断开连接的逻辑**，只是增强了断开原因的追踪能力

---

### 3. 提交 7dc3fdde (2025-12-08)

**提交信息**: 先提交一下，写到了人脸识别，还没测试

**主要变更**:

- 新增监控模式判断：`if self.current_mode == "monitor"`
- 新增 `_forward_to_apps()` 方法用于转发数据给 App
- 监控模式下不再将音频送入 ASR，而是直接转发

**关于连接关闭**: ❌ **无相关修改**

- 未修改 `close()` 方法
- 未修改连接管理逻辑

---

### 4. 提交 adcc06ed (2025-12-04)

**提交信息**: 计划完成，开始执行，已经做了第1部分计划

**主要变更**:

- 导入 `ConnectionManager` 模块
- 新增 `current_mode` 字段（normal | monitor）
- 在 `handle_connection()` 中注册 ESP32 到 `ConnectionManager`
- 在 `close()` 中从 `ConnectionManager` 注销 ESP32

**关于连接关闭**: ⚠️ **有修改，但不是主动断开逻辑**

```python
# 在 handle_connection() 中新增
if self.device_id:
    manager = ConnectionManager.get_instance()
    manager.register_esp32(self.device_id, self)

# 在 close() 中新增
if self.device_id:
    manager = ConnectionManager.get_instance()
    manager.unregister_esp32(self.device_id)
```

**分析**:

- 引入了 `ConnectionManager` 统一管理连接
- 在连接建立时注册，在连接关闭时注销
- **没有修改主动断开连接的逻辑**，只是增加了连接管理机制

---

## 结论

### ❌ 未发现服务器主动断开 ESP32 连接的修改

在这四次提交中，**没有找到修改服务器主动断开 ESP32 连接的代码**。

### 相关修改总结

1. **提交 adfbe951**: 为 `close()` 方法增加了 `reason` 参数，用于记录断开原因
2. **提交 adcc06ed**: 引入 `ConnectionManager` 进行连接注册/注销管理

这些修改都是**增强连接管理能力**，而非修改主动断开逻辑。

### 可能的主动断开逻辑位置

如果需要查找服务器主动断开 ESP32 的逻辑，应该检查：

1. **超时断开**: 搜索 `timeout`、`idle`、`last_activity` 相关代码
2. **异常断开**: 搜索 `websocket.close()`、`await self.close()` 的调用位置
3. **ConnectionManager**: 检查 `ConnectionManager` 类中是否有主动断开的方法

### 建议

如果需要进一步分析主动断开逻辑，可以：

```bash
# 搜索 close() 方法的调用位置
git log -p --all -S "await self.close" -- main/xiaozhi-server/core/connection.py

# 搜索超时相关的修改
git log -p --all -S "timeout" -- main/xiaozhi-server/core/connection.py

# 搜索 websocket.close 的调用
git log -p --all -S "websocket.close" -- main/xiaozhi-server/core/connection.py
```
