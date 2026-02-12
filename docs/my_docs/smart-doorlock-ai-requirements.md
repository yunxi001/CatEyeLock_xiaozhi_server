# 智能门锁AI功能需求规格说明

## 文档信息

- **版本**: v1.0
- **创建日期**: 2026-02-08
- **状态**: 待实现
- **优先级**: 高

---

## 一、功能概述

本需求旨在为智能门锁系统增加两大AI核心功能：

1. **快递/外卖看护模式**：通过视觉AI监控门口快递，检测异常行为并实时警报
2. **访客意图识别**：基于人脸识别和视觉对话，自动识别访客意图并通知主人

---

## 二、核心功能需求

### 2.1 快递/外卖看护模式

#### 2.1.1 功能描述

当用户门口有快递或外卖时，系统通过视觉AI持续监控，检测可疑行为（翻找、拿走、破坏等），并根据威胁等级进行语音警告和App通知。

#### 2.1.2 触发机制

- **启用条件**：用户在App中开启"看护模式可用"开关
- **激活方式**：由AI在意图识别对话中自动判断是否需要激活
  - 示例场景：快递员说"我把快递放门口了"，AI判断需要看护，自动激活看护模式
- **手动控制**：支持通过App手动启动/停止看护模式

#### 2.1.3 工作流程

**注意**：看护模式只有在"看护模式可用"开关启用，且"看护模式已激活"的情况下才会执行监控。

```
PIR触发（检测到人体）
→ 等待5秒（过滤路人）
→ 启动人脸识别流程（最多3次重试）
→ 进入意图识别模式（VLLM + 对话）
→ 如果看护模式已激活，同时启动看护监控：
   - 每5秒拍照一次
   - 将照片 + 基准图片 + 提示词发送给VLLM
   - AI判断威胁等级和行为类型
   - 根据威胁等级执行相应动作（语音警告 + App通知）
→ PIR检测不到人体
→ 拍摄新的基准图片（如果AI判断有新快递）
→ 立即清除会话
```

#### 2.1.4 威胁等级定义

| 威胁等级   | 判断标准                                                                                        | 语音提醒内容                   | 通知App |
| ---------- | ----------------------------------------------------------------------------------------------- | ------------------------------ | ------- |
| **低威胁** | - 路人快速经过（停留<3秒）<br>- 主人取走快递（is_owner=true）<br>- 物业、保洁等工作人员正常工作 | 不提醒或轻提醒："已记录"       | 否      |
| **中威胁** | - 在门口长时间停留（>10秒）但未触碰快递<br>- 翻看快递包装（查看地址、收件人）<br>- 多次往返门口 | "请问有什么可以帮您？"         | 是      |
| **高威胁** | - 非主人拿走快递<br>- 破坏、踢踹快递<br>- 使用工具撬门、撬锁<br>- 多人聚集且行为可疑            | "您的行为已被记录，请立即停止" | 是      |

#### 2.1.5 基准图片管理

- **拍摄时机**：PIR检测不到人体后（访客离开）
- **更新条件**：
  1. AI通过对比图片判断有新快递送达
  2. AI在对话中识别到"我把快递放这了"等关键信息
- **存储位置**：文件系统 `data/face_recognition/package_baseline/`
- **命名规则**：`device_{device_id}_baseline_{timestamp}.jpg`

#### 2.1.6 关闭条件

- **自动关闭**：AI判断快递已被主人取走（is_owner=true的人拿走）
- **手动关闭**：用户通过App手动停止
- **通知方式**：关闭时发送App通知
- **重要说明**：主人回家（有开门权限的用户识别成功）时，看护模式继续运行，不会自动关闭，必须等待快递被取走或手动关闭

---

### 2.2 访客意图识别

#### 2.2.1 功能描述

当有访客到访时，系统通过人脸识别确定身份，根据权限播放个性化欢迎词或进行意图识别对话，最终生成结构化总结并通知主人。

#### 2.2.2 触发条件

- PIR检测到人体
- 有人按门铃（如果有门铃功能）

#### 2.2.3 工作流程

**【有开门权限访客】**

```
PIR触发
→ 人脸识别成功（识别为有权限用户）
→ 播放个性化欢迎词（根据时段选择）
→ 自动开门
→ 结束
```

**【无开门权限访客】**

