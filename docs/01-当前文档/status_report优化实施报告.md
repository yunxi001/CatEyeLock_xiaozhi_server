# status_report 状态上报优化实施报告

## 问题背景

### 原始问题

App 端在远程开锁后，UI 上的锁状态不更新，电量信息也不更新。

### 根本原因

1. **ESP32 定期发送 `status_report`**，但服务器**无条件转发**所有消息给 App
2. **服务器在开锁成功后不会主动上报状态变化**
3. App 端只认 `status_report` 消息格式，不认 `device_state_update`

## 解决方案

### 方案概述

实现**状态变化检测**和**主动构造 status_report**机制：

1. **ESP32 定期发送 `status_report`** → 服务器检测状态变化 → **仅在变化时转发**给 App
2. **服务器推断出状态变化**（如开锁成功）→ **构造 `status_report`** → 发送给 App

### 实施细节

#### 1. statusReportHandler.py 修改

**新增功能：状态变化检测**

```python
def _check_state_changed(self, conn, battery: int, lux: int,
                         lock_state: int, light_state: int) -> bool:
    """检查状态是否发生变化

    比较新旧状态：
    - battery: 电量百分比
    - lux: 光照值
    - lock_state: 锁状态 (0=关闭, 1=打开)
    - light_state: 灯状态 (0=灭, 1=亮)

    Returns:
        bool: 任一字段变化返回 True
    """
```

**修改逻辑：**

- 收到 ESP32 的 `status_report` 后
- 与内存缓存 `conn.iot_descriptors["smart_doorlock"]` 比较
- **仅在状态变化时转发**给 App
- 更新内存缓存

**优化效果：**

- 减少无效消息推送
- App 端只收到真正的状态变化通知

#### 2. logReportHandler.py 修改

**新增功能：主动构造 status_report**

```python
async def _update_lock_state_from_log(self, conn, status: str):
    """根据开锁日志更新锁状态并推送给 App

    当 status=success 时：
    1. 从缓存获取其他状态（bat, lux, light）
    2. 构造 status_report 消息（lock=1）
    3. 更新内存缓存
    4. 发送给所有关联的 App
    """
```

**触发条件：**

- 收到 `log_report` 且 `status=success`（开锁成功）

**构造的消息格式：**

```json
{
  "type": "status_report",
  "ts": 1702234567890,
  "data": {
    "bat": 85, // 从缓存获取
    "lux": 300, // 从缓存获取
    "lock": 1, // 强制设为 1 (open)
    "light": 1 // 从缓存获取
  }
}
```

**优化效果：**

- 开锁成功后立即通知 App
- 无需等待 ESP32 下一次定期上报

## 数据流对比

### 优化前

```
ESP32 定期上报 status_report (每 5 秒)
  ↓
服务器无条件转发
  ↓
App 收到大量重复消息

开锁成功
  ↓
服务器发送 device_state_update (App 不认识)
  ↓
App 状态不更新 ❌

开灯成功
  ↓
服务器不发送任何状态更新
  ↓
App 状态不更新 ❌
```

### 优化后

```
ESP32 定期上报 status_report (每 5 秒)
  ↓
服务器检测状态变化
  ↓
仅在变化时转发
  ↓
App 收到有效状态更新 ✅

开锁成功
  ↓
服务器构造 status_report (lock=1)
  ↓
立即发送给 App
  ↓
App 状态立即更新 ✅

开灯成功
  ↓
服务器构造 status_report (light=1)
  ↓
立即发送给 App
  ↓
App 状态立即更新 ✅
```

## 状态缓存结构

### 内存缓存位置

```python
conn.iot_descriptors["smart_doorlock"] = {
    "battery": 85,           # 电量百分比
    "lux": 300,              # 光照值
    "lock_state": 1,         # 锁状态: 0=关闭, 1=打开
    "light_state": 1,        # 灯状态: 0=灭, 1=亮
    "last_update": 1702234567890  # 最后更新时间戳
}
```

### 缓存更新时机

