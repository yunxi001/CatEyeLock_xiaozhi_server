# App 功能完善修复方案

## 修复优先级

### 🔴 P0 - 高优先级（影响核心功能）

1. ✅ 修复到访记录 SQL 查询 - **已完成**
2. ⚠️ 增强设备离线错误日志 - **待实施**

### 🟡 P1 - 中优先级（影响用户体验）

3. ⚠️ 添加 `get_events()` 方法 - **待实施**
4. ⚠️ 添加 `get_unlock_logs()` 方法 - **待实施**
5. ⚠️ 修复 `Person` 模型参数错误 - **待实施**

### 🟢 P2 - 低优先级（优化改进）

6. ⚠️ 数据库预初始化 - **可选**

---

## 修复方案详解

---

## 修复 1: 增强设备离线错误日志 🔴

### 问题描述

设备离线时，NFC 和指纹查询没有在日志中显示错误响应，导致难以排查问题。

### 修改文件

`main/xiaozhi-server/core/handle/textHandler/commandProxyHandler.py`

### 修改内容

#### 1.1 修改 `LockControlProxyHandler._send_error()`

**位置**: 约第 90 行

```python
async def _send_error(self, conn, message: str, code: int = ErrorCode.INTERNAL_ERROR):
    """发送错误响应

    Args:
        conn: App 连接对象
        message: 错误消息
        code: 统一错误码（0-10）
    """
    try:
        # 添加日志记录
        conn.logger.bind(tag=TAG).warning(
            f"锁控命令错误: device_id={conn.device_id}, app_id={conn.app_id}, "
            f"code={code}, message={message}"
        )

        await conn.websocket.send(json.dumps({
            "type": "lock_control",
            "status": "error",
            "code": code,
            "message": message
        }))
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"发送错误响应失败: {e}")
```

#### 1.2 修改 `DevControlProxyHandler._send_error()`

**位置**: 约第 230 行

```python
async def _send_error(self, conn, message: str, code: int = ErrorCode.INTERNAL_ERROR):
    """发送错误响应

    Args:
        conn: App 连接对象
        message: 错误消息
        code: 统一错误码（0-10）
    """
    try:
        # 添加日志记录
        conn.logger.bind(tag=TAG).warning(
            f"设备控制错误: device_id={conn.device_id}, app_id={conn.app_id}, "
            f"code={code}, message={message}"
        )

        await conn.websocket.send(json.dumps({
            "type": "dev_control",
            "status": "error",
            "code": code,
            "message": message
        }))
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"发送错误响应失败: {e}")
```

#### 1.3 修改 `UserMgmtProxyHandler._send_error()`

**位置**: 约第 370 行

```python
async def _send_error(self, conn, message: str, code: int = ErrorCode.INTERNAL_ERROR):
    """发送错误响应

    Args:
        conn: App 连接对象
        message: 错误消息
        code: 统一错误码（0-10）
    """
    try:
        # 添加日志记录
        conn.logger.bind(tag=TAG).warning(
            f"用户管理错误: device_id={conn.device_id}, app_id={conn.app_id}, "
            f"code={code}, message={message}"
        )

        await conn.websocket.send(json.dumps({
            "type": "user_mgmt",
            "status": "error",
            "code": code,
            "message": message
        }))
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"发送错误响应失败: {e}")
```

### 预期效果

修改后，日志中会显示：

```
260509 19:32:32 [commandProxyHandler]-INFO-收到 App 用户管理命令: category=nfc, command=query
260509 19:32:32 [commandProxyHandler]-WARNING-用户管理错误: device_id=e8:f6:0a:83:8f:50, app_id=app_xxx, code=1, message=设备离线
```

---

## 修复 2: 添加 `get_events()` 方法 🟡

### 问题描述

`DoorlockDatabase` 类缺少 `get_events()` 方法，导致 App 无法查询设备事件历史。

### 修改文件

`main/xiaozhi-server/core/providers/doorlock/doorlock_database.py`

### 修改内容

在 `DoorlockDatabase` 类中添加方法（建议在 `get_status_history()` 方法后面）：

```python
def get_events(self, device_id: str, event_type: str = None,
               limit: int = 100, offset: int = 0) -> Tuple[List[dict], int]:
    """查询设备事件历史（带分页）

    Args:
        device_id: 设备 ID
        event_type: 事件类型过滤（可选）
        limit: 每页数量
        offset: 偏移量

    Returns:
        (记录列表, 总数)
    """
    conn = None
    cursor = None
    try:
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        # 构建查询条件
        where_sql = "device_id = %s"
        params = [device_id]
        if event_type:
            where_sql += " AND event_type = %s"
            params.append(event_type)

        # 查询总数
        cursor.execute(f"SELECT COUNT(*) as total FROM device_events WHERE {where_sql}", params)
        total = cursor.fetchone()['total']

        # 查询记录
        cursor.execute(f"""
            SELECT id, event_type, param, created_at
            FROM device_events
            WHERE {where_sql}
            ORDER BY created_at DESC LIMIT %s OFFSET %s
        """, params + [limit, offset])
        records = cursor.fetchall()

        # 转换 datetime 为字符串
        for r in records:
            if r.get('created_at'):
                try:
                    r['created_at'] = r['created_at'].isoformat()
                except (AttributeError, ValueError) as e:
                    if self.logger:
                        self.logger.bind(tag=TAG).warning(f"转换 created_at 失败: {e}")
                    r['created_at'] = str(r['created_at'])

        return records, total
    except Exception as e:
        if self.logger:
            self.logger.bind(tag=TAG).error(f"查询事件历史失败: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
```

