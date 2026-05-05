# DoorlockIntentHandler API 参考文档

## 概述

`DoorlockIntentHandler` 是智能门锁系统的意图处理器，负责管理访客对话流程、看护监控和照片缓存。该类位于 `core/handle/doorlock_intent_handler.py`，提供统一的对话和看护模式支持。

## 核心特性

- **统一对话流程**：同时处理访客对话和快递看护任务
- **定时拍照机制**：对话期间每 5 秒自动拍照并缓存
- **照片缓存管理**：智能管理最近 10 张照片
- **对话结束后处理**：自动执行快递检查和意图总结
- **工具调用执行**：支持 AI 调用系统工具函数
- **高威胁打断**：检测到高威胁时立即警告

## 主要方法

### start_unified_dialogue

启动统一模式对话（支持看护）。

#### 方法签名

```python
async def start_unified_dialogue(
    self,
    device_id: str,
    session_id: str,
    person_info: Optional[Dict[str, Any]],
    visitor_image: bytes,
    conn=None
) -> Dict[str, Any]
```

#### 参数说明

| 参数            | 类型                       | 必需 | 说明                     |
| --------------- | -------------------------- | ---- | ------------------------ |
| `device_id`     | `str`                      | 是   | 设备 ID                  |
| `session_id`    | `str`                      | 是   | 会话 ID                  |
| `person_info`   | `Optional[Dict[str, Any]]` | 否   | 人员信息（人脸识别结果） |
| `visitor_image` | `bytes`                    | 是   | 访客照片（原始字节）     |
| `conn`          | 连接对象                   | 否   | WebSocket 连接对象       |

#### 返回值

```python
{
    "success": bool,              # 是否成功
    "action": str,                # 操作类型："intent_recognized"
    "visit_id": int,              # 访问记录 ID
    "intent_summary": Dict,       # 意图总结
    "dialogue_count": int,        # 对话轮次
    "package_check": Optional[Dict]  # 快递检查结果（看护激活时）
}
```

#### 核心流程

1. **检查看护模式状态**
   - 查询数据库获取看护模式配置
   - 如果激活，加载基准图片

2. **保存初次访客照片**
   - 用于后续意图总结生成

3. **启动定时拍照任务**
   - 每 5 秒拍照一次
   - 照片缓存到 PhotoCacheManager

4. **播放主动问候**
   - 使用 TTS 播放问候语音

5. **进入对话循环**
   - 等待访客语音回复（ASR 识别）
   - 将访客语音文本添加到对话历史
   - 从 PhotoCacheManager 获取最新缓存照片
   - 调用 VLLM 统一分析
   - 播放 AI 回复（TTS）
   - 处理工具调用
   - 检查对话结束条件

6. **停止定时拍照任务**

7. **对话结束后处理**
   - 检查快递状态（如果看护激活）
   - 生成访客意图总结
   - 保存访问记录
   - 发送 App 通知
   - 清理会话
   - 清理照片缓存

#### 对话结束条件

- 沉默超过 30 秒
- PIR 无人体检测
- AI 主动结束对话
- 达到最大对话轮次（10 轮）

#### 使用示例

```python
# 示例 1：看护模式激活时的对话
result = await intent_handler.start_unified_dialogue(
    device_id="doorlock_001",
    session_id="session_123",
    person_info=None,  # 未识别的访客
    visitor_image=visitor_image_bytes,
    conn=websocket_conn
)

print(f"对话轮次: {result['dialogue_count']}")
print(f"意图类型: {result['intent_summary']['intent_type']}")

if result.get('package_check'):
    print(f"快递状态: {result['package_check']['threat_level']}")

# 示例 2：仅对话模式（看护未激活）
result = await intent_handler.start_unified_dialogue(
    device_id="doorlock_001",
    session_id="session_124",
    person_info=None,
    visitor_image=visitor_image_bytes,
    conn=websocket_conn
)

# 不会有 package_check 结果
assert 'package_check' not in result
```

#### Token 消耗参考

| 场景                | 对话轮次 | 总 Token 消耗 |
| ------------------- | -------- | ------------- |
| 看护激活（10 轮）   | 10       | ~100K         |
| 看护激活（5 轮）    | 5        | ~65K          |
| 仅对话模式（10 轮） | 10       | ~85K          |

---

### start_photo_capture_task

启动定时拍照任务。

#### 方法签名

```python
async def start_photo_capture_task(
    self,
    device_id: str,
    session_id: str,
    interval_seconds: int = 5
)
```

#### 参数说明

