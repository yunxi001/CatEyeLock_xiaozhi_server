"""
验证 v5.2 新增处理器导入是否正确

这个脚本只验证导入语句，不实例化对象，避免触发配置加载
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

print("=" * 60)
print("验证 v5.2 新增处理器导入")
print("=" * 60)

# 测试 1: 验证 esp32AckHandler 导入
print("\n测试 1: 导入 Esp32AckHandler")
try:
    from core.handle.textHandler.esp32AckHandler import Esp32AckHandler
    print("✓ Esp32AckHandler 导入成功")
    print(f"  类名: {Esp32AckHandler.__name__}")
except ImportError as e:
    print(f"✗ Esp32AckHandler 导入失败: {e}")
    sys.exit(1)

# 测试 2: 验证 doorOpenedReportHandler 导入
print("\n测试 2: 导入 DoorOpenedReportHandler")
try:
    from core.handle.textHandler.doorOpenedReportHandler import DoorOpenedReportHandler
    print("✓ DoorOpenedReportHandler 导入成功")
    print(f"  类名: {DoorOpenedReportHandler.__name__}")
except ImportError as e:
    print(f"✗ DoorOpenedReportHandler 导入失败: {e}")
    sys.exit(1)

# 测试 3: 验证 passwordReportHandler 导入
print("\n测试 3: 导入 PasswordReportHandler")
try:
    from core.handle.textHandler.passwordReportHandler import PasswordReportHandler
    print("✓ PasswordReportHandler 导入成功")
    print(f"  类名: {PasswordReportHandler.__name__}")
except ImportError as e:
    print(f"✗ PasswordReportHandler 导入失败: {e}")
    sys.exit(1)

# 测试 4: 验证注册表文件的导入语句
print("\n测试 4: 验证注册表文件的导入语句")
try:
    registry_file = os.path.join(os.path.dirname(__file__), '..', 'core', 'handle', 'textMessageHandlerRegistry.py')
    with open(registry_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查导入语句
    imports_found = []
    if 'from core.handle.textHandler.esp32AckHandler import Esp32AckHandler' in content:
        imports_found.append('Esp32AckHandler')
    if 'from core.handle.textHandler.doorOpenedReportHandler import DoorOpenedReportHandler' in content:
        imports_found.append('DoorOpenedReportHandler')
    if 'from core.handle.textHandler.passwordReportHandler import PasswordReportHandler' in content:
        imports_found.append('PasswordReportHandler')
    
    print(f"✓ 找到 {len(imports_found)} 个导入语句:")
    for imp in imports_found:
        print(f"  - {imp}")
    
    if len(imports_found) != 3:
        print("✗ 导入语句不完整")
        sys.exit(1)
    
    # 检查注册语句
    registrations_found = []
    if 'Esp32AckHandler()' in content:
        registrations_found.append('Esp32AckHandler()')
    if 'DoorOpenedReportHandler()' in content:
        registrations_found.append('DoorOpenedReportHandler()')
    if 'PasswordReportHandler()' in content:
        registrations_found.append('PasswordReportHandler()')
    
    print(f"\n✓ 找到 {len(registrations_found)} 个注册语句:")
    for reg in registrations_found:
        print(f"  - {reg}")
    
    if len(registrations_found) != 3:
        print("✗ 注册语句不完整")
        sys.exit(1)
    
except Exception as e:
    print(f"✗ 验证注册表文件失败: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ 所有验证通过！")
print("=" * 60)
print("\n总结:")
print("  - 3 个处理器类导入成功")
print("  - 3 个导入语句已添加到注册表")
print("  - 3 个注册语句已添加到 _register_default_handlers()")
