# 本地预览功能 - MCP 实施快速指南

## 快速开始

本指南帮助你快速实现基于 MCP 的本地预览功能。

---

## ESP32 端实现（核心代码）

### 1. 添加 MCP 工具定义

在 ESP32 的 MCP 工具注册函数中添加：

```cpp
// 在 tools/list 响应中添加
{
  "name": "self.screen.show_camera",
  "description": "Display the camera preview on the device screen in real-time. Use this when user wants to see camera view on screen. Trigger: '显示监控画面', '打开监控模式', '打开本地预览', '屏幕显示摄像头'. Stop: '关闭监控画面', '关闭本地预览'.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "action": {
        "type": "string",
        "enum": ["start", "stop"],
        "description": "start: enable preview, stop: disable preview"
      }
    },
    "required": ["action"]
  }
}
```

### 2. 实现工具处理函数

```cpp
// 全局变量
bool localPreviewActive = false;

// MCP 工具调用处理
void handleMCPToolCall(JsonObject payload) {
    const char* method = payload["method"];
    if (strcmp(method, "tools/call") != 0) return;

    JsonObject params = payload["params"];
    const char* toolName = params["name"];
    JsonObject arguments = params["arguments"];
    int callId = payload["id"];

    if (strcmp(toolName, "self.screen.show_camera") == 0) {
        handleShowCamera(arguments, callId);
    }
    // ... 其他工具处理 ...
}

void handleShowCamera(JsonObject arguments, int callId) {
    const char* action = arguments["action"];
    bool success = false;
    const char* message = "";

    if (strcmp(action, "start") == 0) {
        // 检查互斥条件
        if (isMonitorModeActive()) {
            message = "Monitor mode is active";
        } else if (isFaceRecognitionActive()) {
            message = "Face recognition is active";
        } else if (!isCameraAvailable()) {
            message = "Camera not available";
        } else {
            // 启动本地预览
            success = startLocalPreview();
            message = success ? "Local preview started" : "System error";
        }
    }
    else if (strcmp(action, "stop") == 0) {
        success = stopLocalPreview();
        message = success ? "Local preview stopped" : "Failed to stop";
    }

    // 发送响应
    sendMCPResponse(callId, success, message);
}

bool startLocalPreview() {
    if (localPreviewActive) return true;

    // 初始化摄像头
    if (!camera.isInitialized()) {
        if (!camera.init()) return false;
    }

    localPreviewActive = true;
    Serial.println("Local preview started");
    return true;
}

bool stopLocalPreview() {
    if (!localPreviewActive) return false;

    localPreviewActive = false;
    screen.clear();
    Serial.println("Local preview stopped");
    return true;
}

void sendMCPResponse(int callId, bool success, const char* message) {
    JsonDocument doc;
    doc["type"] = "mcp";

    JsonObject payload = doc.createNestedObject("payload");
    payload["jsonrpc"] = "2.0";
    payload["id"] = callId;

    JsonObject result = payload.createNestedObject("result");
    JsonArray content = result.createNestedArray("content");
    JsonObject item = content.createNestedObject();
    item["type"] = "text";

    // 构建返回 JSON
    String resultStr = "{\"success\":";
    resultStr += success ? "true" : "false";
    resultStr += ",\"message\":\"";
    resultStr += message;
    resultStr += "\"}";
    item["text"] = resultStr;

    result["isError"] = !success;

    String output;
    serializeJson(doc, output);
    webSocket.sendTXT(output);
}
```

### 3. 更新主循环

```cpp
void loop() {
    // ... 其他逻辑 ...

    // 本地预览刷新
    if (localPreviewActive) {
        camera_fb_t* fb = esp_camera_fb_get();
        if (fb) {
            screen.drawImage(fb->buf, fb->len);
            esp_camera_fb_return(fb);
        }
        delay(100);  // 控制帧率 ~10 FPS
    }

    // ... 其他逻辑 ...
}
```

---

## 服务器端（无需修改）

服务器端**完全不需要修改**！MCP 工具会自动注册和调用。

### 验证工具已注册

查看服务器启动日志：

```
[core.providers.tools.unified_tool_handler]-INFO-当前支持的函数列表: [
    ...,
    'self_screen_show_camera'  ← 应该看到这个
]
```

---

## 测试步骤

### 1. 编译上传 ESP32 固件

```bash
# 使用你的 ESP32 开发环境编译并上传
```

### 2. 重启 ESP32 并连接服务器

### 3. 查看服务器日志

确认工具已注册：

```
客户端设备支持的工具数量: 6
当前支持的函数列表: [..., 'self_screen_show_camera']
```

### 4. 语音测试

**测试 1：启动本地预览**

```
用户："打开监控模式"
预期：
  - ESP32 屏幕显示摄像头画面
  - 语音反馈："已打开本地预览"
```

**测试 2：停止本地预览**

```
用户："关闭监控模式"
预期：
  - ESP32 屏幕恢复正常
  - 语音反馈："已关闭本地预览"
```

**测试 3：错误场景**

```
场景：监控模式运行中
用户："打开本地预览"
预期：
  - 语音反馈："监控模式正在运行，无法启动本地预览"
```

---

## 常见问题

### Q1: 工具没有注册到服务器？

**检查**：

- ESP32 是否正确发送了 tools/list 响应
- 工具定义的 JSON 格式是否正确
- 服务器日志中是否有错误信息

### Q2: LLM 没有调用工具？

**检查**：

- 工具描述是否包含足够的触发词
- 用户的表达是否与触发词相似
- 服务器日志中 LLM 的意图识别结果

### Q3: 屏幕显示卡顿？

**优化**：

- 降低分辨率
- 降低帧率（增加 delay 时间）
- 优化图像解码算法

### Q4: 内存不足？

**优化**：

- 使用较小的帧缓冲
- 及时释放 camera_fb_t
- 检查内存泄漏

---

## 清理旧的服务器端插件（可选）

如果之前实现了服务器端插件，可以清理：

```bash
# 删除插件文件
rm main/xiaozhi-server/plugins_func/functions/control_local_preview.py

# 删除响应处理器
rm main/xiaozhi-server/core/handle/textHandler/localPreviewHandler.py

# 从 textMessageHandlerRegistry.py 中移除注册
# 从 textMessageType.py 中移除消息类型定义

# 从 config.yaml 中移除配置（如果添加了）
```

---

## 下一步

1. ✅ 实现基本的启动/停止功能
2. ⏳ 添加参数支持（分辨率、帧率）
3. ⏳ 添加状态查询工具
4. ⏳ 性能优化（帧率自适应）
5. ⏳ 添加截图功能

---

## 参考

- **完整设计文档**：`docs/本地预览功能-MCP方案设计.md`
- **MCP 协议规范**：`docs/my_docs/智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md`
- **现有 MCP 工具示例**：ESP32 固件中的其他 5 个工具

---

**祝实施顺利！** 🚀
