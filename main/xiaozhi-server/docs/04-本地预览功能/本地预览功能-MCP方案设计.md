# 本地预览功能 - MCP 方案设计

## 文档信息

- **功能名称**：本地预览功能（Local Preview Mode）
- **实现方式**：ESP32 端 MCP 工具
- **设计日期**：2026-05-05
- **状态**：📋 设计中

---

## 1. 方案概述

### 1.1 设计理念

将本地预览功能作为 **ESP32 端 MCP 工具** 实现，而不是服务器端插件。这样：

- ✅ **自动发现**：ESP32 连接时自动注册工具
- ✅ **无需配置**：服务器端无需修改配置文件
- ✅ **架构清晰**：设备功能由设备端实现
- ✅ **易于扩展**：新增设备功能只需修改 ESP32 代码

### 1.2 工作流程

```
用户语音："打开监控模式"
    ↓
ASR 识别："打开监控模式"
    ↓
LLM 意图识别 → 调用 MCP 工具：self_screen_show_camera
    ↓
服务器发送 MCP 调用请求到 ESP32
    ↓
ESP32 执行本地预览功能
    ↓
ESP32 返回执行结果
    ↓
服务器生成语音反馈："已打开本地预览"
```

---

## 2. MCP 工具定义

### 2.1 工具名称

```
self.screen.show_camera
```

**命名规范**：

- `self`：表示设备自身
- `screen`：表示屏幕相关功能
- `show_camera`：显示摄像头画面

### 2.2 工具描述（JSON Schema）

```json
{
  "name": "self.screen.show_camera",
  "description": "Display the camera preview on the device screen in real-time. This allows viewing the camera feed directly on the ESP32's LCD screen without sending video to the server. Use this tool when the user wants to see what the camera is capturing on the device screen. Common trigger phrases: '显示监控画面', '打开监控模式', '打开本地预览', '让我看看门口', '屏幕显示摄像头', '打开屏幕', '显示摄像头', '开启实时预览'. To stop: '关闭监控画面', '关闭监控模式', '关闭本地预览', '关闭屏幕'.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "action": {
        "type": "string",
        "enum": ["start", "stop"],
        "description": "Action to perform: 'start' to enable camera preview, 'stop' to disable camera preview"
      }
    },
    "required": ["action"]
  }
}
```

### 2.3 描述优化要点

1. **明确功能**：说明是在设备屏幕上显示，不是发送到服务器
2. **丰富触发词**：列出常见的用户表达方式
3. **中英文结合**：描述用英文，触发词用中文
4. **区分场景**：明确与拍照功能的区别

---

## 3. ESP32 端实现

### 3.1 工具注册（在 MCP 初始化时）

```cpp
// 在 ESP32 的 MCP 工具列表中添加
void registerMCPTools() {
    // ... 其他工具 ...

    // 本地预览工具
    JsonObject showCamera = tools.createNestedObject();
    showCamera["name"] = "self.screen.show_camera";
    showCamera["description"] = "Display the camera preview on the device screen in real-time. This allows viewing the camera feed directly on the ESP32's LCD screen without sending video to the server. Use this tool when the user wants to see what the camera is capturing on the device screen. Common trigger phrases: '显示监控画面', '打开监控模式', '打开本地预览', '让我看看门口', '屏幕显示摄像头', '打开屏幕', '显示摄像头', '开启实时预览'. To stop: '关闭监控画面', '关闭监控模式', '关闭本地预览', '关闭屏幕'.";

    JsonObject showCameraSchema = showCamera.createNestedObject("inputSchema");
    showCameraSchema["type"] = "object";

    JsonObject showCameraProps = showCameraSchema.createNestedObject("properties");
    JsonObject actionProp = showCameraProps.createNestedObject("action");
    actionProp["type"] = "string";
    JsonArray actionEnum = actionProp.createNestedArray("enum");
    actionEnum.add("start");
    actionEnum.add("stop");
    actionProp["description"] = "Action to perform: 'start' to enable camera preview, 'stop' to disable camera preview";

    JsonArray showCameraRequired = showCameraSchema.createNestedArray("required");
    showCameraRequired.add("action");
}
```

### 3.2 工具调用处理

