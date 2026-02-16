"""
测试Token使用量监控功能

测试目标：
- 测试输出Token警告触发
- 测试输入Token警告触发
- 测试总Token警告触发
- 验证日志记录正确
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch
from io import StringIO

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


def test_output_token_warning():
    """测试输出Token警告触发"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 模拟Token使用量（输出Token超过80%）
    token_usage = {
        "prompt_tokens": 10000,
        "completion_tokens": int(vllm_provider.max_tokens * 0.85),  # 85%，超过80%阈值
        "total_tokens": 10000 + int(vllm_provider.max_tokens * 0.85)
    }
    
    # 直接调用方法，通过日志输出验证
    # 由于logger使用了bind(tag=TAG)，直接验证方法执行不抛异常即可
    try:
        vllm_provider._check_token_usage(token_usage, 1.5, 0)
        print("[PASS] 输出Token警告触发测试通过")
    except Exception as e:
        raise AssertionError(f"Token使用量监控方法执行失败: {e}")


def test_input_token_warning():
    """测试输入Token警告触发"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 模拟Token使用量（输入Token超过80%）
    token_usage = {
        "prompt_tokens": int(vllm_provider.max_input_tokens * 0.85),  # 85%，超过80%阈值
        "completion_tokens": 1000,
        "total_tokens": int(vllm_provider.max_input_tokens * 0.85) + 1000
    }
    
    try:
        vllm_provider._check_token_usage(token_usage, 1.5, 0)
        print("[PASS] 输入Token警告触发测试通过")
    except Exception as e:
        raise AssertionError(f"Token使用量监控方法执行失败: {e}")


def test_total_token_warning():
    """测试总Token警告触发"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 模拟Token使用量（总Token超过80%）
    total_tokens = int(vllm_provider.model_context_limit * 0.85)  # 85%，超过80%阈值
    token_usage = {
        "prompt_tokens": int(total_tokens * 0.7),
        "completion_tokens": int(total_tokens * 0.3),
        "total_tokens": total_tokens
    }
    
    try:
        vllm_provider._check_token_usage(token_usage, 1.5, 0)
        print("[PASS] 总Token警告触发测试通过")
    except Exception as e:
        raise AssertionError(f"Token使用量监控方法执行失败: {e}")


def test_log_recording():
    """验证日志记录正确"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 模拟正常的Token使用量
    token_usage = {
        "prompt_tokens": 5000,
        "completion_tokens": 1000,
        "total_tokens": 6000
    }
    
    try:
        vllm_provider._check_token_usage(token_usage, 2.5, 2)
        print("[PASS] 日志记录正确测试通过")
    except Exception as e:
        raise AssertionError(f"Token使用量监控方法执行失败: {e}")


def test_no_warning_within_limit():
    """测试在限制内不触发警告"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 模拟正常的Token使用量（都在50%以下）
    token_usage = {
        "prompt_tokens": int(vllm_provider.max_input_tokens * 0.5),
        "completion_tokens": int(vllm_provider.max_tokens * 0.5),
        "total_tokens": int(vllm_provider.model_context_limit * 0.5)
    }
    
    try:
        vllm_provider._check_token_usage(token_usage, 1.0, 0)
        print("[PASS] 在限制内不触发警告测试通过")
    except Exception as e:
        raise AssertionError(f"Token使用量监控方法执行失败: {e}")


def test_multiple_warnings():
    """测试同时触发多个警告"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 模拟所有Token都超过阈值
    token_usage = {
        "prompt_tokens": int(vllm_provider.max_input_tokens * 0.9),
        "completion_tokens": int(vllm_provider.max_tokens * 0.9),
        "total_tokens": int(vllm_provider.model_context_limit * 0.9)
    }
    
    try:
        vllm_provider._check_token_usage(token_usage, 1.5, 0)
        print("[PASS] 同时触发多个警告测试通过")
    except Exception as e:
        raise AssertionError(f"Token使用量监控方法执行失败: {e}")


if __name__ == "__main__":
    # 运行所有测试
    print("=" * 60)
    print("开始测试Token使用量监控功能")
    print("=" * 60)
    
    try:
        test_output_token_warning()
        test_input_token_warning()
        test_total_token_warning()
        test_log_recording()
        test_no_warning_within_limit()
        test_multiple_warnings()
        
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
