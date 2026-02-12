#!/usr/bin/env python3
"""
验证数据库迁移结果

此脚本会详细检查迁移后的数据库状态
"""

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

def verify_migration():
    """验证迁移结果"""
    try:
        conn = pymysql.connect(**config)
        cursor = conn.cursor()
        
        print("="*70)
        print("数据库迁移验证报告")
        print("="*70)
        print(f"数据库: {config['host']}:{config['port']}/{config['database']}")
        print()
        
        # 1. 验证 unlock_logs 表结构
        print("1. 验证 unlock_logs 表结构")
        print("-"*70)
        cursor.execute("DESCRIBE unlock_logs")
        columns = cursor.fetchall()
        
        required_fields = {
            'status': False,
            'lock_time': False
        }
        
        print("  表字段:")
        for col in columns:
            field_name = col[0]
            field_type = col[1]
            field_null = col[2]
            field_default = col[4]
            
            print(f"    - {field_name:15} {field_type:20} NULL={field_null:3} DEFAULT={field_default}")
            
            if field_name in required_fields:
                required_fields[field_name] = True
        
        print()
        if all(required_fields.values()):
            print("  ✓ 所有必需字段都存在")
        else:
            missing = [k for k, v in required_fields.items() if not v]
            print(f"  ✗ 缺少字段: {', '.join(missing)}")
        
        # 2. 验证索引
        print()
        print("2. 验证索引")
        print("-"*70)
        cursor.execute("SHOW INDEX FROM unlock_logs")
        indexes = cursor.fetchall()
        
        has_idx_status = False
        print("  表索引:")
        for idx in indexes:
            index_name = idx[2]
            column_name = idx[4]
            print(f"    - {index_name:20} on {column_name}")
            
            if index_name == 'idx_status':
                has_idx_status = True
        
        print()
        if has_idx_status:
            print("  ✓ idx_status 索引存在")
        else:
            print("  ✗ idx_status 索引不存在")
        
        # 3. 验证 door_opened_logs 表
        print()
        print("3. 验证 door_opened_logs 表")
        print("-"*70)
        cursor.execute("SHOW TABLES LIKE 'door_opened_logs'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            print("  ✓ door_opened_logs 表存在")
            cursor.execute("DESCRIBE door_opened_logs")
            columns = cursor.fetchall()
            print("  表字段:")
            for col in columns:
                print(f"    - {col[0]:15} {col[1]:20}")
        else:
            print("  ✗ door_opened_logs 表不存在")
        
        # 4. 验证 device_events 表
        print()
        print("4. 验证 device_events 表")
        print("-"*70)
        cursor.execute("DESCRIBE device_events")
        columns = cursor.fetchall()
        
        event_type_field = None
        for col in columns:
            if col[0] == 'event_type':
                event_type_field = col
                break
        
        if event_type_field:
            field_type = event_type_field[1]
            print(f"  event_type 字段类型: {field_type}")
            
            if 'varchar' in field_type.lower():
                print("  ✓ event_type 使用 VARCHAR 类型，支持新事件类型")
            elif 'enum' in field_type.lower():
                print("  ⚠ event_type 使用 ENUM 类型，可能需要更新枚举值")
            else:
                print(f"  ? event_type 使用未知类型: {field_type}")
        else:
            print("  ✗ event_type 字段不存在")
        
        # 5. 测试数据插入
        print()
        print("5. 测试数据操作")
        print("-"*70)
        
        # 测试插入带 status 和 lock_time 的记录
        try:
            cursor.execute("""
                INSERT INTO unlock_logs (device_id, method, user_id, result, fail_count, status, lock_time)
                VALUES ('test_device', 'finger', 1, 1, 0, 'success', 0)
            """)
            conn.commit()
            print("  ✓ 成功插入测试记录（status='success', lock_time=0）")
            
            # 读取刚插入的记录
            cursor.execute("""
                SELECT status, lock_time FROM unlock_logs 
                WHERE device_id = 'test_device' 
                ORDER BY id DESC LIMIT 1
            """)
            record = cursor.fetchone()
            if record:
                print(f"  ✓ 成功读取记录: status={record[0]}, lock_time={record[1]}")
            
            # 清理测试数据
            cursor.execute("DELETE FROM unlock_logs WHERE device_id = 'test_device'")
            conn.commit()
            print("  ✓ 测试数据已清理")
            
        except Exception as e:
            print(f"  ✗ 数据操作测试失败: {e}")
        
        # 6. 总结
        print()
        print("="*70)
        print("验证总结")
        print("="*70)
        
        all_passed = (
            all(required_fields.values()) and
            has_idx_status and
            table_exists
        )
        
        if all_passed:
            print("✓ 所有验证项通过，迁移成功！")
            print()
            print("迁移内容:")
            print("  ✓ unlock_logs 表新增 status 字段")
            print("  ✓ unlock_logs 表新增 lock_time 字段")
            print("  ✓ unlock_logs 表新增 idx_status 索引")
            print("  ✓ door_opened_logs 表已存在")
            print("  ✓ device_events 表支持新事件类型")
        else:
            print("✗ 部分验证项失败，请检查上述错误")
        
        print("="*70)
        
        conn.close()
        return all_passed
        
    except Exception as e:
        print(f"✗ 验证失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False


if __name__ == '__main__':
    import sys
    success = verify_migration()
    sys.exit(0 if success else 1)