```cpp
// 在 MCP 工具调用处理函数中添加
void handleMCPToolCall(const char* toolName, JsonObject arguments) {
    if (strcmp(toolName, "self.screen.show_camera") == 0) {
        handleShowCamera(arguments);
        return;
    }

    // ... 其他工具处理 ...
}

void handleShowCamera(JsonObject arguments) {
    const char* action = arguments["action"];

    if (strcmp(action, "start") == 0) {
        // 启动本地预览
        bool success = startLocalPreview();

        if (success) {
            sendMCPResponse(true, "Local preview started");
        } else {
            // 检查失败原因
            if (isMonitorModeActive()) {
                sendMCPResponse(false, "Monitor mode is active");
            } else if (isFaceRecognitionActive()) {
                sendMCPResponse(false, "Face recognition is active");
            } else if (!isCameraAvailable()) {
                sendMCPResponse(false, "Camera not available");
            } else {
                sendMCPResponse(false, "System error");
            }
        }
    }
    else if (strcmp(action, "stop") == 0) {
        // 停止本地预览
        bool success = stopLocalPreview();

        if (success) {
            sendMCPResponse(true, "Local preview stopped");
        } else {
            sendMCPResponse(false, "Failed to stop local preview");
        }
    }
    else {
        sendMCPResponse(false, "Invalid action");
    }
}
```

### 3.3 MCP 响应格式

```cpp
void sendMCPResponse(bool success, const char* message) {
    JsonDocument doc;
    doc["type"] = "mcp";

    JsonObject payload = doc.createNestedObject("payload");
    payload["jsonrpc"] = "2.0";
    payload["id"] = currentMCPCallId;  // 保存的调用ID

    JsonObject result = payload.createNestedObject("result");
    JsonArray content = result.createNestedArray("content");
    JsonObject contentItem = content.createNestedObject();
    contentItem["type"] = "text";

    // 构建返回的 JSON 字符串
    JsonDocument resultDoc;
    resultDoc["success"] = success;
    resultDoc["message"] = message;

    String resultStr;
    serializeJson(resultDoc, resultStr);
    contentItem["text"] = resultStr;

    result["isError"] = !success;

    // 发送到服务器
    String output;
    serializeJson(doc, output);
    webSocket.sendTXT(output);
}
```

### 3.4 本地预览功能实现

```cpp
// 本地预览状态
bool localPreviewActive = false;

bool startLocalPreview() {
    // 1. 检查互斥条件
    if (isMonitorModeActive()) {
        Serial.println("Cannot start local preview: Monitor mode is active");
        return false;
    }

    if (isFaceRecognitionActive()) {
        Serial.println("Cannot start local preview: Face recognition is active");
        return false;
    }

    if (!isCameraAvailable()) {
        Serial.println("Cannot start local preview: Camera not available");
        return false;
    }

    // 2. 初始化摄像头（如果未初始化）
    if (!camera.isInitialized()) {
        if (!camera.init()) {
            Serial.println("Failed to initialize camera");
            return false;
        }
    }

    // 3. 启动预览循环
    localPreviewActive = true;

    // 4. 在主循环中持续刷新屏幕
    Serial.println("Local preview started");
    return true;
}

bool stopLocalPreview() {
    if (!localPreviewActive) {
        Serial.println("Local preview is not active");
        return false;
    }

    localPreviewActive = false;

    // 清空屏幕或显示默认界面
    screen.clear();
    screen.showDefaultUI();

    Serial.println("Local preview stopped");
    return true;
}

// 在主循环中
void loop() {
    // ... 其他逻辑 ...

    if (localPreviewActive) {
        // 获取摄像头帧
        camera_fb_t* fb = esp_camera_fb_get();
        if (fb) {
            // 显示到屏幕
            screen.drawImage(fb->buf, fb->len);

            // 释放帧缓冲
            esp_camera_fb_return(fb);
        }
    }

    // ... 其他逻辑 ...
}
```

---

## 4. 服务器端处理

### 4.1 无需修改

服务器端**完全不需要修改**！MCP 工具会自动：

1. **注册**：ESP32 连接时自动注册到工具列表
2. **调用**：LLM 识别意图后自动调用
3. **响应**：服务器自动处理 MCP 响应并生成语音反馈

