#!/usr/bin/env python3
"""
数据库迁移执行脚本：添加门锁用户表（简化版）

功能：
1. 读取并执行 add_doorlock_users_table.sql 脚本
2. 验证表创建是否成功
3. 记录迁移日志

使用方法：
    cd main/xiaozhi-server
    python migrations/run_add_doorlock_users_simple.py
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import mysql.connector
from config.config_loader import load_config


def execute_migration():
    """执行数据库迁移"""
    try:
        # 从配置文件读取数据库配置
        config = load_config()
        mysql_config = config.get('mysql', {})
        
        if not mysql_config:
            print("❌ 配置文件中未找到 MySQL 配置")
            return False
        
        # 读取 SQL 脚本
        sql_file = Path(__file__).parent / "add_doorlock_users_table.sql"
        if not sql_file.exists():
            print(f"❌ SQL 脚本文件不存在: {sql_file}")
            return False
        
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        print("开始执行数据库迁移...")
        print(f"SQL 脚本: {sql_file}")
        
        # 连接数据库
        conn = mysql.connector.connect(
            host=mysql_config.get('host', '127.0.0.1'),
            port=mysql_config.get('port', 3306),
            user=mysql_config.get('user', 'root'),
            password=mysql_config.get('password', ''),
            database=mysql_config.get('database', 'smart_doorlock'),
            charset='utf8mb4'
        )
        
        cursor = conn.cursor(dictionary=True)
        
        try:
            # 分割 SQL 语句（按分号分割，忽略注释）
            statements = []
            current_statement = []
            
            for line in sql_content.split('\n'):
                # 跳过注释行
                stripped = line.strip()
                if stripped.startswith('--') or not stripped:
                    continue
                
                current_statement.append(line)
                
                # 如果行以分号结尾，表示一条语句结束
                if stripped.endswith(';'):
                    statement = '\n'.join(current_statement)
                    if statement.strip():
                        statements.append(statement)
                    current_statement = []
            
            # 执行每条 SQL 语句
            for i, statement in enumerate(statements, 1):
                try:
                    print(f"执行语句 {i}/{len(statements)}...")
                    cursor.execute(statement)
                    
                    # 如果是 SELECT 语句，获取结果
                    if statement.strip().upper().startswith('SELECT'):
                        results = cursor.fetchall()
                        if results:
                            print(f"查询结果: {len(results)} 行")
                            for row in results[:5]:  # 只显示前5行
                                print(f"  {row}")
                            if len(results) > 5:
                                print(f"  ... 还有 {len(results) - 5} 行")
                except Exception as e:
                    print(f"❌ 执行语句失败: {e}")
                    print(f"语句内容: {statement[:200]}...")
                    raise
            
            conn.commit()
            print("✅ 数据库迁移执行成功！")
            
            # 验证表是否创建成功
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() 
                  AND TABLE_NAME = 'doorlock_users'
            """)
            result = cursor.fetchone()
            
            if result and result['count'] == 1:
                print("✅ doorlock_users 表创建成功")
                
                # 显示表结构
                cursor.execute("DESCRIBE doorlock_users")
                columns = cursor.fetchall()
                print("\n表结构:")
                print("-" * 80)
                for col in columns:
                    print(f"  {col['Field']:15} {col['Type']:20} {col['Null']:5} {col['Key']:5} {col['Default']}")
                print("-" * 80)
                
                return True
            else:
                print("❌ doorlock_users 表创建失败")
                return False
                
        finally:
            cursor.close()
            conn.close()
            
    except mysql.connector.Error as e:
        print(f"❌ 数据库错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 数据库迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("数据库迁移：添加门锁用户表")
    print("=" * 60)
    
    # 读取数据库配置
    try:
        config = load_config()
        mysql_config = config.get('mysql', {})
        
        print(f"\n数据库配置:")
        print(f"  Host: {mysql_config.get('host', '127.0.0.1')}")
        print(f"  Port: {mysql_config.get('port', 3306)}")
        print(f"  Database: {mysql_config.get('database', 'smart_doorlock')}")
        print(f"  User: {mysql_config.get('user', 'root')}")
        print()
    except Exception as e:
        print(f"❌ 读取配置失败: {e}")
        sys.exit(1)
    
    # 执行迁移
    success = execute_migration()
    
    print("=" * 60)
    if success:
        print("✅ 迁移完成！")
        sys.exit(0)
    else:
        print("❌ 迁移失败！")
        sys.exit(1)


if __name__ == "__main__":
    main()