```
PIR触发
→ 人脸识别（第1次）
   ├─ 失败 → 语音提示"人脸识别失败，请正视摄像头重试"
   └─ 间隔1秒 → 重试（第2次）
      ├─ 失败 → 间隔1秒 → 重试（第3次）
      └─ 失败 → 语音提示"人脸识别失败，请使用其他方式解锁"
→ 立即主动问候："您好，请问有什么可以帮您？"
→ 进入意图识别对话（VLLM + 语音交互）
   - 如果识别出陌生人：先询问"请问您找谁？"
   - 如果识别出已注册但无权限的人：根据身份调整对话策略
→ 对话持续进行，直到：
   - 访客沉默超过30秒
   - PIR检测不到人体（访客离开）
→ 生成结构化总结
→ 发送App通知（包含人脸照片、对话文字、意图摘要）
→ 立即清除会话
```

**【看护模式激活时】**

```
PIR触发
→ 人脸识别流程（同上，最多3次重试）
→ 立即主动问候并进入意图识别对话
→ 同时启动看护监控（每5秒拍照 + AI判断）
→ 对话结束 + PIR检测不到人体
→ 生成总结 → 通知App
→ 拍摄基准图片（如有新快递）
→ 立即清除会话
```

#### 2.2.4 个性化欢迎词

**数据结构**（存储在 `persons.custom_greeting` 字段，JSON格式）：

```json
{
  "morning": "早上好，张三",
  "afternoon": "下午好，张三",
  "evening": "晚上好，张三",
  "night": "夜深了，张三",
  "default": "欢迎回家"
}
```

**时段划分**：

- 早晨（morning）：6:00 - 12:00
- 下午（afternoon）：12:00 - 18:00
- 晚上（evening）：18:00 - 22:00
- 夜间（night）：22:00 - 6:00

**配置方式**：

- 在App中为每个用户配置
- 提供预设模板供用户选择
- 支持自定义文本

#### 2.2.5 意图识别对话策略

**AI角色定位**：智能门卫助手

**对话风格**：礼貌正式，但根据访客身份调整语气

- 对陌生人：礼貌但保持距离
- 对已识别但无权限的人：根据关系类型调整（朋友、同事、快递员等）
- 对可疑人员：严肃警告

**对话目标**：

1. 了解访客来访目的
2. 记录留言和重要信息
3. 帮助预约时间（如需要）
4. 识别并拒绝推销

**对话时长**：无限制，直到访客停止对话或离开

#### 2.2.6 对话总结格式

**结构化总结**（JSON格式）：

```json
{
  "important_notes": [
    "【留言】明天下午3点再来拜访",
    "【提醒】带了一份礼物放在门口"
  ],
  "intent_type": "visit",
  "purpose": "拜访朋友，约定明天见面",
  "full_summary": "访客张三来拜访，主人不在家。访客表示明天下午3点会再来，并留下了一份礼物在门口。"
}
```

**intent_type 类型**：

- `delivery`：送快递/外卖
- `visit`：拜访
- `sales`：推销
- `maintenance`：维修/物业
- `other`：其他

**生成要求**：

- 重要信息（留言、提醒）必须显著标注并放在开头
- 总结需简洁明了，突出关键信息
- 如果访客不配合或沉默，也需要生成总结说明情况

---

## 三、技术实现方案

### 3.1 系统架构

#### 3.1.1 组件关系

```
ESP32设备
  ├─ PIR传感器（人体检测）
  ├─ 摄像头（拍照）
  └─ 麦克风/扬声器（语音交互）
       ↓ WebSocket/HTTP
xiaozhi-server
  ├─ 人脸识别服务（face_service）
  ├─ VLLM服务（视觉语言模型）
  ├─ 意图识别处理器（doorlock_intent_handler）
  ├─ 看护模式管理器（package_guard_manager）
  └─ 数据库（MySQL）
       ↓ HTTP API
manager-api（Java后端）
  └─ App通知推送
       ↓
手机App
```

#### 3.1.2 核心模块

| 模块           | 路径                                               | 职责                                       |
| -------------- | -------------------------------------------------- | ------------------------------------------ |
| 意图识别处理器 | `core/handle/doorlock_intent_handler.py`           | 处理访客对话，生成意图总结                 |
| 看护模式管理器 | `core/providers/doorlock/package_guard_manager.py` | 管理看护状态，协调拍照和AI判断             |
| 门锁数据库服务 | `core/providers/doorlock/doorlock_database.py`     | 扩展现有Database类，新增门锁相关表操作     |
| 门锁AI提示词   | `config/doorlock_prompts.yaml`                     | 存储意图识别和看护模式的提示词             |
| 门锁工具函数   | `plugins_func/functions/doorlock_tools.py`         | 定义AI可调用的工具（看护控制、通知发送等） |

