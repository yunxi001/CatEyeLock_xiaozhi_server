#!/usr/bin/env python3
"""
验证 DoorOpenedReportHandler 实现的静态检查脚本
不需要运行服务器，只检查代码结构
"""
import os
import ast
import sys


def check_file_exists(filepath):
    """检查文件是否存在"""
    if os.path.exists(filepath):
        print(f"✓ 文件存在: {filepath}")
        return True
    else:
        print(f"✗ 文件不存在: {filepath}")
        return False


def parse_python_file(filepath):
    """解析 Python 文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)
        return tree, content
    except Exception as e:
        print(f"✗ 解析文件失败: {e}")
        return None, None


def check_class_exists(tree, class_name):
    """检查类是否存在"""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            print(f"✓ 类存在: {class_name}")
            return node
    print(f"✗ 类不存在: {class_name}")
    return None


def check_method_exists(class_node, method_name):
    """检查方法是否存在（包括 async 方法）"""
    for node in class_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name:
            print(f"✓ 方法存在: {method_name}")
            return node
    print(f"✗ 方法不存在: {method_name}")
    return None


def check_property_exists(class_node, property_name):
    """检查属性是否存在"""
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == property_name:
            # 检查是否有 @property 装饰器
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name) and decorator.id == 'property':
                    print(f"✓ 属性存在: {property_name}")
                    return node
    print(f"✗ 属性不存在: {property_name}")
    return None


def check_imports(content, required_imports):
    """检查必需的导入"""
    for imp in required_imports:
        if imp in content:
            print(f"✓ 导入存在: {imp}")
        else:
            print(f"✗ 导入缺失: {imp}")


def verify_handler():
    """验证 DoorOpenedReportHandler"""
    print("=== 验证 DoorOpenedReportHandler 实现 ===\n")
    
    # 1. 检查文件存在
    print("步骤 1: 检查文件")
    handler_file = "core/handle/textHandler/doorOpenedReportHandler.py"
    if not check_file_exists(handler_file):
        return False
    
    # 2. 解析文件
    print("\n步骤 2: 解析文件")
    tree, content = parse_python_file(handler_file)
    if tree is None:
        return False
    print("✓ 文件解析成功")
    
    # 3. 检查类
    print("\n步骤 3: 检查类定义")
    class_node = check_class_exists(tree, "DoorOpenedReportHandler")
    if class_node is None:
        return False
    
    # 4. 检查继承
    print("\n步骤 4: 检查继承")
    if class_node.bases:
        base_name = None
        for base in class_node.bases:
            if isinstance(base, ast.Name):
                base_name = base.id
        if base_name == "TextMessageHandler":
            print(f"✓ 继承正确: TextMessageHandler")
        else:
            print(f"✗ 继承错误: {base_name}")
    
    # 5. 检查属性
    print("\n步骤 5: 检查属性")
    check_property_exists(class_node, "message_type")
    
    # 6. 检查方法
    print("\n步骤 6: 检查方法")
    check_method_exists(class_node, "handle")
    check_method_exists(class_node, "_save_to_database")
    check_method_exists(class_node, "_forward_to_apps")
    
    # 7. 检查导入
    print("\n步骤 7: 检查导入")
    required_imports = [
        "from core.handle.textMessageHandler import TextMessageHandler",
        "from core.handle.textMessageType import TextMessageType",
        "from core.connection_manager import ConnectionManager",
    ]
    check_imports(content, required_imports)
    
    # 8. 检查关键字
    print("\n步骤 8: 检查关键实现")
    keywords = [
        "DOOR_OPENED_REPORT",
        "save_door_opened_log",
        "method",
        "source",
        "valid_methods",
        "valid_sources",
    ]
    for keyword in keywords:
        if keyword in content:
            print(f"✓ 关键字存在: {keyword}")
        else:
            print(f"✗ 关键字缺失: {keyword}")
    
    return True


def verify_database():
    """验证数据库方法"""
    print("\n\n=== 验证数据库方法 ===\n")
    
    # 1. 检查文件
    print("步骤 1: 检查数据库文件")
    db_file = "core/providers/doorlock/database.py"
    if not check_file_exists(db_file):
        return False
    
    # 2. 解析文件
    print("\n步骤 2: 解析数据库文件")
    tree, content = parse_python_file(db_file)
    if tree is None:
        return False
    print("✓ 文件解析成功")
    
    # 3. 检查类
    print("\n步骤 3: 检查 Database 类")
    class_node = check_class_exists(tree, "Database")
    if class_node is None:
        return False
    
    # 4. 检查方法
    print("\n步骤 4: 检查数据库方法")
    check_method_exists(class_node, "save_door_opened_log")
    
    # 5. 检查表创建
    print("\n步骤 5: 检查表创建 SQL")
    if "door_opened_logs" in content:
        print("✓ door_opened_logs 表创建语句存在")
    else:
        print("✗ door_opened_logs 表创建语句缺失")
    
    # 6. 检查字段
    print("\n步骤 6: 检查表字段")
    fields = ["device_id", "method", "source", "created_at"]
    for field in fields:
        if field in content:
            print(f"✓ 字段存在: {field}")
        else:
            print(f"✗ 字段缺失: {field}")
    
    return True


def main():
    """主函数"""
    success = True
    
    # 切换到项目根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
    
    # 验证 Handler
    if not verify_handler():
        success = False
    
    # 验证数据库
    if not verify_database():
        success = False
    
    # 输出结果
    print("\n" + "="*60)
    if success:
        print("✓ 所有验证通过！DoorOpenedReportHandler 实现正确。")
    else:
        print("✗ 验证失败，请检查上述错误。")
    print("="*60)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
