# 智能门锁VLLM两种模式流程详解

## 文档概述

本文档详细说明智能门锁系统中VLLM（视觉语言模型）的两种工作模式：

1. **意图识别模式**：访客到访时的对话意图分析
2. **看护监控模式**：快递看护的持续监控和威胁检测

## 核心组件

### DoorlockVLLMProvider

- 位置：`main/xiaozhi-server/core/providers/vllm/doorlock_vllm.py`
- 职责：门锁专用VLLM提供者，复用系统VLLM配置，支持工具函数调用
- 特性：
  - 多图片输入（单图片用于意图识别，双图片用于看护监控）
  - Token消耗统计和多层次监控
  - 提示词动态加载
  - 对话历史自动截断

### DoorlockTools

- 位置：`main/xiaozhi-server/core/providers/doorlock/doorlock_tools.py`
- 职责：提供AI可调用的工具函数
- 工具列表：
  - `enable_package_guard`：启用快递看护模式
  - `disable_package_guard`：关闭快递看护模式
  - `update_package_baseline`：更新看护基准图片
  - `report_package_status`：报告快递状态和威胁等级
  - `report_visitor_intent`：报告访客意图总结

---

## 模式一：意图识别模式

### 使用场景

访客到访时，通过人脸识别、对话交互和图像分析，识别访客意图并生成结构化总结。

### 触发条件

- PIR传感器检测到人体
- 访客无开门权限或人脸识别失败
- 需要与访客进行对话交互

### 完整流程

#### 1. 访客到访处理入口

**处理器**：`DoorlockIntentHandler.handle_visitor()`

**流程步骤**：

```
1. 生成会话ID（如果未提供）
2. 检查看护模式是否激活
3. 拍摄访客照片（如果未提供）
4. 执行人脸识别（支持重试）
5. 判断开门权限
   - 有权限 → 下发face_result + 播放欢迎词 → 结束
   - 无权限/识别失败 → 继续意图识别流程
6. 启动意图识别对话
7. 生成意图总结
8. 保存访问记录
9. 发送App通知
```

**关键代码位置**：

- `main/xiaozhi-server/core/handle/doorlock_intent_handler.py`
- 方法：`handle_visitor()`, `start_intent_dialogue()`

#### 2. 意图识别对话循环

**处理器**：`DoorlockIntentHandler.start_intent_dialogue()`

**流程步骤**：

```
1. 播放主动问候
   - 已识别但无权限："您好，{姓名}，请问有什么可以帮您？"
   - 陌生人："您好，请问您找谁？"

2. 进入对话循环（最多10轮）
   while 对话未结束:
     a. 检查结束条件（沉默30秒或PIR无人体）
     b. 等待访客语音回复（ASR识别）
     c. 添加访客回复到对话历史
     d. 调用VLLM进行意图识别
     e. 播放AI回复（TTS合成）
     f. 执行工具调用（如果有）
     g. 检查Token使用量

3. 对话结束后生成意图总结
```

#### 3. VLLM意图分析

**方法**：`DoorlockVLLMProvider.analyze_intent()`

**输入参数**：

- `visitor_image`：访客照片（Base64编码）
- `dialogue_history`：对话历史列表
- `system_prompt`：意图识别提示词（从配置加载）

**处理流程**：

```
1. 检查图片Token限制
   - 1张图片估算约7000 tokens
   - 超过max_image_tokens则报错

2. 构建消息列表
   - 添加系统提示词
   - 截断对话历史（基于Token限制）
   - 添加当前问题和访客图片

3. 调用OpenAI API
   - model: 从系统配置获取
   - messages: 构建的消息列表
   - tools: DoorlockTools的JSON Schema
   - max_tokens: 限制输出长度

4. 解析响应
   - content: AI回复文本
   - tool_calls: 工具调用列表
   - token_usage: Token统计

5. 多层次Token检查
   - 输出Token使用率（影响回复完整性）
   - 输入Token使用率（影响上下文容量）
   - 总Token使用率（接近模型上限）
```

**Token限制策略**：

