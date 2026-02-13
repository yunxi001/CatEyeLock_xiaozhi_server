"""
门锁工具函数单元测试
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from core.providers.doorlock.doorlock_tools import DoorlockTools


class TestDoorlockTools:
    """工具函数测试"""
    
    @pytest.mark.asyncio
    async def test_report_package_status(self, mock_logger, mock_database):
        """测试报告快递状态工具"""
        tools = DoorlockTools(
            database=mock_database,
            notification_service=AsyncMock(),
            logger_instance=mock_logger
        )
        
        # 设置会话上下文
        tools.set_session_context('test_session_001', 'test_device_001')
        
        # 调用工具
        result = await tools.call_tool('report_package_status', {
            'action': 'taking',
            'threat_level': 'high',
            'description': '检测到陌生人拿走快递',
            'voice_warning': '您的行为已被记录'
        })
        
        assert result['success'] is True
        assert 'alert_id' in result
        print("✓ 报告快递状态工具测试通过")
    
    @pytest.mark.asyncio
    async def test_summarize_intent(self, mock_logger, mock_database):
        """测试总结访客意图工具"""
        tools = DoorlockTools(
            database=mock_database,
            notification_service=AsyncMock(),
            logger_instance=mock_logger
        )
        
        # 设置会话上下文
        tools.set_session_context('test_session_001', 'test_device_001')
        
        # 调用工具
        result = await tools.call_tool('summarize_intent', {
            'important_notes': ['【留言】明天再来'],
            'intent_type': 'visit',
            'purpose': '拜访朋友',
            'full_summary': '访客来拜访，主人不在'
        })
        
        assert result['success'] is True
        print("✓ 总结访客意图工具测试通过")
    
    def test_get_tools_schema(self):
        """测试获取工具Schema"""
        schema = DoorlockTools.get_tools_schema()
        
        assert isinstance(schema, list)
        assert len(schema) > 0
        
        # 检查Schema结构
        for tool in schema:
            assert 'type' in tool
            assert 'function' in tool
            assert 'name' in tool['function']
            assert 'description' in tool['function']
            assert 'parameters' in tool['function']
        
        print(f"✓ 获取工具Schema测试通过: {len(schema)} 个工具")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
