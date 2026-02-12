"""
门锁AI单元测试配置和fixtures
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from pathlib import Path
from datetime import datetime


@pytest.fixture
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_logger():
    """模拟日志实例"""
    logger = Mock()
    logger.bind = Mock(return_value=logger)
    logger.info = Mock()
    logger.debug = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
def mock_config():
    """模拟配置字典"""
    return {
        'doorlock': {
            'package_guard': {
                'photo_interval': 5,
                'baseline_dir': 'data/face_recognition/package_baseline/'
            },
            'intent_recognition': {
                'dialogue_timeout': 30,
                'max_dialogue_rounds': 10
            },
            'face_recognition': {
                'max_retries': 3,
                'retry_interval': 1
            },
            'performance': {
                'max_token_usage_ratio': 0.8,
                'session_cleanup_delay': 0
            }
        },
        'VLLM': {
            'test_vllm': {
                'model_name': 'test-model',
                'api_key': 'test-key',
                'base_url': 'http://localhost:8000',
                'max_tokens': 500,
                'temperature': 0.7,
                'top_p': 1.0
            }
        },
        'selected_module': {
            'VLLM': 'test_vllm'
        }
    }


@pytest.fixture
def mock_database():
    """模拟数据库服务"""
    db = AsyncMock()
    db.get_config = AsyncMock(return_value=None)
    db.update_config = AsyncMock(return_value=True)
    db.save_visitor_intent = AsyncMock(return_value=1)
    db.save_package_alert = AsyncMock(return_value=1)
    db.get_visitor_intents = AsyncMock(return_value=[])
    db.get_package_alerts = AsyncMock(return_value=[])
    db.get_person_greeting = AsyncMock(return_value=None)
    db.update_person_greeting = AsyncMock(return_value=True)
    return db


@pytest.fixture
def mock_session_manager():
    """模拟会话管理器"""
    from core.providers.doorlock.models import DoorlockSession
    
    manager = Mock()
    
    # 创建会话
    def create_session(device_id):
        session = DoorlockSession(
            session_id=f"{device_id}_{int(datetime.now().timestamp() * 1000)}",
            device_id=device_id
        )
        return session
    
    manager.create_session = Mock(side_effect=create_session)
    manager.get_session = Mock(return_value=None)
    manager.update_session = AsyncMock()
    manager.cleanup_session = AsyncMock()
    manager.check_dialogue_end = AsyncMock(return_value=False)
    manager.add_dialogue = Mock()
    manager.get_dialogue_history = Mock(return_value=[])
    
    return manager


@pytest.fixture
def mock_notification_service():
    """模拟通知服务"""
    service = AsyncMock()
    service.notify_visitor_intent = AsyncMock(return_value=True)
    service.notify_package_alert = AsyncMock(return_value=True)
    service.notify_guard_status_change = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_vllm_provider():
    """模拟VLLM提供者"""
    provider = AsyncMock()
    provider.analyze_intent = AsyncMock(return_value={
        "content": "测试回复",
        "tool_calls": [],
        "token_usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        },
        "response_time": 1.5
    })
    provider.analyze_package_status = AsyncMock(return_value={
        "content": "",
        "tool_calls": [{
            "id": "test_call_1",
            "name": "report_package_status",
            "arguments": {
                "action": "normal",
                "threat_level": "low",
                "description": "正常状态"
            }
        }],
        "token_usage": {
            "prompt_tokens": 200,
            "completion_tokens": 100,
            "total_tokens": 300
        },
        "response_time": 2.0
    })
    provider.execute_tool_calls = AsyncMock(return_value=[])
    provider.max_tokens = 500
    return provider


@pytest.fixture
def sample_jpeg_data():
    """示例JPEG数据"""
    # 最小的有效JPEG文件头
    return b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9'


@pytest.fixture
def sample_person_info():
    """示例人员信息"""
    return {
        "person_id": 1,
        "name": "张三",
        "relation_type": "family",
        "has_permission": True
    }


@pytest.fixture
def sample_intent_summary():
    """示例意图总结"""
    return {
        "important_notes": ["【留言】明天下午3点再来"],
        "intent_type": "visit",
        "purpose": "拜访朋友",
        "full_summary": "访客张三来拜访，主人不在家。访客表示明天下午3点会再来。"
    }


@pytest.fixture
def sample_dialogue_history():
    """示例对话历史"""
    return [
        {"role": "assistant", "content": "您好，请问您找谁？"},
        {"role": "user", "content": "我找李四，他在家吗？"},
        {"role": "assistant", "content": "主人不在家，请问有什么可以帮您？"},
        {"role": "user", "content": "那我明天下午3点再来吧"}
    ]
