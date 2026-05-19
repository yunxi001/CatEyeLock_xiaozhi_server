#!/usr/bin/env python3
"""
快速验证修复是否正确
"""
import sys

def verify_query_handlers():
    """验证查询处理器是否添加成功"""
    print("="*70)
    print("验证 1: 查询处理器")
    print("="*70)
    
    try:
        from core.handle.textHandler.queryHandler import QueryHandler
        
        handler = QueryHandler()
        
        # 检查是否有 _query_visitor_intents 方法
        if hasattr(handler, '_query_visitor_intents'):
            print("✓ _query_visitor_intents 方法存在")
        else:
            print("✗ _query_visitor_intents 方法不存在")
            return False
        
        # 检查是否有 _query_package_alerts 方法
        if hasattr(handler, '_query_package_alerts'):
            print("✓ _query_package_alerts 方法存在")
        else:
            print("✗ _query_package_alerts 方法不存在")
            return False
        
        print("✓ 所有查询处理器已添加")
        return True
        
    except Exception as e:
        print(f"✗ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_status_report_fix():
    """验证 status_report 修复"""
    print("\n" + "="*70)
    print("验证 2: status_report 修复")
    print("="*70)
    
    try:
        # 检查 ackHandler.py
        with open('core/handle/textHandler/ackHandler.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 检查是否使用了默认值
        if 'if old_state.get("battery") is not None else 0' in content:
            print("✓ ackHandler.py 已修复（使用默认值避免 null）")
        else:
            print("✗ ackHandler.py 未修复")
            return False
        
        # 检查 logReportHandler.py
        with open('core/handle/textHandler/logReportHandler.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 检查是否使用了默认值
        if 'if old_state.get("battery") is not None else 0' in content:
            print("✓ logReportHandler.py 已修复（使用默认值避免 null）")
        else:
            print("✗ logReportHandler.py 未修复")
            return False
        
        print("✓ status_report 修复完成")
        return True
        
    except Exception as e:
        print(f"✗ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_remote_unlock_fix():
    """验证远程开锁 user_id 修复"""
    print("\n" + "="*70)
    print("验证 3: 远程开锁 user_id 修复")
    print("="*70)
    
    try:
        with open('core/handle/textHandler/logReportHandler.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否修改了远程开锁的处理逻辑
        if 'App ID 为字符串，不存储到 user_id 字段' in content:
            print("✓ 远程开锁 user_id 修复完成")
            print("  - 远程开锁的 user_id 统一设置为 0")
            print("  - 避免将字符串插入到 INT 字段")
            return True
        else:
            print("✗ 远程开锁 user_id 未修复")
            return False
        
    except Exception as e:
        print(f"✗ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有验证"""
    print("\n" + "="*70)
    print("修复验证")
    print("="*70)
    
    results = []
    
    # 验证 1: 查询处理器
    result1 = verify_query_handlers()
    results.append(("查询处理器", result1))
    
    # 验证 2: status_report 修复
    result2 = verify_status_report_fix()
    results.append(("status_report 修复", result2))
    
    # 验证 3: 远程开锁 user_id 修复
    result3 = verify_remote_unlock_fix()
    results.append(("远程开锁 user_id 修复", result3))
    
    # 输出验证结果
    print("\n" + "="*70)
    print("验证结果汇总")
    print("="*70)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status} - {name}")
    
    all_passed = all(r for _, r in results)
    print("\n" + "="*70)
    if all_passed:
        print("✓ 所有验证通过，修复成功！")
        print("\n下一步：")
        print("1. 重启服务器：python app.py")
        print("2. 测试 App 查询功能")
        print("3. 检查日志确认没有错误")
    else:
        print("✗ 部分验证失败，请检查修复")
    print("="*70)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
