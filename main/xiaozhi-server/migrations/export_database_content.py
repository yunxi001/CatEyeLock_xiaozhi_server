#!/usr/bin/env python3
"""
导出数据库内容到文档
此脚本会读取数据库中所有表的数据，并生成一个汇总文档
"""

import sys
from pathlib import Path
from datetime import datetime
import json

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

def format_datetime(dt):
    """格式化日期时间"""
    if dt is None:
        return "N/A"
    if isinstance(dt, str):
        return dt
    try:
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return str(dt)

def export_database_content():
    """导出数据库内容"""
    print("="*80)
    print("数据库内容导出工具")
    print("="*80)
    print(f"数据库: {config['host']}:{config['port']}/{config['database']}")
    print(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # 创建数据库连接（不自动初始化表）
        db = Database(config, auto_init=False)
        
        # 准备文档内容
        doc_lines = []
        doc_lines.append("# 智能门锁数据库内容汇总报告")
        doc_lines.append("")
        doc_lines.append(f"**导出时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        doc_lines.append(f"**数据库**: {config['database']}")
        doc_lines.append(f"**服务器**: {config['host']}:{config['port']}")
        doc_lines.append("")
        doc_lines.append("---")
        doc_lines.append("")
        
        # 1. 人员信息表
        print("正在读取 persons 表...")
        persons = db.get_all_persons()
        doc_lines.append("## 1. 人员信息 (persons)")
        doc_lines.append("")
        doc_lines.append(f"**总记录数**: {len(persons)}")
        doc_lines.append("")
        if persons:
            doc_lines.append("| ID | 姓名 | 关系类型 | 是否有人脸 | 照片路径 | 自定义问候语 | 创建时间 |")
            doc_lines.append("|---|---|---|---|---|---|---|")
            for p in persons:
                has_face = "✓" if p.face_encoding is not None else "✗"
                greeting = p.custom_greeting if p.custom_greeting else "-"
                photo = p.photo_path if p.photo_path else "-"
                doc_lines.append(f"| {p.id} | {p.name} | {p.relation_type} | {has_face} | {photo} | {greeting} | {format_datetime(p.created_at)} |")
        else:
            doc_lines.append("*暂无数据*")
        doc_lines.append("")
        
        # 2. 访问权限表
        print("正在读取 access_permissions 表...")
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM access_permissions ORDER BY created_at DESC")
        permissions = cursor.fetchall()
        cursor.close()
        conn.close()
        
        doc_lines.append("## 2. 访问权限 (access_permissions)")
        doc_lines.append("")
        doc_lines.append(f"**总记录数**: {len(permissions)}")
        doc_lines.append("")
        if permissions:
            doc_lines.append("| ID | 人员ID | 权限类型 | 时间段 | 日期类型 | 剩余次数 | 有效期 | 状态 |")
            doc_lines.append("|---|---|---|---|---|---|---|---|")
            for perm in permissions:
                time_range = f"{perm.get('time_start', 'N/A')} - {perm.get('time_end', 'N/A')}"
                valid_range = f"{perm.get('valid_from', 'N/A')} ~ {perm.get('valid_until', 'N/A')}"
                status = "启用" if perm.get('is_active') else "禁用"
                doc_lines.append(f"| {perm['id']} | {perm['person_id']} | {perm['permission_type']} | {time_range} | {perm['day_type']} | {perm.get('remaining_count', 'N/A')} | {valid_range} | {status} |")
        else:
            doc_lines.append("*暂无数据*")
        doc_lines.append("")
        
        # 3. 访问记录表
        print("正在读取 visit_records 表...")
        visits, total_visits = db.get_visits(page=1, page_size=100)
        doc_lines.append("## 3. 访问记录 (visit_records)")
        doc_lines.append("")
        doc_lines.append(f"**总记录数**: {total_visits} (显示最近100条)")
        doc_lines.append("")
        if visits:
            doc_lines.append("| ID | 人员 | 识别结果 | 是否允许 | 拒绝原因 | 访问时间 |")
            doc_lines.append("|---|---|---|---|---|---|")
            for v in visits:
                person_name = v.get('person_name', '未知')
                access = "✓" if v['access_granted'] else "✗"
                deny_reason = v.get('deny_reason', '-')
                doc_lines.append(f"| {v['id']} | {person_name} | {v['result']} | {access} | {deny_reason} | {v.get('visit_time', 'N/A')} |")
        else:
            doc_lines.append("*暂无数据*")
        doc_lines.append("")
        
        # 4. 设备信息表
        print("正在读取 device_info 表...")
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM device_info ORDER BY created_at DESC")
        devices = cursor.fetchall()
        cursor.close()
        conn.close()
        
        doc_lines.append("## 4. 设备信息 (device_info)")
        doc_lines.append("")
        doc_lines.append(f"**总记录数**: {len(devices)}")
        doc_lines.append("")
        if devices:
            doc_lines.append("| ID | 设备ID | 密码状态 | 创建时间 | 更新时间 |")
            doc_lines.append("|---|---|---|---|---|")
            for dev in devices:
                pwd_status = "已设置" if dev.get('password_encrypted') else "未设置"
                doc_lines.append(f"| {dev['id']} | {dev['device_id']} | {pwd_status} | {format_datetime(dev.get('created_at'))} | {format_datetime(dev.get('updated_at'))} |")
        else:
            doc_lines.append("*暂无数据*")
        doc_lines.append("")
        
        # 5. 设备状态表（最近记录）
        print("正在读取 device_status 表...")
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM device_status ORDER BY created_at DESC LIMIT 50")
        statuses = cursor.fetchall()
        cursor.close()
        conn.close()
        
        doc_lines.append("## 5. 设备状态 (device_status)")
        doc_lines.append("")
        doc_lines.append(f"**显示**: 最近50条记录")
        doc_lines.append("")
        if statuses:
            doc_lines.append("| ID | 设备ID | 电池 | 光照 | 门锁状态 | 灯光状态 | 记录时间 |")
            doc_lines.append("|---|---|---|---|---|---|---|")
            for s in statuses:
                doc_lines.append(f"| {s['id']} | {s['device_id']} | {s.get('battery', 'N/A')}% | {s.get('lux', 'N/A')} | {s.get('lock_state', 'N/A')} | {s.get('light_state', 'N/A')} | {format_datetime(s.get('created_at'))} |")
        else:
            doc_lines.append("*暂无数据*")
        doc_lines.append("")
        
        # 6. 设备事件表（最近记录）
        print("正在读取 device_events 表...")
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM device_events ORDER BY created_at DESC LIMIT 50")
        events = cursor.fetchall()
        cursor.close()
        conn.close()
        
        doc_lines.append("## 6. 设备事件 (device_events)")
        doc_lines.append("")
        doc_lines.append(f"**显示**: 最近50条记录")
        doc_lines.append("")
        if events:
            doc_lines.append("| ID | 设备ID | 事件类型 | 参数 | 发生时间 |")
            doc_lines.append("|---|---|---|---|---|")
            for e in events:
                doc_lines.append(f"| {e['id']} | {e['device_id']} | {e['event_type']} | {e.get('param', 'N/A')} | {format_datetime(e.get('created_at'))} |")
        else:
            doc_lines.append("*暂无数据*")
        doc_lines.append("")
        
        # 7. 开锁日志表（最近记录）
        print("正在读取 unlock_logs 表...")
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM unlock_logs ORDER BY created_at DESC LIMIT 50")
        unlock_logs = cursor.fetchall()
        cursor.close()
        conn.close()
        
        doc_lines.append("## 7. 开锁日志 (unlock_logs)")
        doc_lines.append("")
        doc_lines.append(f"**显示**: 最近50条记录")
        doc_lines.append("")
        if unlock_logs:
            doc_lines.append("| ID | 设备ID | 开锁方式 | 用户ID | 结果 | 失败次数 | 状态 | 锁定时间 | 操作时间 |")
            doc_lines.append("|---|---|---|---|---|---|---|---|---|")
            for log in unlock_logs:
                result = "成功" if log.get('result') == 1 else "失败"
                status = log.get('status', 'N/A')
                lock_time = f"{log.get('lock_time', 0)}分钟" if log.get('lock_time') else "-"
                doc_lines.append(f"| {log['id']} | {log['device_id']} | {log['method']} | {log.get('user_id', 'N/A')} | {result} | {log.get('fail_count', 0)} | {status} | {lock_time} | {format_datetime(log.get('created_at'))} |")
        else:
            doc_lines.append("*暂无数据*")
        doc_lines.append("")
        
        # 8. 开门日志表（最近记录）
        print("正在读取 door_opened_logs 表...")
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM door_opened_logs ORDER BY created_at DESC LIMIT 50")
        door_logs = cursor.fetchall()
        cursor.close()
        conn.close()
        
        doc_lines.append("## 8. 开门日志 (door_opened_logs)")
        doc_lines.append("")
        doc_lines.append(f"**显示**: 最近50条记录")
        doc_lines.append("")
        if door_logs:
            doc_lines.append("| ID | 设备ID | 开锁方式 | 开门来源 | 开门时间 |")
            doc_lines.append("|---|---|---|---|---|")
            for log in door_logs:
                doc_lines.append(f"| {log['id']} | {log['device_id']} | {log['method']} | {log['source']} | {format_datetime(log.get('created_at'))} |")
        else:
            doc_lines.append("*暂无数据*")
        doc_lines.append("")
        
        # 9. 门锁用户表
        print("正在读取 doorlock_users 表...")
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM doorlock_users ORDER BY created_at DESC")
        doorlock_users = cursor.fetchall()
        cursor.close()
        conn.close()
        
        doc_lines.append("## 9. 门锁用户 (doorlock_users)")
        doc_lines.append("")
        doc_lines.append(f"**总记录数**: {len(doorlock_users)}")
        doc_lines.append("")
        if doorlock_users:
            doc_lines.append("| ID | 设备ID | 用户ID | 姓名 | 角色 | 指纹数 | NFC卡数 | 人脸 | 创建时间 |")
            doc_lines.append("|---|---|---|---|---|---|---|---|---|")
            for user in doorlock_users:
                finger_count = len(json.loads(user.get('finger_ids', '[]'))) if user.get('finger_ids') else 0
                nfc_count = len(json.loads(user.get('nfc_ids', '[]'))) if user.get('nfc_ids') else 0
                face_status = "✓" if user.get('face_registered') else "✗"
                doc_lines.append(f"| {user['id']} | {user['device_id']} | {user['user_id']} | {user.get('name', 'N/A')} | {user.get('role', 'N/A')} | {finger_count} | {nfc_count} | {face_status} | {format_datetime(user.get('created_at'))} |")
        else:
            doc_lines.append("*暂无数据*")
        doc_lines.append("")
        
        # 10. 媒体文件表（最近记录）
        print("正在读取 media_files 表...")
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM media_files ORDER BY created_at DESC LIMIT 50")
        media_files = cursor.fetchall()
        cursor.close()
        conn.close()
        
        doc_lines.append("## 10. 媒体文件 (media_files)")
        doc_lines.append("")
        doc_lines.append(f"**显示**: 最近50条记录")
        doc_lines.append("")
        if media_files:
            doc_lines.append("| ID | 设备ID | 文件类型 | 文件路径 | 文件大小 | 时长 | 用户ID | 创建时间 |")
            doc_lines.append("|---|---|---|---|---|---|---|---|")
            for mf in media_files:
                file_size = f"{mf.get('file_size', 0)} bytes" if mf.get('file_size') else "N/A"
                duration = f"{mf.get('duration', 0)}s" if mf.get('duration') else "N/A"
                doc_lines.append(f"| {mf['id']} | {mf['device_id']} | {mf['file_type']} | {mf.get('file_path', 'N/A')} | {file_size} | {duration} | {mf.get('user_id', 'N/A')} | {format_datetime(mf.get('created_at'))} |")
        else:
            doc_lines.append("*暂无数据*")
        doc_lines.append("")
        
        # 统计信息
        doc_lines.append("---")
        doc_lines.append("")
        doc_lines.append("## 数据统计汇总")
        doc_lines.append("")
        doc_lines.append(f"- **人员总数**: {len(persons)}")
        doc_lines.append(f"- **权限配置数**: {len(permissions)}")
        doc_lines.append(f"- **访问记录数**: {total_visits}")
        doc_lines.append(f"- **设备数量**: {len(devices)}")
        doc_lines.append(f"- **门锁用户数**: {len(doorlock_users)}")
        doc_lines.append("")
        
        # 写入文件
        output_file = Path(__file__).parent.parent / "docs" / "database_content_report.md"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(doc_lines))
        
        print()
        print("="*80)
        print(f"✓ 数据库内容导出成功")
        print(f"✓ 报告文件: {output_file}")
        print("="*80)
        
        return str(output_file)
        
    except Exception as e:
        print(f"✗ 导出失败: {e}")
        import traceback
        print(traceback.format_exc())
        return None

if __name__ == "__main__":
    export_database_content()
