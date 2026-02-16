# VLLM 意图识别模拟测试方案

## 概述

本文档描述如何通过 Python 脚本模拟 ESP32 设备，测试服务器端的 VLLM 意图识别模块。

## 测试目标

1. 验证 VLLM 意图识别的完整流程
2. 测试多轮对话的意图分析能力
3. 验证意图总结生成功能（JSON 格式）
4. 测试快递看护模式触发
5. 验证对话历史保存和通知发送

## 测试环境

- **服务器地址**：`ws://localhost:8000`
- **测试设备 ID**：`test_device_001`
- **认证方式**：白名单模式（无需 token）
- **VLLM 配置**：已配置并启用

## 目录结构

```
main/xiaozhi-server/test/vllm_simulation/
├── simulator/                       # 模拟器核心代码
│   ├── __init__.py
│   ├── websocket_client.py         # WebSocket 客户端
│   ├── message_builder.py          # 消息构建器
│   ├── scenario_runner.py          # 场景执行器
│   └── result_validator.py         # 结果验证器
├── test_data/                      # 测试数据
│   ├── images/                     # 访客照片
│   │   ├── delivery_person/        # 快递员照片
│   │   │   ├── 1.jpg
│   │   │   ├── 2.jpg
│   │   │   └── 3.jpg
│   │   ├── friend_visitor/         # 朋友照片
│   │   │   ├── 1.jpg
│   │   │   └── 2.jpg
│   │   ├── stranger_sales/         # 陌生推销照片
│   │   │   └── 1.jpg
│   │   └── maintenance/            # 维修人员照片
│   │       └── 1.jpg
│   └── scenarios.json              # 对话场景配置
├── test_results/                   # 测试结果输出
│   └── test_report_YYYYMMDD_HHMMSS.md
├── run_test.py                     # 测试入口脚本
├── config.yaml                     # 测试配置
└── README.md                       # 使用说明
```

## 测试场景设计

### 场景1：快递员送快递（包含看护功能）

**访客类型**：快递员  
**照片目录**：`test_data/images/delivery_person/`  
**预期意图类型**：`delivery`  
**预期行为**：启动看护模式

**对话流程**：

1. 快递员："有快递"
2. AI："您好，请问是什么快递呀？"
3. 快递员："京东的，手机"
4. AI："好的，能帮我把快递放在门口吗？我现在不在家"
5. 快递员："行，放这儿了啊"
6. AI："好的谢谢，麻烦您拍个照片给我看一下"
7. （快递员拍照，触发看护模式）
8. AI："收到了，谢谢您！"

**验证点**：

- ✅ 意图类型识别为 `delivery`
- ✅ 意图总结包含"快递"、"京东"、"手机"等关键词
- ✅ 触发看护模式（guard_active=true）
- ✅ 对话历史完整保存
- ✅ 发送 App 通知

---

### 场景2：朋友来访（遵循 who/what/why）

**访客类型**：朋友  
**照片目录**：`test_data/images/friend_visitor/`  
**预期意图类型**：`visit`  
**预期行为**：通知主人

**对话流程**：

1. 访客："张哥在吗？"
2. AI："请问您是哪位？"（who）
3. 访客："我李明啊，上次一起吃饭那个"
4. AI："哦李明，找张哥有什么事吗？"（why）
5. 访客："上次说好今天来拿那个工具的"（what）
6. AI："好的，我通知他一下，您稍等"

**验证点**：

- ✅ 意图类型识别为 `visit`
- ✅ 意图总结包含访客姓名"李明"
- ✅ 意图总结包含来访目的"拿工具"
- ✅ important_notes 包含【留言】或【提醒】
- ✅ 对话历史完整保存

---

### 场景3：陌生推销（遵循 who/what/why 后拒绝）

**访客类型**：陌生推销  
**照片目录**：`test_data/images/stranger_sales/`  
**预期意图类型**：`sales`  
**预期行为**：礼貌拒绝

**对话流程**：

1. 陌生人："你好"
2. AI："您好，请问您找谁？"（who）
3. 陌生人："我们是XX装修公司的，想了解下您家装修情况"
4. AI："请问具体是什么业务呢？"（what）
5. 陌生人："我们现在有优惠活动，全屋定制打8折"
6. AI："哦这样啊，不好意思我们暂时不需要，谢谢"

**验证点**：

