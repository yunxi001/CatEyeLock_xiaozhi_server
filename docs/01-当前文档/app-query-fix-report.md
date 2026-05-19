# App 查询功能缺失修复报告

## 修复时间

2025-01-10

## 问题描述

根据日志分析，发现以下问题：

### 问题 1：`doorlock_users` 查询目标未注册

```
ERROR-查询失败: target=doorlock_users, error=未知查询目标: doorlock_users
```

**原因**：`queryHandler.py` 的 `handlers` 字典中没有注册 `doorlock_users` 目标。

### 问题 2：`get_device_password` 方法不存在

```
ERROR-查询密码失败: 'DoorlockDatabase' object has no attribute 'get_device_password'
```

**原因**：

- `queryHandler.py` 使用 `DoorlockDatabase` 实例调用 `get_device_password()`
- 但该方法只存在于 `Database` 类中，不存在于 `DoorlockDatabase` 类中

### 问题 3：数据库类职责混乱

当前有两个数据库类：

- **`Database`** (`database.py`) - 完整的门锁数据库操作
- **`DoorlockDatabase`** (`doorlock_database.py`) - 门锁 AI 功能专用

`queryHandler.py` 期望使用统一的数据库实例，但 `DoorlockDatabase` 缺少基础查询方法。

---

## 修复方案

采用**双数据库实例方案**，在 `queryHandler.py` 中同时使用两个数据库实例：

- `DoorlockDatabase` - 处理 AI 功能查询（访客意图、快递警报）
- `Database` - 处理基础查询（密码、门锁用户、事件、开锁日志等）

---

## 修改内容

### 文件：`core/handle/textHandler/queryHandler.py`

#### 1. 重构数据库获取函数

**原函数**：`_get_database(conn)` - 只返回 `DoorlockDatabase`

**新函数**：

- `_get_ai_database(conn)` - 返回 `DoorlockDatabase`（用于 AI 功能）
- `_get_base_database(conn)` - 返回 `Database`（用于基础功能）

```python
def _get_ai_database(conn):
    """获取 AI 功能数据库实例（DoorlockDatabase）

    用于访客意图、快递警报等 AI 功能查询
    """
    # ... 实现代码

def _get_base_database(conn):
    """获取基础功能数据库实例（Database）

    用于设备状态、事件、开锁日志、密码、门锁用户等基础查询
    """
    # ... 实现代码
```

#### 2. 添加 `doorlock_users` 查询处理器

在 `handlers` 字典中添加：

```python
handlers = {
    # ... 其他处理器
    "doorlock_users": self._query_doorlock_users,  # 新增
}
```

新增方法：

```python
async def _query_doorlock_users(self, conn, data: Dict):
    """查询门锁用户列表

    请求参数:
    - user_type: 用户类型过滤（可选）：finger/nfc/face
    - limit: 返回条数，默认100，最大500
    - offset: 偏移量，默认0
    """
    # ... 实现代码
```

**功能特性**：

- 支持按用户类型过滤（finger/nfc/face）
- 支持分页查询
- 自动解析 JSON 字段（finger_ids、nfc_ids）
- 返回标准化的响应格式

#### 3. 修改现有查询方法的数据库调用

| 查询方法                 | 原调用            | 新调用                 | 说明           |
| ------------------------ | ----------------- | ---------------------- | -------------- |
| `_query_status`          | `_get_database()` | `_get_base_database()` | 基础功能       |
| `_query_status_history`  | `_get_database()` | `_get_base_database()` | 基础功能       |
| `_query_events`          | `_get_database()` | `_get_base_database()` | 基础功能       |
| `_query_unlock_logs`     | `_get_database()` | `_get_base_database()` | 基础功能       |
| `_query_media_files`     | `_get_database()` | `_get_base_database()` | 基础功能       |
| `_query_password`        | `_get_database()` | `_get_base_database()` | 基础功能       |
| `_query_visitor_intents` | `_get_database()` | `_get_ai_database()`   | AI 功能        |
| `_query_package_alerts`  | `_get_database()` | `_get_ai_database()`   | AI 功能        |
| `_query_doorlock_users`  | -                 | `_get_base_database()` | 新增，基础功能 |

---

## 修改统计

- **修改文件数**：1 个
- **新增函数**：2 个（`_get_ai_database`, `_get_base_database`）
- **新增查询方法**：1 个（`_query_doorlock_users`）
- **修改查询方法**：8 个
- **代码行数变化**：+约 120 行

---

## 测试验证

### 1. 门锁用户查询测试

**请求示例**：

```json
{
  "type": "query",
  "target": "doorlock_users",
  "data": {
    "user_type": "finger",
    "limit": 100,
    "offset": 0
  }
}
```

**预期响应**：

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
        "user_id": 1,
        "name": "张三",
        "role": "admin",
        "finger_ids": [1, 2],
        "nfc_ids": [],
        "face_registered": true,
        "created_at": "2024-12-11T10:30:00",
        "updated_at": "2024-12-11T10:30:00"
      }
    ],
    "total": 1,
    "limit": 100,
    "offset": 0
  }
}
```

### 2. 密码查询测试

**请求示例**：

```json
{
  "type": "query",
  "target": "password"
}
```

**预期响应**：

```json
{
  "type": "query_result",
  "target": "password",
  "status": "success",
  "data": {
    "password": "123456"
  }
}
```

### 3. 其他查询验证

需要验证以下查询功能正常：

- ✅ `status` - 设备状态查询
- ✅ `status_history` - 历史状态查询
- ✅ `events` - 事件历史查询
- ✅ `unlock_logs` - 开锁日志查询
- ✅ `media_files` - 媒体文件查询
- ✅ `visitor_intents` - 访客意图查询（AI 功能）
- ✅ `package_alerts` - 快递警报查询（AI 功能）

---

## 风险评估

### 低风险 ✅

- 只修改一个文件
- 不改变数据库类的实现
- 向后兼容，不影响其他模块
- 职责清晰：AI 功能和基础功能分离

### 需要注意 ⚠️

- 确保 `Database` 类的 `get_doorlock_users()` 方法返回正确格式
- 确保 `face_service` 能正确缓存两个数据库实例
- 测试所有查询功能，确保没有回归

---

## 后续建议

### 1. 协议文档更新

更新 `app-protocol-v2.5-update-checklist-final.md`，添加 `doorlock_users` 查询接口说明。

### 2. 数据库架构优化（可选）

考虑长期优化方案：

- **方案 A**：让 `DoorlockDatabase` 继承 `Database` 类
- **方案 B**：创建统一的数据库接口层
- **方案 C**：保持当前双实例方案（推荐，职责清晰）

### 3. 单元测试

为新增的 `_query_doorlock_users` 方法添加单元测试。

### 4. 集成测试

在真实环境中测试所有查询功能，确保：

- App 能正常查询门锁用户列表
- 密码查询返回正确结果
- 其他查询功能不受影响

---

## 修复状态

- ✅ 问题 1：`doorlock_users` 查询目标未注册 - **已修复**
- ✅ 问题 2：`get_device_password` 方法不存在 - **已修复**
- ✅ 问题 3：数据库类职责混乱 - **已优化**

---

## 相关文件

- **修改文件**：`core/handle/textHandler/queryHandler.py`
- **依赖文件**：
  - `core/providers/doorlock/database.py`
  - `core/providers/doorlock/doorlock_database.py`
  - `core/handle/textHandler/faceRecognitionHandler.py`

---

**修复完成时间**：2025-01-10  
**修复人员**：Kiro AI  
**文档版本**：v1.0
