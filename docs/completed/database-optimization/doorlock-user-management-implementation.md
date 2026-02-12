# 门锁用户管理功能实现报告

> **实现日期**: 2026-01-30  
> **协议版本**: v2.4  
> **功能状态**: ✅ 已完成

## 1. 功能概述

实现了指纹、NFC、密码用户的元数据存储和查询功能，支持用户备注、创建者追踪、软删除等特性。

### 1.1 核心需求

- 将指纹/NFC 的元数据（用户备注、ID）存储到服务器数据库
- 支持查询和管理用户列表
- 记录操作来源（app_id）
- 支持软删除，保留历史记录

### 1.2 设计方案

采用统一用户表（`doorlock_users`）存储所有类型用户：

| 字段       | 类型         | 说明                                      |
| ---------- | ------------ | ----------------------------------------- |
| id         | BIGINT       | 自增主键                                  |
| device_id  | VARCHAR(64)  | 设备 MAC 地址                             |
| user_type  | VARCHAR(16)  | 用户类型：finger/nfc/password             |
| user_id    | INT          | ESP32 分配的用户 ID（指纹/NFC 的槽位 ID） |
| user_name  | VARCHAR(64)  | 用户备注名称                              |
| user_data  | VARCHAR(255) | 额外数据（如 NFC 卡号）                   |
| status     | TINYINT      | 状态：0=已删除，1=正常                    |
| created_at | DATETIME     | 创建时间                                  |
| updated_at | DATETIME     | 更新时间                                  |
| created_by | VARCHAR(64)  | 创建者 app_id                             |

## 2. 实现清单

### 2.1 数据库层 ✅

**文件**: `main/xiaozhi-server/core/providers/doorlock/database.py`

实现的方法：

1. **save_doorlock_user()** - 保存用户
   - 支持 INSERT 或 UPDATE（基于唯一键）
   - 记录 created_by（app_id）
   - 返回数据库记录 ID

2. **delete_doorlock_user()** - 删除用户（软删除）
   - 设置 status=0
   - 保留历史记录
   - 返回是否成功

3. **get_doorlock_user()** - 获取单个用户
   - 根据 device_id + user_type + user_id 查询
   - 只返回 status=1 的记录
   - 返回完整用户信息

4. **query_doorlock_users()** - 查询用户列表（带分页）
   - 支持按 user_type 过滤
   - 支持分页（limit/offset）
   - 返回记录列表和总数
   - 只返回 status=1 的记录

5. **clear_doorlock_users()** - 清空用户（软删除）
   - 批量设置 status=0
   - 按 user_type 清空
   - 返回影响行数

### 2.2 消息处理层 ✅

#### 2.2.1 用户管理命令代理

**文件**: `main/xiaozhi-server/core/handle/textHandler/commandProxyHandler.py`

**类**: `UserMgmtProxyHandler`

**修改内容**：

- 接收 App 发送的 `user_name` 参数
- 缓存到 ESP32 连接对象的 `_pending_user_names` 字典
- 转发给 ESP32 时移除 `user_name` 字段（ESP32 不需要）
- 使用 `seq_id` 作为缓存键

**代码示例**：

```python
# 缓存 user_name
if "user_name" in msg_json:
    user_name = msg_json["user_name"]
    if not hasattr(esp32_conn, "_pending_user_names"):
        esp32_conn._pending_user_names = {}
    esp32_conn._pending_user_names[seq_id] = {
        "user_name": user_name,
        "app_id": conn.app_id
    }

# 转发时移除 user_name
forward_msg = msg_json.copy()
forward_msg.pop("user_name", None)
```

#### 2.2.2 用户管理结果处理

**文件**: `main/xiaozhi-server/core/handle/textHandler/userMgmtResultHandler.py`

**类**: `UserMgmtResultHandler`

**修改内容**：

- 从缓存获取 `user_name` 和 `app_id`
- 根据操作类型（add/del/clear）更新数据库
- 记录详细日志

**处理逻辑**：

1. **add 命令成功**：
   - 从 ESP32 获取分配的 user_id
   - 从缓存获取 user_name 和 app_id
   - 调用 `save_doorlock_user()` 保存到数据库

2. **del 命令成功**：
   - 调用 `delete_doorlock_user()` 软删除

3. **clear 命令成功**：
   - 调用 `clear_doorlock_users()` 批量软删除

**代码示例**：

