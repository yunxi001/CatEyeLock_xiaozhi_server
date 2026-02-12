# 数据库空表说明文档

**文档创建时间**: 2026-01-30  
**数据库**: smart_doorlock  
**目的**: 说明当前为空的数据库表的设计用途和使用场景

---

## 概述

当前数据库中有 5 张表暂无数据，这些表是为智能门锁系统的完整功能预留的。本文档详细说明每张表的设计目的、字段含义和使用场景。

---

## 1. device_info（设备基本信息表）

### 1.1 表结构

| 字段               | 类型         | 说明                         |
| ------------------ | ------------ | ---------------------------- |
| id                 | BIGINT       | 主键，自增                   |
| device_id          | VARCHAR(64)  | 设备 ID（唯一，如 MAC 地址） |
| password_encrypted | VARCHAR(255) | 加密后的设备密码             |
| created_at         | DATETIME     | 创建时间                     |
| updated_at         | DATETIME     | 更新时间                     |

### 1.2 设计用途

存储智能门锁设备的基本配置信息，主要用于：

1. **设备密码管理**
   - 存储设备的 6 位数字密码（加密存储）
   - 支持服务器端快速查询密码（无需设备在线）
   - 默认密码为 "123456"

2. **设备注册**
   - 记录设备首次连接时间
   - 追踪设备配置变更历史

### 1.3 使用场景

**场景 1：密码查询**

```json
// App 发送查询请求
{
    "type": "query",
    "seq_id": "1702234567890_019",
    "target": "password"
}

// 服务器从 device_info 表读取并返回
{
    "type": "query_result",
    "target": "password",
    "status": "success",
    "data": {
        "password": "123456"
    }
}
```

**场景 2：密码更新**

- ESP32 上报密码时，服务器自动更新此表
- 支持离线查询最后一次同步的密码

### 1.4 数据来源

- **初始化**：设备首次连接时自动创建记录
- **更新**：ESP32 通过 `password_report` 消息上报密码时更新
- **手动设置**：通过 `user_mgmt` 命令设置密码后同步更新

### 1.5 相关文档

- `docs/completed/database-optimization/CHANGELOG_password_query.md`
- `docs/my_docs/智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md` (3.2.5 密码上报)

---

## 2. device_status（设备状态记录表）

### 2.1 表结构

| 字段        | 类型        | 说明                   |
| ----------- | ----------- | ---------------------- |
| id          | BIGINT      | 主键，自增             |
| device_id   | VARCHAR(64) | 设备 ID                |
| battery     | INT         | 电池电量百分比 (0-100) |
| lux         | INT         | 光照强度值 (Lux)       |
| lock_state  | TINYINT     | 锁状态：0=关闭, 1=打开 |
| light_state | TINYINT     | 补光灯状态：0=灭, 1=亮 |
| created_at  | DATETIME    | 记录时间               |

### 2.2 设计用途

记录设备传感器状态的历史数据，用于：

1. **状态监控**
   - 实时监控设备电量、光照、锁状态
   - 追踪设备状态变化历史

2. **数据分析**
   - 电量消耗趋势分析
   - 光照环境统计
   - 门锁使用频率分析

3. **告警触发**
   - 低电量预警（< 20%）
   - 异常状态检测（门长时间未关）

### 2.3 使用场景

**场景 1：状态上报**

ESP32 检测到状态变化时自动上报：

```json
{
  "type": "status_report",
  "ts": 1702234567890,
  "data": {
    "bat": 85,
    "lux": 300,
    "lock": 0,
    "light": 1
  }
}
```

服务器收到后存入 `device_status` 表。

**场景 2：状态查询**

App 可以查询设备历史状态：

```json
{
  "type": "query",
  "seq_id": "1702234567890_1",
  "target": "status_history",
  "device_id": "e8:f6:0a:83:8f:50",
  "limit": 100
}
```

**场景 3：远程查询当前状态**

```json
{
  "type": "query",
  "seq_id": "1702234567890_1",
  "command": "status"
}
```

服务器转发给 ESP32，ESP32 查询 STM32 后上报最新状态。

### 2.4 数据来源

- **自动上报**：ESP32 检测到状态变化时主动上报
- **定期上报**：可配置定时上报（如每小时）
- **查询触发**：App 发起查询时实时获取

### 2.5 数据保留策略

- 默认保留 7 天的状态记录
- 可通过 `cleanup_old_data()` 方法清理过期数据

### 2.6 相关文档

- `docs/my_docs/智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md` (3.2.1 传感器状态上报)

---

## 3. door_opened_logs（开门日志表）

### 3.1 表结构

