#!/usr/bin/env python3
"""检查数据库状态"""

import pymysql

# 数据库配置
config = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'database': 'smart_doorlock',
    'charset': 'utf8mb4'
}

try:
    conn = pymysql.connect(**config)
    cursor = conn.cursor()
    
    print("✓ 数据库连接成功\n")
    
    # 查看所有表
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    
    print(f"数据库 '{config['database']}' 中的表:")
    print("="*60)
    if tables:
        for table in tables:
            print(f"  - {table[0]}")
            
            # 查看表结构
            cursor.execute(f"DESCRIBE {table[0]}")
            columns = cursor.fetchall()
            print(f"    字段: {', '.join([col[0] for col in columns])}")
    else:
        print("  (数据库为空，没有表)")
    
    print("="*60)
    
    conn.close()
    
except Exception as e:
    print(f"✗ 错误: {e}")
