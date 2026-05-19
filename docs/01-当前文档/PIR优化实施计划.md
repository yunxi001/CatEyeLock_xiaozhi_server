# PIR优化实施计划

## 文档信息

- **创建时间**: 2026-05-08
- **版本**: v1.0
- **状态**: 待实施
- **负责人**: 开发团队

## 一、项目背景

### 1.1 当前问题

ESP32设备的PIR传感器在检测到人体时，**每秒上报一次**持续时间参数，直到人体离开才停止上报。当前服务器端代码存在以下问题：

#### 问题1：PIR重复触发

- 同一访客被重复拍照、识别、播放欢迎词
- 每次PIR上报都触发完整流程
- 资源浪费严重（5秒内触发5次）

#### 问题2：访客管理体验差

- **路人路过也会触发**：没有停留时间判断
- **陌生人立即播放问候**：体验不友好
- **识别中途人离开仍继续重试**：浪费资源

#### 问题3：包裹看守资源消耗大

- **无人也在监控**：每5秒无条件拍照分析
- **8小时消耗5,760次检测**：资源浪费巨大
- **没有事件驱动机制**：无法根据人体存在状态调整

### 1.2 ESP32 PIR上报机制

```
检测到人体 → 每秒上报一次（param=持续时间秒数）
人体离开   → 停止上报（无结束事件）

示例：
第1秒: {"type": "event_report", "event": "pir_trigger", "param": 1}
第2秒: {"type": "event_report", "event": "pir_trigger", "param": 2}
第3秒: {"type": "event_report", "event": "pir_trigger", "param": 3}
...
人体离开后：不再上报
```

### 1.3 优化目标

#### 目标1：修复PIR重复触发问题

- ✅ 同一访客只处理一次
- ✅ 避免重复拍照、识别、播放
- ✅ 减少80%的无效处理

#### 目标2：优化访客管理体验

- ✅ **停留3秒后触发**：过滤路人路过
- ✅ **PIR停止上报时中断重试**：人离开立即停止
- ✅ **不延迟问候**：识别成功立即播放欢迎词

#### 目标3：优化包裹看守资源消耗

- ✅ **事件驱动监控**：PIR检测到人开始，PIR停止上报结束
- ✅ **高频监控**：有人时每3秒检测
- ✅ **节省95%资源**：无人时不监控

## 二、技术方案

### 2.1 核心设计思路

#### 2.1.1 PIR状态管理

在 `ConnectionHandler` 中添加PIR状态属性：

```python
# PIR状态管理
self.pir_detected = False        # 是否检测到人体
self.last_pir_time = 0           # 最后一次PIR上报时间（毫秒时间戳）
self.pir_duration = 0            # PIR持续时间（秒）
self.visitor_processing = False  # 是否正在处理访客
```

#### 2.1.2 PIR超时判断

**判断逻辑**：距离上次PIR上报超过2秒 → 认为人体已离开

```python
def _check_pir_status(conn) -> bool:
    """检查PIR是否仍在检测人体"""
    current_time = int(time.time() * 1000)
    time_since_pir = current_time - conn.last_pir_time
    return time_since_pir <= 2000  # 2秒超时阈值
```

#### 2.1.3 三大优化方案关系

```
┌─────────────────────────────────────────────────────────┐
│                    PIR事件上报（每秒）                    │
│                 更新 pir_detected/last_pir_time          │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
┌───────────────┐          ┌────────────────┐
│ 访客管理优化   │          │ 包裹看守优化    │
├───────────────┤          ├────────────────┤
│ • 停留3秒触发  │          │ • 事件驱动监控  │
│ • 避免重复触发 │          │ • 有人高频检测  │
│ • PIR超时中断  │          │ • 无人停止监控  │
└───────────────┘          └────────────────┘
```

### 2.2 方案1：PIR重复触发修复

#### 2.2.1 问题分析

