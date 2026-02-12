"""门锁AI功能HTTP API测试脚本

测试所有门锁相关的HTTP API接口
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.api.doorlock_config_handler import DoorlockConfigHandler
from core.api.doorlock_guard_handler import DoorlockGuardHandler
from core.api.doorlock_welcome_handler import DoorlockWelcomeHandler
from core.api.doorlock_history_handler import DoorlockHistoryHandler
from core.providers.doorlock.doorlock_database import DoorlockDatabase
from core.providers.doorlock.models import DoorlockConfig, VisitorIntent, PackageAlert
from config.config_loader import load_config
from loguru import logger
from datetime import datetime


class MockRequest:
    """模拟HTTP请求对象"""
    
    def __init__(self, query_params=None, json_data=None):
        self.query = query_params or {}
        self._json_data = json_data or {}
    
    async def json(self):
        return self._json_data


async def test_config_api():
    """测试设备配置API"""
    logger.info("=" * 60)
    logger.info("测试设备配置API")
    logger.info("=" * 60)
    
    config = load_config()
    handler = DoorlockConfigHandler(config)
    db = DoorlockDatabase(config)
    
    test_device_id = "test_device_001"
    
    # 1. 创建测试配置
    logger.info("1. 创建测试设备配置...")
    test_config = DoorlockConfig(
        device_id=test_device_id,
        intent_recognition_enabled=True,
        package_guard_available=True,
        package_guard_active=False
    )
    await db.update_config(test_config)
    
    # 2. 测试GET请求 - 获取配置
    logger.info("2. 测试GET /api/doorlock/config...")
    request = MockRequest(query_params={"device_id": test_device_id})
    response = await handler.handle_get(request)
    logger.info(f"响应状态: {response.status}")
    logger.info(f"响应内容: {response.body}")
    
    # 3. 测试GET请求 - 缺少device_id
    logger.info("3. 测试GET /api/doorlock/config (缺少device_id)...")
    request = MockRequest(query_params={})
    response = await handler.handle_get(request)
    logger.info(f"响应状态: {response.status}")
    assert response.status == 400, "应该返回400错误"
    
    # 4. 测试POST请求 - 更新配置
    logger.info("4. 测试POST /api/doorlock/config...")
    request = MockRequest(json_data={
        "device_id": test_device_id,
        "intent_recognition_enabled": False,
        "package_guard_available": False
    })
    response = await handler.handle_post(request)
    logger.info(f"响应状态: {response.status}")
    logger.info(f"响应内容: {response.body}")
    
    # 5. 验证配置已更新
    logger.info("5. 验证配置已更新...")
    updated_config = await db.get_config(test_device_id)
    assert updated_config.intent_recognition_enabled == False
    assert updated_config.package_guard_available == False
    logger.info("✓ 配置更新成功")
    
    logger.info("✓ 设备配置API测试通过\n")


async def test_guard_api():
    """测试看护模式控制API"""
    logger.info("=" * 60)
    logger.info("测试看护模式控制API")
    logger.info("=" * 60)
    
    config = load_config()
    handler = DoorlockGuardHandler(config)
    db = DoorlockDatabase(config)
    
    test_device_id = "test_device_002"
    
    # 1. 创建测试配置（启用看护功能）
    logger.info("1. 创建测试设备配置...")
    test_config = DoorlockConfig(
        device_id=test_device_id,
        intent_recognition_enabled=True,
        package_guard_available=True,
        package_guard_active=False
    )
    await db.update_config(test_config)
    
    # 2. 测试启动看护模式
    logger.info("2. 测试POST /api/doorlock/package_guard/start...")
    request = MockRequest(json_data={
        "device_id": test_device_id,
        "reason": "测试启动看护"
    })
    response = await handler.handle_start(request)
    logger.info(f"响应状态: {response.status}")
    logger.info(f"响应内容: {response.body}")
    
    # 3. 测试停止看护模式
    logger.info("3. 测试POST /api/doorlock/package_guard/stop...")
    request = MockRequest(json_data={
        "device_id": test_device_id,
        "reason": "测试停止看护"
    })
    response = await handler.handle_stop(request)
    logger.info(f"响应状态: {response.status}")
    logger.info(f"响应内容: {response.body}")
    
    # 4. 测试启动看护模式 - 功能未启用
    logger.info("4. 测试启动看护模式（功能未启用）...")
    test_config.package_guard_available = False
    await db.update_config(test_config)
    request = MockRequest(json_data={
        "device_id": test_device_id,
        "reason": "测试启动看护"
    })
    response = await handler.handle_start(request)
    logger.info(f"响应状态: {response.status}")
    assert response.status == 400, "应该返回400错误"
    
    logger.info("✓ 看护模式控制API测试通过\n")


async def test_welcome_api():
    """测试欢迎词配置API"""
    logger.info("=" * 60)
    logger.info("测试欢迎词配置API")
    logger.info("=" * 60)
    
    config = load_config()
    handler = DoorlockWelcomeHandler(config)
    
    # 注意：这里需要一个真实存在的person_id，或者先创建一个测试用户
    # 为了测试，我们假设person_id=1存在
    test_person_id = 1
    
    # 1. 测试配置欢迎词
    logger.info("1. 测试POST /api/doorlock/welcome/config...")
    request = MockRequest(json_data={
        "person_id": test_person_id,
        "custom_greeting": {
            "morning": "早上好，测试用户",
            "afternoon": "下午好，测试用户",
            "evening": "晚上好，测试用户",
            "night": "夜深了，测试用户",
            "default": "欢迎回家"
        }
    })
    response = await handler.handle_post_config(request)
    logger.info(f"响应状态: {response.status}")
    logger.info(f"响应内容: {response.body}")
    
    # 2. 测试查询欢迎词配置
    logger.info("2. 测试GET /api/doorlock/welcome/config...")
    request = MockRequest(query_params={"person_id": str(test_person_id)})
    response = await handler.handle_get_config(request)
    logger.info(f"响应状态: {response.status}")
    logger.info(f"响应内容: {response.body}")
    
    # 3. 测试获取预设模板
    logger.info("3. 测试GET /api/doorlock/welcome/templates...")
    request = MockRequest()
    response = await handler.handle_get_templates(request)
    logger.info(f"响应状态: {response.status}")
    logger.info(f"响应内容: {response.body}")
    
    # 4. 测试无效的欢迎词格式
    logger.info("4. 测试无效的欢迎词格式...")
    request = MockRequest(json_data={
        "person_id": test_person_id,
        "custom_greeting": {
            "invalid_key": "测试",
            "morning": "早上好"
        }
    })
    response = await handler.handle_post_config(request)
    logger.info(f"响应状态: {response.status}")
    assert response.status == 400, "应该返回400错误"
    
    logger.info("✓ 欢迎词配置API测试通过\n")


async def test_history_api():
    """测试历史记录查询API"""
    logger.info("=" * 60)
    logger.info("测试历史记录查询API")
    logger.info("=" * 60)
    
    config = load_config()
    handler = DoorlockHistoryHandler(config)
    db = DoorlockDatabase(config)
    
    test_device_id = "test_device_003"
    
    # 1. 创建测试数据 - 访客意图记录
    logger.info("1. 创建测试访客意图记录...")
    test_intent = VisitorIntent(
        visit_id=None,
        session_id=f"{test_device_id}_1707379822000",
        person_id=None,
        intent_type="delivery",
        intent_summary={"purpose": "送快递"},
        dialogue_history=[
            {"role": "assistant", "content": "您好，请问有什么可以帮您？"},
            {"role": "user", "content": "我是快递员，有您的快递"}
        ]
    )
    await db.save_visitor_intent(test_intent)
    
    # 2. 创建测试数据 - 快递警报记录
    logger.info("2. 创建测试快递警报记录...")
    test_alert = PackageAlert(
        device_id=test_device_id,
        session_id=f"{test_device_id}_1707380410000",
        threat_level="medium",
        action="searching",
        description="检测到有人翻看快递",
        photo_path="test/alert.jpg",
        voice_warning_sent=True,
        notified=True
    )
    await db.save_package_alert(test_alert)
    
    # 3. 测试查询意图识别历史
    logger.info("3. 测试GET /api/doorlock/intents/history...")
    request = MockRequest(query_params={
        "device_id": test_device_id,
        "limit": "10",
        "offset": "0"
    })
    response = await handler.handle_get_intents(request)
    logger.info(f"响应状态: {response.status}")
    logger.info(f"响应内容: {response.body}")
    
    # 4. 测试查询快递警报历史
    logger.info("4. 测试GET /api/doorlock/alerts/history...")
    request = MockRequest(query_params={
        "device_id": test_device_id,
        "limit": "10",
        "offset": "0"
    })
    response = await handler.handle_get_alerts(request)
    logger.info(f"响应状态: {response.status}")
    logger.info(f"响应内容: {response.body}")
    
    # 5. 测试带时间范围的查询
    logger.info("5. 测试带时间范围的查询...")
    request = MockRequest(query_params={
        "device_id": test_device_id,
        "limit": "10",
        "offset": "0",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31"
    })
    response = await handler.handle_get_intents(request)
    logger.info(f"响应状态: {response.status}")
    logger.info(f"响应内容: {response.body}")
    
    # 6. 测试无效的分页参数
    logger.info("6. 测试无效的分页参数...")
    request = MockRequest(query_params={
        "device_id": test_device_id,
        "limit": "200"  # 超过最大值100
    })
    response = await handler.handle_get_intents(request)
    logger.info(f"响应状态: {response.status}")
    assert response.status == 400, "应该返回400错误"
    
    logger.info("✓ 历史记录查询API测试通过\n")


async def main():
    """主测试函数"""
    logger.info("开始测试门锁AI功能HTTP API")
    logger.info("=" * 60)
    
    try:
        # 测试所有API
        await test_config_api()
        await test_guard_api()
        await test_welcome_api()
        await test_history_api()
        
        logger.info("=" * 60)
        logger.info("✓ 所有API测试通过！")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
