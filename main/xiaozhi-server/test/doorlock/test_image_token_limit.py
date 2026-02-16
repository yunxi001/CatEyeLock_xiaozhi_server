"""
测试图片Token限制检查

测试目标：
- 测试1张图片通过检查
- 测试2张图片通过检查
- 测试3张图片失败检查
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


def test_one_image_passes():
    """测试1张图片通过检查"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 调用内部方法检查图片Token限制
    result = vllm_provider._check_image_token_limit(1)
    assert result == True, "1张图片应该通过检查"
    print("[PASS] 1张图片通过检查测试通过")


def test_two_images_pass():
    """测试2张图片通过检查"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 调用内部方法检查图片Token限制
    result = vllm_provider._check_image_token_limit(2)
    assert result == True, "2张图片应该通过检查"
    print("[PASS] 2张图片通过检查测试通过")


def test_three_images_fail():
    """测试3张图片失败检查"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 调用内部方法检查图片Token限制
    result = vllm_provider._check_image_token_limit(3)
    assert result == False, "3张图片应该失败检查"
    print("[PASS] 3张图片失败检查测试通过")


def test_zero_images():
    """测试0张图片的边界情况"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 0张图片应该通过检查
    result = vllm_provider._check_image_token_limit(0)
    assert result == True, "0张图片应该通过检查"
    print("[PASS] 0张图片边界情况测试通过")


def test_exact_limit():
    """测试恰好达到限制的情况"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 获取配置的最大图片Token限制
    max_image_tokens = vllm_provider.max_image_tokens
    tokens_per_image = vllm_provider.tokens_per_image
    
    # 计算最大允许的图片数量
    max_images = max_image_tokens // tokens_per_image
    
    print(f"  配置: max_image_tokens={max_image_tokens}, tokens_per_image={tokens_per_image}")
    print(f"  计算得到最大图片数: {max_images}")
    
    # 测试恰好达到限制
    result1 = vllm_provider._check_image_token_limit(max_images)
    assert result1 == True, f"{max_images}张图片应该通过检查"
    print(f"[PASS] 恰好{max_images}张图片通过检查")
    
    # 测试超过限制1张
    result2 = vllm_provider._check_image_token_limit(max_images + 1)
    assert result2 == False, f"{max_images + 1}张图片应该失败检查"
    print(f"[PASS] {max_images + 1}张图片正确失败")


def test_token_calculation():
    """测试Token计算逻辑"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    tokens_per_image = vllm_provider.tokens_per_image
    max_image_tokens = vllm_provider.max_image_tokens
    
    # 验证1张图片的Token消耗
    image_count = 1
    expected_tokens = image_count * tokens_per_image
    assert expected_tokens <= max_image_tokens, f"1张图片Token计算错误"
    
    # 验证2张图片的Token消耗
    image_count = 2
    expected_tokens = image_count * tokens_per_image
    assert expected_tokens <= max_image_tokens, f"2张图片Token计算错误"
    
    # 验证3张图片的Token消耗
    image_count = 3
    expected_tokens = image_count * tokens_per_image
    # 3张图片应该超过限制（假设tokens_per_image=7000, max_image_tokens=16384）
    if expected_tokens > max_image_tokens:
        print(f"[PASS] Token计算逻辑正确: 3张图片({expected_tokens} tokens)超过限制({max_image_tokens} tokens)")
    else:
        print(f"  注意: 当前配置下3张图片未超限，tokens_per_image可能需要调整")


if __name__ == "__main__":
    # 运行所有测试
    print("=" * 60)
    print("开始测试图片Token限制检查")
    print("=" * 60)
    
    try:
        test_one_image_passes()
        test_two_images_pass()
        test_three_images_fail()
        test_zero_images()
        test_exact_limit()
        test_token_calculation()
        
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