- ✅ 意图类型识别为 `sales`
- ✅ 意图总结包含"装修"、"推销"等关键词
- ✅ 对话历史完整保存
- ✅ 发送 App 通知

---

### 场景4：维修人员

**访客类型**：维修人员  
**照片目录**：`test_data/images/maintenance/`  
**预期意图类型**：`maintenance`  
**预期行为**：通知主人

**对话流程**：

1. 维修人员："物业的，来检查水表"
2. AI："您好，请问是哪个物业公司的？"（who）
3. 维修人员："XX小区物业，今天统一检查水表"
4. AI："需要进屋检查吗？"（what）
5. 维修人员："对，水表在厨房"
6. AI："好的，我通知主人一下"

**验证点**：

- ✅ 意图类型识别为 `maintenance`
- ✅ 意图总结包含"物业"、"检查水表"等关键词
- ✅ 对话历史完整保存

## 协议实现细节

### WebSocket 连接

```python
# 连接地址
ws_url = "ws://localhost:8000"

# 请求头
headers = {
    "device-id": "test_device_001",
    "client-id": "test_client"
}

# 白名单配置（需要在服务器 config.yaml 中添加）
# server:
#   auth:
#     enabled: true
#     allowed_devices:
#       - test_device_001
```

### 消息格式

#### 1. 发送人脸识别图片（Binary Frame）

根据 ESP32 协议 v5.2，使用 BinaryProtocol2 格式：

```
+----------------+----------------+--------------------------------+
|   version(2)   |    type(2)     |         reserved(4)            |
+----------------+----------------+--------------------------------+
|           timestamp(4)          |        payload_size(4)         |
+----------------+----------------+--------------------------------+
|                    payload data (JPEG)...                        |
+------------------------------------------------------------------+
```

**字段说明**：

- `version`: 2 (固定值)
- `type`: 2 (人脸识别图像)
- `reserved`: 分辨率编码 `(width << 16) | height`，例如 640×480 = `0x028001E0`
- `timestamp`: 当前时间戳（毫秒）
- `payload_size`: JPEG 数据大小
- `payload`: JPEG 图片数据

**字节序**：大端序（Big-Endian）

#### 2. 接收 face_result 消息（JSON Frame）

服务器会下发人脸识别结果：

```json
{
  "type": "face_result",
  "result": "known",
  "user_id": 5,
  "access": {
    "granted": false,
    "reason": "unauthorized_user"
  }
}
```

**注意**：根据 v5.2 协议，`face_result` 是服务器主动推送的识别结果：

- ❌ 不需要 `seq_id` 字段
- ❌ 不需要 `esp32_ack` 和 `ack` 两级确认
- ✅ ESP32 根据 `access.granted` 字段决定是否开锁

#### 3. 模拟语音对话（简化实现）

由于测试脚本无法真正发送音频流，我们通过 JSON 消息模拟对话：

```json
{
  "type": "text_message",
  "content": "有快递",
  "session_id": "test_session_001"
}
```

**注意**：这是简化实现，实际 ESP32 会发送音频二进制流。

#### 4. 接收 AI 回复

服务器会通过 TTS 播放回复，测试脚本需要监听：

```json
{
  "type": "tts_response",
  "content": "您好，请问是什么快递呀？",
  "session_id": "test_session_001"
}
```

## 实现架构

### 核心模块划分

#### 1. WebSocket 客户端 (`simulator/websocket_client.py`)

**职责**：

- 建立 WebSocket 连接
- 发送/接收消息
- 处理连接异常

**关键方法**：

```python
class ESP32WebSocketClient:
    async def connect(self, url: str, headers: dict)
    async def send_binary(self, data: bytes)
    async def send_json(self, message: dict)
    async def receive_message(self) -> dict
    async def close()
```

#### 2. 消息构建器 (`simulator/message_builder.py`)

**职责**：

- 构建 BinaryProtocol2 格式的二进制消息
- 构建 JSON 格式的文本消息
- 处理图片编码

**关键方法**：

```python
class MessageBuilder:
    @staticmethod
    def build_face_recognition_frame(jpeg_data: bytes) -> bytes

    @staticmethod
    def build_text_message(content: str, session_id: str) -> dict

    @staticmethod
    def load_image(image_path: str) -> bytes
```

#### 3. 场景执行器 (`simulator/scenario_runner.py`)

**职责**：

