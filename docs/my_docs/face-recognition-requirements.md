# 人脸识别模块需求分析

## 1. 系统概述

### 1.1 系统架构

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│     ESP32       │     │       服务器         │     │     App 端      │
│    (门锁端)     │     │   (识别+数据管理)    │     │    (管理端)     │
├─────────────────┤     ├─────────────────────┤     ├─────────────────┤
│ • 拍照          │────▶│ • 人脸识别          │◀────│ • 人脸录入      │
│ • 发起识别请求  │◀────│ • 权限验证          │────▶│ • 权限管理      │
│ • 播放语音      │     │ • 数据库管理        │     │ • 到访记录      │
│ • 开门控制      │     │ • TTS语音合成       │     │ • 实时监控      │
└─────────────────┘     │ • 到访通知推送      │     └─────────────────┘
                        └─────────────────────┘
                                  │
                                  ▼
                        ┌─────────────────────┐
                        │   MySQL 数据库       │
                        │   127.0.0.1:3306    │
                        │   root / 123456     │
                        └─────────────────────┘
```

### 1.2 技术栈

- **人脸识别库**：face_recognition (基于 dlib)
- **数据库**：MySQL 8.0 (已部署，容器名：xiaozhi-esp32-server-db)
- **通信协议**：WebSocket (复用现有连接)
- **图像格式**：JPEG（与 ESP32 视频流格式一致）
- **语音合成**：复用现有 TTS 模块

## 2. 数据库设计

### 2.1 数据库配置

- **数据库名称**：`smart_doorlock` (新建，不影响现有数据)
- **主机**：127.0.0.1
- **端口**：3306
- **用户名**：root
- **密码**：123456

### 2.2 数据表设计

#### 2.2.1 人员信息表 (persons)

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INT AUTO_INCREMENT | 主键 |
| name | VARCHAR(50) | 姓名 |
| relation_type | ENUM | 关系类型 |
| face_encoding | BLOB | 128维人脸编码（numpy数组序列化） |
| photo_path | VARCHAR(255) | 照片存储路径 |
| custom_greeting | VARCHAR(255) | 自定义问候语（可选，预留） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

#### 2.2.2 关系类型枚举

```sql
ENUM('family', 'friend', 'colleague', 'property', 'courier', 'delivery', 'tutor', 'classmate', 'other')
-- 家人、朋友、同事、物业、快递、外卖、家教、同学、其他
```

#### 2.2.3 开门权限表 (access_permissions)

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INT AUTO_INCREMENT | 主键 |
| person_id | INT | 关联人员ID (外键) |
| permission_type | ENUM('permanent', 'temporary') | 权限类型 |
| time_start | TIME | 允许时段开始（如 08:00） |
| time_end | TIME | 允许时段结束（如 22:00） |
| day_type | ENUM('daily', 'weekly', 'monthly') | 时段类型 |
| week_days | VARCHAR(20) | 周几允许（如 "1,2,3,4,5"，1=周一） |
| month_days | VARCHAR(100) | 每月几号允许（如 "1,15,30"） |
| remaining_count | INT | 剩余次数（临时权限用，默认1） |
| valid_from | DATE | 有效期开始 |
| valid_until | DATE | 有效期结束 |
| is_active | BOOLEAN | 是否启用 |
| created_at | DATETIME | 创建时间 |

#### 2.2.4 到访记录表 (visit_records)

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INT AUTO_INCREMENT | 主键 |
| person_id | INT | 关联人员ID（可为NULL表示陌生人） |
| recognition_result | ENUM('known', 'unknown', 'no_face') | 识别结果 |
| access_granted | BOOLEAN | 是否允许开门 |
| deny_reason | VARCHAR(100) | 拒绝原因 |
| photo_path | VARCHAR(255) | 到访照片路径 |
| visit_time | DATETIME | 到访时间 |
| notified | BOOLEAN | 是否已通知App |

## 3. 功能详细设计

### 3.1 ESP32 端功能

#### 3.1.1 发起人脸识别请求

ESP32 拍照后，发送图像数据请求人脸识别。图像格式与视频流中的 JPEG 帧格式一致。

**消息格式（JSON文本）：**
```json
{
    "type": "face_recognition",
    "action": "recognize",
    "image": "<BinaryProtocol2格式封装的JPEG图像>"
}
```

注：image 字段包含 BinaryProtocol2 协议头 + JPEG 数据，整体进行 base64 编码。服务器需要先 base64 解码，再解析 BinaryProtocol2 协议提取 JPEG 图像。

#### 3.1.2 接收识别结果

服务器返回识别结果，包含 TTS 语音数据和 JSON 文本。

**成功 + 认识（有开门权限）：**
```json
{
    "type": "face_recognition",
    "result": "known",
    "person": {
        "id": 1,
        "name": "张三",
        "relation": "friend"
    },
    "access": {
        "granted": true,
        "action": "open_door"
    }
}
```
+ TTS 语音："您好，张三，欢迎来访！"

**成功 + 认识（无开门权限）：**
```json
{
    "type": "face_recognition",
    "result": "known",
    "person": {
        "id": 1,
        "name": "张三",
        "relation": "friend"
    },
    "access": {
        "granted": false,
        "reason": "不在允许时段"
    }
}
```
+ TTS 语音："抱歉，张三，当前时段不允许进入。"

**成功 + 不认识：**
```json
{
    "type": "face_recognition",
    "result": "unknown",
    "access": {
        "granted": false
    }
}
```
+ TTS 语音："您好，请问您找谁？"

**识别失败（无人脸）：**
```json
{
    "type": "face_recognition",
    "result": "no_face"
}
```
（无 TTS 语音）

### 3.2 App 端功能

#### 3.2.1 人脸录入

App 上传照片进行人脸录入，图像格式与 ESP32 发送的格式一致（JPEG）。

**请求：**
```json
{
    "type": "face_management",
    "action": "register",
    "data": {
        "name": "张三",
        "relation_type": "friend",
        "images": ["<JPEG图像base64>", "<JPEG图像base64>"],
        "permission": {
            "type": "permanent",
            "time_start": "08:00",
            "time_end": "22:00",
            "day_type": "daily"
        }
    }
}
```

**响应：**
```json
{
    "type": "face_management",
    "action": "register",
    "status": "success",
    "person_id": 1
}
```

**错误响应：**
```json
{
    "type": "face_management",
    "action": "register",
    "status": "error",
    "error": "no_face_detected"
}
```

#### 3.2.2 获取人员列表

**请求：**
```json
{
    "type": "face_management",
    "action": "get_persons"
}
```

**响应：**
```json
{
    "type": "face_management",
    "action": "get_persons",
    "status": "success",
    "data": [
        {
            "id": 1,
            "name": "张三",
            "relation_type": "friend",
            "photo_url": "/api/face/photo/1",
            "permission": {
                "type": "permanent",
                "time_start": "08:00",
                "time_end": "22:00",
                "day_type": "daily"
            }
        }
    ]
}
```

#### 3.2.3 更新权限

**请求：**
```json
{
    "type": "face_management",
    "action": "update_permission",
    "data": {
        "person_id": 1,
        "permission": {
            "type": "temporary",
            "remaining_count": 5,
            "valid_until": "2025-02-01",
            "time_start": "09:00",
            "time_end": "18:00"
        }
    }
}
```

#### 3.2.4 删除人员

**请求：**
```json
{
    "type": "face_management",
    "action": "delete_person",
    "data": {
        "person_id": 1
    }
}
```

#### 3.2.5 查看到访记录

**请求：**
```json
{
    "type": "face_management",
    "action": "get_visits",
    "data": {
        "page": 1,
        "page_size": 20,
        "date_from": "2025-01-01",
        "date_to": "2025-12-31"
    }
}
```

**响应：**
```json
{
    "type": "face_management",
    "action": "get_visits",
    "status": "success",
    "data": {
        "total": 100,
        "page": 1,
        "records": [
            {
                "id": 1,
                "person_id": 1,
                "person_name": "张三",
                "relation": "friend",
                "result": "known",
                "access_granted": true,
                "visit_time": "2025-01-15 14:30:00",
                "photo_url": "/api/face/visit_photo/1"
            }
        ]
    }
}
```

### 3.3 服务器端功能

#### 3.3.1 人脸识别流程

```
1. 接收 ESP32 发送的 JPEG 图像
2. 将 JPEG 解码为 numpy 数组
3. 使用 face_recognition.face_locations() 检测人脸
   ├── 无人脸 → 返回 {"result": "no_face"}
   └── 有人脸 → 继续
