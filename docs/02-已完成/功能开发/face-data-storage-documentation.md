# 人脸数据存储文档

## 概述

智能门锁系统的人脸识别功能使用 MySQL 数据库存储人脸数据和相关信息。本文档详细说明人脸数据的存储结构、表设计和使用方式。

---

## 数据库配置

### 配置文件位置

- `main/xiaozhi-server/config/face_recognition_config.yaml`

### 数据库连接配置

```yaml
database:
  host: 127.0.0.1
  port: 3306
  user: root
  password: "123456"
  database: smart_doorlock
  pool_size: 5
```

---

## 核心数据表

### 1. persons 表（人员信息表）

**用途**：存储已注册人员的基本信息和人脸特征编码

**表结构**：

```sql
CREATE TABLE persons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL COMMENT '人员姓名',
    relation_type ENUM('family', 'friend', 'colleague', 'property', 'courier', 'delivery', 'tutor', 'classmate', 'other') NOT NULL DEFAULT 'other' COMMENT '关系类型',
    face_encoding BLOB COMMENT '人脸特征编码（序列化后的 numpy 数组）',
    photo_path VARCHAR(255) COMMENT '人脸照片路径',
    custom_greeting VARCHAR(255) COMMENT '自定义问候语',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**字段说明**：

- `id`: 人员唯一标识
- `name`: 人员姓名
- `relation_type`: 关系类型（家人、朋友、同事等）
- `face_encoding`: **核心字段**，存储人脸特征向量（使用 pickle 序列化的 numpy 数组）
- `photo_path`: 人脸照片存储路径（相对路径）
- `custom_greeting`: 自定义问候语（可选）

**人脸编码存储方式**：

```python
# 序列化（存储时）
face_encoding_blob = pickle.dumps(face_encoding_array)

# 反序列化（读取时）
face_encoding_array = pickle.loads(face_encoding_blob)
```

---

### 2. access_permissions 表（访问权限表）

**用途**：管理人员的开门权限配置

**表结构**：

```sql
CREATE TABLE access_permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    person_id INT NOT NULL COMMENT '关联的人员 ID',
    permission_type ENUM('permanent', 'temporary') NOT NULL DEFAULT 'permanent' COMMENT '权限类型',
    time_start TIME DEFAULT '00:00:00' COMMENT '允许时间段开始',
    time_end TIME DEFAULT '23:59:59' COMMENT '允许时间段结束',
    day_type ENUM('daily', 'weekly', 'monthly') NOT NULL DEFAULT 'daily' COMMENT '日期类型',
    week_days VARCHAR(20) COMMENT '允许的星期（如 "1,2,3,4,5"）',
    month_days VARCHAR(100) COMMENT '允许的日期（如 "1,15,30"）',
    remaining_count INT DEFAULT 1 COMMENT '临时权限剩余次数',
    valid_from DATE COMMENT '有效期开始日期',
    valid_until DATE COMMENT '有效期结束日期',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**权限类型**：

- `permanent`: 永久权限
- `temporary`: 临时权限（有次数限制）

**时间控制**：

- `time_start` / `time_end`: 每天允许的时间段
- `day_type`: 日期类型（每天、每周、每月）
- `week_days`: 每周允许的星期几
- `month_days`: 每月允许的日期

---

### 3. visit_records 表（到访记录表）

**用途**：记录所有人脸识别的到访记录（包括已知和陌生人）

**表结构**：

```sql
CREATE TABLE visit_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    person_id INT COMMENT '识别到的人员 ID（陌生人为 NULL）',
    recognition_result ENUM('known', 'unknown', 'no_face') NOT NULL COMMENT '识别结果',
    access_granted BOOLEAN DEFAULT FALSE COMMENT '是否允许开门',
    deny_reason VARCHAR(100) COMMENT '拒绝原因',
    photo_path VARCHAR(255) COMMENT '到访时的人脸照片路径',
    visit_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '到访时间',
    notified BOOLEAN DEFAULT FALSE COMMENT '是否已通知',
    FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**识别结果类型**：

- `known`: 识别为已注册人员
- `unknown`: 陌生人
- `no_face`: 未检测到人脸

**拒绝原因示例**：

- "不在允许时间段内"
- "临时权限已用完"
- "权限已过期"

---

## 文件存储结构

### 人脸照片存储路径

**配置**：

```yaml
storage:
  base_dir: "data/face_recognition"
  faces_dir: "data/face_recognition/faces"
  visits_dir: "data/face_recognition/visits"
```

**目录结构**：

```
data/face_recognition/
├── faces/                          # 已注册人员的人脸照片
│   ├── person_1/                   # 人员 ID 为 1 的照片目录
│   │   ├── face_1.jpg
│   │   ├── face_2.jpg
│   │   └── ...
│   ├── person_2/
│   └── ...
└── visits/                         # 到访记录的人脸照片
    ├── 2026-02/                    # 按年月组织
    │   ├── visit_123_20260208_143022.jpg
    │   └── ...
    └── ...
```

---

## 数据模型（Python）

### Person 模型

```python
@dataclass
class Person:
    """人员信息"""
    id: Optional[int] = None
    name: str = ""
    relation_type: str = "other"
    face_encoding: Optional[np.ndarray] = None  # 人脸特征向量
    photo_path: str = ""
    custom_greeting: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

### AccessPermission 模型

```python
@dataclass
class AccessPermission:
    """开门权限"""
    id: Optional[int] = None
    person_id: int = 0
    permission_type: str = "permanent"
    time_start: time = field(default_factory=lambda: time(0, 0))
    time_end: time = field(default_factory=lambda: time(23, 59))
    day_type: str = "daily"
    week_days: Optional[str] = None
    month_days: Optional[str] = None
    remaining_count: int = 1
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
```

