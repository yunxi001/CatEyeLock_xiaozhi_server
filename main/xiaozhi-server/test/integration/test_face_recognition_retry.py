"""
人脸识别重试流程集成测试
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch


class TestFaceRecognitionRetry:
    """人脸识别重试流程测试"""
    
    @pytest.mark.asyncio
    async def test_retry_until_success(
        self,
        test_config,
        test_device_id,
        test_jpeg_data
    ):
        """测试重试直到成功
        
        流程：
        1. 第一次识别失败
        2. 等待1秒
        3. 第二次识别成功
        """
        from core.providers.doorlock.face_recognition_handler import FaceRecognitionHandler
        
        handler = FaceRecognitionHandler(test_config, Mock())
        
        # 模拟识别服务
        with patch.object(handler, 'recognize', new_callable=AsyncMock) as mock_recognize:
            # 第一次失败，第二次成功
            mock_person = Mock()
            mock_person.id = 1
            mock_person.name = '张三'
            
            mock_recognize.side_effect = [
                {'success': False, 'error': '识别失败'},
                {'success': True, 'person': mock_person}
            ]
            
            # 执行重试
            result = await handler.recognize_with_retry(
                device_id=test_device_id,
                jpeg_data=test_jpeg_data
            )
            
            # 验证结果
            assert result['success'] is True
            assert result['person'].name == '张三'
            assert mock_recognize.call_count == 2
            
            print("✓ 人脸识别重试成功测试通过")
    
    @pytest.mark.asyncio
    async def test_retry_max_attempts(
        self,
        test_config,
        test_device_id,
        test_jpeg_data
    ):
        """测试达到最大重试次数
        
        流程：
        1. 第一次识别失败
        2. 第二次识别失败
        3. 第三次识别失败
        4. 返回失败结果
        """
        from core.providers.doorlock.face_recognition_handler import FaceRecognitionHandler
        
        handler = FaceRecognitionHandler(test_config, Mock())
        
        # 模拟识别服务
        with patch.object(handler, 'recognize', new_callable=AsyncMock) as mock_recognize:
            # 所有尝试都失败
            mock_recognize.return_value = {'success': False, 'error': '识别失败'}
            
            # 执行重试
            result = await handler.recognize_with_retry(
                device_id=test_device_id,
                jpeg_data=test_jpeg_data
            )
            
            # 验证结果
            assert result['success'] is False
            assert mock_recognize.call_count == 3  # 最大重试次数
            
            print("✓ 人脸识别达到最大重试次数测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
