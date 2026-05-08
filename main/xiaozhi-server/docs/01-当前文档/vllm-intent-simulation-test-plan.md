# 统一看护对话模式仿真测试方案

## 概述

本文档描述如何通过 Python 脚本模拟 ESP32 设备,测试服务器端的统一看护对话模式。该模式将意图识别对话和快递看护监控统一到一个智能流程中。

**测试重点**：仿真测试（模拟ESP32设备向服务器提供数据）

## 测试目标

1. 验证统一模式对话的完整流程
2. 测试定时拍照机制和照片缓存管理
3. 验证图片传递策略（第一轮传2张,后续传1张）
4. 测试对话结束后的快递状态检查
5. 验证意图总结生成功能（JSON格式）
6. 测试Token优化效果

## 测试环境

- **服务器地址**：`ws://localhost:8000`
- **测试设备 ID**：`test_device_001`
- **认证方式**：白名单模式（无需 token）
- **VLLM 配置**：已配置并启用

## 核心测试场景

### 场景1：仅对话模式（看护未激活）

**测试目的**：验证无看护模式下的基本对话流程

**前置条件**：

- 看护模式未激活
- 无基准图片

**测试流程**：

```
1. PIR检测到人体
   ↓
2. 拍摄访客照片
   ↓
3. 人脸识别 → 陌生人/无权限
   ↓
4. 启动对话（不启动定时拍照）
   ↓
5. 对话循环（使用初次访客照片）
   - 第1轮：传入1张访客照片
   - 第2-N轮：传入1张访客照片
   ↓
6. 对话结束
   ↓
7. 生成意图总结（不检查快递状态）
   ↓
8. 保存记录并发送通知
```

**验证点**：

- ✅ 不启动定时拍照任务
- ✅ 每轮对话仅传入1张访客照片
- ✅ 对话结束后不执行快递状态检查
- ✅ 意图总结正常生成
- ✅ Token消耗符合预期（~7K/轮）

---

### 场景2：统一模式（看护激活）

**测试目的**：验证看护模式下的完整统一流程

**前置条件**：

- 看护模式已激活
- 有基准图片

**测试流程**：

```
1. PIR检测到人体
   ↓
2. 拍摄访客照片
   ↓
3. 人脸识别 → 陌生人/无权限
   ↓
4. 启动对话 + 启动定时拍照任务（每5秒）
   ↓
5. 对话循环
   - 第1轮：传入最新缓存照片 + 基准图片（2张）
   - 第2-N轮：传入最新缓存照片（1张）
   ↓
6. 对话结束
   ↓
7. 停止定时拍照任务
   ↓
8. 快递状态检查（最后缓存照片 + 基准图片）
   ↓
9. 生成意图总结（初次访客照片）
   ↓
10. 清理照片缓存
   ↓
11. 保存记录并发送通知
```

**验证点**：

- ✅ 定时拍照任务正常启动和停止
- ✅ 照片缓存管理正常（最多10张）
- ✅ 第一轮传入2张图片（访客+基准）
- ✅ 后续轮次传入1张图片（最新缓存）
- ✅ 对话结束后执行快递状态检查
- ✅ 意图总结使用初次访客照片
- ✅ 照片缓存正常清理
- ✅ Token消耗符合预期（第一轮~14K,后续~7K/轮）

---

### 场景3：快递员送快递（完整流程）

**测试目的**：验证快递场景的完整业务流程

**对话内容**：

1. 访客："有快递"
2. AI："您好,请问是什么快递呀？"
3. 访客："京东的,手机"
4. AI："好的,能帮我把快递放在门口吗？我现在不在家"
5. 访客："行,放这儿了啊"
6. AI："好的谢谢！"

**验证点**：

- ✅ AI识别到"快递"关键词
- ✅ AI可能调用 enable_package_guard 工具
- ✅ 意图类型识别为 "delivery"
- ✅ 意图总结包含"快递"、"京东"、"手机"等关键词
- ✅ 对话历史完整保存
- ✅ 发送App通知

---

## 测试实现架构

### 核心模块

#### 1. WebSocket 客户端

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

#### 2. 消息构建器

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

#### 3. 场景执行器