当前代码每次收到PIR事件都会触发 `handle_visitor()`，导致：

- 5秒内触发5次完整流程
- 重复拍照、识别、播放
- 资源浪费严重

#### 2.2.2 解决方案

**核心思路**：添加 `visitor_processing` 标志，处理中忽略后续PIR上报

```python
# 在 eventReportHandler.py 的 _handle_pir_event() 中
async def _handle_pir_event(self, conn, ts: int, param):
    # 更新PIR状态
    conn.pir_detected = True
    conn.last_pir_time = ts
    conn.pir_duration = param

    # ✅ 检查是否正在处理访客
    if hasattr(conn, 'visitor_processing') and conn.visitor_processing:
        conn.logger.bind(tag=TAG).debug("访客处理中，忽略重复PIR")
        return

    # 触发访客处理
    await self._trigger_face_recognition(...)
```

#### 2.2.3 效果

- ✅ 同一访客只处理一次
- ✅ 减少80%的重复处理
- ✅ 资源消耗大幅降低

### 2.3 方案2：访客管理优化

#### 2.3.1 优化点

| 优化项       | 当前问题       | 优化方案                       | 效果       |
| ------------ | -------------- | ------------------------------ | ---------- |
| **停留判断** | 路人路过也触发 | 只在 `param >= 3` 时触发       | 过滤路人   |
| **重复触发** | 每秒触发一次   | 添加 `visitor_processing` 标志 | 只处理一次 |
| **中途离开** | 识别重试继续   | 检查PIR状态，超时停止          | 节省资源   |

#### 2.3.2 完整流程图

```
PIR上报（每秒）
  ↓
更新 pir_detected、last_pir_time、pir_duration
  ↓
检查 visitor_processing？
  ├─ True  → 忽略（避免重复触发）
  └─ False → 继续
       ↓
  检查 param >= 3？
    ├─ False → 忽略（未达到停留阈值）
    └─ True  → 触发访客处理
         ↓
    设置 visitor_processing = True
         ↓
    拍照 → 人脸识别（支持重试）
         ↓
    每次重试前检查PIR状态
      ├─ PIR超时 → 停止重试，返回 pir_interrupted
      └─ PIR正常 → 继续重试
         ↓
    识别成功？
      ├─ 有权限 → 下发face_result + 播放欢迎词
      └─ 无权限 → 下发face_result + 启动意图识别对话
         ↓
    清除 visitor_processing = False
```

#### 2.3.3 场景分析

**场景1：路人路过（停留1秒）**

```
第1秒 PIR上报 param=1 → ❌ 未达到3秒阈值，忽略
人体离开 → PIR停止上报
结果：不触发任何处理
```

**场景2：访客停留（停留5秒）**

```
第1秒 PIR上报 param=1 → ❌ 未达到3秒阈值
第2秒 PIR上报 param=2 → ❌ 未达到3秒阈值
第3秒 PIR上报 param=3 → ✅ 触发访客处理（visitor_processing=True）
第4秒 PIR上报 param=4 → ❌ 检测到处理中，忽略
第5秒 PIR上报 param=5 → ❌ 检测到处理中，忽略
处理完成 → visitor_processing=False
结果：只触发1次处理
```

**场景3：识别中途离开**

```
第3秒 PIR上报 → 触发人脸识别
  ├─ 第1次识别失败 → 播放"请正视摄像头"
  ├─ 等待1秒准备重试
  ├─ 检查PIR状态 → 距离上次上报已超过2秒
  └─ 判断人体已离开 → 停止重试，返回 pir_interrupted
结果：节省2次重试资源
```

#### 2.3.4 关键代码位置

1. **PIR事件处理** (`eventReportHandler.py`)

   ```python
   async def _handle_pir_event(self, conn, ts: int, param):
       # 更新状态
       conn.pir_detected = True
       conn.last_pir_time = ts
       conn.pir_duration = param

       # 检查重复触发
       if conn.visitor_processing:
           return

       # 检查停留阈值
       if param >= 3:
           await self._trigger_face_recognition(...)
   ```

