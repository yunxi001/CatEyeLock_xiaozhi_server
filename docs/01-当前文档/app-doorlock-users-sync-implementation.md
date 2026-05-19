# App 门锁用户数据同步实现报告

## 问题背景

### 现象

App 查询 `doorlock_users` 时返回空数据（count=0, total=0），但查询成功无报错。

### 根本原因

**功能缺失**：ESP32 上报用户管理结果时，服务器只转发给 App，从未保存到数据库。

- `userMgmtResultHandler.py` 只负责转发，不保存数据
- `database.py` 已有 `save_doorlock_user()` 等方法，但从未被调用
- `doorlock_users` 表为空是正常的，因为没有数据写入

## 解决方案

### 设计思路

**双向数据流**：

1. **App → ESP32**：App 发送用户管理命令（`user_mgmt`）
2. **ESP32 → 服务器**：ESP32 上报操作结果（`user_mgmt_result`）
3. **服务器 → 数据库**：服务器保存结果到 `doorlock_users` 表（**新增**）
4. **服务器 → App**：服务器转发结果给 App（已有）

### 实现方案

#### 1. 缓存用户管理命令（`commandProxyHandler.py`）

**目的**：保存 App 提供的 `user_name` 等参数，供后续数据库保存使用。

**修改位置**：`UserMgmtProxyHandler._forward_to_esp32()`

**实现**：

```python
# 缓存用户管理命令信息（用于后续保存到数据库）
category = msg_json.get("category")
command = msg_json.get("command")
if command in ["add", "del", "clear"]:
    esp32_conn.last_user_mgmt_cmd = {
        "ts": int(time.time() * 1000),
        "category": category,
        "command": command,
        "user_name": msg_json.get("user_name"),  # App 可能提供
        "user_id": msg_json.get("user_id"),      # App 可能提供
        "seq_id": seq_id
    }
```

#### 2. 保存到数据库（`userMgmtResultHandler.py`）

**修改内容**：

1. **导入数据库获取函数**：

   ```python
   from core.handle.textHandler.queryHandler import _get_base_database
   ```

2. **在 `handle()` 中调用保存逻辑**：

   ```python
   if result:
       conn.logger.bind(tag=TAG).info(
           f"用户管理成功: {category}/{command}, val={val}"
       )

       # 保存到数据库
       await self._save_to_database(conn, msg_json)
   ```

3. **新增 `_save_to_database()` 方法**：

| category | command | 操作                                                    |
| -------- | ------- | ------------------------------------------------------- |
| `finger` | `add`   | 调用 `save_doorlock_user()` 创建用户，更新 `finger_ids` |
| `nfc`    | `add`   | 调用 `save_doorlock_user()` 创建用户，更新 `nfc_ids`    |
| `finger` | `del`   | 从 `finger_ids` 中移除对应 ID                           |
| `nfc`    | `del`   | 从 `nfc_ids` 中移除对应 ID                              |
| `finger` | `clear` | 清空所有用户的 `finger_ids`                             |
| `nfc`    | `clear` | 清空所有用户的 `nfc_ids`                                |

**关键逻辑**：

```python
# 指纹添加
if category == "finger" and command == "add":
    finger_id = val  # ESP32 返回的指纹 ID
    db.save_doorlock_user(
        device_id=conn.device_id,
        user_id=finger_id,  # 使用 finger_id 作为 user_id
        name=user_name or f"指纹用户{finger_id}",
        role="member"
    )
    db.update_doorlock_user_finger(
        device_id=conn.device_id,
        user_id=finger_id,
        finger_ids=[finger_id]
    )
```

## 技术细节

### 用户 ID 映射

**问题**：ESP32 返回的 `val` 是硬件 ID（0-99），如何映射到 `doorlock_users.user_id`？

**方案**：直接使用硬件 ID 作为 `user_id`

- 指纹用户：`user_id = finger_id`
- NFC 用户：`user_id = nfc_id`
- 优点：简单直接，无需额外映射表
- 缺点：不同类型用户可能有相同 `user_id`（通过 `device_id` 区分）

### 用户名称处理

**来源**：

1. **优先**：从缓存的 App 命令中获取 `user_name`
2. **默认**：使用 `"指纹用户{ID}"` 或 `"NFC用户{ID}"`

**示例**：

```python
user_name = last_cmd.get("user_name") if last_cmd else None
name = user_name or f"指纹用户{finger_id}"
```