```python
# 固定部分Token
system_tokens = 估算系统提示词
question_tokens = 估算问题文本
image_tokens = 7000 * 图片数量

# 对话历史可用Token
available_for_history = min(
    max_input_tokens - fixed_tokens - max_tokens,  # 基于输入限制
    model_context_limit - fixed_tokens - max_tokens  # 基于总限制
)

# 截断对话历史（保留最近的对话）
truncated_history = 从最新开始累加，直到达到available_for_history
```

#### 4. 工具调用执行

**方法**：`DoorlockVLLMProvider.execute_tool_calls()`

**支持的工具**：

- `enable_package_guard`：访客提到"快递放门口了"时调用
- `report_visitor_intent`：对话结束时生成意图总结

**执行流程**：

```
for tool_call in tool_calls:
    1. 提取工具名称和参数
    2. 调用DoorlockTools.call_tool()
    3. 记录执行结果
    4. 处理异常情况
```

#### 5. 意图总结生成

**方法**：`DoorlockIntentHandler.generate_intent_summary()`

**输出格式**：

```json
{
  "important_notes": ["【留言】明天下午3点再来", "【提醒】带了礼物放门口"],
  "intent_type": "delivery|visit|sales|maintenance|other",
  "purpose": "来访目的简述",
  "full_summary": "完整的对话总结"
}
```

**生成方式**：

- 方式1：调用VLLM生成结构化总结（推荐）
- 方式2：基于关键词规则提取（当前实现）

#### 6. 数据保存和通知

**流程**：

```
1. 保存访问记录到数据库
   - 表：visitor_intents
   - 字段：session_id, person_id, intent_type, intent_summary, dialogue_history

2. 发送App通知
   - 通知类型：访客意图识别
   - 内容：人员信息、意图总结、对话文本
```

---

## 模式二：看护监控模式

### 使用场景

快递放置门口后，持续监控门口状态，检测异常行为（拿走、翻找、破坏），并根据威胁等级响应。

### 触发条件

- 用户通过App或AI对话启用看护模式
- 设备配置中`package_guard_available=true`
- 已设置基准图片（快递初始状态）

### 完整流程

#### 1. 启用看护模式

**入口1：HTTP API**

- 端点：`POST /api/doorlock/package_guard/start`
- 处理器：`DoorlockGuardHandler.handle_start()`

**入口2：AI工具调用**

- 工具：`enable_package_guard`
- 触发：访客对话中提到"快递放门口了"

**流程步骤**：

```
1. 验证参数
   - device_id: 设备ID（必填）
   - reason: 启用原因（必填）

2. 检查设备配置
   - 验证package_guard_available=true
   - 如果为false，返回错误

3. 更新配置
   - package_guard_active = true
   - package_guard_start_time = 当前时间

4. 发送状态变化通知
   - 通知App看护模式已启用
   - 包含基准图片和启动时间
```

#### 2. 监控循环启动

**管理器**：`PackageGuardManager.start_monitoring()`

**流程步骤**：

```
1. 检查是否已有监控任务
   - 如果有，先停止旧任务

2. 创建异步监控任务
   - 使用asyncio.create_task()
   - 任务函数：_monitoring_loop()

3. 记录任务到字典
   - _monitoring_tasks[device_id] = task
```

#### 3. 持续监控循环

**方法**：`PackageGuardManager._monitoring_loop()`

**循环逻辑**：

```
while True:
    1. 检查看护模式是否仍然激活
       - 如果已关闭，退出循环

    2. 等待5秒（photo_interval配置）

    3. 执行拍照和分析
       - 调用_capture_and_analyze()

    4. 处理异常
       - CancelledError: 任务被取消
       - 其他异常: 记录日志继续运行
```

#### 4. 拍照和VLLM分析

**方法**：`PackageGuardManager._capture_and_analyze()`

**流程步骤**：

```
1. 拍摄当前照片
   - 通过ESP32 MCP协议请求拍照
   - 如果失败，跳过本次分析

2. 加载基准图片
   - 优先从缓存读取
   - 缓存未命中则从文件系统读取
   - 如果不存在，跳过本次分析

3. 调用VLLM分析
   - 方法：_analyze_with_vllm()
   - 输入：当前图片 + 基准图片

4. 处理分析结果
   - 方法：_handle_analysis_result()
```