### 3.2 数据库设计

#### 3.2.1 修改现有表

**persons 表**（新增字段）：

```sql
ALTER TABLE persons
ADD COLUMN is_owner BOOLEAN DEFAULT FALSE COMMENT '是否为主人（可取走快递）',
MODIFY COLUMN custom_greeting TEXT COMMENT '欢迎词配置(JSON格式，支持分时段)';
```

#### 3.2.2 新建表

**doorlock_config 表**（设备配置）：

```sql
CREATE TABLE doorlock_config (
    device_id VARCHAR(50) PRIMARY KEY,
    intent_recognition_enabled BOOLEAN DEFAULT TRUE COMMENT '是否启用意图识别',
    package_guard_available BOOLEAN DEFAULT TRUE COMMENT '是否可使用看护模式',
    package_guard_active BOOLEAN DEFAULT FALSE COMMENT '看护模式是否激活中',
    package_baseline_image VARCHAR(255) COMMENT '看护基准图片路径',
    package_guard_start_time DATETIME COMMENT '看护开始时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**doorlock_visitor_intents 表**（意图识别记录）：

```sql
CREATE TABLE doorlock_visitor_intents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    visit_id INT COMMENT '关联的到访记录ID',
    session_id VARCHAR(50) NOT NULL COMMENT '会话ID（基于时间戳）',
    person_id INT COMMENT '识别到的人员ID（陌生人为NULL）',
    intent_type VARCHAR(50) COMMENT '意图类型（delivery/visit/sales等）',
    intent_summary TEXT COMMENT '意图总结(JSON格式)',
    dialogue_history TEXT COMMENT '对话历史(JSON格式)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (visit_id) REFERENCES visit_records(id) ON DELETE CASCADE,
    FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**doorlock_package_alerts 表**（快递警报记录）：

```sql
CREATE TABLE doorlock_package_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    session_id VARCHAR(50) NOT NULL COMMENT '会话ID',
    threat_level ENUM('low', 'medium', 'high') NOT NULL COMMENT '威胁等级',
    action VARCHAR(50) COMMENT '行为类型（taking/searching/damaging/normal）',
    description TEXT COMMENT 'AI判断描述',
    photo_path VARCHAR(255) COMMENT '证据照片路径',
    voice_warning_sent BOOLEAN DEFAULT FALSE COMMENT '是否已语音警告',
    notified BOOLEAN DEFAULT FALSE COMMENT '是否已通知App',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_device_time (device_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 3.3 AI提示词设计

#### 3.3.1 意图识别提示词

**基础身份**（参考 `agent-base-prompt.txt` 结构）：

```yaml
identity: |
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

communication_style: |
  - 主动引导对话，明确询问来访目的
  - 使用简洁明了的语言，避免冗长
  - 对重要信息（留言、预约）进行确认
  - 识别推销意图时礼貌拒绝

tool_calling: |
  你可以调用以下工具：

  1. enable_package_guard(reason: str)
     - 启用快递看护模式
     - 当访客提到"快递放门口"、"外卖在这"等信息时调用

  2. disable_package_guard(reason: str)
     - 关闭快递看护模式
     - 当判断快递已被主人取走时调用

  3. update_package_baseline()
     - 更新看护基准图片
     - 当发现门口有新快递送达时调用

  4. report_visitor_intent(intent_type: str, summary: str, important_notes: list)
     - 报告访客意图（对话结束时自动调用）
     - intent_type: delivery/visit/sales/maintenance/other
     - important_notes: 留言、提醒等重要信息列表
```

#### 3.3.2 看护模式提示词

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

### 3.4 拍照接口实现

#### 3.4.1 ESP32拍照接口

**参考文档**：`docs/my_docs/esp32-vision-guide.md`

**调用方式**：通过MCP协议调用ESP32的 `capture_image` 工具

```json
{
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "capture_image",
      "arguments": {
        "question": "判断门口快递状态"
      }
    }
  }
}
```

**图片上传**：ESP32通过HTTP POST上传到 `/mcp/vision/explain`

```
POST /mcp/vision/explain
Content-Type: multipart/form-data

