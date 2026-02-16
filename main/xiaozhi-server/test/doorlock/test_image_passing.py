"""
测试图片传递逻辑

测试目标：
- 测试第一轮传入2张图片
- 测试后续轮次传入1张图片
- 验证is_first_round标志正确使用
"""

import sys
import base64
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

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


def get_test_image_base64():
    """生成测试用的Base64图片"""
    # 创建一个简单的1x1像素图片
    import io
    from PIL import Image
    
    img = Image.new('RGB', (1, 1), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    return base64.b64encode(buffer.getvalue()).decode()


def test_first_round_two_images():
    """测试第一轮传入2张图片"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    visitor_image = get_test_image_base64()
    baseline_image = get_test_image_base64()
    dialogue_history = []
    
    # Mock VLLM API调用
    with patch.object(vllm_provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        # 设置mock返回值
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "你好，请问有什么可以帮助你的？"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 1000
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 1050
        mock_create.return_value = mock_response
        
        # 调用analyze_unified方法（第一轮）
        import asyncio
        result = asyncio.run(vllm_provider.analyze_unified(
            visitor_image=visitor_image,
            baseline_image=baseline_image,
            dialogue_history=dialogue_history,
            is_first_round=True
        ))
        
        # 验证API被调用
        assert mock_create.called, "VLLM API应该被调用"
        
        # 获取调用参数
        call_args = mock_create.call_args
        messages = call_args[1]['messages']
        
        # 验证消息中包含2张图片
        image_count = 0
        for msg in messages:
            if isinstance(msg.get('content'), list):
                for item in msg['content']:
                    if item.get('type') == 'image_url':
                        image_count += 1
        
        assert image_count == 2, f"第一轮应传入2张图片，实际传入{image_count}张"
        
        print("[PASS] 第一轮传入2张图片测试通过")


def test_subsequent_round_one_image():
    """测试后续轮次传入1张图片"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    visitor_image = get_test_image_base64()
    baseline_image = get_test_image_base64()
    dialogue_history = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好，请问有什么可以帮助你的？"}
    ]
    
    # Mock VLLM API调用
    with patch.object(vllm_provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        # 设置mock返回值
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "好的，我明白了"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 800
        mock_response.usage.completion_tokens = 30
        mock_response.usage.total_tokens = 830
        mock_create.return_value = mock_response
        
        # 调用analyze_unified方法（后续轮次）
        import asyncio
        result = asyncio.run(vllm_provider.analyze_unified(
            visitor_image=visitor_image,
            baseline_image=baseline_image,
            dialogue_history=dialogue_history,
            is_first_round=False
        ))
        
        # 验证API被调用
        assert mock_create.called, "VLLM API应该被调用"
        
        # 获取调用参数
        call_args = mock_create.call_args
        messages = call_args[1]['messages']
        
        # 验证消息中只包含1张图片
        image_count = 0
        for msg in messages:
            if isinstance(msg.get('content'), list):
                for item in msg['content']:
                    if item.get('type') == 'image_url':
                        image_count += 1
        
        assert image_count == 1, f"后续轮次应传入1张图片，实际传入{image_count}张"
        
        print("[PASS] 后续轮次传入1张图片测试通过")


def test_is_first_round_flag():
    """验证is_first_round标志正确使用"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    visitor_image = get_test_image_base64()
    baseline_image = get_test_image_base64()
    
    # Mock VLLM API调用
    with patch.object(vllm_provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        # 设置mock返回值
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "测试回复"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 1000
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 1050
        mock_create.return_value = mock_response
        
        import asyncio
        
        # 测试1：is_first_round=True，应传入2张图片
        result1 = asyncio.run(vllm_provider.analyze_unified(
            visitor_image=visitor_image,
            baseline_image=baseline_image,
            dialogue_history=[],
            is_first_round=True
        ))
        
        call_args1 = mock_create.call_args
        messages1 = call_args1[1]['messages']
        image_count1 = sum(
            1 for msg in messages1
            if isinstance(msg.get('content'), list)
            for item in msg['content']
            if item.get('type') == 'image_url'
        )
        
        # 测试2：is_first_round=False，应传入1张图片
        mock_create.reset_mock()
        result2 = asyncio.run(vllm_provider.analyze_unified(
            visitor_image=visitor_image,
            baseline_image=baseline_image,
            dialogue_history=[{"role": "user", "content": "测试"}],
            is_first_round=False
        ))
        
        call_args2 = mock_create.call_args
        messages2 = call_args2[1]['messages']
        image_count2 = sum(
            1 for msg in messages2
            if isinstance(msg.get('content'), list)
            for item in msg['content']
            if item.get('type') == 'image_url'
        )
        
        # 验证
        assert image_count1 == 2, f"is_first_round=True时应传入2张图片，实际{image_count1}张"
        assert image_count2 == 1, f"is_first_round=False时应传入1张图片，实际{image_count2}张"
        
        print("[PASS] is_first_round标志正确使用测试通过")


def test_no_baseline_image():
    """测试无基准图片时的行为"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    visitor_image = get_test_image_base64()
    dialogue_history = []
    
    # Mock VLLM API调用
    with patch.object(vllm_provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        # 设置mock返回值
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "你好"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 800
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 820
        mock_create.return_value = mock_response
        
        # 调用analyze_unified方法（无基准图片）
        import asyncio
        result = asyncio.run(vllm_provider.analyze_unified(
            visitor_image=visitor_image,
            baseline_image=None,
            dialogue_history=dialogue_history,
            is_first_round=True
        ))
        
        # 验证API被调用
        assert mock_create.called, "VLLM API应该被调用"
        
        # 获取调用参数
        call_args = mock_create.call_args
        messages = call_args[1]['messages']
        
        # 验证消息中只包含1张图片（访客图片）
        image_count = 0
        for msg in messages:
            if isinstance(msg.get('content'), list):
                for item in msg['content']:
                    if item.get('type') == 'image_url':
                        image_count += 1
        
        assert image_count == 1, f"无基准图片时应传入1张图片，实际传入{image_count}张"
        
        print("[PASS] 无基准图片时的行为测试通过")


if __name__ == "__main__":
    # 运行所有测试
    print("=" * 60)
    print("开始测试图片传递逻辑")
    print("=" * 60)
    
    try:
        test_first_round_two_images()
        test_subsequent_round_one_image()
        test_is_first_round_flag()
        test_no_baseline_image()
        
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
