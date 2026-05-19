"""
检查 doorlock_users 表数据
"""
import sys
sys.path.insert(0, 'C:\\Users\\yunxi\\Desktop\\graduation_project\\xiaozhi-server\\xiaozhi-esp32-server\\main\\xiaozhi-server')

from config.config_loader import load_config
from core.providers.doorlock.database import Database

config = load_config()
mysql_config = config.get('mysql', {})
db = Database(mysql_config, auto_init=False)

# 查询 doorlock_users 表
conn = db.get_connection()
cursor = conn.cursor(dictionary=True)

print("=" * 60)
print("检查 doorlock_users 表数据")
print("=" * 60)

# 检查表是否存在
cursor.execute("""
    SELECT COUNT(*) as count 
    FROM information_schema.tables 
    WHERE table_schema = DATABASE() 
    AND table_name = 'doorlock_users'
""")
table_exists = cursor.fetchone()['count']
print(f'\n1. doorlock_users 表是否存在: {table_exists > 0}')

if table_exists:
    # 查询所有数据
    cursor.execute('SELECT * FROM doorlock_users')
    users = cursor.fetchall()
    print(f'\n2. doorlock_users 表总记录数: {len(users)}')
    
    if users:
        print('\n3. 前 5 条记录:')
        for user in users[:5]:
            print(f'  - device_id={user["device_id"]}, user_id={user["user_id"]}, name={user.get("name", "")}')
    else:
        print('\n3. 表中没有数据 ❌')
        print('\n可能原因:')
        print('  - 设备从未添加过用户（指纹、NFC、人脸）')
        print('  - 数据库迁移未完成')
        print('  - 用户数据在其他表中')
        
    # 查询特定设备
    device_id = 'e8:f6:0a:83:8f:50'
    cursor.execute('SELECT * FROM doorlock_users WHERE device_id = %s', (device_id,))
    device_users = cursor.fetchall()
    print(f'\n4. 设备 {device_id} 的用户数: {len(device_users)}')
    
    # 检查其他相关表
    print('\n5. 检查其他用户相关表:')
    
    # persons 表（人脸识别用户）
    cursor.execute('SELECT COUNT(*) as count FROM persons')
    persons_count = cursor.fetchone()['count']
    print(f'  - persons 表（人脸用户）: {persons_count} 条记录')
    
    # 检查是否有表结构问题
    print('\n6. doorlock_users 表结构:')
    cursor.execute('DESCRIBE doorlock_users')
    columns = cursor.fetchall()
    for col in columns:
        print(f'  - {col["Field"]}: {col["Type"]}')

cursor.close()
conn.close()

print("\n" + "=" * 60)
