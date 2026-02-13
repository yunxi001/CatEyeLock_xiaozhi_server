"""
看护模式管理器单元测试
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from core.providers.doorlock.package_guard_manager import PackageGuardManager


class TestPackageGuardManager:
    """看护模式管理器测试"""
    
    @pytest.mark.asyncio
    async def test_activate_guard(self, mock_logger, mock_config):
        """测试激活看护模式"""
        manager = PackageGuardManager(mock_config, mock_logger)
        
        device_id = 'test_device_001'
        baseline_image = 'baseline.jpg'
        
        with patch.object(manager, 'db') as mock_db:
            mock_db.update_config = AsyncMock(return_value=True)
            
            result = await manager.activate(device_id, baseline_image)
            
            assert result is True
            mock_db.update_config.assert_called_once()
            print("✓ 激活看护模式测试通过")
    
    @pytest.mark.asyncio
    async def test_deactivate_guard(self, mock_logger, mock_config):
        """测试停止看护模式"""
        manager = PackageGuardManager(mock_config, mock_logger)
        
        device_id = 'test_device_001'
        
        with patch.object(manager, 'db') as mock_db:
            mock_db.update_config = AsyncMock(return_value=True)
            
            result = await manager.deactivate(device_id, reason='用户手动停止')
            
            assert result is True
            mock_db.update_config.assert_called_once()
            print("✓ 停止看护模式测试通过")
    
    @pytest.mark.asyncio
    async def test_is_active(self, mock_logger, mock_config):
        """测试检查看护模式状态"""
        manager = PackageGuardManager(mock_config, mock_logger)
        
        device_id = 'test_device_001'
        
        with patch.object(manager, 'db') as mock_db:
            from core.providers.doorlock.models import DoorlockConfig
            
            mock_config_obj = DoorlockConfig(
                device_id=device_id,
                package_guard_active=True
            )
            mock_db.get_config = AsyncMock(return_value=mock_config_obj)
            
            is_active = await manager.is_active(device_id)
            
            assert is_active is True
            print("✓ 检查看护模式状态测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