```python
if command == "add" and result:
    user_id = msg_json.get("val")
    db.save_doorlock_user(
        device_id=conn.device_id,
        user_type=category,
        user_id=user_id,
        user_name=user_name,
        created_by=app_id
    )
```

#### 2.2.3 查询处理

**文件**: `main/xiaozhi-server/core/handle/textHandler/queryHandler.py`

**类**: `QueryHandler`

**新增方法**: `_query_doorlock_users()`

**功能**：

- 支持按 `user_type` 过滤
- 支持分页查询（limit/offset）
- 返回完整的用户信息列表

**请求示例**：

```json
{
  "type": "query",
  "seq_id": "1702234567890_023",
  "target": "doorlock_users",
  "data": {
    "user_type": "finger",
    "limit": 100,
    "offset": 0
  }
}
```

**响应示例**：

```json
{
  "type": "query_result",
  "target": "doorlock_users",
  "status": "success",
  "data": {
    "records": [
      {
        "id": 1,
        "device_id": "AA:BB:CC:DD:EE:FF",
        "user_type": "finger",
        "user_id": 5,
        "user_name": "张三的右手食指",
        "status": 1,
        "created_at": "2024-12-11T10:30:00",
        "created_by": "user_12345"
      }
    ],
    "total": 1,
    "limit": 100,
    "offset": 0
  }
}
```

### 2.3 数据库迁移 ✅

#### 2.3.1 SQL 脚本

**文件**: `main/xiaozhi-server/migrations/add_doorlock_users_table.sql`

**内容**：

- 创建 `doorlock_users` 表
- 定义唯一键：`uk_device_type_userid (device_id, user_type, user_id)`
- 创建索引：device_id, user_type, status, created_at
- 包含验证查询

#### 2.3.2 执行脚本

**文件**: `main/xiaozhi-server/migrations/run_add_doorlock_users.py`

**功能**：

- 读取并执行 SQL 脚本
- 分割多条 SQL 语句
- 验证表创建是否成功
- 显示表结构
- 记录详细日志

**使用方法**：

```bash
cd main/xiaozhi-server
python migrations/run_add_doorlock_users.py
```

### 2.4 协议文档更新 ✅

**文件**: `docs/my_docs/智能猫眼门锁系统-服务器与App通信协议规范-v2.4.md`

**更新内容**：

1. **第 5.6 节 - 用户管理命令**：
   - 添加 `user_name` 字段说明
   - 标注为可选字段
   - 添加使用说明

2. **第 9.7 节 - 查询门锁用户列表**（新增）：
   - 完整的请求/响应格式
   - 参数说明
   - 字段说明
   - 使用说明

3. **第 17 节 - 版本历史**：
   - 记录 v2.4 版本变更
   - 说明新增功能

## 3. 数据流程

### 3.1 添加用户流程

```
App                    Server                   ESP32
 │                        │                        │
 │── user_mgmt ──────────►│                        │
 │   (user_name="张三")   │                        │
 │                        │ 缓存 user_name         │
 │                        │                        │
 │                        │── user_mgmt ──────────►│
 │                        │   (无 user_name)       │
 │                        │                        │
 │                        │◄── user_mgmt_result ──│
 │                        │   (val=5, result=true) │
 │                        │                        │
 │                        │ 保存到数据库:          │
 │                        │ - device_id            │
 │                        │ - user_type=finger     │
 │                        │ - user_id=5            │
 │                        │ - user_name="张三"     │
 │                        │ - created_by=app_id    │
 │                        │                        │
 │◄── user_mgmt_result ──│ (转发给 App)           │
 │                        │                        │
```

### 3.2 查询用户流程

```
App                    Server
 │                        │
 │── query ──────────────►│
 │   (target=doorlock_    │
 │    users)               │
 │                        │ 从数据库查询
 │                        │ WHERE status=1
 │                        │
 │◄── query_result ──────│
 │   (records=[...])      │
 │                        │
```

### 3.3 删除用户流程

```
App                    Server                   ESP32
 │                        │                        │
 │── user_mgmt ──────────►│                        │
 │   (command=del)        │                        │
 │                        │                        │
 │                        │── user_mgmt ──────────►│
 │                        │                        │
 │                        │◄── user_mgmt_result ──│
 │                        │   (result=true)        │
 │                        │                        │
 │                        │ 软删除数据库记录:      │
 │                        │ UPDATE status=0        │
 │                        │                        │
 │◄── user_mgmt_result ──│ (转发给 App)           │
 │                        │                        │
```

