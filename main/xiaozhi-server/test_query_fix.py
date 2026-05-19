"""
App 查询功能修复验证脚本

用于验证 queryHandler.py 的修改是否正确
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """测试导入是否正常"""
    print("=" * 60)
    print("测试 1: 验证模块导入")
    print("=" * 60)
    
    try:
        from core.handle.textHandler.queryHandler import QueryHandler, _get_ai_database, _get_base_database
        print("✅ QueryHandler 导入成功")
        print("✅ _get_ai_database 函数存在")
        print("✅ _get_base_database 函数存在")
        return True
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False


def test_handler_registration():
    """测试查询处理器是否正确注册"""
    print("\n" + "=" * 60)
    print("测试 2: 验证查询处理器注册")
    print("=" * 60)
    
    try:
        from core.handle.textHandler.queryHandler import QueryHandler
        
        handler = QueryHandler()
        
        # 检查是否有 _query_doorlock_users 方法
        if hasattr(handler, '_query_doorlock_users'):
            print("✅ _query_doorlock_users 方法存在")
        else:
            print("❌ _query_doorlock_users 方法不存在")
            return False
        
        # 检查其他查询方法
        required_methods = [
            '_query_status',
            '_query_status_history',
            '_query_events',
            '_query_unlock_logs',
            '_query_media_files',
            '_query_password',
            '_query_visitor_intents',
            '_query_package_alerts',
            '_query_doorlock_users'
        ]
        
        for method in required_methods:
            if hasattr(handler, method):
                print(f"✅ {method} 方法存在")
            else:
                print(f"❌ {method} 方法不存在")
                return False
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_database_classes():
    """测试数据库类是否可用"""
    print("\n" + "=" * 60)
    print("测试 3: 验证数据库类")
    print("=" * 60)
    
    try:
        from core.providers.doorlock.database import Database
        from core.providers.doorlock.doorlock_database import DoorlockDatabase
        
        print("✅ Database 类导入成功")
        print("✅ DoorlockDatabase 类导入成功")
        
        # 检查 Database 类是否有必要的方法
        required_methods = [
            'get_doorlock_users',
            'get_device_password',
            'get_events',
            'get_unlock_logs',
            'get_status_history',
            'get_media_files'
        ]
        
        for method in required_methods:
            if hasattr(Database, method):
                print(f"✅ Database.{method} 方法存在")
            else:
                print(f"❌ Database.{method} 方法不存在")
                return False
        
        # 检查 DoorlockDatabase 类是否有 AI 功能方法
        ai_methods = [
            'get_visitor_intents',
            'get_package_alerts'
        ]
        
        for method in ai_methods:
            if hasattr(DoorlockDatabase, method):
                print(f"✅ DoorlockDatabase.{method} 方法存在")
            else:
                print(f"❌ DoorlockDatabase.{method} 方法不存在")
                return False
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("App 查询功能修复验证")
    print("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(("模块导入", test_imports()))
    results.append(("查询处理器注册", test_handler_registration()))
    results.append(("数据库类验证", test_database_classes()))
    
    # 输出总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！修改验证成功。")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查修改。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
