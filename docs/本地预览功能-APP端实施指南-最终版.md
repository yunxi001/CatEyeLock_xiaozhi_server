# 本地预览功能 - APP端实施指南（最终版）

## ✅ 确认：服务器端无需修改

**重要发现**：

- ✅ 服务器端已有完整的**消息转发机制**（`forward` 字段）
- ✅ 转发机制**正在使用中**，不是废弃功能
- ✅ `LocalPreviewHandler` 已实现，可处理 ESP32 响应
- ✅ **服务器端完全不需要任何修改**

**结论**：APP 端可以**立即开始实施**，无需等待服务器端开发。

---

## 文档信息

- **功能名称**：本地预览功能 APP 端控制
- **目标平台**：iOS / Android
- **实施方式**：使用现有的消息转发机制
- **创建日期**：2026-05-04
- **状态**：可立即实施

---

## 1. 功能概述

### 1.1 目标

通过 APP 远程控制 ESP32 的本地预览功能，允许用户在手机上启动/停止 ESP32 LCD 屏幕的摄像头画面显示。

### 1.2 工作原理

```
APP 发送消息（带 forward: true）
    ↓
服务器检测到 forward 字段
    ↓
服务器删除 forward 字段，转发到 ESP32
    ↓
ESP32 执行命令，返回响应（带 forward: true）
    ↓
服务器转发响应到 APP
    ↓
APP 更新 UI
```

### 1.3 优势

- ✅ **无需服务器端开发**（0 小时）
- ✅ **实时性高**（WebSocket 长连接）
- ✅ **实现简单**（利用现有机制）
- ✅ **可立即实施**（无依赖）

---

## 2. 消息格式

### 2.1 APP 发送控制消息

#### 启动本地预览

```json
{
  "forward": true,
  "type": "local_preview",
  "action": "start"
}
```

#### 停止本地预览

```json
{
  "forward": true,
  "type": "local_preview",
  "action": "stop"
}
```

**关键点**：

- `forward: true` 告诉服务器这是需要转发的消息
- 服务器会删除 `forward` 字段后转发到 ESP32
- ESP32 收到的消息：`{"type": "local_preview", "action": "start"}`

### 2.2 ESP32 响应消息

#### 成功响应

```json
{
  "type": "local_preview",
  "action": "start",
  "status": "success"
}
```

#### 失败响应

```json
{
  "type": "local_preview",
  "action": "start",
  "status": "error",
  "error": "Monitor mode active"
}
```

**说明**：

- ESP32 的响应会自动转发回 APP
- APP 监听 `type: "local_preview"` 的消息即可

### 2.3 错误码映射

| ESP32 错误信息            | 用户提示                             |
| ------------------------- | ------------------------------------ |
| `Camera not available`    | "摄像头暂时不可用"                   |
| `Monitor mode active`     | "监控模式正在运行，请先关闭监控模式" |
| `Face recognition active` | "人脸识别正在进行，请稍后再试"       |
| `System error`            | "系统错误，请稍后再试"               |
| 超时（10秒无响应）        | "操作超时，请稍后再试"               |

---

## 3. APP 端实施步骤

### 步骤 1：设计 UI 界面（2 小时）

#### 控制按钮设计

**位置**：

- 设备控制页面
- 与"监控模式"按钮并列显示

**按钮状态**：

| 状态   | 显示文字             | 颜色      | 可点击 |
| ------ | -------------------- | --------- | ------ |
| 未启动 | "打开本地预览"       | 灰色      | ✅     |
| 运行中 | "关闭本地预览"       | 蓝色/绿色 | ✅     |
| 加载中 | "处理中..."          | 灰色      | ❌     |
| 禁用   | "本地预览（不可用）" | 浅灰色    | ❌     |

**界面布局示例**：

```
┌─────────────────────────────┐
│  设备控制                    │
├─────────────────────────────┤
│                             │
│  [监控模式]  [本地预览]     │
│   (运行中)    (未启动)      │
│                             │
│  💡 提示：监控模式运行时，   │
│     无法启动本地预览         │
│                             │
└─────────────────────────────┘
```

#### 加载动画

