"""
测试命令下发重试机制

验证 commandProxyHandler 中的重试逻辑是否正确实现
"""
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.handle.textHandler.commandProxyHandler import LockControlProxyHandler
from core.constants.error_codes import ErrorCode


async def test_forward_with_retry_success():
    """测试重试机制 - 成功场景"""
    print("\n=== 测试 1: 重试机制 - 第一次就成功 ===")
    
    handler = LockControlProxyHandler()
    
    # 模拟 App 连接
    app_conn = Mock()
    app_conn.logger = Mock()
    app_conn.logger.bind = Mock(return_value=app_conn.logger)
    app_conn.logger.debug = Mock()
    app_conn.logger.info = Mock()
    app_conn.logger.warning = Mock()
    app_conn.websocket = AsyncMock()
    
    # 模拟 ESP32 连接
    esp32_conn = Mock()
    esp32_conn.websocket = AsyncMock()
    esp32_conn._pending_esp32_acks = {}
    
    # 准备测试消息
    msg_json = {
        "type": "lock_control",
        "command": "unlock",
        "seq_id": "test_123"
    }
    
    # 模拟 esp32_ack 立即返回成功
    async def mock_wait_for_ack(esp32_conn, seq_id, timeout):
        # 模拟收到 esp32_ack (code=0)
        return True
    
    # 替换 _wait_for_esp32_ack 方法
    handler._wait_for_esp32_ack = mock_wait_for_ack
    
    # 执行测试
    success = await handler._forward_with_retry(app_conn, esp32_conn, msg_json)
    
    # 验证结果
    assert success == True, "应该返回 True（成功）"
    assert esp32_conn.websocket.send.call_count == 1, "应该只发送 1 次命令"
    print("✓ 第一次就成功，没有重试")


async def test_forward_with_retry_timeout_then_success():
    """测试重试机制 - 第一次超时，第二次成功"""
    print("\n=== 测试 2: 重试机制 - 第一次超时，第二次成功 ===")
    
    handler = LockControlProxyHandler()
    
    # 模拟 App 连接
    app_conn = Mock()
    app_conn.logger = Mock()
    app_conn.logger.bind = Mock(return_value=app_conn.logger)
    app_conn.logger.debug = Mock()
    app_conn.logger.info = Mock()
    app_conn.logger.warning = Mock()
    app_conn.websocket = AsyncMock()
    
    # 模拟 ESP32 连接
    esp32_conn = Mock()
    esp32_conn.websocket = AsyncMock()
    esp32_conn._pending_esp32_acks = {}
    
    # 准备测试消息
    msg_json = {
        "type": "lock_control",
        "command": "unlock",
        "seq_id": "test_456"
    }
    
    # 模拟第一次超时，第二次成功
    call_count = 0
    async def mock_wait_for_ack(esp32_conn, seq_id, timeout):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return False  # 第一次超时
        else:
            return True   # 第二次成功
    
    # 替换 _wait_for_esp32_ack 方法
    handler._wait_for_esp32_ack = mock_wait_for_ack
    
    # 执行测试
    success = await handler._forward_with_retry(app_conn, esp32_conn, msg_json)
    
    # 验证结果
    assert success == True, "应该返回 True（最终成功）"
    assert esp32_conn.websocket.send.call_count == 2, "应该发送 2 次命令（1次失败 + 1次成功）"
    print("✓ 第一次超时后重试，第二次成功")


