"""
测试JSON解析功能

测试目标：
- 测试final_package_check JSON解析
- 测试generate_intent_summary JSON解析
- 测试正常JSON解析
- 测试JSON解析失败返回默认值
- 测试markdown代码块中的JSON提取
"""

import sys
import json
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


def test_final_package_check_normal_json():
    """测试final_package_check正常JSON解析"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 模拟正常的JSON响应
    json_response = {
        "threat_level": "medium",
        "action": "searching",
        "description": "访客正在翻看快递"
    }
    
    # Mock VLLM API调用
    async def mock_create(*args, **kwargs):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = json.dumps(json_response, ensure_ascii=False)
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 1000
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 1050
        return mock_response
    
    with patch.object(vllm_provider.client.chat.completions, 'create', side_effect=mock_create):
        import asyncio
        result = asyncio.run(vllm_provider.final_package_check(
            current_image="test_image",
            baseline_image="baseline_image"
        ))
        
        # 验证解析结果
        assert result["threat_level"] == "medium"
        assert result["action"] == "searching"
        assert "description" in result
        
        print("✓ final_package_check正常JSON解析测试通过")


def test_final_package_check_parse_failure():
    """测试final_package_check JSON解析失败返回默认值"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # Mock VLLM API调用返回非JSON格式
    async def mock_create(*args, **kwargs):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "这不是一个有效的JSON格式"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 1000
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 1050
        return mock_response
    
    with patch.object(vllm_provider.client.chat.completions, 'create', side_effect=mock_create):
        import asyncio
        result = asyncio.run(vllm_provider.final_package_check(
            current_image="test_image",
            baseline_image="baseline_image"
        ))
        
        # 验证返回默认值
        assert result["threat_level"] == "low"
        assert result["action"] == "normal"
        assert "description" in result
        
        print("✓ final_package_check JSON解析失败返回默认值测试通过")


def test_final_package_check_markdown_json():
    """测试final_package_check从markdown代码块中提取JSON"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 模拟markdown代码块中的JSON
    json_response = {
        "threat_level": "high",
        "action": "taking",
        "description": "访客拿走了快递"
    }
    markdown_content = f"```json\n{json.dumps(json_response, ensure_ascii=False)}\n```"
    
    # Mock VLLM API调用
    async def mock_create(*args, **kwargs):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = markdown_content
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 1000
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 1050
        return mock_response
    
    with patch.object(vllm_provider.client.chat.completions, 'create', side_effect=mock_create):
        import asyncio
        result = asyncio.run(vllm_provider.final_package_check(
            current_image="test_image",
            baseline_image="baseline_image"
        ))
        
        # 验证解析结果
        assert result["threat_level"] == "high"
        assert result["action"] == "taking"
        
        print("✓ final_package_check从markdown代码块提取JSON测试通过")


def test_generate_intent_summary_normal_json():
    """测试generate_intent_summary正常JSON解析"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 模拟正常的JSON响应
    json_response = {
        "intent_type": "delivery",
        "summary": "快递员送快递",
        "important_notes": ["【留言】快递已放门口"],
        "ai_analysis": "访客是快递员，态度友好"
    }
    
    # Mock VLLM API调用
    async def mock_create(*args, **kwargs):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = json.dumps(json_response, ensure_ascii=False)
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 1000
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 1050
        return mock_response
    
    with patch.object(vllm_provider.client.chat.completions, 'create', side_effect=mock_create):
        import asyncio
        result = asyncio.run(vllm_provider.generate_intent_summary(
            visitor_image="test_image",
            dialogue_history=[]
        ))
        
        # 验证解析结果
        assert result["intent_type"] == "delivery"
        assert result["summary"] == "快递员送快递"
        assert isinstance(result["important_notes"], list)
        
        print("✓ generate_intent_summary正常JSON解析测试通过")


def test_generate_intent_summary_parse_failure():
    """测试generate_intent_summary JSON解析失败返回默认值"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # Mock VLLM API调用返回非JSON格式
    async def mock_create(*args, **kwargs):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "无法解析的内容"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 1000
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 1050
        return mock_response
    
    with patch.object(vllm_provider.client.chat.completions, 'create', side_effect=mock_create):
        import asyncio
        result = asyncio.run(vllm_provider.generate_intent_summary(
            visitor_image="test_image",
            dialogue_history=[]
        ))
        
        # 验证返回默认值
        assert result["intent_type"] == "other"
        assert "summary" in result
        assert isinstance(result["important_notes"], list)
        
        print("✓ generate_intent_summary JSON解析失败返回默认值测试通过")


def test_generate_intent_summary_markdown_json():
    """测试generate_intent_summary从markdown代码块中提取JSON"""
    vllm_provider = DoorlockVLLMProvider(get_mock_config(), logger)
    
    # 模拟markdown代码块中的JSON
    json_response = {
        "intent_type": "sales",
        "summary": "推销人员推销产品",
        "important_notes": ["【提醒】已礼貌拒绝"],
        "ai_analysis": "访客是推销人员"
    }
    markdown_content = f"根据对话分析：\n```json\n{json.dumps(json_response, ensure_ascii=False)}\n```"
    
    # Mock VLLM API调用
    async def mock_create(*args, **kwargs):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = markdown_content
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 1000
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 1050
        return mock_response
    
    with patch.object(vllm_provider.client.chat.completions, 'create', side_effect=mock_create):
        import asyncio
        result = asyncio.run(vllm_provider.generate_intent_summary(
            visitor_image="test_image",
            dialogue_history=[]
        ))
        
        # 验证解析结果
        assert result["intent_type"] == "sales"
        assert result["summary"] == "推销人员推销产品"
        
        print("✓ generate_intent_summary从markdown代码块提取JSON测试通过")


if __name__ == "__main__":
    # 运行所有测试
    print("=" * 60)
    print("开始测试JSON解析功能")
    print("=" * 60)
    
    try:
        test_final_package_check_normal_json()
        test_final_package_check_parse_failure()
        test_final_package_check_markdown_json()
        test_generate_intent_summary_normal_json()
        test_generate_intent_summary_parse_failure()
        test_generate_intent_summary_markdown_json()
        
        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
