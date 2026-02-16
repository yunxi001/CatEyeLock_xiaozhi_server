"""
统一模式对话流程简单测试

验证代码的基本结构和方法签名
"""
import asyncio
import sys
from unittest.mock import Mock, AsyncMock

# 添加路径
sys.path.insert(0, '.')

from core.handle.doorlock_intent_handler import DoorlockIntentHandler


def test_method_signatures():
    """测试方法签名是否正确"""
    print("测试1: 检查方法签名...")
    
    # 创建模拟对象
    handler = DoorlockIntentHandler(
        face_recognition_handler=Mock(),
        greeting_handler=Mock(),
        session_manager=Mock(),
        notification_service=Mock(),
        doorlock_database=Mock(),
        vllm_provider=Mock(),
        config={}
    )
    
    # 检查方法是否存在
    assert hasattr(handler, 'start_unified_dialogue'), "缺少start_unified_dialogue方法"
    assert hasattr(handler, '_post_dialogue_processing'), "缺少_post_dialogue_processing方法"
    assert hasattr(handler, '_handle_tool_calls'), "缺少_handle_tool_calls方法"
    assert hasattr(handler, 'start_photo_capture_task'), "缺少start_photo_capture_task方法"
    assert hasattr(handler, 'stop_photo_capture_task'), "缺少stop_photo_capture_task方法"
    
    print("✓ 所有方法签名正确")


async def test_start_unified_dialogue_basic():
    """测试start_unified_dialogue基本调用"""
    print("\n测试2: 测试start_unified_dialogue基本调用...")
    
    # 创建模拟对象
    mock_vllm = AsyncMock()
    mock_vllm.analyze_unified = AsyncMock(return_value={
        "content": "测试回复",
        "tool_calls": [],
        "token_usage": {"total_tokens": 100},
        "response_time": 1.0
    })
    mock_vllm.final_package_check = AsyncMock(return_value={
        "threat_level": "low",
        "action": "normal",
        "description": "正常"
    })
    mock_vllm.generate_intent_summary = AsyncMock(return_value={
        "intent_type": "delivery",
        "summary": "快递员送快递",
        "important_notes": [],
        "ai_analysis": "测试"
    })
    
    mock_session_mgr = Mock()
    mock_session_mgr.add_dialogue = Mock()
    mock_session_mgr.get_dialogue_history = Mock(return_value=[])
    mock_session_mgr.check_dialogue_end = AsyncMock(return_value=True)
    
    handler = DoorlockIntentHandler(
        face_recognition_handler=Mock(),
        greeting_handler=Mock(),
        session_manager=mock_session_mgr,
        notification_service=Mock(),
        doorlock_database=Mock(),
        vllm_provider=mock_vllm,
        config={'max_dialogue_rounds': 10}
    )
    
    # 模拟辅助方法
    handler._play_initial_greeting = AsyncMock(return_value="您好")
    handler._check_pir_status = AsyncMock(return_value=True)
    handler._wait_for_visitor_response = AsyncMock(return_value=None)
    handler._save_visit_record = AsyncMock(return_value=123)
    handler.notification_service.notify_visitor_intent = AsyncMock()
    
    # 调用方法（看护未激活）
    result = await handler.start_unified_dialogue(
        device_id="test_device",
        session_id="test_session",
        person_info=None,
        visitor_image=b"photo",
        baseline_image=None,
        conn=Mock()
    )
    
    # 验证结果
    assert result["success"] is True, f"期望success=True，实际: {result}"
    assert result["action"] == "intent_recognized", f"期望action=intent_recognized，实际: {result['action']}"
    assert "visit_id" in result, "结果中缺少visit_id"
    assert "intent_summary" in result, "结果中缺少intent_summary"
    
    print("✓ start_unified_dialogue基本调用成功")