**职责**：

- 加载场景配置
- 执行对话流程
- 收集测试结果
- 模拟定时拍照（如果看护激活）

**关键方法**：

```python
class ScenarioRunner:
    async def run_scenario(self, scenario: dict, client: ESP32WebSocketClient)
    async def wait_for_ai_response(self, timeout: int = 30)
    async def simulate_photo_capture(self, session_id: str, interval: int = 5)
    def collect_dialogue_history(self) -> list
```

#### 4. 结果验证器

**职责**：

- 验证意图识别结果
- 检查对话完整性
- 验证照片传递策略
- 验证Token消耗
- 生成测试报告

**关键方法**：

```python
class ResultValidator:
    def validate_intent_type(self, expected: str, actual: str) -> bool
    def validate_intent_summary(self, summary: dict) -> bool
    def validate_photo_strategy(self, photo_logs: list) -> bool
    def validate_token_consumption(self, token_logs: list) -> bool
    def generate_report(self, results: list) -> str
```

---

## 协议实现细节

### 1. 发送人脸识别图片（Binary Frame）

根据 ESP32 协议 v5.2,使用 BinaryProtocol2 格式：

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
- `reserved`: 分辨率编码 `(width << 16) | height`,例如 640×480 = `0x028001E0`
- `timestamp`: 当前时间戳（毫秒）
- `payload_size`: JPEG 数据大小
- `payload`: JPEG 图片数据

**字节序**：大端序（Big-Endian）

### 2. 接收 face_result 消息（JSON Frame）

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

**注意**：根据 v5.2 协议,`face_result` 是服务器主动推送的识别结果：

- ❌ 不需要 `seq_id` 字段
- ❌ 不需要 `esp32_ack` 和 `ack` 两级确认
- ✅ ESP32 根据 `access.granted` 字段决定是否开锁

### 3. 模拟语音对话（简化实现）

由于测试脚本无法真正发送音频流,我们通过 JSON 消息模拟对话：

```json
{
  "type": "text_message",
  "content": "有快递",
  "session_id": "test_session_001"
}
```

**注意**：这是简化实现,实际 ESP32 会发送音频二进制流。

### 4. 接收 AI 回复

服务器会通过 TTS 播放回复,测试脚本需要监听：

```json
{
  "type": "tts_response",
  "content": "您好,请问是什么快递呀？",
  "session_id": "test_session_001"
}
```

---

## 测试数据准备

### 图片准备

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
└── baseline/
    ├── empty_door.jpg      # 空门口（无快递）
    └── with_package.jpg    # 门口有快递
```

**图片要求**：

- 格式：JPEG
- 分辨率：建议 640×480 或更高
- 大小：不超过 5MB
- 内容：清晰的人脸照片或门口场景

### 场景配置文件

```json
{
  "scenarios": [
    {
      "id": "scenario_1",
      "name": "仅对话模式",
      "description": "测试无看护模式下的基本对话流程",
      "guard_mode": false,
      "visitor_image": "delivery_person/1.jpg",
      "baseline_image": null,
      "dialogue": [
        { "role": "user", "content": "有快递" },
        { "role": "assistant", "content": "您好,请问是什么快递呀？" },
        { "role": "user", "content": "京东的,手机" },
        { "role": "assistant", "content": "好的,能帮我把快递放在门口吗？" },
        { "role": "user", "content": "行,放这儿了啊" },
        { "role": "assistant", "content": "好的谢谢！" }
      ],
      "validation": {
        "intent_type": "delivery",
        "keywords": ["快递", "京东", "手机"],
        "photo_count_first_round": 1,
        "photo_count_other_rounds": 1,
        "package_check": false,
        "expected_token_first_round": 7000,
        "expected_token_other_rounds": 7000
      }
    },
    {
      "id": "scenario_2",
      "name": "统一模式（看护激活）",
      "description": "测试看护模式下的完整统一流程",
      "guard_mode": true,
      "visitor_image": "delivery_person/1.jpg",
      "baseline_image": "baseline/with_package.jpg",
      "dialogue": [
        { "role": "user", "content": "有快递" },
        { "role": "assistant", "content": "您好,请问是什么快递呀？" },
        { "role": "user", "content": "京东的,手机" },
        { "role": "assistant", "content": "好的,能帮我把快递放在门口吗？" },
        { "role": "user", "content": "行,放这儿了啊" },
        { "role": "assistant", "content": "好的谢谢！" }
      ],
      "validation": {
        "intent_type": "delivery",
        "keywords": ["快递", "京东", "手机"],
        "photo_count_first_round": 2,
        "photo_count_other_rounds": 1,
        "package_check": true,
        "expected_token_first_round": 14000,
        "expected_token_other_rounds": 7000,
        "photo_cache_enabled": true,
        "photo_capture_interval": 5
      }
    }
  ]
}
```

---

## 测试流程

### 自动化测试模式

```
1. 加载所有场景配置
2. 依次执行每个场景：
   a. 建立 WebSocket 连接
   b. 发送人脸识别图片（Binary Frame）
   c. 接收 face_result 消息
   d. 如果看护激活,模拟启动定时拍照
   e. 执行多轮对话
   f. 记录每轮传入的图片数量
   g. 记录Token消耗
   h. 等待意图总结生成
   i. 验证测试结果
   j. 关闭连接
