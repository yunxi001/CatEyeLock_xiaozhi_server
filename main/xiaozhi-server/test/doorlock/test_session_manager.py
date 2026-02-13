"""
会话管理器单元测试
"""
import pytest
import asyncio
from unittest.mock import Mock
from datetime import datetime

from core.providers.doorlock.session_manager import SessionManager
from core.providers.doorlock.models import DoorlockSession


class TestSessionManager:
    """会话管理器测试"""
    
    def test_create_session(self, mock_logger):
        """测试创建会话"""
        manager = SessionManager(mock_logger)
        
        device_id = 'test_device_001'
        session = manager.create_session(device_id)
        
        assert session is not None
        assert session.device_id == device_id
        assert session.session_id.startswith(device_id)
        assert session.dialogue_history == []
        print(f"✓ 创建会话测试通过: {session.session_id}")
    
    def test_add_dialogue(self, mock_logger):
        """测试添加对话"""
        manager = SessionManager(mock_logger)
        
        session = manager.create_session('test_device_001')
        session_id = session.session_id
        
        # 添加对话
        manager.add_dialogue(session_id, 'assistant', '您好，请问您找谁？')
        manager.add_dialogue(session_id, 'user', '我找李四')
        
        # 获取对话历史
        history = manager.get_dialogue_history(session_id)
        
        assert len(history) == 2
        assert history[0]['role'] == 'assistant'
        assert history[1]['role'] == 'user'
        print("✓ 添加对话测试通过")
    
    @pytest.mark.asyncio
    async def test_check_dialogue_end(self, mock_logger):
        """测试检查对话结束"""
        manager = SessionManager(mock_logger)
        
        session = manager.create_session('test_device_001')
        session_id = session.session_id
        
        # 刚创建的会话不应该结束
        should_end = await manager.check_dialogue_end(session_id, pir_detected=True)
        assert should_end is False
        
        # 模拟超时
        session.last_activity = datetime.fromtimestamp(0)
        should_end = await manager.check_dialogue_end(session_id, pir_detected=False)
        assert should_end is True
        print("✓ 检查对话结束测试通过")
    
    @pytest.mark.asyncio
    async def test_cleanup_session(self, mock_logger):
        """测试清理会话"""
        manager = SessionManager(mock_logger)
        
        session = manager.create_session('test_device_001')
        session_id = session.session_id
        
        # 清理会话
        await manager.cleanup_session(session_id)
        
        # 会话应该被移除
        retrieved_session = manager.get_session(session_id)
        assert retrieved_session is None
        print("✓ 清理会话测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