#### 5. VLLM威胁分析

**方法**：`DoorlockVLLMProvider.analyze_package_status()`

**输入参数**：

- `current_image`：当前图片（Base64编码）
- `baseline_image`：基准图片（Base64编码）
- `dialogue_history`：对话历史（可选）
- `system_prompt`：看护模式提示词（从配置加载）

**处理流程**：

```
1. 检查图片Token限制
   - 2张图片估算约14000 tokens
   - 超过max_image_tokens则报错

2. 构建问题文本
   "请对比当前图片和基准图片，判断门口快递的状态变化和威胁等级。
    第一张图片是基准图片（之前的状态）
    第二张图片是当前图片（现在的状态）
    请调用 report_package_status 工具报告情况。"

3. 构建消息列表
   - 添加系统提示词（看护模式专用）
   - 截断对话历史（如果有）
   - 添加问题文本
   - 添加2张图片（基准图片在前，当前图片在后）

4. 调用OpenAI API
   - tools: 包含report_package_status工具
   - 期望AI调用工具报告威胁等级

5. 解析工具调用
   - 提取action（行为类型）
   - 提取threat_level（威胁等级）
   - 提取description（详细描述）
```

**威胁等级定义**：

```
low（低威胁）：
  - action: passing（路人经过）
  - action: normal（正常状态）
  - 响应：不处理

medium（中威胁）：
  - action: searching（翻找快递）
  - 响应：语音提示 + App通知
  - 语音："请问有什么可以帮您？"

high（高威胁）：
  - action: taking（拿走快递）
  - action: damaging（破坏快递）
  - 响应：语音警告 + App通知
  - 语音："您的行为已被记录，请立即停止"
```

#### 6. 威胁响应处理

**方法**：`PackageGuardManager._handle_analysis_result()`

**流程步骤**：

```
1. 保存警报记录
   - 表：package_alerts
   - 字段：device_id, session_id, threat_level, action, description, photo_path

2. 根据威胁等级响应

   if threat_level == "low":
       - 不处理，仅记录日志

   elif threat_level == "medium":
       - 播放语音提示："请问有什么可以帮您？"
       - 发送App通知（中等威胁）
       - 更新alert记录：voice_warning_sent=true, notified=true

   elif threat_level == "high":
       - 播放语音警告："您的行为已被记录，请立即停止"
       - 发送App通知（高威胁）
       - 更新alert记录：voice_warning_sent=true, notified=true
```

#### 7. 关闭看护模式

**入口1：HTTP API**

- 端点：`POST /api/doorlock/package_guard/stop`
- 处理器：`DoorlockGuardHandler.handle_stop()`

**入口2：AI工具调用**

- 工具：`disable_package_guard`
- 触发：AI判断主人已取走快递

**流程步骤**：

```
1. 停止监控循环
   - 取消异步任务
   - 清理任务字典

2. 更新配置
   - package_guard_active = false

3. 发送状态变化通知
   - 通知App看护模式已关闭
```

---

## 配置文件

### 系统配置（config.yaml）

```yaml
selected_module:
  VLLM: "qwen_vl" # 选择的VLLM提供者

VLLM:
  qwen_vl:
    model_name: "Qwen2-VL-7B-Instruct"
    api_key: "your-api-key"
    base_url: "http://localhost:8001/v1"
    max_tokens: 500
    temperature: 0.7
    top_p: 1.0
```

### 门锁配置（config/doorlock_config.yaml）

```yaml
performance:
  max_token_usage_ratio: 0.8 # 输出Token警告阈值

  vllm_limits:
    model_context_limit: 262144 # 模型上下文窗口
    max_input_tokens: 260096 # 最大输入Token
    max_output_tokens: 32768 # 最大输出Token
    max_image_tokens: 16384 # 最大图片Token
    tokens_per_image: 7000 # 每张图片Token数
    input_warning_ratio: 0.8 # 输入Token警告阈值
    total_warning_ratio: 0.8 # 总Token警告阈值

package_guard:
  photo_interval: 5 # 拍照间隔（秒）
  baseline_dir: "data/face_recognition/package_baseline/" # 基准图片目录

intent_recognition:
  dialogue_timeout: 30 # 对话超时（秒）
  max_dialogue_rounds: 10 # 最大对话轮次
```