### 测试方法

重启服务器后，App 查询事件历史应该成功：

```json
{
  "type": "query",
  "target": "events",
  "data": {
    "limit": 20,
    "offset": 0
  }
}
```

---

## 修复 3: 添加 `get_unlock_logs()` 方法 🟡

### 问题描述

`DoorlockDatabase` 类缺少 `get_unlock_logs()` 方法，导致 App 无法查询更多开锁日志。

### 修改文件

`main/xiaozhi-server/core/providers/doorlock/doorlock_database.py`

### 修改内容

在 `get_events()` 方法后面添加：

```python
def get_unlock_logs(self, device_id: str, method: str = None,
                    result: int = None, limit: int = 100,
                    offset: int = 0) -> Tuple[List[dict], int]:
    """查询开锁日志（带分页）

    Args:
        device_id: 设备 ID
        method: 开锁方式过滤（可选）
        result: 结果过滤（可选，1=成功，0=失败）
        limit: 每页数量
        offset: 偏移量

    Returns:
        (记录列表, 总数)
    """
    conn = None
    cursor = None
    try:
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        # 构建查询条件
        where_clauses = ["device_id = %s"]
        params = [device_id]

        if method:
            where_clauses.append("method = %s")
            params.append(method)

        if result is not None:
            # result 字段在数据库中可能是 TINYINT 类型
            # status 字段是 VARCHAR，需要根据实际表结构调整
            where_clauses.append("(result = %s OR status = %s)")
            status_str = "success" if result == 1 else "fail"
            params.extend([result, status_str])

        where_sql = " AND ".join(where_clauses)

        # 查询总数
        cursor.execute(f"SELECT COUNT(*) as total FROM unlock_logs WHERE {where_sql}", params)
        total = cursor.fetchone()['total']

        # 查询记录
        cursor.execute(f"""
            SELECT id, method, user_id, result, status, fail_count, lock_time, created_at
            FROM unlock_logs
            WHERE {where_sql}
            ORDER BY created_at DESC LIMIT %s OFFSET %s
        """, params + [limit, offset])
        records = cursor.fetchall()

        # 转换 datetime 为字符串
        for r in records:
            if r.get('created_at'):
                try:
                    r['created_at'] = r['created_at'].isoformat()
                except (AttributeError, ValueError) as e:
                    if self.logger:
                        self.logger.bind(tag=TAG).warning(f"转换 created_at 失败: {e}")
                    r['created_at'] = str(r['created_at'])

        return records, total
    except Exception as e:
        if self.logger:
            self.logger.bind(tag=TAG).error(f"查询开锁日志失败: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
```

### 测试方法

重启服务器后，App 查询开锁日志应该成功：

```json
{
  "type": "query",
  "target": "unlock_logs",
  "data": {
    "limit": 20,
    "offset": 0
  }
}
```

---

## 修复 4: 修复 `Person` 模型参数错误 🟡

### 问题描述

`Person` 模型的构造函数不接受 `photo_path` 参数，导致获取人员列表失败。

### 排查步骤

#### 4.1 查看 `Person` 模型定义

```bash
# 查找 Person 类定义
grep -r "class Person" main/xiaozhi-server/
```

#### 4.2 查看数据库查询代码

查看 `core/providers/doorlock/database.py` 中的 `_row_to_person()` 方法：

```python
def _row_to_person(self, row: dict) -> Person:
    """将数据库行转换为 Person 对象"""
    encoding = None
    if row.get('face_encoding'):
        encoding = self.deserialize_encoding(row['face_encoding'])
    return Person(
        id=row['id'],
        name=row['name'],
        relation_type=row['relation_type'],
        face_encoding=encoding,
        photo_path=row.get('photo_path', ''),  # ← 这里传入了 photo_path
        custom_greeting=row.get('custom_greeting'),
        created_at=row.get('created_at'),
        updated_at=row.get('updated_at')
    )
```

### 修改方案

#### 方案 A: 修改 `Person` 模型（推荐）

找到 `Person` 类定义（可能在 `core/providers/doorlock/models.py`），添加 `photo_path` 参数：

