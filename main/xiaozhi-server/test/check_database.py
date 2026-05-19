#!/usr/bin/env python3
"""
检查数据库连接和数据情况
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ruamel.yaml import YAML
from core.providers.doorlock.database import Database
from config.logger import setup_logging


def main():
    """主函数"""
    print("="*60)
    print("数据库连接和数据检查")
    print("="*60)
    
    # 加载配置
    yaml = YAML()
    with open('config/doorlock_config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.load(f)
    
    mysql_config = config.get('mysql', {})
    print(f"\n数据库配置:")
    print(f"  主机: {mysql_config.get('host')}")
    print(f"  端口: {mysql_config.get('port')}")
    print(f"  用户: {mysql_config.get('user')}")
    print(f"  数据库: {mysql_config.get('database')}")
    
    # 初始化日志
    logger = setup_logging()
    
    # 连接数据库
    try:
        print("\n正在连接数据库...")
        db = Database(mysql_config, logger, auto_init=True)
        print("✓ 数据库连接成功")
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return
    
    # 检查各个表的数据
    device_id = "AA:BB:CC:DD:EE:FF"
    
    print(f"\n检查设备 {device_id} 的数据:")
    print("-"*60)
    
    conn = None
    cursor = None
    try:
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 检查 device_status 表
        cursor.execute("""
            SELECT COUNT(*) as count FROM device_status WHERE device_id = %s
        """, (device_id,))
        status_count = cursor.fetchone()['count']
        print(f"  device_status: {status_count} 条记录")
        
        if status_count > 0:
            cursor.execute("""
                SELECT battery, lux, lock_state, light_state, created_at
                FROM device_status
                WHERE device_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (device_id,))
            latest = cursor.fetchone()
            print(f"    最新状态: 电量={latest['battery']}%, 光照={latest['lux']}, "
                  f"锁={latest['lock_state']}, 灯={latest['light_state']}")
        
        # 检查 unlock_logs 表
        cursor.execute("""
            SELECT COUNT(*) as count FROM unlock_logs WHERE device_id = %s
        """, (device_id,))
        log_count = cursor.fetchone()['count']
        print(f"  unlock_logs: {log_count} 条记录")
        
        if log_count > 0:
            cursor.execute("""
                SELECT method, user_id, status, created_at
                FROM unlock_logs
                WHERE device_id = %s
                ORDER BY created_at DESC
                LIMIT 3
            """, (device_id,))
            for row in cursor.fetchall():
                print(f"    - {row['method']}, 用户={row['user_id']}, "
                      f"状态={row['status']}, 时间={row['created_at']}")
        
        # 检查 visit_records 表
        cursor.execute("""
            SELECT COUNT(*) as count FROM visit_records
        """)
        visit_count = cursor.fetchone()['count']
        print(f"  visit_records: {visit_count} 条记录")
        
        if visit_count > 0:
            cursor.execute("""
                SELECT vr.id, vr.person_id, p.name as person_name, 
                       vr.recognition_result, vr.access_granted, vr.visit_time
                FROM visit_records vr
                LEFT JOIN persons p ON vr.person_id = p.id
                ORDER BY vr.visit_time DESC
                LIMIT 3
            """)
            for row in cursor.fetchall():
                print(f"    - {row.get('person_name', '陌生人')}, "
                      f"结果={row['recognition_result']}, "
                      f"授权={row['access_granted']}, 时间={row['visit_time']}")
        
        # 检查 device_events 表
        cursor.execute("""
            SELECT COUNT(*) as count FROM device_events WHERE device_id = %s
        """, (device_id,))
        event_count = cursor.fetchone()['count']
        print(f"  device_events: {event_count} 条记录")
        
        # 检查 persons 表
        cursor.execute("""
            SELECT COUNT(*) as count FROM persons
        """)
        person_count = cursor.fetchone()['count']
        print(f"  persons: {person_count} 条记录")
        
        print("\n" + "="*60)
        print("检查完成")
        print("="*60)
        
        # 如果没有数据，提示插入测试数据
        if status_count == 0 and log_count == 0 and visit_count == 0:
            print("\n提示: 数据库中没有测试数据")
            print("建议: 运行以下命令插入测试数据")
            print("  python test/insert_test_data.py")
        
    except Exception as e:
        print(f"✗ 查询失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
