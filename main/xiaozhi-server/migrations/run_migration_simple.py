#!/usr/bin/env python3
"""
简化版数据库迁移执行脚本（不依赖项目配置）

用法：
    python run_migration_simple.py --host localhost --user root --password xxx --database smart_doorlock
"""

import argparse
import sys
from pathlib import Path
import pymysql


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
        print(f"✗ 迁移脚本不存在: {script_path}")
        return False
    
    print(f"开始执行数据库迁移: {script_name}")
    print(f"数据库: {host}:{port}/{database}")
    
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
        print("✓ 数据库连接成功")
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return False
    
    try:
        cursor = conn.cursor()
        
        # 分割 SQL 语句
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
                    print(f"  跳过验证语句 [{i}/{len(statements)}]")
                    continue
                
                print(f"  执行语句 [{i}/{len(statements)}]: {statement[:80]}...")
                cursor.execute(statement)
                success_count += 1
                
            except pymysql.Error as e:
                # 某些错误可以忽略（如字段已存在）
                error_msg = str(e)
                if "Duplicate column name" in error_msg or "Duplicate key name" in error_msg:
                    print(f"  ⚠ 语句 [{i}] 警告（可忽略）: {error_msg}")
                else:
                    print(f"  ✗ 语句 [{i}] 执行失败: {error_msg}")
                    error_count += 1
        
        # 提交事务
        conn.commit()
        print(f"\n迁移完成: 成功 {success_count} 条，错误 {error_count} 条")
        
        # 验证迁移结果
        print("\n验证迁移结果...")
        cursor.execute("""
            SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT 
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = 'unlock_logs'
              AND COLUMN_NAME IN ('status', 'lock_time')
        """, (database,))
        
        columns = cursor.fetchall()
        if len(columns) == 2:
            print("✓ unlock_logs 表字段验证通过")
            for col in columns:
                print(f"  - {col[0]}: {col[1]} (默认值: {col[2]})")
        else:
            print(f"✗ unlock_logs 表字段验证失败，预期 2 个字段，实际 {len(columns)} 个")
        
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
            print("✓ idx_status 索引验证通过")
        else:
            print("✗ idx_status 索引验证失败")
        
        return error_count == 0
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ 迁移失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False
        
    finally:
        conn.close()
        print("\n数据库连接已关闭")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='执行数据库迁移脚本（简化版）')
    parser.add_argument('--host', type=str, required=True, help='数据库主机')
    parser.add_argument('--port', type=int, default=3306, help='数据库端口')
    parser.add_argument('--user', type=str, required=True, help='数据库用户')
    parser.add_argument('--password', type=str, required=True, help='数据库密码')
    parser.add_argument('--database', type=str, required=True, help='数据库名称')
    parser.add_argument('--script', type=str, default='upgrade_v5.0_to_v5.2.sql',
                       help='迁移脚本文件名')
    
    args = parser.parse_args()
    
    # 执行迁移
    success = execute_migration(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        script_name=args.script
    )
    
    if success:
        print("\n" + "="*60)
        print("✓ 数据库迁移成功完成")
        print("="*60)
        return 0
    else:
        print("\n" + "="*60)
        print("✗ 数据库迁移失败")
        print("="*60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