## 4. 测试建议

### 4.1 数据库测试

```sql
-- 1. 验证表创建
DESCRIBE doorlock_users;

-- 2. 测试插入
INSERT INTO doorlock_users
(device_id, user_type, user_id, user_name, created_by)
VALUES
('AA:BB:CC:DD:EE:FF', 'finger', 1, '测试用户', 'test_app');

-- 3. 测试查询
SELECT * FROM doorlock_users
WHERE device_id = 'AA:BB:CC:DD:EE:FF'
  AND status = 1;

-- 4. 测试软删除
UPDATE doorlock_users
SET status = 0
WHERE device_id = 'AA:BB:CC:DD:EE:FF'
  AND user_type = 'finger'
  AND user_id = 1;

-- 5. 验证软删除
SELECT * FROM doorlock_users
WHERE device_id = 'AA:BB:CC:DD:EE:FF';
```

### 4.2 接口测试

#### 测试 1: 添加指纹用户

**App 发送**：

```json
{
  "type": "user_mgmt",
  "seq_id": "1702234567890_001",
  "category": "finger",
  "command": "add",
  "user_id": 0,
  "user_name": "张三的右手食指"
}
```

**预期结果**：

1. Server 缓存 user_name
2. ESP32 收到不含 user_name 的命令
3. ESP32 返回 user_id=5
4. Server 保存到数据库
5. App 收到成功响应

#### 测试 2: 查询用户列表

**App 发送**：

```json
{
  "type": "query",
  "seq_id": "1702234567890_002",
  "target": "doorlock_users",
  "data": {
    "user_type": "finger"
  }
}
```

**预期结果**：

```json
{
  "type": "query_result",
  "target": "doorlock_users",
  "status": "success",
  "data": {
    "records": [
      {
        "user_id": 5,
        "user_name": "张三的右手食指",
        "user_type": "finger",
        ...
      }
    ],
    "total": 1
  }
}
```

#### 测试 3: 删除用户

**App 发送**：

```json
{
  "type": "user_mgmt",
  "seq_id": "1702234567890_003",
  "category": "finger",
  "command": "del",
  "user_id": 5
}
```

**预期结果**：

1. ESP32 删除指纹
2. Server 软删除数据库记录（status=0）
3. 再次查询时不返回该用户

## 5. 注意事项

### 5.1 数据一致性

- ESP32 和数据库的用户数据可能不一致
- 建议定期同步（可选功能，未实现）
- 删除操作采用软删除，保留历史记录

### 5.2 并发处理

- 使用 `seq_id` 作为缓存键，避免并发冲突
- 数据库使用唯一键约束，防止重复插入
- 缓存在处理完成后应清理（当前实现未清理）

### 5.3 错误处理

- 数据库操作失败时记录日志
- 不影响 ESP32 命令执行
- App 端可通过查询接口验证结果

### 5.4 性能优化

- 查询接口支持分页，避免一次返回大量数据
- 使用索引优化查询性能
- 软删除记录定期归档（可选功能，未实现）

## 6. 后续优化建议

### 6.1 功能增强

1. **同步校验**（可选）：
   - 定期从 ESP32 查询用户列表
   - 与数据库对比，发现不一致时告警
   - 提供手动同步接口

2. **批量操作**：
   - 支持批量添加用户
   - 支持批量删除用户
   - 提高操作效率

3. **用户分组**：
   - 支持用户分组管理
   - 按组设置权限
   - 便于管理大量用户

### 6.2 性能优化

1. **缓存优化**：
   - 使用 Redis 缓存用户列表
   - 减少数据库查询
   - 提高响应速度

2. **数据归档**：
   - 定期归档已删除的用户记录
   - 保持主表数据量可控
   - 提高查询性能

3. **索引优化**：
   - 根据实际查询模式调整索引
   - 定期分析慢查询
   - 优化查询性能

## 7. 总结

门锁用户管理功能已完整实现，包括：

✅ 数据库表设计和创建  
✅ CRUD 方法实现  
✅ 消息处理逻辑  
✅ 查询接口  
✅ 数据库迁移脚本  
✅ 协议文档更新

所有代码遵循项目规范：

- 使用 async/await 异步编程
- 使用 loguru 记录日志
- 添加详细的中文注释
- 遵循类型注解规范

功能已就绪，可以开始测试和使用。

---

**文档维护者**: 毕业设计项目组  
**最后更新**: 2026-01-30
