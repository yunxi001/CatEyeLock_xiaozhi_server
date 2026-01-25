#!/usr/bin/env python3
"""
数据库迁移执行脚本

用法：
    python run_migration.py --config ../config.yaml
    python run_migration.py --host localhost --user root --password xxx --database xiaozhi
"""

import argparse
import sys
from pathlib import Path
import pymysql
from ruamel.yaml import YAML

# 添加父目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.logger import setup_logging

logger = setup_logging()


def load_config(config_path: str) -> dict:
    """从 YAML 文件加载配置"""
    yaml = YAML()
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.load(f)
    return config


def get_db_config_from_yaml(config_path: str) -> dict:
    """从配置文件获取数据库配置"""
    config = load_config(config_path)
    
    # 从 face_recognition 配置中获取数据库信息
    face_config = config.get('face_recognition', {})
    db_config = face_config.get('database', {})
    
    return {
        'host': db_config.get('host', 'localhost'),
        'port': db_config.get('port', 3306),
        'user': db_config.get('user', 'root'),
        'password': db_config.get('password', ''),
        'database': db_config.get('database', 'xiaozhi'),
    }


def execute_migration(host: str, port: int, user: str, password: str, database: str, 
                     script_name: str = "upgrade_v5.0_to_v5.2.sql") -> bool:
    """
    执行数据库迁移
    
    Args:
        host: 数据库主机
        port: 数据库端口
        user: 数据库用户
        password: 数据库密码
        database: 数据库名称
        script_name: 迁移脚本文件名
        
    Returns:
        bool: 迁移是否成功
    """
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        logger.error(f"迁移脚本不存在: {script_path}")
        return False
    
    logger.info(f"开始执行数据库迁移: {script_name}")
    logger.info(f"数据库: {host}:{port}/{database}")
    
    # 读取迁移脚本
    with open(script_path, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    
    # 连接数据库
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset='utf8mb4',
            autocommit=False
        )
        logger.info("数据库连接成功")
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return False
    
    try:
        cursor = conn.cursor()
        
        # 分割 SQL 语句
        # 注意：这是一个简化的分割方法，对于复杂的存储过程可能需要更复杂的解析
        statements = []
        current_statement = []
        in_delimiter_block = False
        
        for line in sql_script.split('\n'):
            line = line.strip()
            
            # 跳过注释和空行
            if not line or line.startswith('--'):
                continue
            
            # 处理 DELIMITER 命令
            if line.upper().startswith('DELIMITER'):
                in_delimiter_block = not in_delimiter_block
                continue
            
            current_statement.append(line)
            
            # 检查语句结束
            if not in_delimiter_block and line.endswith(';'):
                statement = ' '.join(current_statement)
                if statement.strip():
                    statements.append(statement)
                current_statement = []
        
        # 执行所有语句
        success_count = 0
        error_count = 0
        
        for i, statement in enumerate(statements, 1):
            try:
                # 跳过 SELECT 语句（验证语句）
                if statement.strip().upper().startswith('SELECT'):
                    logger.debug(f"跳过验证语句 [{i}/{len(statements)}]")
                    continue
                
                logger.debug(f"执行语句 [{i}/{len(statements)}]: {statement[:100]}...")
                cursor.execute(statement)
                success_count += 1
                
            except pymysql.Error as e:
                # 某些错误可以忽略（如字段已存在）
                error_msg = str(e)
                if "Duplicate column name" in error_msg or "Duplicate key name" in error_msg:
                    logger.warning(f"语句 [{i}] 警告（可忽略）: {error_msg}")
                else:
                    logger.error(f"语句 [{i}] 执行失败: {error_msg}")
                    error_count += 1
        
        # 提交事务
        conn.commit()
        logger.info(f"迁移完成: 成功 {success_count} 条，错误 {error_count} 条")
        
        # 验证迁移结果
        logger.info("验证迁移结果...")
        cursor.execute("""
            SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT 
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = 'unlock_logs'
              AND COLUMN_NAME IN ('status', 'lock_time')
        """, (database,))
        
        columns = cursor.fetchall()
        if len(columns) == 2:
            logger.info("✓ unlock_logs 表字段验证通过")
            for col in columns:
                logger.info(f"  - {col[0]}: {col[1]} (默认值: {col[2]})")
        else:
            logger.warning(f"✗ unlock_logs 表字段验证失败，预期 2 个字段，实际 {len(columns)} 个")
        
        # 验证索引
        cursor.execute("""
            SELECT INDEX_NAME, COLUMN_NAME
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = 'unlock_logs'
              AND INDEX_NAME = 'idx_status'
        """, (database,))
        
        indexes = cursor.fetchall()
        if indexes:
            logger.info("✓ idx_status 索引验证通过")
        else:
            logger.warning("✗ idx_status 索引验证失败")
        
        return error_count == 0
        
    except Exception as e:
        conn.rollback()
        logger.error(f"迁移失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
        
    finally:
        conn.close()
        logger.info("数据库连接已关闭")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='执行数据库迁移脚本')
    parser.add_argument('--config', type=str, help='配置文件路径（如 ../config.yaml）')
    parser.add_argument('--host', type=str, help='数据库主机')
    parser.add_argument('--port', type=int, default=3306, help='数据库端口')
    parser.add_argument('--user', type=str, help='数据库用户')
    parser.add_argument('--password', type=str, help='数据库密码')
    parser.add_argument('--database', type=str, help='数据库名称')
    parser.add_argument('--script', type=str, default='upgrade_v5.0_to_v5.2.sql',
                       help='迁移脚本文件名')
    
    args = parser.parse_args()
    
    # 获取数据库配置
    if args.config:
        logger.info(f"从配置文件加载数据库配置: {args.config}")
        try:
            db_config = get_db_config_from_yaml(args.config)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return 1
    elif all([args.host, args.user, args.database]):
        db_config = {
            'host': args.host,
            'port': args.port,
            'user': args.user,
            'password': args.password or '',
            'database': args.database,
        }
    else:
        logger.error("请提供 --config 或 --host/--user/--database 参数")
        parser.print_help()
        return 1
    
    # 执行迁移
    success = execute_migration(
        host=db_config['host'],
        port=db_config['port'],
        user=db_config['user'],
        password=db_config['password'],
        database=db_config['database'],
        script_name=args.script
    )
    
    if success:
        logger.info("✓ 数据库迁移成功完成")
        return 0
    else:
        logger.error("✗ 数据库迁移失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