| 参数               | 类型  | 必需 | 说明                      |
| ------------------ | ----- | ---- | ------------------------- |
| `device_id`        | `str` | 是   | 设备 ID                   |
| `session_id`       | `str` | 是   | 会话 ID                   |
| `interval_seconds` | `int` | 否   | 拍照间隔（秒），默认 5 秒 |

#### 核心逻辑

1. 创建异步定时任务
2. 每隔指定时间调用 ESP32 拍照接口
3. 将照片添加到 PhotoCacheManager
4. 记录任务 ID 用于后续停止
5. 异常处理：拍照失败时记录日志但继续运行

#### 使用示例

```python
# 启动定时拍照任务
await intent_handler.start_photo_capture_task(
    device_id="doorlock_001",
    session_id="session_123",
    interval_seconds=5
)

# 任务在后台运行，不阻塞对话
```

#### 注意事项

- 任务在后台异步运行，不阻塞对话流程
- 拍照失败不会中断任务，会继续下一次拍照
- 必须在对话结束后调用 `stop_photo_capture_task` 停止任务

---

### stop_photo_capture_task

停止定时拍照任务。

#### 方法签名

```python
async def stop_photo_capture_task(self, session_id: str)
```

#### 参数说明

| 参数         | 类型  | 必需 | 说明    |
| ------------ | ----- | ---- | ------- |
| `session_id` | `str` | 是   | 会话 ID |

#### 核心逻辑

1. 查找对应会话的拍照任务
2. 取消异步任务
3. 清理任务引用
4. 记录停止日志

#### 使用示例

```python
# 对话结束后停止拍照任务
await intent_handler.stop_photo_capture_task(
    session_id="session_123"
)
```

#### 注意事项

- 必须在对话结束后调用，否则任务会持续运行
- 如果任务不存在，不会抛出异常
- 停止后无法恢复，需要重新启动

---

### \_post_dialogue_processing

对话结束后的处理流程（内部方法）。

#### 方法签名

```python
async def _post_dialogue_processing(
    self,
    device_id: str,
    session_id: str,
    visitor_image: bytes,
    baseline_image: Optional[bytes],
    dialogue_history: List[Dict[str, str]]
) -> Dict[str, Any]
```

#### 参数说明

| 参数               | 类型                   | 必需 | 说明                   |
| ------------------ | ---------------------- | ---- | ---------------------- |
| `device_id`        | `str`                  | 是   | 设备 ID                |
| `session_id`       | `str`                  | 是   | 会话 ID                |
| `visitor_image`    | `bytes`                | 是   | 初次访客照片           |
| `baseline_image`   | `Optional[bytes]`      | 否   | 基准图片（看护激活时） |
| `dialogue_history` | `List[Dict[str, str]]` | 是   | 完整对话历史           |

#### 返回值

```python
{
    "package_check": Optional[Dict],  # 快递检查结果
    "intent_summary": Dict,           # 意图总结
    "visit_id": int                   # 访问记录 ID
}
```

#### 处理步骤

**步骤 1：检查快递状态**（如果看护激活）

- 使用最后一张缓存照片
- 调用 VLLM 检查快递状态
- 如果检测到威胁，保存警报

**步骤 2：生成访客意图总结**

- 调用 VLLM 生成总结
- 解析结构化结果

**步骤 3：保存访问记录**

- 保存到数据库

**步骤 4：发送 App 通知**

- 通知房主访客信息

**步骤 5：清理会话**

- 清理会话数据

**步骤 6：清理照片缓存**

- 清理 PhotoCacheManager 中的照片

#### 使用示例

```python
# 对话结束后自动调用（内部方法）
result = await self._post_dialogue_processing(
    device_id="doorlock_001",
    session_id="session_123",
    visitor_image=visitor_image_bytes,
    baseline_image=baseline_image_bytes,
    dialogue_history=dialogue_history
)

# 处理结果
if result.get('package_check'):
    threat_level = result['package_check']['threat_level']
    if threat_level == 'high':
        # 发送紧急警报
        await send_emergency_alert(device_id, result['package_check'])
```

---

### \_handle_tool_calls

处理工具调用（内部方法）。

#### 方法签名

```python
async def _handle_tool_calls(
    self,
    tool_calls: List[Dict[str, Any]],
    device_id: str,
    session_id: str
) -> List[Dict[str, Any]]
```

#### 参数说明

| 参数         | 类型                   | 必需 | 说明         |
| ------------ | ---------------------- | ---- | ------------ |
| `tool_calls` | `List[Dict[str, Any]]` | 是   | 工具调用列表 |
| `device_id`  | `str`                  | 是   | 设备 ID      |
| `session_id` | `str`                  | 是   | 会话 ID      |

