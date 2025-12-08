# Design Document

## Overview

智能门锁人脸识别模块设计，基于 face_recognition 库实现人脸检测、编码和比对功能。系统采用 WebSocket 通信，复用现有的 xiaozhi-server 架构。

### 核心流程

```
ESP32 拍照 → JSON(BinaryProtocol2封装JPEG) → 服务器解析 → 人脸检测 → 编码比对 → 权限验证 → TTS语音 + JSON响应
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        WebSocket Server                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │ faceRecognitionHandler │──▶│      FaceService               │ │
│  │ (消息路由)            │    │  ┌─────────────────────────┐   │ │
│  └─────────────────────┘    │  │ recognize()             │   │ │
│                              │  │ register_face()         │   │ │
│                              │  │ check_permission()      │   │ │
│                              │  │ generate_greeting()     │   │ │
│                              │  └─────────────────────────┘   │ │
│                              └──────────────┬──────────────────┘ │
│                                             │                    │
│  ┌─────────────────────┐    ┌──────────────▼──────────────────┐ │
│  │      TTS Module      │◀───│         Database               │ │
│  │ (复用现有)           │    │  ┌─────────────────────────┐   │ │
│  └─────────────────────┘    │  │ persons                 │   │ │
│                              │  │ access_permissions      │   │ │
│                              │  │ visit_records           │   │ │
│                              │  └─────────────────────────┘   │ │
│                              └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. FaceRecognitionHandler (消息处理器)

位置：`core/handle/textHandler/faceRecognitionHandler.py`

```python
class FaceRecognitionHandler(TextMessageHandler):
    """处理 face_recognition 和 face_management 类型消息"""
    
    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        msg_type = msg_json.get("type")
        if msg_type == "face_recognition":
            await self._handle_recognition(conn, msg_json)
        elif msg_type == "face_management":
            await self._handle_management(conn, msg_json)
```

### 2. FaceService (核心服务)

位置：`core/providers/doorlock/face_service.py`

```python
class FaceService:
    """人脸识别核心服务"""
    
    def __init__(self, config: dict):
        self.db = Database(config['database'])
        self.tolerance = config.get('tolerance', 0.6)
        self.greetings = config.get('greetings', {})
    
    def parse_image(self, image_data: str) -> bytes:
        """解析 BinaryProtocol2 格式的图像数据"""
        
    def recognize(self, jpeg_data: bytes) -> RecognitionResult:
        """执行人脸识别"""
        
    def register_face(self, name: str, relation: str, images: List[bytes], permission: dict) -> int:
        """录入人脸"""
        
    def check_permission(self, person_id: int, current_time: datetime) -> Tuple[bool, str]:
        """验证开门权限"""
        
    def generate_greeting(self, result: RecognitionResult, access_granted: bool, deny_reason: str) -> str:
        """生成问候语"""
```

### 3. Database (数据库操作)

位置：`core/providers/doorlock/database.py`

```python
class Database:
    """MySQL 数据库操作"""
    
    def __init__(self, config: dict):
        self.pool = mysql.connector.pooling.MySQLConnectionPool(...)
    
    def init_tables(self):
        """初始化数据库表"""
        
    def save_person(self, person: Person) -> int:
        """保存人员信息"""
        
    def get_all_encodings(self) -> List[Tuple[int, np.ndarray]]:
        """获取所有人脸编码用于比对"""
        
    def serialize_encoding(self, encoding: np.ndarray) -> bytes:
        """序列化人脸编码"""
        
    def deserialize_encoding(self, data: bytes) -> np.ndarray:
        """反序列化人脸编码"""