4. 使用 face_recognition.face_encodings() 提取人脸编码
5. 使用 face_recognition.compare_faces() 与数据库比对
   ├── 无匹配 → 返回 "unknown" + TTS语音
   └── 有匹配 → 查询权限
6. 验证开门权限
   ├── 无权限 → 返回拒绝 + 原因 + TTS语音
   └── 有权限 → 返回开门指令 + TTS语音
7. 保存到访记录
8. 推送通知给 App
```

#### 3.3.2 权限验证逻辑

```python
def check_permission(person_id, current_datetime):
    """
    检查人员的开门权限
    返回: (是否允许, 拒绝原因或None)
    """
    permissions = get_active_permissions(person_id)
    
    for perm in permissions:
        # 1. 检查有效期
        if not (perm.valid_from <= current_date <= perm.valid_until):
            continue
        
        # 2. 检查时段
        if not (perm.time_start <= current_time <= perm.time_end):
            continue
        
        # 3. 检查日期类型
        if perm.day_type == 'weekly':
            if str(current_weekday) not in perm.week_days.split(','):
                continue
        elif perm.day_type == 'monthly':
            if str(current_day) not in perm.month_days.split(','):
                continue
        
        # 4. 检查临时权限次数
        if perm.permission_type == 'temporary':
            if perm.remaining_count <= 0:
                continue
            # 扣减次数
            perm.remaining_count -= 1
            save_permission(perm)
        
        return True, None
    
    return False, "不在允许时段或权限已过期"
