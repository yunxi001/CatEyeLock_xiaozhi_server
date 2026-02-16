"""
定时拍照任务测试

测试DoorlockIntentHandler的定时拍照功能：
- start_photo_capture_task方法
- stop_photo_capture_task方法
- start_unified_dialogue方法中的定时拍照集成
"""
import sys
import os
import asyncio
from unittest.mock import Mock, AsyncMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.handle.doorlock_intent_handler import DoorlockIntentHandler
from core.providers.doorlock.photo_cache_manager import PhotoCacheManager


def create_mock_components():
    """创建模拟组件"""
    face_handler = Mock()
    greeting_handler = Mock()
    session_manager = Mock()
    notification_service = Mock()
    doorlock_database = Mock()
    vllm_provider = Mock()
    
    config = {
        'dialogue_timeout': 30,
        'max_dialogue_rounds': 10,
        'max_token_usage_ratio': 0.8,
        'intent_recognition_prompt': 'test prompt'
    }
    
    return {
        'face_handler': face_handler,
        'greeting_handler': greeting_handler,
        'session_manager': session_manager,
        'notification_service': notification_service,
        'doorlock_database': doorlock_database,
        'vllm_provider': vllm_provider,
        'config': config
    }


def create_intent_handler():
    """创建意图处理器实例"""
    components = create_mock_components()
    handler = DoorlockIntentHandler(
        face_recognition_handler=components['face_handler'],
        greeting_handler=components['greeting_handler'],
        session_manager=components['session_manager'],
        notification_service=components['notification_service'],
        doorlock_database=components['doorlock_database'],
        vllm_provider=components['vllm_provider'],
        config=components['config']
    )
    return handler


def create_mock_conn():
    """创建模拟连接对象"""
    conn = Mock()
    conn.device_id = "test_device_001"
    return conn


async def test_start_photo_capture_task():
    """测试启动定时拍照任务"""
    print("\n=== 测试1: 启动定时拍照任务 ===")
    
    handler = create_intent_handler()
    conn = create_mock_conn()
    device_id = "test_device_001"
    session_id = "test_session_001"
    
    # 模拟拍照方法
    mock_photo_data = b"fake_jpeg_data"
    handler._capture_visitor_photo = AsyncMock(return_value=mock_photo_data)
    
    # 启动定时拍照任务
    await handler.start_photo_capture_task(
        device_id=device_id,
        session_id=session_id,
        conn=conn,
        interval_seconds=0.1  # 使用短间隔加快测试
    )
    
    # 验证任务已创建
    assert session_id in handler._photo_capture_tasks, "❌ 任务未创建"
    task = handler._photo_capture_tasks[session_id]
    assert not task.done(), "❌ 任务不应该已完成"
    print("✓ 定时拍照任务已启动")
    
    # 等待几次拍照
    await asyncio.sleep(0.3)
    
    # 验证拍照方法被调用
    call_count = handler._capture_visitor_photo.call_count
    assert call_count >= 2, f"❌ 拍照次数不足：期望>=2，实际{call_count}"
    print(f"✓ 拍照方法被调用{call_count}次")
    
    # 验证照片被添加到缓存
    photo_cache = PhotoCacheManager()
    cache_size = photo_cache.get_cache_size(session_id)
    assert cache_size >= 2, f"❌ 缓存数量不足：期望>=2，实际{cache_size}"
    print(f"✓ 照片已添加到缓存，数量: {cache_size}")
    
    # 停止任务
    await handler.stop_photo_capture_task(session_id)
    print("✓ 定时拍照任务已停止")
    
    # 清理缓存
    photo_cache.clear_cache(session_id)