- 加载场景配置
- 执行对话流程
- 收集测试结果

**关键方法**：

```python
class ScenarioRunner:
    async def run_scenario(self, scenario: dict, client: ESP32WebSocketClient)
    async def wait_for_ai_response(self, timeout: int = 30)
    def collect_dialogue_history(self) -> list
```

#### 4. 结果验证器 (`simulator/result_validator.py`)

**职责**：

- 验证意图识别结果
- 检查对话完整性
- 生成测试报告

**关键方法**：

```python
class ResultValidator:
    def validate_intent_type(self, expected: str, actual: str) -> bool
    def validate_intent_summary(self, summary: dict) -> bool
    def generate_report(self, results: list) -> str
```

## 测试流程

### 自动化测试模式

```
1. 加载所有场景配置
2. 依次执行每个场景：
   a. 建立 WebSocket 连接
   b. 发送人脸识别图片（Binary Frame）
   c. 接收 face_result 消息
   d. 执行多轮对话
   e. 等待意图总结生成
   f. 验证测试结果
   g. 关闭连接
3. 生成测试报告
```

### 交互式测试模式

```
1. 显示可用场景列表
2. 用户选择场景
3. 执行选定场景
4. 显示实时对话过程
5. 显示测试结果
6. 询问是否继续测试
```

### 错误处理策略

**连接失败**：

- 记录错误日志
- 不重试，直接跳过该场景
- 在报告中标记为"连接失败"

**VLLM 识别失败**：

- 记录错误日志
- 继续执行下一个场景
- 在报告中标记为"识别失败"

**超时处理**：

- 对话等待超时：30 秒
- 意图总结生成超时：60 秒
- 超时后标记为"超时失败"

## 配置文件格式

### scenarios.json

```json
{
  "scenarios": [
    {
      "id": "scenario_1",
      "name": "快递员送快递",
      "description": "测试快递场景的意图识别和看护模式触发",
      "image_folder": "delivery_person",
      "expected_intent": "delivery",
      "enable_guard_mode": true,
      "dialogue": [
        {
          "role": "user",
          "content": "有快递"
        },
        {
          "role": "assistant",
          "content": "您好，请问是什么快递呀？"
        },
        {
          "role": "user",
          "content": "京东的，手机"
        },
        {
          "role": "assistant",
          "content": "好的,能帮我把快递放在门口吗？我现在不在家"
        },
        {
          "role": "user",
          "content": "行，放这儿了啊"
        },
        {
          "role": "assistant",
          "content": "好的谢谢，麻烦您拍个照片给我看一下"
        },
        {
          "role": "user",
          "content": "[拍照动作]"
        },
        {
          "role": "assistant",
          "content": "收到了，谢谢您！"
        }
      ],
      "validation": {
        "intent_type": "delivery",
        "keywords": ["快递", "京东", "手机"],
        "guard_mode": true
      }
    },
    {
      "id": "scenario_2",
      "name": "朋友来访",
      "description": "测试访客场景的 who/what/why 询问",
      "image_folder": "friend_visitor",
      "expected_intent": "visit",
      "enable_guard_mode": false,
      "dialogue": [
        {
          "role": "user",
          "content": "张哥在吗？"
        },
        {
          "role": "assistant",
          "content": "请问您是哪位？"
        },
        {
          "role": "user",
          "content": "我李明啊，上次一起吃饭那个"
        },
        {
          "role": "assistant",
          "content": "哦李明，找张哥有什么事吗？"
        },
        {
          "role": "user",
          "content": "上次说好今天来拿那个工具的"
        },
        {
          "role": "assistant",
          "content": "好的，我通知他一下，您稍等"
        }
      ],
      "validation": {
        "intent_type": "visit",
        "keywords": ["李明", "工具"],
        "important_notes_count": 1
      }
    }
  ]
}
```

### config.yaml

```yaml
# 测试配置
test:
  # 服务器配置
  server:
    url: "ws://localhost:8000"
    device_id: "test_device_001"
    client_id: "test_client"

  # 超时配置
  timeout:
    connection: 10 # 连接超时（秒）
    dialogue: 30 # 对话等待超时（秒）
    summary: 60 # 意图总结生成超时（秒）

  # 测试数据路径
  data:
    images_dir: "test_data/images"
    scenarios_file: "test_data/scenarios.json"

  # 测试结果输出
  output:
    results_dir: "test_results"
    console_output: true
    file_output: true
    report_format: "markdown" # markdown 或 json
```

