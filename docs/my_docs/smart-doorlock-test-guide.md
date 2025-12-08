# 智能门锁测试指南

## 测试准备

### 1. 启动服务器

```bash
cd main/xiaozhi-server
python app.py
```

确保服务器在 `http://localhost:8000` 运行。

### 2. 打开 App Demo

在浏览器中打开：
```
main/xiaozhi-server/test/app_demo.html
```

---

## 测试步骤

### 测试 1：基础连接测试

**目标**：验证 App 可以连接到服务器并通过认证

**步骤**：
1. 确保有一个 ESP32 设备已连接（device-id: `AA:BB:CC:DD:EE:FF`）
2. 在 App Demo 中填写：
   - 服务器地址：`ws://localhost:8000/ws/app`
   - 设备 ID：`AA:BB:CC:DD:EE:FF`
3. 点击"连接服务器"

**预期结果**：
- 日志显示"WebSocket 连接已建立"
- 日志显示"已发送认证消息"
- 日志显示"认证成功！"
- 状态变为"已连接"（绿色）
- 模式控制按钮变为可用

**失败情况**：
- 如果 ESP32 不在线，会显示"认证失败: 设备 AA:BB:CC:DD:EE:FF 不在线"

---

### 测试 2：模式切换测试

**目标**：验证可以切换到监控模式

**前提**：已完成测试 1

**步骤**：
1. 点击"启动监控模式"按钮
2. 观察日志

**预期结果**：
- 日志显示"发送启动监控模式命令"
- 日志显示"收到消息: {type: 'system', status: 'success', command: 'start_monitor'}"
- 日志显示"系统命令执行成功: start_monitor"

**验证**：
- ESP32 端应该收到 `{"type": "system", "command": "start_monitor"}` 消息

---

### 测试 3：视频监控测试

**目标**：验证可以接收并显示视频数据

**前提**：已完成测试 2（处于监控模式）

**步骤**：
1. ESP32 发送视频数据（BinaryProtocol2 格式）
2. 观察 App Demo 的视频区域

**预期结果**：
- 视频区域显示实时画面
- "视频帧数"计数器增加
- "接收数据"显示数据量
- 日志显示"收到视频帧 640x480 (xxx bytes)"

**测试数据示例**（Python）：
```python
import struct

# 构造 BinaryProtocol2 视频帧
version = 2
msg_type = 0
width = 640
height = 480
reserved = (width << 16) | height
timestamp = int(time.time() * 1000)
jpeg_data = b'...'  # JPEG 图像数据
payload_size = len(jpeg_data)

header = struct.pack('>HHIII', version, msg_type, reserved, timestamp, payload_size)
message = header + jpeg_data

# 发送
await websocket.send(message)
```

---

### 测试 4：音频接收测试

**目标**：验证可以接收音频数据

**前提**：已完成测试 2（处于监控模式）

**步骤**：
1. ESP32 发送音频数据（BinaryProtocol2 格式，reserved=0）
2. 观察日志

**预期结果**：
- "音频包数"计数器增加
- 日志显示"收到音频包 (xxx bytes)"

---

### 测试 5：双向对讲测试

**目标**：验证 App 可以发送音频给 ESP32

**前提**：已完成测试 2（处于监控模式）

**步骤**：
1. 点击"开始对讲"按钮
2. 浏览器会请求麦克风权限，点击"允许"
3. 对着麦克风说话
4. 观察日志

**预期结果**：
- 日志显示"开始对讲"
- 日志显示"发送音频数据 (xxx bytes)"
- ESP32 端应该收到音频数据

**停止对讲**：
- 点击"停止对讲"按钮

---

### 测试 6：消息转发测试

**目标**：验证带 forward 字段的消息可以正确转发

**前提**：已完成测试 1

**步骤**：
1. 打开浏览器开发者工具（F12）
2. 在 Console 中执行：
```javascript
ws.send(JSON.stringify({
    type: 'control',
    forward: true,
    command: 'unlock',
    params: {}
}));
```

**预期结果**：
- ESP32 收到消息：`{"type": "control", "command": "unlock", "params": {}}`
- 注意：消息中不包含 `forward` 字段

---

### 测试 7：停止监控模式测试

**目标**：验证可以退出监控模式

**前提**：已完成测试 2（处于监控模式）

**步骤**：
1. 点击"停止监控模式"按钮
2. 观察日志

**预期结果**：
- 日志显示"发送停止监控模式命令"
- 日志显示"系统命令执行成功: stop_monitor"
- ESP32 收到 `{"type": "system", "command": "stop_monitor"}` 消息

---

### 测试 8：多 App 连接测试

**目标**：验证多个 App 可以同时连接同一设备

**步骤**：
1. 打开第一个 App Demo 并连接
2. 在另一个浏览器标签页打开第二个 App Demo
3. 使用相同的 device_id 连接
4. 在第一个 App 中启动监控模式
5. ESP32 发送视频数据

**预期结果**：
- 两个 App 都能成功连接
- 两个 App 都能收到视频数据
- 视频帧数同步增加

---

## 常见问题

### Q1: 连接失败
**原因**：
- 服务器未启动
- 服务器地址错误
- ESP32 设备不在线

**解决**：
- 检查服务器是否运行在 `http://localhost:8000`
- 确认 device_id 正确
- 确保 ESP32 已连接到 `/ws/xiaozhi` 端点

### Q2: 认证失败
**原因**：
- device_id 对应的 ESP32 不在线

**解决**：
- 先连接 ESP32 设备
- 确认 device_id 匹配

### Q3: 看不到视频
**原因**：
- 未启动监控模式
- ESP32 未发送视频数据
- 视频数据格式错误

**解决**：
- 确保已点击"启动监控模式"
- 检查 ESP32 是否正在发送视频
- 验证 BinaryProtocol2 格式是否正确

### Q4: 对讲功能不工作
**原因**：
- 浏览器不支持 MediaRecorder API
- 未授予麦克风权限
- 未启动监控模式

**解决**：
- 使用 Chrome/Edge/Firefox 等现代浏览器
- 允许浏览器访问麦克风
- 先启动监控模式

---

## 性能指标

正常情况下应该达到：

- **连接延迟**：< 100ms
- **视频帧率**：10-30 FPS
- **音频延迟**：< 200ms
- **数据传输**：稳定无丢包

---

## 下一步

测试通过后，可以：

1. 开发真实的移动 App（Android/iOS）
2. 优化视频编码和传输
3. 添加人脸识别功能
4. 实现录像存储
5. 添加推送通知