```

#### 3.3.3 语音消息生成

```python
# 关系类型对应的问候语模板
GREETINGS = {
    'family': "欢迎回家，{name}！",
    'friend': "您好，{name}，欢迎来访！",
    'colleague': "您好，{name}，请进！",
    'property': "您好，物业人员{name}，请进！",
    'courier': "您好，快递员{name}，请稍等！",
    'delivery': "您好，外卖员{name}，请稍等！",
    'tutor': "您好，{name}老师，请进！",
    'classmate': "您好，{name}同学，请进！",
    'other': "您好，{name}，请进！"
}

# 陌生人问候语
UNKNOWN_GREETING = "您好，请问您找谁？"

# 权限拒绝语
DENY_GREETING = "抱歉，{name}，{reason}。"
```

### 3.4 到访通知推送

当有人到访时，服务器主动推送消息给已连接的 App：

```json
{
    "type": "visit_notification",
    "data": {
        "visit_id": 123,
        "person_id": 1,
        "person_name": "张三",
        "relation": "friend",
        "result": "known",
        "access_granted": true,
        "visit_time": "2025-01-15 14:30:00",
        "photo_url": "/api/face/visit_photo/123"
    }
}
```

## 4. 文件目录结构

### 4.1 新增/修改的文件

```
main/xiaozhi-server/
├── core/
│   ├── handle/
│   │   └── textHandler/
│   │       └── faceRecognitionHandler.py    # [新增] 人脸识别消息处理器
│   └── providers/
│       └── doorlock/                         # [新增] 智能门锁模块（避免与face_recognition库冲突）
│           ├── __init__.py
│           ├── face_service.py              # 人脸识别核心服务
│           ├── database.py                  # 数据库操作
│           └── models.py                    # 数据模型
├── config/
│   └── face_recognition_config.yaml         # [新增] 人脸识别配置文件
├── data/
│   └── face_recognition/                    # [新增] 数据存储目录
│       ├── faces/                           # 录入的人脸照片
│       │   └── person_{id}/
│       │       └── face_{n}.jpg
│       └── visits/                          # 到访照片
│           └── {year}-{month}/
│               └── visit_{id}.jpg
└── test/
    └── app_demo.html                        # [修改] 添加人脸管理功能