2. **人脸识别重试** (`face_recognition_handler.py`)

   ```python
   async def recognize_with_retry(self, device_id, jpeg_data, conn=None, max_retries=3):
       for attempt in range(1, max_retries + 1):
           # 检查PIR状态
           if conn:
               current_time = int(time.time() * 1000)
               time_since_pir = current_time - conn.last_pir_time
               if time_since_pir > 2000:
                   return {"success": False, "result": "pir_interrupted"}

           # 执行识别
           result = self.face_service.recognize(jpeg_data)
           if result.result == 'known':
               return {"success": True, ...}

           # 等待重试
           await asyncio.sleep(self.retry_interval)
   ```

3. **意图识别处理** (`doorlock_intent_handler.py`)
   ```python
   async def handle_visitor(self, device_id, conn=None, ...):
       try:
           # 设置处理标志
           if conn:
               conn.visitor_processing = True

           # 处理访客...

       finally:
           # 清除标志
           if conn:
               conn.visitor_processing = False
   ```

### 2.4 方案3：包裹看守优化

#### 2.4.1 优化点

| 优化项       | 当前问题   | 优化方案          | 效果        |
| ------------ | ---------- | ----------------- | ----------- |
| **监控触发** | 无人也监控 | PIR检测到人才开始 | 节省资源    |
| **监控频率** | 固定5秒    | 有人3秒，无人停止 | 提高效率    |
| **监控结束** | 无结束机制 | PIR超时自动停止   | 节省95%资源 |

#### 2.4.2 完整流程图

```
包裹看守启用
  ↓
┌─────────────────────────────────┐
│  等待PIR检测到人体                │
│  while True:                    │
│    if pir_detected && 未超时:   │
│      break                      │
│    sleep(1)                     │
└─────────────────────────────────┘
  ↓
检测到人体 → 开始高频监控
  ↓
┌─────────────────────────────────┐
│  高频监控循环（每3秒）            │
│  while True:                    │
│    ├─ 检查PIR状态                │
│    │   ├─ 超时 → 退出循环        │
│    │   └─ 正常 → 继续            │
│    ├─ 拍照                      │
│    ├─ VLLM分析威胁等级           │
│    ├─ 根据威胁等级响应           │
│    │   ├─ low: 无操作            │
│    │   ├─ medium: 语音提示+通知  │
│    │   └─ high: 语音警告+通知    │
│    └─ 等待3秒                   │
└─────────────────────────────────┘
  ↓
PIR超时，人体已离开
  ↓
返回等待状态
```

#### 2.4.3 场景分析

**场景1：无人时（8小时）**

```
当前方案：
  每5秒监控一次 × 8小时 = 5,760次检测
  资源消耗：100%

优化方案：
  等待PIR检测 → 不进行任何监控
  资源消耗：0%

节省：100%资源
```

**场景2：有人时（持续5分钟）**

```
当前方案：
  每5秒监控一次 × 5分钟 = 60次检测

优化方案：
  PIR检测到人 → 每3秒监控一次 × 5分钟 = 100次检测

说明：有人时检测频率提高，监控更及时
```

**场景3：人离开后**

```
当前方案：
  继续每5秒监控 → 无法自动停止

优化方案：
  PIR超时（2秒无上报）→ 立即停止监控 → 返回等待状态

节省：避免无人时的无效监控
```

#### 2.4.4 资源消耗对比

**8小时看守周期，访客到访3次，每次停留5分钟**

| 方案         | 无人监控 | 有人监控 | 总计      | 资源消耗  |
| ------------ | -------- | -------- | --------- | --------- |
| **当前方案** | 5,580次  | 180次    | 5,760次   | 100%      |
| **优化方案** | 0次      | 300次    | 300次     | 5.2%      |
| **节省**     | 100%     | -66%     | **94.8%** | **94.8%** |

