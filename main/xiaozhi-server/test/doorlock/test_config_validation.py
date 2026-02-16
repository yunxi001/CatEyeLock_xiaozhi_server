"""
配置文件格式验证测试

验证 doorlock_config.yaml 和 doorlock_prompts.yaml 的格式和必需字段
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from ruamel.yaml import YAML


def test_doorlock_config_format():
    """测试 doorlock_config.yaml 格式和必需字段"""
    print("=" * 60)
    print("测试 doorlock_config.yaml 格式")
    print("=" * 60)
    
    yaml = YAML()
    config_path = project_root / "config" / "doorlock_config.yaml"
    
    # 加载配置文件
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.load(f)
    
    print(f"✓ 配置文件加载成功: {config_path}")
    
    # 验证必需字段
    required_sections = {
        'mysql': ['host', 'port', 'user', 'password', 'database', 'pool_size'],
        'unified_mode': ['enabled', 'dialogue', 'guard', 'token_optimization'],
        'unified_mode.dialogue': ['max_rounds', 'timeout_seconds'],
        'unified_mode.guard': ['threat_detection', 'report_threshold'],
        'unified_mode.token_optimization': ['baseline_image_once', 'reuse_context'],
        'photo_cache': ['interval_seconds', 'max_cache_size'],
        'performance': ['max_token_usage_ratio', 'session_cleanup_delay', 'vllm_limits'],
        'performance.vllm_limits': [
            'model_context_limit',
            'max_input_tokens',
            'max_output_tokens',
            'max_image_tokens',
            'tokens_per_image',
            'input_warning_ratio',
            'total_warning_ratio'
        ]
    }
    
    errors = []
    
    for section_path, fields in required_sections.items():
        parts = section_path.split('.')
        current = config
        
        # 导航到嵌套节点
        for part in parts:
            if part not in current:
                errors.append(f"缺少配置节: {section_path}")
                break
            current = current[part]
        else:
            # 验证字段
            for field in fields:
                if field not in current:
                    errors.append(f"缺少字段: {section_path}.{field}")
    
    if errors:
        print("\n❌ 配置验证失败:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    print("✓ 所有必需字段存在")
    
    # 验证数值范围
    print("\n验证数值范围...")
    
    # unified_mode.dialogue
    dialogue = config['unified_mode']['dialogue']
    assert dialogue['max_rounds'] > 0, "max_rounds 必须大于 0"
    assert dialogue['timeout_seconds'] > 0, "timeout_seconds 必须大于 0"
    print(f"  ✓ dialogue.max_rounds = {dialogue['max_rounds']}")
    print(f"  ✓ dialogue.timeout_seconds = {dialogue['timeout_seconds']}")
    
    # photo_cache
    photo_cache = config['photo_cache']
    assert photo_cache['interval_seconds'] > 0, "interval_seconds 必须大于 0"
    assert photo_cache['max_cache_size'] > 0, "max_cache_size 必须大于 0"
    print(f"  ✓ photo_cache.interval_seconds = {photo_cache['interval_seconds']}")
    print(f"  ✓ photo_cache.max_cache_size = {photo_cache['max_cache_size']}")
    
    # performance.vllm_limits
    vllm_limits = config['performance']['vllm_limits']
    assert vllm_limits['model_context_limit'] > 0, "model_context_limit 必须大于 0"
    assert vllm_limits['max_input_tokens'] > 0, "max_input_tokens 必须大于 0"
    assert vllm_limits['max_output_tokens'] > 0, "max_output_tokens 必须大于 0"
    assert vllm_limits['max_image_tokens'] > 0, "max_image_tokens 必须大于 0"
    assert vllm_limits['tokens_per_image'] > 0, "tokens_per_image 必须大于 0"
    assert 0 < vllm_limits['input_warning_ratio'] <= 1, "input_warning_ratio 必须在 (0, 1] 范围内"
    assert 0 < vllm_limits['total_warning_ratio'] <= 1, "total_warning_ratio 必须在 (0, 1] 范围内"
    print(f"  ✓ vllm_limits.model_context_limit = {vllm_limits['model_context_limit']}")
    print(f"  ✓ vllm_limits.max_input_tokens = {vllm_limits['max_input_tokens']}")
    print(f"  ✓ vllm_limits.max_output_tokens = {vllm_limits['max_output_tokens']}")
    print(f"  ✓ vllm_limits.tokens_per_image = {vllm_limits['tokens_per_image']}")
    print(f"  ✓ vllm_limits.input_warning_ratio = {vllm_limits['input_warning_ratio']}")
    print(f"  ✓ vllm_limits.total_warning_ratio = {vllm_limits['total_warning_ratio']}")
    
    print("\n✓ 所有数值范围合理")
    print("\n✅ doorlock_config.yaml 验证通过")
    return True


def test_doorlock_prompts_format():
    """测试 doorlock_prompts.yaml 格式和必需字段"""
    print("\n" + "=" * 60)
    print("测试 doorlock_prompts.yaml 格式")
    print("=" * 60)
    
    yaml = YAML()
    prompts_path = project_root / "config" / "doorlock_prompts.yaml"
    
    # 加载提示词文件
    with open(prompts_path, 'r', encoding='utf-8') as f:
        prompts = yaml.load(f)
    
    print(f"✓ 提示词文件加载成功: {prompts_path}")
    
    # 验证必需的提示词字段
    required_prompts = [
        'core_role_and_style',
        'dialogue_tasks',
        'guard_tasks',
        'tools_guide',
        'final_package_check_prompt',
        'intent_summary_prompt'
    ]
    
    errors = []
    
    for prompt_name in required_prompts:
        if prompt_name not in prompts:
            errors.append(f"缺少提示词: {prompt_name}")
        elif not prompts[prompt_name] or not prompts[prompt_name].strip():
            errors.append(f"提示词为空: {prompt_name}")
    
    if errors:
        print("\n❌ 提示词验证失败:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    print("✓ 所有必需提示词存在")
    
    # 验证提示词内容长度
    print("\n验证提示词内容...")
    for prompt_name in required_prompts:
        content = prompts[prompt_name].strip()
        length = len(content)
        print(f"  ✓ {prompt_name}: {length} 字符")
        assert length > 0, f"{prompt_name} 不能为空"
    
    print("\n✅ doorlock_prompts.yaml 验证通过")
    return True


def main():
    """主测试函数"""
    try:
        # 测试配置文件
        config_ok = test_doorlock_config_format()
        
        # 测试提示词文件
        prompts_ok = test_doorlock_prompts_format()
        
        # 总结
        print("\n" + "=" * 60)
        print("验证总结")
        print("=" * 60)
        
        if config_ok and prompts_ok:
            print("✅ 所有配置文件验证通过")
            return 0
        else:
            print("❌ 配置文件验证失败")
            return 1
            
    except Exception as e:
        print(f"\n❌ 验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
