# App 离线连接功能说明

## 功能概述

App 现在可以在 ESP32 设备离线时连接服务器，并实时接收设备状态更新。

## 日志输出说明

### App 连接时的日志

#### 1. App 认证成功

```
[INFO] App 认证成功: device_id=device_001, app_id=user_001, 设备在线=True
```

#### 2. 推送设备状态通知（设备在线）

```
[INFO] 已推送设备状态通知: device_id=device_001, status=在线
[INFO] 已推送完整设备状态: device_id=device_001, state_keys=['light', 'door', 'sensors', 'last_update']
```

#### 3. 推送设备状态通知（设备离线）

```
[INFO] 已推送设备状态通知: device_id=device_001, status=离线
[INFO] 设备离线，无法推送详细状态: device_id=device_001
```

### 设备状态变化时的日志

#### 1. 状态更新

```
[INFO] 设备状态已更新: device_id=device_001, state_type=light, state_data={'status': 'on'}
[INFO] 开始推送状态更新: device_id=device_001, state_type=light, app_count=2
[DEBUG] 已推送状态到 App: device_id=device_001, app_id=user_001, state_type=light
[DEBUG] 已推送状态到 App: device_id=device_001, app_id=user_002, state_type=light
[INFO] 状态推送完成: device_id=device_001, state_type=light, 成功=2, 失败=0
```

#### 2. 无关联 App 时

```
[DEBUG] 无需推送状态（无关联 App）: device_id=device_001, state_type=light
```

### 设备上线/下线时的日志

#### 1. 设备上线

```
[INFO] ESP32 连接已注册: device_001
[INFO] 开始通知设备状态变化: device_id=device_001, status=online, reason=None, app_count=2
[DEBUG] 已通知 App 设备online: device_id=device_001, app_id=user_001
[DEBUG] 已通知 App 设备online: device_id=device_001, app_id=user_002
[INFO] 设备状态通知完成: device_id=device_001, status=online, 成功=2, 失败=0
```

#### 2. 设备下线

```
[INFO] ESP32 连接已注销: device_001, 原因: connection_lost
[INFO] 开始通知设备状态变化: device_id=device_001, status=offline, reason=connection_lost, app_count=2
[DEBUG] 已通知 App 设备offline: device_id=device_001, app_id=user_001
[DEBUG] 已通知 App 设备offline: device_id=device_001, app_id=user_002
[INFO] 设备状态通知完成: device_id=device_001, status=offline, 成功=2, 失败=0
```

### App 查询设备状态时的日志

```
[INFO] 处理设备状态查询: device_id=device_001, app_id=user_001, seq_id=seq_1705564800000, 设备在线=True
[INFO] 设备在线，返回状态: mode=normal, state_keys=['light', 'door', 'sensors', 'last_update']
[INFO] 已发送设备状态响应: device_id=device_001, online=True, data_size=256 bytes
```

## 主要改进

### 1. App 可以在设备离线时连接

**之前的行为：**

- App 连接时必须验证 ESP32 是否在线
- 如果设备离线，App 连接会被拒绝

**现在的行为：**

- App 可以随时连接服务器，无论设备是否在线
- 连接成功后会返回设备的在线状态

### 2. 实时状态推送

App 连接后可以接收以下推送：

#### 设备上线/下线通知

```json
{
  "type": "device_status",
  "status": "online", // 或 "offline"
  "device_id": "device_001",
  "ts": 1705564800000,
  "reason": "connection_lost" // 仅下线时有此字段
}
```

#### 设备状态更新

```json
{
  "type": "device_state_update",
  "ts": 1705564800000,
  "state_type": "light", // light/door/sensor
  "state_data": {
    "status": "on",
    "brightness": 80
  }
}
```

#### 来访通知（人脸识别）

```json
{
  "type": "visit_notification",
  "ts": 1705564800000,
  "data": {
    "visit_id": "visit_123",
    "person_id": "person_001",
    "person_name": "张三",
    "relation": "family",
    "result": "known",
    "access_granted": true,
    "image": "base64_encoded_image_data"
  }
}
```

