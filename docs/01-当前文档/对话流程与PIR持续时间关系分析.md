# 对话流程与PIR持续时间关系分析

## 对话部分的作用

### 1. 对话触发场景

对话只在以下情况启动：

```
访客到访
  ↓
人脸识别
  ├─ 识别成功 + 有权限 → ✅ 开锁 + 播放欢迎词（无对话）
  └─ 识别失败 或 无权限 → ❌ 拒绝开锁 + 启动意图识别对话
```

### 2. 对话的目的

**核心目标：** 识别访客意图并记录留言

**具体功能：**

- 主动询问访客来访目的
- 通过多轮对话了解访客需求
- 识别意图类型（送快递、拜访、推销、维修等）
- 提取重要信息（留言、提醒事项）
- 生成结构化总结发送给App

### 3. 对话流程示例

```
AI: "您好，请问您找谁？"
访客: "我是快递员，有您的快递"
AI: "好的，请把快递放在门口就可以了，有什么需要转达的吗？"
访客: "这是易碎品，请小心拿取"
AI: "好的，我会转告主人。还有其他事情吗？"
访客: "没有了，谢谢"
AI: "好的，再见"

（访客离开或沉默30秒）

生成意图总结：
{
  "intent_type": "delivery",
  "important_notes": ["【留言】这是易碎品，请小心拿取"],
  "purpose": "送快递",
  "full_summary": "快递员送快递，提醒易碎品需小心拿取"
}
```

## 对话结束判定机制

### 判定条件（两个条件满足其一即结束）

#### 条件1：PIR检测不到人体

```python
async def check_dialogue_end(self, session_id: str, pir_detected: bool = True) -> bool:
    # 条件1：PIR检测不到人体
    if not pir_detected:
        logger.bind(tag=TAG).info(f"对话结束（PIR无人体）: session_id={session_id}")
        return True
```

**作用：** 访客离开时自动结束对话

#### 条件2：访客沉默超过30秒

```python
    # 条件2：访客沉默超过30秒
    silence_duration = (datetime.now() - session.last_activity).total_seconds()
    if silence_duration > self.dialogue_timeout:
        logger.bind(tag=TAG).info(
            f"对话结束（沉默超时）: session_id={session_id}, "
            f"silence_duration={silence_duration:.1f}s"
        )
        return True
```

**作用：** 访客不说话时自动结束对话

### 对话循环中的检查

```python
while dialogue_count < max_rounds:
    # 检查对话是否应该结束
    should_end = await self.session_manager.check_dialogue_end(
        session_id=session_id,
        pir_detected=await self._check_pir_status(device_id)  # ← 这里需要PIR状态
    )

    if should_end:
        logger.bind(tag=TAG).info(f"对话结束 - 会话: {session_id}")
        break

    # 等待访客回复
    visitor_response = await self._wait_for_visitor_response(device_id)

    # ... 处理对话 ...
```

## PIR持续时间的作用

### 当前实现的问题

#### 问题1：\_check_pir_status() 方法未实现

```python
async def _check_pir_status(self, device_id: str) -> bool:
    """检查PIR传感器状态

    Args:
        device_id: 设备ID

    Returns:
        是否检测到人体
    """
    # TODO: 查询设备的PIR状态
    # 这里简化处理，假设一直有人
    return True  # ← 永远返回True，无法判断访客是否离开
```

**影响：** 无法通过PIR状态判断对话结束，只能依赖沉默超时（30秒）

#### 问题2：PIR持续时间信息未被利用

当前代码中：

- ✅ ESP32每秒上报PIR事件（包含持续时间）
- ✅ 服务器接收到PIR消息
- ❌ 但**没有保存PIR状态**到连接对象
- ❌ 对话循环中**无法查询当前PIR状态**

### PIR持续时间的正确用途

#### 用途1：判断访客是否还在门口

```
PIR持续上报 → 访客还在门口 → 对话继续
PIR停止上报 → 访客已离开 → 对话结束
```

#### 用途2：优化对话结束判定

**当前逻辑（有缺陷）：**

```
访客离开 → 等待30秒沉默超时 → 对话结束
```

- ❌ 延迟30秒才结束
- ❌ 浪费资源（继续等待ASR识别）

**理想逻辑（使用PIR）：**

```
访客离开 → PIR无人体 → 立即结束对话
```

- ✅ 立即结束，无延迟
- ✅ 节省资源

## 修改建议

### 建议1：在ConnectionHandler中保存PIR状态

```python
class ConnectionHandler:
    def __init__(self, ...):
        # PIR状态
        self.pir_detected = False  # 当前是否检测到人体
        self.last_pir_update_time = 0  # 最后一次PIR更新时间
```

### 建议2：在EventReportHandler中更新PIR状态

