"""
验证 EventReportHandler 对新增事件类型的支持

测试场景：
1. 验证 door_closed 事件处理
2. 验证 lock_success 事件处理
3. 验证 bolt_alarm 事件处理
4. 验证未知事件类型的警告处理
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
from unittest.mock import Mock, AsyncMock, patch
from core.handle.textHandler.eventReportHandler import EventReportHandler
from core.handle.textMessageType import TextMessageType


def create_mock_conn():
    """创建模拟的连接对象"""
    conn = Mock()
    conn.device_id = "test_device_001"
    conn.logger = Mock()
    conn.logger.bind = Mock(return_value=conn.logger)
    conn.logger.info = Mock()
    conn.logger.warning = Mock()
    conn.logger.error = Mock()
    return conn


async def test_door_closed_event():
    """测试 door_closed 事件处理"""
    print("\n=== 测试 door_closed 事件 ===")
    
    handler = EventReportHandler()
    conn = create_mock_conn()
    
    msg_json = {
        "type": "event_report",
        "ts": 1702234567890,
        "event": "door_closed",
        "param": 0
    }
    
    with patch('core.handle.textHandler.eventReportHandler._get_database', return_value=None):
        with patch.object(handler, '_forward_to_apps', new_callable=AsyncMock) as mock_forward:
            await handler.handle(conn, msg_json)
            
            # 验证日志记录
            assert conn.logger.info.called, "应该记录 INFO 日志"
            
            # 验证消息转发
            assert mock_forward.called, "应该转发消息到 App"
            
            print("✓ door_closed 事件处理正确")


async def test_lock_success_event():
    """测试 lock_success 事件处理"""
    print("\n=== 测试 lock_success 事件 ===")
    
    handler = EventReportHandler()
    conn = create_mock_conn()
    
    msg_json = {
        "type": "event_report",
        "ts": 1702234567890,
        "event": "lock_success",
        "param": 0
    }
    
    with patch('core.handle.textHandler.eventReportHandler._get_database', return_value=None):
        with patch.object(handler, '_forward_to_apps', new_callable=AsyncMock) as mock_forward:
            await handler.handle(conn, msg_json)
            
            # 验证日志记录
            assert conn.logger.info.called, "应该记录 INFO 日志"
            
            # 验证消息转发
            assert mock_forward.called, "应该转发消息到 App"
            
            print("✓ lock_success 事件处理正确")


async def test_bolt_alarm_event():
    """测试 bolt_alarm 事件处理"""
    print("\n=== 测试 bolt_alarm 事件 ===")
    
    handler = EventReportHandler()
    conn = create_mock_conn()
    
    msg_json = {
        "type": "event_report",
        "ts": 1702234567890,
        "event": "bolt_alarm",
        "param": 1
    }
    
    with patch('core.handle.textHandler.eventReportHandler._get_database', return_value=None):
        with patch.object(handler, '_forward_to_apps', new_callable=AsyncMock) as mock_forward:
            await handler.handle(conn, msg_json)
            
            # 验证日志记录（应该是 WARNING 级别）
            assert conn.logger.warning.called, "应该记录 WARNING 日志"
            
            # 验证消息转发
            assert mock_forward.called, "应该转发消息到 App"
            
            print("✓ bolt_alarm 事件处理正确")


async def test_unknown_event_type():
    """测试未知事件类型的处理"""
    print("\n=== 测试未知事件类型 ===")
    
    handler = EventReportHandler()
    conn = create_mock_conn()
    
    msg_json = {
        "type": "event_report",
        "ts": 1702234567890,
        "event": "unknown_event",
        "param": 0
    }
    
    with patch('core.handle.textHandler.eventReportHandler._get_database', return_value=None):
        with patch.object(handler, '_forward_to_apps', new_callable=AsyncMock) as mock_forward:
            await handler.handle(conn, msg_json)
            
            # 验证警告日志
            warning_calls = [call for call in conn.logger.warning.call_args_list 
                           if "未知事件类型" in str(call)]
            assert len(warning_calls) > 0, "应该记录未知事件类型的警告"
            
            # 验证仍然转发消息
            assert mock_forward.called, "即使是未知事件类型，也应该转发消息"
            
            print("✓ 未知事件类型处理正确（记录警告但仍转发）")


async def test_valid_events_list():
    """测试 valid_events 列表包含所有事件类型"""
    print("\n=== 测试 valid_events 列表 ===")
    
    handler = EventReportHandler()
    conn = create_mock_conn()
    
    # 测试所有有效事件类型
    valid_events = [
        "bell", "pir_trigger", "tamper", "door_open", "low_battery",
        "door_closed", "lock_success", "bolt_alarm"
    ]
    
    for event in valid_events:
        msg_json = {
            "type": "event_report",
            "ts": 1702234567890,
            "event": event,
            "param": 0
        }
        
        with patch('core.handle.textHandler.eventReportHandler._get_database', return_value=None):
            with patch.object(handler, '_forward_to_apps', new_callable=AsyncMock):
                await handler.handle(conn, msg_json)
                
                # 验证没有记录"未知事件类型"的警告
                warning_calls = [call for call in conn.logger.warning.call_args_list 
                               if "未知事件类型" in str(call)]
                assert len(warning_calls) == 0, f"事件 {event} 不应该被标记为未知"
    
    print(f"✓ 所有 {len(valid_events)} 个事件类型都被正确识别")


async def test_database_storage():
    """测试数据库存储功能"""
    print("\n=== 测试数据库存储 ===")
    
    handler = EventReportHandler()
    conn = create_mock_conn()
    
    # 创建模拟数据库
    mock_db = Mock()
    mock_db.save_device_event = Mock()
    
    msg_json = {
        "type": "event_report",
        "ts": 1702234567890,
        "event": "door_closed",
        "param": 0
    }
    
    with patch('core.handle.textHandler.eventReportHandler._get_database', return_value=mock_db):
        with patch.object(handler, '_forward_to_apps', new_callable=AsyncMock):
            await handler.handle(conn, msg_json)
            
            # 验证调用了 save_device_event
            assert mock_db.save_device_event.called, "应该调用 save_device_event"
            
            # 验证参数
            call_args = mock_db.save_device_event.call_args
            assert call_args[1]['device_id'] == "test_device_001"
            assert call_args[1]['event_type'] == "door_closed"
            assert call_args[1]['param'] == 0
            
            print("✓ 数据库存储调用正确")


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("EventReportHandler 新增事件类型验证")
    print("=" * 60)
    
    try:
        await test_door_closed_event()
        await test_lock_success_event()
        await test_bolt_alarm_event()
        await test_unknown_event_type()
        await test_valid_events_list()
        await test_database_storage()
        
        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
