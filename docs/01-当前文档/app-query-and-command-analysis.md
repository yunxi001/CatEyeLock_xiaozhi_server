# App 查询和命令功能分析

## 问题回答

### Q1: `get_events` 和 `get_unlock_logs` 方法是做什么的？

这两个方法是 **P2 按需查询接口**，用于 App 主动查询历史数据。

#### `get_events()` - 查询设备事件历史

**用途**: 查询设备的各种事件记录

**支持的事件类型**:

- `pir` - 人体红外感应事件
- `door_open` - 门打开事件
- `door_close` - 门关闭事件
- `alarm` - 报警事件
- `low_battery` - 低电量事件

**查询参数**:

```json
{
  "type": "query",
  "target": "events",
  "data": {
    "event_type": "pir", // 可选，过滤特定类型
    "limit": 20, // 返回条数，默认100，最大500
    "offset": 0 // 偏移量，用于分页
  }
}
```

**返回数据**:

```json
{
  "type": "query_result",
  "target": "events",
  "status": "success",
  "data": {
    "records": [
      {
        "id": 1,
        "event_type": "pir",
        "param": 1,
        "created_at": "2026-05-09T19:00:00"
      }
    ],
    "total": 100,
    "limit": 20,
    "offset": 0
  }
}
```

**使用场景**:

- App 查看设备的活动历史
- 分析门的开关频率
- 查看 PIR 触发记录
- 监控报警事件

---

#### `get_unlock_logs()` - 查询开锁日志

**用途**: 查询设备的开锁历史记录（比推送的 5 条更多）

**查询参数**:

```json
{
  "type": "query",
  "target": "unlock_logs",
  "data": {
    "method": "password", // 可选，过滤开锁方式
    "result": 1, // 可选，过滤结果（1=成功，0=失败）
    "limit": 20, // 返回条数
    "offset": 0 // 偏移量
  }
}
```

**返回数据**:

```json
{
  "type": "query_result",
  "target": "unlock_logs",
  "status": "success",
  "data": {
    "records": [
      {
        "id": 1,
        "method": "password",
        "user_id": 1,
        "status": "success",
        "fail_count": 0,
        "lock_time": 0,
        "created_at": "2026-05-09T19:00:00"
      }
    ],
    "total": 50,
    "limit": 20,
    "offset": 0
  }
}
```

**使用场景**:

- App 查看完整的开锁历史（推送只有最近 5 条）
- 按开锁方式过滤（密码、指纹、NFC、人脸、远程）
- 查看失败的开锁尝试
- 分析开锁模式和频率

---

### Q2: 密码、NFC、指纹、人员列表查询是否需要设备在线？

让我详细分析每个操作：

## 操作类型分类

### 🟢 不需要设备在线的操作（从服务器数据库查询）

#### 1. 密码查询 ✅

```json
{
  "type": "query",
  "target": "password"
}
```

**实现方式**:

- ✅ 从服务器数据库 `device_info` 表查询
- ✅ 不需要设备在线
- ✅ 立即返回结果

**代码逻辑**:

```python
async def _query_password(self, conn, data: Dict):
    db = _get_database(conn)
    password = db.get_device_password(conn.device_id)
    # 从数据库返回，不需要设备在线
```

**日志中的表现**:

```
260509 19:32:21 [commandProxyHandler]-INFO-收到 App 用户管理命令: category=password, command=query
```

- ⚠️ 日志显示这个请求被 `commandProxyHandler` 处理
- ⚠️ 但代码中已经改为通过 `query` 接口处理
- ⚠️ 说明 App 使用了旧的 `user_mgmt` 协议

**问题**: App 使用了错误的接口！应该使用：

```json
// ✅ 正确方式
{"type": "query", "target": "password"}

// ❌ 错误方式（旧协议）
{"type": "user_mgmt", "category": "password", "command": "query"}
```

---

#### 2. 人员列表查询 ✅

```json
{
  "type": "face_management",
  "action": "get_persons"
}
```

**实现方式**:

- ✅ 从服务器数据库 `persons` 表查询
- ✅ 不需要设备在线
- ✅ 立即返回结果

**日志中的表现**:

```
260509 19:32:42 [faceRecognitionHandler]-ERROR-获取人员列表失败: Person.__init__() got an unexpected keyword argument 'photo_path'
```

- ❌ 查询失败，但不是因为设备离线
- ❌ 是因为 `Person` 模型参数错误

---

#### 3. 其他数据库查询 ✅

- ✅ 设备状态历史 (`status_history`)
- ✅ 事件历史 (`events`)
- ✅ 开锁日志 (`unlock_logs`)
- ✅ 媒体文件列表 (`media_files`)
- ✅ 访客意图历史 (`visitor_intents`)
- ✅ 快递警报历史 (`package_alerts`)

