"""
核心功能验证脚本

验证协议升级 v5.0 到 v5.2 的核心功能：
1. 所有新增和更新的 Handler 已实现
2. 消息路由正确注册
3. 错误码常量定义正确
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def verify_handlers():
    """验证所有 Handler 已实现"""
    print("\n=== 验证 1: Handler 实现 ===")
    
    try:
        # 验证新增的 Handler
        from core.handle.textHandler.esp32AckHandler import Esp32AckHandler
        from core.handle.textHandler.doorOpenedReportHandler import DoorOpenedReportHandler
        from core.handle.textHandler.passwordReportHandler import PasswordReportHandler
        
        # 验证更新的 Handler
        from core.handle.textHandler.ackHandler import AckHandler
        from core.handle.textHandler.logReportHandler import LogReportHandler
        from core.handle.textHandler.eventReportHandler import EventReportHandler
        
        # 验证命令代理 Handler（包含重试机制）
        from core.handle.textHandler.commandProxyHandler import (
            LockControlProxyHandler,
            DevControlProxyHandler,
            UserMgmtProxyHandler
        )
        
        print("✓ 所有 Handler 类已成功导入")
        
        # 验证 Handler 实例化
        handlers = [
            Esp32AckHandler(),
            DoorOpenedReportHandler(),
            PasswordReportHandler(),
            AckHandler(),
            LogReportHandler(),
            EventReportHandler(),
            LockControlProxyHandler(),
            DevControlProxyHandler(),
            UserMgmtProxyHandler(),
        ]
        
        print(f"✓ 成功实例化 {len(handlers)} 个 Handler")
        
        # 验证 Handler 接口
        for handler in handlers:
            assert hasattr(handler, 'message_type'), f"{handler.__class__.__name__} 缺少 message_type 属性"
            assert hasattr(handler, 'handle'), f"{handler.__class__.__name__} 缺少 handle 方法"
        
        print("✓ 所有 Handler 接口验证通过")
        
        return True
        
    except Exception as e:
        print(f"✗ Handler 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_message_types():
    """验证消息类型枚举"""
    print("\n=== 验证 2: 消息类型枚举 ===")
    
    try:
        from core.handle.textMessageType import TextMessageType
        
        # 验证新增的消息类型
        required_types = [
            "ESP32_ACK",
            "DOOR_OPENED_REPORT",
            "PASSWORD_REPORT",
        ]
        
        for type_name in required_types:
            assert hasattr(TextMessageType, type_name), f"缺少消息类型: {type_name}"
            print(f"✓ 消息类型 {type_name} 已定义")
        
        # 验证枚举值
        assert TextMessageType.ESP32_ACK.value == "esp32_ack"
        assert TextMessageType.DOOR_OPENED_REPORT.value == "door_opened_report"
        assert TextMessageType.PASSWORD_REPORT.value == "password_report"
        
        print("✓ 所有消息类型枚举验证通过")
        
        return True
        
    except Exception as e:
        print(f"✗ 消息类型验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_handler_registry():
    """验证 Handler 注册表"""
    print("\n=== 验证 3: Handler 注册表 ===")
    
    try:
        from core.handle.textMessageHandlerRegistry import TextMessageHandlerRegistry
        
        registry = TextMessageHandlerRegistry()
        
        # 验证新增的 Handler 已注册
        required_handlers = [
            "esp32_ack",
            "door_opened_report",
            "password_report",
        ]
        
        for handler_type in required_handlers:
            handler = registry.get_handler(handler_type)
            assert handler is not None, f"Handler 未注册: {handler_type}"
            print(f"✓ Handler 已注册: {handler_type} -> {handler.__class__.__name__}")
        
        # 验证更新的 Handler 仍然注册
        updated_handlers = [
            "ack",
            "log_report",
            "event_report",
        ]
        
        for handler_type in updated_handlers:
            handler = registry.get_handler(handler_type)
            assert handler is not None, f"Handler 未注册: {handler_type}"
            print(f"✓ Handler 已注册: {handler_type} -> {handler.__class__.__name__}")
        
        # 验证命令代理 Handler 已注册
        proxy_handlers = [
            "lock_control",
            "dev_control",
            "user_mgmt",
        ]
        
        for handler_type in proxy_handlers:
            handler = registry.get_handler(handler_type)
            assert handler is not None, f"Handler 未注册: {handler_type}"
            print(f"✓ Handler 已注册: {handler_type} -> {handler.__class__.__name__}")
        
        print(f"✓ 注册表共有 {len(registry.get_supported_types())} 个 Handler")
        
        return True
        
    except Exception as e:
        print(f"✗ Handler 注册表验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_error_codes():
    """验证错误码常量定义"""
    print("\n=== 验证 4: 错误码常量 ===")
    
    try:
        from core.constants.error_codes import (
            ErrorCode,
            ERROR_MESSAGES,
            is_valid_error_code,
            get_error_message
        )
        
        # 验证错误码常量
        assert ErrorCode.SUCCESS == 0
        assert ErrorCode.DEVICE_OFFLINE == 1
        assert ErrorCode.DEVICE_BUSY == 2
        assert ErrorCode.PARAM_ERROR == 3
        assert ErrorCode.NOT_SUPPORTED == 4
        assert ErrorCode.TIMEOUT == 5
        assert ErrorCode.HARDWARE_FAULT == 6
        assert ErrorCode.RESOURCE_FULL == 7
        assert ErrorCode.UNAUTHORIZED == 8
        assert ErrorCode.DUPLICATE_MESSAGE == 9
        assert ErrorCode.INTERNAL_ERROR == 10
        
        print("✓ 所有错误码常量已定义")
        
        # 验证错误消息
        assert len(ERROR_MESSAGES) == 11, f"错误消息数量不正确: {len(ERROR_MESSAGES)}"
        print(f"✓ 错误消息字典包含 {len(ERROR_MESSAGES)} 条消息")
        
        # 验证辅助函数
        assert is_valid_error_code(0) == True
        assert is_valid_error_code(5) == True
        assert is_valid_error_code(10) == True
        assert is_valid_error_code(-1) == False
        assert is_valid_error_code(11) == False
        
        print("✓ is_valid_error_code() 函数验证通过")
        
        assert get_error_message(0) == "成功"
        assert get_error_message(5) == "超时"
        assert get_error_message(10) == "内部错误"
        assert get_error_message(99) == "未知错误"
        
        print("✓ get_error_message() 函数验证通过")
        
        return True
        
    except Exception as e:
        print(f"✗ 错误码验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_retry_mechanism():
    """验证命令重试机制"""
    print("\n=== 验证 5: 命令重试机制 ===")
    
    try:
        from core.handle.textHandler.commandProxyHandler import (
            LockControlProxyHandler,
            DevControlProxyHandler,
            UserMgmtProxyHandler
        )
        
        # 验证重试方法存在
        handlers = [
            LockControlProxyHandler(),
            DevControlProxyHandler(),
            UserMgmtProxyHandler(),
        ]
        
        for handler in handlers:
            assert hasattr(handler, '_forward_with_retry'), \
                f"{handler.__class__.__name__} 缺少 _forward_with_retry 方法"
            assert hasattr(handler, '_wait_for_esp32_ack'), \
                f"{handler.__class__.__name__} 缺少 _wait_for_esp32_ack 方法"
            assert hasattr(handler, '_send_error'), \
                f"{handler.__class__.__name__} 缺少 _send_error 方法"
            print(f"✓ {handler.__class__.__name__} 包含重试机制方法")
        
        print("✓ 所有命令代理 Handler 包含重试机制")
        
        return True
        
    except Exception as e:
        print(f"✗ 重试机制验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("协议升级 v5.0 到 v5.2 - 核心功能验证")
    print("=" * 60)
    
    results = []
    
    # 执行所有验证
    results.append(("Handler 实现", verify_handlers()))
    results.append(("消息类型枚举", verify_message_types()))
    results.append(("Handler 注册表", verify_handler_registry()))
    results.append(("错误码常量", verify_error_codes()))
    results.append(("命令重试机制", verify_retry_mechanism()))
    
    # 输出总结
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name}: {status}")
    
    print(f"\n总计: {passed}/{total} 项验证通过")
    
    if passed == total:
        print("\n🎉 所有核心功能验证通过！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 项验证失败，请检查")
        return 1


if __name__ == "__main__":
    sys.exit(main())