3. 生成测试报告
```

### 关键验证点

#### 1. 照片传递策略验证

```python
def validate_photo_strategy(photo_logs: list, guard_mode: bool) -> bool:
    """验证照片传递策略"""
    if not guard_mode:
        # 仅对话模式：每轮都传1张
        for log in photo_logs:
            if log['photo_count'] != 1:
                return False
    else:
        # 统一模式：第一轮传2张,后续传1张
        if photo_logs[0]['photo_count'] != 2:
            return False
        for log in photo_logs[1:]:
            if log['photo_count'] != 1:
                return False
    return True
```

#### 2. Token消耗验证

```python
def validate_token_consumption(token_logs: list, guard_mode: bool) -> bool:
    """验证Token消耗"""
    if not guard_mode:
        # 仅对话模式：每轮约7K
        for log in token_logs:
            if not (6000 <= log['total_tokens'] <= 8000):
                return False
    else:
        # 统一模式：第一轮约14K,后续约7K
        if not (13000 <= token_logs[0]['total_tokens'] <= 15000):
            return False
        for log in token_logs[1:]:
            if not (6000 <= log['total_tokens'] <= 8000):
                return False
    return True
```

#### 3. 照片缓存验证

```python
def validate_photo_cache(cache_logs: list, guard_mode: bool) -> bool:
    """验证照片缓存管理"""
    if not guard_mode:
        # 仅对话模式：不使用缓存
        return len(cache_logs) == 0
    else:
        # 统一模式：缓存应该增长,最多10张
        for log in cache_logs:
            if log['cache_size'] > 10:
                return False
        return True
