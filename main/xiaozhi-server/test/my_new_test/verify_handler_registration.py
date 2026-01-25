"""
验证 v5.2 新增处理器是否正确注册

测试目标：
1. 验证 Esp32AckHandler 已注册
2. 验证 DoorOpenedReportHandler 已注册
3. 验证 PasswordReportHandler 已注册
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.handle.textMessageHandlerRegistry import TextMessageHandlerRegistry
from core.handle.textHandler.esp32AckHandler import Esp32AckHandler
from core.handle.textHandler.doorOpenedReportHandler import DoorOpenedReportHandler
from core.handle.textHandler.passwordReportHandler import PasswordReportHandler


def test_handler_registration():
    """测试处理器注册"""
    print("=" * 60)
    print("验证 v5.2 新增处理器注册")
    print("=" * 60)
    
    # 创建注册表实例
    registry = TextMessageHandlerRegistry()
    
    # 获取所有支持的消息类型
    supported_types = registry.get_supported_types()
    print(f"\n支持的消息类型总数: {len(supported_types)}")
    print(f"消息类型列表: {sorted(supported_types)}")
    
    # 测试 1: 验证 esp32_ack 处理器
    print("\n" + "-" * 60)
    print("测试 1: 验证 Esp32AckHandler")
    print("-" * 60)
    handler = registry.get_handler("esp32_ack")
    if handler:
        print(f"✓ esp32_ack 处理器已注册")
        print(f"  类型: {type(handler).__name__}")
        print(f"  消息类型: {handler.message_type.value}")
        assert isinstance(handler, Esp32AckHandler), "处理器类型不匹配"
        print("  ✓ 类型验证通过")
    else:
        print("✗ esp32_ack 处理器未注册")
        return False
    
    # 测试 2: 验证 door_opened_report 处理器
    print("\n" + "-" * 60)
    print("测试 2: 验证 DoorOpenedReportHandler")
    print("-" * 60)
    handler = registry.get_handler("door_opened_report")
    if handler:
        print(f"✓ door_opened_report 处理器已注册")
        print(f"  类型: {type(handler).__name__}")
        print(f"  消息类型: {handler.message_type.value}")
        assert isinstance(handler, DoorOpenedReportHandler), "处理器类型不匹配"
        print("  ✓ 类型验证通过")
    else:
        print("✗ door_opened_report 处理器未注册")
        return False
    
    # 测试 3: 验证 password_report 处理器
    print("\n" + "-" * 60)
    print("测试 3: 验证 PasswordReportHandler")
    print("-" * 60)
    handler = registry.get_handler("password_report")
    if handler:
        print(f"✓ password_report 处理器已注册")
        print(f"  类型: {type(handler).__name__}")
        print(f"  消息类型: {handler.message_type.value}")
        assert isinstance(handler, PasswordReportHandler), "处理器类型不匹配"
        print("  ✓ 类型验证通过")
    else:
        print("✗ password_report 处理器未注册")
        return False
    
    print("\n" + "=" * 60)
    print("✓ 所有测试通过！v5.2 新增处理器已正确注册")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        success = test_handler_registration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
