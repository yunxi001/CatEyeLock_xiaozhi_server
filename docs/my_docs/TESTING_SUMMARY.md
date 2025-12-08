# 智能门锁功能测试总结

## 已完成的修复

### 1. App 端命令功能 ✅
- **问题**：App 发送的系统命令（start_monitor、stop_monitor）无响应
- **原因**：AppConnectionHandler 没有调用消息处理器
- **修复**：导入并调用 handleTextMessage() 处理系统命令

### 2. 模式切换逻辑 ✅
- **问题**：尝试修改 App 连接的 current_mode，但应该修改 ESP32 的模式
- **原因**：没有区分 App 和 ESP32 连接类型
- **修复**：判断连接类型，正确切换 ESP32 的工作模式

### 3. 数据转发逻辑 ✅
- **正常模式**：ESP32 发送 version=1 原始音频 → 服务器送入 ASR
- **监控模式**：ESP32 发送 version=2 音视频 → 服务器**直接转发**给 App（不解析）
- **App 对讲**：App 发送原始 OPUS → 服务器**直接转发**给 ESP32

## 当前协议说明

### 正常模式

**ESP32 → 服务器**：
```
version=1: 原始 OPUS 音频数据（无头部）
→ 服务器送入 ASR 进行语音识别
```

### 监控模式

**ESP32 → 服务器 → App**：
```
version=2: BinaryProtocol2 格式（16字节头部 + 数据）
- 音频: type=0, reserved=0
- 视频: type=0, reserved=(width<<16)|height
→ 服务器直接转发给 App，不解析
→ App 负责解析并根据时间戳同步播放
```

**App → 服务器 → ESP32（对讲）**：
```
原始 OPUS 数据（和服务器发送给 ESP32 的格式一致）
→ 服务器直接转发给 ESP32，不解析
```

### 服务器 → ESP32（TTS 音频）

**普通 ESP32**：
```
原始 OPUS 数据（无头部）
```

**MQTT 网关**：
```
16字节头部 + OPUS 数据
```

## 测试步骤

### 1. 启动服务器
```bash
cd main/xiaozhi-server
python app.py
```

### 2. 连接 ESP32
确保 ESP32 已连接到服务器（device-id: AA:BB:CC:DD:EE:FF）

### 3. 打开 App Demo
在浏览器中打开 `main/xiaozhi-server/test/app_demo.html`

### 4. 测试流程

#### 4.1 基础连接测试
1. 填写服务器地址：`ws://localhost:8000/ws/app`
2. 填写设备 ID：`AA:BB:CC:DD:EE:FF`
3. 点击"连接服务器"
4. **预期**：认证成功，状态变为"已连接"

#### 4.2 系统命令测试
1. 点击"启动监控模式"
2. **预期**：
   - App 日志显示"系统命令执行成功: start_monitor"
   - 服务器日志显示"ESP32 AA:BB:CC:DD:EE:FF 监控模式已启动"
   - 无解析错误

#### 4.3 视频监控测试
1. ESP32 发送视频数据（version=2, type=0, reserved!=0）
2. **预期**：
   - App 显示实时视频画面
   - 视频帧数计数器增加
   - 服务器日志无错误

#### 4.4 音频对讲测试
1. 点击"开始对讲"
2. 允许麦克风权限
3. 说话
4. **预期**：
   - App 日志显示"发送音频数据"
   - ESP32 收到音频并播放
   - 服务器正确转发

## 常见问题

### Q1: 服务器报错 "解析BinaryProtocol2失败"
**原因**：ESP32 可能还在使用 version=1  
**解决**：确认 ESP32 已切换到 version=2

### Q2: App 命令无响应
**原因**：ESP32 未连接或 device_id 不匹配  
**解决**：
1. 检查 ESP32 是否在线
2. 确认 device_id 正确

### Q3: 视频无法显示
**原因**：未启动监控模式或 ESP32 未发送视频  
**解决**：
1. 确保已点击"启动监控模式"
2. 检查 ESP32 是否正在发送视频数据

### Q4: 对讲无声音
**原因**：音频格式不匹配  
**解决**：
1. 确认 App 发送的是原始 OPUS 数据
2. 检查 ESP32 是否支持接收的音频格式

## 下一步

如果所有测试通过：
1. ✅ 开始开发 ESP32 固件端的对应功能
2. ✅ 实现真实的移动 App（Android/iOS）
3. ✅ 添加更多功能（人脸识别、录像存储等）

## 文件清单

### 核心实现
- `main/xiaozhi-server/core/connection_manager.py` - 连接管理器
- `main/xiaozhi-server/core/app_connection.py` - App 连接处理
- `main/xiaozhi-server/core/connection.py` - ESP32 连接处理
- `main/xiaozhi-server/core/websocket_server.py` - WebSocket 服务器
- `main/xiaozhi-server/core/handle/textHandler/systemMessageHandler.py` - 系统命令处理

### 测试工具
- `main/xiaozhi-server/test/app_demo.html` - Web App Demo
- `main/xiaozhi-server/test/test_app_commands.py` - 命令测试脚本

### 文档
- `docs/my_docs/protocol-version-fix.md` - 协议修复说明
- `docs/my_docs/smart-doorlock-test-guide.md` - 详细测试指南
- `docs/my_docs/smart-doorlock-usage-guide.md` - 使用指南