## 测试报告格式

### Markdown 报告示例

````markdown
# VLLM 意图识别测试报告

**测试时间**：2026-02-15 14:30:00  
**测试设备**：test_device_001  
**服务器地址**：ws://localhost:8000

---

## 测试概览

| 指标     | 数值 |
| -------- | ---- |
| 总场景数 | 4    |
| 成功场景 | 3    |
| 失败场景 | 1    |
| 成功率   | 75%  |

---

## 场景详情

### ✅ 场景1：快递员送快递

**状态**：成功  
**执行时间**：45 秒  
**意图识别**：delivery（正确）

**对话历史**：

1. 用户："有快递"
2. AI："您好，请问是什么快递呀？"
3. 用户："京东的，手机"
4. AI："好的，能帮我把快递放在门口吗？我现在不在家"
5. 用户："行，放这儿了啊"
6. AI："好的谢谢，麻烦您拍个照片给我看一下"
7. 用户："[拍照动作]"
8. AI："收到了，谢谢您！"

**意图总结**：

```json
{
  "intent_type": "delivery",
  "purpose": "送快递",
  "important_notes": ["【留言】京东快递，手机"],
  "full_summary": "访客是快递员，送来京东快递（手机），已放置门口并拍照确认"
}
```
````

**验证结果**：

- ✅ 意图类型正确
- ✅ 包含关键词：快递、京东、手机
- ✅ 看护模式已触发
- ✅ 对话历史完整

---

### ✅ 场景2：朋友来访

**状态**：成功  
**执行时间**：38 秒  
**意图识别**：visit（正确）

**对话历史**：
（省略...）

**意图总结**：

```json
{
  "intent_type": "visit",
  "purpose": "拿工具",
  "important_notes": ["【留言】李明来拿工具"],
  "full_summary": "访客李明，是主人朋友，来拿之前约定的工具"
}
```

**验证结果**：

- ✅ 意图类型正确
- ✅ 包含关键词：李明、工具
- ✅ important_notes 数量正确
- ✅ 对话历史完整

---

### ❌ 场景3：陌生推销

**状态**：失败  
**失败原因**：意图类型识别错误  
**执行时间**：42 秒  
**意图识别**：other（预期：sales）

**错误详情**：

- 预期意图类型：sales
- 实际意图类型：other
- 可能原因：关键词"装修"、"推销"未被正确识别

---

## 问题总结

1. **场景3 意图识别错误**：
   - 问题：将推销场景识别为 other
   - 建议：优化 VLLM 提示词，增强推销场景的识别能力

2. **对话超时**：
   - 无超时问题

3. **连接稳定性**：
   - 所有场景连接正常

---

## 建议

1. 优化 VLLM 提示词，提高推销场景识别准确率
2. 增加更多测试场景，覆盖边缘情况
3. 测试长对话场景（超过 10 轮）

---

**测试完成时间**：2026-02-15 14:35:00  
**总耗时**：5 分钟

```

```

## 使用说明

### 环境准备

1. **安装依赖**：

```bash
cd main/xiaozhi-server
pip install websockets pillow pyyaml
```

2. **配置服务器白名单**：

编辑 `data/.config.yaml`，添加测试设备到白名单：

```yaml
server:
  auth:
    enabled: true
    allowed_devices:
      - test_device_001 # 添加测试设备
```

3. **准备测试图片**：

将访客照片放置到对应目录：

```
test/vllm_simulation/test_data/images/
├── delivery_person/
│   ├── 1.jpg  # 快递员照片1
│   ├── 2.jpg  # 快递员照片2
│   └── 3.jpg  # 快递员照片3
├── friend_visitor/
│   ├── 1.jpg  # 朋友照片1
│   └── 2.jpg  # 朋友照片2
├── stranger_sales/
│   └── 1.jpg  # 陌生推销照片
└── maintenance/
    └── 1.jpg  # 维修人员照片
```

**图片要求**：

- 格式：JPEG
- 分辨率：建议 640×480 或更高
- 大小：不超过 5MB
- 内容：清晰的人脸照片

### 运行测试

#### 自动化测试模式

```bash
cd test/vllm_simulation
python run_test.py --mode auto
```

#### 交互式测试模式