- 点击按钮后显示转圈图标
- 禁用按钮，防止重复点击
- 显示文字："处理中..."

#### 提示消息

- 成功：Toast/Snackbar 显示"已打开本地预览"
- 失败：Toast/Snackbar 显示错误提示
- 超时：Toast/Snackbar 显示"操作超时，请稍后再试"

---

### 步骤 2：实现消息发送（2 小时）

#### 封装发送方法

**伪代码示意**：

```
function sendLocalPreviewCommand(action) {
    // 构建消息
    message = {
        "forward": true,
        "type": "local_preview",
        "action": action  // "start" 或 "stop"
    }

    // 发送到服务器
    websocket.send(JSON.stringify(message))

    // 显示加载状态
    showLoading()

    // 启动超时定时器（10秒）
    startTimeout(10000)
}
```

#### 按钮点击事件

**伪代码示意**：

```
function onLocalPreviewButtonClick() {
    // 判断当前状态
    if (localPreviewActive) {
        // 当前运行中，发送停止命令
        sendLocalPreviewCommand("stop")
    } else {
        // 当前未启动，发送启动命令
        sendLocalPreviewCommand("start")
    }

    // 禁用按钮
    disableButton()
}
```

---

### 步骤 3：实现响应处理（3 小时）

#### 监听 WebSocket 消息

**伪代码示意**：

```
function onWebSocketMessage(event) {
    // 解析消息
    message = JSON.parse(event.data)

    // 识别本地预览响应
    if (message.type === "local_preview") {
        handleLocalPreviewResponse(message)
    }
}
```

#### 处理响应

**伪代码示意**：

```
function handleLocalPreviewResponse(message) {
    // 取消超时定时器
    cancelTimeout()

    // 隐藏加载状态
    hideLoading()

    // 启用按钮
    enableButton()

    // 判断响应状态
    if (message.status === "success") {
        // 成功
        updateLocalPreviewState(message.action)
        showToast("已" + (message.action === "start" ? "打开" : "关闭") + "本地预览")
    } else {
        // 失败
        errorMessage = mapErrorMessage(message.error)
        showToast(errorMessage)
    }
}
```

#### 超时处理

**伪代码示意**：

```
function onTimeout() {
    // 隐藏加载状态
    hideLoading()

    // 启用按钮
    enableButton()

    // 显示超时提示
    showToast("操作超时，请稍后再试")
}
```

---

### 步骤 4：实现状态管理（2 小时）

#### 状态变量

```
localPreviewActive: boolean  // 本地预览是否运行中
isLoading: boolean           // 是否正在加载
lastError: string            // 最后一次错误信息
```

#### 状态更新

**伪代码示意**：

```
function updateLocalPreviewState(action) {
    if (action === "start") {
        localPreviewActive = true
    } else {
        localPreviewActive = false
    }

    // 更新 UI
    updateButtonUI()
}
```

#### UI 更新

**伪代码示意**：

```
function updateButtonUI() {
    if (isLoading) {
        button.text = "处理中..."
        button.color = "gray"
        button.enabled = false
    } else if (localPreviewActive) {
        button.text = "关闭本地预览"
        button.color = "blue"
        button.enabled = true
    } else {
        button.text = "打开本地预览"
        button.color = "gray"
        button.enabled = true
    }
}
```

---

### 步骤 5：实现互斥逻辑（2 小时）

#### 与监控模式互斥

**方案1：APP 端预检查（推荐）**

**伪代码示意**：

```
function onLocalPreviewButtonClick() {
    // 检查监控模式是否运行
    if (monitorModeActive) {
        showToast("监控模式正在运行，请先关闭监控模式")
        return
    }

    // 发送命令
    sendLocalPreviewCommand(...)
}
```

**方案2：依赖服务器端检查**

**伪代码示意**：

```
function handleLocalPreviewResponse(message) {
    if (message.error === "Monitor mode active") {
        showToast("监控模式正在运行，请先关闭监控模式")
    }
}
```

**推荐**：方案1（提升用户体验，减少无效请求）

#### 按钮禁用逻辑

**伪代码示意**：

