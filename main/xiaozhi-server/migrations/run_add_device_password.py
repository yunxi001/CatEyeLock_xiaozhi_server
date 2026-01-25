#!/usr/bin/env python3
"""
添加设备密码管理功能的数据库迁移脚本

执行方式:
    python migrations/run_add_device_password.py
    
如果数据库配置不存在，请手动提供数据库连接信息
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from loguru import logger


def get_database_config():
    """获取数据库配置"""
    try:
        from config.config_loader import load_config
        config = load_config()
        db_config = config.get('database', {})
        
        if db_config:
            return db_config
    except Exception as e:
        logger.warning(f"无法从配置文件加载数据库配置: {e}")
    
    # 如果配置文件中没有数据库配置，使用默认配置或提示用户输入
    logger.info("未找到数据库配置，使用默认配置...")
    return {
        'host': os.getenv('DB_HOST', '127.0.0.1'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'smart_doorlock')
    }


def run_migration():
    """执行数据库迁移"""
    try:
        # 获取数据库配置
        db_config = get_database_config()
        
        logger.info("开始执行设备密码管理功能迁移...")
        logger.info(f"数据库配置: host={db_config['host']}, port={db_config['port']}, database={db_config['database']}")
        
        # 连接数据库
        conn = mysql.connector.connect(
            host=db_config.get('host', '127.0.0.1'),
            port=db_config.get('port', 3306),
            user=db_config.get('user', 'root'),
            password=db_config.get('password', ''),
            database=db_config.get('database', 'smart_doorlock'),
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        
        # 1. 创建 device_info 表
        logger.info("步骤 1: 创建 device_info 表...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_info (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                device_id VARCHAR(64) NOT NULL UNIQUE COMMENT '设备 ID',
                password_encrypted VARCHAR(255) DEFAULT NULL COMMENT '加密后的密码',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_device_id (device_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备基本信息表'
        """)
        logger.success("✓ device_info 表创建成功")
        
        # 2. 为现有设备初始化默认密码
        logger.info("步骤 2: 为现有设备初始化默认密码...")
        
        # 获取所有现有设备
        cursor.execute("SELECT DISTINCT device_id FROM device_status")
        existing_devices = [row[0] for row in cursor.fetchall()]
        logger.info(f"发现 {len(existing_devices)} 个现有设备")
        
        # 默认密码 "123456" 的 Base64 编码
        default_password_encrypted = "MTIzNDU2"
        
        # 为每个设备初始化密码
        initialized_count = 0
        for device_id in existing_devices:
            cursor.execute("""
                INSERT INTO device_info (device_id, password_encrypted)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE device_id = device_id
            """, (device_id, default_password_encrypted))
            if cursor.rowcount > 0:
                initialized_count += 1
        
        conn.commit()
        logger.success(f"✓ 已为 {initialized_count} 个设备初始化默认密码")
        
        # 3. 验证迁移结果
        logger.info("步骤 3: 验证迁移结果...")
        cursor.execute("SELECT COUNT(*) FROM device_info")
        total_devices = cursor.fetchone()[0]
        logger.info(f"device_info 表中共有 {total_devices} 个设备记录")
        
        # 关闭连接
        cursor.close()
        conn.close()
        
        logger.success("✓ 数据库迁移完成！")
        logger.info("\n迁移说明:")
        logger.info("1. 已创建 device_info 表用于存储设备密码")
        logger.info("2. 所有现有设备的默认密码已设置为: 123456")
        logger.info("3. 密码使用 Base64 编码存储（可逆加密）")
        logger.info("4. App 查询密码时将直接从服务器返回，无需转发到 ESP32")
        logger.info("5. ESP32 上报密码时会自动更新服务器存储的密码")
        
        return True
        
    except mysql.connector.Error as e:
        logger.error(f"✗ 数据库迁移失败: {e}")
        logger.info("\n故障排查:")
        logger.info("1. 检查数据库是否已启动")
        logger.info("2. 检查数据库连接信息是否正确")
        logger.info("3. 检查数据库用户是否有足够权限")
        logger.info("\n可以通过环境变量设置数据库连接:")
        logger.info("  export DB_HOST=127.0.0.1")
        logger.info("  export DB_PORT=3306")
        logger.info("  export DB_USER=root")
        logger.info("  export DB_PASSWORD=your_password")
        logger.info("  export DB_NAME=smart_doorlock")
        return False
    except Exception as e:
        logger.error(f"✗ 迁移过程出错: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
