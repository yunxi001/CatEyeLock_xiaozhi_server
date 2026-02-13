"""
欢迎词处理器单元测试
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from core.providers.doorlock.greeting_handler import GreetingHandler


class TestGreetingHandler:
    """欢迎词处理器测试"""
    
    @pytest.mark.asyncio
    async def test_play_welcome_greeting(self, mock_logger, mock_config, mock_database):
        """测试播放欢迎词"""
        handler = GreetingHandler(mock_config, mock_logger)
        
        with patch.object(handler, 'db', mock_database):
            # 模拟获取欢迎词
            mock_database.get_person_greeting = AsyncMock(return_value='欢迎回家，张三')
            
            # 模拟TTS服务
            with patch.object(handler, '_play_tts', new_callable=AsyncMock) as mock_tts:
                await handler.play_welcome_greeting(
                    device_id='test_device_001',
                    person_id=1,
                    person_name='张三'
                )
                
                mock_tts.assert_called_once()
                print("✓ 播放欢迎词测试通过")
    
    @pytest.mark.asyncio
    async def test_update_greeting(self, mock_logger, mock_config, mock_database):
        """测试更新欢迎词"""
        handler = GreetingHandler(mock_config, mock_logger)
        
        with patch.object(handler, 'db', mock_database):
            mock_database.update_person_greeting = AsyncMock(return_value=True)
            
            result = await handler.update_greeting(
                person_id=1,
                greeting_text='新的欢迎词'
            )
            
            assert result is True
            mock_database.update_person_greeting.assert_called_once()
            print("✓ 更新欢迎词测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