#### 返回值

工具调用结果列表。

#### 核心逻辑

1. 遍历工具调用列表
2. 补充必要参数（device_id, session_id）
3. 执行工具函数
4. 高威胁特殊处理：
   - 如果是 `report_package_status` 且威胁等级为 `high`
   - 立即播放警告语音
   - 可以打断对话
5. 异常处理和日志记录

#### 支持的工具函数

| 工具名称                  | 说明         | 参数                                                     |
| ------------------------- | ------------ | -------------------------------------------------------- |
| `enable_package_guard`    | 启用看护模式 | device_id, reason                                        |
| `disable_package_guard`   | 关闭看护模式 | device_id, reason                                        |
| `update_package_baseline` | 更新基准图片 | device_id                                                |
| `report_package_status`   | 报告快递状态 | device_id, session_id, action, threat_level, description |

#### 使用示例

```python
# AI 返回的工具调用
tool_calls = [
    {
        "name": "report_package_status",
        "arguments": {
            "action": "taking",
            "threat_level": "high",
            "description": "检测到非主人拿走快递"
        }
    }
]

# 处理工具调用
results = await self._handle_tool_calls(
    tool_calls=tool_calls,
    device_id="doorlock_001",
    session_id="session_123"
)

# 高威胁时会自动播放警告语音
```

---

## 定时拍照机制

### 工作原理

```
对话开始
  ↓
启动定时拍照任务
  ↓
┌─────────────────────┐
│  每 5 秒执行一次     │
│  ├─ 调用 ESP32 拍照  │
│  ├─ 获取照片数据     │
│  └─ 添加到缓存       │
└─────────────────────┘
  ↓
对话进行中
  ├─ 每轮对话使用最新缓存照片
  ├─ 不需要等待拍照
  └─ 响应速度快
  ↓
对话结束
  ↓
停止定时拍照任务
  ↓
清理照片缓存
```

### 优势

1. **提高响应速度**：对话中不需要等待拍照
2. **实时捕捉变化**：每 5 秒更新一次照片
3. **后台运行**：不阻塞对话流程
4. **自动管理**：超过 10 张自动清理旧照片

### 配置项

```yaml
# config/doorlock_config.yaml
photo_cache:
  interval_seconds: 5 # 拍照间隔（秒）
  max_cache_size: 10 # 最大缓存数量
```

---

## 照片缓存管理

### PhotoCacheManager

照片缓存管理器，负责管理对话期间的照片缓存。

#### 核心方法

**add_photo**：添加照片到缓存

```python
photo_cache_manager.add_photo(
    session_id="session_123",
    photo_data=photo_bytes
)
```

**get_latest_photo**：获取最新照片

```python
latest_photo = photo_cache_manager.get_latest_photo(
    session_id="session_123"
)
```

**clear_cache**：清理缓存

```python
photo_cache_manager.clear_cache(
    session_id="session_123"
)
```

### 缓存策略

- 按 session_id 隔离缓存
- 最多保留最近 10 张照片
- 超过限制时自动清理最旧的照片
- 对话结束后清理所有缓存

### 内存管理

- 照片以 Base64 编码存储
- 单张照片约 100-200KB
- 10 张照片约 1-2MB
- 对话结束后立即释放

---

## 对话流程图

```
访客到访
  ↓
PIR 检测 + 初次拍照
  ↓
人脸识别 + 权限检查
  ↓
[无权限] → 启动统一模式对话
  ↓
检查看护模式状态
  ├─ 未激活 → 仅对话模式
  └─ 已激活 → 加载基准图片
       ↓
     保存初次访客照片
       ↓
     启动定时拍照任务（每 5 秒）
       ↓
     播放主动问候
       ↓
     第一轮对话
       ├─ 等待访客语音回复（ASR）
       ├─ 获取最新缓存照片
       ├─ 调用 VLLM 分析（访客语音 + 照片 + 基准图片）
       ├─ 播放 AI 回复（TTS）
       ├─ 处理工具调用
       └─ 检查对话结束条件
       ↓
     后续对话（2-10 轮）
       ├─ 等待访客语音回复（ASR）
       ├─ 获取最新缓存照片
       ├─ 调用 VLLM 分析（访客语音 + 照片）
       ├─ 播放 AI 回复（TTS）
       ├─ 处理工具调用
       └─ 检查对话结束条件
       ↓
     对话结束
       ↓
     停止定时拍照任务
       ↓
     对话结束后处理
       ├─ 步骤 1：检查快递状态（如果看护激活）
       ├─ 步骤 2：生成意图总结
       ├─ 步骤 3：保存访问记录
       ├─ 步骤 4：发送 App 通知
       ├─ 步骤 5：清理会话
       └─ 步骤 6：清理照片缓存
```

