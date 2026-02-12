# 设计文档

## 架构概述

本文档描述智能门锁AI功能的技术设计，包括系统架构、数据模型、API设计和核心算法。

### 系统组件

```
┌─────────────────┐
│   ESP32设备     │
│  ├─ PIR传感器   │
│  ├─ 摄像头      │
│  └─ 扬声器      │
└────────┬────────┘
         │ WebSocket/HTTP
         ↓
┌─────────────────────────────────────┐
│      xiaozhi-server (Python)        │
│  ├─ 意图识别处理器                  │
│  ├─ 看护模式管理器                  │
│  ├─ 人脸识别服务                    │
│  ├─ VLLM服务                        │
│  ├─ 会话管理器                      │
│  └─ 数据库服务                      │
└────────┬────────────────────────────┘
         │ HTTP API
         ↓
┌─────────────────┐
│  manager-api    │
│  (Java后端)     │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   手机App       │
└─────────────────┘
```

### 核心模块

| 模块           | 路径                                               | 职责                           |
| -------------- | -------------------------------------------------- | ------------------------------ |
| 意图识别处理器 | `core/handle/doorlock_intent_handler.py`           | 处理访客对话，生成意图总结     |
| 看护模式管理器 | `core/providers/doorlock/package_guard_manager.py` | 管理看护状态，协调拍照和AI判断 |
| 门锁数据库服务 | `core/providers/doorlock/doorlock_database.py`     | 数据库CRUD操作                 |
| 会话管理器     | `core/providers/doorlock/session_manager.py`       | 管理对话会话生命周期           |
| 门锁工具函数   | `core/providers/doorlock/doorlock_tools.py`        | AI可调用的工具函数             |
| 通知服务       | `core/providers/doorlock/notification_service.py`  | App通知推送                    |

## 数据模型

### 数据库表设计

#### 1. persons 表扩展

```sql
ALTER TABLE persons
ADD COLUMN is_owner BOOLEAN DEFAULT FALSE COMMENT '是否为主人（可取走快递）',
MODIFY COLUMN custom_greeting TEXT COMMENT '欢迎词配置(JSON格式)';
```

**custom_greeting JSON格式**：

```json
{
  "morning": "早上好，张三",
  "afternoon": "下午好，张三",
  "evening": "晚上好，张三",
  "night": "夜深了，张三",
  "default": "欢迎回家"
}
```

#### 2. doorlock_config 表

```sql
CREATE TABLE doorlock_config (
    device_id VARCHAR(50) PRIMARY KEY,
    intent_recognition_enabled BOOLEAN DEFAULT TRUE,
    package_guard_available BOOLEAN DEFAULT TRUE,
    package_guard_active BOOLEAN DEFAULT FALSE,
    package_baseline_image VARCHAR(255),
    package_guard_start_time DATETIME,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 3. doorlock_visitor_intents 表

```sql
CREATE TABLE doorlock_visitor_intents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    visit_id INT,
    session_id VARCHAR(50) NOT NULL,
    person_id INT,
    intent_type VARCHAR(50),
    intent_summary TEXT,
    dialogue_history TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (visit_id) REFERENCES visit_records(id) ON DELETE CASCADE,
    FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 4. doorlock_package_alerts 表

```sql
CREATE TABLE doorlock_package_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    session_id VARCHAR(50) NOT NULL,
    threat_level ENUM('low', 'medium', 'high') NOT NULL,
    action VARCHAR(50),
    description TEXT,
    photo_path VARCHAR(255),
    voice_warning_sent BOOLEAN DEFAULT FALSE,
    notified BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_device_time (device_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### Python数据模型

#### DoorlockConfig

```python
@dataclass
class DoorlockConfig:
    device_id: str
    intent_recognition_enabled: bool = True
    package_guard_available: bool = True
    package_guard_active: bool = False
    package_baseline_image: Optional[str] = None
    package_guard_start_time: Optional[datetime] = None
```

#### VisitorIntent

```python
@dataclass
class VisitorIntent:
    id: Optional[int] = None
    visit_id: Optional[int] = None
    session_id: str = ""
    person_id: Optional[int] = None
    intent_type: str = "other"
    intent_summary: dict = field(default_factory=dict)
    dialogue_history: list = field(default_factory=list)
    created_at: Optional[datetime] = None
```

#### PackageAlert

```python
@dataclass
class PackageAlert:
    id: Optional[int] = None
    device_id: str = ""
    session_id: str = ""
    threat_level: str = "low"
    action: str = "normal"
    description: str = ""
    photo_path: str = ""
    voice_warning_sent: bool = False
    notified: bool = False
    created_at: Optional[datetime] = None
```

## 核心算法

### 1. 会话管理算法

#### 会话ID生成

```python
def generate_session_id(device_id: str) -> str:
    """生成唯一会话ID"""
    timestamp = int(time.time() * 1000)
    return f"{device_id}_{timestamp}"