字段：
- question: "判断门口快递状态"
- image: <JPEG图片数据，640x480>
- dialogue: [对话历史]（可选）
- timestamp: "2026-02-08 14:30:22"（图片时间戳）
```

#### 3.4.2 看护模式拍照流程

```python
# 伪代码示例
async def package_guard_monitoring(device_id: str, session_id: str):
    """看护模式监控循环"""
    while pir_detected and package_guard_active:
        # 每5秒拍照一次
        await asyncio.sleep(5)

        # 调用ESP32拍照
        photo_result = await call_esp32_capture(device_id, "判断门口快递状态")

        # 加载基准图片
        baseline_image = load_baseline_image(device_id)

        # 构建VLLM请求（包含当前图片和基准图片）
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
                    await handle_package_alert(
                        device_id, session_id,
                        tool_call.arguments
                    )
```

### 3.5 会话管理

#### 3.5.1 会话ID生成

```python
import time

def generate_session_id(device_id: str) -> str:
    """生成会话ID（基于时间戳）"""
    timestamp = int(time.time() * 1000)  # 毫秒级时间戳
    return f"{device_id}_{timestamp}"
```

#### 3.5.2 会话生命周期

```python
class DoorlockSession:
    """门锁会话管理"""

    def __init__(self, session_id: str, device_id: str):
        self.session_id = session_id
        self.device_id = device_id
        self.dialogue_history = []  # 对话历史
        self.photos = []  # 拍照记录
        self.person_id = None  # 识别到的人员ID
        self.created_at = datetime.now()
        self.last_activity = datetime.now()

    async def cleanup(self):
        """清除会话（PIR检测不到人体时立即调用）"""
        # 生成对话总结
        summary = await generate_intent_summary(self.dialogue_history)

        # 保存到数据库
        await save_visitor_intent(
            session_id=self.session_id,
            person_id=self.person_id,
            intent_summary=summary,
            dialogue_history=self.dialogue_history
        )

        # 通知App
        await notify_app_visitor_intent(self.device_id, summary)

        # 清除内存
        self.dialogue_history.clear()
        self.photos.clear()
```

#### 3.5.3 对话结束判定

```python
async def check_dialogue_end(session: DoorlockSession) -> bool:
    """判断对话是否结束"""

    # 条件1：访客沉默超过30秒
    silence_duration = (datetime.now() - session.last_activity).total_seconds()
    if silence_duration > 30:
        logger.info(f"会话 {session.session_id} 因访客沉默30秒而结束")
        return True

    # 条件2：PIR检测不到人体（访客离开）
    if not pir_detected(session.device_id):
        logger.info(f"会话 {session.session_id} 因PIR检测不到人体而结束")
        return True

    return False
```

### 3.6 AI工具函数定义

#### 3.6.1 工具函数实现位置

**内置功能**（不作为插件）：`core/providers/doorlock/doorlock_tools.py`

#### 3.6.2 工具函数列表

```python
# 看护模式控制
async def enable_package_guard(device_id: str, reason: str) -> dict:
    """启用快递看护模式"""
    pass

async def disable_package_guard(device_id: str, reason: str) -> dict:
    """关闭快递看护模式"""
    pass

async def update_package_baseline(device_id: str) -> dict:
    """更新看护基准图片"""
    pass

# 状态报告
async def report_package_status(
    device_id: str,
    session_id: str,
    action: str,  # taking/searching/damaging/normal/passing
    threat_level: str,  # low/medium/high
    description: str
) -> dict:
    """报告快递状态（AI判断结果）"""
    pass

async def report_visitor_intent(
    device_id: str,
    session_id: str,
    intent_type: str,  # delivery/visit/sales/maintenance/other
    summary: str,
    important_notes: list
) -> dict:
    """报告访客意图（对话结束时调用）"""
    pass
```

#### 3.6.3 工具Schema定义

```python
DOORLOCK_TOOLS_SCHEMA = [
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
    },
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
    },
    {
        "name": "update_package_baseline",
        "description": "更新看护基准图片。当发现门口有新快递送达时调用。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
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
    },
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
                    "items": {"type": "string"},
                    "description": "重要信息列表，每条以【留言】或【提醒】开头，例如：['【留言】明天下午3点再来', '【提醒】带了礼物放门口']"
                }
            },
            "required": ["intent_type", "summary", "important_notes"]
        }
    }
]
```

### 3.7 App通信协议

#### 3.7.1 新增消息类型（服务器 → App）

**访客意图识别结果通知**：

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
      { "role": "user", "content": "我找李四，他在家吗？" },
      {
        "role": "assistant",
        "content": "主人暂时不在家，请问有什么需要转达的吗？"
      },
      {
        "role": "user",
        "content": "那我明天下午3点再来吧，我给他带了份礼物放门口了"
      }
    ]
  }
}
```