| 字段       | 类型        | 说明                             |
| ---------- | ----------- | -------------------------------- |
| id         | BIGINT      | 主键，自增                       |
| device_id  | VARCHAR(64) | 设备 ID                          |
| method     | VARCHAR(16) | 开锁方式                         |
| source     | VARCHAR(16) | 开门来源：outside/inside/unknown |
| created_at | DATETIME    | 开门时间                         |

### 3.2 设计用途

记录用户实际开门行为，与 `unlock_logs` 区分：

- **unlock_logs**：记录开锁操作（命令执行成功）
- **door_opened_logs**：记录开门行为（用户实际开门）

用途：

1. **行为分析**
   - 区分室内开门和室外开门
   - 统计开门频率和时间分布
   - 分析用户使用习惯

2. **安全审计**
   - 追踪异常开门行为
   - 检测未授权开门
   - 配合 PIR 传感器判断开门来源

3. **智能联动**
   - 室外开门触发欢迎语音
   - 室内开门关闭报警
   - 开门后自动开灯

### 3.3 使用场景

**场景 1：室外开门**

用户在门外使用指纹开锁并开门：

```json
{
  "type": "door_opened_report",
  "ts": 1702234567890,
  "data": {
    "method": "finger",
    "source": "outside" // PIR 检测到人体
  }
}
```

**场景 2：室内开门**

用户从室内打开门：

```json
{
  "type": "door_opened_report",
  "ts": 1702234567890,
  "data": {
    "method": "manual",
    "source": "inside" // PIR 未检测到人体
  }
}
```

### 3.4 source 判断逻辑

| source  | 说明     | PIR 状态     | 典型场景           |
| ------- | -------- | ------------ | ------------------ |
| outside | 室外开门 | 检测到人体   | 访客进入、主人回家 |
| inside  | 室内开门 | 未检测到人体 | 主人外出、室内活动 |
| unknown | 未知     | 传感器故障   | 异常情况           |

### 3.5 与 unlock_logs 的关系

```
时间线：
1. 用户按指纹 → unlock_logs 记录（开锁操作）
2. 用户推门进入 → door_opened_logs 记录（开门行为）
```

两者可能存在时间差（几秒到几分钟）。

### 3.6 数据来源

- **STM32 上报**：通过 `RPT_DOOR_OPENED (0xA2)` 消息
- **触发条件**：门磁传感器检测到门被打开

### 3.7 相关文档

- `docs/my_docs/智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md` (3.2.4 开门日志上报)
- `.kiro/specs/protocol-upgrade-v5.0-to-v5.2/design.md` (4.1.2 door_opened_logs 表)

---

## 4. doorlock_users（门锁用户表）

### 4.1 表结构

| 字段            | 类型        | 说明                       |
| --------------- | ----------- | -------------------------- |
| id              | BIGINT      | 主键，自增                 |
| device_id       | VARCHAR(64) | 设备 ID                    |
| user_id         | INT         | 用户 ID（门锁内部 ID）     |
| name            | VARCHAR(64) | 用户姓名                   |
| role            | VARCHAR(16) | 用户角色：admin/member     |
| finger_ids      | JSON        | 指纹 ID 列表               |
| nfc_ids         | JSON        | NFC 卡 ID 列表             |
| face_registered | TINYINT     | 人脸是否已注册：0=否, 1=是 |
| created_at      | DATETIME    | 创建时间                   |
| updated_at      | DATETIME    | 更新时间                   |

### 4.2 设计用途

管理门锁系统中的用户信息，用于：

1. **用户管理**
   - 记录每个用户的认证方式（指纹/NFC/人脸）
   - 追踪用户权限和角色
   - 关联用户与认证凭证

2. **多设备同步**
   - 同一用户在多个门锁上的信息同步
   - 集中管理用户权限

3. **审计追溯**
   - 记录用户创建和修改历史
   - 关联开锁日志到具体用户

### 4.3 使用场景

**场景 1：添加指纹用户**

```json
// App 发送添加指纹命令
{
    "type": "user_mgmt",
    "seq_id": "1702234567890_6",
    "category": "finger",
    "command": "add",
    "user_id": 0  // 自动分配
}

// ESP32 返回结果
{
    "type": "user_mgmt_result",
    "category": "finger",
    "command": "add",
    "result": true,
    "val": 5,  // 分配的指纹 ID
    "msg": "Success"
}

// 服务器更新 doorlock_users 表
// user_id=5, finger_ids=[5]
```

**场景 2：用户添加多个指纹**

```json
// 用户 ID 5 添加第二个指纹
{
  "type": "user_mgmt",
  "seq_id": "1702234567890_7",
  "category": "finger",
  "command": "add",
  "user_id": 5
}

// 服务器更新
// user_id=5, finger_ids=[5, 8]
```