```bash
cd test/vllm_simulation
python run_test.py --mode interactive
```

#### 指定场景测试

```bash
cd test/vllm_simulation
python run_test.py --scenario scenario_1
```

#### 生成报告

```bash
# 控制台输出 + Markdown 报告
python run_test.py --mode auto --output both

# 仅控制台输出
python run_test.py --mode auto --output console

# 仅生成报告文件
python run_test.py --mode auto --output file
```

### 查看测试结果

测试报告保存在 `test_results/` 目录：

```bash
# 查看最新报告
cat test_results/test_report_20260215_143000.md

# 或使用 Markdown 查看器
code test_results/test_report_20260215_143000.md
```

## 技术实现要点

### 1. BinaryProtocol2 编码

```python
import struct
import time

def build_face_recognition_frame(jpeg_data: bytes) -> bytes:
    """构建人脸识别二进制帧

    Args:
        jpeg_data: JPEG 图片数据

    Returns:
        BinaryProtocol2 格式的二进制数据
    """
    # 协议字段
    version = 2
    msg_type = 2  # 人脸识别图像
    width = 640
    height = 480
    reserved = (width << 16) | height  # 0x028001E0
    timestamp = int(time.time() * 1000)  # 毫秒时间戳
    payload_size = len(jpeg_data)

    # 打包头部（大端序）
    header = struct.pack(
        '>HHIII',  # > 表示大端序
        version,
        msg_type,
        reserved,
        timestamp,
        payload_size
    )

    # 组合头部和负载
    return header + jpeg_data
```

### 2. WebSocket 异步通信

```python
import asyncio
import websockets
import json

class ESP32WebSocketClient:
    def __init__(self, url: str, headers: dict):
        self.url = url
        self.headers = headers
        self.websocket = None

    async def connect(self):
        """建立 WebSocket 连接"""
        self.websocket = await websockets.connect(
            self.url,
            extra_headers=self.headers
        )

    async def send_binary(self, data: bytes):
        """发送二进制消息"""
        await self.websocket.send(data)

    async def send_json(self, message: dict):
        """发送 JSON 消息"""
        await self.websocket.send(json.dumps(message))

    async def receive_message(self, timeout: int = 30):
        """接收消息（带超时）"""
        try:
            message = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=timeout
            )

            # 判断是二进制还是文本
            if isinstance(message, bytes):
                return {"type": "binary", "data": message}
            else:
                return {"type": "json", "data": json.loads(message)}

        except asyncio.TimeoutError:
            return {"type": "timeout", "data": None}

    async def close(self):
        """关闭连接"""
        if self.websocket:
            await self.websocket.close()
```

### 3. 场景执行逻辑

```python
async def run_scenario(scenario: dict, client: ESP32WebSocketClient):
    """执行单个测试场景

    Args:
        scenario: 场景配置
        client: WebSocket 客户端

    Returns:
        测试结果字典
    """
    result = {
        "scenario_id": scenario["id"],
        "scenario_name": scenario["name"],
        "status": "unknown",
        "dialogue_history": [],
        "intent_summary": None,
        "errors": []
    }

    try:
        # 1. 发送人脸识别图片
        image_path = f"test_data/images/{scenario['image_folder']}/1.jpg"
        jpeg_data = load_image(image_path)
        binary_frame = build_face_recognition_frame(jpeg_data)
        await client.send_binary(binary_frame)

        # 2. 接收 face_result
        response = await client.receive_message(timeout=10)
        if response["type"] == "timeout":
            result["status"] = "timeout"
            result["errors"].append("等待 face_result 超时")
            return result

        face_result = response["data"]
        logger.info(f"收到 face_result: {face_result}")

        # 3. 执行对话流程
        for turn in scenario["dialogue"]:
            if turn["role"] == "user":
                # 发送用户消息
                await client.send_json({
                    "type": "text_message",
                    "content": turn["content"],
                    "session_id": scenario["id"]
                })

                result["dialogue_history"].append({
                    "role": "user",
                    "content": turn["content"]
                })

            elif turn["role"] == "assistant":
                # 等待 AI 回复
                response = await client.receive_message(timeout=30)
                if response["type"] == "timeout":
                    result["status"] = "timeout"
                    result["errors"].append("等待 AI 回复超时")
                    return result

                ai_response = response["data"]
                result["dialogue_history"].append({
                    "role": "assistant",
                    "content": ai_response.get("content", "")
                })

        # 4. 等待意图总结
        # TODO: 实现意图总结接收逻辑

        result["status"] = "success"

    except Exception as e:
        result["status"] = "error"
        result["errors"].append(str(e))

    return result
```