```python
async def _handle_pir_event(self, conn, ts: int, param):
    """处理 PIR 人体检测事件"""
    duration = param

    # ✅ 更新PIR状态
    conn.pir_detected = True
    conn.last_pir_update_time = ts

    conn.logger.bind(tag=TAG).info(f"PIR 检测到人体，持续 {duration} 秒")

    # 检查是否正在处理访客
    if conn.visitor_processing:
        conn.logger.bind(tag=TAG).debug("访客处理中，忽略重复的PIR事件")
        return

    # 触发人脸识别流程
    await self._trigger_face_recognition(...)
```

### 建议3：添加PIR超时检测

```python
async def _check_pir_status(self, device_id: str) -> bool:
    """检查PIR传感器状态

    Args:
        device_id: 设备ID

    Returns:
        是否检测到人体
    """
    # 获取连接对象
    manager = ConnectionManager.get_instance()
    conn = manager.get_esp32_conn(device_id)

    if not conn:
        return False

    # 检查PIR状态
    if not conn.pir_detected:
        return False

    # 检查PIR是否超时（超过2秒未更新认为无人体）
    import time
    current_time = time.time() * 1000
    time_since_last_update = current_time - conn.last_pir_update_time

    if time_since_last_update > 2000:  # 2秒超时
        logger.bind(tag=TAG).info(
            f"PIR超时未更新，认为无人体 - 设备: {device_id}, "
            f"超时时长: {time_since_last_update}ms"
        )
        conn.pir_detected = False
        return False

    return True
```

### 建议4：在对话循环中使用PIR状态

```python
while dialogue_count < max_rounds:
    # ✅ 检查对话是否应该结束（使用实时PIR状态）
    pir_detected = await self._check_pir_status(device_id)
    should_end = await self.session_manager.check_dialogue_end(
        session_id=session_id,
        pir_detected=pir_detected
    )

    if should_end:
        if not pir_detected:
            logger.bind(tag=TAG).info(
                f"对话结束（访客已离开）- 会话: {session_id}"
            )
        else:
            logger.bind(tag=TAG).info(
                f"对话结束（沉默超时）- 会话: {session_id}"
            )
        break

    # ... 继续对话 ...
```

## 完整流程示例

### 场景：陌生人送快递（使用PIR状态）

```
第1秒：PIR触发
  ├─ conn.pir_detected = True
  ├─ conn.last_pir_update_time = 1000
  └─ 触发访客处理流程
      ├─ visitor_processing = True
      ├─ 拍照 + 识别（陌生人）
      └─ 启动意图识别对话

第2秒：PIR上报（持续2秒）
  ├─ conn.pir_detected = True
  ├─ conn.last_pir_update_time = 2000
  └─ visitor_processing = True，忽略

第3秒：PIR上报（持续3秒）
  ├─ conn.pir_detected = True
  ├─ conn.last_pir_update_time = 3000
  └─ visitor_processing = True，忽略

对话进行中：
  AI: "您好，请问您找谁？"
  访客: "我是快递员"
  AI: "好的，请把快递放在门口"
  访客: "好的"

第15秒：访客离开
  └─ PIR停止上报

第17秒：对话循环检查
  ├─ _check_pir_status() 检测到PIR超时（17000 - 3000 > 2000）
  ├─ conn.pir_detected = False
  ├─ check_dialogue_end() 返回 True（PIR无人体）
  └─ 对话立即结束（无需等待30秒）

对话结束处理：
  ├─ 生成意图总结
  ├─ 保存访问记录
  ├─ 发送App通知
  └─ visitor_processing = False
```

**优势：**

- ✅ 访客离开后2秒内结束对话（而不是30秒）
- ✅ 节省资源（不再等待ASR识别）
- ✅ 用户体验更好（App更快收到通知）

## 总结

### 对话部分的作用

1. **识别访客意图**：通过多轮对话了解来访目的
2. **记录留言信息**：提取重要信息发送给主人
3. **生成结构化总结**：便于App展示和后续查询

### PIR持续时间的作用

1. **判断访客是否还在门口**：实时更新PIR状态
2. **优化对话结束判定**：访客离开立即结束，无需等待30秒
3. **节省系统资源**：避免无效的ASR识别等待

### 当前问题

- ❌ PIR状态未保存到连接对象
- ❌ `_check_pir_status()` 方法未实现
- ❌ 对话只能依赖沉默超时（30秒）结束
- ❌ 访客离开后仍需等待30秒才结束对话

### 修改建议优先级

**高优先级（必须修改）：**

1. 在 `ConnectionHandler` 中添加 `pir_detected` 和 `last_pir_update_time` 属性
2. 在 `EventReportHandler._handle_pir_event()` 中更新PIR状态
3. 实现 `_check_pir_status()` 方法（包含超时检测）

**中优先级（建议修改）：** 4. 在对话循环中使用实时PIR状态 5. 添加日志记录对话结束原因（PIR无人体 vs 沉默超时）

**低优先级（可选优化）：** 6. 根据PIR状态调整对话策略（如访客即将离开时加快对话节奏）7. 统计PIR状态变化，分析访客行为模式