```

## Data Models

位置：`core/providers/doorlock/models.py`

```python
@dataclass
class Person:
    id: Optional[int]
    name: str
    relation_type: str  # family, friend, colleague, property, courier, delivery, tutor, classmate, other
    face_encoding: np.ndarray
    photo_path: str
    custom_greeting: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class AccessPermission:
    id: Optional[int]
    person_id: int
    permission_type: str  # permanent, temporary
    time_start: time
    time_end: time
    day_type: str  # daily, weekly, monthly
    week_days: Optional[str] = None  # "1,2,3,4,5"
    month_days: Optional[str] = None  # "1,15,30"
    remaining_count: int = 1
    valid_from: date = None
    valid_until: date = None
    is_active: bool = True

@dataclass
class VisitRecord:
    id: Optional[int]
    person_id: Optional[int]
    recognition_result: str  # known, unknown, no_face
    access_granted: bool
    deny_reason: Optional[str]
    photo_path: str
    visit_time: datetime
    notified: bool = False

@dataclass
class RecognitionResult:
    result: str  # known, unknown, no_face
    person: Optional[Person] = None
    confidence: float = 0.0
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: BinaryProtocol2 解析正确性

*For any* 有效的 BinaryProtocol2 格式数据（包含 JPEG payload），解析后提取的 JPEG 数据应与原始 payload 完全一致。

**Validates: Requirements 1.1**

### Property 2: 人脸编码序列化 round-trip

*For any* 128 维 numpy 数组（人脸编码），序列化后再反序列化应得到数值相等的数组。

**Validates: Requirements 7.3, 7.4**

### Property 3: 问候语包含姓名

*For any* 关系类型和非空姓名，生成的问候语字符串应包含该姓名。

**Validates: Requirements 2.1**

### Property 4: 时段权限验证正确性

*For any* 时段配置（time_start, time_end）和当前时间，权限验证结果应正确反映当前时间是否在时段内。

**Validates: Requirements 3.1**

### Property 5: 按周权限验证正确性

*For any* 允许的星期列表和当前星期几，权限验证结果应正确反映当前星期几是否在允许列表中。

**Validates: Requirements 3.2**

### Property 6: 按月权限验证正确性

*For any* 允许的日期列表和当前日期，权限验证结果应正确反映当前日期是否在允许列表中。

**Validates: Requirements 3.3**

### Property 7: 临时权限次数扣减

*For any* 临时权限（remaining_count > 0），验证通过后 remaining_count 应减少 1。

**Validates: Requirements 3.4, 3.5**

## Error Handling

| 错误场景 | 处理方式 |
|---------|---------|
| 图像解码失败 | 返回 `{"status": "error", "error": "invalid_image"}` |
| 数据库连接失败 | 记录日志，返回 `{"status": "error", "error": "database_error"}` |
| 人脸检测失败 | 返回 `{"result": "no_face"}` |
| 权限配置无效 | 返回 `{"status": "error", "error": "invalid_permission"}` |

## Testing Strategy

### 单元测试

使用 pytest 框架：

1. `test_parse_image()` - 测试 BinaryProtocol2 解析
2. `test_serialize_encoding()` - 测试编码序列化/反序列化
3. `test_generate_greeting()` - 测试问候语生成
4. `test_check_permission_*()` - 测试各类权限验证

### 属性测试

使用 hypothesis 库进行属性测试：

```python
from hypothesis import given, strategies as st

@given(st.binary(min_size=100))
def test_binary_protocol_roundtrip(payload):
    """Property 1: BinaryProtocol2 解析正确性"""
    # 构造 BinaryProtocol2 格式数据
    # 解析并验证 payload 一致
    
@given(st.lists(st.floats(allow_nan=False, allow_infinity=False), min_size=128, max_size=128))
def test_encoding_roundtrip(encoding_list):
    """Property 2: 人脸编码序列化 round-trip"""
    encoding = np.array(encoding_list)
    serialized = serialize_encoding(encoding)
    deserialized = deserialize_encoding(serialized)
    assert np.allclose(encoding, deserialized)
```

### 测试配置

- 属性测试最小运行 100 次迭代
- 每个属性测试需标注对应的 Correctness Property
