"""
统一模式对话流程测试

测试意图处理器的核心流程：
- start_unified_dialogue方法
- 对话循环核心逻辑
- _post_dialogue_processing方法
- _handle_tool_calls方法
"""
import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from core.handle.doorlock_intent_handler import DoorlockIntentHandler
from core.providers.doorlock.face_recognition_handler import FaceRecognitionHandler
from core.providers.doorlock.greeting_handler import GreetingHandler
from core.providers.doorlock.session_manager import SessionManager
from core.providers.doorlock.notification_service import NotificationService
from core.providers.doorlock.doorlock_database import DoorlockDatabase
from core.providers.vllm.doorlock_vllm import DoorlockVLLMProvider
from core.providers.doorlock.photo_cache_manager import PhotoCacheManager


@pytest.fixture
def mock_vllm_provider():
    """模拟VLLM提供者"""
    vllm = AsyncMock(spec=DoorlockVLLMProvider)
    
    # 模拟analyze_unified方法
    vllm.analyze_unified = AsyncMock(return_value={
        "content": "好的，我会帮您转达。",
        "tool_calls": [],
        "token_usage": {
            "prompt_tokens": 5000,
            "completion_tokens": 100,
            "total_tokens": 5100
        },
        "response_time": 1.5
    })
    
    # 模拟final_package_check方法
    vllm.final_package_check = AsyncMock(return_value={
        "threat_level": "low",
        "action": "normal",
        "description": "快递状态正常，未发现异常"
    })
    
    # 模拟generate_intent_summary方法
    vllm.generate_intent_summary = AsyncMock(return_value={
        "intent_type": "delivery",
        "summary": "快递员送快递",
        "important_notes": ["【留言】快递已放门口"],
        "ai_analysis": "访客是快递员，送了一个包裹"
    })
    
    # 模拟doorlock_tools
    mock_tools = AsyncMock()
    mock_tools.call_tool = AsyncMock(return_value={
        "success": True,
        "message": "工具调用成功"
    })
    vllm.doorlock_tools = mock_tools
    
    return vllm


@pytest.fixture
def mock_session_manager():
    """模拟会话管理器"""
    session_mgr = Mock(spec=SessionManager)
    
    # 模拟对话历史
    dialogue_history = [
        {"role": "assistant", "content": "您好，请问您找谁？"},
        {"role": "user", "content": "我是快递员，有个包裹"},
        {"role": "assistant", "content": "好的，请放在门口就可以"}
    ]
    
    session_mgr.add_dialogue = Mock()
    session_mgr.get_dialogue_history = Mock(return_value=dialogue_history)
    session_mgr.check_dialogue_end = AsyncMock(return_value=False)
    session_mgr.cleanup_session = AsyncMock()
    
    return session_mgr


@pytest.fixture
def mock_photo_cache():
    """模拟照片缓存管理器"""
    with patch('core.handle.doorlock_intent_handler.PhotoCacheManager') as MockCache:
        cache_instance = MockCache.return_value
        cache_instance.add_photo = Mock()
        cache_instance.get_latest_photo = Mock(return_value=b"fake_photo_data")
        cache_instance.clear_cache = Mock()
        cache_instance.get_cache_size = Mock(return_value=5)
        yield cache_instance


@pytest.fixture
def intent_handler(mock_vllm_provider, mock_session_manager):
    """创建意图处理器实例"""
    handler = DoorlockIntentHandler(
        face_recognition_handler=Mock(spec=FaceRecognitionHandler),
        greeting_handler=Mock(spec=GreetingHandler),
        session_manager=mock_session_manager,
        notification_service=Mock(spec=NotificationService),
        doorlock_database=Mock(spec=DoorlockDatabase),
        vllm_provider=mock_vllm_provider,
        config={
            'dialogue_timeout': 30,
            'max_dialogue_rounds': 10,
            'max_token_usage_ratio': 0.8
        }
    )
    
    # 模拟辅助方法
    handler._capture_visitor_photo = AsyncMock(return_value=b"fake_photo")
    handler._play_initial_greeting = AsyncMock(return_value="您好，请问您找谁？")
    handler._check_pir_status = AsyncMock(return_value=True)
    handler._wait_for_visitor_response = AsyncMock(return_value=None)  # 默认无回复
    handler._play_ai_response = AsyncMock()
    handler._save_visit_record = AsyncMock(return_value=123)
    
    # 模拟通知服务
    handler.notification_service.notify_visitor_intent = AsyncMock()
    
    return handler