```

### 4.2 文件说明

| 文件 | 说明 |
|------|------|
| `faceRecognitionHandler.py` | 处理 ESP32 和 App 发送的人脸识别相关消息 |
| `doorlock/face_service.py` | 人脸识别核心逻辑：检测、编码、比对、权限验证 |
| `doorlock/database.py` | MySQL 数据库操作：CRUD、连接管理 |
| `doorlock/models.py` | 数据模型定义：Person, Permission, VisitRecord |
| `face_recognition_config.yaml` | 配置文件：数据库连接、识别参数、语音模板 |

### 4.3 配置文件示例

```yaml
# face_recognition_config.yaml
database:
  host: 127.0.0.1
  port: 3306
  user: root
  password: "123456"
  database: smart_doorlock

recognition:
  tolerance: 0.6          # 人脸匹配阈值
  model: "hog"            # 检测模型: hog 或 cnn
  num_jitters: 1          # 编码重采样次数

storage:
  faces_dir: "data/face_recognition/faces"
  visits_dir: "data/face_recognition/visits"

greetings:
  family: "欢迎回家，{name}！"
  friend: "您好，{name}，欢迎来访！"
  colleague: "您好，{name}，请进！"
  property: "您好，物业人员{name}，请进！"
  courier: "您好，快递员{name}，请稍等！"
  delivery: "您好，外卖员{name}，请稍等！"
  tutor: "您好，{name}老师，请进！"
  classmate: "您好，{name}同学，请进！"
  other: "您好，{name}，请进！"
  unknown: "您好，请问您找谁？"
  denied: "抱歉，{name}，{reason}。"
```

## 5. 接口汇总

### 5.1 ESP32 → 服务器

| 消息类型 | action | 说明 |
|----------|--------|------|
| face_recognition | recognize | 发起人脸识别（附带JPEG图像） |

### 5.2 App → 服务器

| 消息类型 | action | 说明 |
|----------|--------|------|
| face_management | register | 录入人脸 |
| face_management | get_persons | 获取人员列表 |
| face_management | get_person | 获取单个人员详情 |
| face_management | update_person | 更新人员信息 |
| face_management | delete_person | 删除人员 |
| face_management | update_permission | 更新权限 |
| face_management | get_visits | 获取到访记录 |

### 5.3 服务器 → ESP32

| 消息类型 | 说明 |
|----------|------|
| face_recognition | 识别结果 + TTS语音 |

### 5.4 服务器 → App（推送）

| 消息类型 | 说明 |
|----------|------|
| visit_notification | 到访通知 |

## 6. 依赖项

### 6.1 Python 包

```
face_recognition>=1.3.0
numpy>=1.24.0
Pillow>=9.0.0
mysql-connector-python>=8.0.0
PyYAML>=6.0
```

### 6.2 系统依赖

```bash
# 直接安装（大多数环境可用）
pip install face_recognition

# 如果安装失败，可能需要先安装 dlib 依赖：
# Ubuntu/Debian: apt-get install cmake libboost-all-dev
# 然后: pip install dlib && pip install face_recognition
```

## 7. 实现优先级

### 第一阶段：核心功能
1. 数据库表创建和连接
2. 人脸识别服务（ESP32 → 服务器 → ESP32）
3. 人脸录入功能（App → 服务器）
4. 基础权限验证（永久权限）

### 第二阶段：完善功能
5. 到访记录管理
6. 高级权限管理（时段、临时权限）
7. 到访通知推送

### 第三阶段：优化
8. App 端 UI 完善（人脸管理页面）
9. 性能优化（人脸编码缓存）
10. 错误处理完善