### 提示词配置（config/doorlock_prompts.yaml）

```yaml
intent_recognition_prompt: |
  你是智能门锁的AI助手，负责与访客对话并识别其来访意图。

  任务：
  1. 与访客进行自然对话，了解来访目的
  2. 识别意图类型（delivery/visit/sales/maintenance/other）
  3. 提取重要信息（留言、提醒）
  4. 对话结束时调用report_visitor_intent工具生成总结

  注意：
  - 如果访客提到"快递放门口了"，调用enable_package_guard启用看护
  - 保持礼貌友好的对话风格
  - 不要主动结束对话，等待访客沉默或离开

package_guard_prompt: |
  你是智能门锁的看护AI，负责监控门口快递的安全。

  任务：
  1. 对比基准图片和当前图片，判断快递状态变化
  2. 识别人物行为（taking/searching/damaging/normal/passing）
  3. 评估威胁等级（low/medium/high）
  4. 调用report_package_status工具报告情况

  威胁等级判断：
  - low: 路人经过、无异常
  - medium: 有人翻找快递、靠近观察
  - high: 有人拿走快递、破坏快递

  注意：
  - 准确描述你看到的情况
  - 不要误判正常行为为威胁
```

---

## Token管理策略

### Token估算方法

```python
def _estimate_tokens(text: str) -> int:
    """估算文本Token数量"""
    chinese_chars = 统计中文字符数
    other_chars = 统计其他字符数

    estimated_tokens = int(
        chinese_chars / 1.5 +  # 中文约1.5字符/Token
        other_chars / 4         # 英文约4字符/Token
    )

    return estimated_tokens

def _estimate_image_tokens(image_count: int) -> int:
    """估算图片Token数量"""
    return image_count * tokens_per_image  # 默认7000/张
```

### 对话历史截断

```python
def _truncate_dialogue_history(
    dialogue_history: List[Dict],
    max_tokens: int
) -> List[Dict]:
    """截断对话历史以满足Token限制"""

    # 从最新的对话开始累加
    truncated = []
    current_tokens = 0

    for msg in reversed(dialogue_history):
        msg_tokens = _estimate_tokens(msg["content"])

        if current_tokens + msg_tokens > max_tokens:
            break  # 超出限制，停止添加

        truncated.insert(0, msg)
        current_tokens += msg_tokens

    return truncated
```

### 多层次Token监控

```python
def _check_token_usage(token_usage: dict, response_time: float, tool_calls_count: int):
    """多层次检查Token使用情况"""

    # 1. 输出Token使用率（主要警告）
    output_usage_ratio = completion_tokens / max_tokens
    if output_usage_ratio > 0.8:
        logger.warning("输出Token接近限制，AI回复可能被截断")

    # 2. 输入Token使用率（次要警告）
    input_usage_ratio = prompt_tokens / max_input_tokens
    if input_usage_ratio > 0.8:
        logger.warning("输入Token较高，建议优化提示词或减少对话历史")

    # 3. 总Token使用率（严重警告）
    total_usage_ratio = total_tokens / model_context_limit
    if total_usage_ratio > 0.8:
        logger.warning("总Token接近上下文窗口，接近模型上限")

    # 4. 记录详细统计
    logger.info(f"VLLM调用统计 | 输入: {prompt_tokens} | 输出: {completion_tokens} | "
                f"总计: {total_tokens} | 响应时间: {response_time:.2f}s | "
                f"工具调用: {tool_calls_count}")
```

---

## 数据库表结构

### visitor_intents（访客意图记录）

```sql
CREATE TABLE visitor_intents (
    id INT PRIMARY KEY AUTO_INCREMENT,
    visit_id INT,  -- 关联visit_records表
    session_id VARCHAR(64) NOT NULL,
    person_id INT,  -- 关联persons表，陌生人为NULL
    intent_type ENUM('delivery', 'visit', 'sales', 'maintenance', 'other'),
    intent_summary JSON,  -- 意图总结（important_notes, purpose, full_summary）
    dialogue_history JSON,  -- 对话历史
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### package_alerts（快递警报记录）

```sql
CREATE TABLE package_alerts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    device_id VARCHAR(64) NOT NULL,
    session_id VARCHAR(64) NOT NULL,
    threat_level ENUM('low', 'medium', 'high'),
    action ENUM('taking', 'searching', 'damaging', 'normal', 'passing'),
    description TEXT,  -- AI生成的详细描述
    photo_path VARCHAR(255),  -- 当前照片路径
    voice_warning_sent BOOLEAN DEFAULT FALSE,
    notified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### doorlock_configs（设备配置）

