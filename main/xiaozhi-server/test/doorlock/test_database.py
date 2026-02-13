"""
门锁数据库服务单元测试
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from core.providers.doorlock.doorlock_database import DoorlockDatabase
from core.providers.doorlock.models import (
    DoorlockConfig,
    VisitorIntent,
    PackageAlert
)


class TestDoorlockDatabase:
    """数据库服务测试"""
    
    @pytest.mark.asyncio
    async def test_get_config(self, mock_logger):
        """测试获取设备配置"""
        db = DoorlockDatabase(mock_logger)
        
        # 模拟数据库查询
        with patch.object(db, '_execute_query', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [{
                'device_id': 'test_device_001',
                'intent_recognition_enabled': True,
                'package_guard_enabled': True,
                'package_guard_active': False
            }]
            
            config = await db.get_config('test_device_001')
            
            assert config is not None
            assert config.device_id == 'test_device_001'
            assert config.intent_recognition_enabled is True
            print("✓ 获取设备配置测试通过")
    
    @pytest.mark.asyncio
    async def test_save_visitor_intent(self, mock_logger):
        """测试保存访客意图"""
        db = DoorlockDatabase(mock_logger)
        
        intent = VisitorIntent(
            session_id='test_session_001',
            person_id=1,
            intent_type='visit',
            intent_summary={'test': 'data'},
            dialogue_history=[]
        )
        
        with patch.object(db, '_execute_insert', new_callable=AsyncMock) as mock_insert:
            mock_insert.return_value = 123
            
            visit_id = await db.save_visitor_intent(intent)
            
            assert visit_id == 123
            mock_insert.assert_called_once()
            print("✓ 保存访客意图测试通过")
    
    @pytest.mark.asyncio
    async def test_save_package_alert(self, mock_logger):
        """测试保存快递警报"""
        db = DoorlockDatabase(mock_logger)
        
        alert = PackageAlert(
            device_id='test_device_001',
            session_id='test_session_001',
            threat_level='high',
            action='taking',
            description='测试警报'
        )
        
        with patch.object(db, '_execute_insert', new_callable=AsyncMock) as mock_insert:
            mock_insert.return_value = 456
            
            alert_id = await db.save_package_alert(alert)
            
            assert alert_id == 456
            mock_insert.assert_called_once()
            print("✓ 保存快递警报测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