```python
@dataclass
class Person:
    """人员信息"""
    id: Optional[int] = None
    name: str = ""
    relation_type: str = "other"
    face_encoding: Optional[np.ndarray] = None
    photo_path: str = ""  # ← 添加这个字段
    custom_greeting: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

#### 方案 B: 修改查询代码（不推荐）

如果不想修改模型，可以在查询时不传入 `photo_path`：

```python
def _row_to_person(self, row: dict) -> Person:
    """将数据库行转换为 Person 对象"""
    encoding = None
    if row.get('face_encoding'):
        encoding = self.deserialize_encoding(row['face_encoding'])

    person = Person(
        id=row['id'],
        name=row['name'],
        relation_type=row['relation_type'],
        face_encoding=encoding,
        # photo_path=row.get('photo_path', ''),  # ← 注释掉
        custom_greeting=row.get('custom_greeting'),
        created_at=row.get('created_at'),
        updated_at=row.get('updated_at')
    )

    # 手动设置 photo_path 属性
    person.photo_path = row.get('photo_path', '')

    return person
```

### 推荐方案 A

因为 `photo_path` 是数据库表中的字段，应该在模型中定义。

---

## 修复 5: 数据库预初始化（可选）🟢

### 问题描述

首次推送时，数据库初始化耗时约 1 秒，影响推送速度。

### 修改文件

`main/xiaozhi-server/app.py`

### 修改内容

在服务器启动时预初始化数据库：

```python
async def main():
    """主函数"""
    # ... 现有代码 ...

    # 预初始化门锁数据库（可选优化）
    try:
        from core.providers.doorlock.doorlock_database import DoorlockDatabase
        from config.config_loader import load_config

        config = load_config()
        doorlock_db = DoorlockDatabase(config)

        # 缓存到 FaceService（如果存在）
        try:
            from core.handle.textHandler.faceRecognitionHandler import get_face_service
            face_service = get_face_service(logger)
            face_service.doorlock_db = doorlock_db
            logger.info("门锁数据库预初始化成功")
        except Exception as e:
            logger.warning(f"缓存数据库实例失败: {e}")
    except Exception as e:
        logger.warning(f"门锁数据库预初始化失败: {e}")

    # ... 启动服务器 ...
```

### 效果

- 首次 App 连接时，推送速度从 ~2s 降低到 ~1s
- 数据库连接池提前创建，避免首次查询延迟

---

## 实施步骤

### 第一步：修复高优先级问题（必须）

1. ✅ 到访记录 SQL - **已完成**
2. ⚠️ 增强错误日志 - **立即实施**

```bash
# 修改 commandProxyHandler.py
# 在 3 个 _send_error() 方法中添加日志
```

### 第二步：添加缺失的查询方法（重要）

3. ⚠️ 添加 `get_events()` 方法
4. ⚠️ 添加 `get_unlock_logs()` 方法

```bash
# 修改 doorlock_database.py
# 添加两个查询方法
```

### 第三步：修复模型错误（重要）

5. ⚠️ 修复 `Person` 模型

```bash
# 查找 Person 类定义
# 添加 photo_path 字段
```

### 第四步：性能优化（可选）

6. ⚠️ 数据库预初始化

```bash
# 修改 app.py
# 在启动时初始化数据库
```

---

## 测试验证

### 测试 1: 设备离线错误日志

```bash
# 1. 确保设备离线
# 2. App 查询 NFC 或指纹
# 3. 查看日志，应该显示：
#    [commandProxyHandler]-WARNING-用户管理错误: ... code=1, message=设备离线
```

### 测试 2: 事件历史查询

```bash
# 1. 重启服务器
# 2. App 查询事件历史
# 3. 应该返回成功，不再报错
```

### 测试 3: 开锁日志查询

```bash
# 1. 重启服务器
# 2. App 查询开锁日志
# 3. 应该返回成功，不再报错
```

### 测试 4: 人员列表查询

```bash
# 1. 重启服务器
# 2. App 查询人员列表
# 3. 应该返回成功，不再报错
```

---

## 预期结果

### 修复前

```
✅ 推送功能: 80% (到访记录失败)
⚠️ 查询功能: 60% (缺少 2 个方法)
⚠️ 错误处理: 70% (日志不完整)
```

### 修复后

```
✅ 推送功能: 100% (所有推送正常)
✅ 查询功能: 100% (所有查询正常)
✅ 错误处理: 100% (日志完整清晰)
```

---

## 文件清单

需要修改的文件：

1. ✅ `main/xiaozhi-server/core/app_connection.py` - 到访记录 SQL（已完成）
2. ⚠️ `main/xiaozhi-server/core/handle/textHandler/commandProxyHandler.py` - 错误日志
3. ⚠️ `main/xiaozhi-server/core/providers/doorlock/doorlock_database.py` - 查询方法
4. ⚠️ `main/xiaozhi-server/core/providers/doorlock/models.py` - Person 模型
5. ⚠️ `main/xiaozhi-server/app.py` - 数据库预初始化（可选）

---

## 总结

### 必须修复（P0-P1）

- ✅ 到访记录 SQL
- ⚠️ 错误日志增强
- ⚠️ 添加 `get_events()`
- ⚠️ 添加 `get_unlock_logs()`
- ⚠️ 修复 `Person` 模型

### 可选优化（P2）

- ⚠️ 数据库预初始化

### 预计工作量

- 必须修复: 约 1-2 小时
- 可选优化: 约 30 分钟
- 测试验证: 约 30 分钟

**总计: 2-3 小时可以完成所有修复**