**共同特点**: 都从服务器数据库查询，不需要设备在线

---

### 🔴 需要设备在线的操作（需要转发到 ESP32）

#### 1. NFC 卡查询 ❌

```json
{
  "type": "user_mgmt",
  "category": "nfc",
  "command": "query"
}
```

**实现方式**:

- ❌ 需要转发到 ESP32 设备
- ❌ ESP32 从本地存储读取 NFC 卡信息
- ❌ 设备离线时无法查询

**代码逻辑**:

```python
async def handle(self, conn, msg_json: Dict[str, Any]):
    # 检查 ESP32 是否在线
    esp32_conn = manager.get_esp32_conn(conn.device_id)

    if not esp32_conn or not esp32_conn.websocket:
        await self._send_error(conn, "设备离线", code=ErrorCode.DEVICE_OFFLINE)
        return  # ← 设备离线直接返回错误

    # 转发给 ESP32
    await self._forward_to_esp32(conn, esp32_conn, msg_json)
```

**日志中的表现**:

```
260509 19:32:32 [commandProxyHandler]-INFO-收到 App 用户管理命令: category=nfc, command=query
```

- ⚠️ 日志只显示收到命令，没有显示错误
- ⚠️ 说明代码**没有返回设备离线错误**！

---

#### 2. 指纹查询 ❌

```json
{
  "type": "user_mgmt",
  "category": "finger",
  "command": "query"
}
```

**实现方式**:

- ❌ 需要转发到 ESP32 设备
- ❌ ESP32 从指纹模块读取信息
- ❌ 设备离线时无法查询

**日志中的表现**:

```
260509 19:32:39 [commandProxyHandler]-INFO-收到 App 用户管理命令: category=finger, command=query
```

- ⚠️ 同样没有显示设备离线错误

---

#### 3. 其他需要设备在线的操作

- ❌ 远程开锁 (`lock_control` - `unlock`)
- ❌ 远程关锁 (`lock_control` - `lock`)
- ❌ 设置临时密码 (`lock_control` - `temp_code`)
- ❌ 蜂鸣器控制 (`dev_control` - `beep`)
- ❌ 补光灯控制 (`dev_control` - `light`)
- ❌ OLED 显示控制 (`dev_control` - `oled`)
- ❌ 指纹添加/删除 (`user_mgmt` - `finger`)
- ❌ NFC 卡添加/删除 (`user_mgmt` - `nfc`)
- ❌ 密码设置/修改 (`user_mgmt` - `password`)

---

## 问题分析

### 🐛 Bug 1: 设备离线时没有返回错误

**问题**: 从日志看，NFC 和指纹查询时设备离线，但没有看到错误响应

**原因分析**:

查看代码，`UserMgmtProxyHandler` 确实有设备离线检查：

```python
if not esp32_conn or not esp32_conn.websocket:
    await self._send_error(conn, "设备离线", code=ErrorCode.DEVICE_OFFLINE)
    return
```

**可能的原因**:

1. ✅ 代码逻辑正确，应该返回错误
2. ⚠️ 日志中没有显示错误，可能是：
   - 错误响应已发送，但日志级别不够（只记录了 INFO）
   - App 收到了错误，但没有显示
   - 日志被截断了

**验证方法**: 查看完整日志或添加更详细的日志

---

### 🐛 Bug 2: 密码查询使用了错误的接口

**问题**: App 使用 `user_mgmt` 查询密码，但代码已改为 `query` 接口

**代码中的处理**:

```python
# 密码查询已改为通过 query 接口，不再转发到 ESP32
if category == "password" and command == "query":
    await self._send_error(
        conn,
        "密码查询请使用 query 接口（target=password），不再支持通过 user_mgmt 查询",
        code=ErrorCode.PARAM_ERROR
    )
    return
```

**说明**:

- ✅ 服务器正确拒绝了旧协议
- ⚠️ App 需要更新，使用新的 `query` 接口

---

## 总结表格