说明：虽然有人时检测频率提高（3秒 vs 5秒），但由于无人时完全不监控，总体资源节省94.8%

#### 2.4.5 关键代码位置

1. **监控启动** (`package_guard_manager.py`)

   ```python
   async def start_monitoring(self, device_id, session_id, conn):
       """启动事件驱动的监控循环"""
       while True:
           # 等待PIR检测到人体
           await self._wait_for_pir_detection(conn)

           # 开始高频监控
           await self._high_frequency_monitoring(device_id, session_id, conn)
   ```

2. **等待PIR检测**

   ```python
   async def _wait_for_pir_detection(self, conn):
       """等待PIR检测到人体"""
       while True:
           if hasattr(conn, 'pir_detected') and conn.pir_detected:
               if self._check_pir_status(conn):
                   logger.info("PIR检测到人体，开始监控")
                   return
           await asyncio.sleep(1)
   ```

3. **高频监控**

   ```python
   async def _high_frequency_monitoring(self, device_id, session_id, conn):
       """高频监控（每3秒）"""
       while True:
           # 检查PIR状态
           if not self._check_pir_status(conn):
               logger.info("PIR超时，人体已离开，停止监控")
               return

           # 拍照并分析
           await self._capture_and_analyze(device_id, session_id)

           # 等待3秒
           await asyncio.sleep(3)
   ```

4. **PIR状态检查**
   ```python
   def _check_pir_status(self, conn) -> bool:
       """检查PIR状态"""
       if not hasattr(conn, 'last_pir_time'):
           return False

       current_time = int(time.time() * 1000)
       time_since_pir = current_time - conn.last_pir_time

       return time_since_pir <= 2000  # 2秒超时阈值
   ```

### 2.4 配置参数

```yaml
doorlock:
  visitor_management:
    pir_stay_threshold: 3 # PIR停留阈值（秒）
    pir_timeout: 2 # PIR超时判断（秒）
    face_recognition_max_retries: 3
    face_recognition_retry_interval: 1

  package_guard:
    monitoring_interval: 3 # 监控间隔（秒）
    pir_timeout: 2 # PIR超时判断（秒）
```

## 三、实施计划

### 3.1 任务分解

#### 阶段1：基础设施准备（预计1小时）

**TASK-1.1**: 修改 `ConnectionHandler` 类

- [ ] 在 `__init__` 方法中添加PIR状态属性
- [ ] 添加代码注释说明各属性用途
- [ ] 文件：`main/xiaozhi-server/core/connection.py`

**TASK-1.2**: 创建PIR状态检查工具函数

- [ ] 在 `core/utils/` 下创建 `pir_utils.py`
- [ ] 实现 `check_pir_status(conn, timeout_ms=2000)` 函数
- [ ] 添加单元测试

#### 阶段2：访客管理优化（预计2小时）

**TASK-2.1**: 修改PIR事件处理器

- [ ] 修改 `_handle_pir_event()` 方法
  - [ ] 每次上报更新 `pir_detected`、`last_pir_time`、`pir_duration`
  - [ ] 添加 `visitor_processing` 检查
  - [ ] 添加 `param >= 3` 停留阈值检查
- [ ] 添加详细日志输出
- [ ] 文件：`main/xiaozhi-server/core/handle/textHandler/eventReportHandler.py`

**TASK-2.2**: 修改人脸识别处理器

- [ ] 修改 `recognize_with_retry()` 方法签名，添加 `conn` 参数
- [ ] 在每次重试前添加PIR状态检查
- [ ] PIR超时时返回 `pir_interrupted` 结果
- [ ] 更新所有调用点传入 `conn` 参数
- [ ] 文件：`main/xiaozhi-server/core/providers/doorlock/face_recognition_handler.py`

**TASK-2.3**: 修改意图识别处理器

