"""
边界情况测试（简化版）
只测试可以独立测试的边界情况
"""

import asyncio
import json
import sys
from unittest.mock import Mock, patch
from core.providers.vllm.doorlock_vllm import DoorlockVLLMProvider
from core.providers.doorlock.photo_cache_manager import PhotoCacheManager
from loguru import logger


def get_full_config():
    """获取完整配置"""
    return {
        "selected_module": {"VLLM": "QwenVLVLLM"},
        "VLLM": {
            "QwenVLVLLM": {
                "type": "openai",
                "model_name": "qwen2.5-vl-3b-instruct",
                "url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key": "test_api_key"
            }
        },
        "unified_mode": {"enabled": True},
        "performance": {
            "vllm_limits": {
                "model_context_limit": 262144,
                "max_input_tokens": 260096,
                "max_output_tokens": 32768,
                "max_image_tokens": 16384,
                "tokens_per_image": 7000
            }
        },
        "photo_cache": {"max_cache_size": 10}
    }


def get_mock_prompts():
    """获取模拟提示词"""
    return {
        "core_role_and_style": "你是智能门锁AI助手",
        "dialogue_tasks": "与访客对话",
        "guard_tasks": "监控快递",
        "tools_guide": "工具指南",
        "final_package_check_prompt": "检查快递",
        "intent_summary_prompt": "生成总结"
    }


async def test_10_2_owner_with_guard():
    """10.2 测试主人取快递但不关闭看护"""
    print("\n[测试 10.2] 主人取快递但不关闭看护")
    
    provider = DoorlockVLLMProvider(get_full_config(), logger)
    provider.prompts = get_mock_prompts()
    
    # 创建mock响应
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = json.dumps({
        "threat_level": "low",
        "action": "normal",
        "description": "主人取走快递，正常行为"
    })
    mock_response.usage = Mock(prompt_tokens=1000, completion_tokens=100, total_tokens=1100)
    
    with patch.object(provider.client.chat.completions, 'create', return_value=mock_response):
        result = await provider.final_package_check("current_img", "baseline_img")
        assert result["threat_level"] == "low"
        assert result["action"] == "normal"
        print("  ✓ 验证通过：主人取快递判定为低威胁")
    
    print("  ✓ 测试 10.2 通过")


async def test_10_3_json_parse_failure():
    """10.3 测试JSON解析失败场景"""
    print("\n[测试 10.3] JSON解析失败场景")
    
    provider = DoorlockVLLMProvider(get_full_config(), logger)
    provider.prompts = get_mock_prompts()
    
    # 创建非JSON响应
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "这不是JSON格式"
    mock_response.usage = Mock(prompt_tokens=1000, completion_tokens=100, total_tokens=1100)
    
    with patch.object(provider.client.chat.completions, 'create', return_value=mock_response):
        # 测试final_package_check
        result = await provider.final_package_check("img1", "img2")
        assert result["threat_level"] == "low"
        print("  ✓ 验证通过：快递检查JSON解析失败返回默认结果")
        
        # 测试generate_intent_summary
        result = await provider.generate_intent_summary("img", [{"role": "user", "content": "测试"}])
        assert result["intent_type"] == "other"
        print("  ✓ 验证通过：意图总结JSON解析失败返回默认结果")
    
    print("  ✓ 测试 10.3 通过")


def test_10_4_image_token_exceeded():
    """10.4 测试图片Token超限场景"""
    print("\n[测试 10.4] 图片Token超限场景")
    
    provider = DoorlockVLLMProvider(get_full_config(), logger)
    
    assert provider._check_image_token_limit(1) == True
    print("  ✓ 验证通过：1张图片通过检查")
    
    assert provider._check_image_token_limit(2) == True
    print("  ✓ 验证通过：2张图片通过检查")
    
    assert provider._check_image_token_limit(3) == False
    print("  ✓ 验证通过：3张图片超限检查失败")
    
    print("  ✓ 测试 10.4 通过")


async def test_10_5_vllm_call_failure():
    """10.5 测试VLLM调用失败场景"""
    print("\n[测试 10.5] VLLM调用失败场景")
    
    provider = DoorlockVLLMProvider(get_full_config(), logger)
    provider.prompts = get_mock_prompts()
    
    with patch.object(provider.client.chat.completions, 'create', side_effect=Exception("VLLM服务不可用")):
        # 测试analyze_unified
        result = await provider.analyze_unified("img", None, [], False)
        assert "content" in result
        print("  ✓ 验证通过：analyze_unified失败返回默认响应")
        
        # 测试final_package_check
        result = await provider.final_package_check("img1", "img2")
        assert result["threat_level"] == "low"
        print("  ✓ 验证通过：快递检查失败返回默认结果")
        
        # 测试generate_intent_summary
        result = await provider.generate_intent_summary("img", [{"role": "user", "content": "测试"}])
        assert result["intent_type"] == "other"
        print("  ✓ 验证通过：意图总结失败返回默认结果")
    
    print("  ✓ 测试 10.5 通过")


def test_10_8_photo_cache_full():
    """10.8 测试照片缓存满时的处理"""
    print("\n[测试 10.8] 照片缓存满时的处理")
    
    cache_manager = PhotoCacheManager()
    session_id = "test_session_edge"
    cache_manager.clear_cache(session_id)
    
    # 添加15张照片
    for i in range(15):
        cache_manager.add_photo(session_id, f"photo_{i}".encode())
    
    # 验证缓存大小
    cache_size = cache_manager.get_cache_size(session_id)
    assert cache_size <= 10, f"缓存应最多10张，实际 {cache_size}"
    print(f"  ✓ 验证通过：缓存保持在10张以内（实际 {cache_size} 张）")
    
    # 验证最新照片保留
    latest = cache_manager.get_latest_photo(session_id)
    assert latest is not None
    print("  ✓ 验证通过：最新照片被保留")
    
    # 清理
    cache_manager.clear_cache(session_id)
    assert cache_manager.get_cache_size(session_id) == 0
    print("  ✓ 验证通过：缓存清理成功")
    
    print("  ✓ 测试 10.8 通过")


async def run_all_tests():
    """运行所有边界情况测试"""
    print("=" * 70)
    print("边界情况测试（简化版）")
    print("=" * 70)
    
    tests = [
        ("10.2", test_10_2_owner_with_guard),
        ("10.3", test_10_3_json_parse_failure),
        ("10.4", test_10_4_image_token_exceeded),
        ("10.5", test_10_5_vllm_call_failure),
        ("10.8", test_10_8_photo_cache_full),
    ]
    
    passed = 0
    failed = 0
    
    for test_id, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                await test_func()
            else:
                test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n✗ 测试 {test_id} 失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("=" * 70)
    print("\n说明：")
    print("- 测试 10.1（看护未激活时主人取快递）：需要完整的系统集成测试")
    print("- 测试 10.6（工具调用失败）：需要完整的意图处理器实例")
    print("- 测试 10.7（定时拍照异常）：需要完整的意图处理器实例")
    print("- 以上测试已在集成测试中覆盖")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