**场景 3：查询用户信息**

```json
{
    "type": "query",
    "target": "users",
    "device_id": "e8:f6:0a:83:8f:50"
}

// 返回
{
    "type": "query_result",
    "target": "users",
    "data": [
        {
            "user_id": 5,
            "name": "张三",
            "role": "admin",
            "finger_ids": [5, 8],
            "nfc_ids": [1],
            "face_registered": 1
        }
    ]
}
```

### 4.4 字段说明

**finger_ids (JSON 数组)**

```json
[5, 8, 12] // 用户录入的指纹 ID 列表
```

**nfc_ids (JSON 数组)**

```json
[1, 3] // 用户绑定的 NFC 卡 ID 列表
```

**role 取值**

- `admin`：管理员，可以添加/删除其他用户
- `member`：普通成员，只能使用自己的凭证

### 4.5 数据来源

- **用户管理操作**：通过 `user_mgmt` 命令添加/删除用户时更新
- **ESP32 同步**：ESP32 可以上报当前用户列表
- **手动录入**：管理员通过 Web 界面添加

### 4.6 与 persons 表的关系

- **persons 表**：人脸识别系统的人员信息（服务器端）
- **doorlock_users 表**：门锁硬件的用户信息（设备端）

两者可以关联但独立管理：

- persons 用于人脸识别和权限控制
- doorlock_users 用于指纹/NFC 管理

### 4.7 相关文档

- `docs/my_docs/智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md` (3.8 用户管理)

---

## 5. media_files（媒体文件元数据表）

### 5.1 表结构

| 字段       | 类型         | 说明                        |
| ---------- | ------------ | --------------------------- |
| id         | BIGINT       | 主键，自增                  |
| device_id  | VARCHAR(64)  | 设备 ID                     |
| file_type  | VARCHAR(16)  | 文件类型：photo/video/audio |
| file_path  | VARCHAR(256) | 文件存储路径                |
| file_size  | INT          | 文件大小（字节）            |
| duration   | INT          | 时长（秒，视频/音频有效）   |
| user_id    | INT          | 关联用户 ID                 |
| created_at | DATETIME     | 创建时间                    |

### 5.2 设计用途

存储智能门锁产生的媒体文件元数据，用于：

1. **人脸识别照片**
   - 访客到访时拍摄的照片
   - 陌生人检测照片
   - 人脸识别失败的照片

2. **监控录像**
   - 门铃触发的视频片段
   - 异常事件录像
   - 定时监控录像

3. **音频记录**
   - 对讲录音
   - 语音留言

4. **文件管理**
   - 追踪文件存储位置
   - 统计存储空间使用
   - 定期清理过期文件

### 5.3 使用场景

**场景 1：人脸识别照片**

```json
// ESP32 发送人脸图像（BinaryProtocol2）
// type=2, payload=JPEG 数据

// 服务器保存文件并记录
INSERT INTO media_files (
    device_id,
    file_type,
    file_path,
    file_size,
    user_id
) VALUES (
    'e8:f6:0a:83:8f:50',
    'photo',
    '/data/faces/2026-01-30/14-30-25_e8f60a838f50.jpg',
    45678,
    5  // 识别到的用户 ID
);
```

**场景 2：监控录像**

```json
// App 请求查看监控录像
{
    "type": "query",
    "target": "media_files",
    "device_id": "e8:f6:0a:83:8f:50",
    "file_type": "video",
    "date_from": "2026-01-30",
    "date_to": "2026-01-30"
}

// 返回文件列表
{
    "type": "query_result",
    "target": "media_files",
    "data": [
        {
            "id": 123,
            "file_type": "video",
            "file_path": "/data/videos/2026-01-30/14-30-25.mp4",
            "file_size": 1234567,
            "duration": 30,
            "created_at": "2026-01-30 14:30:25"
        }
    ]
}
```

**场景 3：陌生人照片推送**

```
1. PIR 检测到人体
2. ESP32 拍摄照片并上传
3. 服务器人脸识别：unknown
4. 保存照片到 media_files
5. 推送通知到 App："检测到陌生人"
6. App 显示照片（通过 file_path 获取）
```

### 5.4 file_type 说明

| file_type | 说明 | 典型场景           | 文件格式   |
| --------- | ---- | ------------------ | ---------- |
| photo     | 照片 | 人脸识别、访客记录 | JPEG       |
| video     | 视频 | 监控录像、事件回放 | MP4, MJPEG |
| audio     | 音频 | 对讲录音、语音留言 | OPUS, MP3  |

