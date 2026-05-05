# 任务 9 实现总结 - 命令下发重试机制

## 实现概述

成功实现了服务器端命令下发重试机制，支持 ESP32 v5.2 协议的两级确认机制。

## 完成的子任务

### ✅ 9.1 更新 LockControlProxyHandler
- 修改 `_forward_to_esp32()` 方法，调用 `_forward_with_retry()`
- 使用 `seq_id` 替代 `msg_id`（v5.2 协议）
- 添加错误码支持（`ErrorCode.DEVICE_OFFLINE`）

### ✅ 9.2 实现 _forward_with_retry() 方法
- 循环最多 3 次重试
- 每次发送命令后调用 `_wait_for_esp32_ack()`
- 如果收到 `esp32_ack`，返回 `True` 并停止重试
- 如果 3 次都超时，调用 `_send_error()` 发送 `code=5`（超时）错误

### ✅ 9.3 实现 _wait_for_esp32_ack() 方法
- 创建 `asyncio.Future` 对象
- 将 Future 存储到 `esp32_conn._pending_esp32_acks[seq_id]`
- 使用 `asyncio.wait_for()` 等待 2 秒超时
- 超时返回 `False`，收到响应返回 `True`
- 清理 `_pending_esp32_acks` 中的 Future

### ✅ 9.4 更新 _send_error() 方法
- 支持 `code` 参数（统一错误码 0-10）
- 发送包含 `code` 字段的错误响应
- 默认值为 `ErrorCode.INTERNAL_ERROR`

### ✅ 9.5 复制到其他 ProxyHandler
- 将重试机制复制到 `DevControlProxyHandler`
- 将重试机制复制到 `UserMgmtProxyHandler`
- 所有三个 ProxyHandler 现在都支持重试机制

## 关键实现细节

### 1. 协议版本升级
```python
# v5.0 (旧版)
msg_json["msg_id"] = f"cmd_{int(time.time() * 1000)}"

# v5.2 (新版)
seq_id = f"cmd_{int(time.time() * 1000)}"
msg_json["seq_id"] = seq_id
```

### 2. 重试机制流程
```
App → Server → ESP32
         ↓
    发送命令（第1次）
         ↓
    等待 esp32_ack (2秒超时)
         ↓
    超时？→ 重试（第2次）
         ↓
    等待 esp32_ack (2秒超时)
         ↓
    超时？→ 重试（第3次）
         ↓
    等待 esp32_ack (2秒超时)
         ↓
    超时？→ 返回错误给 App (code=5)
         ↓
    成功？→ 停止重试，等待 ack
```

### 3. Future 触发机制
```python
# commandProxyHandler.py 中注册 Future
esp32_conn._pending_esp32_acks[seq_id] = future

# esp32AckHandler.py 中触发 Future
if hasattr(conn, "_pending_esp32_acks") and seq_id in conn._pending_esp32_acks:
    future = conn._pending_esp32_acks[seq_id]
    if not future.done():
        future.set_result(code == 0)
```

### 4. 错误码映射
```python
from core.constants.error_codes import ErrorCode

# 设备离线
await self._send_error(conn, "设备离线", code=ErrorCode.DEVICE_OFFLINE)

# 超时
await self._send_error(conn, "设备无响应，请检查设备状态", code=ErrorCode.TIMEOUT)

# 内部错误
await self._send_error(conn, f"转发失败: {str(e)}", code=ErrorCode.INTERNAL_ERROR)
```

## 测试结果

所有测试用例通过：

1. ✅ 重试机制 - 第一次就成功
2. ✅ 重试机制 - 第一次超时，第二次成功
3. ✅ 重试机制 - 全部超时（3次）
4. ✅ _wait_for_esp32_ack - 超时
5. ✅ _wait_for_esp32_ack - 收到确认

## 验证需求

### Requirements 1.3 - 命令重试机制
✅ 实现了最多 3 次重试
✅ 每次等待 2 秒超时
✅ 收到 `esp32_ack` 后停止重试

### Requirements 1.4 - 错误处理
✅ 重试全部失败后返回 `code=5`（超时）错误
✅ 设备离线返回 `code=1`（设备离线）错误
✅ 内部错误返回 `code=10`（内部错误）错误

## 影响的文件

### 修改的文件
- `main/xiaozhi-server/core/handle/textHandler/commandProxyHandler.py`
  - 更新了 `LockControlProxyHandler`
  - 更新了 `DevControlProxyHandler`
  - 更新了 `UserMgmtProxyHandler`

### 新增的文件
- `main/xiaozhi-server/test/test_retry_mechanism.py` - 重试机制测试
- `main/xiaozhi-server/test/TASK_9_SUMMARY.md` - 本文档

## 与其他任务的集成

### 依赖的任务
- ✅ 任务 1: 创建错误码常量定义（`ErrorCode`）
- ✅ 任务 3: 实现 `Esp32AckHandler`（触发 Future）

### 被依赖的任务
- 任务 10: 注册新增处理器（需要确保 `Esp32AckHandler` 已注册）
- 任务 14.7: 编写单元测试（测试命令重试机制）

## 注意事项

1. **Server 内部重试对 App 透明**：App 只收到最终结果（成功或失败）
2. **esp32_ack 不转发给 App**：仅用于 Server 内部判断是否需要重试
3. **Future 清理**：无论成功还是超时，都会清理 `_pending_esp32_acks` 中的 Future
4. **异步编程**：所有方法都是异步的，使用 `async/await`
5. **错误码统一**：使用 `ErrorCode` 常量，范围 0-10

## 后续工作

1. 集成测试：测试端到端的命令下发流程（App → Server → ESP32 → Server → App）
2. 性能测试：验证重试机制不会显著增加延迟
3. 监控指标：添加重试次数、成功率等监控指标

---

**实现日期**: 2026-01-17  
**实现者**: Kiro AI Assistant  
**状态**: ✅ 完成
