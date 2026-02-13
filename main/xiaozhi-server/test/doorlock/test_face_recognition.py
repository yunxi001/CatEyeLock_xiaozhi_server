"""
人脸识别处理器单元测试
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from core.providers.doorlock.face_recognition_handler import FaceRecognitionHandler


class TestFaceRecognitionHandler:
    """人脸识别处理器测试"""
    
    @pytest.mark.asyncio
    async def test_recognize_success(self, mock_logger, mock_config, sample_jpeg_data):
        """测试人脸识别成功"""
        handler = FaceRecognitionHandler(mock_config, mock_logger)
        
        with patch.object(handler, 'face_service') as mock_face_service:
            # 模拟识别成功
            mock_person = Mock()
            mock_person.id = 1
            mock_person.name = '张三'
            mock_person.relation_type = 'family'
            
            mock_face_service.recognize_face = AsyncMock(return_value={
                'success': True,
                'person': mock_person
            })
            
            result = await handler.recognize(
                device_id='test_device_001',
                jpeg_data=sample_jpeg_data
            )
            
            assert result['success'] is True
            assert result['person'] is not None
            assert result['person'].name == '张三'
            print("✓ 人脸识别成功测试通过")
    
    @pytest.mark.asyncio
    async def test_recognize_with_retry(self, mock_logger, mock_config, sample_jpeg_data):
        """测试人脸识别重试"""
        handler = FaceRecognitionHandler(mock_config, mock_logger)
        
        with patch.object(handler, 'recognize', new_callable=AsyncMock) as mock_recognize:
            # 第一次失败，第二次成功
            mock_person = Mock()
            mock_person.id = 1
            mock_person.name = '张三'
            
            mock_recognize.side_effect = [
                {'success': False, 'error': '识别失败'},
                {'success': True, 'person': mock_person}
            ]
            
            result = await handler.recognize_with_retry(
                device_id='test_device_001',
                jpeg_data=sample_jpeg_data
            )
            
            assert result['success'] is True
            assert mock_recognize.call_count == 2
            print("✓ 人脸识别重试测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
