#!/usr/bin/env python3
"""
插入测试数据到数据库

为设备 AA:BB:CC:DD:EE:FF 插入：
- 设备状态记录
- 开锁日志
- 到访记录
"""
import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ruamel.yaml import YAML
from core.providers.doorlock.database import Database
from config.logger import setup_logging


def main():
    """主函数"""
    print("="*60)
    print("插入测试数据")
    print("="*60)
    
    # 加载配置
    yaml = YAML()
    with open('config/doorlock_config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.load(f)
    
    mysql_config = config.get('mysql', {})
    device_id = "AA:BB:CC:DD:EE:FF"
    
    print(f"\n目标设备: {device_id}")
    print(f"数据库: {mysql_config.get('database')}")
    
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
    
    conn = None
    cursor = None
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        print("\n开始插入测试数据...")
        print("-"*60)
        
        # 1. 插入设备状态记录（最近5条）
        print("\n1. 插入设备状态记录...")
        now = datetime.now()
        for i in range(5):
            created_at = now - timedelta(minutes=i*10)
            battery = 85 - i*5  # 电量逐渐降低
            lux = 300 + i*50    # 光照逐渐增加
            lock_state = 1 if i % 2 == 0 else 0  # 交替锁定/解锁
            light_state = 0 if i % 3 == 0 else 1  # 补光灯状态
            
            cursor.execute("""
                INSERT INTO device_status (device_id, battery, lux, lock_state, light_state, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (device_id, battery, lux, lock_state, light_state, created_at))
        
        print(f"  ✓ 已插入 5 条设备状态记录")
        
        # 2. 插入开锁日志（最近10条）
        print("\n2. 插入开锁日志...")
        methods = ['password', 'fingerprint', 'nfc', 'face', 'app']
        statuses = ['success', 'success', 'success', 'fail', 'success']  # 大部分成功
        
        for i in range(10):
            created_at = now - timedelta(hours=i*2)
            method = methods[i % len(methods)]
            status = statuses[i % len(statuses)]
            user_id = (i % 3) + 1  # 用户ID: 1, 2, 3
            fail_count = 1 if status == 'fail' else 0
            lock_time = 5 if status == 'fail' and i % 5 == 0 else 0
            
            cursor.execute("""
                INSERT INTO unlock_logs (device_id, method, user_id, status, fail_count, lock_time, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (device_id, method, user_id, status, fail_count, lock_time, created_at))
        
        print(f"  ✓ 已插入 10 条开锁日志")
        
        # 3. 插入到访记录（最近8条）
        print("\n3. 插入到访记录...")
        
        # 先确保有人员记录
        cursor.execute("SELECT COUNT(*) as count FROM persons")
        person_count = cursor.fetchone()[0]
        
        if person_count == 0:
            print("  ! 没有人员记录，先插入测试人员...")
            cursor.execute("""
                INSERT INTO persons (name, relation_type, custom_greeting)
                VALUES 
                ('张三', 'family', '欢迎回家'),
                ('李四', 'friend', '欢迎来访'),
                ('快递员', 'courier', NULL)
            """)
            print("  ✓ 已插入 3 条人员记录")
        
        # 获取人员ID
        cursor.execute("SELECT id FROM persons LIMIT 3")
        person_ids = [row[0] for row in cursor.fetchall()]
        
        results = ['known', 'known', 'unknown', 'no_face']
        access_granted_list = [True, True, False, False]
        
        for i in range(8):
            created_at = now - timedelta(hours=i*3)
            result = results[i % len(results)]
            access_granted = access_granted_list[i % len(access_granted_list)]
            person_id = person_ids[i % len(person_ids)] if result == 'known' and person_ids else None
            deny_reason = '未授权' if not access_granted and result == 'known' else None
            photo_path = f'/data/photos/visit_{i}.jpg'
            
            cursor.execute("""
                INSERT INTO visit_records (person_id, recognition_result, access_granted, deny_reason, photo_path, visit_time)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (person_id, result, access_granted, deny_reason, photo_path, created_at))
        
        print(f"  ✓ 已插入 8 条到访记录")
        
        # 4. 插入设备事件（最近5条）
        print("\n4. 插入设备事件...")
        event_types = ['pir', 'door_open', 'door_close', 'alarm', 'low_battery']
        
        for i in range(5):
            created_at = now - timedelta(hours=i*4)
            event_type = event_types[i % len(event_types)]
            param = i + 1
            
            cursor.execute("""
                INSERT INTO device_events (device_id, event_type, param, created_at)
                VALUES (%s, %s, %s, %s)
            """, (device_id, event_type, param, created_at))
        
        print(f"  ✓ 已插入 5 条设备事件")
        
        # 提交事务
        conn.commit()
        
        print("\n" + "="*60)
        print("✓ 测试数据插入完成")
        print("="*60)
        
        # 显示统计
        print("\n数据统计:")
        cursor.execute("SELECT COUNT(*) as count FROM device_status WHERE device_id = %s", (device_id,))
        print(f"  device_status: {cursor.fetchone()[0]} 条")
        
        cursor.execute("SELECT COUNT(*) as count FROM unlock_logs WHERE device_id = %s", (device_id,))
        print(f"  unlock_logs: {cursor.fetchone()[0]} 条")
        
        cursor.execute("SELECT COUNT(*) as count FROM visit_records")
        print(f"  visit_records: {cursor.fetchone()[0]} 条")
        
        cursor.execute("SELECT COUNT(*) as count FROM device_events WHERE device_id = %s", (device_id,))
        print(f"  device_events: {cursor.fetchone()[0]} 条")
        
        cursor.execute("SELECT COUNT(*) as count FROM persons")
        print(f"  persons: {cursor.fetchone()[0]} 条")
        
        print("\n现在可以运行测试脚本验证推送功能:")
        print("  python test/test_app_initial_push.py")
        
    except Exception as e:
        print(f"\n✗ 插入失败: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