```
function updateButtonState() {
    if (monitorModeActive) {
        // 监控模式运行时，禁用本地预览按钮
        localPreviewButton.enabled = false
        localPreviewButton.text = "本地预览（监控模式运行中）"
    } else if (deviceOffline) {
        // 设备离线时，禁用按钮
        localPreviewButton.enabled = false
        localPreviewButton.text = "本地预览（设备离线）"
    } else {
        // 正常状态
        localPreviewButton.enabled = true
        updateButtonUI()
    }
}
```

---

### 步骤 6：实现状态同步（2 小时）

#### 监听状态变化

**场景**：

- 其他用户通过 APP 改变状态
- 用户通过语音命令改变状态
- ESP32 自动停止

**实现方式**：

- 监听所有 `type: "local_preview"` 的消息
- 不仅是自己发送的请求的响应
- 也包括其他来源触发的状态变化

**伪代码示意**：

```
function onWebSocketMessage(event) {
    message = JSON.parse(event.data)

    // 监听所有本地预览消息
    if (message.type === "local_preview") {
        // 更新状态（无论是谁触发的）
        if (message.status === "success") {
            updateLocalPreviewState(message.action)
        }
    }
}
```

---

### 步骤 7：测试验证（3 小时）

#### 功能测试

**测试场景**：

1. **正常启动和停止**
   - 点击"打开本地预览"
   - 验证：ESP32 启动本地预览，APP 显示"已打开本地预览"
   - 点击"关闭本地预览"
   - 验证：ESP32 停止本地预览，APP 显示"已关闭本地预览"

2. **互斥冲突**
   - 启动监控模式
   - 点击"打开本地预览"
   - 验证：显示"监控模式正在运行，请先关闭监控模式"

3. **设备离线**
   - 断开 ESP32 连接
   - 验证：按钮禁用，显示"设备离线"

4. **超时处理**
   - 模拟 ESP32 无响应
   - 验证：10 秒后显示"操作超时"

5. **状态同步**
   - 用户 A 通过 APP 启动本地预览
   - 验证：用户 B 的 APP 自动更新状态

6. **语音命令同步**
   - 用户通过语音启动本地预览
   - 验证：APP 自动更新状态

#### UI 测试

- 按钮样式正确显示
- 加载动画正常显示
- Toast/Snackbar 提示正确显示
- 不同屏幕尺寸适配

#### 性能测试

- 消息发送延迟：< 500ms
- UI 更新延迟：< 500ms
- 状态同步延迟：< 1 秒

---

## 4. 开发时间估算

| 任务         | 预计时间    |
| ------------ | ----------- |
| 设计 UI 界面 | 2 小时      |
| 实现消息发送 | 2 小时      |
| 实现响应处理 | 3 小时      |
| 实现状态管理 | 2 小时      |
| 实现互斥逻辑 | 2 小时      |
| 实现状态同步 | 2 小时      |
| 测试验证     | 3 小时      |
| **总计**     | **16 小时** |

---

## 5. 验收标准

### 5.1 功能验收

- ✅ 用户可以通过 APP 启动本地预览
- ✅ 用户可以通过 APP 停止本地预览
- ✅ 按钮状态正确显示（未启动、运行中、禁用）
- ✅ 互斥逻辑正确（与监控模式互斥）
- ✅ 错误提示准确友好
- ✅ 状态实时同步

### 5.2 性能验收

- ✅ 消息发送延迟 < 500ms
- ✅ UI 更新流畅，无卡顿
- ✅ 状态同步延迟 < 1 秒

### 5.3 用户体验验收

- ✅ 操作流程简单直观
- ✅ 加载状态清晰可见
- ✅ 错误提示友好易懂
- ✅ 无明显 Bug

---

## 6. 技术要点

### 6.1 消息转发机制

**服务器端实现**（已存在，无需修改）：

```python
# 检测 forward 字段
if msg_json.get("forward") == True:
    # 删除 forward 字段
    del msg_json["forward"]

    # 判断来源并转发
    if conn.client_type == "app":
        # App → ESP32
        await esp32_conn.websocket.send(json.dumps(msg_json))
    else:
        # ESP32 → App
        for app_conn in app_conns:
            await app_conn.websocket.send(json.dumps(msg_json))
```

**关键点**：

