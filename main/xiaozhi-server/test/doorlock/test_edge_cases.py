"""
边界情况测试
测试统一看护对话模式的各种边界情况和异常处理
"""

import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from core.providers.vllm.doorlock_vllm import DoorlockVLLMProvider
from core.providers.doorlock.photo_cache_manager import PhotoCacheManager
from loguru import logger


# ============================================================================
# 测试配置
# ============================================================================

def get_full_config():
    """获取完整配置（包含VLLM配置）"""
    return {
        "selected_module": {
            "VLLM": "QwenVLVLLM"
        },
        "VLLM": {
            "QwenVLVLLM": {
                "type": "openai",
                "model_name": "qwen2.5-vl-3b-instruct",
                "url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key": "test_api_key"
            }
        },
        "unified_mode": {
            "enabled": True,
            "dialogue": {"max_rounds": 10, "timeout_seconds": 30},
            "guard": {"threat_detection": "behavior_based", "report_threshold": "medium"},
            "token_optimization": {"baseline_image_once": True, "reuse_context": True}
        },
        "performance": {
            "vllm_limits": {
                "model_context_limit": 262144,
                "max_input_tokens": 260096,
                "max_output_tokens": 32768,
                "max_image_tokens": 16384,
                "tokens_per_image": 7000,
                "input_warning_ratio": 0.8,
                "total_warning_ratio": 0.8
            }
        },
        "photo_cache": {"interval_seconds": 5, "max_cache_size": 10}
    }


def get_mock_prompts():
    """获取模拟提示词"""
    return {
        "core_role_and_style": "你是智能门锁AI助手",
        "dialogue_tasks": "与访客对话了解来访目的",
        "guard_tasks": "监控快递安全",
        "tools_guide": "可以调用工具函数",
        "final_package_check_prompt": "检查快递状态",
        "intent_summary_prompt": "生成意图总结"
    }


# ============================================================================
# 测试用例
# ============================================================================

async def test_10_2_owner_with_guard():
    """10.2 测试主人取快递但不关闭看护"""
    print("\n[测试 10.2] 主人取快递但不关闭看护")
    
    config = get_full_config()
    prompts = get_mock_prompts()
    provider = DoorlockVLLMProvider(config, logger)
    provider.prompts = prompts
    
    # 模拟VLLM返回：主人取快递，低威胁
    mock_response = {
        "threat_level": "low",
        "action": "normal",
        "description": "主人取走快递，正常行为"
    }
    
    mock_vllm_response = {
        "choices": [{"message": {"content": json.dumps(mock_response)}}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100}
    }
    
    with patch.object(provider, '_call_vllm', return_value=mock_vllm_response):
        result = await provider.final_package_check("current_img", "baseline_img")
        
        # 验证：判定为低威胁
        assert result["threat_level"] == "low", f"期望 low，实际 {result['threat_level']}"
        assert result["action"] == "normal", f"期望 normal，实际 {result['action']}"
        print("  ✓ 验证通过：主人取快递判定为低威胁")
    
    print("  ✓ 测试 10.2 通过")


async def test_10_3_json_parse_failure():
    """10.3 测试JSON解析失败场景"""
    print("\n[测试 10.3] JSON解析失败场景")
    
    config = get_full_config()
    prompts = get_mock_prompts()
    provider = DoorlockVLLMProvider(config, logger)
    provider.prompts = prompts
    
    # 模拟VLLM返回非JSON格式
    invalid_response = {
        "choices": [{"message": {"content": "这不是JSON格式"}}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100}
    }
    
    with patch.object(provider, '_call_vllm', return_value=invalid_response):
        # 测试final_package_check
        result = await provider.final_package_check("img1", "img2")
        assert result["threat_level"] == "low", "JSON解析失败应返回默认低威胁"
        print("  ✓ 验证通过：快递检查JSON解析失败返回默认结果")
        
        # 测试generate_intent_summary
        result = await provider.generate_intent_summary("img", [{"role": "user", "content": "测试"}])
        assert result["intent_type"] == "other", "JSON解析失败应返回默认意图类型"
        print("  ✓ 验证通过：意图总结JSON解析失败返回默认结果")
    
    print("  ✓ 测试 10.3 通过")


def test_10_4_image_token_exceeded():
    """10.4 测试图片Token超限场景"""
    print("\n[测试 10.4] 图片Token超限场景")
    
    config = get_full_config()
    prompts = get_mock_prompts()
    provider = DoorlockVLLMProvider(config, logger)
    provider.prompts = prompts
    
    # 测试图片Token限制检查
    assert provider._check_image_token_limit(1) == True, "1张图片应该通过"
    print("  ✓ 验证通过：1张图片通过检查")
    
    assert provider._check_image_token_limit(2) == True, "2张图片应该通过"
    print("  ✓ 验证通过：2张图片通过检查")
    
    assert provider._check_image_token_limit(3) == False, "3张图片应该失败"
    print("  ✓ 验证通过：3张图片超限检查失败")
    
    print("  ✓ 测试 10.4 通过")


