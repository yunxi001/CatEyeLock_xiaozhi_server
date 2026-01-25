"""
核心功能简化验证脚本（不依赖外部服务）

验证协议升级 v5.0 到 v5.2 的核心功能：
1. 所有新增和更新的 Handler 文件存在
2. 消息类型枚举定义正确
3. 错误码常量定义正确
4. 重试机制方法存在
"""
import sys
import os
import importlib.util

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def check_file_exists(file_path):
    """检查文件是否存在"""
    full_path = os.path.join(os.path.dirname(__file__), '..', file_path)
    return os.path.exists(full_path)


def verify_handler_files():
    """验证所有 Handler 文件存在"""
    print("\n=== 验证 1: Handler 文件存在性 ===")
    
    handler_files = [
        # 新增的 Handler
        "core/handle/textHandler/esp32AckHandler.py",
        "core/handle/textHandler/doorOpenedReportHandler.py",
        "core/handle/textHandler/passwordReportHandler.py",
        # 更新的 Handler
        "core/handle/textHandler/ackHandler.py",
        "core/handle/textHandler/logReportHandler.py",
        "core/handle/textHandler/eventReportHandler.py",
        # 命令代理 Handler
        "core/handle/textHandler/commandProxyHandler.py",
    ]
    
    all_exist = True
    for file_path in handler_files:
        exists = check_file_exists(file_path)
        status = "✓" if exists else "✗"
        print(f"{status} {file_path}")
        if not exists:
            all_exist = False
    
    if all_exist:
        print("✓ 所有 Handler 文件存在")
    else:
        print("✗ 部分 Handler 文件缺失")
    
    return all_exist