### VisitRecord 模型

```python
@dataclass
class VisitRecord:
    """到访记录"""
    id: Optional[int] = None
    person_id: Optional[int] = None
    recognition_result: str = "unknown"
    access_granted: bool = False
    deny_reason: Optional[str] = None
    photo_path: str = ""
    visit_time: Optional[datetime] = None
    notified: bool = False
```

---

## 数据库操作接口

### Database 类（`core/providers/doorlock/database.py`）

#### 人员管理

```python
# 保存人员信息
person_id = db.save_person(person)

# 获取单个人员
person = db.get_person(person_id)

# 获取所有人员
persons = db.get_all_persons()

# 获取所有人脸编码（用于识别比对）
encodings = db.get_all_encodings()  # 返回 [(person_id, encoding), ...]

# 删除人员
db.delete_person(person_id)
```

#### 权限管理

```python
# 保存权限
perm_id = db.save_permission(permission)

# 获取人员权限
permissions = db.get_permissions(person_id)

# 更新权限
db.update_permission(permission)

# 扣减临时权限次数
db.decrement_remaining_count(perm_id)
```

#### 到访记录

```python
# 保存到访记录
visit_id = db.save_visit(visit_record)

# 查询到访记录（分页）
records, total = db.get_visits(page=1, page_size=20, date_from=None, date_to=None)

# 标记已通知
db.mark_visit_notified(visit_id)
```

---

## 人脸识别流程

### 1. 人脸注册流程

```
1. 接收多张人脸照片（建议 3-5 张）
   ↓
2. 使用 face_recognition 库提取人脸编码
   ↓
3. 计算平均编码（提高识别准确率）
   ↓
4. 保存到 persons 表（face_encoding 字段）
   ↓
5. 保存照片到 data/face_recognition/faces/person_{id}/
   ↓
6. 创建默认权限（access_permissions 表）
```

### 2. 人脸识别流程

```
1. ESP32 发送人脸图像（JPEG 格式）
   ↓
2. 服务器提取人脸编码
   ↓
3. 从数据库加载所有已注册人脸编码
   ↓
4. 计算相似度（face_distance）
   ↓
5. 找到最匹配的人员（距离 < tolerance）
   ↓
6. 检查访问权限（时间段、有效期等）
   ↓
7. 保存到访记录（visit_records 表）
   ↓
8. 返回识别结果和开门决策
```

### 3. 识别参数配置

```yaml
recognition:
  tolerance: 0.6 # 人脸匹配阈值（越小越严格，推荐 0.4-0.6）
  model: "hog" # 检测模型：hog（CPU 快）或 cnn（GPU 精确）
  num_jitters: 1 # 编码重采样次数（越大越精确但越慢）
```

---

## 数据安全与隐私

### 1. 人脸编码存储

- 人脸编码是不可逆的特征向量，无法还原为原始照片
- 使用 BLOB 类型存储，防止直接查看
- 使用 pickle 序列化，确保数据完整性

### 2. 照片存储

- 照片存储在服务器本地文件系统
- 数据库仅存储相对路径
- 建议定期清理过期到访照片

### 3. 数据清理

```python
# 清理过期数据
result = db.cleanup_old_data(
    status_days=7,      # 状态记录保留 7 天
    event_days=30,      # 事件记录保留 30 天
    log_days=90,        # 开锁日志保留 90 天
    media_days=30       # 媒体文件保留 30 天
)
```

---

## 数据库初始化

### 自动初始化

```python
# Database 类会自动创建表结构（开发环境）
db = Database(config, logger, auto_init=True)
```

### 手动初始化（生产环境推荐）

```bash
# 使用迁移脚本
cd main/xiaozhi-server/migrations
python init_database.py
```

---

## 相关文件

### 核心代码

- `main/xiaozhi-server/core/providers/doorlock/database.py` - 数据库操作
- `main/xiaozhi-server/core/providers/doorlock/models.py` - 数据模型
- `main/xiaozhi-server/core/providers/doorlock/face_service.py` - 人脸识别服务

### 配置文件

- `main/xiaozhi-server/config/face_recognition_config.yaml` - 人脸识别配置

### 迁移脚本

- `main/xiaozhi-server/migrations/init_database.py` - 数据库初始化

### 协议文档

- `docs/my_docs/智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md` - 通信协议

---

## 常见问题

### Q1: 人脸编码是什么？

A: 人脸编码是 face_recognition 库提取的 128 维特征向量，用于表示人脸的独特特征。它是不可逆的，无法还原为原始照片。

### Q2: 如何提高识别准确率？

A:

- 注册时使用多张不同角度的照片
- 调整 `tolerance` 参数（降低值提高严格度）
- 增加 `num_jitters` 参数（提高编码质量）
- 确保照片光线充足、人脸清晰

### Q3: 数据库连接池大小如何设置？

A: 默认为 5，可根据并发连接数调整。一般情况下 5-10 足够。

### Q4: 如何备份人脸数据？

A:

```bash
# 备份数据库
mysqldump -u root -p smart_doorlock > backup.sql

# 备份照片目录
tar -czf faces_backup.tar.gz data/face_recognition/
```

---

## 更新日志

| 版本 | 日期       | 说明                             |
| ---- | ---------- | -------------------------------- |
| 1.0  | 2026-02-08 | 初始版本，完整的人脸数据存储文档 |

---

**文档维护者**: Kiro AI Assistant  
**最后更新**: 2026-02-08
