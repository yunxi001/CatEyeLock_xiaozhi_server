"""
集成测试配置和fixtures
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock


@pytest.fixture
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config():
    """测试配置"""
    return {
        'doorlock': {
            'package_guard': {
                'photo_interval': 5,
                'baseline_dir': 'data/test/package_baseline/'
            },
            'intent_recognition': {
                'dialogue_timeout': 30,
                'max_dialogue_rounds': 10
            },
            'face_recognition': {
                'max_retries': 3,
                'retry_interval': 1
            }
        },
        'VLLM': {
            'test_vllm': {
                'model_name': 'test-model',
                'api_key': 'test-key',
                'base_url': 'http://localhost:8000',
                'max_tokens': 500
            }
        },
        'selected_module': {
            'VLLM': 'test_vllm'
        }
    }


@pytest.fixture
def test_device_id():
    """测试设备ID"""
    return 'test_device_integration_001'


@pytest.fixture
def test_jpeg_data():
    """测试JPEG数据"""
    return b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9'


@pytest.fixture
def mock_esp32_conn():
    """模拟ESP32连接"""
    conn = Mock()
    conn.device_id = 'test_device_integration_001'
    conn.websocket = AsyncMock()
    conn.logger = Mock()
    conn.logger.bind = Mock(return_value=conn.logger)
    conn.logger.info = Mock()
    conn.logger.debug = Mock()
    conn.logger.warning = Mock()
    conn.logger.error = Mock()
    return conn
