# ESP32 永久连接测试指南

## 测试目的

验证禁用超时机制后，ESP32 设备可以保持永久在线状态，不会因为无活动而被服务器断开。

## 测试环境

- 服务器：xiaozhi-server（已禁用超时机制）
- 客户端：ESP32 设备或测试工具
- 网络：稳定的局域网或互联网连接

## 测试场景

### 场景 1：长时间无活动连接

**目的：** 验证连接在无任何活动的情况下不会被超时断开

**步骤：**

1. ESP32 连接服务器

   ```
   WebSocket: ws://server_ip:8000/ws
   Headers: device-id: test_device_001
   ```

2. 发送 hello 消息

   ```json
   {
     "type": "hello",
     "audio_params": {
       "format": "opus",
       "sample_rate": 16000,
       "channels": 1
     }
   }
   ```

3. 收到服务器响应后，保持连接但不发送任何消息

4. 等待时间：
   - 原超时时间：3 分钟（180 秒）
   - 测试等待：5 分钟（300 秒）

**预期结果：**

- ✅ 连接保持活跃，不会断开
- ✅ 服务器日志中无超时相关日志
- ✅ ConnectionManager 中设备仍然在线

**验证方法：**

```bash
# 查看服务器日志
tail -f main/xiaozhi-server/tmp/server.log | grep -E "超时|timeout|断开|disconnect"

# 应该看不到超时相关日志
```

### 场景 2：间歇性活动

**目的：** 验证间歇性发送消息时连接保持稳定

**步骤：**

1. ESP32 连接服务器并发送 hello
2. 每隔 5 分钟发送一次心跳消息
   ```json
   {
     "type": "heartbeat",
     "ts": 1705564800000,
     "uptime": 300
   }
   ```
3. 持续测试 30 分钟

**预期结果：**

- ✅ 连接始终保持
- ✅ 每次心跳都收到响应
- ✅ 无异常断开

### 场景 3：多设备长连接

**目的：** 验证多个设备同时保持长连接

**步骤：**

1. 同时连接 5 个 ESP32 设备（或模拟）
2. 每个设备保持连接但不发送消息
3. 等待 10 分钟

**预期结果：**

- ✅ 所有设备连接保持
- ✅ 服务器资源占用正常
- ✅ 无内存泄漏

**监控命令：**

```bash
# 监控服务器资源
top -p $(pgrep -f "python.*app.py")

# 查看连接数
netstat -an | grep :8000 | grep ESTABLISHED | wc -l
```

### 场景 4：网络波动恢复

**目的：** 验证网络短暂中断后的重连机制

**步骤：**

1. ESP32 连接服务器
2. 模拟网络中断（拔网线或禁用网卡）10 秒
3. 恢复网络
4. ESP32 尝试重连

**预期结果：**

- ✅ 服务器检测到连接断开
- ✅ ESP32 能够成功重连
- ✅ 重连后功能正常

**服务器日志：**

```
[INFO] 客户端断开连接
[INFO] ESP32 连接已注销: test_device_001, 原因: connection_lost
[INFO] ESP32 连接已注册: test_device_001
```

## 测试工具

### 使用 Python 测试脚本

```python
#!/usr/bin/env python3
"""ESP32 长连接测试脚本"""

import asyncio
import websockets
import json
import time

async def test_long_connection():
    uri = "ws://localhost:8000/ws"
    headers = {"device-id": "test_device_001"}

    print("🔌 连接服务器...")
    async with websockets.connect(uri, extra_headers=headers) as ws:
        # 发送 hello
        hello_msg = {
            "type": "hello",
            "audio_params": {
                "format": "opus",
                "sample_rate": 16000,
                "channels": 1
            }
        }
        await ws.send(json.dumps(hello_msg))
        response = await ws.recv()
        print(f"✅ 收到响应: {response[:100]}...")

        # 保持连接
        print(f"⏳ 保持连接 5 分钟，不发送任何消息...")
        start_time = time.time()

        try:
            # 设置超时为 6 分钟（超过原超时时间）
            await asyncio.wait_for(ws.recv(), timeout=360)
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            print(f"✅ 测试通过！连接保持了 {elapsed:.1f} 秒")
            print(f"   原超时时间为 180 秒，已超过")
        except websockets.exceptions.ConnectionClosed:
            elapsed = time.time() - start_time
            print(f"❌ 测试失败！连接在 {elapsed:.1f} 秒后断开")
            print(f"   可能超时机制未正确禁用")

if __name__ == "__main__":
    asyncio.run(test_long_connection())
```

**运行测试：**

```bash
python docs/my_docs/test_long_connection.py
```

### 使用 WebSocket 测试页面

打开 `main/xiaozhi-server/test/test_page.html`，修改连接参数：

```javascript
// 修改 device-id
const deviceId = "test_device_001";

// 连接后不发送任何消息，观察连接状态
// 等待 5 分钟，检查是否仍然连接
```