| 操作                     | 接口类型          | 需要设备在线 | 数据来源     | 离线时行为        |
| ------------------------ | ----------------- | ------------ | ------------ | ----------------- |
| **查询类（不需要在线）** |
| 密码查询                 | `query`           | ❌ 否        | 服务器数据库 | ✅ 返回数据       |
| 人员列表                 | `face_management` | ❌ 否        | 服务器数据库 | ✅ 返回数据       |
| 设备状态历史             | `query`           | ❌ 否        | 服务器数据库 | ✅ 返回数据       |
| 事件历史                 | `query`           | ❌ 否        | 服务器数据库 | ✅ 返回数据       |
| 开锁日志                 | `query`           | ❌ 否        | 服务器数据库 | ✅ 返回数据       |
| 媒体文件                 | `query`           | ❌ 否        | 服务器数据库 | ✅ 返回数据       |
| 访客意图                 | `query`           | ❌ 否        | 服务器数据库 | ✅ 返回数据       |
| 快递警报                 | `query`           | ❌ 否        | 服务器数据库 | ✅ 返回数据       |
| **控制类（需要在线）**   |
| NFC 卡查询               | `user_mgmt`       | ✅ 是        | ESP32 设备   | ❌ 返回"设备离线" |
| 指纹查询                 | `user_mgmt`       | ✅ 是        | ESP32 设备   | ❌ 返回"设备离线" |
| 远程开锁                 | `lock_control`    | ✅ 是        | ESP32 设备   | ❌ 返回"设备离线" |
| 设备控制                 | `dev_control`     | ✅ 是        | ESP32 设备   | ❌ 返回"设备离线" |
| 用户管理                 | `user_mgmt`       | ✅ 是        | ESP32 设备   | ❌ 返回"设备离线" |

---

## 设计原则

### 为什么有些操作需要设备在线？

#### 1. 数据存储位置不同

**服务器存储**（不需要在线）:

- 历史记录（状态、事件、日志）
- 人员信息（姓名、关系、人脸特征）
- 媒体文件元数据
- 设备密码（加密存储）

**设备存储**（需要在线）:

- 指纹模板（存储在指纹模块中）
- NFC 卡 ID（存储在设备 Flash 中）
- 实时状态（传感器数据）
- 设备配置（OLED、蜂鸣器等）

#### 2. 安全性考虑

**敏感操作必须设备在线**:

- 远程开锁 - 需要设备确认执行
- 添加/删除指纹 - 需要设备配合
- 添加/删除 NFC - 需要设备写入
- 修改密码 - 需要设备同步

**只读操作可以离线**:

- 查看历史记录 - 服务器已有数据
- 查看人员列表 - 服务器已有数据
- 查看密码 - 服务器已有备份

#### 3. 性能优化

**频繁查询的数据存储在服务器**:

- 避免频繁唤醒设备
- 减少设备功耗
- 提高查询速度
- 支持离线查看

---

## 改进建议

### 1. 统一错误响应 ✅

**当前问题**: 设备离线时，不同接口的错误响应不一致

**建议**: 统一使用错误码

```json
{
  "type": "xxx_result",
  "status": "error",
  "code": 1, // ErrorCode.DEVICE_OFFLINE
  "message": "设备离线，无法执行此操作"
}
```

---

### 2. 增强日志记录 ✅

**当前问题**: 日志中看不到错误响应

**建议**: 添加错误响应日志

```python
async def _send_error(self, conn, message: str, code: int):
    conn.logger.bind(tag=TAG).warning(
        f"返回错误响应: code={code}, message={message}, device_online=False"
    )
    await conn.websocket.send(...)
```

---

### 3. App 协议更新 ✅

**当前问题**: App 使用旧的 `user_mgmt` 查询密码

**建议**: 更新 App，使用新的 `query` 接口

```javascript
// ❌ 旧方式
{
  type: "user_mgmt",
  category: "password",
  command: "query"
}

// ✅ 新方式
{
  type: "query",
  target: "password"
}
```

---

### 4. 添加缺失的数据库方法 ✅

**当前问题**: `get_events()` 和 `get_unlock_logs()` 方法不存在

**建议**: 在 `DoorlockDatabase` 中添加这些方法

```python
def get_events(self, device_id: str, event_type: str = None,
               limit: int = 100, offset: int = 0) -> Tuple[List[dict], int]:
    """查询设备事件历史"""
    # 实现查询逻辑
    pass

def get_unlock_logs(self, device_id: str, method: str = None,
                    result: int = None, limit: int = 100,
                    offset: int = 0) -> Tuple[List[dict], int]:
    """查询开锁日志"""
    # 实现查询逻辑
    pass
```

---

## 结论

### ✅ 正确的设计

1. **查询历史数据不需要设备在线** - 从服务器数据库读取
2. **控制设备必须设备在线** - 需要设备执行操作
3. **查询设备本地数据需要设备在线** - 数据存储在设备中

### ⚠️ 需要改进的地方

1. **日志中没有显示设备离线错误** - 需要增强日志
2. **App 使用了错误的密码查询接口** - 需要更新 App
3. **缺少 `get_events` 和 `get_unlock_logs` 方法** - 需要补充实现

### 📊 功能完整性

- **推送功能**: 80% 完成（到访记录 SQL 已修复）
- **查询功能**: 60% 完成（缺少 2 个方法）
- **控制功能**: 100% 完成（设备离线检查正常）
- **错误处理**: 90% 完成（需要增强日志）

**总体评价**: 架构设计合理，功能基本完整，需要补充缺失的方法和增强日志。
