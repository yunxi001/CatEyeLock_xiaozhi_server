#!/usr/bin/env python3
"""
测试 PIR 事件处理优化

验证：
1. FaceRecognitionHandler 初始化参数修复
2. 配置加载缓存优化（避免每次 PIR 事件都重新加载）
"""
import asyncio
import sys
from unittest.mock import Mock, AsyncMock, patch
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, level="DEBUG")


async def test_face_recognition_handler_init():
    """测试 FaceRecognitionHandler 初始化参数修复"""
    print("\n" + "="*60)
    print("测试 1: FaceRecognitionHandler 初始化参数修复")
    print("="*60)
    
    try:
        from core.providers.doorlock.face_recognition_handler import FaceRecognitionHandler
        
        # 创建 mock 对象
        mock_face_service = Mock()
        mock_tts_provider = Mock()
        mock_config = {
            'max_retries': 3,
            'retry_interval': 1
        }
        
        # 测试正确的初始化方式（3个参数）
        handler = FaceRecognitionHandler(
            face_service=mock_face_service,
            tts_provider=mock_tts_provider,
            config=mock_config
        )
        
        print("✅ FaceRecognitionHandler 初始化成功")
        print(f"   - max_retries: {handler.max_retries}")
        print(f"   - retry_interval: {handler.retry_interval}")
        
        return True
        
    except Exception as e:
        print(f"❌ FaceRecognitionHandler 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_doorlock_intent_handler_factory():
    """测试 DoorlockIntentHandler 工厂方法修复"""
    print("\n" + "="*60)
    print("测试 2: DoorlockIntentHandler.create_from_config 修复")
    print("="*60)
    
    try:
        from core.handle.doorlock_intent_handler import DoorlockIntentHandler
        
        # 创建 mock 配置
        mock_config = {
            'doorlock': {
                'face_recognition': {
                    'max_retries': 3,
                    'retry_interval': 1
                },
                'intent_recognition': {
                    'dialogue_timeout': 30,
                    'max_dialogue_rounds': 10
                }
            },
            'selected_module': {}
        }
        
        mock_logger = logger
        
        # Mock 依赖的服务
        with patch('core.handle.doorlock_intent_handler.get_face_service') as mock_get_face_service, \
             patch('core.handle.doorlock_intent_handler.get_tts_provider') as mock_get_tts_provider:
            
            mock_get_face_service.return_value = Mock()
            mock_get_tts_provider.return_value = Mock()
            
            # 测试工厂方法
            handler = await DoorlockIntentHandler.create_from_config(
                config=mock_config,
                logger_instance=mock_logger
            )
            
            print("✅ DoorlockIntentHandler.create_from_config 成功")
            print(f"   - dialogue_timeout: {handler.dialogue_timeout}")
            print(f"   - max_dialogue_rounds: {handler.max_dialogue_rounds}")
            
            return True
            
    except Exception as e:
        print(f"❌ DoorlockIntentHandler.create_from_config 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_event_handler_cache():
    """测试 EventReportHandler 缓存机制"""
    print("\n" + "="*60)
    print("测试 3: EventReportHandler 配置加载缓存优化")
    print("="*60)
    
    try:
        from core.handle.textHandler.eventReportHandler import EventReportHandler
        
        handler = EventReportHandler()
        
        # 检查类级别缓存属性
        assert hasattr(EventReportHandler, '_db_instances'), "缺少 _db_instances 缓存"
        assert hasattr(EventReportHandler, '_intent_handlers'), "缺少 _intent_handlers 缓存"
        assert hasattr(EventReportHandler, '_last_cleanup_time'), "缺少 _last_cleanup_time"
        
        print("✅ EventReportHandler 缓存机制已实现")
        print(f"   - _db_instances: {type(EventReportHandler._db_instances)}")
        print(f"   - _intent_handlers: {type(EventReportHandler._intent_handlers)}")
        print(f"   - _last_cleanup_time: {EventReportHandler._last_cleanup_time}")
        
        # 模拟多次 PIR 事件，验证缓存复用
        print("\n模拟 5 次 PIR 事件，验证缓存复用...")
        
        # 创建 mock 连接对象
        mock_conn = Mock()
        mock_conn.device_id = "test_device_001"
        mock_conn.config = {'doorlock': {}}
        mock_conn.logger = logger
        mock_conn.visitor_processing = False
        
        # Mock 数据库和处理器
        with patch('core.handle.textHandler.eventReportHandler.DoorlockDatabase') as MockDB, \
             patch('core.handle.textHandler.eventReportHandler.DoorlockIntentHandler') as MockHandler, \
             patch('core.handle.textHandler.eventReportHandler.PackageGuardManager'):
            
            # 配置 mock
            mock_db_instance = Mock()
            mock_db_instance.get_config = AsyncMock(return_value=None)  # 返回 None，提前退出
            MockDB.return_value = mock_db_instance
            
            db_create_count = 0
            handler_create_count = 0
            
            def count_db_creation(*args, **kwargs):
                nonlocal db_create_count
                db_create_count += 1
                return mock_db_instance
            
            def count_handler_creation(*args, **kwargs):
                nonlocal handler_create_count
                handler_create_count += 1
                mock_handler_instance = Mock()
                mock_handler_instance.handle_visitor = AsyncMock(return_value={"success": True})
                return mock_handler_instance
            
            MockDB.side_effect = count_db_creation
            MockHandler.create_from_config = AsyncMock(side_effect=count_handler_creation)
            
            # 模拟 5 次 PIR 事件
            for i in range(5):
                await handler._trigger_face_recognition(
                    conn=mock_conn,
                    ts=1000 + i,
                    param=10 + i,
                    trigger_type="pir"
                )
            
            print(f"\n   - 数据库实例创建次数: {db_create_count} (期望: 1)")
            print(f"   - 意图处理器创建次数: {handler_create_count} (期望: 0，因为配置返回None)")
            
            if db_create_count == 1:
                print("   ✅ 数据库实例成功复用（只创建一次）")
            else:
                print(f"   ⚠️  数据库实例创建了 {db_create_count} 次（应该只创建 1 次）")
            
        return True
        
    except Exception as e:
        print(f"❌ EventReportHandler 缓存测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("PIR 事件处理优化测试")
    print("="*60)
    
    results = []
    
    # 测试 1: FaceRecognitionHandler 初始化
    results.append(await test_face_recognition_handler_init())
    
    # 测试 2: DoorlockIntentHandler 工厂方法
    results.append(await test_doorlock_intent_handler_factory())
    
    # 测试 3: EventReportHandler 缓存
    results.append(await test_event_handler_cache())
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("✅ 所有测试通过！")
        return 0
    else:
        print(f"❌ {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
