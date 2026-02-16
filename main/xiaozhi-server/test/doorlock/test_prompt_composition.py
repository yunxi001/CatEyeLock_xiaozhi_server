"""
测试提示词动态组合功能

测试目标：
- 测试无基准图片时的提示词组合
- 测试有基准图片时的提示词组合
- 验证看护任务提示词正确添加
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.providers.vllm.doorlock_vllm import DoorlockVLLMProvider
from loguru import logger


def get_mock_config():
    """模拟配置"""
    return {
        "selected_module": {
            "VLLM": "qwen2_vl"
        },
        "VLLM": {
            "qwen2_vl": {
                "model_name": "Qwen/Qwen2-VL-7B-Instruct",
                "api_key": "test-key",
                "base_url": "http://localhost:8000/v1",
                "max_tokens": 32768,
                "temperature": 0.7,
                "top_p": 1.0
            }
        }
    }


def get_vllm_provider():
    """创建VLLM提供者实例"""
    return DoorlockVLLMProvider(get_mock_config(), logger)


def test_prompt_without_baseline():
    """测试无基准图片时的提示词组合"""
    vllm_provider = get_vllm_provider()
    
    # 调用内部方法构建提示词
    prompt = vllm_provider._build_unified_prompt(has_baseline=False)
    
    # 验证包含核心角色和风格
    assert "系统角色" in prompt or "核心角色" in prompt or "AI门卫助手" in prompt
    
    # 验证包含对话任务
    assert "对话任务" in prompt or "来访目的" in prompt
    
    # 验证包含工具指南
    assert "工具" in prompt or "enable_package_guard" in prompt
    
    # 验证不包含看护任务
    assert "看护任务" not in prompt
    assert "监控" not in prompt or "不要在对话中提及监控功能" not in prompt
    
    print("[PASS] 无基准图片时的提示词组合测试通过")


def test_prompt_with_baseline():
    """测试有基准图片时的提示词组合"""
    vllm_provider = get_vllm_provider()
    
    # 调用内部方法构建提示词
    prompt = vllm_provider._build_unified_prompt(has_baseline=True)
    
    # 验证包含核心角色和风格
    assert "系统角色" in prompt or "核心角色" in prompt or "AI门卫助手" in prompt
    
    # 验证包含对话任务
    assert "对话任务" in prompt or "来访目的" in prompt
    
    # 验证包含工具指南
    assert "工具" in prompt or "enable_package_guard" in prompt
    
    # 验证包含看护任务
    assert "看护任务" in prompt
    
    # 验证看护任务的关键内容
    assert "监控" in prompt or "快递" in prompt
    assert "威胁等级" in prompt or "threat_level" in prompt or "low" in prompt
    
    print("[PASS] 有基准图片时的提示词组合测试通过")


def test_guard_tasks_correctly_added():
    """验证看护任务提示词正确添加"""
    vllm_provider = get_vllm_provider()
    
    # 获取两种模式的提示词
    prompt_without_guard = vllm_provider._build_unified_prompt(has_baseline=False)
    prompt_with_guard = vllm_provider._build_unified_prompt(has_baseline=True)
    
    # 验证有基准图片时的提示词更长（包含看护任务）
    assert len(prompt_with_guard) > len(prompt_without_guard)
    
    # 验证看护任务的关键词只在有基准图片时出现
    guard_keywords = ["看护任务", "report_package_status", "威胁等级"]
    
    # 至少有一个看护关键词在有基准图片的提示词中
    has_guard_keyword = any(keyword in prompt_with_guard for keyword in guard_keywords)
    assert has_guard_keyword, "有基准图片时应包含看护任务关键词"
    
    # 验证看护任务的具体内容
    if "看护任务" in prompt_with_guard:
        # 提取看护任务部分
        guard_section_start = prompt_with_guard.find("看护任务")
        guard_section = prompt_with_guard[guard_section_start:guard_section_start + 500]
        
        # 验证包含关键指导内容
        assert "后台任务" in guard_section or "不要在对话中提及" in guard_section
    
    print("[PASS] 看护任务提示词正确添加测试通过")


def test_prompt_structure_consistency():
    """测试提示词结构一致性"""
    vllm_provider = get_vllm_provider()
    
    # 多次调用应返回相同的结果
    prompt1 = vllm_provider._build_unified_prompt(has_baseline=True)
    prompt2 = vllm_provider._build_unified_prompt(has_baseline=True)
    
    assert prompt1 == prompt2, "相同参数应返回相同的提示词"
    
    prompt3 = vllm_provider._build_unified_prompt(has_baseline=False)
    prompt4 = vllm_provider._build_unified_prompt(has_baseline=False)
    
    assert prompt3 == prompt4, "相同参数应返回相同的提示词"
    
    print("[PASS] 提示词结构一致性测试通过")


if __name__ == "__main__":
    # 运行所有测试
    print("=" * 60)
    print("开始测试提示词动态组合功能")
    print("=" * 60)
    
    try:
        test_prompt_without_baseline()
        test_prompt_with_baseline()
        test_guard_tasks_correctly_added()
        test_prompt_structure_consistency()
        
        print("\n" + "=" * 60)
        print("[PASS] 所有测试通过！")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n[FAIL] 测试异常: {e}")
        import traceback
        traceback.print_exc()
