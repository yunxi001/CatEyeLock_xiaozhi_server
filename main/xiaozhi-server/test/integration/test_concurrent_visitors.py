"""
并发访客处理集成测试

测试多个设备同时有访客到访的情况
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch


class TestConcurrentVisitors:
    """并发访客处理测试"""
    
    @pytest.mark.asyncio
    async def test_multiple_devices_concurrent(
        self,
        test_config,
        test_jpeg_data
    ):
        """测试多个设备并发处理访客
        
        场景：
        - 设备A有访客（有权限）
        - 设备B有访客（无权限）
        - 设备C有访客（陌生人）
        - 三个设备同时处理
        """
        from core.handle.doorlock_intent_handler import DoorlockIntentHandler
        
        # 创建三个设备的处理器
        devices = ['device_a', 'device_b', 'device_c']
        handlers = []
        
        for device_id in devices:
            # 创建模拟组件
            mock_face_handler = AsyncMock()
            mock_greeting_handler = AsyncMock()
            mock_session_manager = Mock()
            mock_notification = AsyncMock()
            mock_database = AsyncMock()
            mock_vllm = AsyncMock()
            
            # 创建会话
            from core.providers.doorlock.models import DoorlockSession
            test_session = DoorlockSession(
                session_id=f"{device_id}_test",
                device_id=device_id
            )
            mock_session_manager.create_session = Mock(return_value=test_session)
            mock_session_manager.cleanup_session = AsyncMock()
            
            handler = DoorlockIntentHandler(
                face_recognition_handler=mock_face_handler,
                greeting_handler=mock_greeting_handler,
                session_manager=mock_session_manager,
                notification_service=mock_notification,
                doorlock_database=mock_database,
                vllm_provider=mock_vllm,
                config=test_config['doorlock']['intent_recognition']
            )
            
            handlers.append({
                'device_id': device_id,
                'handler': handler,
                'face_handler': mock_face_handler,
                'session_manager': mock_session_manager
            })
        
        # 设置不同的识别结果
        # 设备A：有权限
        mock_person_a = Mock()
        mock_person_a.id = 1
        mock_person_a.name = '张三'
        handlers[0]['face_handler'].recognize_with_retry = AsyncMock(return_value={
            'success': True,
            'person': mock_person_a
        })
        
        # 设备B：无权限
        mock_person_b = Mock()
        mock_person_b.id = 2
        mock_person_b.name = '李四'
        handlers[1]['face_handler'].recognize_with_retry = AsyncMock(return_value={
            'success': True,
            'person': mock_person_b
        })
        handlers[1]['session_manager'].check_dialogue_end = AsyncMock(return_value=True)
        handlers[1]['session_manager'].add_dialogue = Mock()
        handlers[1]['session_manager'].get_dialogue_history = Mock(return_value=[])
        
        # 设备C：陌生人
        handlers[2]['face_handler'].recognize_with_retry = AsyncMock(return_value={
            'success': False,
            'error': '未识别'
        })
        handlers[2]['session_manager'].check_dialogue_end = AsyncMock(return_value=True)
        handlers[2]['session_manager'].add_dialogue = Mock()
        handlers[2]['session_manager'].get_dialogue_history = Mock(return_value=[])
        
        # 并发执行
        async def process_visitor(handler_info):
            handler = handler_info['handler']
            device_id = handler_info['device_id']
            
            # 模拟权限检查
            with patch.object(handler, '_check_access_permission', new_callable=AsyncMock) as mock_check, \
                 patch.object(handler, '_play_initial_greeting', new_callable=AsyncMock) as mock_greeting, \
                 patch.object(handler, '_wait_for_visitor_response', new_callable=AsyncMock) as mock_wait:
                
                # 设备A有权限，设备B和C无权限
                mock_check.return_value = (device_id == 'device_a')
                mock_greeting.return_value = '您好'
                mock_wait.return_value = None
                
                result = await handler.handle_visitor(
                    device_id=device_id,
                    jpeg_data=test_jpeg_data
                )
                
                return {
                    'device_id': device_id,
                    'result': result
                }
        
        # 并发处理所有设备
        tasks = [process_visitor(h) for h in handlers]
        results = await asyncio.gather(*tasks)
        
        # 验证结果
        assert len(results) == 3
        
        # 设备A应该开门
        device_a_result = next(r for r in results if r['device_id'] == 'device_a')
        assert device_a_result['result']['success'] is True
        assert device_a_result['result']['action'] == 'door_opened'
        
        # 设备B和C应该进行意图识别
        device_b_result = next(r for r in results if r['device_id'] == 'device_b')
        assert device_b_result['result']['success'] is True
        assert device_b_result['result']['action'] == 'intent_recognized'
        
        device_c_result = next(r for r in results if r['device_id'] == 'device_c')
        assert device_c_result['result']['success'] is True
        assert device_c_result['result']['action'] == 'intent_recognized'
        
        print("✓ 多设备并发处理访客测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
