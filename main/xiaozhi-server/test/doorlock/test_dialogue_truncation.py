"""
测试对话历史截断功能

测试目标：
- 测试对话历史超出限制时截断
- 验证保留最新对话
- 验证Token估算准确性
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


def test_truncate_when_exceeds_limit():
    """测试对话历史超出限制时截断"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 创建一个很长的对话历史
    dialogue_history = []
    for i in range(20):
        dialogue_history.append({
            "role": "user",
            "content": f"这是第{i+1}轮用户消息，包含一些内容来增加Token数量。" * 10
        })
        dialogue_history.append({
            "role": "assistant",
            "content": f"这是第{i+1}轮助手回复，也包含一些内容来增加Token数量。" * 10
        })
    
    # 设置一个较小的限制
    max_tokens = 1000
    
    # 调用截断方法
    truncated = vllm_provider._truncate_dialogue_history(dialogue_history, max_tokens)
    
    # 验证截断后的对话历史更短
    assert len(truncated) < len(dialogue_history), "对话历史应该被截断"
    
    # 验证截断后的Token数量在限制内
    total_tokens = sum(
        vllm_provider._estimate_tokens(msg["content"])
        for msg in truncated
    )
    assert total_tokens <= max_tokens, f"截断后Token数({total_tokens})应该在限制内({max_tokens})"
    
    print(f"[PASS] 对话历史截断测试通过: {len(dialogue_history)}轮 -> {len(truncated)}轮, {total_tokens} tokens")


def test_keep_latest_messages():
    """验证保留最新对话"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 创建对话历史，每条消息有明确的标识
    dialogue_history = []
    for i in range(10):
        dialogue_history.append({
            "role": "user",
            "content": f"用户消息{i+1}"
        })
        dialogue_history.append({
            "role": "assistant",
            "content": f"助手回复{i+1}"
        })
    
    # 设置一个较小的限制，只能保留最后几轮
    max_tokens = 100
    
    # 调用截断方法
    truncated = vllm_provider._truncate_dialogue_history(dialogue_history, max_tokens)
    
    # 验证保留的是最新的消息
    if len(truncated) > 0:
        # 最后一条消息应该是原始对话历史的最后一条
        assert truncated[-1]["content"] == dialogue_history[-1]["content"], "应该保留最新的消息"
        
        # 验证截断后的消息都来自原始对话历史的末尾
        for msg in truncated:
            assert msg in dialogue_history, "截断后的消息应该来自原始对话历史"
    
    print(f"[PASS] 保留最新对话测试通过: 保留了最后{len(truncated)}条消息")


def test_token_estimation_accuracy():
    """验证Token估算准确性"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 测试中文文本
    chinese_text = "这是一段中文文本，用于测试Token估算。"
    chinese_tokens = vllm_provider._estimate_tokens(chinese_text)
    # 中文按1.5字符/Token估算
    expected_chinese = len(chinese_text) / 1.5
    assert abs(chinese_tokens - expected_chinese) < 5, f"中文Token估算偏差过大: {chinese_tokens} vs {expected_chinese}"
    print(f"  中文Token估算: '{chinese_text}' -> {chinese_tokens} tokens (预期约{expected_chinese:.1f})")
    
    # 测试英文文本
    english_text = "This is an English text for token estimation testing."
    english_tokens = vllm_provider._estimate_tokens(english_text)
    # 英文按4字符/Token估算
    expected_english = len(english_text) / 4
    assert abs(english_tokens - expected_english) < 5, f"英文Token估算偏差过大: {english_tokens} vs {expected_english}"
    print(f"  英文Token估算: '{english_text}' -> {english_tokens} tokens (预期约{expected_english:.1f})")
    
    # 测试混合文本
    mixed_text = "这是中文 and this is English 混合文本。"
    mixed_tokens = vllm_provider._estimate_tokens(mixed_text)
    print(f"  混合Token估算: '{mixed_text}' -> {mixed_tokens} tokens")
    
    print("[PASS] Token估算准确性测试通过")


def test_empty_dialogue():
    """测试空对话历史"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    dialogue_history = []
    max_tokens = 1000
    
    truncated = vllm_provider._truncate_dialogue_history(dialogue_history, max_tokens)
    
    assert len(truncated) == 0, "空对话历史应该返回空列表"
    print("[PASS] 空对话历史测试通过")


def test_within_limit():
    """测试对话历史在限制内"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 创建一个较短的对话历史
    dialogue_history = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好，有什么可以帮助你的？"},
        {"role": "user", "content": "我想了解一下"},
        {"role": "assistant", "content": "好的，请说"}
    ]
    
    # 设置一个很大的限制
    max_tokens = 10000
    
    truncated = vllm_provider._truncate_dialogue_history(dialogue_history, max_tokens)
    
    # 验证没有被截断
    assert len(truncated) == len(dialogue_history), "对话历史在限制内不应该被截断"
    assert truncated == dialogue_history, "对话历史应该完全保留"
    
    print("[PASS] 对话历史在限制内测试通过")


def test_truncation_preserves_order():
    """测试截断保持消息顺序"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 创建对话历史
    dialogue_history = []
    for i in range(10):
        dialogue_history.append({
            "role": "user",
            "content": f"消息{i+1}"
        })
    
    max_tokens = 50
    
    truncated = vllm_provider._truncate_dialogue_history(dialogue_history, max_tokens)
    
    # 验证顺序保持
    for i in range(len(truncated) - 1):
        # 提取消息编号
        current_num = int(truncated[i]["content"].replace("消息", ""))
        next_num = int(truncated[i+1]["content"].replace("消息", ""))
        assert next_num == current_num + 1, "消息顺序应该保持"
    
    print(f"[PASS] 截断保持消息顺序测试通过: 保留了消息{truncated[0]['content']}到{truncated[-1]['content']}")


if __name__ == "__main__":
    # 运行所有测试
    print("=" * 60)
    print("开始测试对话历史截断功能")
    print("=" * 60)
    
    try:
        test_truncate_when_exceeds_limit()
        test_keep_latest_messages()
        test_token_estimation_accuracy()
        test_empty_dialogue()
        test_within_limit()
        test_truncation_preserves_order()
        
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
