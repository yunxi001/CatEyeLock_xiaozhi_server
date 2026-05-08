# 定时拍照任务实现总结

## 实现日期

2026-02-16

## 概述

实现了统一看护对话模式中的定时拍照任务功能，支持在对话过程中每5秒自动拍照并缓存，用于实时监控访客行为。

## 实现内容

### 1. 核心方法实现

#### 1.1 start_photo_capture_task方法

**位置**: `core/handle/doorlock_intent_handler.py`

**功能**:

- 创建异步定时拍照任务
- 每5秒调用ESP32拍照接口
- 将照片添加到PhotoCacheManager
- 记录任务ID用于后续停止

**关键特性**:

- 使用`asyncio.create_task`创建后台任务
- 拍照失败不中断任务，继续运行
- 支持自定义拍照间隔（默认5秒）
- 详细的日志记录

#### 1.2 stop_photo_capture_task方法

**位置**: `core/handle/doorlock_intent_handler.py`

**功能**:

- 取消定时拍照任务
- 清理任务引用
- 优雅处理任务取消

**关键特性**:

- 检查任务是否存在
- 使用`task.cancel()`取消任务
- 等待任务完成取消
- 确保清理任务引用

#### 1.3 start_unified_dialogue方法

**位置**: `core/handle/doorlock_intent_handler.py`

**功能**:

- 启动统一模式对话
- 集成定时拍照任务
- 对话结束后清理资源

**关键特性**:

- 看护模式激活时启动定时拍照
- 对话结束后停止定时拍照
- 异常情况下确保资源清理
- 清理照片缓存

### 2. 集成PhotoCacheManager

在`DoorlockIntentHandler`初始化时添加：

```python
# 照片缓存管理器
self.photo_cache = PhotoCacheManager()

# 定时拍照任务字典：{session_id: asyncio.Task}
self._photo_capture_tasks: Dict[str, asyncio.Task] = {}
```

### 3. 测试覆盖

创建了完整的测试文件：`test_photo_capture_task.py`

**测试用例**:

1. ✅ 启动定时拍照任务
2. ✅ 停止定时拍照任务
3. ✅ 停止不存在的任务
4. ✅ 定时拍照任务异常处理
5. ✅ 统一模式对话（看护模式激活）
6. ✅ 统一模式对话（看护模式未激活）
7. ✅ 统一模式对话异常清理

**测试结果**: 所有7个测试用例全部通过 ✅

## 技术细节

### 异步任务管理

```python
async def photo_capture_loop():
    """定时拍照循环"""
    capture_count = 0

    try:
        while True:
            try:
                # 拍照
                jpeg_data = await self._capture_visitor_photo(...)

                if jpeg_data:
                    # 添加到缓存
                    self.photo_cache.add_photo(...)
                    capture_count += 1

            except Exception as e:
                # 记录错误但继续运行
                logger.error(...)

            # 等待下一次拍照
            await asyncio.sleep(interval_seconds)

    except asyncio.CancelledError:
        # 任务被取消
        logger.info(...)
        raise

# 创建并启动任务
task = asyncio.create_task(photo_capture_loop())
self._photo_capture_tasks[session_id] = task
```

### 资源清理策略

1. **正常结束**: 对话结束后调用`stop_photo_capture_task`
2. **异常情况**: try-finally确保调用`stop_photo_capture_task`
3. **照片缓存**: 对话结束后调用`photo_cache.clear_cache`

### 错误处理

- 拍照失败不中断任务
- 任务取消优雅处理
- 异常情况确保资源清理
- 详细的错误日志

## 工作流程

### 看护模式激活时

```
访客到访
  ↓
启动统一模式对话
  ↓
检测到看护模式激活（baseline_image不为None）
  ↓
启动定时拍照任务（每5秒拍照）
  ├─ 拍照 → 添加到缓存
  ├─ 拍照 → 添加到缓存
  └─ 拍照 → 添加到缓存
  ↓
对话进行中（使用最新缓存照片）
  ↓
对话结束
  ↓
停止定时拍照任务
  ↓
清理照片缓存
```

### 看护模式未激活时

```
访客到访
  ↓
启动统一模式对话
  ↓
检测到看护模式未激活（baseline_image为None）
  ↓
不启动定时拍照任务
  ↓
对话进行中
  ↓
对话结束
```

## 性能优化

### 1. 异步非阻塞

- 定时拍照在后台运行
- 不阻塞对话流程
- 使用asyncio实现并发

### 2. 缓存管理

- 最多保留10张照片
- 自动清理旧照片
- 对话结束后清理缓存

### 3. 错误恢复

- 单次拍照失败不影响后续
- 任务继续运行
- 详细的错误日志

## 配置参数

| 参数             | 默认值 | 说明             |
| ---------------- | ------ | ---------------- |
| interval_seconds | 5      | 拍照间隔（秒）   |
| max_cache_size   | 10     | 最大缓存照片数量 |

## 依赖关系

- `PhotoCacheManager`: 照片缓存管理
- `ESP32CameraService`: ESP32拍照服务
- `asyncio`: 异步任务管理

## 后续任务

定时拍照任务已完成，后续需要实现：

- Task 5: 意图处理器核心流程（使用缓存照片）
- Task 6: 配置文件和提示词
- Task 7: 工具函数调整

## 验证方法

运行测试：

```bash
cd main/xiaozhi-server
python test_photo_capture_task.py
```

预期输出：

```
============================================================
开始测试 定时拍照任务
============================================================
...
✅ 所有测试通过！
============================================================
```

## 注意事项

1. **任务清理**: 必须在对话结束时调用`stop_photo_capture_task`
2. **缓存清理**: 必须在对话结束时调用`photo_cache.clear_cache`
3. **异常处理**: 异常情况下也要确保资源清理
4. **日志记录**: 详细记录拍照次数和缓存状态

## 总结

定时拍照任务实现完成，所有测试通过。该功能为统一看护对话模式提供了实时照片缓存能力，支持在对话过程中持续监控访客行为。实现遵循异步编程规范，具有良好的错误处理和资源管理机制。
