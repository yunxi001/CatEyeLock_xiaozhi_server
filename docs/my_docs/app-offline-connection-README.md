# App 离线连接功能 - 实现总结

## 修改概述

本次修改实现了 App 在 ESP32 设备离线时也能连接服务器的功能，并支持实时推送设备状态信息。

## 核心修改文件

### 1. `core/app_connection.py`

**修改内容：**

- ✅ 移除了设备在线检查，允许 App 在设备离线时连接
- ✅ 添加 `_handle_get_device_status()` 方法处理状态查询
- ✅ 在 `_handle_text_message()` 中添加特殊消息类型处理

**关键代码：**

```python
# 认证时不再检查设备是否在线
is_online = manager.is_esp32_online(device_id)
# 无论设备是否在线都允许连接
await self.websocket.send(json.dumps({
    "type": "hello",
    "status": "ok",
    "device_info": {
        "online": is_online,
        "mode": current_mode
    }
}))
```

### 2. `core/connection.py`

**修改内容：**

- ✅ 在 `__init__` 中添加 `device_state` 属性存储设备状态
- ✅ 添加 `update_device_state()` 异步方法推送状态更新

**关键代码：**

```python
# 设备状态结构
self.device_state = {
    "light": {"status": "unknown"},
    "door": {"status": "unknown", "locked": None},
    "sensors": {},
    "last_update": 0
}

# 状态更新并推送
async def update_device_state(self, state_type: str, state_data: dict):
    # 更新本地状态
    # 推送给所有关联的 App
```

### 3. `core/connection_manager.py`

**修改内容：**

- ✅ 添加 `notify_apps_device_status()` 方法通知设备上线/下线

**关键代码：**

```python
async def notify_apps_device_status(self, device_id: str, status: str, reason: str = None):
    # 通知所有关联的 App 设备状态变化
```

### 4. `core/handle/textHandler/statusReportHandler.py`

**修改内容：**

- ✅ 使用新的 `update_device_state()` 方法替代直接转发
- ✅ 分别更新灯、门锁、传感器状态

## 新增文件

### 1. `test/test_app_offline_connection.py`

测试脚本，验证以下功能：

- 设备离线时 App 连接
- 设备状态变化通知
- 多个 App 同时连接

### 2. `docs/app-offline-connection.md`

详细的功能说明文档，包含：

- 功能概述
- 消息协议
- 连接流程
- 使用场景
- 技术实现

### 3. `docs/app-connection-example.html`

可视化的 Web 测试页面，支持：

- 连接服务器
- 查看设备状态
- 实时接收推送
- 消息日志显示

## 协议定义

### App → 服务器

#### 1. Hello 消息（认证）

```json
{
  "type": "hello",
  "client_type": "app",
  "device_id": "device_001",
  "app_id": "user_001"
}
```

#### 2. 查询设备状态

```json
{
  "type": "get_device_status",
  "seq_id": "seq_1705564800000"
}
```

### 服务器 → App

#### 1. Hello 响应

```json
{
  "type": "hello",
  "status": "ok",
  "device_info": {
    "online": false,
    "mode": "normal"
  }
}
```

#### 2. 设备上线/下线通知

```json
{
  "type": "device_status",
  "status": "online",
  "device_id": "device_001",
  "ts": 1705564800000,
  "reason": "connection_lost"
}
```

#### 3. 设备状态更新

```json
{
  "type": "device_state_update",
  "ts": 1705564800000,
  "state_type": "light",
  "state_data": {
    "status": "on"
  }
}
```

#### 4. 状态查询响应

```json
{
  "type": "device_status_response",
  "seq_id": "seq_1705564800000",
  "ts": 1705564800000,
  "device_id": "device_001",
  "online": true,
  "mode": "normal",
  "state": {
    "light": { "status": "on" },
    "door": { "status": "closed", "locked": true },
    "sensors": {
      "battery": { "name": "battery", "value": 85, "unit": "%" }
    }
  }
}
```

## 测试方法

### 1. 运行自动化测试

```bash
cd main/xiaozhi-server
python test/test_app_offline_connection.py
```

### 2. 使用 Web 测试页面

```bash
# 在浏览器中打开
docs/app-connection-example.html
```

### 3. 手动测试流程

1. 启动服务器（不启动 ESP32 设备）
2. 使用测试页面连接服务器
3. 验证连接成功且显示设备离线
4. 启动 ESP32 设备
5. 验证收到设备上线通知
6. 触发设备状态变化（开关灯、开关门等）
7. 验证收到状态更新推送

## 使用场景

### 场景 1：远程监控

- 用户打开 App 时立即连接服务器
- 即使设备离线也能看到最后的状态
- 设备上线后立即收到通知和最新状态

### 场景 2：多用户协同

- 多个家庭成员可以同时连接
- 任何状态变化都会推送给所有在线的 App
- 支持实时协同操作

### 场景 3：来访记录

- 有人按门铃或人脸识别时
- 所有在线的 App 都会收到通知
- 包含访客照片和识别结果

## 技术亮点

1. **异步推送机制**
   - 使用 `ConnectionManager` 管理连接映射
   - 状态变化时自动推送给所有关联的 App
   - 不阻塞主流程

2. **状态管理**
   - 设备状态存储在 `ConnectionHandler` 中
   - 支持灯、门锁、传感器等多种状态类型
   - 自动记录最后更新时间

3. **容错处理**
   - App 连接失败不影响设备运行
   - 推送失败不影响其他 App
   - 支持断线重连

## 后续优化建议

1. **状态持久化**
   - 将设备状态存储到 Redis/MySQL
   - 支持历史状态查询
   - 设备重启后恢复状态

2. **消息队列**
   - 使用消息队列缓存离线消息
   - App 上线后推送未读消息
   - 支持消息优先级

3. **权限控制**
   - 添加 App 用户权限验证
   - 不同用户看到不同的状态信息
   - 支持操作权限控制

4. **性能优化**
   - 状态推送批量处理
   - 添加推送频率限制
   - 支持状态变化订阅机制

## 兼容性说明

- ✅ 向后兼容现有的 ESP32 连接逻辑
- ✅ 不影响现有的消息处理流程
- ✅ 可选功能，不启用不影响原有功能

## 相关文档

- [详细功能说明](./app-offline-connection.md)
- [Web 测试页面](./app-connection-example.html)
- [测试脚本](../main/xiaozhi-server/test/test_app_offline_connection.py)