## 监控指标

### 服务器端监控

**1. 连接状态**

```python
# 在 Python 控制台中
from core.connection_manager import ConnectionManager

manager = ConnectionManager.get_instance()
print(f"在线设备数: {len(manager.esp32_connections)}")
print(f"设备列表: {list(manager.esp32_connections.keys())}")
```

**2. 日志监控**

```bash
# 实时查看日志
tail -f main/xiaozhi-server/tmp/server.log

# 过滤关键信息
tail -f main/xiaozhi-server/tmp/server.log | grep -E "连接|断开|超时|注册|注销"
```

**3. 资源监控**

```bash
# CPU 和内存使用
ps aux | grep "python.*app.py"

# 网络连接数
netstat -an | grep :8000 | grep ESTABLISHED
```

### ESP32 端监控

**建议在 ESP32 端实现：**

```cpp
// 连接状态监控
unsigned long last_server_response = 0;
const unsigned long RESPONSE_TIMEOUT = 60000; // 60 秒

void checkConnectionHealth() {
    if (millis() - last_server_response > RESPONSE_TIMEOUT) {
        Serial.println("⚠️ 警告：超过 60 秒未收到服务器响应");
        // 可选：发送心跳测试连接
        sendHeartbeat();
    }
}

void onWebSocketMessage(String msg) {
    last_server_response = millis();
    // 处理消息...
}
```

## 问题排查

### 问题 1：连接仍然被断开

**可能原因：**

1. 修改未生效，需要重启服务器
2. 代码修改不完整
3. WebSocket 底层超时（TCP keepalive）

**排查步骤：**

```bash
# 1. 检查代码修改
grep -n "self.timeout_task = None" main/xiaozhi-server/core/connection.py

# 2. 检查进程
ps aux | grep "python.*app.py"

# 3. 重启服务器
pkill -f "python.*app.py"
python main/xiaozhi-server/app.py
```

### 问题 2：服务器资源占用过高

**可能原因：**

1. 僵尸连接未释放
2. 内存泄漏
3. 连接数过多

**排查步骤：**

```bash
# 查看连接数
netstat -an | grep :8000 | wc -l

# 查看内存使用
ps aux | grep "python.*app.py" | awk '{print $6}'

# 查看打开的文件描述符
lsof -p $(pgrep -f "python.*app.py") | wc -l
```

### 问题 3：ESP32 无法重连

**可能原因：**

1. 服务器端连接对象未清理
2. device_id 冲突
3. 网络问题

**排查步骤：**

```bash
# 查看服务器日志
tail -100 main/xiaozhi-server/tmp/server.log | grep "test_device_001"

# 检查 ConnectionManager 状态
# 在 Python 控制台中
from core.connection_manager import ConnectionManager
manager = ConnectionManager.get_instance()
print(manager.esp32_connections)
```

## 成功标准

测试通过的标准：

- ✅ 场景 1：连接保持超过 5 分钟无断开
- ✅ 场景 2：间歇性活动 30 分钟无异常
- ✅ 场景 3：多设备同时在线无问题
- ✅ 场景 4：网络恢复后能正常重连
- ✅ 服务器日志无超时相关错误
- ✅ 服务器资源占用正常
- ✅ 无内存泄漏

## 回退测试

如果需要验证回退是否成功：

1. 运行回退脚本

   ```bash
   bash docs/my_docs/restore-timeout-mechanism.sh
   ```

2. 重启服务器

3. 运行场景 1 测试

4. **预期结果：** 连接在 3 分钟后被超时断开

5. 查看日志应该包含：
   ```
   [INFO] 连接超时，准备关闭
   [INFO] ESP32 连接已注销: test_device_001, 原因: timeout
   ```

## 建议的生产环境配置

### 启用心跳机制

**ESP32 端：**

```cpp
// 每 30 秒发送一次心跳
void sendHeartbeat() {
    StaticJsonDocument<128> doc;
    doc["type"] = "heartbeat";
    doc["ts"] = millis();
    doc["uptime"] = millis() / 1000;

    String msg;
    serializeJson(doc, msg);
    webSocket.sendTXT(msg);
}

// 在主循环中
unsigned long lastHeartbeat = 0;
void loop() {
    if (millis() - lastHeartbeat > 30000) {
        sendHeartbeat();
        lastHeartbeat = millis();
    }
}
```

**服务器端：**

心跳处理器已实现（`core/handle/textHandler/heartbeatHandler.py`），无需修改。

### 监控告警

建议添加监控告警：

1. 连接数异常增长
2. 内存使用超过阈值
3. 长时间无心跳的连接

## 相关文档

- [禁用超时机制详细说明](./disable-timeout-mechanism.md)
- [CHANGELOG](./CHANGELOG.md)
- [ESP32 通信协议规范](./智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md)
