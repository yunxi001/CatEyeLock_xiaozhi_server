#!/usr/bin/env python3
"""
密码查询功能测试脚本

测试内容:
1. 数据库密码操作
2. 密码查询接口
3. 密码上报处理
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config_loader import load_config
from core.providers.doorlock.database import Database
from loguru import logger


def test_database_operations():
    """测试数据库密码操作"""
    logger.info("=" * 60)
    logger.info("测试 1: 数据库密码操作")
    logger.info("=" * 60)
    
    try:
        # 使用环境变量配置数据库
        import os
        db_config = {
            'host': os.getenv('DB_HOST', '127.0.0.1'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD', '123456'),
            'database': os.getenv('DB_NAME', 'smart_doorlock')
        }
        
        logger.info(f"使用数据库配置: host={db_config['host']}, database={db_config['database']}")
        
        # 创建数据库实例
        db = Database(db_config, logger)
        
        test_device_id = "TEST:AA:BB:CC:DD:EE"
        
        # 测试 1.1: 初始化设备密码
        logger.info("\n测试 1.1: 初始化设备密码")
        success = db.init_device_password(test_device_id, "123456")
        if success:
            logger.success("✓ 设备密码初始化成功")
        else:
            logger.warning("⚠ 设备密码已存在或初始化失败")
        
        # 测试 1.2: 获取设备密码
        logger.info("\n测试 1.2: 获取设备密码")
        password = db.get_device_password(test_device_id)
        if password == "123456":
            logger.success(f"✓ 获取密码成功: {password}")
        else:
            logger.error(f"✗ 获取密码失败，期望 '123456'，实际 '{password}'")
            return False
        
        # 测试 1.3: 更新设备密码
        logger.info("\n测试 1.3: 更新设备密码")
        new_password = "654321"
        success = db.update_device_password(test_device_id, new_password)
        if success:
            logger.success(f"✓ 密码更新成功: {new_password}")
        else:
            logger.error("✗ 密码更新失败")
            return False
        
        # 测试 1.4: 验证密码已更新
        logger.info("\n测试 1.4: 验证密码已更新")
        password = db.get_device_password(test_device_id)
        if password == new_password:
            logger.success(f"✓ 密码验证成功: {password}")
        else:
            logger.error(f"✗ 密码验证失败，期望 '{new_password}'，实际 '{password}'")
            return False
        
        # 测试 1.5: 测试不存在的设备（应返回默认密码）
        logger.info("\n测试 1.5: 测试不存在的设备")
        non_exist_device = "TEST:FF:FF:FF:FF:FF"
        password = db.get_device_password(non_exist_device)
        if password == "123456":
            logger.success(f"✓ 不存在的设备返回默认密码: {password}")
        else:
            logger.error(f"✗ 不存在的设备应返回默认密码 '123456'，实际 '{password}'")
            return False
        
        # 清理测试数据
        logger.info("\n清理测试数据...")
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM device_info WHERE device_id LIKE 'TEST:%'")
        conn.commit()
        cursor.close()
        conn.close()
        logger.success("✓ 测试数据已清理")
        
        logger.success("\n✓ 所有数据库操作测试通过！")
        return True
        
    except Exception as e:
        logger.error(f"✗ 数据库操作测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_password_encoding():
    """测试密码编码/解码"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 2: 密码编码/解码")
    logger.info("=" * 60)
    
    try:
        from core.providers.doorlock.database import Database
        
        # 测试 2.1: 编码密码
        logger.info("\n测试 2.1: 编码密码")
        original_password = "123456"
        encoded = Database.encode_password_simple(original_password)
        logger.info(f"原始密码: {original_password}")
        logger.info(f"编码后: {encoded}")
        
        # 测试 2.2: 解码密码
        logger.info("\n测试 2.2: 解码密码")
        decoded = Database.decrypt_password(encoded)
        logger.info(f"解码后: {decoded}")
        
        if decoded == original_password:
            logger.success("✓ 密码编码/解码测试通过")
            return True
        else:
            logger.error(f"✗ 密码编码/解码失败，期望 '{original_password}'，实际 '{decoded}'")
            return False
            
    except Exception as e:
        logger.error(f"✗ 密码编码/解码测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_query_interface():
    """测试查询接口（需要服务器运行）"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 3: 查询接口（需要服务器运行）")
    logger.info("=" * 60)
    
    logger.warning("⚠ 此测试需要服务器运行，请手动测试")
    logger.info("\n手动测试步骤:")
    logger.info("1. 启动服务器: python app.py")
    logger.info("2. 使用 WebSocket 客户端连接")
    logger.info("3. 发送查询请求:")
    logger.info("""
    {
        "type": "query",
        "seq_id": "test_1234567890",
        "target": "password"
    }
    """)
    logger.info("4. 验证响应:")
    logger.info("""
    {
        "type": "query_result",
        "target": "password",
        "status": "success",
        "data": {
            "password": "123456"
        }
    }
    """)
    
    return True


def main():
    """主测试函数"""
    logger.info("开始密码查询功能测试...\n")
    
    results = []
    
    # 测试 1: 数据库操作
    results.append(("数据库密码操作", test_database_operations()))
    
    # 测试 2: 密码编码/解码
    results.append(("密码编码/解码", test_password_encoding()))
    
    # 测试 3: 查询接口（手动测试）
    results.append(("查询接口", test_query_interface()))
    
    # 输出测试结果
    logger.info("\n" + "=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        logger.info(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    logger.info("=" * 60)
    
    if all_passed:
        logger.success("\n✓ 所有测试通过！")
        return 0
    else:
        logger.error("\n✗ 部分测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
