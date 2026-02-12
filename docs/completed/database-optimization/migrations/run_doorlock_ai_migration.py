#!/usr/bin/env python3
"""
智能门锁AI功能数据库迁移执行脚本

用法：
    # 从 config.yaml 读取配置（推荐）
    python run_doorlock_ai_migration.py
    
    # 或使用命令行参数
    python run_doorlock_ai_migration.py --host localhost --user root --password xxx --database smart_doorlock
"""

import argparse
import sys
from pathlib import Path
import pymysql
from loguru import logger

# 添加父目录到 Python 路径以导入配置
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ruamel.yaml import YAML
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def execute_migration(host: str, port: int, user: str, password: str, database: str) -> bool:
    """
    执行智能门锁AI功能数据库迁移
    
    Args:
        host: 数据库主机
        port: 数据库端口
        user: 数据库用户
        password: 数据库密码
        database: 数据库名称
        
    Returns:
        bool: 迁移是否成功
    """
    script_path = Path(__file__).parent / "add_doorlock_ai_tables.sql"
    
    if not script_path.exists():
        logger.error(f"迁移脚本不存在: {script_path}")
        return False
    
    logger.info("="*70)
    logger.info("开始执行智能门锁AI功能数据库迁移")
    logger.info("="*70)
    logger.info(f"数据库: {host}:{port}/{database}")
    logger.info(f"迁移脚本: {script_path.name}")
    logger.info("")
    
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
        logger.success("✓ 数据库连接成功")
    except Exception as e:
        logger.error(f"✗ 数据库连接失败: {e}")
        return False
    
    try:
        cursor = conn.cursor()
        
        # 分割 SQL 语句
        statements = []
        current_statement = []
        
        for line in sql_script.split('\n'):
            line = line.strip()
            
            # 跳过注释和空行
            if not line or line.startswith('--'):
                continue
            
            current_statement.append(line)
            
            # 检查语句结束
            if line.endswith(';'):
                statement = ' '.join(current_statement)
                if statement.strip():
                    statements.append(statement)
                current_statement = []
        
        # 执行所有语句
        success_count = 0
        warning_count = 0
        error_count = 0
        
        logger.info(f"共 {len(statements)} 条SQL语句待执行")
        logger.info("")
        
        for i, statement in enumerate(statements, 1):
            try:
                # 跳过 SELECT 语句（验证语句）
                if statement.strip().upper().startswith('SELECT'):
                    logger.info(f"[{i}/{len(statements)}] 跳过验证语句")
                    continue
                
                # 显示执行的语句摘要
                stmt_preview = statement[:100].replace('\n', ' ')
                logger.info(f"[{i}/{len(statements)}] 执行: {stmt_preview}...")
                
                cursor.execute(statement)
                success_count += 1
                logger.success(f"  ✓ 执行成功")
                
            except pymysql.Error as e:
                error_msg = str(e)
                
                # 某些错误可以忽略（如字段已存在、表已存在）
                if any(keyword in error_msg for keyword in [
                    "Duplicate column name",
                    "Duplicate key name", 
                    "already exists",
                    "Table '.*' already exists"
                ]):
                    logger.warning(f"  ⚠ 警告（可忽略）: {error_msg}")
                    warning_count += 1
                else:
                    logger.error(f"  ✗ 执行失败: {error_msg}")
                    error_count += 1
        
        # 提交事务
        if error_count == 0:
            conn.commit()
            logger.info("")
            logger.success("="*70)
            logger.success(f"迁移完成: 成功 {success_count} 条，警告 {warning_count} 条")
            logger.success("="*70)
            return True
        else:
            conn.rollback()
            logger.error("")
            logger.error("="*70)
            logger.error(f"迁移失败: 成功 {success_count} 条，警告 {warning_count} 条，错误 {error_count} 条")
            logger.error("事务已回滚")
            logger.error("="*70)
            return False
        
    except Exception as e:
        conn.rollback()
        logger.error("")
        logger.error(f"迁移执行异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
        
    finally:
        conn.close()
        logger.info("数据库连接已关闭")


def load_config_from_yaml() -> dict:
    """
    从 config.yaml 读取 MySQL 配置
    
    Returns:
        dict: MySQL 配置字典，如果读取失败返回 None
    """
    config_path = Path(__file__).parent.parent / "config.yaml"
    
    if not config_path.exists():
        logger.warning(f"配置文件不存在: {config_path}")
        return None
    
    if not HAS_YAML:
        logger.warning("未安装 ruamel.yaml，无法读取配置文件")
        return None
    
    try:
        yaml = YAML()
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.load(f)
        
        if 'mysql' not in config:
            logger.warning("config.yaml 中未找到 mysql 配置段")
            return None
        
        mysql_config = config['mysql']
        
        # 验证必需字段
        required_fields = ['host', 'port', 'user', 'password', 'database']
        for field in required_fields:
            if field not in mysql_config:
                logger.warning(f"mysql 配置缺少必需字段: {field}")
                return None
        
        logger.info(f"✓ 从 config.yaml 读取到 MySQL 配置")
        return mysql_config
        
    except Exception as e:
        logger.warning(f"读取配置文件失败: {e}")
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='执行智能门锁AI功能数据库迁移',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从 config.yaml 读取配置（推荐）
  python run_doorlock_ai_migration.py
  
  # 使用命令行参数
  python run_doorlock_ai_migration.py --user root --password 123456 --database smart_doorlock
        """
    )
    parser.add_argument('--host', type=str, help='数据库主机（默认: 从config.yaml读取或localhost）')
    parser.add_argument('--port', type=int, help='数据库端口（默认: 从config.yaml读取或3306）')
    parser.add_argument('--user', type=str, help='数据库用户（默认: 从config.yaml读取）')
    parser.add_argument('--password', type=str, help='数据库密码（默认: 从config.yaml读取）')
    parser.add_argument('--database', type=str, help='数据库名称（默认: 从config.yaml读取）')
    
    args = parser.parse_args()
    
    # 尝试从 config.yaml 读取配置
    yaml_config = load_config_from_yaml()
    
    # 合并配置：命令行参数优先级高于配置文件
    host = args.host or (yaml_config.get('host') if yaml_config else None) or 'localhost'
    port = args.port or (yaml_config.get('port') if yaml_config else None) or 3306
    user = args.user or (yaml_config.get('user') if yaml_config else None)
    password = args.password or (str(yaml_config.get('password')) if yaml_config else None)
    database = args.database or (yaml_config.get('database') if yaml_config else None)
    
    # 验证必需参数
    if not user or not password or not database:
        logger.error("错误: 缺少必需的数据库连接参数")
        logger.error("")
        logger.error("请使用以下方式之一:")
        logger.error("  1. 在 config.yaml 中配置 mysql 段（推荐）")
        logger.error("  2. 使用命令行参数: --user USER --password PASSWORD --database DATABASE")
        logger.error("")
        logger.error("运行 'python run_doorlock_ai_migration.py --help' 查看详细帮助")
        return 1
    
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # 执行迁移
    success = execute_migration(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database
    )
    
    if success:
        logger.info("")
        logger.info("下一步: 运行验证脚本检查迁移结果")
        logger.info(f"  python verify_doorlock_ai_migration.py")
        return 0
    else:
        return 1


if __name__ == '__main__':
    sys.exit(main())
