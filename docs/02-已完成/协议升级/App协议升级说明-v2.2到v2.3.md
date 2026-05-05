# App 协议升级说明 - v2.2 到 v2.3

## 1. 升级概述

**升级时间**：2024-12-11  
**升级原因**：与 ESP32 协议 v5.2 保持一致，修复协议文档与代码实现的不一致问题

---

## 2. 主要变更

### 2.1 统一错误码（高优先级）

**变更内容**：
- ESP32 ack 错误码从 0-7 扩展到 0-10
- 与 ESP32 协议 v5.2 保持一致

**影响范围**：
- 第 7.6 节：ESP32 ACK 响应

**新增错误码**：
- 8: 未认证（权限不足）
- 9: 重复消息（消息已处理过）
- 10: 内部错误（设备内部错误）

**App 端适配**：
- 更新错误码处理逻辑，支持 0-10 范围
- 添加新增错误码的提示文案

---

### 2.2 更新 log_report 字段（高优先级）

**变更内容**：
- 将 `result` + `fail_count` 字段改为 `status` + `lock_time`
- 提供更精确的开锁状态信息

**旧格式（v2.2）**：
```json
{
    "type": "log_report",
    "ts": 1702234567890,
    "data": {
        "method": "finger",
        "uid": 5,
        "result": true,
        "fail_count": 0
    }
}
```

**新格式（v2.3）**：
```json
{
    "type": "log_report",
    "ts": 1702234567890,
    "data": {
        "method": "finger",
        "uid": 5,
        "status": 0,
        "lock_time": 1702234567890
    }
}
```

**字段映射**：
- `result: true` → `status: 0`（成功）
- `result: false` → `status: 1`（失败）或 `status: 2`（超时）
- `fail_count` → 移除（不再使用）
- 新增 `lock_time`：开锁时间戳（毫秒）

**App 端适配**：
- 更新 log_report 解析逻辑
- 使用 `status` 字段判断开锁结果
- 使用 `lock_time` 显示精确的开锁时间

---

### 2.3 新增消息类型（中优先级）

#### 2.3.1 door_opened_report（门已开启通知）

**消息格式**：
```json
{
    "type": "door_opened_report",
    "ts": 1702234567890,
    "data": {
        "method": "remote",
        "uid": 0,
        "duration": 5
    }
}
```

**用途**：
- ESP32 检测到门已开启时上报
- 可用于确认远程开锁是否成功

**App 端适配**：
- 添加 door_opened_report 消息处理
- 显示"门已开启"通知

#### 2.3.2 password_report（密码上报）

**消息格式**：
```json
{
    "type": "password_report",
    "ts": 1702234567890,
    "data": {
        "code": "123456",
        "expires": 3600,
        "status": "active"
    }
}
```

**用途**：
- ESP32 上报密码信息（如临时密码生成结果）
- 可用于显示临时密码

**App 端适配**：
- 添加 password_report 消息处理
- 显示临时密码和有效期

---

### 2.4 新增事件类型（中优先级）

**变更内容**：
- event_report 新增 3 个事件类型

**新增事件**：

| event | 说明 | param 含义 |
|-------|------|------------|
| `door_closed` | 门已关闭 | 无 |
| `lock_success` | 上锁成功 | 无 |
| `bolt_alarm` | 反锁报警 | 无 |

**App 端适配**：
- 更新 event_report 事件处理逻辑
- 添加新增事件的提示文案

---

### 2.5 明确 esp32_ack 不转发（文档说明）

**变更内容**：
- 明确说明 `esp32_ack`（ESP32 收到命令的即时确认）不会转发给 App
- 只有最终的 `ack`（命令执行结果）会转发

**影响**：
- App 端不会收到 esp32_ack 消息
- 只需要处理最终的 ack 响应

---

### 2.6 说明 ack 转发时的 ID 映射（文档说明）

**变更内容**：
- 明确说明 Server 转发 ack 时的 ID 处理机制

**ID 映射流程**：
1. App 发送命令时携带 `seq_id`（如 `app_1702234567890_001`）
2. Server 转发给 ESP32 时使用 `msg_id`（透传 seq_id）
3. ESP32 返回 ack 时携带 `msg_id`
4. Server 转发给 App 时保持原始 `seq_id`

**影响**：
- App 端可以使用 `seq_id` 匹配响应
- 无需处理 `msg_id` 字段

---

## 3. 兼容性说明

### 3.1 向后兼容性

| 变更 | 向后兼容 | 说明 |
|------|----------|------|
| 错误码扩展 | ✅ | 新增错误码不影响旧版本 |
| log_report 字段 | ❌ | 字段名变更，需要更新 |
| 新增消息类型 | ✅ | 旧版本可忽略 |
| 新增事件类型 | ✅ | 旧版本可忽略 |

