"""
完整访客流程集成测试

测试从PIR触发到意图识别完成的完整流程
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch


class TestVisitorFlow:
    """访客流程集成测试"""
    
    @pytest.mark.asyncio
    async def test_visitor_with_permission_flow(
        self,
        test_config,
        test_device_id,
        test_jpeg_data,
        mock_esp32_conn
    ):
        """测试有权限访客的完整流程
        
        流程：
        1. PIR触发
        2. 拍照
        3. 人脸识别成功
        4. 检查权限（有权限）
        5. 播放欢迎词
        6. 开门
        """
        from core.handle.doorlock_intent_handler import DoorlockIntentHandler
        
        # 创建模拟组件
        mock_face_handler = AsyncMock()
        mock_greeting_handler = AsyncMock()
        mock_session_manager = Mock()
        mock_notification = AsyncMock()
        mock_database = AsyncMock()
        mock_vllm = AsyncMock()
        
        # 模拟人脸识别成功
        mock_person = Mock()
        mock_person.id = 1
        mock_person.name = '张三'
        mock_person.relation_type = 'family'
        
        mock_face_handler.recognize_with_retry = AsyncMock(return_value={
            'success': True,
            'person': mock_person
        })
        
        # 创建会话
        from core.providers.doorlock.models import DoorlockSession
        test_session = DoorlockSession(
            session_id=f"{test_device_id}_test",
            device_id=test_device_id
        )
        mock_session_manager.create_session = Mock(return_value=test_session)
        mock_session_manager.cleanup_session = AsyncMock()
        
        # 创建处理器
        handler = DoorlockIntentHandler(
            face_recognition_handler=mock_face_handler,
            greeting_handler=mock_greeting_handler,
            session_manager=mock_session_manager,
            notification_service=mock_notification,
            doorlock_database=mock_database,
            vllm_provider=mock_vllm,
            config=test_config['doorlock']['intent_recognition']
        )
        
        # 模拟权限检查
        with patch.object(handler, '_check_access_permission', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True
            
            # 执行流程
            result = await handler.handle_visitor(
                device_id=test_device_id,
                conn=mock_esp32_conn,
                jpeg_data=test_jpeg_data
            )
            
            # 验证结果
            assert result['success'] is True
            assert result['action'] == 'door_opened'
            assert result['person_id'] == 1
            
            # 验证调用
            mock_face_handler.recognize_with_retry.assert_called_once()
            mock_greeting_handler.play_welcome_greeting.assert_called_once()
            mock_session_manager.cleanup_session.assert_called_once()
            
            print("✓ 有权限访客完整流程测试通过")
    
    @pytest.mark.asyncio
    async def test_visitor_without_permission_flow(
        self,
        test_config,
        test_device_id,
        test_jpeg_data,
        mock_esp32_conn
    ):
        """测试无权限访客的完整流程
        
        流程：
        1. PIR触发
        2. 拍照
        3. 人脸识别成功
        4. 检查权限（无权限）
        5. 启动意图识别对话
        6. 生成意图总结
        7. 发送App通知
        """
        from core.handle.doorlock_intent_handler import DoorlockIntentHandler
        
        # 创建模拟组件
        mock_face_handler = AsyncMock()
        mock_greeting_handler = AsyncMock()
        mock_session_manager = Mock()
        mock_notification = AsyncMock()
        mock_database = AsyncMock()
        mock_vllm = AsyncMock()
        
        # 模拟人脸识别成功但无权限
        mock_person = Mock()
        mock_person.id = 2
        mock_person.name = '李四'
        mock_person.relation_type = 'friend'
        
        mock_face_handler.recognize_with_retry = AsyncMock(return_value={
            'success': True,
            'person': mock_person
        })
        
        # 创建会话
        from core.providers.doorlock.models import DoorlockSession
        test_session = DoorlockSession(
            session_id=f"{test_device_id}_test",
            device_id=test_device_id
        )
        mock_session_manager.create_session = Mock(return_value=test_session)
        mock_session_manager.cleanup_session = AsyncMock()
        mock_session_manager.add_dialogue = Mock()
        mock_session_manager.get_dialogue_history = Mock(return_value=[])
        mock_session_manager.check_dialogue_end = AsyncMock(return_value=True)
        
        # 模拟数据库保存
        mock_database.save_visitor_intent = AsyncMock(return_value=123)
        
        # 创建处理器
        handler = DoorlockIntentHandler(
            face_recognition_handler=mock_face_handler,
            greeting_handler=mock_greeting_handler,
            session_manager=mock_session_manager,
            notification_service=mock_notification,
            doorlock_database=mock_database,
            vllm_provider=mock_vllm,
            config=test_config['doorlock']['intent_recognition']
        )
        
        # 模拟权限检查和其他方法
        with patch.object(handler, '_check_access_permission', new_callable=AsyncMock) as mock_check, \
             patch.object(handler, '_play_initial_greeting', new_callable=AsyncMock) as mock_greeting, \
             patch.object(handler, '_wait_for_visitor_response', new_callable=AsyncMock) as mock_wait:
            
            mock_check.return_value = False
            mock_greeting.return_value = '您好，请问您找谁？'
            mock_wait.return_value = None  # 模拟对话结束
            
            # 执行流程
            result = await handler.handle_visitor(
                device_id=test_device_id,
                conn=mock_esp32_conn,
                jpeg_data=test_jpeg_data
            )
            
            # 验证结果
            assert result['success'] is True
            assert result['action'] == 'intent_recognized'
            assert 'visit_id' in result
            
            # 验证调用
            mock_face_handler.recognize_with_retry.assert_called_once()
            mock_notification.notify_visitor_intent.assert_called_once()
            
            print("✓ 无权限访客完整流程测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
