#!/usr/bin/env python3
"""
添加门锁用户管理功能的数据库迁移脚本

执行方式:
    cd main/xiaozhi-server
    python migrations/run_add_doorlock_users.py
    
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
        # 尝试从 face_recognition_config.yaml 读取数据库配置
        import yaml
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config',
            'face_recognition_config.yaml'
        )
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                db_config = config.get('database', {})
                if db_config:
                    logger.info(f"从 {config_path} 加载数据库配置")
                    return db_config
    except Exception as e:
        logger.warning(f"无法从配置文件加载数据库配置: {e}")
    
    # 如果配置文件中没有数据库配置，使用默认配置或提示用户输入
    logger.info("未找到数据库配置，使用默认配置...")
    return {
        'host': os.getenv('DB_HOST', '127.0.0.1'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', '123456'),
        'database': os.getenv('DB_NAME', 'smart_doorlock')
    }


def run_migration():
    """执行数据库迁移"""
    try:
        # 获取数据库配置
        db_config = get_database_config()
        
        logger.info("开始执行门锁用户管理功能迁移...")
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
        
        # 1. 检查表是否已存在
        logger.info("步骤 1: 检查 doorlock_users 表是否已存在...")
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA = DATABASE() 
              AND TABLE_NAME = 'doorlock_users'
        """)
        result = cursor.fetchone()
        
        if result and result[0] > 0:
            logger.warning("⚠ doorlock_users 表已存在，检查表结构...")
            
            # 检查是否是新版表结构（包含 user_type 字段）
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'doorlock_users'
                  AND COLUMN_NAME = 'user_type'
            """)
            has_user_type = cursor.fetchone()[0] > 0
            
            if has_user_type:
                logger.success("✓ doorlock_users 表已是最新版本（v2.4），无需迁移")
                
                # 显示表结构
                cursor.execute("DESCRIBE doorlock_users")
                columns = cursor.fetchall()
                logger.info("\n当前表结构:")
                logger.info("-" * 80)
                for col in columns:
                    logger.info(f"  {col[0]:15} {col[1]:20} {col[2]:5} {col[3]:5} {col[4]}")
                logger.info("-" * 80)
                
                cursor.close()
                conn.close()
                return True
            else:
                logger.warning("⚠ doorlock_users 表是旧版本，需要升级")
                logger.info("建议：")
                logger.info("1. 备份现有数据")
                logger.info("2. 删除旧表: DROP TABLE doorlock_users;")
                logger.info("3. 重新运行此迁移脚本")
                cursor.close()
                conn.close()
                return False
        
        # 2. 创建 doorlock_users 表（v2.4 版本）
        logger.info("步骤 2: 创建 doorlock_users 表（v2.4 版本）...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doorlock_users (
                id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
                device_id VARCHAR(64) NOT NULL COMMENT '设备 ID',
                user_type VARCHAR(16) NOT NULL COMMENT '用户类型：finger/nfc/password',
                user_id INT NOT NULL COMMENT 'ESP32 分配的用户 ID（指纹/NFC 的槽位 ID）',
                user_name VARCHAR(64) DEFAULT NULL COMMENT '用户备注名称',
                user_data VARCHAR(255) DEFAULT NULL COMMENT '额外数据（如 NFC 卡号、密码哈希）',
                status TINYINT DEFAULT 1 COMMENT '状态：0=已删除，1=正常',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                created_by VARCHAR(64) DEFAULT NULL COMMENT '创建者 app_id',
                
                UNIQUE KEY uk_device_type_userid (device_id, user_type, user_id),
                INDEX idx_device_id (device_id),
                INDEX idx_user_type (user_type),
                INDEX idx_status (status),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='门锁用户表（统一管理指纹、NFC、密码）'
        """)
        conn.commit()
        logger.success("✓ doorlock_users 表创建成功")
        
        # 3. 验证表结构
        logger.info("步骤 3: 验证表结构...")
        cursor.execute("DESCRIBE doorlock_users")
        columns = cursor.fetchall()
        logger.info("\n表结构:")
        logger.info("-" * 80)
        for col in columns:
            logger.info(f"  {col[0]:15} {col[1]:20} {col[2]:5} {col[3]:5} {col[4]}")
        logger.info("-" * 80)
        
        # 4. 验证索引
        logger.info("\n步骤 4: 验证索引...")
        cursor.execute("""
            SELECT INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX, NON_UNIQUE
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE() 
              AND TABLE_NAME = 'doorlock_users'
            ORDER BY INDEX_NAME, SEQ_IN_INDEX
        """)
        indexes = cursor.fetchall()
        logger.info("索引列表:")
        logger.info("-" * 80)
        for idx in indexes:
            logger.info(f"  {idx[0]:25} {idx[1]:20} Seq:{idx[2]} Unique:{not idx[3]}")
        logger.info("-" * 80)
        
        # 关闭连接
        cursor.close()
        conn.close()
        
        logger.success("\n✓ 数据库迁移完成！")
        logger.info("\n迁移说明:")
        logger.info("1. 已创建 doorlock_users 表用于统一管理指纹、NFC、密码用户")
        logger.info("2. 表结构支持用户备注（user_name）、额外数据（user_data）")
        logger.info("3. 支持软删除（status 字段）")
        logger.info("4. 记录创建者（created_by 字段存储 app_id）")
        logger.info("5. App 可通过 query 接口查询用户列表（target=doorlock_users）")
        logger.info("6. user_mgmt 命令添加用户时，user_name 会自动保存到数据库")
        
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
