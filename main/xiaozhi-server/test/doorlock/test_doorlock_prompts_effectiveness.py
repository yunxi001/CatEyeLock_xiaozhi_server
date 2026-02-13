"""
测试门锁AI提示词有效性

验证提示词在实际场景中的表现：
1. 提示词格式正确
2. 工具调用说明清晰
3. 示例场景覆盖完整
4. 欢迎词模板可用
"""
import yaml
from pathlib import Path
from loguru import logger

TAG = "PromptEffectiveness"


def test_prompt_loading():
    """测试提示词加载"""
    logger.bind(tag=TAG).info("测试1: 提示词加载")
    
    config_path = Path("config/doorlock_prompts.yaml")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    assert 'intent_recognition_prompt' in config
    assert 'package_guard_prompt' in config
    assert 'welcome_templates' in config
    
    logger.bind(tag=TAG).success("✓ 提示词加载成功")
    return config


def test_intent_recognition_prompt(config):
    """测试意图识别提示词"""
    logger.bind(tag=TAG).info("测试2: 意图识别提示词有效性")
    
    prompt = config['intent_recognition_prompt']
    
    # 检查关键部分
    assert '系统角色' in prompt, "缺少系统角色定义"
    assert '职责说明' in prompt, "缺少职责说明"
    assert '对话风格' in prompt, "缺少对话风格指南"
    assert '对话策略' in prompt, "缺少对话策略"
    assert '工具调用' in prompt, "缺少工具调用说明"
    
    # 检查5个工具函数
    tools = [
        'enable_package_guard',
        'disable_package_guard',
        'update_package_baseline',
        'report_package_status',
        'report_visitor_intent'
    ]
    
    for tool in tools:
        assert tool in prompt, f"缺少工具函数: {tool}"
    
    # 检查示例场景（至少3个）
    scenario_count = prompt.count('场景')
    assert scenario_count >= 3, f"示例场景不足，当前: {scenario_count}"
    
    logger.bind(tag=TAG).success(f"✓ 意图识别提示词有效（包含{scenario_count}个示例场景）")


def test_package_guard_prompt(config):
    """测试看护模式提示词"""
    logger.bind(tag=TAG).info("测试3: 看护模式提示词有效性")
    
    prompt = config['package_guard_prompt']
    
    # 检查威胁等级标准
    assert '低威胁' in prompt, "缺少低威胁标准"
    assert '中威胁' in prompt, "缺少中威胁标准"
    assert '高威胁' in prompt, "缺少高威胁标准"
    
    # 检查主人判断规则
    assert 'is_owner=true' in prompt, "缺少主人判断规则"
    assert '主人取走快递' in prompt, "缺少主人取件说明"
    assert '非主人' in prompt, "缺少非主人判断"
    
    # 检查行为类型
    actions = ['taking', 'searching', 'damaging', 'normal', 'passing']
    for action in actions:
        assert action in prompt, f"缺少行为类型: {action}"
    
    # 检查工具调用说明
    tools = [
        'report_package_status',
        'update_package_baseline',
        'enable_package_guard',
        'disable_package_guard'
    ]
    
    for tool in tools:
        assert tool in prompt, f"缺少工具函数: {tool}"
    
    # 检查示例场景（至少5个）
    scenario_count = prompt.count('场景')
    assert scenario_count >= 5, f"示例场景不足，当前: {scenario_count}"
    
    logger.bind(tag=TAG).success(f"✓ 看护模式提示词有效（包含{scenario_count}个示例场景）")


