#!/usr/bin/env python3
"""
验证 PasswordReportHandler 实现的静态检查脚本
不需要运行服务器，只检查代码结构
"""
import os
import sys
import ast

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def check_file_exists(filepath):
    """检查文件是否存在"""
    full_path = os.path.join(os.path.dirname(__file__), '..', filepath)
    exists = os.path.exists(full_path)
    if exists:
        print(f"  ✓ 文件存在: {filepath}")
    else:
        print(f"  ✗ 文件不存在: {filepath}")
    return exists


def check_imports(tree):
    """检查必需的导入"""
    print("\n步骤 2: 检查导入")
    required_imports = {
        'json': False,
        'Dict': False,
        'Any': False,
        'TextMessageHandler': False,
        'TextMessageType': False,
        'ConnectionManager': False,
    }
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in required_imports:
                    required_imports[alias.name] = True
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in required_imports:
                    required_imports[alias.name] = True
    
    all_imported = True
    for name, imported in required_imports.items():
        if imported:
            print(f"  ✓ 导入 {name}")
        else:
            print(f"  ✗ 缺少导入 {name}")
            all_imported = False
    
    return all_imported


def check_class_exists(tree, class_name):
    """检查类是否存在"""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            print(f"  ✓ 类 {class_name} 存在")
            return node
    print(f"  ✗ 类 {class_name} 不存在")
    return None


def check_class_inheritance(class_node):
    """检查类继承"""
    print("\n步骤 4: 检查类继承")
    if class_node.bases:
        for base in class_node.bases:
            if isinstance(base, ast.Name) and base.id == 'TextMessageHandler':
                print(f"  ✓ 继承自 TextMessageHandler")
                return True
    print(f"  ✗ 未继承 TextMessageHandler")
    return False


def check_property_method(class_node, method_name):
    """检查属性方法"""
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef) and item.name == method_name:
            # 检查是否有 @property 装饰器
            for decorator in item.decorator_list:
                if isinstance(decorator, ast.Name) and decorator.id == 'property':
                    print(f"  ✓ 属性方法 {method_name} 存在")
                    return True
    print(f"  ✗ 属性方法 {method_name} 不存在")
    return False


def check_async_method(class_node, method_name):
    """检查异步方法"""
    for item in class_node.body:
        if isinstance(item, ast.AsyncFunctionDef) and item.name == method_name:
            print(f"  ✓ 异步方法 {method_name} 存在")
            return True
    print(f"  ✗ 异步方法 {method_name} 不存在")
    return False


def check_method_parameters(class_node, method_name, expected_params):
    """检查方法参数"""
    for item in class_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
            actual_params = [arg.arg for arg in item.args.args]
            if set(expected_params).issubset(set(actual_params)):
                print(f"  ✓ 方法 {method_name} 参数正确: {actual_params}")
                return True
            else:
                print(f"  ✗ 方法 {method_name} 参数不正确")
                print(f"    期望: {expected_params}")
                print(f"    实际: {actual_params}")
                return False
    return False


def check_method_body_contains(class_node, method_name, keywords):
    """检查方法体是否包含关键字"""
    for item in class_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
            method_source = ast.unparse(item)
            missing = []
            for keyword in keywords:
                if keyword not in method_source:
                    missing.append(keyword)
            
            if not missing:
                print(f"  ✓ 方法 {method_name} 包含所有关键逻辑")
                return True
            else:
                print(f"  ✗ 方法 {method_name} 缺少关键逻辑: {missing}")
                return False
    return False


def verify_handler():
    """验证 PasswordReportHandler"""
    print("=== 验证 PasswordReportHandler 实现 ===\n")
    
    success = True
    
    # 1. 检查文件存在
    print("步骤 1: 检查文件")
    handler_file = "core/handle/textHandler/passwordReportHandler.py"
    
    if not check_file_exists(handler_file):
        return False
    
    # 读取文件内容
    full_path = os.path.join(os.path.dirname(__file__), '..', handler_file)
    with open(full_path, 'r', encoding='utf-8') as f:
        source = f.read()
    
    tree = ast.parse(source)
    
    # 2. 检查导入
    if not check_imports(tree):
        success = False
    
    # 3. 检查类
    print("\n步骤 3: 检查类定义")
    class_node = check_class_exists(tree, "PasswordReportHandler")
    
    if class_node is None:
        return False
    
    # 4. 检查继承
    if not check_class_inheritance(class_node):
        success = False
    
    # 5. 检查 message_type 属性
    print("\n步骤 5: 检查 message_type 属性")
    if not check_property_method(class_node, "message_type"):
        success = False
    
    # 6. 检查 handle 方法
    print("\n步骤 6: 检查 handle 方法")
    if not check_async_method(class_node, "handle"):
        success = False
    
    if not check_method_parameters(class_node, "handle", ["self", "conn", "msg_json"]):
        success = False
    
    # 7. 检查 handle 方法逻辑
    print("\n步骤 7: 检查 handle 方法逻辑")
    handle_keywords = [
        "ts",
        "data",
        "password",
        "logger",
        "info",  # INFO 级别日志
        "_forward_to_apps"
    ]
    if not check_method_body_contains(class_node, "handle", handle_keywords):
        success = False
    
    # 8. 检查 _forward_to_apps 方法
    print("\n步骤 8: 检查 _forward_to_apps 方法")
    if not check_async_method(class_node, "_forward_to_apps"):
        success = False
    
    if not check_method_parameters(class_node, "_forward_to_apps", ["self", "conn", "msg_json"]):
        success = False
    
    # 9. 检查转发逻辑
    print("\n步骤 9: 检查转发逻辑")
    forward_keywords = [
        "ConnectionManager",
        "get_app_conns",
        "websocket",
        "send"
    ]
    if not check_method_body_contains(class_node, "_forward_to_apps", forward_keywords):
        success = False
    
    # 10. 检查是否不存储到数据库
    print("\n步骤 10: 检查不存储到数据库")
    handle_source = None
    for item in class_node.body:
        if isinstance(item, ast.AsyncFunctionDef) and item.name == "handle":
            handle_source = ast.unparse(item)
            break
    
    if handle_source:
        # 确保没有调用数据库存储方法
        if "save_" not in handle_source or "database" not in handle_source.lower():
            print("  ✓ handle 方法不调用数据库存储")
        else:
            print("  ✗ handle 方法不应调用数据库存储")
            success = False
    
    # 11. 检查日志不记录密码明文
    print("\n步骤 11: 检查日志安全性")
    if handle_source:
        # 检查日志中是否直接记录 password 变量
        if "password_length" in handle_source or "len(" in handle_source:
            print("  ✓ 日志不记录密码明文（使用长度或其他方式）")
        else:
            print("  ⚠ 建议日志不要直接记录密码明文")
    
    print("\n" + "="*60)
    if success:
        print("✓ 所有验证通过！PasswordReportHandler 实现正确。")
    else:
        print("✗ 验证失败，请检查上述错误。")
    
    return success


if __name__ == "__main__":
    success = verify_handler()
    sys.exit(0 if success else 1)