```

#### 对话结束判定

```python
async def check_dialogue_end(session: DoorlockSession) -> bool:
    """判断对话是否结束"""
    # 条件1：访客沉默超过30秒
    silence_duration = (datetime.now() - session.last_activity).total_seconds()
    if silence_duration > 30:
        return True

    # 条件2：PIR检测不到人体
    if not await pir_detected(session.device_id):
        return True

    return False
```

### 2. 人脸识别重试算法

```python
async def face_recognition_with_retry(device_id: str, max_retries: int = 3) -> dict:
    """人脸识别（支持重试）"""
    for attempt in range(1, max_retries + 1):
        result = await face_service.recognize(device_id)

        if result.success:
            return result

        # 第一次失败时语音提示
        if attempt == 1:
            await tts_service.speak(device_id, "人脸识别失败，请正视摄像头重试")

        # 间隔1秒后重试
        if attempt < max_retries:
            await asyncio.sleep(1)

    # 三次都失败
    await tts_service.speak(device_id, "人脸识别失败，请使用其他方式解锁")
    return {"success": False, "person_id": None}
```

### 3. 欢迎词选择算法

```python
def select_greeting(custom_greeting: dict, current_time: datetime) -> str:
    """根据时段选择欢迎词"""
    hour = current_time.hour

    if 6 <= hour < 12:
        time_slot = "morning"
    elif 12 <= hour < 18:
        time_slot = "afternoon"
    elif 18 <= hour < 22:
        time_slot = "evening"
    else:
        time_slot = "night"

    return custom_greeting.get(time_slot, custom_greeting.get("default", "欢迎回家"))
```

### 4. 看护监控循环算法

```python
async def package_guard_monitoring(device_id: str, session_id: str):
    """看护模式监控循环"""
    while await is_guard_active(device_id) and await pir_detected(device_id):
        # 每5秒拍照一次
        await asyncio.sleep(5)

        # 调用ESP32拍照
        photo_result = await call_esp32_capture(device_id, "判断门口快递状态")

        # 加载基准图片
        baseline_image = await load_baseline_image(device_id)

        # 构建VLLM请求
        vllm_response = await vllm_provider.analyze_package_status(
            current_image=photo_result.image,
            baseline_image=baseline_image,
            dialogue_history=session.dialogue_history,
            prompt=package_guard_prompt
        )

        # 处理AI判断结果
        if vllm_response.tool_calls:
            for tool_call in vllm_response.tool_calls:
                if tool_call.name == "report_package_status":
                    await handle_package_alert(device_id, session_id, tool_call.arguments)
```

### 5. 威胁等级响应算法

```python
async def handle_package_alert(device_id: str, session_id: str, alert_data: dict):
    """处理快递警报"""
    threat_level = alert_data["threat_level"]
    action = alert_data["action"]
    description = alert_data["description"]

    # 保存警报记录
    alert = PackageAlert(
        device_id=device_id,
        session_id=session_id,
        threat_level=threat_level,
        action=action,
        description=description,
        photo_path=await save_alert_photo(device_id)
    )
    await db.save_package_alert(alert)

    # 根据威胁等级响应
    if threat_level == "low":
        # 低威胁：不处理
        pass
    elif threat_level == "medium":
        # 中威胁：语音提示 + App通知
        await tts_service.speak(device_id, "请问有什么可以帮您？")
        await notify_app_package_alert(alert)
        alert.voice_warning_sent = True
        alert.notified = True
    elif threat_level == "high":
        # 高威胁：语音警告 + App通知
        await tts_service.speak(device_id, "您的行为已被记录，请立即停止")
        await notify_app_package_alert(alert)
        alert.voice_warning_sent = True
        alert.notified = True

    await db.update_package_alert(alert)
```

## API设计

### 内部API（Python）

#### 1. DoorlockDatabase类

```python
class DoorlockDatabase:
    """门锁数据库操作"""

    async def get_config(self, device_id: str) -> DoorlockConfig:
        """获取设备配置"""
        pass

    async def update_config(self, config: DoorlockConfig) -> bool:
        """更新设备配置"""
        pass

    async def save_visitor_intent(self, intent: VisitorIntent) -> int:
        """保存访客意图记录"""
        pass

    async def save_package_alert(self, alert: PackageAlert) -> int:
        """保存快递警报记录"""
        pass

    async def get_visitor_intents(self, device_id: str, limit: int = 20) -> List[VisitorIntent]:
        """查询意图识别历史"""
        pass

    async def get_package_alerts(self, device_id: str, limit: int = 20) -> List[PackageAlert]:
        """查询快递警报历史"""
        pass