### 4.2 服务器日志示例

```
[core.providers.tools.device_mcp.mcp_handler]-INFO-客户端设备支持的工具数量: 6
[core.providers.tools.unified_tool_handler]-INFO-当前支持的函数列表: [
    'play_music',
    'handle_exit_intent',
    'get_weather',
    'self_get_device_status',
    'self_audio_speaker_set_volume',
    'self_screen_set_brightness',
    'self_screen_set_theme',
    'self_camera_take_photo',
    'self_screen_show_camera'  ← 新增的工具
]
```

### 4.3 调用流程日志

```
[core.connection]-INFO-大模型收到用户消息: 打开监控模式
[core.providers.tools.unified_tool_manager]-INFO-执行工具: self_screen_show_camera，参数: {'action': 'start'}
[core.providers.tools.device_mcp.mcp_handler]-INFO-发送客户端mcp工具调用请求: self.screen.show_camera，参数: {"action": "start"}
[core.providers.tools.device_mcp.mcp_handler]-INFO-客户端mcp工具调用 self.screen.show_camera 成功，原始结果: {'content': [{'type': 'text', 'text': '{"success":true,"message":"Local preview started"}'}], 'isError': False}
[core.handle.sendAudioHandle]-INFO-发送音频消息: 已打开本地预览
```

---

## 5. 错误处理

### 5.1 错误码定义

| 错误消息                     | 说明           | 用户反馈                             |
| ---------------------------- | -------------- | ------------------------------------ |
| `Camera not available`       | 摄像头不可用   | "摄像头暂时不可用"                   |
| `Monitor mode is active`     | 监控模式运行中 | "监控模式正在运行，无法启动本地预览" |
| `Face recognition is active` | 人脸识别运行中 | "人脸识别正在进行，请稍后再试"       |
| `System error`               | 系统错误       | "系统错误，请稍后再试"               |
| `Invalid action`             | 无效的操作     | "操作失败，参数错误"                 |

### 5.2 服务器端错误处理

服务器端的 `device_mcp/mcp_handler.py` 已经实现了通用的错误处理：

```python
# 解析 MCP 响应
result_text = content[0]["text"]
result_json = json.loads(result_text)

if result_json.get("success"):
    # 成功
    return result_json.get("message", "操作成功")
else:
    # 失败
    error_msg = result_json.get("message", "未知错误")
    # 可以在这里映射到中文错误消息
    return translate_error_message(error_msg)
```

---

## 6. 测试计划

### 6.1 单元测试

**ESP32 端测试**：

1. **工具注册测试**
   - 验证工具是否正确注册到 MCP 工具列表
   - 验证工具描述和参数定义是否正确

2. **功能测试**
   - 测试启动本地预览
   - 测试停止本地预览
   - 测试重复启动/停止

3. **互斥测试**
   - 监控模式运行时启动本地预览（应失败）
   - 人脸识别运行时启动本地预览（应失败）
   - 摄像头不可用时启动本地预览（应失败）

### 6.2 集成测试

**端到端测试**：

1. **语音触发测试**

   ```
   用户："打开监控模式"
   预期：ESP32 屏幕显示摄像头画面，语音反馈"已打开本地预览"
   ```

2. **停止测试**

   ```
   用户："关闭监控模式"
   预期：ESP32 屏幕恢复默认界面，语音反馈"已关闭本地预览"
   ```

3. **错误场景测试**
   ```
   场景：监控模式运行中
   用户："打开本地预览"
   预期：语音反馈"监控模式正在运行，无法启动本地预览"
   ```

### 6.3 性能测试

1. **响应时间**
   - 从语音输入到屏幕显示的总时间 < 3 秒

2. **帧率**
   - 本地预览帧率 ≥ 10 FPS

3. **资源占用**
   - CPU 占用 < 80%
   - 内存占用 < 200KB

---

## 7. 迁移步骤

### 7.1 清理服务器端插件（可选）

如果之前实现了服务器端插件，可以清理：

```bash
# 删除插件文件
rm main/xiaozhi-server/plugins_func/functions/control_local_preview.py

# 删除响应处理器
rm main/xiaozhi-server/core/handle/textHandler/localPreviewHandler.py

# 从配置中移除（如果添加了）
# 编辑 config.yaml，从 functions 列表中删除 control_local_preview
```