@pytest.mark.asyncio
async def test_start_unified_dialogue_without_guard(intent_handler, mock_session_manager):
    """测试统一模式对话（看护未激活）"""
    # 模拟对话结束
    mock_session_manager.check_dialogue_end = AsyncMock(return_value=True)
    
    result = await intent_handler.start_unified_dialogue(
        device_id="test_device",
        session_id="test_session",
        person_info=None,
        visitor_image=b"visitor_photo",
        baseline_image=None,  # 看护未激活
        conn=Mock()
    )
    
    # 验证结果
    assert result["success"] is True
    assert result["action"] == "intent_recognized"
    assert "visit_id" in result
    assert "intent_summary" in result
    
    # 验证播放了主动问候
    intent_handler._play_initial_greeting.assert_called_once()
    
    # 验证生成了意图总结
    intent_handler.vllm.generate_intent_summary.assert_called_once()
    
    # 验证未调用快递检查（看护未激活）
    intent_handler.vllm.final_package_check.assert_not_called()


@pytest.mark.asyncio
async def test_start_unified_dialogue_with_guard(intent_handler, mock_session_manager, mock_photo_cache):
    """测试统一模式对话（看护激活）"""
    # 模拟对话结束
    mock_session_manager.check_dialogue_end = AsyncMock(return_value=True)
    
    # 替换photo_cache
    intent_handler.photo_cache = mock_photo_cache
    
    result = await intent_handler.start_unified_dialogue(
        device_id="test_device",
        session_id="test_session",
        person_info=None,
        visitor_image=b"visitor_photo",
        baseline_image=b"baseline_photo",  # 看护激活
        conn=Mock()
    )
    
    # 验证结果
    assert result["success"] is True
    assert result["action"] == "intent_recognized"
    
    # 验证调用了快递检查（看护激活）
    intent_handler.vllm.final_package_check.assert_called_once()
    
    # 验证清理了照片缓存
    mock_photo_cache.clear_cache.assert_called_once_with("test_session")