### 3.2 升级建议

**必须升级**：
- log_report 字段解析逻辑（否则无法正确显示开锁日志）

**推荐升级**：
- 错误码处理逻辑（支持新增错误码）
- 新增消息类型处理（door_opened_report、password_report）
- 新增事件类型处理（door_closed、lock_success、bolt_alarm）

**可选升级**：
- 无

---

## 4. 升级检查清单

### 4.1 App 端代码修改

- [ ] 更新 log_report 解析逻辑（使用 status + lock_time）
- [ ] 更新错误码处理逻辑（支持 0-10）
- [ ] 添加 door_opened_report 消息处理
- [ ] 添加 password_report 消息处理
- [ ] 更新 event_report 事件处理（新增 3 个事件）
- [ ] 添加新增错误码的提示文案
- [ ] 添加新增事件的提示文案

### 4.2 测试验证

- [ ] 测试 log_report 显示是否正确
- [ ] 测试新增错误码是否正确显示
- [ ] 测试 door_opened_report 通知是否正常
- [ ] 测试 password_report 显示是否正确
- [ ] 测试新增事件是否正确显示
- [ ] 测试 ack 响应匹配是否正常

---

## 5. 示例代码

### 5.1 log_report 解析（旧版本）

```javascript
// v2.2 版本
function handleLogReport(data) {
    const { method, uid, result, fail_count } = data;
    
    if (result) {
        showNotification(`${method} 开锁成功，用户 ID: ${uid}`);
    } else {
        showNotification(`${method} 开锁失败，失败次数: ${fail_count}`);
    }
}
```

### 5.2 log_report 解析（新版本）

```javascript
// v2.3 版本
function handleLogReport(data) {
    const { method, uid, status, lock_time } = data;
    
    const statusText = {
        0: '成功',
        1: '失败',
        2: '超时'
    };
    
    const lockTimeStr = new Date(lock_time).toLocaleString();
    
    showNotification(
        `${method} 开锁${statusText[status]}，用户 ID: ${uid}，时间: ${lockTimeStr}`
    );
}
```

### 5.3 错误码处理（新版本）

```javascript
// v2.3 版本
function handleAck(data) {
    const { seq_id, code, msg } = data;
    
    const errorMessages = {
        0: '成功',
        1: '设备离线',
        2: '设备忙碌',
        3: '参数错误',
        4: '不支持',
        5: '超时',
        6: '硬件故障',
        7: '资源已满',
        8: '未认证',      // 新增
        9: '重复消息',    // 新增
        10: '内部错误'    // 新增
    };
    
    if (code === 0) {
        showSuccess(`命令执行成功: ${msg}`);
    } else {
        showError(`命令执行失败: ${errorMessages[code]} (${msg})`);
    }
}
```

### 5.4 新增消息处理

```javascript
// v2.3 版本
function handleMessage(message) {
    const { type, data } = message;
    
    switch (type) {
        case 'log_report':
            handleLogReport(data);
            break;
        
        case 'door_opened_report':
            // 新增
            showNotification(`门已开启，开锁方式: ${data.method}`);
            break;
        
        case 'password_report':
            // 新增
            showNotification(`临时密码: ${data.code}，有效期: ${data.expires}秒`);
            break;
        
        case 'event_report':
            handleEventReport(data);
            break;
        
        // ... 其他消息类型
    }
}

function handleEventReport(data) {
    const { event, param } = data;
    
    const eventMessages = {
        'bell': '门铃按下',
        'pir_trigger': `PIR 检测到人体，持续 ${param} 秒`,
        'tamper': `撬锁报警，级别 ${param}`,
        'door_open': `门未关超时 ${param} 分钟`,
        'door_closed': '门已关闭',        // 新增
        'lock_success': '上锁成功',       // 新增
        'bolt_alarm': '反锁报警',         // 新增
        'low_battery': `低电量警告 ${param}%`
    };
    
    showNotification(eventMessages[event] || `未知事件: ${event}`);
}
```

---

## 6. 常见问题

### Q1: 旧版本 App 能否继续使用？

**A**: 部分功能可以继续使用，但 log_report 显示会出错。建议尽快升级。

### Q2: 如何判断服务器是否已升级到 v2.3？

**A**: 检查 log_report 消息是否包含 `status` 字段（而不是 `result` 字段）。

### Q3: 新增的消息类型是否必须处理？

**A**: 不是必须的，但建议处理以提供更好的用户体验。

### Q4: 错误码扩展是否影响旧版本？

**A**: 不影响。旧版本可以忽略新增的错误码（8、9、10），但建议更新以提供更准确的错误提示。

---

**文档维护者**：毕业设计项目组  
**最后更新**：2024-12-11
