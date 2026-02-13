"""
意图识别处理器单元测试
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from core.handle.doorlock_intent_handler import DoorlockIntentHandler


class TestDoorlockIntentHandler:
    """意图识别处理器测试"""
    
    @pytest.mark.asyncio
    async def test_handle_visitor_with_permission(
        self,
        mock_logger,
        mock_config,
        sample_jpeg_data
    ):
        """测试处理有权限的访客"""
        # 创建模拟组件
        mock_face_handler = AsyncMock()
        mock_greeting_handler = AsyncMock()
        mock_session_manager = Mock()
        mock_notification = AsyncMock()
        mock_database = AsyncMock()
        mock_vllm = AsyncMock()
        
        # 模拟人脸识别成功且有权限
        mock_person = Mock()
        mock_person.id = 1
        mock_person.name = '张三'
        mock_person.relation_type = 'family'
        
        mock_face_handler.recognize_with_retry = AsyncMock(return_value={
            'success': True,
            'person': mock_person
        })
        
        # 创建处理器
        handler = DoorlockIntentHandler(
            face_recognition_handler=mock_face_handler,
            greeting_handler=mock_greeting_handler,
            session_manager=mock_session_manager,
            notification_service=mock_notification,
            doorlock_database=mock_database,
            vllm_provider=mock_vllm,
            config={'dialogue_timeout': 30}
        )
        
        # 模拟权限检查
        with patch.object(handler, '_check_access_permission', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True
            
            result = await handler.handle_visitor(
                device_id='test_device_001',
                jpeg_data=sample_jpeg_data
            )
            
            assert result['success'] is True
            assert result['action'] == 'door_opened'
            mock_greeting_handler.play_welcome_greeting.assert_called_once()
            print("✓ 处理有权限访客测试通过")
    
    @pytest.mark.asyncio
    async def test_generate_intent_summary(
        self,
        mock_logger,
        mock_config,
        sample_dialogue_history
    ):
        """测试生成意图总结"""
        handler = DoorlockIntentHandler(
            face_recognition_handler=AsyncMock(),
            greeting_handler=AsyncMock(),
            session_manager=Mock(),
            notification_service=AsyncMock(),
            doorlock_database=AsyncMock(),
            vllm_provider=AsyncMock(),
            config={'dialogue_timeout': 30}
        )
        
        summary = await handler.generate_intent_summary(sample_dialogue_history)
        
        assert 'intent_type' in summary
        assert 'purpose' in summary
        assert 'full_summary' in summary
        assert 'important_notes' in summary
        print(f"✓ 生成意图总结测试通过: intent_type={summary['intent_type']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
