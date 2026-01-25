#!/usr/bin/env python3
"""
验证数据库迁移脚本

此脚本验证迁移脚本的语法和结构是否正确
"""

import sys
from pathlib import Path

# 添加父目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def verify_migration_script():
    """验证迁移脚本"""
    script_path = Path(__file__).parent.parent / "migrations" / "upgrade_v5.0_to_v5.2.sql"
    
    print(f"验证迁移脚本: {script_path}")
    
    # 检查文件是否存在
    if not script_path.exists():
        print(f"✗ 迁移脚本不存在: {script_path}")
        return False
    
    print("✓ 迁移脚本文件存在")
    
    # 读取脚本内容
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 验证关键内容
    checks = [
        ("ALTER TABLE unlock_logs", "包含 unlock_logs 表修改语句"),
        ("'status'", "包含 status 字段添加语句"),
        ("'lock_time'", "包含 lock_time 字段添加语句"),
        ("'idx_status'", "包含 idx_status 索引创建语句"),
        ("UPDATE unlock_logs", "包含数据迁移语句"),
        ("door_opened_logs", "包含 door_opened_logs 表验证"),
        ("device_events", "包含 device_events 表验证"),
    ]
    
    all_passed = True
    for keyword, description in checks:
        if keyword in content:
            print(f"✓ {description}")
        else:
            print(f"✗ {description}")
            all_passed = False
    
    # 验证 SQL 语法基本结构
    print("\n验证 SQL 语法结构:")
    
    # 检查是否有未闭合的括号
    open_parens = content.count('(')
    close_parens = content.count(')')
    if open_parens == close_parens:
        print(f"✓ 括号匹配 ({open_parens} 对)")
    else:
        print(f"✗ 括号不匹配: 开括号 {open_parens}, 闭括号 {close_parens}")
        all_passed = False
    
    # 检查是否有基本的 SQL 关键字
    sql_keywords = ['ALTER', 'CREATE', 'UPDATE', 'SELECT', 'TABLE', 'INDEX']
    for keyword in sql_keywords:
        if keyword in content.upper():
            print(f"✓ 包含 {keyword} 关键字")
        else:
            print(f"✗ 缺少 {keyword} 关键字")
    
    # 统计语句数量
    statements = [s.strip() for s in content.split(';') if s.strip() and not s.strip().startswith('--')]
    print(f"\n✓ 共 {len(statements)} 条 SQL 语句")
    
    # 验证编码
    try:
        content.encode('utf-8')
        print("✓ 文件编码正确 (UTF-8)")
    except UnicodeEncodeError:
        print("✗ 文件编码错误")
        all_passed = False
    
    # 验证文件大小
    file_size = script_path.stat().st_size
    print(f"✓ 文件大小: {file_size} 字节")
    
    if file_size < 100:
        print("✗ 文件太小，可能内容不完整")
        all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ 所有验证通过")
        return True
    else:
        print("✗ 部分验证失败")
        return False


def verify_migration_runner():
    """验证迁移执行脚本"""
    script_path = Path(__file__).parent.parent / "migrations" / "run_migration.py"
    
    print(f"\n验证迁移执行脚本: {script_path}")
    
    # 检查文件是否存在
    if not script_path.exists():
        print(f"✗ 迁移执行脚本不存在: {script_path}")
        return False
    
    print("✓ 迁移执行脚本文件存在")
    
    # 读取脚本内容
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 验证关键函数
    checks = [
        ("def execute_migration", "包含 execute_migration 函数"),
        ("def load_config", "包含 load_config 函数"),
        ("def get_db_config_from_yaml", "包含 get_db_config_from_yaml 函数"),
        ("def main", "包含 main 函数"),
        ("import pymysql", "导入 pymysql 模块"),
        ("import argparse", "导入 argparse 模块"),
    ]
    
    all_passed = True
    for keyword, description in checks:
        if keyword in content:
            print(f"✓ {description}")
        else:
            print(f"✗ {description}")
            all_passed = False
    
    # 验证 Python 语法
    try:
        compile(content, script_path, 'exec')
        print("✓ Python 语法正确")
    except SyntaxError as e:
        print(f"✗ Python 语法错误: {e}")
        all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ 所有验证通过")
        return True
    else:
        print("✗ 部分验证失败")
        return False


def verify_readme():
    """验证 README 文件"""
    readme_path = Path(__file__).parent.parent / "migrations" / "README.md"
    
    print(f"\n验证 README 文件: {readme_path}")
    
    # 检查文件是否存在
    if not readme_path.exists():
        print(f"✗ README 文件不存在: {readme_path}")
        return False
    
    print("✓ README 文件存在")
    
    # 读取内容
    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 验证关键章节
    checks = [
        ("# 数据库迁移脚本", "包含标题"),
        ("upgrade_v5.0_to_v5.2.sql", "包含迁移脚本说明"),
        ("执行方式", "包含执行方式说明"),
        ("验证迁移结果", "包含验证说明"),
        ("回滚迁移", "包含回滚说明"),
        ("注意事项", "包含注意事项"),
    ]
    
    all_passed = True
    for keyword, description in checks:
        if keyword in content:
            print(f"✓ {description}")
        else:
            print(f"✗ {description}")
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ 所有验证通过")
        return True
    else:
        print("✗ 部分验证失败")
        return False


def main():
    """主函数"""
    print("="*60)
    print("数据库迁移脚本验证")
    print("="*60)
    
    results = []
    
    # 验证迁移脚本
    results.append(("迁移脚本", verify_migration_script()))
    
    # 验证执行脚本
    results.append(("执行脚本", verify_migration_runner()))
    
    # 验证 README
    results.append(("README", verify_readme()))
    
    # 总结
    print("\n" + "="*60)
    print("验证总结")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("="*60)
    if all_passed:
        print("✓ 所有验证通过，迁移脚本准备就绪")
        return 0
    else:
        print("✗ 部分验证失败，请检查上述错误")
        return 1


if __name__ == '__main__':
    sys.exit(main())