### 3. 主动查询设备状态

App 可以主动请求设备状态：

**请求：**

```json
{
  "type": "get_device_status",
  "seq_id": "seq_1705564800000"
}
```

**响应：**

```json
{
  "type": "device_status_response",
  "seq_id": "seq_1705564800000",
  "ts": 1705564800000,
  "device_id": "device_001",
  "online": true,
  "mode": "normal", // normal/monitor
  "state": {
    "light": {
      "status": "on",
      "brightness": 80
    },
    "door": {
      "status": "closed",
      "locked": true
    },
    "sensors": {
      "temperature": {
        "name": "temperature",
        "value": 25.5,
        "unit": "°C"
      }
    },
    "last_update": 1705564800000
  }
}
```

## 连接流程

### App 连接步骤

1. **建立 WebSocket 连接**

   ```
   ws://server_ip:8000/ws/app
   ```

2. **发送 hello 消息**

   ```json
   {
     "type": "hello",
     "client_type": "app",
     "device_id": "device_001",
     "app_id": "user_001"
   }
   ```

3. **接收响应**

   ```json
   {
     "type": "hello",
     "status": "ok",
     "device_info": {
       "online": false, // 设备当前状态
       "mode": "normal"
     }
   }
   ```

4. **保持连接，接收推送**
   - 设备上线/下线通知
   - 设备状态变化通知
   - 来访通知等

## ESP32 设备状态管理

### 在 ESP32 连接处理器中更新状态

```python
# 更新灯状态
await connection.update_device_state("light", {
    "status": "on",
    "brightness": 80
})

# 更新门状态
await connection.update_device_state("door", {
    "status": "closed",
    "locked": True
})

# 更新传感器数据
await connection.update_device_state("sensor", {
    "name": "temperature",
    "value": 25.5,
    "unit": "°C"
})
```

### 状态会自动推送给所有关联的 App

## 使用场景

### 场景 1：远程监控

- App 打开时立即连接服务器
- 即使设备离线也能看到最后的状态
- 设备上线后立即收到通知

### 场景 2：多用户访问

- 多个家庭成员可以同时连接
- 任何状态变化都会推送给所有在线的 App
- 支持实时协同

### 场景 3：来访记录

- 有人按门铃或人脸识别时
- 所有在线的 App 都会收到通知
- 包含访客照片和识别结果

## 测试方法

运行测试脚本：

```bash
cd main/xiaozhi-server
python test/test_app_offline_connection.py
```

测试内容：

1. 设备离线时 App 连接
2. 设备状态变化通知
3. 多个 App 同时连接

## 技术实现

### 核心修改

1. **app_connection.py**
   - 移除设备在线检查
   - 添加设备状态查询接口
   - 支持状态推送

2. **connection.py**
   - 添加 `device_state` 属性存储设备状态
   - 添加 `update_device_state()` 方法推送状态

3. **connection_manager.py**
   - 管理 ESP32 和 App 的连接映射
   - 处理设备上线/下线通知

### 消息流程

```
ESP32 设备状态变化
    ↓
ConnectionHandler.update_device_state()
    ↓
ConnectionManager.get_app_conns()
    ↓
推送给所有关联的 App
```

## 注意事项

1. **连接管理**
   - App 断开后会自动从 ConnectionManager 注销
   - ESP32 断开后会通知所有关联的 App

2. **状态同步**
   - 设备状态存储在 ConnectionHandler 中
   - App 连接时可以查询最新状态
   - 状态变化会实时推送

3. **性能考虑**
   - 支持多个 App 同时连接同一设备
   - 状态推送采用异步方式，不会阻塞主流程
   - 推送失败不影响其他 App

## 后续扩展

可以考虑添加：

- 设备状态持久化（Redis/MySQL）
- 历史状态查询接口
- 状态变化事件订阅机制
- 更丰富的传感器数据类型
