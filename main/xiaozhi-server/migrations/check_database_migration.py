#!/usr/bin/env python3
"""
检查数据库迁移状态

检查 device_info 表是否存在，以及是否有数据
"""
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import mysql.connector
    from loguru import logger
    
    # 数据库配置
    db_config = {
        'host': os.getenv('DB_HOST', '127.0.0.1'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', '123456'),
        'database': os.getenv('DB_NAME', 'smart_doorlock')
    }
    
    logger.info("=" * 60)
    logger.info("数据库迁移状态检查")
    logger.info("=" * 60)
    logger.info(f"数据库配置: host={db_config['host']}, port={db_config['port']}, database={db_config['database']}")
    
    # 连接数据库
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    # 1. 检查 device_info 表是否存在
    logger.info("\n步骤 1: 检查 device_info 表是否存在...")
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM information_schema.tables 
        WHERE table_schema = %s AND table_name = 'device_info'
    """, (db_config['database'],))
    result = cursor.fetchone()
    
    if result['count'] > 0:
        logger.success("✓ device_info 表已存在")
        
        # 2. 检查表结构
        logger.info("\n步骤 2: 检查表结构...")
        cursor.execute("DESCRIBE device_info")
        columns = cursor.fetchall()
        logger.info("表结构:")
        for col in columns:
            logger.info(f"  - {col['Field']}: {col['Type']} {col['Null']} {col['Key']} {col['Default']}")
        
        # 3. 检查数据
        logger.info("\n步骤 3: 检查数据...")
        cursor.execute("SELECT COUNT(*) as total FROM device_info")
        total = cursor.fetchone()['total']
        logger.info(f"device_info 表中共有 {total} 条记录")
        
        if total > 0:
            # 显示前 5 条记录
            cursor.execute("SELECT device_id, password_encrypted, created_at FROM device_info LIMIT 5")
            records = cursor.fetchall()
            logger.info("\n前 5 条记录:")
            for r in records:
                # 解密密码显示
                try:
                    import base64
                    password = base64.b64decode(r['password_encrypted']).decode('utf-8')
                except:
                    password = "解密失败"
                logger.info(f"  - device_id: {r['device_id']}, password: {password}, created_at: {r['created_at']}")
        
        # 4. 检查是否有设备但没有密码记录
        logger.info("\n步骤 4: 检查是否有设备缺少密码记录...")
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM device_status ds
            LEFT JOIN device_info di ON ds.device_id = di.device_id
            WHERE di.device_id IS NULL
        """)
        missing = cursor.fetchone()['count']
        if missing > 0:
            logger.warning(f"⚠ 发现 {missing} 个设备缺少密码记录")
            cursor.execute("""
                SELECT DISTINCT ds.device_id 
                FROM device_status ds
                LEFT JOIN device_info di ON ds.device_id = di.device_id
                WHERE di.device_id IS NULL
                LIMIT 5
            """)
            devices = cursor.fetchall()
            logger.info("缺少密码记录的设备（前5个）:")
            for d in devices:
                logger.info(f"  - {d['device_id']}")
        else:
            logger.success("✓ 所有设备都有密码记录")
        
        logger.info("\n" + "=" * 60)
        logger.success("✓ 数据库迁移已完成")
        logger.info("=" * 60)
        
    else:
        logger.error("✗ device_info 表不存在")
        logger.info("\n需要执行数据库迁移:")
        logger.info("  python migrations/run_add_device_password.py")
        logger.info("\n或者设置环境变量后执行:")
        logger.info("  export DB_PASSWORD=123456")
        logger.info("  python migrations/run_add_device_password.py")
    
    cursor.close()
    conn.close()
    
except ImportError as e:
    logger.error(f"✗ 缺少依赖模块: {e}")
    logger.info("\n请安装依赖:")
    logger.info("  pip install mysql-connector-python")
    sys.exit(1)
    
except mysql.connector.Error as e:
    logger.error(f"✗ 数据库连接失败: {e}")
    logger.info("\n故障排查:")
    logger.info("1. 检查 MySQL 是否已启动")
    logger.info("2. 检查数据库连接信息是否正确")
    logger.info("3. 检查数据库用户权限")
    logger.info("\n可以通过环境变量设置数据库连接:")
    logger.info("  set DB_HOST=127.0.0.1")
    logger.info("  set DB_PORT=3306")
    logger.info("  set DB_USER=root")
    logger.info("  set DB_PASSWORD=123456")
    logger.info("  set DB_NAME=smart_doorlock")
    sys.exit(1)
    
except Exception as e:
    logger.error(f"✗ 检查过程出错: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