### 删除和清空操作

**删除（del）**：

1. 查询设备所有用户
2. 遍历找到包含该 ID 的用户
3. 从 `finger_ids`/`nfc_ids` 列表中移除
4. 更新数据库

**清空（clear）**：

1. 查询设备所有用户
2. 将所有用户的 `finger_ids`/`nfc_ids` 设为空列表
3. 批量更新数据库

## 数据库表结构

### `doorlock_users` 表

| 字段              | 类型        | 说明                 |
| ----------------- | ----------- | -------------------- |
| `id`              | BIGINT      | 自增主键             |
| `device_id`       | VARCHAR(64) | 设备 ID              |
| `user_id`         | INT         | 用户 ID（硬件 ID）   |
| `name`            | VARCHAR(64) | 用户名称             |
| `role`            | VARCHAR(16) | 角色（member/admin） |
| `finger_ids`      | JSON        | 指纹 ID 列表         |
| `nfc_ids`         | JSON        | NFC ID 列表          |
| `face_registered` | TINYINT     | 是否注册人脸         |
| `created_at`      | DATETIME    | 创建时间             |
| `updated_at`      | DATETIME    | 更新时间             |

**唯一约束**：`(device_id, user_id)`

## 测试场景

### 场景 1：添加指纹用户

**操作**：

1. App 发送 `user_mgmt` 命令：

   ```json
   {
     "type": "user_mgmt",
     "category": "finger",
     "command": "add",
     "user_name": "张三",
     "seq_id": "1778416936294_0"
   }
   ```

2. ESP32 返回成功：
   ```json
   {
     "type": "user_mgmt_result",
     "category": "finger",
     "command": "add",
     "result": true,
     "val": 6
   }
   ```

**预期结果**：

- 数据库插入记录：`device_id=xxx, user_id=6, name="张三", finger_ids=[6]`
- App 收到转发的结果消息
- 日志显示：`已保存指纹用户到数据库: device_id=xxx, finger_id=6, name=张三`

### 场景 2：查询门锁用户

**操作**：

```json
{
  "type": "query",
  "target": "doorlock_users",
  "data": {
    "limit": 100,
    "offset": 0,
    "user_type": "finger"
  }
}
```

**预期结果**：

```json
{
  "type": "query_result",
  "target": "doorlock_users",
  "data": {
    "users": [
      {
        "user_id": 6,
        "name": "张三",
        "role": "member",
        "finger_ids": [6],
        "nfc_ids": null,
        "face_registered": 0
      }
    ],
    "count": 1,
    "total": 1
  }
}
```

### 场景 3：删除指纹

**操作**：

1. App 发送删除命令：

   ```json
   {
     "type": "user_mgmt",
     "category": "finger",
     "command": "del",
     "user_id": 6
   }
   ```

2. ESP32 返回成功：
   ```json
   {
     "type": "user_mgmt_result",
     "category": "finger",
     "command": "del",
     "result": true,
     "val": 6
   }
   ```

**预期结果**：

- 数据库更新：`user_id=6` 的 `finger_ids` 变为 `[]`
- 日志显示：`已从用户 6 移除指纹 ID 6`

## 修改文件清单

| 文件                                               | 修改内容                                                     |
| -------------------------------------------------- | ------------------------------------------------------------ |
| `core/handle/textHandler/commandProxyHandler.py`   | 在 `UserMgmtProxyHandler._forward_to_esp32()` 中缓存命令信息 |
| `core/handle/textHandler/userMgmtResultHandler.py` | 导入 `_get_base_database`，新增 `_save_to_database()` 方法   |

## 注意事项

1. **异步操作**：数据库保存失败不影响转发给 App（已捕获异常）
2. **数据一致性**：ESP32 是真实数据源，数据库只是镜像
3. **用户名称**：如果 App 不提供 `user_name`，使用默认名称
4. **并发安全**：`save_doorlock_user()` 使用 `ON DUPLICATE KEY UPDATE`，支持并发

## 后续优化

1. **用户 ID 映射**：考虑引入独立的 `user_id` 生成策略
2. **批量操作**：`clear` 命令可优化为单条 SQL 更新
3. **事务支持**：添加和更新操作可包装在事务中
4. **审计日志**：记录用户管理操作历史

---

**修改日期**：2026-05-10  
**修改人**：Kiro AI Assistant  
**状态**：已实施
