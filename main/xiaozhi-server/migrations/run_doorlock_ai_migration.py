#!/usr/bin/env python3
"""
智能门锁AI功能数据库迁移执行脚本

用法：
    python run_doorlock_ai_migration.py --host localhost --user root --password xxx --database smart_doorlock
"""

import argparse
import sys
from pathlib import Path
import pymysql
from loguru import logger


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


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='执行智能门锁AI功能数据库迁移')
    parser.add_argument('--host', type=str, default='localhost', help='数据库主机（默认: localhost）')
    parser.add_argument('--port', type=int, default=3306, help='数据库端口（默认: 3306）')
    parser.add_argument('--user', type=str, required=True, help='数据库用户')
    parser.add_argument('--password', type=str, required=True, help='数据库密码')
    parser.add_argument('--database', type=str, required=True, help='数据库名称')
    
    args = parser.parse_args()
    
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # 执行迁移
    success = execute_migration(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database
    )
    
    if success:
        logger.info("")
        logger.info("下一步: 运行验证脚本检查迁移结果")
        logger.info(f"  python verify_doorlock_ai_migration.py --host {args.host} --user {args.user} --password *** --database {args.database}")
        return 0
    else:
        return 1


if __name__ == '__main__':
    sys.exit(main())
