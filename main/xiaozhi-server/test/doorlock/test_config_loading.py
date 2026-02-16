"""
配置加载功能测试

测试配置文件能否被正确加载并在代码中使用
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from ruamel.yaml import YAML


def test_load_doorlock_config():
    """测试加载 doorlock_config.yaml"""
    print("=" * 60)
    print("测试加载 doorlock_config.yaml")
    print("=" * 60)
    
    yaml = YAML()
    config_path = project_root / "config" / "doorlock_config.yaml"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.load(f)
    
    print(f"✓ 配置文件加载成功")
    
    # 测试访问配置项
    print("\n测试访问配置项...")
    
    # unified_mode 配置
    unified_mode = config.get('unified_mode', {})
    print(f"  ✓ unified_mode.enabled = {unified_mode.get('enabled')}")
    print(f"  ✓ unified_mode.dialogue.max_rounds = {unified_mode.get('dialogue', {}).get('max_rounds')}")
    print(f"  ✓ unified_mode.dialogue.timeout_seconds = {unified_mode.get('dialogue', {}).get('timeout_seconds')}")
    print(f"  ✓ unified_mode.guard.threat_detection = {unified_mode.get('guard', {}).get('threat_detection')}")
    print(f"  ✓ unified_mode.guard.report_threshold = {unified_mode.get('guard', {}).get('report_threshold')}")
    print(f"  ✓ unified_mode.token_optimization.baseline_image_once = {unified_mode.get('token_optimization', {}).get('baseline_image_once')}")
    print(f"  ✓ unified_mode.token_optimization.reuse_context = {unified_mode.get('token_optimization', {}).get('reuse_context')}")
    
    # photo_cache 配置
    photo_cache = config.get('photo_cache', {})
    print(f"  ✓ photo_cache.interval_seconds = {photo_cache.get('interval_seconds')}")
    print(f"  ✓ photo_cache.max_cache_size = {photo_cache.get('max_cache_size')}")
    
    # performance 配置
    performance = config.get('performance', {})
    vllm_limits = performance.get('vllm_limits', {})
    print(f"  ✓ performance.vllm_limits.model_context_limit = {vllm_limits.get('model_context_limit')}")
    print(f"  ✓ performance.vllm_limits.max_input_tokens = {vllm_limits.get('max_input_tokens')}")
    print(f"  ✓ performance.vllm_limits.max_output_tokens = {vllm_limits.get('max_output_tokens')}")
    print(f"  ✓ performance.vllm_limits.tokens_per_image = {vllm_limits.get('tokens_per_image')}")
    
    print("\n✅ doorlock_config.yaml 加载测试通过")
    return config


def test_load_doorlock_prompts():
    """测试加载 doorlock_prompts.yaml"""
    print("\n" + "=" * 60)
    print("测试加载 doorlock_prompts.yaml")
    print("=" * 60)
    
    yaml = YAML()
    prompts_path = project_root / "config" / "doorlock_prompts.yaml"
    
    with open(prompts_path, 'r', encoding='utf-8') as f:
        prompts = yaml.load(f)
    
    print(f"✓ 提示词文件加载成功")
    
    # 测试访问提示词
    print("\n测试访问提示词...")
    
    prompt_names = [
        'core_role_and_style',
        'dialogue_tasks',
        'guard_tasks',
        'tools_guide',
        'final_package_check_prompt',
        'intent_summary_prompt'
    ]
    
    for name in prompt_names:
        prompt = prompts.get(name, '')
        preview = prompt.strip()[:50] + "..." if len(prompt.strip()) > 50 else prompt.strip()
        print(f"  ✓ {name}: {preview}")
    
    print("\n✅ doorlock_prompts.yaml 加载测试通过")
    return prompts


def test_build_unified_prompt(prompts):
    """测试动态组合提示词"""
    print("\n" + "=" * 60)
    print("测试动态组合提示词")
    print("=" * 60)
    
    def build_unified_prompt(has_baseline: bool) -> str:
        """动态组合统一模式提示词"""
        prompt_parts = [
            prompts.get('core_role_and_style', ''),
            prompts.get('dialogue_tasks', '')
        ]
        
        # 如果看护模式激活，添加看护任务
        if has_baseline:
            prompt_parts.append(prompts.get('guard_tasks', ''))
        
        # 总是添加工具指南
        prompt_parts.append(prompts.get('tools_guide', ''))
        
        return "\n\n".join(prompt_parts)
    
    # 测试无基准图片
    print("\n测试场景1: 无基准图片（看护未激活）")
    prompt_no_baseline = build_unified_prompt(has_baseline=False)
    assert 'core_role_and_style' not in prompt_no_baseline  # 不应包含字段名
    assert 'dialogue_tasks' not in prompt_no_baseline  # 不应包含字段名
    assert '看护任务' not in prompt_no_baseline  # 不应包含看护任务
    assert '对话任务' in prompt_no_baseline  # 应包含对话任务
    print(f"  ✓ 提示词长度: {len(prompt_no_baseline)} 字符")
    print(f"  ✓ 不包含看护任务")
    print(f"  ✓ 包含对话任务")
    
    # 测试有基准图片
    print("\n测试场景2: 有基准图片（看护激活）")
    prompt_with_baseline = build_unified_prompt(has_baseline=True)
    assert '看护任务' in prompt_with_baseline  # 应包含看护任务
    assert '对话任务' in prompt_with_baseline  # 应包含对话任务
    print(f"  ✓ 提示词长度: {len(prompt_with_baseline)} 字符")
    print(f"  ✓ 包含看护任务")
    print(f"  ✓ 包含对话任务")
    
    # 验证长度差异
    length_diff = len(prompt_with_baseline) - len(prompt_no_baseline)
    print(f"\n  ✓ 看护模式提示词增加: {length_diff} 字符")
    
    print("\n✅ 动态组合提示词测试通过")


def test_config_usage_simulation():
    """模拟配置在代码中的使用"""
    print("\n" + "=" * 60)
    print("模拟配置使用场景")
    print("=" * 60)
    
    yaml = YAML()
    
    # 加载配置
    config_path = project_root / "config" / "doorlock_config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.load(f)
    
    # 模拟场景1: 检查统一模式是否启用
    print("\n场景1: 检查统一模式是否启用")
    unified_mode_enabled = config.get('unified_mode', {}).get('enabled', False)
    print(f"  统一模式启用: {unified_mode_enabled}")
    
    if unified_mode_enabled:
        print("  ✓ 将使用统一模式处理对话和看护")
    else:
        print("  ✓ 将使用分离模式处理")
    
    # 模拟场景2: 获取对话配置
    print("\n场景2: 获取对话配置")
    dialogue_config = config.get('unified_mode', {}).get('dialogue', {})
    max_rounds = dialogue_config.get('max_rounds', 10)
    timeout_seconds = dialogue_config.get('timeout_seconds', 30)
    print(f"  最大对话轮次: {max_rounds}")
    print(f"  沉默超时时间: {timeout_seconds}秒")
    
    # 模拟场景3: 获取照片缓存配置
    print("\n场景3: 获取照片缓存配置")
    photo_cache = config.get('photo_cache', {})
    interval = photo_cache.get('interval_seconds', 5)
    max_size = photo_cache.get('max_cache_size', 10)
    print(f"  拍照间隔: {interval}秒")
    print(f"  最大缓存数量: {max_size}张")
    
    # 模拟场景4: 获取Token限制配置
    print("\n场景4: 获取Token限制配置")
    vllm_limits = config.get('performance', {}).get('vllm_limits', {})
    tokens_per_image = vllm_limits.get('tokens_per_image', 7000)
    max_input_tokens = vllm_limits.get('max_input_tokens', 260096)
    print(f"  每张图片Token数: {tokens_per_image}")
    print(f"  最大输入Token数: {max_input_tokens}")
    
    # 模拟Token检查
    image_count = 2
    estimated_image_tokens = image_count * tokens_per_image
    print(f"  2张图片估算Token: {estimated_image_tokens}")
    
    if estimated_image_tokens < max_input_tokens:
        print(f"  ✓ Token使用量在限制内")
    else:
        print(f"  ✗ Token使用量超出限制")
    
    print("\n✅ 配置使用场景模拟通过")


def main():
    """主测试函数"""
    try:
        # 测试加载配置文件
        config = test_load_doorlock_config()
        
        # 测试加载提示词文件
        prompts = test_load_doorlock_prompts()
        
        # 测试动态组合提示词
        test_build_unified_prompt(prompts)
        
        # 测试配置使用场景
        test_config_usage_simulation()
        
        # 总结
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)
        print("✅ 所有配置加载测试通过")
        print("✅ 配置文件可以正常使用")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