### 7.2 ESP32 端实现

1. **添加 MCP 工具定义**
   - 在工具注册函数中添加 `self.screen.show_camera`

2. **实现工具处理函数**
   - 实现 `handleShowCamera()` 函数
   - 实现 `startLocalPreview()` 和 `stopLocalPreview()` 函数

3. **更新主循环**
   - 在 `loop()` 中添加本地预览刷新逻辑

4. **编译上传**
   - 编译固件
   - 上传到 ESP32

### 7.3 测试验证

1. **重启 ESP32**
   - 连接到服务器

2. **查看服务器日志**
   - 确认新工具已注册
   - 确认工具列表包含 `self_screen_show_camera`

3. **语音测试**
   - 说"打开监控模式"
   - 验证屏幕显示摄像头画面
   - 说"关闭监控模式"
   - 验证屏幕恢复正常

---

## 8. 优势总结

### 8.1 与服务器端插件对比

| 特性       | 服务器端插件            | ESP32 端 MCP 工具      |
| ---------- | ----------------------- | ---------------------- |
| 配置复杂度 | ❌ 需要修改 config.yaml | ✅ 无需配置            |
| 自动发现   | ❌ 需要手动配置         | ✅ 自动注册            |
| 扩展性     | ❌ 每次新增需修改服务器 | ✅ 只需修改 ESP32      |
| 架构清晰度 | ❌ 设备功能在服务器实现 | ✅ 设备功能在设备实现  |
| 维护成本   | ❌ 需要同步维护两端     | ✅ 只需维护 ESP32      |
| 部署复杂度 | ❌ 需要重启服务器       | ✅ 只需更新 ESP32 固件 |

### 8.2 核心优势

1. **零配置**：ESP32 连接即可使用，无需修改服务器配置
2. **自动发现**：LLM 自动识别新工具，无需训练
3. **解耦合**：服务器和设备职责清晰，互不干扰
4. **易扩展**：新增设备功能只需修改 ESP32 代码
5. **易维护**：功能实现在设备端，逻辑集中

---

## 9. 后续优化

### 9.1 功能增强

1. **参数扩展**

   ```json
   {
     "action": "start",
     "resolution": "640x480", // 分辨率
     "fps": 15, // 帧率
     "duration": 60 // 自动停止时间（秒）
   }
   ```

2. **状态查询**
   - 添加 `self.screen.get_preview_status` 工具
   - 返回当前预览状态、分辨率、帧率等

3. **截图功能**
   - 在预览模式下支持截图
   - 保存到本地或上传到服务器

### 9.2 性能优化

1. **帧率自适应**
   - 根据 CPU 负载动态调整帧率

2. **分辨率优化**
   - 根据屏幕尺寸选择最佳分辨率

3. **内存优化**
   - 使用双缓冲减少闪烁
   - 优化图像解码算法

---

## 10. 参考资料

### 10.1 相关文档

- **MCP 协议规范**：`docs/my_docs/智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md`
- **MCP 工具示例**：ESP32 现有的 5 个 MCP 工具实现
- **服务器端 MCP 处理**：`main/xiaozhi-server/core/providers/tools/device_mcp/mcp_handler.py`

### 10.2 代码参考

- **ESP32 MCP 工具注册**：ESP32 固件中的 `registerMCPTools()` 函数
- **ESP32 MCP 工具调用**：ESP32 固件中的 `handleMCPToolCall()` 函数
- **服务器端 MCP 调用**：`call_mcp_tool()` 函数

---

## 11. 总结

**MCP 方案是实现本地预览功能的最佳选择**：

- ✅ **架构合理**：设备功能由设备实现
- ✅ **零配置**：自动发现，无需手动配置
- ✅ **易扩展**：新增功能只需修改 ESP32
- ✅ **易维护**：逻辑集中，职责清晰

**实施建议**：

1. 优先实现 MCP 方案
2. 删除或废弃服务器端插件方案
3. 将其他类似功能也迁移到 MCP 实现

---

**文档维护者**：毕业设计项目组  
**设计日期**：2026-05-05  
**状态**：📋 设计完成，待实施