```sql
CREATE TABLE doorlock_configs (
    device_id VARCHAR(64) PRIMARY KEY,
    package_guard_available BOOLEAN DEFAULT FALSE,  -- 看护功能是否可用
    package_guard_active BOOLEAN DEFAULT FALSE,     -- 看护模式是否激活
    package_baseline_image VARCHAR(255),            -- 基准图片路径
    package_guard_start_time TIMESTAMP,             -- 看护启动时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

---

## 关键差异对比

| 特性      | 意图识别模式                                | 看护监控模式             |
| --------- | ------------------------------------------- | ------------------------ |
| 触发方式  | PIR检测到访客                               | 用户主动启用或AI判断     |
| 图片输入  | 1张（访客照片）                             | 2张（基准图片+当前图片） |
| 运行方式  | 单次对话流程                                | 持续循环监控             |
| 对话历史  | 完整对话历史                                | 可选（通常为空）         |
| 工具调用  | report_visitor_intent, enable_package_guard | report_package_status    |
| 输出结果  | 意图总结（JSON）                            | 威胁等级和行为类型       |
| 响应动作  | 播放AI回复、发送通知                        | 语音警告、发送警报       |
| 结束条件  | 对话超时或PIR无人体                         | 用户关闭或AI判断结束     |
| Token消耗 | 较高（多轮对话）                            | 中等（每5秒一次分析）    |

---

## 最佳实践

### 意图识别模式

1. **提示词优化**：明确告知AI需要识别的意图类型和重要信息
2. **对话控制**：设置合理的超时时间和最大轮次，避免无限对话
3. **Token管理**：优先保留最近的对话，截断早期对话历史
4. **工具调用**：确保AI在对话结束时调用report_visitor_intent生成总结

### 看护监控模式

1. **基准图片**：确保基准图片清晰，包含完整的快递和门口环境
2. **拍照间隔**：5秒间隔平衡实时性和系统负载
3. **威胁判断**：提示词中明确威胁等级的判断标准
4. **误报控制**：避免将正常行为（如主人取快递）判断为威胁

### Token优化

1. **图片分辨率**：使用VGA分辨率（640x480），每张约7000 tokens
2. **提示词精简**：去除冗余描述，保留核心指令
3. **对话历史**：根据Token限制动态截断，优先保留最近对话
4. **监控告警**：设置多层次Token监控，及时发现异常

---

## 故障排查

### 常见问题

1. **Token超限导致回复被截断**
   - 现象：AI回复不完整或突然中断
   - 原因：completion_tokens达到max_tokens限制
   - 解决：增加max_tokens配置或优化提示词

2. **对话历史被过度截断**
   - 现象：AI无法理解上下文，重复提问
   - 原因：available_for_history过小，对话历史被清空
   - 解决：减少系统提示词长度或降低图片分辨率

3. **看护模式误报**
   - 现象：正常行为被判断为高威胁
   - 原因：提示词不够明确或基准图片不清晰
   - 解决：优化提示词，重新拍摄基准图片

4. **VLLM响应慢**
   - 现象：每次分析耗时超过5秒
   - 原因：模型推理慢或网络延迟
   - 解决：优化模型配置或增加拍照间隔

---

## 总结

智能门锁VLLM系统通过两种模式实现了完整的访客管理和快递看护功能：

1. **意图识别模式**：通过单图片+对话历史，实现访客意图的智能识别和结构化总结
2. **看护监控模式**：通过双图片对比，实现快递状态的持续监控和威胁检测

两种模式共享同一个VLLM提供者，通过不同的提示词和工具函数实现差异化功能，充分利用了视觉语言模型的多模态能力。