def verify_message_types():
    """验证消息类型枚举"""
    print("\n=== 验证 2: 消息类型枚举 ===")
    
    try:
        from core.handle.textMessageType import TextMessageType
        
        # 验证新增的消息类型
        required_types = [
            ("ESP32_ACK", "esp32_ack"),
            ("DOOR_OPENED_REPORT", "door_opened_report"),
            ("PASSWORD_REPORT", "password_report"),
        ]
        
        all_valid = True
        for type_name, type_value in required_types:
            if hasattr(TextMessageType, type_name):
                actual_value = getattr(TextMessageType, type_name).value
                if actual_value == type_value:
                    print(f"✓ {type_name} = '{type_value}'")
                else:
                    print(f"✗ {type_name} 值不正确: 期望 '{type_value}'，实际 '{actual_value}'")
                    all_valid = False
            else:
                print(f"✗ 缺少消息类型: {type_name}")
                all_valid = False
        
        if all_valid:
            print("✓ 所有消息类型枚举验证通过")
        else:
            print("✗ 部分消息类型枚举验证失败")
        
        return all_valid
        
    except Exception as e:
        print(f"✗ 消息类型验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_error_codes():
    """验证错误码常量定义"""
    print("\n=== 验证 3: 错误码常量 ===")
    
    try:
        from core.constants.error_codes import (
            ErrorCode,
            ERROR_MESSAGES,
            is_valid_error_code,
            get_error_message
        )
        
        # 验证错误码常量
        error_codes = [
            ("SUCCESS", 0),
            ("DEVICE_OFFLINE", 1),
            ("DEVICE_BUSY", 2),
            ("PARAM_ERROR", 3),
            ("NOT_SUPPORTED", 4),
            ("TIMEOUT", 5),
            ("HARDWARE_FAULT", 6),
            ("RESOURCE_FULL", 7),
            ("UNAUTHORIZED", 8),
            ("DUPLICATE_MESSAGE", 9),
            ("INTERNAL_ERROR", 10),
        ]
        
        all_valid = True
        for name, expected_value in error_codes:
            if hasattr(ErrorCode, name):
                actual_value = getattr(ErrorCode, name)
                if actual_value == expected_value:
                    print(f"✓ ErrorCode.{name} = {expected_value}")
                else:
                    print(f"✗ ErrorCode.{name} 值不正确: 期望 {expected_value}，实际 {actual_value}")
                    all_valid = False
            else:
                print(f"✗ 缺少错误码: {name}")
                all_valid = False
        
        # 验证错误消息
        if len(ERROR_MESSAGES) == 11:
            print(f"✓ 错误消息字典包含 {len(ERROR_MESSAGES)} 条消息")
        else:
            print(f"✗ 错误消息数量不正确: 期望 11，实际 {len(ERROR_MESSAGES)}")
            all_valid = False
        
        # 验证辅助函数
        test_cases = [
            (is_valid_error_code(0), True, "is_valid_error_code(0)"),
            (is_valid_error_code(5), True, "is_valid_error_code(5)"),
            (is_valid_error_code(10), True, "is_valid_error_code(10)"),
            (is_valid_error_code(-1), False, "is_valid_error_code(-1)"),
            (is_valid_error_code(11), False, "is_valid_error_code(11)"),
        ]
        
        for actual, expected, test_name in test_cases:
            if actual == expected:
                print(f"✓ {test_name} = {expected}")
            else:
                print(f"✗ {test_name} 失败: 期望 {expected}，实际 {actual}")
                all_valid = False
        
        # 验证错误消息获取
        msg_tests = [
            (get_error_message(0), "成功"),
            (get_error_message(5), "超时"),
            (get_error_message(10), "内部错误"),
            (get_error_message(99), "未知错误"),
        ]
        
        for actual, expected in msg_tests:
            if actual == expected:
                print(f"✓ get_error_message() 返回正确: '{expected}'")
            else:
                print(f"✗ get_error_message() 返回错误: 期望 '{expected}'，实际 '{actual}'")
                all_valid = False
        
        if all_valid:
            print("✓ 所有错误码验证通过")
        else:
            print("✗ 部分错误码验证失败")
        
        return all_valid
        
    except Exception as e:
        print(f"✗ 错误码验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_handler_content():
    """验证 Handler 内容（检查关键方法和属性）"""
    print("\n=== 验证 4: Handler 内容 ===")
    
    try:
        # 读取 Handler 文件内容
        handlers_to_check = [
            ("esp32AckHandler.py", ["class Esp32AckHandler", "def handle", "message_type", "_pending_esp32_acks"]),
            ("doorOpenedReportHandler.py", ["class DoorOpenedReportHandler", "def handle", "save_door_opened_log"]),
            ("passwordReportHandler.py", ["class PasswordReportHandler", "def handle", "PASSWORD_REPORT"]),
            ("ackHandler.py", ["seq_id", "is_valid_error_code", "get_error_message"]),
            ("logReportHandler.py", ["status", "lock_time", "success", "fail", "locked"]),
            ("eventReportHandler.py", ["door_closed", "lock_success", "bolt_alarm"]),
            ("commandProxyHandler.py", ["_forward_with_retry", "_wait_for_esp32_ack", "_send_error"]),
        ]
        
        all_valid = True
        for filename, keywords in handlers_to_check:
            file_path = os.path.join(os.path.dirname(__file__), '..', 'core', 'handle', 'textHandler', filename)
            
            if not os.path.exists(file_path):
                print(f"✗ 文件不存在: {filename}")
                all_valid = False
                continue
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            missing_keywords = []
            for keyword in keywords:
                if keyword not in content:
                    missing_keywords.append(keyword)
            
            if missing_keywords:
                print(f"✗ {filename} 缺少关键内容: {', '.join(missing_keywords)}")
                all_valid = False
            else:
                print(f"✓ {filename} 包含所有关键内容")
        
        if all_valid:
            print("✓ 所有 Handler 内容验证通过")
        else:
            print("✗ 部分 Handler 内容验证失败")
        
        return all_valid
        
    except Exception as e:
        print(f"✗ Handler 内容验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_database_methods():
    """验证数据库方法"""
    print("\n=== 验证 5: 数据库方法 ===")
    
    try:
        # 检查数据库方法文件
        db_file = os.path.join(os.path.dirname(__file__), '..', 'core', 'providers', 'doorlock', 'database.py')
        
        if not os.path.exists(db_file):
            print(f"✗ 数据库文件不存在: {db_file}")
            return False
        
        with open(db_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键方法
        required_methods = [
            "save_unlock_log",
            "save_door_opened_log",
            "save_device_event",
        ]
        
        all_valid = True
        for method in required_methods:
            if f"def {method}" in content:
                print(f"✓ 数据库方法存在: {method}")
            else:
                print(f"✗ 数据库方法缺失: {method}")
                all_valid = False
        
        # 检查新字段支持
        new_fields = ["status", "lock_time"]
        for field in new_fields:
            if field in content:
                print(f"✓ 支持新字段: {field}")
            else:
                print(f"⚠ 可能缺少新字段支持: {field}")
        
        if all_valid:
            print("✓ 数据库方法验证通过")
        else:
            print("✗ 部分数据库方法验证失败")
        
        return all_valid
        
    except Exception as e:
        print(f"✗ 数据库方法验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("协议升级 v5.0 到 v5.2 - 核心功能简化验证")
    print("=" * 60)
    
    results = []
    
    # 执行所有验证
    results.append(("Handler 文件存在性", verify_handler_files()))
    results.append(("消息类型枚举", verify_message_types()))
    results.append(("错误码常量", verify_error_codes()))
    results.append(("Handler 内容", verify_handler_content()))
    results.append(("数据库方法", verify_database_methods()))
    
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
        print("\n核心功能清单：")
        print("  ✓ 新增 3 个消息处理器（esp32_ack、door_opened_report、password_report）")
        print("  ✓ 更新 3 个现有处理器（ack、log_report、event_report）")
        print("  ✓ 实现命令下发重试机制")
        print("  ✓ 错误码常量定义完整")
        print("  ✓ 消息类型枚举更新")
        print("  ✓ 数据库访问方法就绪")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 项验证失败，请检查")
        return 1


if __name__ == "__main__":
    sys.exit(main())