def test_welcome_templates(config):
    """测试欢迎词模板"""
    logger.bind(tag=TAG).info("测试4: 欢迎词模板有效性")
    
    templates = config['welcome_templates']
    
    # 检查至少有3个风格
    assert len(templates) >= 3, f"欢迎词模板不足，当前: {len(templates)}"
    
    # 检查必需的风格
    template_names = [t['name'] for t in templates]
    required_styles = ['温馨家庭', '简洁风格', '正式风格']
    
    for style in required_styles:
        assert style in template_names, f"缺少必需风格: {style}"
    
    # 检查占位符
    placeholder_count = 0
    for template in templates:
        for key, value in template.items():
            if key != 'name' and isinstance(value, str):
                if '{name}' in value:
                    placeholder_count += 1
    
    assert placeholder_count > 0, "欢迎词模板缺少{name}占位符"
    
    # 检查长度（<20字）
    max_length = 20
    for template in templates:
        for key, value in template.items():
            if key != 'name' and isinstance(value, str):
                test_greeting = value.replace('{name}', '张三')
                assert len(test_greeting) <= max_length, \
                    f"欢迎词过长: {template['name']}.{key} = {len(test_greeting)}字"
    
    logger.bind(tag=TAG).success(f"✓ 欢迎词模板有效（共{len(templates)}个风格）")


def test_default_greeting(config):
    """测试默认欢迎词"""
    logger.bind(tag=TAG).info("测试5: 默认欢迎词有效性")
    
    default_greeting = config['default_greeting']
    
    # 检查所有时段
    required_slots = ['morning', 'afternoon', 'evening', 'night', 'default']
    for slot in required_slots:
        assert slot in default_greeting, f"缺少时段: {slot}"
        assert len(default_greeting[slot]) > 0, f"时段{slot}的欢迎词为空"
    
    logger.bind(tag=TAG).success("✓ 默认欢迎词有效")


def test_tool_schema_consistency():
    """测试工具Schema一致性"""
    logger.bind(tag=TAG).info("测试6: 工具Schema一致性")
    
    # 导入工具类
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    
    from core.providers.doorlock.doorlock_tools import DoorlockTools
    
    # 获取工具Schema
    tools_schema = DoorlockTools.get_tools_schema()
    
    # 检查5个工具都存在
    tool_names = [tool['name'] for tool in tools_schema]
    expected_tools = [
        'enable_package_guard',
        'disable_package_guard',
        'update_package_baseline',
        'report_package_status',
        'report_visitor_intent'
    ]
    
    for tool in expected_tools:
        assert tool in tool_names, f"工具Schema缺少: {tool}"
    
    # 检查每个工具都有完整的定义
    for tool in tools_schema:
        assert 'name' in tool, f"工具{tool}缺少name"
        assert 'description' in tool, f"工具{tool}缺少description"
        assert 'parameters' in tool, f"工具{tool}缺少parameters"
        assert 'type' in tool['parameters'], f"工具{tool}的parameters缺少type"
        assert 'properties' in tool['parameters'], f"工具{tool}的parameters缺少properties"
        assert 'required' in tool['parameters'], f"工具{tool}的parameters缺少required"
    
    logger.bind(tag=TAG).success(f"✓ 工具Schema一致性验证通过（共{len(tools_schema)}个工具）")


def run_all_tests():
    """运行所有测试"""
    logger.bind(tag=TAG).info("=" * 60)
    logger.bind(tag=TAG).info("开始测试门锁AI提示词有效性")
    logger.bind(tag=TAG).info("=" * 60)
    
    try:
        # 测试1: 加载提示词
        config = test_prompt_loading()
        
        # 测试2: 意图识别提示词
        test_intent_recognition_prompt(config)
        
        # 测试3: 看护模式提示词
        test_package_guard_prompt(config)
        
        # 测试4: 欢迎词模板
        test_welcome_templates(config)
        
        # 测试5: 默认欢迎词
        test_default_greeting(config)
        
        # 测试6: 工具Schema一致性
        test_tool_schema_consistency()
        
        # 所有测试通过
        logger.bind(tag=TAG).info("=" * 60)
        logger.bind(tag=TAG).success("所有测试通过！提示词配置有效且可用")
        logger.bind(tag=TAG).info("=" * 60)
        
        return True
        
    except AssertionError as e:
        logger.bind(tag=TAG).error(f"测试失败: {e}")
        return False
    except Exception as e:
        logger.bind(tag=TAG).error(f"测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    
    success = run_all_tests()
    sys.exit(0 if success else 1)