### 4. 日志记录

```python
from loguru import logger

# 配置日志
logger.add(
    "test_results/test_{time}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

# 使用日志
logger.info("开始测试场景: {}", scenario["name"])
logger.debug("发送二进制帧，大小: {} bytes", len(binary_frame))
logger.error("测试失败: {}", error_message)
```

## 注意事项

### 1. 协议兼容性

- 严格遵循 ESP32 协议 v5.2 规范
- 二进制帧使用大端序（Big-Endian）
- `face_result` 消息不需要 `seq_id` 和两级确认

### 2. 测试限制

**当前实现的简化**：

- ❌ 不发送真实音频流（使用文本消息模拟）
- ❌ 不处理 TTS 音频播放（只接收文本）
- ❌ 不模拟 PIR 传感器状态
- ✅ 只测试核心的意图识别流程

**未来可扩展**：

- 集成真实音频流测试
- 模拟完整的硬件传感器状态
- 测试看护模式的完整流程

### 3. 性能考虑

- 每个场景独立连接，避免状态污染
- 使用异步 I/O，提高测试效率
- 合理设置超时时间，避免长时间等待

### 4. 调试技巧

**查看实时日志**：

```bash
tail -f test_results/test_*.log
```

**抓包分析**：

```bash
# 使用 Wireshark 抓取 WebSocket 流量
# 过滤器：tcp.port == 8000
```

**手动测试单个消息**：

```python
# 在 Python REPL 中测试
import asyncio
from simulator.websocket_client import ESP32WebSocketClient

async def test():
    client = ESP32WebSocketClient(
        "ws://localhost:8000",
        {"device-id": "test_device_001"}
    )
    await client.connect()
    # 发送测试消息...
    await client.close()

asyncio.run(test())
```

### 5. 常见问题

**Q1: 连接被拒绝**

- 检查服务器是否运行（端口 8000）
- 确认 `test_device_001` 已添加到白名单
- 查看服务器日志确认认证状态

**Q2: 意图识别结果不准确**

- 检查 VLLM 配置是否正确
- 查看对话历史是否完整
- 调整提示词优化识别效果

**Q3: 测试超时**

- 检查网络连接
- 增加超时时间配置
- 查看服务器负载情况

**Q4: 图片无法加载**

- 确认图片路径正确
- 检查图片格式（必须是 JPEG）
- 验证图片大小（不超过 5MB）

## 下一步计划

### 阶段 1：基础实现（1-2 天）

- [ ] 创建测试目录结构
- [ ] 实现 WebSocket 客户端
- [ ] 实现消息构建器
- [ ] 实现场景执行器
- [ ] 编写场景配置文件

### 阶段 2：功能完善（1 天）

- [ ] 实现结果验证器
- [ ] 实现测试报告生成
- [ ] 添加交互式测试模式
- [ ] 完善错误处理

### 阶段 3：测试和优化（1 天）

- [ ] 准备测试图片
- [ ] 执行完整测试
- [ ] 修复发现的问题
- [ ] 优化测试流程
- [ ] 编写使用文档

### 阶段 4：扩展功能（可选）

- [ ] 支持真实音频流测试
- [ ] 集成 PIR 传感器模拟
- [ ] 测试看护模式完整流程
- [ ] 添加性能测试
- [ ] 支持批量测试

## 总结

本测试方案提供了一个完整的 VLLM 意图识别模块测试框架，通过模拟 ESP32 设备与服务器的 WebSocket 通信，可以：

1. ✅ 验证意图识别的准确性
2. ✅ 测试多轮对话流程
3. ✅ 检查意图总结生成
4. ✅ 验证看护模式触发
5. ✅ 生成详细的测试报告

**核心优势**：

- 无需真实硬件设备
- 支持自动化和交互式测试
- 完整的错误处理和日志记录
- 灵活的场景配置
- 详细的测试报告

**适用场景**：

- 开发阶段的功能验证
- 回归测试
- 性能测试
- 问题排查

---

**文档维护者**：Kiro AI Assistant  
**最后更新**：2026-02-15  
**版本**：v1.0