async def test_post_dialogue_processing_basic():
    """测试_post_dialogue_processing基本调用"""
    print("\n测试3: 测试_post_dialogue_processing基本调用...")
    
    # 创建模拟对象
    mock_vllm = AsyncMock()
    mock_vllm.final_package_check = AsyncMock(return_value={
        "threat_level": "low",
        "action": "normal",
        "description": "正常"
    })
    mock_vllm.generate_intent_summary = AsyncMock(return_value={
        "intent_type": "delivery",
        "summary": "快递员送快递",
        "important_notes": [],
        "ai_analysis": "测试"
    })
    
    handler = DoorlockIntentHandler(
        face_recognition_handler=Mock(),
        greeting_handler=Mock(),
        session_manager=Mock(),
        notification_service=Mock(),
        doorlock_database=Mock(),
        vllm_provider=mock_vllm,
        config={}
    )
    
    # 模拟辅助方法
    handler._save_visit_record = AsyncMock(return_value=123)
    handler.notification_service.notify_visitor_intent = AsyncMock()
    handler.photo_cache.get_latest_photo = Mock(return_value=b"photo")
    
    # 调用方法（看护激活）
    result = await handler._post_dialogue_processing(
        device_id="test_device",
        session_id="test_session",
        visitor_image=b"photo",
        baseline_image=b"baseline",
        dialogue_history=[],
        conn=Mock()
    )
    
    # 验证结果
    assert result["success"] is True, f"期望success=True，实际: {result}"
    assert "visit_id" in result, "结果中缺少visit_id"
    assert "intent_summary" in result, "结果中缺少intent_summary"
    assert "package_check_result" in result, "结果中缺少package_check_result"
    
    # 验证调用了快递检查
    mock_vllm.final_package_check.assert_called_once()
    
    print("✓ _post_dialogue_processing基本调用成功")


async def test_handle_tool_calls_basic():
    """测试_handle_tool_calls基本调用"""
    print("\n测试4: 测试_handle_tool_calls基本调用...")
    
    # 创建模拟对象
    mock_tools = AsyncMock()
    mock_tools.call_tool = AsyncMock(return_value={"success": True})
    
    mock_vllm = Mock()
    mock_vllm.doorlock_tools = mock_tools
    
    handler = DoorlockIntentHandler(
        face_recognition_handler=Mock(),
        greeting_handler=Mock(),
        session_manager=Mock(),
        notification_service=Mock(),
        doorlock_database=Mock(),
        vllm_provider=mock_vllm,
        config={}
    )
    
    handler._play_ai_response = AsyncMock()
    
    # 调用方法（正常威胁）
    tool_calls = [
        {
            "name": "report_package_status",
            "arguments": {
                "action": "searching",
                "threat_level": "medium",
                "description": "翻看快递"
            }
        }
    ]
    
    await handler._handle_tool_calls(
        device_id="test_device",
        session_id="test_session",
        tool_calls=tool_calls,
        conn=Mock()
    )
    
    # 验证调用了工具
    mock_tools.call_tool.assert_called_once()
    
    # 验证补充了参数
    call_args = mock_tools.call_tool.call_args
    assert call_args[1]["arguments"]["device_id"] == "test_device"
    assert call_args[1]["arguments"]["session_id"] == "test_session"
    
    print("✓ _handle_tool_calls基本调用成功")


async def test_handle_tool_calls_high_threat():
    """测试_handle_tool_calls高威胁处理"""
    print("\n测试5: 测试_handle_tool_calls高威胁处理...")
    
    # 创建模拟对象
    mock_tools = AsyncMock()
    mock_tools.call_tool = AsyncMock(return_value={"success": True})
    
    mock_vllm = Mock()
    mock_vllm.doorlock_tools = mock_tools
    
    handler = DoorlockIntentHandler(
        face_recognition_handler=Mock(),
        greeting_handler=Mock(),
        session_manager=Mock(),
        notification_service=Mock(),
        doorlock_database=Mock(),
        vllm_provider=mock_vllm,
        config={}
    )
    
    handler._play_ai_response = AsyncMock()
    
    # 调用方法（高威胁）
    tool_calls = [
        {
            "name": "report_package_status",
            "arguments": {
                "action": "taking",
                "threat_level": "high",
                "description": "试图拿走快递"
            }
        }
    ]
    
    await handler._handle_tool_calls(
        device_id="test_device",
        session_id="test_session",
        tool_calls=tool_calls,
        conn=Mock()
    )
    
    # 验证调用了工具
    mock_tools.call_tool.assert_called_once()
    
    # 验证播放了警告（高威胁）
    handler._play_ai_response.assert_called_once()
    call_args = handler._play_ai_response.call_args
    # call_args是一个Call对象，使用kwargs访问
    if call_args.kwargs:
        assert "警告" in call_args.kwargs.get('response', ''), "高威胁时应播放警告"
    else:
        # 使用args访问
        assert "警告" in call_args.args[1], "高威胁时应播放警告"
    
    print("✓ _handle_tool_calls高威胁处理成功")


async def run_async_tests():
    """运行所有异步测试"""
    await test_start_unified_dialogue_basic()
    await test_post_dialogue_processing_basic()
    await test_handle_tool_calls_basic()
    await test_handle_tool_calls_high_threat()


def main():
    """主测试函数"""
    print("=" * 60)
    print("统一模式对话流程测试")
    print("=" * 60)
    
    try:
        # 同步测试
        test_method_signatures()
        
        # 异步测试
        asyncio.run(run_async_tests())
        
        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
