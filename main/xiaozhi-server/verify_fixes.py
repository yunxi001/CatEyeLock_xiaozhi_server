#!/usr/bin/env python3
"""
验证 PIR 优化修复

检查点：
1. FaceRecognitionHandler 构造函数签名正确（3个参数）
2. EventReportHandler 有缓存机制
3. doorlock_intent_handler.py 中的 create_from_config 方法正确调用 FaceRecognitionHandler
"""
import inspect
import sys


def verify_face_recognition_handler():
    """验证 FaceRecognitionHandler 构造函数"""
    print("\n" + "="*60)
    print("验证 1: FaceRecognitionHandler 构造函数签名")
    print("="*60)
    
    try:
        from core.providers.doorlock.face_recognition_handler import FaceRecognitionHandler
        
        # 获取构造函数签名
        sig = inspect.signature(FaceRecognitionHandler.__init__)
        params = list(sig.parameters.keys())
        
        print(f"构造函数参数: {params}")
        
        # 期望: ['self', 'face_service', 'tts_provider', 'config']
        expected_params = ['self', 'face_service', 'tts_provider', 'config']
        
        if params == expected_params:
            print("✅ 构造函数签名正确")
            return True
        else:
            print(f"❌ 构造函数签名不正确")
            print(f"   期望: {expected_params}")
            print(f"   实际: {params}")
            return False
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False


def verify_event_handler_cache():
    """验证 EventReportHandler 缓存机制"""
    print("\n" + "="*60)
    print("验证 2: EventReportHandler 缓存机制")
    print("="*60)
    
    try:
        from core.handle.textHandler.eventReportHandler import EventReportHandler
        
        # 检查类属性
        has_db_cache = hasattr(EventReportHandler, '_db_instances')
        has_handler_cache = hasattr(EventReportHandler, '_intent_handlers')
        has_cleanup_time = hasattr(EventReportHandler, '_last_cleanup_time')
        
        print(f"_db_instances 缓存: {'✅' if has_db_cache else '❌'}")
        print(f"_intent_handlers 缓存: {'✅' if has_handler_cache else '❌'}")
        print(f"_last_cleanup_time: {'✅' if has_cleanup_time else '❌'}")
        
        if has_db_cache and has_handler_cache and has_cleanup_time:
            print("✅ 缓存机制已实现")
            return True
        else:
            print("❌ 缓存机制不完整")
            return False
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False


def verify_create_from_config():
    """验证 create_from_config 方法中的 FaceRecognitionHandler 调用"""
    print("\n" + "="*60)
    print("验证 3: create_from_config 中的 FaceRecognitionHandler 调用")
    print("="*60)
    
    try:
        # 读取源代码
        with open('core/handle/doorlock_intent_handler.py', 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        # 检查关键代码片段
        checks = [
            ('导入 get_face_service', 'from core.handle.textHandler.faceRecognitionHandler import get_face_service'),
            ('导入 get_tts_provider', 'from core.providers.tts.base import get_tts_provider'),
            ('调用 get_face_service', 'face_service = get_face_service(logger_instance)'),
            ('调用 get_tts_provider', 'tts_provider = get_tts_provider(config, logger_instance)'),
            ('正确初始化 FaceRecognitionHandler', 'face_handler = FaceRecognitionHandler('),
            ('传递 face_service 参数', 'face_service=face_service'),
            ('传递 tts_provider 参数', 'tts_provider=tts_provider'),
            ('传递 config 参数', "config=doorlock_config.get('face_recognition', {})")
        ]
        
        all_passed = True
        for check_name, check_str in checks:
            if check_str in source_code:
                print(f"✅ {check_name}")
            else:
                print(f"❌ {check_name}")
                all_passed = False
        
        if all_passed:
            print("\n✅ create_from_config 方法修复正确")
            return True
        else:
            print("\n❌ create_from_config 方法修复不完整")
            return False
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_trigger_face_recognition():
    """验证 _trigger_face_recognition 方法使用缓存"""
    print("\n" + "="*60)
    print("验证 4: _trigger_face_recognition 使用缓存")
    print("="*60)
    
    try:
        # 读取源代码
        with open('core/handle/textHandler/eventReportHandler.py', 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        # 检查关键代码片段
        checks = [
            ('检查缓存是否存在', 'if device_id not in self._db_instances:'),
            ('创建数据库实例并缓存', 'self._db_instances[device_id] = DoorlockDatabase'),
            ('从缓存获取数据库实例', 'db = self._db_instances[device_id]'),
            ('检查意图处理器缓存', 'if device_id not in self._intent_handlers:'),
            ('创建意图处理器并缓存', 'self._intent_handlers[device_id] = await DoorlockIntentHandler.create_from_config'),
            ('从缓存获取意图处理器', 'intent_handler = self._intent_handlers[device_id]'),
            ('定期清理缓存', 'if current_time - self._last_cleanup_time > 3600:')
        ]
        
        all_passed = True
        for check_name, check_str in checks:
            if check_str in source_code:
                print(f"✅ {check_name}")
            else:
                print(f"❌ {check_name}")
                all_passed = False
        
        if all_passed:
            print("\n✅ _trigger_face_recognition 缓存优化正确")
            return True
        else:
            print("\n❌ _trigger_face_recognition 缓存优化不完整")
            return False
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有验证"""
    print("\n" + "="*60)
    print("PIR 事件处理优化修复验证")
    print("="*60)
    
    results = []
    
    # 验证 1: FaceRecognitionHandler 构造函数
    results.append(verify_face_recognition_handler())
    
    # 验证 2: EventReportHandler 缓存机制
    results.append(verify_event_handler_cache())
    
    # 验证 3: create_from_config 方法
    results.append(verify_create_from_config())
    
    # 验证 4: _trigger_face_recognition 缓存
    results.append(verify_trigger_face_recognition())
    
    # 总结
    print("\n" + "="*60)
    print("验证总结")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("\n✅ 所有修复验证通过！")
        print("\n修复内容：")
        print("1. ✅ FaceRecognitionHandler 初始化参数修复（3个参数）")
        print("2. ✅ EventReportHandler 添加类级别缓存")
        print("3. ✅ create_from_config 正确调用 FaceRecognitionHandler")
        print("4. ✅ _trigger_face_recognition 使用缓存避免重复加载")
        print("\n预期效果：")
        print("- 每次 PIR 事件不再重新加载配置和创建实例")
        print("- 数据库连接池和意图处理器会被缓存复用")
        print("- 每小时自动清理一次缓存，避免内存泄漏")
        return 0
    else:
        print(f"\n❌ {total - passed} 个验证失败")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