```

#### 2. PackageGuardManager类

```python
class PackageGuardManager:
    """看护模式管理器"""

    async def enable_guard(self, device_id: str, reason: str) -> bool:
        """启用看护模式"""
        pass

    async def disable_guard(self, device_id: str, reason: str) -> bool:
        """关闭看护模式"""
        pass

    async def update_baseline(self, device_id: str) -> str:
        """更新基准图片"""
        pass

    async def start_monitoring(self, device_id: str, session_id: str):
        """启动监控循环"""
        pass

    async def is_active(self, device_id: str) -> bool:
        """检查看护模式是否激活"""
        pass
```

#### 3. SessionManager类

```python
class SessionManager:
    """会话管理器"""

    def create_session(self, device_id: str) -> DoorlockSession:
        """创建新会话"""
        pass

    def get_session(self, session_id: str) -> Optional[DoorlockSession]:
        """获取会话"""
        pass

    async def cleanup_session(self, session_id: str):
        """清除会话"""
        pass

    async def check_dialogue_end(self, session_id: str) -> bool:
        """检查对话是否结束"""
        pass
```

#### 4. DoorlockIntentHandler类

```python
class DoorlockIntentHandler:
    """意图识别处理器"""

    async def handle_visitor(self, device_id: str, session_id: str):
        """处理访客到访"""
        pass

    async def face_recognition_with_retry(self, device_id: str) -> dict:
        """人脸识别（支持重试）"""
        pass

    async def play_welcome_greeting(self, device_id: str, person_id: int):
        """播放欢迎词"""
        pass

    async def start_intent_dialogue(self, device_id: str, session_id: str, person_info: dict):
        """启动意图识别对话"""
        pass

    async def generate_intent_summary(self, dialogue_history: list) -> dict:
        """生成意图总结"""
        pass
```

#### 5. DoorlockTools类

```python
class DoorlockTools:
    """AI工具函数"""

    async def enable_package_guard(self, device_id: str, reason: str) -> dict:
        """启用快递看护模式"""
        pass

    async def disable_package_guard(self, device_id: str, reason: str) -> dict:
        """关闭快递看护模式"""
        pass

    async def update_package_baseline(self, device_id: str) -> dict:
        """更新看护基准图片"""
        pass

    async def report_package_status(
        self, device_id: str, session_id: str,
        action: str, threat_level: str, description: str
    ) -> dict:
        """报告快递状态"""
        pass

    async def report_visitor_intent(
        self, device_id: str, session_id: str,
        intent_type: str, summary: str, important_notes: list
    ) -> dict:
        """报告访客意图"""
        pass