1. 收到 ESP32 的 `status_report` 时
2. 服务器推断出状态变化时（如开锁成功）

## 测试验证

### 测试场景 1：远程开锁

**预期行为：**

1. App 发送 `lock_control` (command=unlock)
2. 服务器转发给 ESP32
3. ESP32 执行开锁，返回 `log_report` (status=success)
4. 服务器构造 `status_report` (lock=1)
5. App 收到 `status_report`，UI 更新为"已开锁" ✅

### 测试场景 2：电量变化

**预期行为：**

1. ESP32 定期上报 `status_report` (bat=85)
2. 服务器检测到电量从 90% 降到 85%
3. 转发 `status_report` 给 App
4. App 收到消息，UI 更新电量显示 ✅

### 测试场景 3：灯控制

**预期行为：**

1. App 发送 `dev_control` (target=light, action=on)
2. 服务器转发给 ESP32，缓存命令信息
3. ESP32 执行开灯，返回 `ack` (code=0)
4. 服务器构造 `status_report` (light=1)
5. App 收到 `status_report`，UI 更新为"灯已开启" ✅

### 测试场景 4：状态无变化

**预期行为：**

1. ESP32 定期上报 `status_report` (所有字段不变)
2. 服务器检测到状态无变化
3. **不转发**给 App
4. 减少无效消息 ✅

## 注意事项

### 1. 缓存初始化

- 第一次收到 `status_report` 时，缓存为空
- 此时认为状态变化，会转发给 App

### 2. 缓存数据完整性

- 构造 `status_report` 时，从缓存获取其他字段
- 如果缓存中某字段为 `None`，会原样传递给 App
- ESP32 应确保定期上报完整数据

### 3. 并发安全

- `conn.iot_descriptors` 是连接级别的内存缓存
- 每个 ESP32 连接独立维护
- 无需考虑跨连接的并发问题

### 4. 状态不一致风险

- 如果 ESP32 开锁后未上报 `log_report`
- 服务器无法感知状态变化
- 需依赖 ESP32 下一次定期上报

## 后续优化建议

### 1. ESP32 固件优化（推荐）

在 ESP32 执行完开锁/关锁操作后，**立即主动上报一次 `status_report`**，而不是等待定期上报。

**优点：**

- 服务器无需推断状态
- 数据来源唯一，避免不一致
- 服务器逻辑更简单

### 2. 增加关锁状态上报

目前只处理了开锁成功（lock=1），未处理关锁事件。

**建议：**

- 监听 `event_report` 中的 `lock_success` 事件
- 构造 `status_report` (lock=0)

### 3. 灯状态变化上报

App 控制灯开关后，服务器也应构造 `status_report` 通知状态变化。

**实现位置：**

- `commandProxyHandler.py` 中的 `DevControlProxyHandler`
- `ackHandler.py` 中的 `AckHandler`

**实现逻辑：**

1. App 发送 `dev_control` (target=light, action=on/off)
2. `DevControlProxyHandler` 缓存控制命令到 `esp32_conn.last_light_control`
3. ESP32 执行成功，返回 `ack` (code=0)
4. `AckHandler` 检测到灯控制命令成功
5. 构造 `status_report` (light=新状态)
6. 发送给所有关联的 App

**已实现 ✅**

## 修改文件清单

| 文件                     | 修改内容                       | 行数变化 |
| ------------------------ | ------------------------------ | -------- |
| `statusReportHandler.py` | 新增状态变化检测逻辑           | +30 行   |
| `logReportHandler.py`    | 开锁成功后构造 status_report   | +40 行   |
| `ackHandler.py`          | 灯控制成功后构造 status_report | +70 行   |
| `commandProxyHandler.py` | 缓存灯控制命令信息             | +15 行   |

## 版本信息

- **修改日期**: 2026-05-08
- **协议版本**: v5.2
- **服务器版本**: 0.8.8

## 相关文档

- [ESP32 数据处理流程](./esp32-data-processing-flow.md)
- [App 协议 v2.5 更新清单](./app-protocol-v2.5-update-checklist-final.md)
