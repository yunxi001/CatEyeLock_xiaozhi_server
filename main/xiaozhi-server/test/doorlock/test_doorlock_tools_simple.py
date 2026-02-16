"""
门锁AI工具函数简单测试（无外部依赖）

测试内容：
- 工具函数Schema验证
- 工具函数结构完整性
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.providers.doorlock.doorlock_tools import DoorlockTools


def test_tools_schema():
    """测试工具函数Schema"""
    print("=" * 60)
    print("测试1: 工具函数Schema验证")
    print("=" * 60)
    
    schema = DoorlockTools.get_tools_schema()
    
    # 验证Schema结构
    assert isinstance(schema, list), "Schema应该是列表"
    assert len(schema) == 4, f"应该有4个工具函数，实际有{len(schema)}个"
    
    # 验证每个工具的必需字段
    required_fields = ["name", "description", "parameters"]
    tool_names = []
    
    for tool in schema:
        for field in required_fields:
            assert field in tool, f"工具缺少必需字段: {field}"
        
        tool_names.append(tool['name'])
        print(f"✓ 工具函数: {tool['name']}")
        print(f"  描述: {tool['description'][:50]}...")
        print(f"  参数: {list(tool['parameters']['properties'].keys())}")
        print()
    
    # 验证工具名称
    expected_tools = [
        "enable_package_guard",
        "disable_package_guard",
        "update_package_baseline",
        "report_package_status"
    ]
    
    for expected in expected_tools:
        assert expected in tool_names, f"缺少工具函数: {expected}"
    
    print("✓ 工具函数Schema验证通过")
    return True


def main():
    """主测试函数"""
    print("开始门锁AI工具函数测试（简化版）")
    print()
    
    try:
        test_tools_schema()
        print()
        
        print("=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        print()
        print("测试总结:")
        print("✓ 工具函数可被VLLM正确识别（Schema验证通过）")
        print("✓ 工具函数定义完整（4个工具函数全部存在）")
        print("✓ 工具函数参数Schema正确（包含必需字段）")
        
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
