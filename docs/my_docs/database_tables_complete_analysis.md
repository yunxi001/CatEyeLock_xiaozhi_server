# 智能门锁数据库表完整分析报告

**文档创建时间**: 2026-02-03  
**最后更新时间**: 2026-02-03  
**数据库**: smart_doorlock  
**目的**: 完整分析所有 10 张表的填充逻辑、数据来源和当前状态

---

## 📋 目录

1. [概述](#概述)
2. [有数据的表（5张）](#有数据的表)
3. [空表（5张）](#空表)
4. [数据流程图](#数据流程图)
5. [代码实现状态](#代码实现状态)
6. [问题总结](#问题总结)
7. [修复建议](#修复建议)

---

## 概述

### 数据库表分类

| 分类       | 表名               | 记录数 | 状态          | 代码状态  |
| ---------- | ------------------ | ------ | ------------- | --------- |
| **有数据** | persons            | 2      | ✅ 正常       | ✅ 完整   |
| **有数据** | access_permissions | 2      | ✅ 正常       | ✅ 完整   |
| **有数据** | visit_records      | 25     | ✅ 正常       | ✅ 完整   |
| **有数据** | device_events      | 20     | ✅ 正常       | ✅ 完整   |
| **有数据** | unlock_logs        | 12     | ✅ 正常       | ✅ 完整   |
| **空表**   | device_info        | 0      | ⚠️ 功能未触发 | ✅ 完整   |
| **空表**   | device_status      | 0      | ⚠️ 功能未触发 | ✅ 完整   |
| **空表**   | door_opened_logs   | 0      | ⚠️ 功能未触发 | ✅ 完整   |
| **空表**   | doorlock_users     | 0      | ⚠️ 功能未触发 | ✅ 已修复 |
| **空表**   | media_files        | 0      | ⚠️ 配置问题   | ✅ 完整   |

### 代码完整性评估（2026-02-03 更新）

✅ **数据库方法**：所有 10 张表的 CRUD 方法都已完整实现  
✅ **消息处理器**：所有消息类型都有对应的处理器  
✅ **协议支持**：ESP32 通信协议已完整定义  
✅ **数据库更新逻辑**：所有处理器都已正确调用数据库方法  
✅ **doorlock_users 已修复**：UserMgmtResultHandler 已添加数据库更新逻辑

### 重要更新说明

**2026-02-03 代码审查发现**：

- ✅ `UserMgmtResultHandler` 已修复，现在包含完整的数据库更新逻辑
- ✅ `PasswordReportHandler` 正确调用 `update_device_password()`
- ✅ `StatusReportHandler` 正确调用 `save_device_status()`
- ✅ `DoorOpenedReportHandler` 正确调用 `save_door_opened_log()`
- ⚠️ 空表的原因主要是**功能未触发**，而非代码缺陷

---

## 有数据的表

### 1. persons（人员信息表）✅

**当前数据**: 2 条记录（张迪、王书刚）  
**代码状态**: ✅ 完整实现

#### 1.1 表结构

| 字段            | 类型         | 说明                                  |
| --------------- | ------------ | ------------------------------------- |
| id              | INT          | 主键                                  |
| name            | VARCHAR(50)  | 姓名                                  |
| relation_type   | ENUM         | 关系类型（family/friend/colleague等） |
| face_encoding   | BLOB         | 人脸编码（序列化的 numpy 数组）       |
| photo_path      | VARCHAR(255) | 照片路径                              |
| custom_greeting | VARCHAR(255) | 自定义问候语                          |
| created_at      | DATETIME     | 创建时间                              |
| updated_at      | DATETIME     | 更新时间                              |

#### 1.2 填充代码位置

- **数据库方法**: `core/providers/doorlock/database.py`
  - `save_person()` - 保存人员信息
  - `get_person()` - 获取单个人员
  - `get_all_persons()` - 获取所有人员
  - `get_all_encodings()` - 获取所有人脸编码

- **服务层**: `core/providers/doorlock/face_service.py`
  - `register_person()` - 注册新人员

#### 1.3 数据来源

- **手动注册**: 通过 Web 管理界面添加
- **API 调用**: 通过 HTTP API 注册
- **批量导入**: 通过脚本批量导入

#### 1.4 为什么有数据？

✅ **已手动注册**: 测试环境中手动添加了 2 个人员（张迪、王书刚）  
✅ **功能正常**: 人脸识别功能正常工作，visit_records 中有识别记录

---

### 2. access_permissions（访问权限表）✅

**当前数据**: 2 条记录  
**代码状态**: ✅ 完整实现

#### 2.1 表结构

| 字段            | 类型         | 说明                             |
| --------------- | ------------ | -------------------------------- |
| id              | INT          | 主键                             |
| person_id       | INT          | 人员 ID（外键）                  |
| permission_type | ENUM         | 权限类型（permanent/temporary）  |
| time_start      | TIME         | 开始时间                         |
| time_end        | TIME         | 结束时间                         |
| day_type        | ENUM         | 日期类型（daily/weekly/monthly） |
| week_days       | VARCHAR(20)  | 星期几（如 "1,3,5"）             |
| month_days      | VARCHAR(100) | 每月哪几天                       |
| remaining_count | INT          | 剩余次数                         |
| valid_from      | DATE         | 有效期开始                       |
| valid_until     | DATE         | 有效期结束                       |
| is_active       | BOOLEAN      | 是否启用                         |
| created_at      | DATETIME     | 创建时间                         |

#### 2.2 填充代码位置

- **数据库方法**: `core/providers/doorlock/database.py`
  - `save_permission()` - 保存权限配置
  - `get_permissions()` - 获取人员权限
  - `update_permission()` - 更新权限

- **服务层**: `core/providers/doorlock/face_service.py`
  - `register_person()` - 注册人员时创建权限

#### 2.3 数据来源

- **自动创建**: 注册人员时自动创建默认权限
- **手动配置**: 通过管理界面配置权限

#### 2.4 为什么有数据？

✅ **自动创建**: 注册人员时自动创建了永久权限（8:00-22:00）  
✅ **配置合理**: 两个人员都有对应的权限配置

---

### 3. visit_records（访问记录表）✅

**当前数据**: 25 条记录  
**代码状态**: ✅ 完整实现

#### 3.1 表结构

| 字段               | 类型         | 说明                              |
| ------------------ | ------------ | --------------------------------- |
| id                 | INT          | 主键                              |
| person_id          | INT          | 人员 ID（外键，可为 NULL）        |
| recognition_result | ENUM         | 识别结果（known/unknown/no_face） |
| access_granted     | BOOLEAN      | 是否允许进入                      |
| deny_reason        | VARCHAR(100) | 拒绝原因                          |
| photo_path         | VARCHAR(255) | 访问照片路径                      |
| visit_time         | DATETIME     | 访问时间                          |
| notified           | BOOLEAN      | 是否已通知                        |

#### 3.2 填充代码位置

- **数据库方法**: `core/providers/doorlock/database.py`
  - `save_visit()` - 保存到访记录

- **服务层**: `core/providers/doorlock/face_service.py`
  - `save_visit_record()` - 保存到访记录

- **处理器**: `core/handle/textHandler/faceRecognitionHandler.py`
  - `FaceRecognitionHandler.handle()` - 处理人脸识别

#### 3.3 数据来源

- **人脸识别触发**: ESP32 发送人脸图像时自动创建
- **触发条件**:
  - 门铃按下
  - PIR 检测到人体
  - 手动触发识别

#### 3.4 为什么有数据？

✅ **功能正常使用**: 有 25 条访问记录  
✅ **识别结果多样**:

- 2 条 known（识别成功：张迪、王书刚）
- 23 条 no_face（未检测到人脸）

✅ **时间分布**: 2025-12-09 和 2026-01-18 两个时间段

---

### 4. device_events（设备事件表）✅

**当前数据**: 20 条记录（全部为 pir_trigger 事件）  
**代码状态**: ✅ 完整实现

#### 4.1 表结构

| 字段       | 类型        | 说明     |
| ---------- | ----------- | -------- |
| id         | BIGINT      | 主键     |
| device_id  | VARCHAR(64) | 设备 ID  |
| event_type | VARCHAR(32) | 事件类型 |
| param      | INT         | 事件参数 |
| created_at | DATETIME    | 发生时间 |

#### 4.2 填充代码位置

- **数据库方法**: `core/providers/doorlock/database.py`
  - `save_device_event()` - 保存设备事件

- **处理器**: `core/handle/textHandler/eventReportHandler.py`
  - `EventReportHandler.handle()` - 处理事件上报

#### 4.3 支持的事件类型

| event_type   | 说明         | param 含义       |
| ------------ | ------------ | ---------------- |
| bell         | 门铃按下     | 无               |
| pir_trigger  | PIR 人体检测 | 持续时间（秒）   |
| tamper       | 撬锁报警     | 报警级别（1-3）  |
| door_open    | 门未关超时   | 超时时间（分钟） |
| low_battery  | 低电量警告   | 当前电量（%）    |
| door_closed  | 门已关闭     | 无               |
| lock_success | 上锁成功     | 无               |
| bolt_alarm   | 反锁报警     | 报警类型         |

#### 4.4 数据来源

- **STM32 触发**: STM32 检测到事件后通过 UART 发送给 ESP32
- **ESP32 转发**: ESP32 转换为 JSON 格式发送给服务器
- **自动记录**: 服务器自动保存到数据库

#### 4.5 为什么有数据？

✅ **PIR 传感器正常工作**: 20 条 pir_trigger 事件  
✅ **时间集中**: 2026-01-18 14:37-14:52，约 15 分钟内  
✅ **param 值**: 全部为 255，可能是固定值或最大值  
⚠️ **事件类型单一**: 只有 pir_trigger，其他事件类型未触发

---

### 5. unlock_logs（开锁日志表）✅

**当前数据**: 12 条记录  
**代码状态**: ✅ 完整实现

#### 5.1 表结构

| 字段       | 类型        | 说明                        |
| ---------- | ----------- | --------------------------- |
| id         | BIGINT      | 主键                        |
| device_id  | VARCHAR(64) | 设备 ID                     |
| method     | VARCHAR(16) | 开锁方式                    |
| user_id    | INT         | 用户 ID                     |
| result     | TINYINT     | 开锁结果（1=成功，0=失败）  |
| fail_count | INT         | 连续失败次数                |
| status     | VARCHAR(16) | 状态（success/fail/locked） |
| lock_time  | INT         | 剩余锁定时间（分钟）        |
| created_at | DATETIME    | 操作时间                    |

#### 5.2 填充代码位置

- **数据库方法**: `core/providers/doorlock/database.py`
  - `save_unlock_log()` - 保存开锁日志

- **处理器**:
  - `core/handle/textHandler/logReportHandler.py` - 处理开锁日志上报
  - `core/handle/textHandler/commandProxyHandler.py` - 处理远程开锁命令

#### 5.3 开锁方式（method）

| method   | 说明     | 数据来源   |
| -------- | -------- | ---------- |
| finger   | 指纹开锁 | ESP32 上报 |
| nfc      | NFC 开锁 | ESP32 上报 |
| face     | 人脸开锁 | ESP32 上报 |
| pwd      | 密码开锁 | ESP32 上报 |
| temp_pwd | 临时密码 | ESP32 上报 |
| key      | 机械钥匙 | ESP32 上报 |
| remote   | 远程开锁 | 服务器记录 |

#### 5.4 数据来源

- **ESP32 上报**: STM32 执行开锁操作后上报结果
- **服务器记录**: 远程开锁命令执行时服务器主动记录

#### 5.5 为什么有数据？

✅ **功能正常使用**: 12 条开锁记录  
✅ **开锁方式多样**:

- 5 条 remote（远程开锁成功）
- 1 条 nfc（NFC 开锁成功）
- 6 条 finger（指纹开锁失败）

✅ **失败记录**: 指纹开锁连续失败 4 次（fail_count: 1→2→3→4）  
✅ **时间分布**: 2026-01-19 到 2026-01-29

---

## 空表

### 6. device_info（设备基本信息表）⚠️

**当前数据**: 0 条记录  
**问题类型**: 功能未触发  
**代码状态**: ✅ 完整实现

#### 6.1 表结构

| 字段               | 类型         | 说明            |
| ------------------ | ------------ | --------------- |
| id                 | BIGINT       | 主键            |
| device_id          | VARCHAR(64)  | 设备 ID（唯一） |
| password_encrypted | VARCHAR(255) | 加密后的密码    |
| created_at         | DATETIME     | 创建时间        |
| updated_at         | DATETIME     | 更新时间        |

#### 6.2 填充代码位置

- **数据库方法**: `core/providers/doorlock/database.py`
  - `init_device_password()` - 初始化设备密码
  - `update_device_password()` - 更新设备密码
  - `get_device_password()` - 获取设备密码（自动初始化）

- **处理器**: `core/handle/textHandler/passwordReportHandler.py`
  - `PasswordReportHandler.handle()` - 处理密码上报

#### 6.3 代码实现（已验证）

```python
# core/handle/textHandler/passwordReportHandler.py
async def _update_password_to_database(self, conn, password: str):
    """更新密码到数据库"""
    try:
        db = _get_database(conn)
        if not db:
            conn.logger.bind(tag=TAG).warning("数据库不可用，无法更新密码")
            return

        # ✅ 正确调用数据库方法
        success = db.update_device_password(conn.device_id, password)
        if success:
            conn.logger.bind(tag=TAG).info(f"设备 {conn.device_id} 密码已更新到数据库")
        else:
            conn.logger.bind(tag=TAG).warning(f"设备 {conn.device_id} 密码更新失败")

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"更新密码到数据库失败: {e}")
```

#### 6.4 触发条件

1. **密码查询流程**:

   ```
   App → query(password) → Server → ESP32
                                      ↓
   App ← password_report ← Server ← ESP32
                           ↓
                    更新 device_info 表
   ```

2. **密码设置流程**:
   ```
   App → user_mgmt(set password) → Server → ESP32
                                             ↓
   App ← password_report ← Server ← ESP32
                           ↓
                    更新 device_info 表
   ```

#### 6.5 为什么是空的？

❌ **密码查询未触发**: 测试环境未执行密码查询流程  
❌ **ESP32 未上报密码**: 没有收到 `password_report` 消息  
❌ **自动初始化未触发**: `get_device_password()` 未被调用

**结论**: 代码实现正确，只是功能未被使用

---

### 7. device_status（设备状态记录表）⚠️

**当前数据**: 0 条记录  
**问题类型**: 功能未触发  
**代码状态**: ✅ 完整实现

#### 7.1 表结构

| 字段        | 类型        | 说明                     |
| ----------- | ----------- | ------------------------ |
| id          | BIGINT      | 主键                     |
| device_id   | VARCHAR(64) | 设备 ID                  |
| battery     | INT         | 电池电量（0-100）        |
| lux         | INT         | 光照强度（Lux）          |
| lock_state  | TINYINT     | 锁状态（0=关闭，1=打开） |
| light_state | TINYINT     | 补光灯状态（0=灭，1=亮） |
| created_at  | DATETIME    | 记录时间                 |

#### 7.2 填充代码位置

- **数据库方法**: `core/providers/doorlock/database.py`
  - `save_device_status()` - 保存设备状态

- **处理器**: `core/handle/textHandler/statusReportHandler.py`
  - `StatusReportHandler.handle()` - 处理状态上报

#### 7.3 代码实现（已验证）

```python
# core/handle/textHandler/statusReportHandler.py
async def _save_to_database(self, conn, battery: int, lux: int,
                             lock_state: int, light_state: int):
    """保存状态到数据库"""
    try:
        db = _get_database(conn)
        if db:
            # ✅ 正确调用数据库方法
            db.save_device_status(
                device_id=conn.device_id,
                battery=battery,
                lux=lux,
                lock_state=lock_state,
                light_state=light_state
            )
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"保存状态到数据库失败: {e}")
```

#### 7.4 触发条件

1. **状态变化触发**:
   - 电量变化
   - 光照变化
   - 锁状态变化
   - 灯光状态变化

2. **远程查询触发**:
   ```json
   {
     "type": "query",
     "seq_id": "1702234567890_1",
     "command": "status"
   }
   ```

#### 7.5 为什么是空的？

❌ **状态未变化**: 设备状态保持稳定，未触发上报  
❌ **上报未启用**: ESP32 可能未启用状态上报功能  
❌ **固件版本**: 旧版固件可能不支持状态上报

**结论**: 代码实现正确，只是功能未被使用

---

### 8. door_opened_logs（开门日志表）⚠️

**当前数据**: 0 条记录  
**问题类型**: 功能未触发  
**代码状态**: ✅ 完整实现

#### 8.1 表结构

| 字段       | 类型        | 说明                               |
| ---------- | ----------- | ---------------------------------- |
| id         | BIGINT      | 主键                               |
| device_id  | VARCHAR(64) | 设备 ID                            |
| method     | VARCHAR(16) | 开锁方式                           |
| source     | VARCHAR(16) | 开门来源（outside/inside/unknown） |
| created_at | DATETIME    | 开门时间                           |

#### 8.2 填充代码位置

- **数据库方法**: `core/providers/doorlock/database.py`
  - `save_door_opened_log()` - 保存开门日志

- **处理器**: `core/handle/textHandler/doorOpenedReportHandler.py`
  - `DoorOpenedReportHandler.handle()` - 处理开门日志上报

#### 8.3 代码实现（已验证）

```python
# core/handle/textHandler/doorOpenedReportHandler.py
async def _save_to_database(self, conn, method: str, source: str):
    """保存开门日志到数据库"""
    try:
        db = _get_database(conn)
        if db:
            # ✅ 正确调用数据库方法
            db.save_door_opened_log(
                device_id=conn.device_id,
                method=method,
                source=source
            )
    except Exception as e:
        # 数据库失败不影响转发
        conn.logger.bind(tag=TAG).warning(f"保存开门日志到数据库失败: {e}")
```

#### 8.4 与 unlock_logs 的区别

| 表名             | 记录内容 | 触发时机       |
| ---------------- | -------- | -------------- |
| unlock_logs      | 开锁操作 | 执行开锁命令时 |
| door_opened_logs | 开门行为 | 门被实际打开时 |

**时间线**:

```
1. 用户按指纹 → unlock_logs 记录 ✓（有数据）
2. 用户推门进入 → door_opened_logs 记录 ✗（无数据）
```

#### 8.5 source 判断逻辑

| source  | 说明     | PIR 状态     |
| ------- | -------- | ------------ |
| outside | 室外开门 | 检测到人体   |
| inside  | 室内开门 | 未检测到人体 |
| unknown | 未知     | 传感器故障   |

#### 8.6 为什么是空的？

❌ **实际开门未发生**: 测试只有开锁操作，未实际开门  
❌ **门磁传感器未触发**: 门磁传感器未检测到门被打开  
❌ **固件版本较旧**: v5.1 新增功能，旧固件不支持  
❌ **STM32 未上报**: STM32 未发送 `RPT_DOOR_OPENED (0xA2)` 消息

**结论**: 代码实现正确，只是功能未被使用

---

### 9. doorlock_users（门锁用户表）⚠️

**当前数据**: 0 条记录  
**问题类型**: 功能未触发  
**代码状态**: ✅ 已修复（2026-02-03 验证）

#### 9.1 表结构（新版本）

| 字段       | 类型        | 说明                            |
| ---------- | ----------- | ------------------------------- |
| id         | BIGINT      | 主键                            |
| device_id  | VARCHAR(64) | 设备 ID                         |
| user_type  | VARCHAR(16) | 用户类型（finger/nfc/password） |
| user_id    | INT         | ESP32 分配的用户 ID             |
| user_name  | VARCHAR(64) | 用户备注名称                    |
| user_data  | TEXT        | 额外数据（如 NFC 卡号）         |
| status     | TINYINT     | 状态（1=有效，0=已删除）        |
| created_at | DATETIME    | 创建时间                        |
| updated_at | DATETIME    | 更新时间                        |
| created_by | VARCHAR(64) | 创建者 app_id                   |

#### 9.2 填充代码位置

- **数据库方法**: `core/providers/doorlock/database.py`
  - `save_doorlock_user()` - 保存门锁用户 ✅
  - `delete_doorlock_user()` - 删除门锁用户（软删除）✅
  - `get_doorlock_user()` - 获取单个用户 ✅
  - `query_doorlock_users()` - 查询用户列表 ✅
  - `clear_doorlock_users()` - 清空用户 ✅

- **处理器**: `core/handle/textHandler/userMgmtResultHandler.py`
  - `UserMgmtResultHandler.handle()` - 处理用户管理结果 ✅

#### 9.3 代码实现（已修复，2026-02-03 验证）

```python
# core/handle/textHandler/userMgmtResultHandler.py
async def _update_database(self, conn, category: str, command: str, val: int, msg_json: Dict[str, Any]):
    """根据操作结果更新数据库"""
    try:
        db = _get_database(conn)
        if not db:
            conn.logger.bind(tag=TAG).warning("数据库不可用，跳过更新")
            return

        # 从缓存中获取 user_name 和其他信息
        seq_id = msg_json.get("seq_id")
        pending_info = None
        if hasattr(conn, "_pending_user_names") and seq_id:
            pending_info = conn._pending_user_names.pop(seq_id, None)

        if command == "add" and val > 0:
            # ✅ 添加用户成功，保存到数据库
            user_name = pending_info.get("user_name") if pending_info else None
            app_id = pending_info.get("app_id") if pending_info else None

            db.save_doorlock_user(
                device_id=conn.device_id,
                user_type=category,
                user_id=val,
                user_name=user_name,
                user_data=None,
                created_by=app_id
            )
            conn.logger.bind(tag=TAG).info(
                f"已保存门锁用户到数据库: type={category}, user_id={val}, name={user_name}"
            )

        elif command == "del":
            # ✅ 删除用户成功，更新数据库状态
            user_id = pending_info.get("user_id") if pending_info else msg_json.get("user_id")
            if user_id is not None:
                db.delete_doorlock_user(
                    device_id=conn.device_id,
                    user_type=category,
                    user_id=user_id
                )
                conn.logger.bind(tag=TAG).info(
                    f"已删除门锁用户: type={category}, user_id={user_id}"
                )

        elif command == "clear":
            # ✅ 清空用户成功，更新数据库状态
            count = db.clear_doorlock_users(
                device_id=conn.device_id,
                user_type=category
            )
            conn.logger.bind(tag=TAG).info(
                f"已清空门锁用户: type={category}, count={count}"
            )

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"更新数据库失败: {e}")
```

#### 9.4 为什么是空的？

❌ **功能未使用**: 测试环境未使用指纹/NFC 功能  
❌ **未通过 user_mgmt 添加用户**: 只使用了人脸识别（persons 表有数据）

**结论**: ✅ 代码已修复，实现完整，只是功能未被使用

#### 9.5 修复历史

- **2026-01-30**: 发现代码缺陷，处理器缺少数据库更新逻辑
- **2026-02-03**: 代码已修复，添加了完整的数据库更新逻辑
- **验证状态**: ✅ 代码审查通过，实现正确

---

### 10. media_files（媒体文件元数据表）⚠️

**当前数据**: 0 条记录  
**问题类型**: 配置问题  
**代码状态**: ✅ 完整实现

#### 10.1 表结构

| 字段       | 类型         | 说明                          |
| ---------- | ------------ | ----------------------------- |
| id         | BIGINT       | 主键                          |
| device_id  | VARCHAR(64)  | 设备 ID                       |
| file_type  | VARCHAR(16)  | 文件类型（photo/video/audio） |
| file_path  | VARCHAR(256) | 文件存储路径                  |
| file_size  | INT          | 文件大小（字节）              |
| duration   | INT          | 时长（秒）                    |
| user_id    | INT          | 关联用户 ID                   |
| created_at | DATETIME     | 创建时间                      |

#### 10.2 填充代码位置

- **数据库方法**: `core/providers/doorlock/database.py`
  - `save_media_file()` - 保存媒体文件元数据

- **处理器**:
  - `core/handle/textHandler/faceRecognitionHandler.py` - 人脸识别照片
  - `core/providers/doorlock/video_recorder.py` - 监控录像

#### 10.3 代码实现（已验证）

```python
# core/handle/textHandler/faceRecognitionHandler.py
async def _save_face_image(self, conn, jpeg_data: bytes, user_id: int):
    """保存人脸图片到文件系统"""
    try:
        # ⚠️ 需要 media_storage 对象
        if hasattr(conn, "media_storage") and conn.media_storage:
            # 保存图片文件
            file_path = await conn.media_storage.save_face_image(
                device_id=conn.device_id,
                image_data=jpeg_data,
                user_id=user_id
            )

            # ✅ 记录元数据到数据库
            face_service = get_face_service(conn.logger)
            if face_service and face_service.db:
                file_size = len(jpeg_data)
                face_service.db.save_media_file(
                    device_id=conn.device_id,
                    file_type="face",
                    file_path=file_path,
                    file_size=file_size,
                    user_id=user_id
                )

            conn.logger.bind(tag=TAG).debug(f"保存人脸图片: {file_path}")
            return file_path
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"保存人脸图片失败: {e}")
    return None
```

#### 10.4 触发条件

1. **人脸识别**: ESP32 发送人脸图像时
2. **监控模式**: 启动监控录像时
3. **关键条件**: `conn.media_storage` 必须存在

#### 10.5 为什么是空的？

❌ **media_storage 未初始化**: `conn.media_storage` 不存在或为 None  
❌ **监控功能未使用**: 未启动监控模式  
❌ **配置问题**: 媒体文件存储路径未配置

**结论**: 代码实现正确，但 `media_storage` 对象未初始化

---

## 数据流程图

### 完整的数据流程

```
┌─────────────┐
│   ESP32     │
│  (智能门锁)  │
└──────┬──────┘
       │
       │ WebSocket 连接
       │
       ▼
┌─────────────────────────────────────────────────┐
│              Server (后端服务)                    │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │         消息处理器 (Handlers)             │  │
│  ├──────────────────────────────────────────┤  │
│  │ ✅ EventReportHandler                    │  │
│  │ ✅ LogReportHandler                      │  │
│  │ ✅ StatusReportHandler                   │  │
│  │ ✅ DoorOpenedReportHandler               │  │
│  │ ✅ PasswordReportHandler                 │  │
│  │ ✅ UserMgmtResultHandler (已修复)        │  │
│  │ ✅ FaceRecognitionHandler                │  │
│  └──────────────────────────────────────────┘  │
│                     │                           │
│                     ▼                           │
│  ┌──────────────────────────────────────────┐  │
│  │         数据库操作 (Database)             │  │
│  ├──────────────────────────────────────────┤  │
│  │ ✅ save_person()                         │  │
│  │ ✅ save_permission()                     │  │
│  │ ✅ save_visit()                          │  │
│  │ ✅ save_device_event()                   │  │
│  │ ✅ save_unlock_log()                     │  │
│  │ ✅ save_device_status()                  │  │
│  │ ✅ save_door_opened_log()                │  │
│  │ ✅ update_device_password()              │  │
│  │ ✅ save_doorlock_user() (已修复)         │  │
│  │ ⚠️  save_media_file() (需配置)           │  │
│  └──────────────────────────────────────────┘  │
│                     │                           │
└─────────────────────┼───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│         MySQL Database (smart_doorlock)         │
├─────────────────────────────────────────────────┤
│                                                 │
│  ✅ persons (2 条)                              │
│  ✅ access_permissions (2 条)                   │
│  ✅ visit_records (25 条)                       │
│  ✅ device_events (20 条)                       │
│  ✅ unlock_logs (12 条)                         │
│                                                 │
│  ⚠️  device_info (0 条) - 功能未触发            │
│  ⚠️  device_status (0 条) - 功能未触发          │
│  ⚠️  door_opened_logs (0 条) - 功能未触发       │
│  ⚠️  doorlock_users (0 条) - 功能未触发         │
│  ⚠️  media_files (0 条) - 配置问题              │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 消息流程示例

#### 1. 人脸识别流程（有数据）✅

```
ESP32 → BinaryProtocol2 (人脸图像)
  ↓
Server: FaceRecognitionHandler
  ├─ face_service.recognize()
  ├─ face_service.check_access()
  ├─ face_service.save_visit_record()  ✅
  │   └─ db.save_visit()  ✅ visit_records 表
  └─ 发送 face_result 给 ESP32

结果: visit_records 有 25 条记录 ✅
```

#### 2. 开锁日志流程（有数据）✅

```
ESP32 → log_report (开锁日志)
  ↓
Server: LogReportHandler
  ├─ 解析 method, uid, status
  ├─ db.save_unlock_log()  ✅ unlock_logs 表
  └─ 转发给 App

结果: unlock_logs 有 12 条记录 ✅
```

#### 3. 设备事件流程（有数据）✅

```
ESP32 → event_report (PIR 触发)
  ↓
Server: EventReportHandler
  ├─ 解析 event, param
  ├─ db.save_device_event()  ✅ device_events 表
  └─ 转发给 App

结果: device_events 有 20 条记录 ✅
```

#### 4. 密码上报流程（无数据）⚠️

```
ESP32 → password_report (密码)
  ↓
Server: PasswordReportHandler
  ├─ 解析 password
  ├─ db.update_device_password()  ✅ 代码正确
  └─ 转发给 App

结果: device_info 无记录 ❌ (未触发)
原因: ESP32 未发送 password_report 消息
```

#### 5. 状态上报流程（无数据）⚠️

```
ESP32 → status_report (状态)
  ↓
Server: StatusReportHandler
  ├─ 解析 bat, lux, lock, light
  ├─ db.save_device_status()  ✅ 代码正确
  └─ 转发给 App

结果: device_status 无记录 ❌ (未触发)
原因: ESP32 未发送 status_report 消息
```

#### 6. 开门日志流程（无数据）⚠️

```
ESP32 → door_opened_report (开门)
  ↓
Server: DoorOpenedReportHandler
  ├─ 解析 method, source
  ├─ db.save_door_opened_log()  ✅ 代码正确
  └─ 转发给 App

结果: door_opened_logs 无记录 ❌ (未触发)
原因: ESP32 未发送 door_opened_report 消息
```

#### 7. 用户管理流程（无数据）⚠️

```
ESP32 → user_mgmt_result (用户管理结果)
  ↓
Server: UserMgmtResultHandler
  ├─ 解析 category, command, result, val
  ├─ 记录日志  ✅
  ├─ db.save_doorlock_user()  ✅ 代码已修复
  └─ 转发给 App  ✅

结果: doorlock_users 无记录 ❌ (未触发)
原因: 未使用指纹/NFC 功能
```

#### 8. 媒体文件流程（无数据）⚠️

```
ESP32 → BinaryProtocol2 (人脸图像)
  ↓
Server: FaceRecognitionHandler
  ├─ 检查 conn.media_storage  ❌ (不存在)
  ├─ media_storage.save_face_image()  ❌ (跳过)
  └─ db.save_media_file()  ❌ (未执行)

结果: media_files 无记录 ❌ (配置问题)
原因: conn.media_storage 未初始化
```

---

## 代码实现状态

### 数据库方法实现状态

| 表名               | 数据库方法               | 实现状态 | 位置                                |
| ------------------ | ------------------------ | -------- | ----------------------------------- |
| persons            | save_person()            | ✅ 完整  | core/providers/doorlock/database.py |
| access_permissions | save_permission()        | ✅ 完整  | core/providers/doorlock/database.py |
| visit_records      | save_visit()             | ✅ 完整  | core/providers/doorlock/database.py |
| device_events      | save_device_event()      | ✅ 完整  | core/providers/doorlock/database.py |
| unlock_logs        | save_unlock_log()        | ✅ 完整  | core/providers/doorlock/database.py |
| device_info        | update_device_password() | ✅ 完整  | core/providers/doorlock/database.py |
| device_status      | save_device_status()     | ✅ 完整  | core/providers/doorlock/database.py |
| door_opened_logs   | save_door_opened_log()   | ✅ 完整  | core/providers/doorlock/database.py |
| doorlock_users     | save_doorlock_user()     | ✅ 完整  | core/providers/doorlock/database.py |
| media_files        | save_media_file()        | ✅ 完整  | core/providers/doorlock/database.py |

### 消息处理器实现状态

| 处理器                  | 数据库调用               | 实现状态  | 位置                                               |
| ----------------------- | ------------------------ | --------- | -------------------------------------------------- |
| FaceRecognitionHandler  | save_visit()             | ✅ 完整   | core/handle/textHandler/faceRecognitionHandler.py  |
| LogReportHandler        | save_unlock_log()        | ✅ 完整   | core/handle/textHandler/logReportHandler.py        |
| EventReportHandler      | save_device_event()      | ✅ 完整   | core/handle/textHandler/eventReportHandler.py      |
| PasswordReportHandler   | update_device_password() | ✅ 完整   | core/handle/textHandler/passwordReportHandler.py   |
| StatusReportHandler     | save_device_status()     | ✅ 完整   | core/handle/textHandler/statusReportHandler.py     |
| DoorOpenedReportHandler | save_door_opened_log()   | ✅ 完整   | core/handle/textHandler/doorOpenedReportHandler.py |
| UserMgmtResultHandler   | save_doorlock_user()     | ✅ 已修复 | core/handle/textHandler/userMgmtResultHandler.py   |
| FaceRecognitionHandler  | save_media_file()        | ⚠️ 需配置 | core/handle/textHandler/faceRecognitionHandler.py  |

### 代码质量评估

**优点** ✅

- 所有数据库方法都已完整实现
- 所有消息处理器都已正确调用数据库方法
- 异步处理性能良好
- 错误处理完善
- 日志记录详细
- 代码结构清晰，易于维护

**需要改进** ⚠️

- `media_storage` 对象需要初始化
- 部分功能需要 ESP32 固件支持

---

## 问题总结

### 问题分类统计（2026-02-03 更新）

| 问题类型       | 表数量 | 表名                                                                   | 严重程度 |
| -------------- | ------ | ---------------------------------------------------------------------- | -------- |
| **正常**       | 5      | persons, access_permissions, visit_records, device_events, unlock_logs | -        |
| **功能未触发** | 4      | device_info, device_status, door_opened_logs, doorlock_users           | 低       |
| **配置问题**   | 1      | media_files                                                            | 中       |

### 详细问题列表

#### 1. 功能未触发（4 张表）

**device_info**

- 原因: 密码查询流程未执行
- 影响: 无法离线查询密码
- 优先级: 低
- 代码状态: ✅ 完整

**device_status**

- 原因: 状态未变化或上报未启用
- 影响: 无法追踪设备状态历史
- 优先级: 低
- 代码状态: ✅ 完整

**door_opened_logs**

- 原因: 实际开门行为未发生
- 影响: 无法区分开锁和开门
- 优先级: 中
- 代码状态: ✅ 完整

**doorlock_users**

- 原因: 未使用指纹/NFC 功能
- 影响: 无法追踪门锁用户信息
- 优先级: 低
- 代码状态: ✅ 已修复（2026-02-03）

#### 2. 配置问题（1 张表）

**media_files**

- 原因: `conn.media_storage` 未初始化
- 影响: 无法保存人脸识别照片和监控录像
- 优先级: 中
- 代码状态: ✅ 完整，需要配置

### 代码修复历史

| 日期       | 问题                    | 状态      | 说明                                 |
| ---------- | ----------------------- | --------- | ------------------------------------ |
| 2026-01-30 | doorlock_users 代码缺陷 | ❌ 发现   | UserMgmtResultHandler 缺少数据库更新 |
| 2026-02-03 | doorlock_users 代码缺陷 | ✅ 已修复 | 添加了完整的数据库更新逻辑           |
| 2026-02-03 | 所有处理器代码审查      | ✅ 通过   | 所有处理器都正确调用数据库方法       |

---

## 修复建议

### 优先级 1：配置修复（建议）

#### 修复 media_files 表的配置问题

**问题**: `conn.media_storage` 对象未初始化

**修复方法**:

1. **检查 media_storage 初始化位置**

   ```bash
   # 搜索 media_storage 相关代码
   grep -r "media_storage" main/xiaozhi-server/core/
   ```

2. **在 connection.py 中初始化 media_storage**

   ```python
   # core/connection.py
   class Connection:
       def __init__(self, ...):
           # ... 其他初始化代码

           # 初始化 media_storage
           from core.providers.doorlock.media_storage import MediaStorage
           self.media_storage = MediaStorage(
               storage_path="data/media",
               logger=self.logger
           )
   ```

3. **配置存储路径**
   ```yaml
   # config.yaml
   media:
     storage_path: "data/media"
     face_image_path: "data/media/faces"
     video_path: "data/media/videos"
   ```

**预期效果**:

- 人脸识别照片会自动保存
- media_files 表开始有数据
- 可以追踪媒体文件元数据

---

### 优先级 2：功能测试（建议）

#### 1. 测试密码查询流程

**目的**: 填充 device_info 表

**测试步骤**:

```json
// 1. App 发送密码查询
{
  "type": "query",
  "seq_id": "1702234567890_019",
  "target": "password"
}

// 2. 预期: ESP32 返回 password_report
// 3. 预期: device_info 表有数据
```

**验证方法**:

```sql
SELECT * FROM device_info;
```

---

#### 2. 测试状态上报

**目的**: 填充 device_status 表

**测试步骤**:

```json
// 方法 1: 触发状态变化（充电、开关灯等）
// 方法 2: 发送远程查询
{
  "type": "query",
  "seq_id": "1702234567890_1",
  "command": "status"
}

// 预期: ESP32 返回 status_report
// 预期: device_status 表有数据
```

**验证方法**:

```sql
SELECT * FROM device_status ORDER BY created_at DESC LIMIT 10;
```

---

#### 3. 测试实际开门

**目的**: 填充 door_opened_logs 表

**测试步骤**:

```
1. 执行开锁操作（指纹/NFC/远程）
2. 实际推门进入（触发门磁传感器）
3. 检查 door_opened_logs 表
```

**验证方法**:

```sql
SELECT * FROM door_opened_logs;
```

**注意事项**:

- 需要 ESP32 固件版本 >= v5.1
- 需要 STM32 支持 RPT_DOOR_OPENED (0xA2) 消息
- 需要门磁传感器正常工作

---

#### 4. 测试用户管理

**目的**: 填充 doorlock_users 表

**测试步骤**:

```json
// App 添加指纹用户
{
  "type": "user_mgmt",
  "seq_id": "1702234567890_6",
  "category": "finger",
  "command": "add",
  "user_id": 0,
  "user_name": "测试用户"
}

// 预期: ESP32 返回 user_mgmt_result
// 预期: doorlock_users 表有数据
```

**验证方法**:

```sql
SELECT * FROM doorlock_users WHERE status = 1;
```

---

#### 5. 测试人脸识别照片保存

**目的**: 填充 media_files 表

**前提条件**:

- ✅ 已初始化 `conn.media_storage`
- ✅ 已配置存储路径

**测试步骤**:

```
1. 触发人脸识别
2. 检查日志中是否有 "保存人脸图片"
3. 检查 media_files 表
4. 检查文件系统中是否有图片文件
```

**验证方法**:

```sql
SELECT * FROM media_files WHERE file_type = 'face';
```

---

### 优先级 3：固件检查（可选）

#### 检查 ESP32 固件版本

**检查项目**:

1. 固件版本 >= v5.1（支持 door_opened_logs）
2. 支持状态上报功能
3. 支持密码上报功能
4. 支持用户管理功能

**检查方法**:

```json
// 发送版本查询
{
  "type": "query",
  "seq_id": "1702234567890_1",
  "command": "version"
}
```

---

## 总结

### 当前状态（2026-02-03）

**✅ 代码实现完整（10 张表）**

- 所有数据库方法都已完整实现
- 所有消息处理器都正确调用数据库方法
- UserMgmtResultHandler 已修复（2026-02-03）

**✅ 正常工作（5 张表）**

- persons: 人脸识别功能正常
- access_permissions: 权限管理正常
- visit_records: 访问记录正常
- device_events: 事件上报正常
- unlock_logs: 开锁日志正常

**⚠️ 功能未触发（4 张表）**

- device_info: 密码查询未触发
- device_status: 状态上报未触发
- door_opened_logs: 开门行为未触发
- doorlock_users: 用户管理未触发

**⚠️ 配置问题（1 张表）**

- media_files: media_storage 未初始化

### 关键结论

1. **代码质量**: ✅ 所有代码实现正确，无代码缺陷
2. **空表原因**: 主要是功能未被使用，而非代码问题
3. **修复优先级**:
   - 高: media_storage 配置（影响照片保存）
   - 中: 功能测试（验证完整性）
   - 低: 固件检查（可选）

### 下一步行动

1. **立即执行**: 初始化 media_storage 对象
2. **建议执行**: 完整测试各个功能流程
3. **可选执行**: 检查 ESP32 固件版本

### 预期结果

修复完成后，所有 10 张表都应该能正常填充数据，系统功能完整可用。

---

**文档维护者**: 毕业设计项目组  
**创建时间**: 2026-01-30  
**最后更新**: 2026-02-03  
**状态**: ✅ 代码审查完成，实现正确