**快递异常警报**：

```json
{
  "type": "doorlock_package_alert",
  "data": {
    "alert_id": 456,
    "session_id": "device001_1707380410000",
    "timestamp": "2026-02-08 15:20:10",
    "threat_level": "high",
    "action": "taking",
    "description": "检测到陌生人拿走快递包裹，该人员未在系统中注册",
    "photo_path": "visits/2026-02/alert_456.jpg",
    "voice_warning_sent": true,
    "voice_warning_text": "您的行为已被记录，请立即停止"
  }
}
```

**看护模式状态变化通知**：

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

#### 3.7.2 新增消息类型（App → 服务器）

**配置看护模式开关**：

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

**手动控制看护模式**：

```json
{
  "type": "doorlock_package_guard_control",
  "data": {
    "device_id": "device001",
    "action": "start", // start 或 stop
    "reason": "手动启动看护"
  }
}
```

**配置欢迎词**：

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

### 3.8 人脸识别重试机制

#### 3.8.1 重试流程

```python
async def face_recognition_with_retry(device_id: str, max_retries: int = 3) -> dict:
    """人脸识别（支持重试）"""

    for attempt in range(1, max_retries + 1):
        logger.info(f"设备 {device_id} 人脸识别第 {attempt} 次尝试")

        # 执行人脸识别
        result = await face_service.recognize(device_id)

        if result.success:
            logger.info(f"人脸识别成功：{result.person_name}")
            return result

        # 第一次失败时语音提示
        if attempt == 1:
            await tts_service.speak(
                device_id,
                "人脸识别失败，请正视摄像头重试"
            )

        # 间隔1秒后重试
        if attempt < max_retries:
            await asyncio.sleep(1)

    # 三次都失败
    logger.warning(f"设备 {device_id} 人脸识别失败3次")
    await tts_service.speak(
        device_id,
        "人脸识别失败，请使用其他方式解锁"
    )

    return {"success": False, "person_id": None}
```

### 3.10 ESP32端改动说明

#### 3.10.1 当前状态

根据需求讨论，STM32端的PIR触发时间缩短功能**暂不实现**，保持现有机制不变。

#### 3.10.2 ESP32端保持不变

- ESP32端的人脸识别流程保持不变
- 拍照功能已存在，通过MCP协议调用
- 图片分辨率：640x480
- 上传接口：HTTP POST `/mcp/vision/explain`

#### 3.10.3 未来可能的优化

如果后续需要优化PIR触发机制，可以考虑：

- 在看护模式下缩短PIR触发间隔（从当前值缩短到5秒）
- 通过服务器下发配置参数动态调整
- 需要STM32固件升级支持

#### 3.9.1 Token消耗日志

```python
async def log_vllm_usage(session_id: str, response: dict):
    """记录VLLM调用的Token消耗"""

    if "usage" in response:
        usage = response["usage"]
        logger.info(
            f"会话 {session_id} VLLM调用统计 | "
            f"输入Token: {usage.get('prompt_tokens', 0)} | "
            f"输出Token: {usage.get('completion_tokens', 0)} | "
            f"总计: {usage.get('total_tokens', 0)}"
        )

        # 检查是否接近上下文限制
        max_tokens = 8000  # 根据实际模型调整
        if usage.get('total_tokens', 0) > max_tokens * 0.8:
            logger.warning(
                f"会话 {session_id} Token使用量已达 "
                f"{usage.get('total_tokens', 0)}/{max_tokens}，"
                f"接近上限，建议清理对话历史"
            )
```

#### 3.9.2 性能指标

需要记录的关键指标：

- 人脸识别耗时
- VLLM响应时间
- 拍照上传耗时
- 对话轮次和Token消耗
- 看护模式拍照频率

### 3.10 ESP32端改动说明

#### 3.10.1 当前状态

根据需求讨论，STM32端的PIR触发时间缩短功能**暂不实现**，保持现有机制不变。

#### 3.10.2 ESP32端保持不变

- ESP32端的人脸识别流程保持不变
- 拍照功能已存在，通过MCP协议调用
- 图片分辨率：640x480
- 上传接口：HTTP POST `/mcp/vision/explain`

#### 3.10.3 未来可能的优化