- [ ] 在 `handle_visitor()` 开始时设置 `visitor_processing = True`
- [ ] 在 `handle_visitor()` 的 `finally` 块清除标志
- [ ] 添加 `_check_pir_status()` 方法
- [ ] 处理 `pir_interrupted` 识别结果
- [ ] 文件：`main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

#### 阶段3：包裹看守优化（预计2小时）

**TASK-3.1**: 修改包裹看守管理器

- [ ] 实现 `_wait_for_pir_detection(conn)` 方法
- [ ] 实现 `_high_frequency_monitoring(device_id, session_id, conn)` 方法
- [ ] 实现 `_check_pir_status(conn)` 方法
- [ ] 修改 `start_monitoring()` 使用事件驱动模式
- [ ] 移除原有的无条件5秒循环逻辑
- [ ] 文件：`main/xiaozhi-server/core/providers/doorlock/package_guard_manager.py`

**TASK-3.2**: 更新包裹看守配置

- [ ] 在 `config.yaml` 中添加 `monitoring_interval` 配置
- [ ] 在 `config.yaml` 中添加 `pir_timeout` 配置
- [ ] 更新配置文档

#### 阶段4：测试验证（预计2小时）

**TASK-4.1**: 单元测试

- [ ] 测试PIR状态更新逻辑
- [ ] 测试PIR超时判断逻辑
- [ ] 测试重复触发防护
- [ ] 测试停留阈值判断

**TASK-4.2**: 集成测试

- [ ] 测试访客管理完整流程
  - [ ] 场景1：路人路过（停留<3秒）
  - [ ] 场景2：访客停留（停留>=3秒）
  - [ ] 场景3：识别中途离开（PIR超时）
- [ ] 测试包裹看守完整流程
  - [ ] 场景1：无人时不监控
  - [ ] 场景2：有人时高频监控
  - [ ] 场景3：人离开后停止监控

**TASK-4.3**: 性能测试

- [ ] 对比优化前后的资源消耗
- [ ] 验证80%资源节省目标
- [ ] 记录性能测试报告

#### 阶段5：文档更新（预计1小时）

**TASK-5.1**: 更新技术文档

- [ ] 更新 `PIR重复触发问题分析.md`，标记为已解决
- [ ] 创建 `PIR优化实施总结.md`
- [ ] 更新架构说明文档

**TASK-5.2**: 更新API文档

- [ ] 更新 `face_recognition_handler` API文档
- [ ] 更新 `package_guard_manager` API文档
- [ ] 更新配置文件说明

### 3.2 时间安排

| 阶段     | 任务         | 预计时间  | 依赖         |
| -------- | ------------ | --------- | ------------ |
| 阶段1    | 基础设施准备 | 1小时     | 无           |
| 阶段2    | 访客管理优化 | 2小时     | 阶段1        |
| 阶段3    | 包裹看守优化 | 2小时     | 阶段1        |
| 阶段4    | 测试验证     | 2小时     | 阶段2、阶段3 |
| 阶段5    | 文档更新     | 1小时     | 阶段4        |
| **总计** |              | **8小时** |              |

### 3.3 里程碑

- **M1**: 基础设施完成（1小时后）
- **M2**: 访客管理优化完成（3小时后）
- **M3**: 包裹看守优化完成（5小时后）
- **M4**: 测试验证通过（7小时后）
- **M5**: 文档更新完成（8小时后）

## 四、详细TODO清单

### ✅ TODO List

#### 📋 阶段1：基础设施准备

- [ ] **TASK-1.1**: 修改 `core/connection.py`

  ```python
  # 在 ConnectionHandler.__init__ 中添加：
  # PIR状态管理
  self.pir_detected = False        # 是否检测到人体
  self.last_pir_time = 0           # 最后一次PIR上报时间（毫秒时间戳）
  self.pir_duration = 0            # PIR持续时间（秒）
  self.visitor_processing = False  # 是否正在处理访客
  ```

- [ ] **TASK-1.2**: 创建 `core/utils/pir_utils.py`

  ```python
  def check_pir_status(conn, timeout_ms: int = 2000) -> bool:
      """检查PIR是否仍在检测人体

      Args:
          conn: 连接对象
          timeout_ms: 超时时间（毫秒），默认2000ms

      Returns:
          True: PIR仍在检测人体
          False: PIR超时，人体已离开
      """
      pass
  ```

#### 📋 阶段2：访客管理优化

- [ ] **TASK-2.1**: 修改 `core/handle/textHandler/eventReportHandler.py`
  - [ ] 在 `_handle_pir_event()` 开头添加状态更新：
    ```python
    # 每次PIR上报都更新状态
    conn.pir_detected = True
    conn.last_pir_time = ts
    conn.pir_duration = param
    ```
  - [ ] 添加重复触发检查：
    ```python
    # 检查是否正在处理访客
    if hasattr(conn, 'visitor_processing') and conn.visitor_processing:
        conn.logger.bind(tag=TAG).debug(...)
        return
    ```
  - [ ] 添加停留阈值检查：
    ```python
    # 只在停留3秒后触发
    if param >= 3:
        await self._trigger_face_recognition(...)
    ```

- [ ] **TASK-2.2**: 修改 `core/providers/doorlock/face_recognition_handler.py`
  - [ ] 修改方法签名：
    ```python
    async def recognize_with_retry(
        self,
        device_id: str,
        jpeg_data: bytes,
        conn=None,  # 新增参数
        max_retries: Optional[int] = None
    ) -> Dict[str, Any]:
    ```
  - [ ] 在重试循环中添加PIR检查：

    ```python
    for attempt in range(1, max_retries + 1):
        # 检查PIR状态
        if conn and hasattr(conn, 'last_pir_time'):
            current_time = int(time.time() * 1000)
            time_since_pir = current_time - conn.last_pir_time
            if time_since_pir > 2000:
                return {"success": False, "result": "pir_interrupted", ...}

        # 执行识别...
    ```

  - [ ] 更新所有调用点传入 `conn` 参数

- [ ] **TASK-2.3**: 修改 `core/handle/doorlock_intent_handler.py`
  - [ ] 在 `handle_visitor()` 开始设置标志：
    ```python
    if conn:
        conn.visitor_processing = True
    ```
  - [ ] 在 `finally` 块清除标志：
    ```python
    finally:
        if conn:
            conn.visitor_processing = False
    ```
  - [ ] 添加PIR状态检查方法：
    ```python
    def _check_pir_status(self, conn) -> bool:
        """检查PIR状态"""
        pass
    ```
  - [ ] 处理 `pir_interrupted` 结果

#### 📋 阶段3：包裹看守优化

- [ ] **TASK-3.1**: 修改 `core/providers/doorlock/package_guard_manager.py`
  - [ ] 实现 `_wait_for_pir_detection()`:
    ```python
    async def _wait_for_pir_detection(self, conn):
        """等待PIR检测到人体"""
        while True:
            if hasattr(conn, 'pir_detected') and conn.pir_detected:
                if self._check_pir_status(conn):
                    return
            await asyncio.sleep(1)
    ```
  - [ ] 实现 `_high_frequency_monitoring()`:
    ```python
    async def _high_frequency_monitoring(self, device_id, session_id, conn):
        """高频监控（每3秒）"""
        while True:
            if not self._check_pir_status(conn):
                return
            await self._capture_and_analyze(device_id, session_id)
            await asyncio.sleep(3)
    ```
  - [ ] 实现 `_check_pir_status()`:
    ```python
    def _check_pir_status(self, conn) -> bool:
        """检查PIR状态"""
        if not hasattr(conn, 'last_pir_time'):
            return False
        current_time = int(time.time() * 1000)
        time_since_pir = current_time - conn.last_pir_time
        return time_since_pir <= 2000
    ```
  - [ ] 修改 `start_monitoring()` 使用事件驱动

- [ ] **TASK-3.2**: 更新配置文件
  - [ ] 在 `config.yaml` 添加配置项
  - [ ] 更新配置加载逻辑

#### 📋 阶段4：测试验证

- [ ] **TASK-4.1**: 单元测试
  - [ ] 测试 `check_pir_status()` 函数
  - [ ] 测试PIR状态更新逻辑
  - [ ] 测试重复触发防护
  - [ ] 测试停留阈值判断

- [ ] **TASK-4.2**: 集成测试 - 访客管理
  - [ ] 场景1：路人路过（停留1秒）
    - [ ] 验证：不触发人脸识别
    - [ ] 验证：PIR状态正常更新
  - [ ] 场景2：访客停留（停留5秒）
    - [ ] 验证：第3秒触发人脸识别
    - [ ] 验证：后续PIR上报被忽略
  - [ ] 场景3：识别中途离开
    - [ ] 验证：PIR超时停止重试
    - [ ] 验证：返回 `pir_interrupted`

- [ ] **TASK-4.3**: 集成测试 - 包裹看守
  - [ ] 场景1：无人时
    - [ ] 验证：不进行监控
    - [ ] 验证：等待PIR检测
  - [ ] 场景2：有人时
    - [ ] 验证：每3秒监控一次
    - [ ] 验证：VLLM分析正常
  - [ ] 场景3：人离开后
    - [ ] 验证：停止监控
    - [ ] 验证：返回等待状态

- [ ] **TASK-4.4**: 性能测试
  - [ ] 记录优化前资源消耗
  - [ ] 记录优化后资源消耗
  - [ ] 计算资源节省比例
  - [ ] 生成性能测试报告

#### 📋 阶段5：文档更新

- [ ] **TASK-5.1**: 更新技术文档
  - [ ] 更新 `PIR重复触发问题分析.md`
  - [ ] 创建 `PIR优化实施总结.md`
  - [ ] 更新 `xiaozhi-server-detailed-analysis.md`

- [ ] **TASK-5.2**: 更新API文档
  - [ ] 更新 `face_recognition_handler` 文档
  - [ ] 更新 `package_guard_manager` 文档
  - [ ] 更新配置文件说明

## 五、风险评估与应对

### 5.1 技术风险

| 风险              | 影响 | 概率 | 应对措施                                   |
| ----------------- | ---- | ---- | ------------------------------------------ |
| PIR超时阈值不准确 | 中   | 中   | 通过实际测试调整阈值，提供配置项           |
| 停留阈值过短/过长 | 低   | 中   | 提供配置项，支持动态调整                   |
| 并发访客处理冲突  | 高   | 低   | 使用设备级别锁，确保同一时间只处理一个访客 |
| PIR状态更新延迟   | 中   | 低   | 使用毫秒级时间戳，确保精度                 |

### 5.2 兼容性风险

| 风险                | 影响 | 概率 | 应对措施               |
| ------------------- | ---- | ---- | ---------------------- |
| 旧版ESP32固件不兼容 | 高   | 低   | 添加版本检查，向下兼容 |
| 现有会话被中断      | 中   | 中   | 添加平滑过渡逻辑       |
| 配置文件格式变更    | 低   | 低   | 提供默认值，向下兼容   |

### 5.3 回滚方案

如果优化后出现严重问题，可以通过以下步骤回滚：

1. **配置回滚**：

   ```yaml
   doorlock:
     visitor_management:
       enable_pir_optimization: false # 关闭优化
   ```

2. **代码回滚**：
   - 恢复 `eventReportHandler.py` 的 `_handle_pir_event()` 方法
   - 恢复 `face_recognition_handler.py` 的 `recognize_with_retry()` 方法
   - 恢复 `package_guard_manager.py` 的监控逻辑

3. **数据库回滚**：
   - 无需数据库变更，无回滚需求

## 六、验收标准

### 6.1 功能验收

- [ ] 访客管理：路人路过不触发（停留<3秒）
- [ ] 访客管理：访客停留触发（停留>=3秒）
- [ ] 访客管理：PIR超时停止重试
- [ ] 访客管理：同一访客只处理一次
- [ ] 包裹看守：无人时不监控
- [ ] 包裹看守：有人时高频监控（每3秒）
- [ ] 包裹看守：人离开后停止监控

### 6.2 性能验收

- [ ] 访客管理资源消耗减少 >= 80%
- [ ] 包裹看守资源消耗减少 >= 95%
- [ ] PIR事件处理延迟 < 100ms
- [ ] 人脸识别响应时间无明显增加

### 6.3 稳定性验收

- [ ] 连续运行24小时无异常
- [ ] 并发10个访客无冲突
- [ ] 异常情况下正确清理状态
- [ ] 日志输出完整清晰

## 七、后续优化建议

### 7.1 短期优化（1-2周）

1. **动态阈值调整**
   - 根据历史数据自动调整停留阈值
   - 根据设备位置调整PIR超时时间

2. **智能路人过滤**
   - 结合移动速度判断是否为路人
   - 使用机器学习模型预测访客意图

### 7.2 长期优化（1-3个月）

1. **多传感器融合**
   - 结合门铃按钮、门磁传感器
   - 提高访客检测准确率

2. **访客行为分析**
   - 记录访客停留时间、移动轨迹
   - 生成访客行为报告

3. **预测性监控**
   - 根据历史数据预测访客到访时间
   - 提前准备资源，降低响应延迟

## 八、附录

### 8.1 相关文档

- [PIR重复触发问题分析](./PIR重复触发问题分析.md)
- [智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2](./智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md)
- [doorlock-intent-handler-api-reference](./doorlock-intent-handler-api-reference.md)

### 8.2 关键代码文件

| 文件路径                                              | 说明           | 修改内容               |
| ----------------------------------------------------- | -------------- | ---------------------- |
| `core/connection.py`                                  | 连接处理器     | 添加PIR状态属性        |
| `core/handle/textHandler/eventReportHandler.py`       | PIR事件处理器  | 添加状态更新和检查逻辑 |
| `core/providers/doorlock/face_recognition_handler.py` | 人脸识别处理器 | 添加PIR状态检查        |
| `core/handle/doorlock_intent_handler.py`              | 意图识别处理器 | 添加状态管理           |
| `core/providers/doorlock/package_guard_manager.py`    | 包裹看守管理器 | 实现事件驱动监控       |

### 8.3 配置示例

```yaml
doorlock:
  visitor_management:
    # PIR停留阈值（秒）
    pir_stay_threshold: 3
    # PIR超时判断（秒）
    pir_timeout: 2
    # 人脸识别最大重试次数
    face_recognition_max_retries: 3
    # 人脸识别重试间隔（秒）
    face_recognition_retry_interval: 1

  package_guard:
    # 监控间隔（秒）
    monitoring_interval: 3
    # PIR超时判断（秒）
    pir_timeout: 2
```

### 8.4 测试用例模板

```python
# 测试用例：访客停留3秒触发
async def test_visitor_stay_3_seconds():
    """测试访客停留3秒后触发人脸识别"""
    # 模拟PIR上报
    await send_pir_event(param=1)  # 第1秒
    await asyncio.sleep(1)
    await send_pir_event(param=2)  # 第2秒
    await asyncio.sleep(1)
    await send_pir_event(param=3)  # 第3秒 - 应该触发

    # 验证
    assert conn.visitor_processing == True
    assert face_recognition_called == True
```

---

**文档版本**: v1.0  
**最后更新**: 2026-05-08  
**审核状态**: 待审核