async def test_stop_photo_capture_task():
    """测试停止定时拍照任务"""
    print("\n=== 测试2: 停止定时拍照任务 ===")
    
    handler = create_intent_handler()
    conn = create_mock_conn()
    device_id = "test_device_002"
    session_id = "test_session_002"
    
    # 模拟拍照方法
    handler._capture_visitor_photo = AsyncMock(return_value=b"fake_jpeg_data")
    
    # 启动任务
    await handler.start_photo_capture_task(
        device_id=device_id,
        session_id=session_id,
        conn=conn,
        interval_seconds=0.1
    )
    
    # 验证任务存在
    assert session_id in handler._photo_capture_tasks, "❌ 任务未创建"
    print("✓ 任务已创建")
    
    # 停止任务
    await handler.stop_photo_capture_task(session_id)
    
    # 验证任务已清理
    assert session_id not in handler._photo_capture_tasks, "❌ 任务未清理"
    print("✓ 任务已停止并清理")
    
    # 清理缓存
    photo_cache = PhotoCacheManager()
    photo_cache.clear_cache(session_id)


async def test_stop_nonexistent_task():
    """测试停止不存在的任务"""
    print("\n=== 测试3: 停止不存在的任务 ===")
    
    handler = create_intent_handler()
    session_id = "nonexistent_session"
    
    # 停止不存在的任务（不应抛出异常）
    try:
        await handler.stop_photo_capture_task(session_id)
        print("✓ 停止不存在的任务不会抛出异常")
    except Exception as e:
        raise AssertionError(f"❌ 不应抛出异常: {e}")
    
    # 验证没有任务
    assert session_id not in handler._photo_capture_tasks, "❌ 不应有任务"