如果后续需要优化PIR触发机制，可以考虑：

- 在看护模式下缩短PIR触发间隔（从当前值缩短到5秒）
- 通过服务器下发配置参数动态调整
- 需要STM32固件升级支持

---

## 四、实现任务分解

### 4.1 数据库层（优先级：高）

**任务1：扩展数据库表结构**

- [ ] 修改 `persons` 表，新增 `is_owner` 和 `custom_greeting` 字段
- [ ] 创建 `doorlock_config` 表
- [ ] 创建 `doorlock_visitor_intents` 表
- [ ] 创建 `doorlock_package_alerts` 表
- [ ] 编写数据库迁移脚本 `migrations/add_doorlock_tables.sql`
- [ ] 编写迁移执行脚本 `migrations/run_doorlock_migration.py`

**任务2：扩展数据库操作接口**

- [ ] 在 `core/providers/doorlock/doorlock_database.py` 中实现新表的CRUD操作
- [ ] 实现欢迎词的JSON序列化/反序列化
- [ ] 实现看护模式状态管理
- [ ] 实现意图识别记录查询

**预计工作量**：4-6小时

### 4.2 AI提示词层（优先级：高）

**任务3：设计门锁AI提示词**

- [ ] 创建 `config/doorlock_prompts.yaml` 配置文件
- [ ] 编写意图识别提示词（参考 `agent-base-prompt.txt` 结构）
- [ ] 编写看护模式提示词（威胁等级判断标准）
- [ ] 定义工具调用说明
- [ ] 设计不同场景的对话策略

**预计工作量**：3-4小时

### 4.3 工具函数层（优先级：高）

**任务4：实现门锁AI工具函数**

- [ ] 创建 `core/providers/doorlock/doorlock_tools.py`
- [ ] 实现 `enable_package_guard()` - 启用看护模式
- [ ] 实现 `disable_package_guard()` - 关闭看护模式
- [ ] 实现 `update_package_baseline()` - 更新基准图片
- [ ] 实现 `report_package_status()` - 报告快递状态
- [ ] 实现 `report_visitor_intent()` - 报告访客意图
- [ ] 定义工具Schema（供VLLM调用）

**预计工作量**：4-5小时

### 4.4 会话管理层（优先级：高）

**任务5：实现门锁会话管理**

- [ ] 创建 `core/providers/doorlock/session_manager.py`
- [ ] 实现 `DoorlockSession` 类（会话数据结构）
- [ ] 实现会话ID生成（基于时间戳）
- [ ] 实现会话生命周期管理（创建、更新、清除）
- [ ] 实现对话结束判定（沉默30秒或PIR检测不到人体）
- [ ] 实现对话历史管理（保留最近10轮）

**预计工作量**：3-4小时

### 4.5 看护模式管理层（优先级：高）

**任务6：实现看护模式管理器**

- [ ] 创建 `core/providers/doorlock/package_guard_manager.py`
- [ ] 实现看护状态管理（启用、关闭、查询）
- [ ] 实现基准图片管理（拍摄、存储、加载、更新）
- [ ] 实现看护监控循环（每5秒拍照 + AI判断）
- [ ] 实现威胁等级处理（语音警告 + App通知）
- [ ] 实现与VLLM的集成（传递当前图片和基准图片）

**预计工作量**：6-8小时

### 4.6 意图识别处理层（优先级：高）

**任务7：实现意图识别处理器**

- [ ] 创建 `core/handle/doorlock_intent_handler.py`
- [ ] 实现人脸识别重试机制（最多3次，间隔1秒）
- [ ] 实现主动问候逻辑
- [ ] 实现意图识别对话流程（VLLM + 语音交互）
- [ ] 实现对话总结生成
- [ ] 实现与看护模式的协同（并行执行）
- [ ] 实现欢迎词播放（根据时段选择）

**预计工作量**：6-8小时

### 4.7 HTTP API层（优先级：中）

**任务8：扩展HTTP API接口**

- [ ] 在 `core/api/` 下创建 `doorlock_api.py`
- [ ] 实现 `/api/doorlock/config` - 查询/更新设备配置
- [ ] 实现 `/api/doorlock/package_guard/start` - 手动启动看护
- [ ] 实现 `/api/doorlock/package_guard/stop` - 手动停止看护
- [ ] 实现 `/api/doorlock/welcome/config` - 配置欢迎词
- [ ] 实现 `/api/doorlock/intents/history` - 查询意图识别历史
- [ ] 实现 `/api/doorlock/alerts/history` - 查询快递警报历史

