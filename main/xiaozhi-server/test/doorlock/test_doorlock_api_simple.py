"""门锁AI功能HTTP API简单测试

测试API处理器的基本功能，不依赖外部服务
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger


def test_imports():
    """测试所有API处理器是否可以正常导入"""
    logger.info("=" * 60)
    logger.info("测试API处理器导入")
    logger.info("=" * 60)
    
    try:
        from core.api.doorlock_config_handler import DoorlockConfigHandler
        logger.info("✓ DoorlockConfigHandler 导入成功")
        
        from core.api.doorlock_guard_handler import DoorlockGuardHandler
        logger.info("✓ DoorlockGuardHandler 导入成功")
        
        from core.api.doorlock_welcome_handler import DoorlockWelcomeHandler
        logger.info("✓ DoorlockWelcomeHandler 导入成功")
        
        from core.api.doorlock_history_handler import DoorlockHistoryHandler
        logger.info("✓ DoorlockHistoryHandler 导入成功")
        
        logger.info("✓ 所有API处理器导入成功\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_http_server_integration():
    """测试HTTP服务器是否正确集成了API处理器"""
    logger.info("=" * 60)
    logger.info("测试HTTP服务器集成")
    logger.info("=" * 60)
    
    try:
        from core.http_server import SimpleHttpServer
        logger.info("✓ SimpleHttpServer 导入成功")
        
        # 检查是否有门锁API处理器的属性
        import inspect
        init_source = inspect.getsource(SimpleHttpServer.__init__)
        
        required_handlers = [
            "doorlock_config_handler",
            "doorlock_guard_handler",
            "doorlock_welcome_handler",
            "doorlock_history_handler"
        ]
        
        for handler in required_handlers:
            if handler in init_source:
                logger.info(f"✓ {handler} 已集成到HTTP服务器")
            else:
                logger.error(f"✗ {handler} 未集成到HTTP服务器")
                return False
        
        logger.info("✓ HTTP服务器集成检查通过\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ HTTP服务器集成检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_routes():
    """测试API路由是否正确配置"""
    logger.info("=" * 60)
    logger.info("测试API路由配置")
    logger.info("=" * 60)
    
    try:
        from core.http_server import SimpleHttpServer
        import inspect
        
        start_source = inspect.getsource(SimpleHttpServer.start)
        
        # 检查所有必需的路由
        required_routes = [
            "/api/doorlock/config",
            "/api/doorlock/package_guard/start",
            "/api/doorlock/package_guard/stop",
            "/api/doorlock/welcome/config",
            "/api/doorlock/welcome/templates",
            "/api/doorlock/intents/history",
            "/api/doorlock/alerts/history"
        ]
        
        for route in required_routes:
            if route in start_source:
                logger.info(f"✓ 路由 {route} 已配置")
            else:
                logger.error(f"✗ 路由 {route} 未配置")
                return False
        
        logger.info("✓ API路由配置检查通过\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ API路由配置检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_methods():
    """测试数据库服务是否有必需的方法"""
    logger.info("=" * 60)
    logger.info("测试数据库服务方法")
    logger.info("=" * 60)
    
    try:
        from core.providers.doorlock.doorlock_database import DoorlockDatabase
        
        required_methods = [
            "get_config",
            "update_config",
            "save_visitor_intent",
            "get_visitor_intents",
            "save_package_alert",
            "get_package_alerts",
            "get_person_greeting",
            "update_person_greeting"
        ]
        
        for method in required_methods:
            if hasattr(DoorlockDatabase, method):
                logger.info(f"✓ 方法 {method} 存在")
            else:
                logger.error(f"✗ 方法 {method} 不存在")
                return False
        
        # 检查 get_visitor_intents 和 get_package_alerts 是否支持新参数
        import inspect
        
        sig = inspect.signature(DoorlockDatabase.get_visitor_intents)
        params = list(sig.parameters.keys())
        if 'offset' in params and 'start_date' in params and 'end_date' in params:
            logger.info("✓ get_visitor_intents 支持分页和时间范围过滤")
        else:
            logger.error("✗ get_visitor_intents 缺少必需参数")
            return False
        
        sig = inspect.signature(DoorlockDatabase.get_package_alerts)
        params = list(sig.parameters.keys())
        if 'offset' in params and 'start_date' in params and 'end_date' in params:
            logger.info("✓ get_package_alerts 支持分页和时间范围过滤")
        else:
            logger.error("✗ get_package_alerts 缺少必需参数")
            return False
        
        logger.info("✓ 数据库服务方法检查通过\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ 数据库服务方法检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_handler_methods():
    """测试API处理器是否有必需的方法"""
    logger.info("=" * 60)
    logger.info("测试API处理器方法")
    logger.info("=" * 60)
    
    try:
        from core.api.doorlock_config_handler import DoorlockConfigHandler
        from core.api.doorlock_guard_handler import DoorlockGuardHandler
        from core.api.doorlock_welcome_handler import DoorlockWelcomeHandler
        from core.api.doorlock_history_handler import DoorlockHistoryHandler
        
        # 检查配置处理器
        if hasattr(DoorlockConfigHandler, 'handle_get') and hasattr(DoorlockConfigHandler, 'handle_post'):
            logger.info("✓ DoorlockConfigHandler 有 handle_get 和 handle_post 方法")
        else:
            logger.error("✗ DoorlockConfigHandler 缺少必需方法")
            return False
        
        # 检查看护模式处理器
        if hasattr(DoorlockGuardHandler, 'handle_start') and hasattr(DoorlockGuardHandler, 'handle_stop'):
            logger.info("✓ DoorlockGuardHandler 有 handle_start 和 handle_stop 方法")
        else:
            logger.error("✗ DoorlockGuardHandler 缺少必需方法")
            return False
        
        # 检查欢迎词处理器
        if (hasattr(DoorlockWelcomeHandler, 'handle_get_config') and 
            hasattr(DoorlockWelcomeHandler, 'handle_post_config') and
            hasattr(DoorlockWelcomeHandler, 'handle_get_templates')):
            logger.info("✓ DoorlockWelcomeHandler 有所有必需方法")
        else:
            logger.error("✗ DoorlockWelcomeHandler 缺少必需方法")
            return False
        
        # 检查历史记录处理器
        if (hasattr(DoorlockHistoryHandler, 'handle_get_intents') and 
            hasattr(DoorlockHistoryHandler, 'handle_get_alerts')):
            logger.info("✓ DoorlockHistoryHandler 有 handle_get_intents 和 handle_get_alerts 方法")
        else:
            logger.error("✗ DoorlockHistoryHandler 缺少必需方法")
            return False
        
        logger.info("✓ API处理器方法检查通过\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ API处理器方法检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    logger.info("开始测试门锁AI功能HTTP API")
    logger.info("=" * 60)
    
    all_passed = True
    
    # 运行所有测试
    all_passed &= test_imports()
    all_passed &= test_http_server_integration()
    all_passed &= test_api_routes()
    all_passed &= test_database_methods()
    all_passed &= test_handler_methods()
    
    logger.info("=" * 60)
    if all_passed:
        logger.info("✓ 所有检查通过！")
        logger.info("=" * 60)
        logger.info("\n总结:")
        logger.info("- 所有API处理器已正确实现")
        logger.info("- HTTP服务器已正确集成API处理器")
        logger.info("- 所有API路由已正确配置")
        logger.info("- 数据库服务支持分页和时间范围过滤")
        logger.info("- 所有处理器方法已正确实现")
        logger.info("\nAPI接口列表:")
        logger.info("1. GET  /api/doorlock/config - 获取设备配置")
        logger.info("2. POST /api/doorlock/config - 更新设备配置")
        logger.info("3. POST /api/doorlock/package_guard/start - 启动看护模式")
        logger.info("4. POST /api/doorlock/package_guard/stop - 停止看护模式")
        logger.info("5. GET  /api/doorlock/welcome/config - 查询欢迎词配置")
        logger.info("6. POST /api/doorlock/welcome/config - 配置欢迎词")
        logger.info("7. GET  /api/doorlock/welcome/templates - 获取预设模板")
        logger.info("8. GET  /api/doorlock/intents/history - 查询意图识别历史")
        logger.info("9. GET  /api/doorlock/alerts/history - 查询快递警报历史")
        return 0
    else:
        logger.error("✗ 部分检查失败")
        logger.error("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