async def test_forward_with_retry_all_timeout():
    """测试重试机制 - 全部超时"""
    print("\n=== 测试 3: 重试机制 - 全部超时（3次） ===")
    
    handler = LockControlProxyHandler()
    
    # 模拟 App 连接
    app_conn = Mock()
    app_conn.logger = Mock()
    app_conn.logger.bind = Mock(return_value=app_conn.logger)
    app_conn.logger.debug = Mock()
    app_conn.logger.info = Mock()
    app_conn.logger.warning = Mock()
    app_conn.websocket = AsyncMock()
    
    # 模拟 ESP32 连接
    esp32_conn = Mock()
    esp32_conn.websocket = AsyncMock()
    esp32_conn._pending_esp32_acks = {}
    
    # 准备测试消息
    msg_json = {
        "type": "lock_control",
        "command": "unlock",
        "seq_id": "test_789"
    }
    
    # 模拟全部超时
    async def mock_wait_for_ack(esp32_conn, seq_id, timeout):
        return False  # 始终超时
    
    # 替换 _wait_for_esp32_ack 方法
    handler._wait_for_esp32_ack = mock_wait_for_ack
    
    # 执行测试
    success = await handler._forward_with_retry(app_conn, esp32_conn, msg_json)
    
    # 验证结果
    assert success == False, "应该返回 False（全部失败）"
    assert esp32_conn.websocket.send.call_count == 3, "应该发送 3 次命令（全部超时）"
    assert app_conn.websocket.send.call_count == 1, "应该发送 1 次错误响应给 App"
    
    # 验证错误响应内容
    error_msg = json.loads(app_conn.websocket.send.call_args[0][0])
    assert error_msg["status"] == "error", "应该是错误状态"
    assert error_msg["code"] == ErrorCode.TIMEOUT, f"错误码应该是 {ErrorCode.TIMEOUT}（超时）"
    print("✓ 3次全部超时，返回错误给 App")


async def test_wait_for_esp32_ack_timeout():
    """测试 _wait_for_esp32_ack - 超时场景"""
    print("\n=== 测试 4: _wait_for_esp32_ack - 超时 ===")
    
    handler = LockControlProxyHandler()
    
    # 模拟 ESP32 连接
    esp32_conn = Mock()
    esp32_conn._pending_esp32_acks = {}
    
    # 执行测试（0.1秒超时）
    result = await handler._wait_for_esp32_ack(esp32_conn, "test_seq", timeout=0.1)
    
    # 验证结果
    assert result == False, "应该返回 False（超时）"
    assert "test_seq" not in esp32_conn._pending_esp32_acks, "Future 应该被清理"
    print("✓ 超时后返回 False，并清理 Future")


async def test_wait_for_esp32_ack_success():
    """测试 _wait_for_esp32_ack - 成功场景"""
    print("\n=== 测试 5: _wait_for_esp32_ack - 收到确认 ===")
    
    handler = LockControlProxyHandler()
    
    # 模拟 ESP32 连接
    esp32_conn = Mock()
    esp32_conn._pending_esp32_acks = {}
    
    # 创建一个任务来模拟 esp32_ack 的到达
    async def simulate_esp32_ack():
        await asyncio.sleep(0.05)  # 等待 50ms
        # 模拟 Esp32AckHandler 触发 Future
        if "test_seq" in esp32_conn._pending_esp32_acks:
            future = esp32_conn._pending_esp32_acks["test_seq"]
            if not future.done():
                future.set_result(True)
    
    # 同时启动两个任务
    ack_task = asyncio.create_task(simulate_esp32_ack())
    wait_task = asyncio.create_task(
        handler._wait_for_esp32_ack(esp32_conn, "test_seq", timeout=1.0)
    )
    
    # 等待结果
    result = await wait_task
    await ack_task
    
    # 验证结果
    assert result == True, "应该返回 True（收到确认）"
    assert "test_seq" not in esp32_conn._pending_esp32_acks, "Future 应该被清理"
    print("✓ 收到 esp32_ack 后返回 True，并清理 Future")


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("命令下发重试机制测试")
    print("=" * 60)
    
    try:
        await test_forward_with_retry_success()
        await test_forward_with_retry_timeout_then_success()
        await test_forward_with_retry_all_timeout()
        await test_wait_for_esp32_ack_timeout()
        await test_wait_for_esp32_ack_success()
        
        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
