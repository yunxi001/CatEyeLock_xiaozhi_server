# App 上线推送功能 - 快速启动指南

## 🚀 快速开始

### 1. 确认功能已启用

功能已自动集成到 `AppConnectionHandler` 中，无需额外配置。

### 2. 准备测试数据（可选）

如果数据库中没有数据，可以插入一些测试数据：

```sql
-- 插入设备状态
INSERT INTO device_status (device_id, battery, lux, lock_state, light_state)
VALUES ('AA:BB:CC:DD:EE:FF', 85, 300, 0, 1);

-- 插入开锁日志
INSERT INTO unlock_logs (device_id, method, user_id, status, fail_count, lock_time)
VALUES
  ('AA:BB:CC:DD:EE:FF', 'finger', 5, 'success', 0, 0),
  ('AA:BB:CC:DD:EE:FF', 'nfc', 3, 'success', 0, 0),
  ('AA:BB:CC:DD:EE:FF', 'face', 7, 'success', 0, 0);

-- 插入人员信息
INSERT INTO persons (name, relation_type)
VALUES
  ('张三', 'family'),
  ('李四', 'friend'),
  ('王五', 'courier');

-- 插入到访记录
INSERT INTO visit_records (person_id, recognition_result, access_granted, photo_path)
VALUES
  (1, 'known', 1, 'faces/AA:BB:CC:DD:EE:FF/2024-12-11/face_001.jpg'),
  (2, 'known', 1, 'faces/AA:BB:CC:DD:EE:FF/2024-12-11/face_002.jpg'),
  (3, 'known', 0, 'faces/AA:BB:CC:DD:EE:FF/2024-12-11/face_003.jpg');
```

### 3. 启动服务器

```bash
cd main/xiaozhi-server
python app.py
```

### 4. 测试推送功能

#### 方法 A：使用浏览器测试页面（推荐）

1. 用浏览器打开 `test/test_app_push.html`
2. 配置参数：
   - 服务器地址：`ws://localhost:8000/ws/app`
   - 设备 ID：`AA:BB:CC:DD:EE:FF`
   - App ID：`test_user_001`
3. 点击"连接服务器"按钮
4. 观察推送的消息

#### 方法 B：使用 Python 测试脚本

```bash
cd main/xiaozhi-server
python test/test_app_initial_push.py
```

#### 方法 C：使用 WebSocket 客户端工具

推荐工具：

- [Postman](https://www.postman.com/)
- [WebSocket King](https://websocketking.com/)
- [wscat](https://github.com/websockets/wscat)

连接地址：`ws://localhost:8000/ws/app`

发送消息：

```json
{
  "type": "hello",
  "device_id": "AA:BB:CC:DD:EE:FF",
  "app_id": "test_user_001",
  "client_type": "app"
}
```

### 5. 查看服务器日志

```bash
# 实时查看推送日志
tail -f logs/xiaozhi-server.log | grep "已推送"

# 查看所有 App 相关日志
tail -f logs/xiaozhi-server.log | grep "App"
```

## 📊 预期结果

### 1. 消息推送顺序

```
1. hello 响应（认证成功）
2. device_status（设备在线状态）- 立即
3. status_report（传感器状态）- 立即
4. log_report x 5（开锁日志）- 延迟 1 秒
5. visit_notification x 5（到访记录）- 延迟 1 秒
```

### 2. 日志输出

```
[INFO] App 认证成功: device_id=AA:BB:CC:DD:EE:FF, app_id=test_user_001, 设备在线=True
[INFO] 已推送设备状态通知: device_id=AA:BB:CC:DD:EE:FF, status=在线
[INFO] 已推送传感器状态: device_id=AA:BB:CC:DD:EE:FF, source=数据库
[INFO] 已推送最近开锁日志: device_id=AA:BB:CC:DD:EE:FF, count=3
[INFO] 已推送最近到访记录: device_id=AA:BB:CC:DD:EE:FF, count=3
```

### 3. 浏览器测试页面

- 总消息数：8-10 条
- P0 消息：3 条（hello, device_status, status_report）
- P1 消息：5-10 条（log_report, visit_notification）
- 耗时：约 1-2 秒

## 🔍 故障排查

### 问题 1：没有收到推送消息

**可能原因**：

- 数据库中没有数据
- 数据库连接失败
- WebSocket 连接断开

**解决方法**：

1. 检查数据库是否有数据：

   ```sql
   SELECT COUNT(*) FROM device_status WHERE device_id = 'AA:BB:CC:DD:EE:FF';
   SELECT COUNT(*) FROM unlock_logs WHERE device_id = 'AA:BB:CC:DD:EE:FF';
   SELECT COUNT(*) FROM visit_records;
   ```

2. 检查服务器日志：

   ```bash
   tail -f logs/xiaozhi-server.log | grep "ERROR"
   ```

3. 检查 WebSocket 连接状态

### 问题 2：只收到部分消息

**可能原因**：

- 数据库中只有部分数据
- 推送过程中出现错误

**解决方法**：

1. 查看服务器日志，确认哪些推送失败
2. 检查数据库表是否存在
3. 确认数据库连接配置正确

### 问题 3：推送延迟过长

**可能原因**：

- 数据库查询慢
- 网络延迟
- 服务器负载高

**解决方法**：

1. 检查数据库索引是否存在
2. 优化数据库查询
3. 增加数据库连接池大小

## 📝 配置说明

### 数据库配置

编辑 `config.yaml`：

```yaml
mysql:
  host: 127.0.0.1
  port: 3306
  user: root
  password: "123456"
  database: smart_doorlock
  pool_size: 5
```

### 推送配置（未来扩展）

```yaml
app_push:
  enabled: true
  delay_seconds: 1
  unlock_logs_limit: 5
  visits_limit: 5
```

## 🎯 下一步

1. **集成到 App 客户端**
   - 实现 WebSocket 连接
   - 处理推送消息
   - 更新 UI 显示

2. **优化推送策略**
   - 根据实际使用情况调整推送数量
   - 添加推送配置选项
   - 支持增量推送

3. **监控和告警**
   - 监控推送成功率
   - 监控推送延迟
   - 设置告警阈值

## 📚 相关文档

- [实现文档](./app-initial-push-implementation.md)
- [总结文档](./app-initial-push-summary.md)
- [App 通信协议规范 v2.5](./智能猫眼门锁系统-服务器与App通信协议规范-v2.5.md)

## 💡 提示

- 推送功能不会阻塞认证流程
- 推送失败不会影响 App 连接
- App 可以通过 `query` 接口主动查询更多数据
- 设备离线时也会推送最后已知状态

---

**更新日期**：2026-01-17  
**版本**：v1.0