async def test_photo_capture_task_exception_handling():
    """测试定时拍照任务的异常处理"""
    print("\n=== 测试4: 定时拍照任务异常处理 ===")
    
    handler = create_intent_handler()
    conn = create_mock_conn()
    device_id = "test_device_003"
    session_id = "test_session_003"
    
    # 模拟拍照失败
    call_count = [0]
    
    async def mock_capture_with_failure(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # 第一次失败
            raise Exception("拍照失败")
        else:
            # 后续成功
            return b"fake_jpeg_data"
    
    handler._capture_visitor_photo = AsyncMock(side_effect=mock_capture_with_failure)
    
    # 启动任务
    await handler.start_photo_capture_task(
        device_id=device_id,
        session_id=session_id,
        conn=conn,
        interval_seconds=0.1
    )
    
    # 等待几次拍照
    await asyncio.sleep(0.3)
    
    # 验证任务仍在运行（异常不应中断任务）
    assert session_id in handler._photo_capture_tasks, "❌ 任务不应停止"
    task = handler._photo_capture_tasks[session_id]
    assert not task.done(), "❌ 任务不应完成"
    print("✓ 任务在异常后继续运行")
    
    # 验证至少有一次成功的拍照
    photo_cache = PhotoCacheManager()
    cache_size = photo_cache.get_cache_size(session_id)
    assert cache_size >= 1, f"❌ 应有成功的拍照：实际{cache_size}"
    print(f"✓ 有{cache_size}次成功的拍照")
    
    # 停止任务
    await handler.stop_photo_capture_task(session_id)
    
    # 清理缓存
    photo_cache.clear_cache(session_id)


async def test_start_unified_dialogue_with_guard_mode():
    """测试统一模式对话（看护模式激活）"""
    print("\n=== 测试5: 统一模式对话（看护模式激活）===")
    
    handler = create_intent_handler()
    conn = create_mock_conn()
    device_id = "test_device_004"
    session_id = "test_session_004"
    visitor_image = b"visitor_image_data"
    baseline_image = b"baseline_image_data"
    
    # 模拟各种方法
    handler._capture_visitor_photo = AsyncMock(return_value=b"fake_jpeg_data")
    handler._play_initial_greeting = AsyncMock(return_value="您好，请问有什么可以帮您？")
    handler.session_manager.add_dialogue = Mock()
    handler.session_manager.check_dialogue_end = AsyncMock(return_value=True)  # 立即结束对话
    handler._check_pir_status = AsyncMock(return_value=False)
    
    # 调用统一模式对话
    result = await handler.start_unified_dialogue(
        device_id=device_id,
        session_id=session_id,
        person_info=None,
        visitor_image=visitor_image,
        baseline_image=baseline_image,
        conn=conn
    )
    
    # 验证结果
    assert result["success"] is True, "❌ 对话应该成功"
    assert result["action"] == "unified_dialogue_completed", "❌ action错误"
    print("✓ 统一模式对话完成")
    
    # 验证定时拍照任务已停止
    assert session_id not in handler._photo_capture_tasks, "❌ 任务应该已停止"
    print("✓ 定时拍照任务已停止")
    
    # 验证照片缓存已清理
    photo_cache = PhotoCacheManager()
    cache_size = photo_cache.get_cache_size(session_id)
    assert cache_size == 0, f"❌ 缓存应该已清理：实际{cache_size}"
    print("✓ 照片缓存已清理")


async def test_start_unified_dialogue_without_guard_mode():
    """测试统一模式对话（看护模式未激活）"""
    print("\n=== 测试6: 统一模式对话（看护模式未激活）===")
    
    handler = create_intent_handler()
    conn = create_mock_conn()
    device_id = "test_device_005"
    session_id = "test_session_005"
    visitor_image = b"visitor_image_data"
    baseline_image = None  # 看护模式未激活
    
    # 模拟各种方法
    handler._play_initial_greeting = AsyncMock(return_value="您好，请问有什么可以帮您？")
    handler.session_manager.add_dialogue = Mock()
    handler.session_manager.check_dialogue_end = AsyncMock(return_value=True)
    handler._check_pir_status = AsyncMock(return_value=False)
    
    # 调用统一模式对话
    result = await handler.start_unified_dialogue(
        device_id=device_id,
        session_id=session_id,
        person_info=None,
        visitor_image=visitor_image,
        baseline_image=baseline_image,
        conn=conn
    )
    
    # 验证结果
    assert result["success"] is True, "❌ 对话应该成功"
    print("✓ 统一模式对话完成")
    
    # 验证没有启动定时拍照任务
    assert session_id not in handler._photo_capture_tasks, "❌ 不应启动拍照任务"
    print("✓ 未启动定时拍照任务（符合预期）")


async def test_start_unified_dialogue_exception_cleanup():
    """测试统一模式对话异常时的清理"""
    print("\n=== 测试7: 统一模式对话异常清理 ===")
    
    handler = create_intent_handler()
    conn = create_mock_conn()
    device_id = "test_device_006"
    session_id = "test_session_006"
    visitor_image = b"visitor_image_data"
    baseline_image = b"baseline_image_data"
    
    # 模拟拍照方法
    handler._capture_visitor_photo = AsyncMock(return_value=b"fake_jpeg_data")
    
    # 模拟问候方法抛出异常
    handler._play_initial_greeting = AsyncMock(side_effect=Exception("问候失败"))
    
    # 调用统一模式对话
    result = await handler.start_unified_dialogue(
        device_id=device_id,
        session_id=session_id,
        person_info=None,
        visitor_image=visitor_image,
        baseline_image=baseline_image,
        conn=conn
    )
    
    # 验证返回失败结果
    assert result["success"] is False, "❌ 应该返回失败"
    assert "error" in result, "❌ 应该包含error字段"
    print("✓ 异常时返回失败结果")
    
    # 验证定时拍照任务已停止
    assert session_id not in handler._photo_capture_tasks, "❌ 任务应该已停止"
    print("✓ 定时拍照任务已清理")
    
    # 验证照片缓存已清理
    photo_cache = PhotoCacheManager()
    cache_size = photo_cache.get_cache_size(session_id)
    assert cache_size == 0, f"❌ 缓存应该已清理：实际{cache_size}"
    print("✓ 照片缓存已清理")


async def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始测试 定时拍照任务")
    print("=" * 60)
    
    try:
        await test_start_photo_capture_task()
        await test_stop_photo_capture_task()
        await test_stop_nonexistent_task()
        await test_photo_capture_task_exception_handling()
        await test_start_unified_dialogue_with_guard_mode()
        await test_start_unified_dialogue_without_guard_mode()
        await test_start_unified_dialogue_exception_cleanup()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