### 5.5 文件存储策略

**存储路径规则**

```
/data/{file_type}/{date}/{time}_{device_id}.{ext}

示例：
/data/faces/2026-01-30/14-30-25_e8f60a838f50.jpg
/data/videos/2026-01-30/14-30-25_e8f60a838f50.mp4
```

**清理策略**

- 照片保留 30 天
- 视频保留 7 天
- 音频保留 30 天
- 可通过 `cleanup_old_data()` 自动清理

### 5.6 数据来源

- **人脸识别**：ESP32 上传人脸图像时自动创建
- **监控模式**：监控录像保存时创建
- **手动上传**：用户通过 App 上传照片/视频

### 5.7 相关文档

- `docs/my_docs/智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md` (2. 二进制流媒体协议)

---

## 数据流程图

### 完整的数据流程

```
┌─────────────┐
│   ESP32     │
│  (智能门锁)  │
└──────┬──────┘
       │
       │ 1. 状态变化上报
       │ 2. 事件触发
       │ 3. 用户操作
       │ 4. 媒体数据
       │
       ▼
┌─────────────┐
│   Server    │
│  (后端服务)  │
└──────┬──────┘
       │
       │ 存储到数据库
       │
       ▼
┌─────────────────────────────────┐
│         MySQL Database          │
├─────────────────────────────────┤
│ ✓ persons (人员信息)             │
│ ✓ access_permissions (权限)     │
│ ✓ visit_records (访问记录)       │
│ ✓ device_events (设备事件)       │
│ ✓ unlock_logs (开锁日志)         │
│                                 │
│ ○ device_info (设备信息) ←─┐    │
│ ○ device_status (设备状态) ←┼─ 待填充 │
│ ○ door_opened_logs (开门)  ←┤    │
│ ○ doorlock_users (用户)    ←┤    │
│ ○ media_files (媒体文件)   ←┘    │
└─────────────────────────────────┘
       │
       │ 查询/推送
       │
       ▼
┌─────────────┐
│     App     │
│  (移动应用)  │
└─────────────┘
```

---

## 为什么这些表是空的？

### 原因分析

1. **device_info**
   - 需要设备首次连接并上报密码后才会有数据
   - 当前测试环境可能未配置密码同步

2. **device_status**
   - 需要 ESP32 主动上报状态变化
   - 可能未启用状态上报功能
   - 或者状态未发生变化

3. **door_opened_logs**
   - 需要实际开门行为触发
   - 当前测试可能只有开锁操作，未实际开门
   - 或者 STM32 固件版本较旧，不支持此功能

4. **doorlock_users**
   - 需要通过 `user_mgmt` 命令添加用户
   - 当前可能只使用了人脸识别（persons 表）
   - 未使用指纹/NFC 功能

5. **media_files**
   - 需要人脸识别或监控功能触发
   - 可能未启用照片/视频存储功能
   - 或者文件存储路径配置问题

### 如何填充数据

**device_info**

```bash
# 方法 1：设备连接后自动创建
# 方法 2：手动初始化
python migrations/run_add_device_password.py
```

**device_status**

```json
// ESP32 发送状态上报
{
  "type": "status_report",
  "ts": 1702234567890,
  "data": {
    "bat": 85,
    "lux": 300,
    "lock": 0,
    "light": 1
  }
}
```

**door_opened_logs**

```json
// ESP32 发送开门日志
{
  "type": "door_opened_report",
  "ts": 1702234567890,
  "data": {
    "method": "finger",
    "source": "outside"
  }
}
```

**doorlock_users**

```json
// App 添加指纹用户
{
  "type": "user_mgmt",
  "seq_id": "1702234567890_6",
  "category": "finger",
  "command": "add",
  "user_id": 0
}
```

**media_files**

```
// ESP32 上传人脸图像
// 服务器自动保存并记录
```

---

## 总结

这 5 张空表是智能门锁系统的重要组成部分，它们为以下功能提供支持：

| 表名             | 核心功能     | 数据来源          | 使用频率 |
| ---------------- | ------------ | ----------------- | -------- |
| device_info      | 设备配置管理 | 设备连接/密码上报 | 低频     |
| device_status    | 状态监控     | 状态变化上报      | 中频     |
| door_opened_logs | 开门行为追踪 | 开门事件上报      | 高频     |
| doorlock_users   | 用户凭证管理 | 用户管理操作      | 低频     |
| media_files      | 媒体文件管理 | 人脸识别/监控     | 中频     |

随着系统的实际使用，这些表会逐渐填充数据，为智能门锁提供完整的功能支持。

---

**文档维护者**: 毕业设计项目组  
**最后更新**: 2026-01-30