async def test_10_5_vllm_call_failure():
    """10.5 测试VLLM调用失败场景"""
    print("\n[测试 10.5] VLLM调用失败场景")
    
    config = get_full_config()
    prompts = get_mock_prompts()
    provider = DoorlockVLLMProvider(config, logger)
    provider.prompts = prompts
    
    # 模拟VLLM调用失败
    with patch.object(provider, '_call_vllm', side_effect=Exception("VLLM服务不可用")):
        # 测试analyze_unified
        result = await provider.analyze_unified("img", None, [], False)
        assert "content" in result, "VLLM失败应返回默认响应"
        print("  ✓ 验证通过：analyze_unified失败返回默认响应")
        
        # 测试final_package_check
        result = await provider.final_package_check("img1", "img2")
        assert result["threat_level"] == "low", "快递检查失败应返回默认低威胁"
        print("  ✓ 验证通过：快递检查失败返回默认结果")
        
        # 测试generate_intent_summary
        result = await provider.generate_intent_summary("img", [{"role": "user", "content": "测试"}])
        assert result["intent_type"] == "other", "意图总结失败应返回默认类型"
        print("  ✓ 验证通过：意图总结失败返回默认结果")
    
    print("  ✓ 测试 10.5 通过")


def test_10_8_photo_cache_full():
    """10.8 测试照片缓存满时的处理"""
    print("\n[测试 10.8] 照片缓存满时的处理")
    
    cache_manager = PhotoCacheManager()
    session_id = "test_session_edge"
    
    # 清理可能存在的旧缓存
    cache_manager.clear_cache(session_id)
    
    # 添加15张照片（超过最大限制10张）
    for i in range(15):
        cache_manager.add_photo(session_id, f"photo_{i}".encode())
    
    # 验证缓存大小
    cache_size = cache_manager.get_cache_size(session_id)
    assert cache_size <= 10, f"缓存应最多10张，实际 {cache_size}"
    print(f"  ✓ 验证通过：缓存保持在10张以内（实际 {cache_size} 张）")
    
    # 验证最新照片保留
    latest = cache_manager.get_latest_photo(session_id)
    assert latest is not None, "应该有最新照片"
    print("  ✓ 验证通过：最新照片被保留")
    
    # 清理
    cache_manager.clear_cache(session_id)
    assert cache_manager.get_cache_size(session_id) == 0, "缓存应被清理"
    print("  ✓ 验证通过：缓存清理成功")
    
    print("  ✓ 测试 10.8 通过")


async def test_10_3_json_with_markdown():
    """10.3 扩展：测试markdown代码块中的JSON解析"""
    print("\n[测试 10.3 扩展] markdown代码块中的JSON解析")
    
    config = get_full_config()
    prompts = get_mock_prompts()
    provider = DoorlockVLLMProvider(config, logger)
    provider.prompts = prompts
    
    # 模拟VLLM返回markdown格式的JSON
    markdown_json = """
    ```json
    {
        "threat_level": "medium",
        "action": "searching",
        "description": "访客在翻看快递"
    }
    ```
    """
    
    markdown_response = {
        "choices": [{"message": {"content": markdown_json}}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100}
    }
    
    with patch.object(provider, '_call_vllm', return_value=markdown_response):
        result = await provider.final_package_check("img1", "img2")
        # 应该能够从markdown中提取JSON
        assert result["threat_level"] == "medium", f"期望 medium，实际 {result['threat_level']}"
        assert result["action"] == "searching", f"期望 searching，实际 {result['action']}"
        print("  ✓ 验证通过：成功从markdown代码块中提取JSON")
    
    print("  ✓ 测试 10.3 扩展通过")


async def test_10_4_analyze_with_token_limit():
    """10.4 扩展：测试analyze_unified中的Token限制检查"""
    print("\n[测试 10.4 扩展] analyze_unified中的Token限制检查")
    
    config = get_full_config()
    prompts = get_mock_prompts()
    provider = DoorlockVLLMProvider(config, logger)
    provider.prompts = prompts
    
    # 模拟Token限制检查失败
    with patch.object(provider, '_check_image_token_limit', return_value=False):
        with patch.object(provider, '_call_vllm') as mock_vllm:
            try:
                result = await provider.analyze_unified("img1", "img2", [], True)
                # 如果没有抛出异常，验证返回了默认响应
                assert "content" in result
                print("  ✓ 验证通过：Token超限返回默认响应")
            except ValueError as e:
                # 如果抛出异常也是合理的
                assert "Token" in str(e) or "图片" in str(e)
                print(f"  ✓ 验证通过：Token超限抛出异常 - {e}")
    
    print("  ✓ 测试 10.4 扩展通过")


# ============================================================================
# 主测试运行器
# ============================================================================

async def run_all_tests():
    """运行所有边界情况测试"""
    print("=" * 70)
    print("边界情况测试")
    print("=" * 70)
    
    tests = [
        ("10.2", test_10_2_owner_with_guard),
        ("10.3", test_10_3_json_parse_failure),
        ("10.3-ext", test_10_3_json_with_markdown),
        ("10.4", test_10_4_image_token_exceeded),
        ("10.4-ext", test_10_4_analyze_with_token_limit),
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