```

### HTTP API（对外接口）

#### 1. 设备配置API

```
GET /api/doorlock/config?device_id={device_id}
响应：
{
  "success": true,
  "data": {
    "device_id": "device001",
    "intent_recognition_enabled": true,
    "package_guard_available": true,
    "package_guard_active": false
  }
}
```

```
POST /api/doorlock/config
请求体：
{
  "device_id": "device001",
  "intent_recognition_enabled": true,
  "package_guard_available": true
}
响应：
{
  "success": true,
  "message": "配置更新成功"
}
```

#### 2. 看护模式控制API

```
POST /api/doorlock/package_guard/start
请求体：
{
  "device_id": "device001",
  "reason": "手动启动看护"
}
响应：
{
  "success": true,
  "message": "看护模式已启动"
}
```

```
POST /api/doorlock/package_guard/stop
请求体：
{
  "device_id": "device001",
  "reason": "手动停止看护"
}
响应：
{
  "success": true,
  "message": "看护模式已停止"
}
```

#### 3. 欢迎词配置API

```
POST /api/doorlock/welcome/config
请求体：
{
  "person_id": 5,
  "custom_greeting": {
    "morning": "早上好，张三",
    "afternoon": "下午好，张三",
    "evening": "晚上好，张三",
    "night": "夜深了，张三",
    "default": "欢迎回家"
  }
}
响应：
{
  "success": true,
  "message": "欢迎词配置成功"
}
```

#### 4. 历史记录查询API

```
GET /api/doorlock/intents/history?device_id={device_id}&limit=20
响应：
{
  "success": true,
  "data": [
    {
      "id": 123,
      "session_id": "device001_1707379822000",
      "person_id": 5,
      "intent_type": "visit",
      "intent_summary": {...},
      "created_at": "2026-02-08 14:30:22"
    }
  ],
  "total": 100
}
```

```
GET /api/doorlock/alerts/history?device_id={device_id}&limit=20
响应：
{
  "success": true,
  "data": [
    {
      "id": 456,
      "session_id": "device001_1707380410000",
      "threat_level": "high",
      "action": "taking",
      "description": "检测到陌生人拿走快递",
      "created_at": "2026-02-08 15:20:10"
    }
  ],
  "total": 50
}
```

## App通信协议

### 服务器 → App消息

#### 1. 访客意图识别结果通知

```json
{
  "type": "doorlock_visitor_intent",
  "data": {
    "visit_id": 123,
    "session_id": "device001_1707379822000",
    "timestamp": "2026-02-08 14:30:22",
    "person_info": {
      "person_id": 5,
      "name": "张三",
      "relation_type": "friend",
      "photo_path": "visits/2026-02/visit_123.jpg"
    },
    "intent_summary": {
      "important_notes": [
        "【留言】明天下午3点再来拜访",
        "【提醒】带了一份礼物放在门口"
      ],
      "intent_type": "visit",
      "purpose": "拜访朋友，约定明天见面",
      "full_summary": "访客张三来拜访，主人不在家。访客表示明天下午3点会再来，并留下了一份礼物在门口。"
    },
    "dialogue_text": [
      { "role": "assistant", "content": "您好，请问您找谁？" },
      { "role": "user", "content": "我找李四，他在家吗？" }
    ]
  }
}
```

#### 2. 快递异常警报通知

```json
{
  "type": "doorlock_package_alert",
  "data": {
    "alert_id": 456,
    "session_id": "device001_1707380410000",
    "timestamp": "2026-02-08 15:20:10",
    "threat_level": "high",
    "action": "taking",
    "description": "检测到陌生人拿走快递包裹",
    "photo_path": "visits/2026-02/alert_456.jpg",
    "voice_warning_sent": true,
    "voice_warning_text": "您的行为已被记录，请立即停止"
  }
}
```

#### 3. 看护模式状态变化通知

```json
{
  "type": "doorlock_package_guard_status",
  "data": {
    "device_id": "device001",
    "active": true,
    "reason": "有新快递需要看护",
    "baseline_image": "package_baseline/device001_baseline_1707379900.jpg",
    "start_time": "2026-02-08 14:25:00"
  }
}
```

### App → 服务器消息

#### 1. 配置看护模式开关

```json
{
  "type": "doorlock_config_update",
  "data": {
    "device_id": "device001",
    "intent_recognition_enabled": true,
    "package_guard_available": true
  }
}
```

#### 2. 手动控制看护模式

```json
{
  "type": "doorlock_package_guard_control",
  "data": {
    "device_id": "device001",
    "action": "start",
    "reason": "手动启动看护"
  }
}
```

#### 3. 配置欢迎词

```json
{
  "type": "doorlock_welcome_config",
  "data": {
    "person_id": 5,
    "custom_greeting": {
      "morning": "早上好，张三",
      "afternoon": "下午好，张三",
      "evening": "晚上好，张三",
      "night": "夜深了，张三",
      "default": "欢迎回家"
    }
  }
}
```

## AI提示词设计

### 1. 意图识别提示词

存储位置：`config/doorlock_prompts.yaml`

```yaml
intent_recognition_prompt: |
  你是一个智能门锁的AI门卫助手，负责管理门口的访客接待和安全监控。

  你的职责包括：
  1. 识别访客身份并播放个性化欢迎词
  2. 与无权限访客进行礼貌的意图识别对话
  3. 看护门口的快递和外卖，防止被盗或破坏
  4. 记录所有访客信息并通知主人

  你的对话风格：
  - 礼貌正式，但不失亲和力
  - 根据访客身份调整语气（陌生人保持距离，熟人更亲切）
  - 对可疑行为保持警惕，必要时严肃警告

  对话策略：
  - 主动引导对话，明确询问来访目的
  - 使用简洁明了的语言，避免冗长
  - 对重要信息（留言、预约）进行确认
  - 识别推销意图时礼貌拒绝

  你可以调用以下工具：
  1. enable_package_guard(reason: str) - 启用快递看护模式
  2. disable_package_guard(reason: str) - 关闭快递看护模式
  3. update_package_baseline() - 更新看护基准图片
  4. report_visitor_intent(intent_type, summary, important_notes) - 报告访客意图
```

### 2. 看护模式提示词

```yaml
package_guard_prompt: |
  【看护任务】
  你正在看护门口的快递/外卖。你需要通过对比当前图片和基准图片，判断是否有异常行为。

  【威胁等级判断标准】

  低威胁（low）：
  - 路人快速经过（停留时间<3秒）
  - 主人取走快递（person_id对应的is_owner=true）
  - 物业、保洁等工作人员正常工作

  中威胁（medium）：
  - 在门口长时间停留（>10秒）但未触碰快递
  - 翻看快递包装（查看地址、收件人信息）
  - 多次往返门口，行为可疑

  高威胁（high）：
  - 非主人拿走快递（is_owner=false或陌生人）
  - 破坏、踢踹快递包裹
  - 使用工具撬门、撬锁
  - 多人聚集且行为可疑

  【你需要做的】
  1. 对比基准图片和当前图片，判断快递状态变化
  2. 分析人物行为，判断威胁等级
  3. 调用 report_package_status(action, threat_level, description) 报告情况
     - action: "taking"(拿走), "searching"(翻找), "damaging"(破坏), "normal"(正常), "passing"(路过)
     - threat_level: "low", "medium", "high"
     - description: 详细描述你看到的情况

  【基准图片更新】
  - 当你发现门口的物品比基准图片多了（有新快递送达），调用 update_package_baseline()
  - 当你在对话中听到"我把快递放这了"等信息，也调用 update_package_baseline()

  【看护模式控制】
  - 当你判断快递已被主人（is_owner=true）取走，调用 disable_package_guard(reason="主人已取走快递")
  - 当访客提到"快递放门口了"，调用 enable_package_guard(reason="有新快递需要看护")