```

---

## 测试报告格式

### Markdown 报告示例

````markdown
# 统一看护对话模式测试报告

**测试时间**：2026-02-16 14:30:00  
**测试设备**：test_device_001  
**服务器地址**：ws://localhost:8000

---

## 测试概览

| 指标     | 数值 |
| -------- | ---- |
| 总场景数 | 2    |
| 成功场景 | 2    |
| 失败场景 | 0    |
| 成功率   | 100% |

---

## 场景详情

### ✅ 场景1：仅对话模式

**状态**：成功  
**执行时间**：45 秒  
**看护模式**：未激活

**对话历史**：

1. 用户："有快递"
2. AI："您好,请问是什么快递呀？"
3. 用户："京东的,手机"
4. AI："好的,能帮我把快递放在门口吗？"
5. 用户："行,放这儿了啊"
6. AI："好的谢谢！"

**照片传递验证**：

| 轮次  | 传入图片数 | 预期 | 结果 |
| ----- | ---------- | ---- | ---- |
| 第1轮 | 1          | 1    | ✅   |
| 第2轮 | 1          | 1    | ✅   |
| 第3轮 | 1          | 1    | ✅   |

**Token消耗验证**：

| 轮次  | 实际Token | 预期Token | 结果 |
| ----- | --------- | --------- | ---- |
| 第1轮 | 7200      | ~7000     | ✅   |
| 第2轮 | 7100      | ~7000     | ✅   |
| 第3轮 | 7300      | ~7000     | ✅   |

**意图总结**：

```json
{
  "intent_type": "delivery",
  "summary": "快递员送达京东快递（手机）",
  "important_notes": ["【留言】京东快递,手机"],
  "ai_analysis": "访客是快递员,送来京东快递（手机）,已放置门口"
}
```
````

**验证结果**：

- ✅ 意图类型正确
- ✅ 包含关键词：快递、京东、手机
- ✅ 照片传递策略正确
- ✅ Token消耗符合预期
- ✅ 未执行快递状态检查
- ✅ 对话历史完整

---

### ✅ 场景2：统一模式（看护激活）

**状态**：成功  
**执行时间**：52 秒  
**看护模式**：激活

**对话历史**：（同场景1）

**照片传递验证**：

| 轮次  | 传入图片数 | 预期 | 结果 |
| ----- | ---------- | ---- | ---- |
| 第1轮 | 2          | 2    | ✅   |
| 第2轮 | 1          | 1    | ✅   |
| 第3轮 | 1          | 1    | ✅   |

**Token消耗验证**：

| 轮次  | 实际Token | 预期Token | 结果 |
| ----- | --------- | --------- | ---- |
| 第1轮 | 14200     | ~14000    | ✅   |
| 第2轮 | 7100      | ~7000     | ✅   |
| 第3轮 | 7300      | ~7000     | ✅   |

**照片缓存验证**：

| 时间点   | 缓存数量    | 最大限制 | 结果 |
| -------- | ----------- | -------- | ---- |
| 5秒      | 1           | 10       | ✅   |
| 10秒     | 2           | 10       | ✅   |
| 15秒     | 3           | 10       | ✅   |
| 对话结束 | 0（已清理） | -        | ✅   |

**快递状态检查**：

```json
{
  "threat_level": "low",
  "action": "normal",
  "description": "快递位置未变化,状态正常"
}
```

**意图总结**：（同场景1）

**验证结果**：

- ✅ 意图类型正确
- ✅ 照片传递策略正确（第一轮2张,后续1张）
- ✅ Token消耗符合预期（第一轮~14K,后续~7K）
- ✅ 照片缓存管理正常
- ✅ 执行了快递状态检查
- ✅ 照片缓存已清理
- ✅ 对话历史完整

---

## 性能统计

### Token消耗对比

| 模式     | 第一轮Token | 后续轮次Token | 10轮总Token | 节省比例 |
| -------- | ----------- | ------------- | ----------- | -------- |
| 仅对话   | 7K          | 7K            | 70K         | -        |
| 统一模式 | 14K         | 7K            | 77K         | 30%      |

**说明**：统一模式相比每轮都传基准图片节省约30% Token

### 响应时间统计

| 指标         | 仅对话模式 | 统一模式 |
| ------------ | ---------- | -------- |
| 平均响应时间 | 2.3秒      | 2.5秒    |
| 最大响应时间 | 3.1秒      | 3.8秒    |

---

## 问题总结

无问题发现

---

## 建议

1. Token优化效果显著,建议保持当前策略
2. 照片缓存管理正常,无需调整
3. 响应时间在可接受范围内

---

**测试完成时间**：2026-02-16 14:35:00  
**总耗时**：5 分钟

````

---

## 使用说明

### 环境准备

1. **安装依赖**：

```bash
cd main/xiaozhi-server
pip install websockets pillow pyyaml
````

2. **配置服务器白名单**：

编辑 `data/.config.yaml`,添加测试设备到白名单：

```yaml
server:
  auth:
    enabled: true
    allowed_devices:
      - test_device_001 # 添加测试设备
```

3. **准备测试图片**：

将访客照片和基准图片放置到对应目录。

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

---

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
- ✅ 只测试核心的统一模式流程

### 3. 性能考虑

- 每个场景独立连接,避免状态污染
- 使用异步 I/O,提高测试效率
- 合理设置超时时间,避免长时间等待

---

**文档维护者**：Kiro AI Assistant  
**最后更新**：2026-02-16  
**版本**：v2.0