@pytest.mark.asyncio
async def test_dialogue_loop_with_visitor_response(intent_handler, mock_session_manager):
    """测试对话循环（有访客回复）"""
    # 模拟访客回复一次后对话结束
    call_count = 0
    
    async def mock_wait_response(device_id, conn=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "我是快递员，有个包裹"
        return None
    
    async def mock_check_end(session_id, pir_detected):
        return call_count > 1
    
    intent_handler._wait_for_visitor_response = mock_wait_response
    mock_session_manager.check_dialogue_end = mock_check_end
    
    result = await intent_handler.start_unified_dialogue(
        device_id="test_device",
        session_id="test_session",
        person_info=None,
        visitor_image=b"visitor_photo",
        baseline_image=None,
        conn=Mock()
    )
    
    # 验证调用了VLLM分析
    intent_handler.vllm.analyze_unified.assert_called()
    
    # 验证播放了AI回复
    intent_handler._play_ai_response.assert_called()
    
    # 验证对话轮次
    assert result["dialogue_count"] >= 1


@pytest.mark.asyncio
async def test_post_dialogue_processing_with_guard(intent_handler, mock_photo_cache):
    """测试对话结束后处理（看护激活）"""
    # 替换photo_cache
    intent_handler.photo_cache = mock_photo_cache
    
    result = await intent_handler._post_dialogue_processing(
        device_id="test_device",
        session_id="test_session",
        visitor_image=b"visitor_photo",
        baseline_image=b"baseline_photo",  # 看护激活
        dialogue_history=[
            {"role": "assistant", "content": "您好"},
            {"role": "user", "content": "我是快递员"}
        ],
        conn=Mock()
    )
    
    # 验证结果
    assert result["success"] is True
    assert "visit_id" in result
    assert "intent_summary" in result
    assert "package_check_result" in result
    
    # 验证调用了快递检查
    intent_handler.vllm.final_package_check.assert_called_once()
    
    # 验证调用了意图总结
    intent_handler.vllm.generate_intent_summary.assert_called_once()
    
    # 验证保存了访问记录
    intent_handler._save_visit_record.assert_called_once()
    
    # 验证发送了通知
    intent_handler.notification_service.notify_visitor_intent.assert_called_once()


@pytest.mark.asyncio
async def test_post_dialogue_processing_without_guard(intent_handler):
    """测试对话结束后处理（看护未激活）"""
    result = await intent_handler._post_dialogue_processing(
        device_id="test_device",
        session_id="test_session",
        visitor_image=b"visitor_photo",
        baseline_image=None,  # 看护未激活
        dialogue_history=[
            {"role": "assistant", "content": "您好"},
            {"role": "user", "content": "我是快递员"}
        ],
        conn=Mock()
    )
    
    # 验证结果
    assert result["success"] is True
    
    # 验证未调用快递检查
    intent_handler.vllm.final_package_check.assert_not_called()
    
    # 验证调用了意图总结
    intent_handler.vllm.generate_intent_summary.assert_called_once()


@pytest.mark.asyncio
async def test_handle_tool_calls_normal(intent_handler):
    """测试工具调用处理（正常威胁）"""
    tool_calls = [
        {
            "name": "report_package_status",
            "arguments": {
                "action": "searching",
                "threat_level": "medium",
                "description": "访客在翻看快递"
            }
        }
    ]
    
    await intent_handler._handle_tool_calls(
        device_id="test_device",
        session_id="test_session",
        tool_calls=tool_calls,
        conn=Mock()
    )
    
    # 验证调用了工具
    intent_handler.vllm.doorlock_tools.call_tool.assert_called_once()
    
    # 验证补充了必要参数
    call_args = intent_handler.vllm.doorlock_tools.call_tool.call_args
    assert call_args[1]["arguments"]["device_id"] == "test_device"
    assert call_args[1]["arguments"]["session_id"] == "test_session"


@pytest.mark.asyncio
async def test_handle_tool_calls_high_threat(intent_handler):
    """测试工具调用处理（高威胁）"""
    tool_calls = [
        {
            "name": "report_package_status",
            "arguments": {
                "action": "taking",
                "threat_level": "high",
                "description": "访客试图拿走快递"
            }
        }
    ]
    
    await intent_handler._handle_tool_calls(
        device_id="test_device",
        session_id="test_session",
        tool_calls=tool_calls,
        conn=Mock()
    )
    
    # 验证调用了工具
    intent_handler.vllm.doorlock_tools.call_tool.assert_called_once()
    
    # 验证播放了警告语音（高威胁）
    intent_handler._play_ai_response.assert_called()
    call_args = intent_handler._play_ai_response.call_args
    assert "警告" in call_args[0][1]


@pytest.mark.asyncio
async def test_handle_tool_calls_exception(intent_handler):
    """测试工具调用异常处理"""
    # 模拟工具调用失败
    intent_handler.vllm.doorlock_tools.call_tool = AsyncMock(
        side_effect=Exception("工具调用失败")
    )
    
    tool_calls = [
        {
            "name": "report_package_status",
            "arguments": {
                "action": "normal",
                "threat_level": "low",
                "description": "正常"
            }
        }
    ]
    
    # 不应该抛出异常
    await intent_handler._handle_tool_calls(
        device_id="test_device",
        session_id="test_session",
        tool_calls=tool_calls,
        conn=Mock()
    )
    
    # 验证尝试调用了工具
    intent_handler.vllm.doorlock_tools.call_tool.assert_called_once()


@pytest.mark.asyncio
async def test_unified_dialogue_exception_cleanup(intent_handler, mock_session_manager, mock_photo_cache):
    """测试统一模式对话异常时的清理"""
    # 替换photo_cache
    intent_handler.photo_cache = mock_photo_cache
    
    # 模拟VLLM调用失败
    intent_handler.vllm.analyze_unified = AsyncMock(
        side_effect=Exception("VLLM调用失败")
    )
    
    # 模拟有访客回复
    intent_handler._wait_for_visitor_response = AsyncMock(
        return_value="测试回复"
    )
    
    result = await intent_handler.start_unified_dialogue(
        device_id="test_device",
        session_id="test_session",
        person_info=None,
        visitor_image=b"visitor_photo",
        baseline_image=b"baseline_photo",  # 看护激活
        conn=Mock()
    )
    
    # 验证返回失败
    assert result["success"] is False
    assert "error" in result
    
    # 验证清理了照片缓存（即使异常）
    mock_photo_cache.clear_cache.assert_called_once_with("test_session")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
