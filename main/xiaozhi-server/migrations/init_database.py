#!/usr/bin/env python3
"""
初始化数据库表结构

此脚本会创建所有必需的表（如果不存在）
"""

import sys
from pathlib import Path

# 添加父目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.providers.doorlock.database import Database

# 数据库配置
config = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'database': 'smart_doorlock',
    'pool_size': 5
}

print("="*60)
print("初始化数据库表结构")
print("="*60)
print(f"数据库: {config['host']}:{config['port']}/{config['database']}")
print()

try:
    # 创建 Database 实例，这会自动初始化所有表
    db = Database(config)
    print("✓ 数据库表初始化成功")
    print()
    print("已创建的表:")
    print("  - persons (人员信息)")
    print("  - access_permissions (访问权限)")
    print("  - visit_records (访问记录)")
    print("  - device_status (设备状态)")
    print("  - device_events (设备事件)")
    print("  - unlock_logs (开锁日志)")
    print("  - door_opened_logs (开门日志)")
    print("  - doorlock_users (门锁用户)")
    print("  - media_files (媒体文件)")
    print()
    print("="*60)
    print("✓ 数据库初始化完成，可以执行迁移脚本了")
    print("="*60)
    
except Exception as e:
    print(f"✗ 数据库初始化失败: {e}")
    import traceback
    print(traceback.format_exc())
    sys.exit(1)