```

## 工具函数Schema

### 1. enable_package_guard

```json
{
  "name": "enable_package_guard",
  "description": "启用快递看护模式。当访客提到'快递放门口了'、'外卖在这'等信息时调用。",
  "parameters": {
    "type": "object",
    "properties": {
      "reason": {
        "type": "string",
        "description": "启用看护的原因，例如：'有新快递需要看护'"
      }
    },
    "required": ["reason"]
  }
}
```

### 2. disable_package_guard

```json
{
  "name": "disable_package_guard",
  "description": "关闭快递看护模式。当判断快递已被主人（is_owner=true）取走时调用。",
  "parameters": {
    "type": "object",
    "properties": {
      "reason": {
        "type": "string",
        "description": "关闭看护的原因，例如：'主人已取走快递'"
      }
    },
    "required": ["reason"]
  }
}
```

### 3. update_package_baseline

```json
{
  "name": "update_package_baseline",
  "description": "更新看护基准图片。当发现门口有新快递送达时调用。",
  "parameters": {
    "type": "object",
    "properties": {},
    "required": []
  }
}
```

### 4. report_package_status

```json
{
  "name": "report_package_status",
  "description": "报告快递状态和威胁等级。在看护模式下，每次拍照分析后调用此函数报告情况。",
  "parameters": {
    "type": "object",
    "properties": {
      "action": {
        "type": "string",
        "enum": ["taking", "searching", "damaging", "normal", "passing"],
        "description": "行为类型：taking(拿走)、searching(翻找)、damaging(破坏)、normal(正常)、passing(路过)"
      },
      "threat_level": {
        "type": "string",
        "enum": ["low", "medium", "high"],
        "description": "威胁等级：low(低威胁)、medium(中威胁)、high(高威胁)"
      },
      "description": {
        "type": "string",
        "description": "详细描述你看到的情况，包括人物行为、快递状态等"
      }
    },
    "required": ["action", "threat_level", "description"]
  }
}
```

### 5. report_visitor_intent

```json
{
  "name": "report_visitor_intent",
  "description": "报告访客意图。在对话结束时调用此函数，生成结构化总结。",
  "parameters": {
    "type": "object",
    "properties": {
      "intent_type": {
        "type": "string",
        "enum": ["delivery", "visit", "sales", "maintenance", "other"],
        "description": "意图类型：delivery(送快递/外卖)、visit(拜访)、sales(推销)、maintenance(维修/物业)、other(其他)"
      },
      "summary": {
        "type": "string",
        "description": "完整的对话总结，简洁明了地概括访客来访目的和关键信息"
      },
      "important_notes": {
        "type": "array",
        "items": { "type": "string" },
        "description": "重要信息列表，每条以【留言】或【提醒】开头，例如：['【留言】明天下午3点再来', '【提醒】带了礼物放门口']"
      }
    },
    "required": ["intent_type", "summary", "important_notes"]
  }
}
```

## 状态机设计

### 访客处理状态机

```
┌─────────────┐
│  PIR触发    │
└──────┬──────┘
       │
       ↓
┌─────────────────┐
│  人脸识别(1/3)  │
└──────┬──────────┘
       │
       ├─成功→┌──────────────┐
       │      │  有权限？    │
       │      └──┬───────┬───┘
       │         │是     │否
       │         ↓       ↓
       │    ┌────────┐ ┌──────────────┐
       │    │播放欢迎│ │  意图识别    │
       │    │词+开门 │ │  对话流程    │
       │    └────────┘ └──────┬───────┘
       │                      │
       │                      ↓
       │              ┌──────────────┐
       │              │  生成总结    │
       │              │  通知App     │
       │              └──────────────┘
       │
       ├─失败→┌──────────────┐
       │      │  重试(2/3)   │
       │      └──────┬───────┘
       │             │
       │             ├─成功→(同上)
       │             │
       │             ├─失败→┌──────────────┐
       │             │      │  重试(3/3)   │
       │             │      └──────┬───────┘
       │             │             │
       │             │             ├─成功→(同上)
       │             │             │
       │             │             └─失败→┌──────────────┐
       │             │                    │  意图识别    │
       │             │                    │  对话流程    │
       │             │                    └──────────────┘
       │
       └─────────────────────────────────────────────────┘