**预计工作量**：4-5小时

### 4.8 App通知层（优先级：中）

**任务9：实现App通知推送**

- [ ] 创建 `core/providers/doorlock/notification_service.py`
- [ ] 实现访客意图识别结果通知
- [ ] 实现快递异常警报通知
- [ ] 实现看护模式状态变化通知
- [ ] 与manager-api集成（调用Java后端推送接口）

**预计工作量**：3-4小时

### 4.9 配置管理层（优先级：中）

**任务10：实现配置管理**

- [ ] 在 `config.yaml` 中添加门锁相关配置
- [ ] 实现配置加载和验证
- [ ] 实现配置热更新（通过App修改后生效）
- [ ] 实现默认配置和用户配置的合并

**预计工作量**：2-3小时

### 4.10 测试和优化（优先级：低）

**任务11：单元测试**

- [ ] 编写数据库操作测试
- [ ] 编写工具函数测试
- [ ] 编写会话管理测试
- [ ] 编写看护模式测试

**任务12：集成测试**

- [ ] 测试完整的访客意图识别流程
- [ ] 测试完整的看护模式流程
- [ ] 测试人脸识别重试机制
- [ ] 测试欢迎词播放
- [ ] 测试App通知推送

**任务13：性能优化**

- [ ] 优化VLLM调用频率
- [ ] 优化图片传输和存储
- [ ] 优化对话历史管理
- [ ] 添加性能监控日志

**预计工作量**：8-10小时

---

## 五、验收标准

### 5.1 功能验收

#### 5.1.1 快递看护模式

- [ ] 用户可以在App中开启/关闭"看护模式可用"
- [ ] AI可以在对话中自动判断是否需要启用看护模式
- [ ] 用户可以手动启动/停止看护模式
- [ ] PIR触发后5秒开始拍照监控
- [ ] 每5秒拍照一次，图片带时间戳
- [ ] AI能正确判断威胁等级（低/中/高）
- [ ] 根据威胁等级播放不同的语音警告
- [ ] 中/高威胁时发送App通知
- [ ] 主人取走快递后自动关闭看护模式
- [ ] 基准图片在访客离开后正确更新
- [ ] 所有警报记录保存到数据库

#### 5.1.2 访客意图识别

- [ ] PIR触发后启动人脸识别
- [ ] 人脸识别失败时最多重试3次，间隔1秒
- [ ] 第一次失败时播放语音提示"人脸识别失败，请正视摄像头重试"
- [ ] 三次失败后播放"人脸识别失败，请使用其他方式解锁"
- [ ] 有开门权限的用户识别成功后播放个性化欢迎词
- [ ] 欢迎词根据时段自动选择（早/午/晚/夜）
- [ ] 无权限访客立即进入意图识别对话
- [ ] AI主动问候"您好，请问有什么可以帮您？"
- [ ] 对话持续进行，直到沉默30秒或PIR检测不到人体
- [ ] 对话结束后生成结构化总结
- [ ] 总结中重要信息（留言、提醒）显著标注在开头
- [ ] 总结发送到App，包含人脸照片、对话文字、意图摘要
- [ ] 会话在PIR检测不到人体后立即清除

#### 5.1.3 数据管理

- [ ] persons表成功添加is_owner和custom_greeting字段
- [ ] doorlock_config表正常工作
- [ ] doorlock_visitor_intents表正常工作
- [ ] doorlock_package_alerts表正常工作
- [ ] 欢迎词JSON格式正确存储和读取
- [ ] 所有记录永久保存，不自动删除

### 5.2 性能验收

- [ ] 人脸识别响应时间 < 2秒
- [ ] VLLM意图识别响应时间 < 5秒
- [ ] 拍照上传耗时 < 1秒
- [ ] 看护模式拍照间隔准确为5秒±0.5秒
- [ ] 对话沉默判定准确为30秒±1秒
- [ ] Token消耗日志正确记录
- [ ] 单次对话Token消耗不超过模型上限的80%

### 5.3 稳定性验收

- [ ] 连续运行24小时无崩溃
- [ ] 看护模式连续监控1小时无异常
- [ ] 多个访客同时到访时正确处理（不同会话）
- [ ] VLLM服务不可用时输出错误日志，不影响其他功能
- [ ] 数据库连接异常时正确重连
- [ ] 内存占用稳定，无明显泄漏