---

## 错误处理

### 常见异常

| 异常类型    | 触发条件       | 处理方式               |
| ----------- | -------------- | ---------------------- |
| `Exception` | VLLM 调用失败  | 返回默认响应，对话继续 |
| `Exception` | 拍照失败       | 记录日志，任务继续运行 |
| `Exception` | 工具调用失败   | 记录日志，对话继续     |
| `Exception` | 数据库操作失败 | 记录日志，返回错误信息 |

### 降级策略

1. **VLLM 调用失败**：返回默认响应，对话可以继续
2. **拍照失败**：使用上一张缓存照片，任务继续运行
3. **工具调用失败**：记录日志，不影响对话流程
4. **数据库失败**：记录日志，返回错误但不崩溃

---

## 性能指标

### 响应时间参考

| 操作           | 目标时间 | 说明                  |
| -------------- | -------- | --------------------- |
| 单轮对话       | <5 秒    | 包含 ASR + VLLM + TTS |
| 拍照操作       | <1 秒    | ESP32 拍照            |
| 对话结束后处理 | <10 秒   | 包含检查和总结        |
| 完整对话流程   | <2 分钟  | 10 轮对话             |

### Token 消耗参考

| 场景                | 对话轮次 | 总 Token 消耗 |
| ------------------- | -------- | ------------- |
| 看护激活（10 轮）   | 10       | ~100K         |
| 看护激活（5 轮）    | 5        | ~65K          |
| 仅对话模式（10 轮） | 10       | ~85K          |

---

## 最佳实践

### 1. 会话管理

```python
# ✓ 推荐：对话结束后清理会话
try:
    result = await intent_handler.start_unified_dialogue(...)
finally:
    # 确保清理资源
    await intent_handler.stop_photo_capture_task(session_id)
    photo_cache_manager.clear_cache(session_id)

# ✗ 不推荐：不清理会话
result = await intent_handler.start_unified_dialogue(...)
# 内存泄漏风险
```

### 2. 异常处理

```python
# ✓ 推荐：捕获异常并记录
try:
    result = await intent_handler.start_unified_dialogue(...)
except Exception as e:
    logger.error(f"对话异常: {e}")
    # 清理资源
    await cleanup_session(session_id)
    return error_response

# ✗ 不推荐：不处理异常
result = await intent_handler.start_unified_dialogue(...)
# 可能导致程序崩溃
```

### 3. 照片缓存

```python
# ✓ 推荐：使用最新缓存照片
latest_photo = photo_cache_manager.get_latest_photo(session_id)
if latest_photo:
    result = await vllm.analyze_unified(
        visitor_image=latest_photo,
        ...
    )

# ✗ 不推荐：每次都重新拍照
photo = await esp32.take_photo()  # 阻塞对话
result = await vllm.analyze_unified(
    visitor_image=photo,
    ...
)
```

### 4. 日志记录

```python
# ✓ 推荐：记录关键流程
logger.info(
    f"对话开始 - "
    f"设备: {device_id}, "
    f"会话: {session_id}, "
    f"看护: {guard_enabled}"
)

# ✗ 不推荐：记录敏感数据
logger.info(f"访客照片: {visitor_image}")  # 泄露隐私
```

---

## 配置项

### doorlock_config.yaml

```yaml
# 统一模式配置
unified_mode:
  enabled: true # 启用统一模式

  # 对话配置
  dialogue:
    max_rounds: 10 # 最大对话轮次
    timeout_seconds: 30 # 沉默超时时间（秒）

  # 看护配置
  guard:
    threat_detection: "behavior_based" # 基于行为触发
    report_threshold: "medium" # 威胁等级≥medium 时报告

# 照片缓存配置
photo_cache:
  interval_seconds: 5 # 拍照间隔（秒）
  max_cache_size: 10 # 最大缓存数量
```

---

## 相关文档

- [VLLM 提供者 API 参考](./doorlock-vllm-api-reference.md)
- [统一模式设计文档](./unified-guard-dialogue-implementation.md)
- [照片缓存实现总结](./photo-capture-task-implementation.md)
- [配置指南](./doorlock-configuration-guide.md)

---

## 更新日志

| 版本  | 日期       | 说明                                         |
| ----- | ---------- | -------------------------------------------- |
| 1.0.0 | 2024-02-16 | 初始版本，包含统一模式核心方法和定时拍照机制 |
