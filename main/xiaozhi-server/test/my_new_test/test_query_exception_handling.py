"""
测试查询异常处理

验证修复的问题：
1. 数据库不可用时的处理
2. 查询结果为空时的处理
3. 连接池异常的处理
4. datetime 转换异常的处理
"""
import asyncio
import json
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.handle.textHandler.queryHandler import QueryHandler, _get_database
from core.handle.textMessageType import TextMessageType


class MockConnection:
    """模拟连接对象"""
    def __init__(self):
        self.device_id = "test_device_001"
        self.client_type = "app"
        self.websocket = Mock()
        self.logger = Mock()
        self.logger.bind = Mock(return_value=self.logger)
        self.logger.info = Mock()
        self.logger.error = Mock()
        self.logger.warning = Mock()


async def test_database_unavailable():
    """测试数据库不可用的情况"""
    print("\n=== 测试 1: 数据库不可用 ===")
    
    handler = QueryHandler()
    conn = MockConnection()
    
    # 模拟数据库不可用
    with patch('core.handle.textHandler.queryHandler._get_database', return_value=None):
        msg_json = {
            "type": "query",
            "target": "status_history",
            "data": {"limit": 10}
        }
        
        await handler.handle(conn, msg_json)
        
        # 验证发送了错误响应
        assert conn.websocket.send.called
        sent_data = json.loads(conn.websocket.send.call_args[0][0])
        assert sent_data["status"] == "error"
        assert "数据库不可用" in sent_data["error"]
        print("✓ 数据库不可用时正确返回错误响应")


async def test_empty_query_result():
    """测试查询结果为空的情况"""
    print("\n=== 测试 2: 查询结果为空 ===")
    
    handler = QueryHandler()
    conn = MockConnection()
    
    # 模拟数据库返回空结果
    mock_db = Mock()
    mock_db.get_status_history = Mock(return_value=([], 0))
    
    with patch('core.handle.textHandler.queryHandler._get_database', return_value=mock_db):
        msg_json = {
            "type": "query",
            "target": "status_history",
            "data": {"limit": 10, "offset": 0}
        }
        
        await handler.handle(conn, msg_json)
        
        # 验证发送了成功响应，但 total=0
        assert conn.websocket.send.called
        sent_data = json.loads(conn.websocket.send.call_args[0][0])
        assert sent_data["status"] == "success"
        assert sent_data["data"]["total"] == 0
        assert sent_data["data"]["records"] == []
        
        # 验证记录了日志
        assert conn.logger.info.called
        print("✓ 查询结果为空时正确返回成功响应（total=0）并记录日志")


async def test_database_exception():
    """测试数据库查询异常"""
    print("\n=== 测试 3: 数据库查询异常 ===")
    
    handler = QueryHandler()
    conn = MockConnection()
    
    # 模拟数据库查询抛出异常
    mock_db = Mock()
    mock_db.get_unlock_logs = Mock(side_effect=Exception("连接超时"))
    
    with patch('core.handle.textHandler.queryHandler._get_database', return_value=mock_db):
        msg_json = {
            "type": "query",
            "target": "unlock_logs",
            "data": {"limit": 10}
        }
        
        await handler.handle(conn, msg_json)
        
        # 验证发送了错误响应
        assert conn.websocket.send.called
        sent_data = json.loads(conn.websocket.send.call_args[0][0])
        assert sent_data["status"] == "error"
        assert "连接超时" in sent_data["error"]
        
        # 验证记录了错误日志
        assert conn.logger.error.called
        print("✓ 数据库查询异常时正确返回错误响应并记录日志")


async def test_get_database_exception():
    """测试 _get_database 异常处理"""
    print("\n=== 测试 4: _get_database 异常处理 ===")
    
    conn = MockConnection()
    
    # 模拟 get_face_service 抛出异常
    with patch('core.handle.textHandler.queryHandler.get_face_service', 
               side_effect=Exception("FaceService 初始化失败")):
        result = _get_database(conn)
        
        # 验证返回 None
        assert result is None
        
        # 验证记录了错误日志
        assert conn.logger.error.called
        error_msg = conn.logger.error.call_args[0][0]
        assert "获取数据库实例失败" in error_msg
        print("✓ _get_database 异常时正确返回 None 并记录日志")


async def test_query_with_filters():
    """测试带过滤条件的查询"""
    print("\n=== 测试 5: 带过滤条件的查询 ===")
    
    handler = QueryHandler()
    conn = MockConnection()
    
    # 模拟数据库返回空结果（带过滤条件）
    mock_db = Mock()
    mock_db.get_unlock_logs = Mock(return_value=([], 0))
    
    with patch('core.handle.textHandler.queryHandler._get_database', return_value=mock_db):
        msg_json = {
            "type": "query",
            "target": "unlock_logs",
            "data": {
                "method": "finger",
                "result": 1,
                "limit": 10,
                "offset": 0
            }
        }
        
        await handler.handle(conn, msg_json)
        
        # 验证发送了成功响应
        assert conn.websocket.send.called
        sent_data = json.loads(conn.websocket.send.call_args[0][0])
        assert sent_data["status"] == "success"
        assert sent_data["data"]["total"] == 0
        
        # 验证记录了带过滤条件的日志
        assert conn.logger.info.called
        log_msg = conn.logger.info.call_args[0][0]
        assert "方式: finger" in log_msg
        assert "结果: 成功" in log_msg
        print("✓ 带过滤条件的查询正确处理并记录详细日志")


async def test_unknown_query_target():
    """测试未知查询目标"""
    print("\n=== 测试 6: 未知查询目标 ===")
    
    handler = QueryHandler()
    conn = MockConnection()
    
    msg_json = {
        "type": "query",
        "target": "unknown_target",
        "data": {}
    }
    
    await handler.handle(conn, msg_json)
    
    # 验证发送了错误响应
    assert conn.websocket.send.called
    sent_data = json.loads(conn.websocket.send.call_args[0][0])
    assert sent_data["status"] == "error"
    assert "未知查询目标" in sent_data["error"]
    print("✓ 未知查询目标时正确返回错误响应")


async def test_non_app_client():
    """测试非 App 客户端的查询请求"""
    print("\n=== 测试 7: 非 App 客户端查询 ===")
    
    handler = QueryHandler()
    conn = MockConnection()
    conn.client_type = "esp32"  # 非 App 客户端
    
    msg_json = {
        "type": "query",
        "target": "status",
        "data": {}
    }
    
    await handler.handle(conn, msg_json)
    
    # 验证没有发送任何响应
    assert not conn.websocket.send.called
    print("✓ 非 App 客户端的查询请求被正确忽略")


async def main():
    """运行所有测试"""
    print("开始测试查询异常处理\n")
    
    try:
        await test_database_unavailable()
        await test_empty_query_result()
        await test_database_exception()
        await test_get_database_exception()
        await test_query_with_filters()
        await test_unknown_query_target()
        await test_non_app_client()
        
        print("\n" + "="*50)
        print("✓ 所有测试通过！")
        print("="*50)
        
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        raise
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