- ✅ 服务器自动处理转发
- ✅ APP 只需添加 `"forward": true` 字段
- ✅ 无需额外开发

### 6.2 响应匹配

**问题**：如何知道哪个响应对应哪个请求？

**解决方案**：基于消息类型和时间窗口

**实现逻辑**：

1. 发送请求后，记录请求类型和时间
2. 监听所有 `type: "local_preview"` 的消息
3. 10 秒内收到的响应视为对应的响应
4. 超过 10 秒视为超时

**注意**：

- 假设同一时间只有一个本地预览请求
- 如果需要支持并发请求，需要添加请求 ID（需要服务器端支持）

### 6.3 状态同步

**实时同步方式**：

- 监听所有 `type: "local_preview"` 的消息
- 不仅是自己发送的请求的响应
- 也包括其他来源触发的状态变化

**同步场景**：

- 其他用户通过 APP 改变状态
- 用户通过语音命令改变状态
- ESP32 自动停止

---

## 7. 注意事项

### 7.1 依赖关系

**APP 端依赖**：

- ✅ WebSocket 连接（已有）
- ✅ 消息转发机制（已有）
- ✅ 设备 ID（已有）

**服务器端依赖**：

- ✅ 消息转发机制（已有）
- ✅ `LocalPreviewHandler`（已有）
- ✅ 消息类型注册（已有）

**结论**：所有依赖都已满足，可立即实施。

### 7.2 兼容性

**向后兼容**：

- 旧版本 APP 不支持本地预览功能时，隐藏按钮
- 检查服务器端版本（可选）

**协议版本**：

- 确保服务器端已升级到支持本地预览的版本
- 检查 ESP32 固件版本

### 7.3 安全性

**权限验证**：

- 服务器端会验证 WebSocket 连接的身份
- APP 端无需额外验证

**数据加密**：

- 使用 WSS（WebSocket Secure）传输数据
- 敏感信息加密存储

---

## 8. 常见问题

### Q1: 如何知道响应对应哪个请求？

**A**: 基于消息类型和时间窗口匹配。假设同一时间只有一个本地预览请求，10 秒内收到的 `type: "local_preview"` 响应视为对应的响应。

### Q2: 如果同时有多个用户操作怎么办？

**A**: 当前实现假设同一时间只有一个请求。如果需要支持并发，需要添加请求 ID（需要服务器端支持）。

### Q3: 如何同步其他用户的操作？

**A**: 监听所有 `type: "local_preview"` 的消息，不仅是自己发送的请求的响应，也包括其他来源触发的状态变化。

### Q4: 服务器端真的不需要修改吗？

**A**: 是的，完全不需要。转发机制已经实现，`LocalPreviewHandler` 已经实现，消息类型已经注册。

---

## 9. 参考文档

- **功能说明**：`docs/本地预览功能-服务器端与APP端配合说明.md`
- **服务器端实施报告**：`docs/本地预览功能-服务器端实施完成报告.md`
- **消息转发机制**：`main/xiaozhi-server/core/handle/textMessageProcessor.py`
- **通信协议**：`docs/my_docs/智能猫眼门锁系统-服务器与App通信协议规范-v2.5.md`

---

## 10. 总结

### 10.1 核心优势

- ✅ **服务器端无需修改**（0 小时开发）
- ✅ **利用现有机制**（消息转发）
- ✅ **实时性高**（WebSocket 长连接）
- ✅ **可立即实施**（无依赖）

### 10.2 实施路径

1. **设计 UI**（2 小时）
2. **实现消息发送**（2 小时）
3. **实现响应处理**（3 小时）
4. **实现状态管理**（2 小时）
5. **实现互斥逻辑**（2 小时）
6. **实现状态同步**（2 小时）
7. **测试验证**（3 小时）

**总计**：16 小时

### 10.3 关键消息格式

**APP 发送**：

```json
{
  "forward": true,
  "type": "local_preview",
  "action": "start"
}
```

**ESP32 响应**：

```json
{
  "type": "local_preview",
  "action": "start",
  "status": "success"
}
```

---

**文档维护者**：毕业设计项目组  
**最后更新**：2026-05-04  
**状态**：可立即实施 ✅
