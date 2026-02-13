"""
看护模式流程集成测试

测试看护模式的启动、监控、警报完整流程
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch


class TestPackageGuardFlow:
    """看护模式流程集成测试"""
    
    @pytest.mark.asyncio
    async def test_activate_guard_flow(
        self,
        test_config,
        test_device_id,
        test_jpeg_data
    ):
        """测试激活看护模式流程
        
        流程：
        1. 用户通过App请求激活看护模式
        2. 拍摄基准照片
        3. 保存基准照片
        4. 更新数据库配置
        5. 发送状态变化通知
        """
        from core.providers.doorlock.package_guard_manager import PackageGuardManager
        from core.providers.doorlock.esp32_camera import ESP32CameraService
        from core.providers.doorlock.notification_service import NotificationService
        
        # 创建服务
        guard_manager = PackageGuardManager(test_config, Mock())
        camera_service = ESP32CameraService(test_config, Mock())
        notification_service = NotificationService()
        
        # 模拟数据库和通知
        with patch.object(guard_manager, 'db') as mock_db, \
             patch.object(notification_service, '_send_notification', new_callable=AsyncMock) as mock_notify:
            
            mock_db.update_config = AsyncMock(return_value=True)
            mock_notify.return_value = True
            
            # 保存基准图片
            baseline_path = await camera_service.save_baseline_image(
                device_id=test_device_id,
                image_data=test_jpeg_data
            )
            
            # 激活看护模式
            result = await guard_manager.activate(
                device_id=test_device_id,
                baseline_image=baseline_path
            )
            
            assert result is True
            mock_db.update_config.assert_called_once()
            
            # 发送状态变化通知
            notify_result = await notification_service.notify_guard_status_change(
                device_id=test_device_id,
                active=True,
                reason='用户手动激活',
                baseline_image=baseline_path
            )
            
            assert notify_result is True
            print("✓ 激活看护模式流程测试通过")
    
    @pytest.mark.asyncio
    async def test_package_monitoring_flow(
        self,
        test_config,
        test_device_id,
        test_jpeg_data
    ):
        """测试看护监控流程
        
        流程：
        1. 看护模式已激活
        2. PIR触发
        3. 拍摄当前照片
        4. VLLM对比分析（当前图片 vs 基准图片）
        5. 检测到威胁
        6. 保存警报记录
        7. 发送警报通知
        8. 播放语音警告
        """
        from core.providers.vllm.doorlock_vllm import DoorlockVLLMProvider
        from core.providers.doorlock.doorlock_database import DoorlockDatabase
        from core.providers.doorlock.notification_service import NotificationService
        
        # 创建模拟VLLM提供者
        mock_vllm = AsyncMock()
        mock_vllm.analyze_package_status = AsyncMock(return_value={
            'content': '',
            'tool_calls': [{
                'id': 'call_1',
                'name': 'report_package_status',
                'arguments': {
                    'action': 'taking',
                    'threat_level': 'high',
                    'description': '检测到陌生人拿走快递',
                    'voice_warning': '您的行为已被记录，请立即停止'
                }
            }],
            'token_usage': {'total_tokens': 300},
            'response_time': 2.0
        })
        
        # 创建服务
        mock_db = AsyncMock()
        mock_db.save_package_alert = AsyncMock(return_value=456)
        
        notification_service = NotificationService()
        
        # 模拟通知发送
        with patch.object(notification_service, '_send_notification', new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = True
            
            # 执行VLLM分析
            import base64
            current_image = base64.b64encode(test_jpeg_data).decode('utf-8')
            baseline_image = base64.b64encode(test_jpeg_data).decode('utf-8')
            
            vllm_result = await mock_vllm.analyze_package_status(
                current_image=current_image,
                baseline_image=baseline_image,
                dialogue_history=[]
            )
            
            # 验证工具调用
            assert len(vllm_result['tool_calls']) > 0
            tool_call = vllm_result['tool_calls'][0]
            assert tool_call['name'] == 'report_package_status'
            assert tool_call['arguments']['threat_level'] == 'high'
            
            # 保存警报
            from core.providers.doorlock.models import PackageAlert
            alert = PackageAlert(
                device_id=test_device_id,
                session_id=f"{test_device_id}_guard",
                threat_level=tool_call['arguments']['threat_level'],
                action=tool_call['arguments']['action'],
                description=tool_call['arguments']['description']
            )
            
            alert_id = await mock_db.save_package_alert(alert)
            assert alert_id == 456
            
            # 发送警报通知
            notify_result = await notification_service.notify_package_alert(
                alert_id=alert_id,
                session_id=alert.session_id,
                threat_level=alert.threat_level,
                action=alert.action,
                description=alert.description,
                photo_path='test_photo.jpg',
                voice_warning_text=tool_call['arguments'].get('voice_warning')
            )
            
            assert notify_result is True
            print("✓ 看护监控流程测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