```

### 看护模式状态机

```
┌─────────────┐
│  看护模式    │
│  未激活      │
└──────┬──────┘
       │
       ├─AI判断需要看护→┌──────────────┐
       │                │  激活看护    │
       │                │  拍摄基准图  │
       │                └──────┬───────┘
       │                       │
       │                       ↓
       │                ┌──────────────┐
       │                │  监控循环    │
       │                │  (每5秒拍照) │
       │                └──────┬───────┘
       │                       │
       │                       ├─PIR检测到人体→┌──────────────┐
       │                       │                │  VLLM分析    │
       │                       │                │  威胁等级    │
       │                       │                └──────┬───────┘
       │                       │                       │
       │                       │                       ├─低威胁→(继续监控)
       │                       │                       │
       │                       │                       ├─中威胁→┌──────────────┐
       │                       │                       │        │  语音提示    │
       │                       │                       │        │  App通知     │
       │                       │                       │        └──────────────┘
       │                       │                       │
       │                       │                       └─高威胁→┌──────────────┐
       │                       │                                │  语音警告    │
       │                       │                                │  App通知     │
       │                       │                                └──────────────┘
       │                       │
       │                       ├─PIR无人体→┌──────────────┐
       │                       │            │  拍摄基准图  │
       │                       │            │  (如有新快递)│
       │                       │            └──────────────┘
       │                       │
       │                       └─主人取走快递→┌──────────────┐
       │                                      │  关闭看护    │
       │                                      │  通知App     │
       │                                      └──────────────┘
       │
       └─手动启动/停止→(激活/关闭看护)
```

## 性能优化策略

### 1. Token消耗优化

- 对话历史保留最近10轮（20条消息）
- 超过限制时自动清理最早的对话
- 记录每次VLLM调用的Token消耗
- 当Token使用量超过模型上限80%时输出警告

### 2. 图片传输优化

- 图片分辨率固定为640x480
- 使用JPEG格式压缩
- 基准图片缓存在内存中，避免重复加载
- 图片文件按日期归档存储

### 3. 数据库查询优化

- 为常用查询字段添加索引（device_id, created_at）
- 使用连接池管理数据库连接
- 批量操作使用事务
- 定期清理过期数据（可选）

### 4. 并发处理优化

- 使用asyncio处理并发请求
- 看护监控和意图识别对话并行执行
- 使用会话隔离避免数据混乱
- 限制同时处理的会话数量

## 错误处理策略

### 1. VLLM服务异常

```python
try:
    response = await vllm_provider.analyze(...)
except VLLMServiceError as e:
    logger.error(f"VLLM服务异常: {e}")
    # 降级处理：跳过本次分析，继续其他流程
    return None
```

### 2. 数据库连接异常

```python
try:
    await db.save_visitor_intent(intent)
except DatabaseError as e:
    logger.error(f"数据库异常: {e}")
    # 重试机制
    for retry in range(3):
        try:
            await db.reconnect()
            await db.save_visitor_intent(intent)
            break
        except:
            if retry == 2:
                logger.error("数据库重连失败，数据未保存")
```

### 3. 拍照失败

```python
try:
    photo = await call_esp32_capture(device_id, question)
except CaptureError as e:
    logger.error(f"拍照失败: {e}")
    # 跳过本次监控，继续下一轮
    return None
```

### 4. App通知失败

```python
try:
    await notify_app(message)
except NotificationError as e:
    logger.error(f"App通知失败: {e}")
    # 记录失败但不影响主流程
    await db.mark_notification_failed(message_id)
```

## 安全性设计

### 1. 数据加密

- 人脸照片存储在服务器本地文件系统
- 对话记录使用JSON格式存储，敏感信息可选择性加密
- 数据库连接使用SSL加密
- API通信使用HTTPS

### 2. 访问控制

- HTTP API需要身份验证（Bearer Token）
- 设备ID验证确保只能访问自己的数据
- 管理员权限控制敏感操作

### 3. 隐私保护

- 在门口明显位置提示"此处有监控录像"
- 用户需同意隐私政策
- 数据仅用于安全监控，不用于其他目的
- 支持用户查询和导出自己的数据

### 4. 数据备份

- 定期备份数据库（建议每日）
- 照片文件定期归档
- 保留最近30天的完整备份
- 支持灾难恢复

## 监控与日志

### 1. 日志级别

- **DEBUG**: 详细的调试信息（开发环境）
- **INFO**: 关键操作记录（生产环境）
- **WARNING**: 警告信息（Token接近上限、重试等）
- **ERROR**: 错误信息（服务异常、数据库错误等）

### 2. 关键日志点

```python
# 会话创建
logger.info(f"创建会话: {session_id}, 设备: {device_id}")

# 人脸识别
logger.info(f"人脸识别成功: {person_name}, 设备: {device_id}")
logger.warning(f"人脸识别失败，第{attempt}次重试")

# 看护模式
logger.info(f"启用看护模式: {device_id}, 原因: {reason}")
logger.info(f"检测到威胁: {threat_level}, 行为: {action}")

