"""
验证工具函数Schema的正确性

验证内容：
1. 工具函数数量正确（4个）
2. 每个工具函数的Schema完整
3. 参数定义符合设计文档要求
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.providers.doorlock.doorlock_tools import DoorlockTools


def verify_tools_schema():
    """验证工具函数Schema"""
    print("=" * 70)
    print("验证工具函数Schema")
    print("=" * 70)
    
    schema = DoorlockTools.get_tools_schema()
    
    # 1. 验证工具数量
    print(f"\n1. 工具函数数量: {len(schema)}")
    assert len(schema) == 4, f"应该有4个工具函数，实际有{len(schema)}个"
    print("   ✓ 工具数量正确（4个）")
    
    # 2. 验证工具名称
    tool_names = [tool['name'] for tool in schema]
    expected_tools = [
        "enable_package_guard",
        "disable_package_guard",
        "update_package_baseline",
        "report_package_status"
    ]
    
    print("\n2. 工具函数列表:")
    for tool_name in tool_names:
        assert tool_name in expected_tools, f"发现未预期的工具: {tool_name}"
        print(f"   ✓ {tool_name}")
    
    # 确保没有report_visitor_intent
    assert "report_visitor_intent" not in tool_names, "不应该包含report_visitor_intent工具"
    print("   ✓ 已移除report_visitor_intent工具")
    
    # 3. 验证每个工具的Schema
    print("\n3. 验证工具Schema详情:")
    
    for tool in schema:
        tool_name = tool['name']
        print(f"\n   工具: {tool_name}")
        
        # 验证必需字段
        assert 'name' in tool, f"{tool_name}缺少name字段"
        assert 'description' in tool, f"{tool_name}缺少description字段"
        assert 'parameters' in tool, f"{tool_name}缺少parameters字段"
        print(f"     ✓ 包含必需字段")
        
        # 验证parameters结构
        params = tool['parameters']
        assert 'type' in params, f"{tool_name}的parameters缺少type字段"
        assert params['type'] == 'object', f"{tool_name}的parameters.type应该是object"
        assert 'properties' in params, f"{tool_name}的parameters缺少properties字段"
        assert 'required' in params, f"{tool_name}的parameters缺少required字段"
        print(f"     ✓ parameters结构正确")
        
        # 验证具体参数
        properties = params['properties']
        required = params['required']
        
        if tool_name == "enable_package_guard":
            assert 'device_id' in properties, "enable_package_guard缺少device_id参数"
            assert 'reason' in properties, "enable_package_guard缺少reason参数"
            assert 'device_id' in required, "device_id应该是必需参数"
            assert 'reason' in required, "reason应该是必需参数"
            print(f"     ✓ 参数定义正确: device_id, reason")
        
        elif tool_name == "disable_package_guard":
            assert 'device_id' in properties, "disable_package_guard缺少device_id参数"
            assert 'reason' in properties, "disable_package_guard缺少reason参数"
            assert 'device_id' in required, "device_id应该是必需参数"
            assert 'reason' in required, "reason应该是必需参数"
            print(f"     ✓ 参数定义正确: device_id, reason")
        
        elif tool_name == "update_package_baseline":
            assert 'device_id' in properties, "update_package_baseline缺少device_id参数"
            assert 'device_id' in required, "device_id应该是必需参数"
            print(f"     ✓ 参数定义正确: device_id")
        
        elif tool_name == "report_package_status":
            assert 'device_id' in properties, "report_package_status缺少device_id参数"
            assert 'session_id' in properties, "report_package_status缺少session_id参数"
            assert 'action' in properties, "report_package_status缺少action参数"
            assert 'threat_level' in properties, "report_package_status缺少threat_level参数"
            assert 'description' in properties, "report_package_status缺少description参数"
            
            # 验证枚举值
            action_enum = properties['action'].get('enum', [])
            expected_actions = ["taking", "searching", "damaging", "normal", "passing"]
            assert set(action_enum) == set(expected_actions), f"action枚举值不正确: {action_enum}"
            
            threat_enum = properties['threat_level'].get('enum', [])
            expected_threats = ["low", "medium", "high"]
            assert set(threat_enum) == set(expected_threats), f"threat_level枚举值不正确: {threat_enum}"
            
            print(f"     ✓ 参数定义正确: device_id, session_id, action, threat_level, description")
            print(f"     ✓ 枚举值正确")
    
    print("\n" + "=" * 70)
    print("✓ 所有验证通过！")
    print("=" * 70)
    print("\n验证总结:")
    print("  ✓ 工具函数数量正确（4个）")
    print("  ✓ 已移除report_visitor_intent工具")
    print("  ✓ enable_package_guard参数正确（device_id, reason）")
    print("  ✓ disable_package_guard参数正确（device_id, reason）")
    print("  ✓ update_package_baseline参数正确（device_id）")
    print("  ✓ report_package_status参数正确（device_id, session_id, action, threat_level, description）")
    print("  ✓ 所有枚举值定义正确")
    
    return True


if __name__ == "__main__":
    try:
        verify_tools_schema()
        sys.exit(0)
    except Exception as e:
        print(f"\n验证失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
