# App 上线推送功能实现说明

## 功能概述

当 App 连接到服务器并完成认证后，服务器会主动推送设备状态信息，让 App 无需手动查询即可获取最新状态。

## 推送策略

### P0 优先级（立即推送）

认证成功后立即推送，确保 App 快速获取关键信息：

1. **设备在线状态** (`device_status`)
   - 设备是否在线
   - 当前工作模式（normal/monitor）

2. **传感器状态** (`status_report`)
   - 电量百分比
   - 光照值
   - 锁状态
   - 补光灯状态

### P1 优先级（延迟推送）

认证成功后延迟 1 秒推送，避免阻塞认证响应：

1. **最近 5 条开锁日志** (`log_report`)
   - 开锁方式
   - 用户 ID
   - 开锁状态
   - 失败次数

2. **最近 5 条到访记录** (`visit_notification`)
   - 访客信息
   - 识别结果
   - 访问权限
   - 抓拍图片路径

### P2 优先级（按需查询）

App 通过 `query` 接口主动查询：

- 历史事件 (`events`)
- 访客意图 (`visitor_intents`)
- 快递警报 (`package_alerts`)
- 媒体文件 (`media_files`)

## 实现细节

### 1. 传感器状态推送

**优先级**：实时状态 > 数据库最新记录

```python
async def _push_sensor_status(self, is_online: bool, esp32_conn):
    # 1. 优先从 ESP32 连接对象获取实时状态
    if is_online and esp32_conn:
        device_state = getattr(esp32_conn, "device_state", None)

    # 2. 如果没有实时状态，从数据库查询最后一次上报的状态
    if not device_state:
        # 查询 device_status 表
        SELECT battery, lux, lock_state, light_state, created_at
        FROM device_status
        WHERE device_id = %s
        ORDER BY created_at DESC
        LIMIT 1
```

### 2. 开锁日志推送

从 `unlock_logs` 表查询最近 5 条记录：

```sql
SELECT method, user_id, status, fail_count, lock_time, created_at
FROM unlock_logs
WHERE device_id = %s
ORDER BY created_at DESC
LIMIT 5
```

### 3. 到访记录推送

从 `visit_records` 表关联 `persons` 表查询：

```sql
SELECT vr.id, vr.person_id, p.name as person_name, p.relation_type,
       vr.recognition_result, vr.access_granted, vr.photo_path, vr.visit_time
FROM visit_records vr
LEFT JOIN persons p ON vr.person_id = p.id
WHERE vr.id IN (
    SELECT id FROM visit_records
    ORDER BY visit_time DESC
    LIMIT 5
)
ORDER BY vr.visit_time DESC
```

## 消息格式

### 1. 设备在线状态

```json
{
  "type": "device_status",
  "status": "online",
  "device_id": "AA:BB:CC:DD:EE:FF",
  "ts": 1702234567890
}
```

### 2. 传感器状态

```json
{
  "type": "status_report",
  "ts": 1702234567890,
  "data": {
    "bat": 85,
    "lux": 300,
    "lock": 0,
    "light": 1
  }
}
```

### 3. 开锁日志

```json
{
  "type": "log_report",
  "ts": 1702234567890,
  "data": {
    "method": "finger",
    "uid": 5,
    "status": "success",
    "fail_count": 0,
    "lock_time": 0
  }
}
```

### 4. 到访记录

```json
{
  "type": "visit_notification",
  "ts": 1702234567890,
  "data": {
    "visit_id": 123,
    "person_id": 5,
    "person_name": "张三",
    "relation": "family",
    "result": "known",
    "access_granted": true,
    "image": null,
    "image_path": "faces/AA:BB:CC:DD:EE:FF/2024-12-11/face_1702234567890_5.jpg"
  }
}
```

## 测试方法

### 1. 准备测试数据

在数据库中插入测试数据：

```sql
-- 插入设备状态
INSERT INTO device_status (device_id, battery, lux, lock_state, light_state)
VALUES ('AA:BB:CC:DD:EE:FF', 85, 300, 0, 1);

-- 插入开锁日志
INSERT INTO unlock_logs (device_id, method, user_id, status, fail_count, lock_time)
VALUES ('AA:BB:CC:DD:EE:FF', 'finger', 5, 'success', 0, 0);

-- 插入人员信息
INSERT INTO persons (name, relation_type)
VALUES ('张三', 'family');

-- 插入到访记录
INSERT INTO visit_records (person_id, recognition_result, access_granted, photo_path)
VALUES (1, 'known', 1, 'faces/AA:BB:CC:DD:EE:FF/2024-12-11/face_1702234567890_5.jpg');
```

### 2. 使用 WebSocket 客户端测试

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/app");

ws.onopen = () => {
  // 发送 hello 消息
  ws.send(
    JSON.stringify({
      type: "hello",
      device_id: "AA:BB:CC:DD:EE:FF",
      app_id: "test_user_001",
      client_type: "app",
    }),
  );
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log("收到消息:", msg.type, msg);

  // 预期收到的消息顺序：
  // 1. hello 响应
  // 2. device_status（立即）
  // 3. status_report（立即）
  // 4. log_report x 5（延迟1秒）
  // 5. visit_notification x 5（延迟1秒）
};
```

### 3. 验证推送顺序

使用日志查看推送顺序：

```bash
tail -f logs/xiaozhi-server.log | grep "已推送"
```

预期输出：

```
[INFO] 已推送设备状态通知: device_id=AA:BB:CC:DD:EE:FF, status=在线
[INFO] 已推送传感器状态: device_id=AA:BB:CC:DD:EE:FF, source=数据库
[INFO] 已推送最近开锁日志: device_id=AA:BB:CC:DD:EE:FF, count=5
[INFO] 已推送最近到访记录: device_id=AA:BB:CC:DD:EE:FF, count=5
```

## 性能优化

### 1. 数据库查询优化

- 使用索引：`idx_device_time (device_id, created_at)`
- 限制查询数量：`LIMIT 5`
- 使用连接池：复用数据库连接

### 2. 推送策略优化

- **立即推送**：关键状态（在线、传感器）
- **延迟推送**：历史数据（开锁日志、到访记录）
- **按需查询**：大量历史数据（通过 query 接口）

### 3. 错误处理

- 数据库查询失败：记录日志，跳过推送
- WebSocket 发送失败：记录日志，继续推送其他数据
- 数据不存在：记录 debug 日志，不影响其他推送

## 注意事项

### 1. 设备离线场景

- 设备离线时，传感器状态从数据库查询最后一次上报的状态
- 开锁日志和到访记录仍然推送（历史数据）

### 2. 数据库表不存在

- 如果数据库表不存在，会记录错误日志并跳过推送
- 不影响 App 认证流程

### 3. 推送失败处理

- 推送失败不会重试（避免阻塞）
- App 可以通过 `query` 接口主动查询

## 相关文件

- `main/xiaozhi-server/core/app_connection.py` - App 连接处理器
- `main/xiaozhi-server/core/handle/textHandler/queryHandler.py` - 查询处理器
- `main/xiaozhi-server/core/providers/doorlock/database.py` - 数据库操作
- `docs/01-当前文档/智能猫眼门锁系统-服务器与App通信协议规范-v2.5.md` - 协议规范

## 更新日志

- **2026-01-17**：实现 App 上线推送功能
  - 添加 `_push_sensor_status()` 方法
  - 添加 `_push_history_data_delayed()` 方法
  - 添加 `_push_recent_unlock_logs()` 方法
  - 添加 `_push_recent_visits()` 方法