# VLLM调用
logger.info(f"VLLM调用统计 | 输入Token: {prompt_tokens} | 输出Token: {completion_tokens}")
logger.warning(f"Token使用量已达 {total_tokens}/{max_tokens}，接近上限")

# 错误处理
logger.error(f"VLLM服务异常: {error_message}")
logger.error(f"数据库连接失败: {error_message}")
```

### 3. 性能指标监控

```python
# 记录关键操作耗时
with timer("人脸识别"):
    result = await face_service.recognize(device_id)

with timer("VLLM分析"):
    response = await vllm_provider.analyze(...)

with timer("数据库保存"):
    await db.save_visitor_intent(intent)
```

## 配置管理

### 配置文件结构

#### 1. config.yaml（主配置）

```yaml
doorlock:
  # 看护模式配置
  package_guard:
    photo_interval: 5 # 拍照间隔（秒）
    baseline_dir: "data/face_recognition/package_baseline/"

  # 意图识别配置
  intent_recognition:
    dialogue_timeout: 30 # 对话超时时间（秒）
    max_dialogue_rounds: 10 # 最大对话轮次

  # 人脸识别配置
  face_recognition:
    max_retries: 3 # 最大重试次数
    retry_interval: 1 # 重试间隔（秒）

  # 性能配置
  performance:
    max_token_usage_ratio: 0.8 # Token使用量警告阈值
    session_cleanup_delay: 0 # 会话清理延迟（秒）
```

#### 2. doorlock_prompts.yaml（提示词配置）

```yaml
# 意图识别提示词
intent_recognition_prompt: |
  你是一个智能门锁的AI门卫助手...

# 看护模式提示词
package_guard_prompt: |
  【看护任务】
  你正在看护门口的快递/外卖...

# 欢迎词模板
welcome_templates:
  - name: "温馨家庭"
    morning: "早上好，{name}"
    afternoon: "下午好，{name}"
    evening: "晚上好，{name}"
    night: "夜深了，{name}"
    default: "欢迎回家"

  - name: "简洁风格"
    default: "欢迎回家，{name}"
```

### 配置加载

```python
class DoorlockConfig:
    """门锁配置管理"""

    def __init__(self):
        self.config = self.load_config()
        self.prompts = self.load_prompts()

    def load_config(self) -> dict:
        """加载主配置"""
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)["doorlock"]

    def load_prompts(self) -> dict:
        """加载提示词配置"""
        with open("config/doorlock_prompts.yaml", "r") as f:
            return yaml.safe_load(f)

    def get(self, key: str, default=None):
        """获取配置项"""
        keys = key.split(".")
        value = self.config
        for k in keys:
            value = value.get(k)
            if value is None:
                return default
        return value
```

## 测试策略

### 1. 单元测试

#### 测试覆盖范围

- 数据库操作（CRUD）
- 会话管理（创建、清除、超时判定）
- 欢迎词选择算法
- 威胁等级判断逻辑
- 工具函数调用

#### 示例测试用例

```python
class TestSessionManager:
    """会话管理器测试"""

    async def test_create_session(self):
        """测试创建会话"""
        manager = SessionManager()
        session = manager.create_session("device001")
        assert session.device_id == "device001"
        assert session.session_id.startswith("device001_")

    async def test_dialogue_timeout(self):
        """测试对话超时判定"""
        session = DoorlockSession("test_session", "device001")
        session.last_activity = datetime.now() - timedelta(seconds=31)
        assert await check_dialogue_end(session) == True

class TestGreetingSelection:
    """欢迎词选择测试"""

    def test_morning_greeting(self):
        """测试早晨欢迎词"""
        greeting = {
            "morning": "早上好",
            "default": "欢迎回家"
        }
        result = select_greeting(greeting, datetime(2026, 2, 8, 8, 0))
        assert result == "早上好"

    def test_default_greeting(self):
        """测试默认欢迎词"""
        greeting = {"default": "欢迎回家"}
        result = select_greeting(greeting, datetime(2026, 2, 8, 8, 0))
        assert result == "欢迎回家"