### 5.4 用户体验验收

- [ ] 语音提示清晰、及时、语气恰当
- [ ] 对话流畅，AI理解准确
- [ ] App通知及时送达（延迟<5秒）
- [ ] 通知内容完整、格式清晰
- [ ] 欢迎词播放自然，不生硬
- [ ] 威胁等级判断准确率>90%

---

## 六、风险与注意事项

### 6.1 技术风险

| 风险                 | 影响         | 缓解措施                         |
| -------------------- | ------------ | -------------------------------- |
| VLLM响应延迟较大     | 对话体验差   | 优化提示词长度，减少上下文       |
| 看护模式频繁拍照耗电 | 设备续航下降 | 后续优化：增加图像差异检测       |
| Token消耗过快        | 成本增加     | 记录日志，监控消耗，及时清理历史 |
| 威胁等级误判         | 用户体验差   | 持续优化提示词，收集反馈         |
| 并发访客处理         | 会话混乱     | 严格的会话隔离和ID管理           |

### 6.2 业务风险

| 风险           | 影响           | 缓解措施                           |
| -------------- | -------------- | ---------------------------------- |
| AI误判主人身份 | 看护模式误关闭 | 严格依赖is_owner字段，不依赖AI判断 |
| 访客隐私泄露   | 法律风险       | 明确告知录像，数据加密存储         |
| 推销骚扰       | 用户体验差     | AI识别推销意图后礼貌拒绝           |
| 恶意访客对抗   | 系统失效       | 记录所有行为，保留证据             |

### 6.3 注意事项

1. **隐私保护**：
   - 所有人脸照片和对话记录需加密存储
   - 在门口明显位置提示"此处有监控录像"
   - 用户需同意隐私政策

2. **数据安全**：
   - 定期备份数据库
   - 照片文件定期归档
   - 敏感信息脱敏处理

3. **成本控制**：
   - 监控VLLM API调用次数和Token消耗
   - 设置每日调用上限
   - 优化提示词减少Token使用

4. **用户教育**：
   - 提供使用指南，说明功能和限制
   - 告知AI判断可能存在误差
   - 鼓励用户反馈问题

5. **持续优化**：
   - 收集用户反馈
   - 分析误判案例
   - 定期更新提示词
   - 优化威胁等级判断标准

---

## 七、后续优化方向

### 7.1 短期优化（1-3个月）

1. **性能优化**：
   - 增加图像差异检测，减少不必要的VLLM调用
   - 实现"关键帧"策略，优化拍照频率
   - 压缩图片传输，减少带宽占用

2. **功能增强**：
   - 支持多个快递同时看护
   - 支持快递数量统计
   - 支持访客预约功能

3. **用户体验**：
   - 优化语音提示内容
   - 增加更多欢迎词模板
   - 支持语音留言功能

### 7.2 中期优化（3-6个月）

1. **智能化提升**：
   - 学习用户习惯，自动调整看护策略
   - 识别常见访客（快递员、保洁等）
   - 支持访客黑名单功能

2. **多设备协同**：
   - 支持多个门锁设备联动
   - 支持与其他智能家居设备集成
   - 支持远程视频通话

3. **数据分析**：
   - 访客统计报表
   - 快递收发记录
   - 安全事件分析

### 7.3 长期优化（6个月以上）

1. **边缘计算**：
   - 将部分AI能力下沉到设备端
   - 减少云端依赖，提高响应速度
   - 降低运营成本

2. **多模态融合**：
   - 结合声纹识别
   - 结合行为分析
   - 结合环境感知

3. **生态建设**：
   - 开放API给第三方
   - 支持自定义插件
   - 建立开发者社区

---

## 八、参考文档

- `docs/my_docs/esp32-vision-guide.md` - ESP32视觉功能使用指南
- `docs/my_docs/face-data-storage-documentation.md` - 人脸数据存储文档
- `docs/my_docs/智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md` - 通信协议规范
- `main/xiaozhi-server/agent-base-prompt.txt` - Agent提示词参考
- `docs/my_docs/dialogue-class-explanation.md` - 对话类说明

---

## 九、更新日志

| 版本 | 日期       | 说明                       | 作者              |
| ---- | ---------- | -------------------------- | ----------------- |
| v1.0 | 2026-02-08 | 初始版本，完整需求规格说明 | Kiro AI Assistant |

---

**文档维护者**: Kiro AI Assistant  
**最后更新**: 2026-02-08  
**状态**: 待实现