```

### 2. 集成测试

#### 测试场景

1. **完整访客流程测试**
   - PIR触发 → 人脸识别 → 意图识别 → 生成总结 → 通知App

2. **看护模式流程测试**
   - 启用看护 → 拍照监控 → 威胁检测 → 语音警告 → 关闭看护

3. **人脸识别重试测试**
   - 第1次失败 → 语音提示 → 第2次失败 → 第3次失败 → 进入意图识别

4. **并发访客测试**
   - 多个访客同时到访 → 会话隔离 → 独立处理

### 3. 性能测试

#### 测试指标

- 人脸识别响应时间 < 2秒
- VLLM意图识别响应时间 < 5秒
- 拍照上传耗时 < 1秒
- 看护模式拍照间隔准确性（5秒±0.5秒）
- 对话沉默判定准确性（30秒±1秒）

#### 压力测试

- 连续运行24小时无崩溃
- 看护模式连续监控1小时无异常
- 10个并发会话处理

## 部署方案

### 1. 环境要求

- Python 3.10+
- MySQL 8.0+
- Redis 6.0+（可选，用于缓存）
- 磁盘空间：至少10GB（用于存储照片）

### 2. 依赖安装

```bash
cd main/xiaozhi-server
pip install -r requirements.txt
```

新增依赖：

```
# requirements.txt
face-recognition>=1.3.0
pillow>=10.0.0
aiofiles>=23.0.0
```

### 3. 数据库迁移

```bash
cd main/xiaozhi-server/migrations
python run_doorlock_migration.py
```

### 4. 配置文件

1. 复制配置模板：

```bash
cp config/doorlock_prompts.yaml.example config/doorlock_prompts.yaml
```

2. 修改 `config.yaml`，添加门锁配置：

```yaml
doorlock:
  package_guard:
    photo_interval: 5
    baseline_dir: "data/face_recognition/package_baseline/"
  intent_recognition:
    dialogue_timeout: 30
    max_dialogue_rounds: 10
```

3. 配置数据库连接（`config/face_recognition_config.yaml`）

### 5. 启动服务

```bash
cd main/xiaozhi-server
python app.py
```

### 6. 验证部署

```bash
# 检查数据库表
python migrations/check_database.py

# 测试API
curl http://localhost:8003/api/doorlock/config?device_id=test001
```

## 维护指南

### 1. 日志查看

```bash
# 查看实时日志
tail -f logs/xiaozhi-esp32-api.log

# 查看错误日志
tail -f logs/error.log

# 搜索特定会话日志
grep "session_id" logs/xiaozhi-esp32-api.log
```

### 2. 数据库维护

```bash
# 备份数据库
mysqldump -u root -p smart_doorlock > backup_$(date +%Y%m%d).sql

# 查询统计信息
mysql -u root -p smart_doorlock -e "
SELECT COUNT(*) as total_intents FROM doorlock_visitor_intents;
SELECT COUNT(*) as total_alerts FROM doorlock_package_alerts;
"
```

### 3. 照片文件管理

```bash
# 查看照片存储空间
du -sh data/face_recognition/

# 归档旧照片（保留最近30天）
find data/face_recognition/visits/ -type f -mtime +30 -exec mv {} archive/ \;

# 清理归档（保留90天）
find archive/ -type f -mtime +90 -delete
```

### 4. 性能监控

```bash
# 查看Token消耗统计
grep "VLLM调用统计" logs/xiaozhi-esp32-api.log | tail -20

# 查看响应时间
grep "耗时" logs/xiaozhi-esp32-api.log | tail -20

# 查看错误率
grep "ERROR" logs/error.log | wc -l
```

## 未来扩展

### 1. 短期扩展（1-3个月）

#### 图像差异检测优化

- 在服务器端先做简单的图像差异检测
- 只有变化较大时才调用VLLM
- 减少API调用次数和成本

#### 多快递管理

- 支持同时看护多个快递
- 维护快递数量计数
- 识别快递被部分拿走的情况

#### 访客预约功能

- 支持访客在对话中预约时间
- 自动添加到日历提醒
- 预约时间到达时通知主人

### 2. 中期扩展（3-6个月）

#### 智能学习

- 学习用户习惯，自动调整看护策略
- 识别常见访客（快递员、保洁等）
- 根据历史数据优化威胁等级判断

#### 访客黑名单

- 支持将可疑访客加入黑名单
- 黑名单访客到访时立即警报
- 自动拒绝黑名单访客的对话请求

#### 多设备联动

- 支持多个门锁设备协同工作
- 设备间共享访客信息
- 统一的看护模式管理

### 3. 长期扩展（6个月以上）

#### 边缘计算

- 将部分AI能力下沉到ESP32设备
- 本地进行简单的图像分析
- 减少云端依赖，提高响应速度

#### 多模态融合

- 结合声纹识别增强身份验证
- 结合行为分析（步态、动作）
- 结合环境感知（光线、温度）

#### 开放生态

- 提供开放API给第三方应用
- 支持自定义插件开发
- 建立开发者社区和文档

## 参考文档

- `docs/my_docs/smart-doorlock-ai-requirements.md` - 完整需求规格说明
- `docs/my_docs/esp32-vision-guide.md` - ESP32视觉功能使用指南
- `docs/my_docs/face-data-storage-documentation.md` - 人脸数据存储文档
- `docs/my_docs/智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md` - 通信协议规范
- `main/xiaozhi-server/agent-base-prompt.txt` - Agent提示词参考

## 变更历史

| 版本 | 日期       | 说明         | 作者              |
| ---- | ---------- | ------------ | ----------------- |
| v1.0 | 2026-02-08 | 初始设计文档 | Kiro AI Assistant |

---

**文档维护者**: Kiro AI Assistant  
**最后更新**: 2026-02-08  
**状态**: 设计完成，待实现
