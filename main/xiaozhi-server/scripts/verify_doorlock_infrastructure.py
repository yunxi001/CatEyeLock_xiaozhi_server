#!/usr/bin/env python3
"""
智能门锁AI功能基础设施验证脚本

验证内容：
1. 数据库迁移脚本存在性
2. 配置文件格式正确性
3. 数据模型定义完整性
"""

import sys
import os
from pathlib import Path
import yaml


def verify_migration_scripts():
    """验证数据库迁移脚本"""
    print("1. 验证数据库迁移脚本")
    print("-"*70)
    
    base_path = Path("main/xiaozhi-server/migrations")
    
    # 检查迁移脚本
    migration_sql = base_path / "add_doorlock_ai_tables.sql"
    if migration_sql.exists():
        print(f"  ✓ {migration_sql.name} 存在")
        # 检查文件内容
        content = migration_sql.read_text(encoding='utf-8')
        required_tables = [
            "doorlock_config",
            "doorlock_visitor_intents",
            "doorlock_package_alerts"
        ]
        for table in required_tables:
            if table in content:
                print(f"    ✓ 包含 {table} 表定义")
            else:
                print(f"    ✗ 缺少 {table} 表定义")
                return False
    else:
        print(f"  ✗ {migration_sql.name} 不存在")
        return False
    
    # 检查执行脚本
    run_script = base_path / "run_doorlock_ai_migration.py"
    if run_script.exists():
        print(f"  ✓ {run_script.name} 存在")
    else:
        print(f"  ✗ {run_script.name} 不存在")
        return False
    
    # 检查验证脚本
    verify_script = base_path / "verify_doorlock_ai_migration.py"
    if verify_script.exists():
        print(f"  ✓ {verify_script.name} 存在")
    else:
        print(f"  ✗ {verify_script.name} 不存在")
        return False
    
    print()
    return True


def verify_config_files():
    """验证配置文件"""
    print("2. 验证配置文件")
    print("-"*70)
    
    # 检查 config.yaml
    config_path = Path("main/xiaozhi-server/config.yaml")
    if config_path.exists():
        print(f"  ✓ {config_path.name} 存在")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 检查 doorlock 配置段
            if 'doorlock' in config:
                print(f"    ✓ doorlock 配置段存在")
                
                doorlock_config = config['doorlock']
                required_sections = [
                    'package_guard',
                    'intent_recognition',
                    'face_recognition',
                    'performance'
                ]
                
                for section in required_sections:
                    if section in doorlock_config:
                        print(f"      ✓ {section} 配置存在")
                    else:
                        print(f"      ✗ {section} 配置缺失")
                        return False
            else:
                print(f"    ✗ doorlock 配置段不存在")
                return False
                
        except yaml.YAMLError as e:
            print(f"    ✗ YAML 语法错误: {e}")
            return False
    else:
        print(f"  ✗ {config_path.name} 不存在")
        return False
    
    # 检查 doorlock_prompts.yaml
    prompts_path = Path("main/xiaozhi-server/config/doorlock_prompts.yaml")
    if prompts_path.exists():
        print(f"  ✓ {prompts_path.name} 存在")
        try:
            with open(prompts_path, 'r', encoding='utf-8') as f:
                prompts = yaml.safe_load(f)
            
            required_prompts = [
                'intent_recognition_prompt',
                'package_guard_prompt',
                'welcome_templates',
                'default_greeting'
            ]
            
            for prompt in required_prompts:
                if prompt in prompts:
                    print(f"    ✓ {prompt} 存在")
                else:
                    print(f"    ✗ {prompt} 缺失")
                    return False
                    
        except yaml.YAMLError as e:
            print(f"    ✗ YAML 语法错误: {e}")
            return False
    else:
        print(f"  ✗ {prompts_path.name} 不存在")
        return False
    
    # 检查示例文件
    example_path = Path("main/xiaozhi-server/config/doorlock_prompts.yaml.example")
    if example_path.exists():
        print(f"  ✓ {example_path.name} 存在")
    else:
        print(f"  ✗ {example_path.name} 不存在")
        return False
    
    print()
    return True


def verify_data_models():
    """验证数据模型"""
    print("3. 验证数据模型")
    print("-"*70)
    
    # 检查模型文件
    models_path = Path("main/xiaozhi-server/core/providers/doorlock/models.py")
    if models_path.exists():
        print(f"  ✓ {models_path.name} 存在")
    else:
        print(f"  ✗ {models_path.name} 不存在")
        return False
    
    # 尝试导入模型
    try:
        sys.path.insert(0, 'main/xiaozhi-server')
        from core.providers.doorlock.models import (
            DoorlockConfig,
            VisitorIntent,
            PackageAlert,
            DoorlockSession
        )
        print(f"  ✓ 数据模型导入成功")
        
        # 检查每个模型的必需方法
        models = {
            'DoorlockConfig': DoorlockConfig,
            'VisitorIntent': VisitorIntent,
            'PackageAlert': PackageAlert,
            'DoorlockSession': DoorlockSession
        }
        
        required_methods = ['to_dict', 'to_json', 'from_dict', 'from_json']
        
        for model_name, model_class in models.items():
            print(f"    检查 {model_name}:")
            for method in required_methods:
                if hasattr(model_class, method):
                    print(f"      ✓ {method} 方法存在")
                else:
                    print(f"      ✗ {method} 方法缺失")
                    return False
        
    except ImportError as e:
        print(f"  ✗ 数据模型导入失败: {e}")
        return False
    except Exception as e:
        print(f"  ✗ 验证失败: {e}")
        return False
    
    print()
    return True


def verify_type_annotations():
    """验证类型注解"""
    print("4. 验证类型注解")
    print("-"*70)
    
    models_path = Path("main/xiaozhi-server/core/providers/doorlock/models.py")
    content = models_path.read_text(encoding='utf-8')
    
    # 检查是否使用了类型注解
    type_hints = [
        'from typing import',
        'Optional[',
        'List[',
        'Dict[',
        'Any'
    ]
    
    for hint in type_hints:
        if hint in content:
            print(f"  ✓ 使用了 {hint}")
        else:
            print(f"  ⚠ 未使用 {hint}")
    
    # 检查是否使用了 dataclass
    if '@dataclass' in content:
        print(f"  ✓ 使用了 @dataclass 装饰器")
    else:
        print(f"  ✗ 未使用 @dataclass 装饰器")
        return False
    
    print()
    return True


def main():
    """主函数"""
    print("="*70)
    print("智能门锁AI功能基础设施验证")
    print("="*70)
    print()
    
    results = []
    
    # 执行所有验证
    results.append(("数据库迁移脚本", verify_migration_scripts()))
    results.append(("配置文件", verify_config_files()))
    results.append(("数据模型", verify_data_models()))
    results.append(("类型注解", verify_type_annotations()))
    
    # 打印总结
    print("="*70)
    print("验证总结")
    print("="*70)
    
    all_passed = True
    for name, result in results:
        status = "✓" if result else "✗"
        print(f"  {status} {name}")
        if not result:
            all_passed = False
    
    print()
    if all_passed:
        print("="*70)
        print("✓ 所有验证项通过，基础设施搭建完成！")
        print("="*70)
        print()
        print("已完成的工作:")
        print("  ✓ 数据库迁移脚本（add_doorlock_ai_tables.sql）")
        print("  ✓ 迁移执行脚本（run_doorlock_ai_migration.py）")
        print("  ✓ 迁移验证脚本（verify_doorlock_ai_migration.py）")
        print("  ✓ 主配置文件（config.yaml - doorlock 配置段）")
        print("  ✓ 提示词配置文件（doorlock_prompts.yaml）")
        print("  ✓ 提示词示例文件（doorlock_prompts.yaml.example）")
        print("  ✓ 数据模型定义（models.py）")
        print()
        print("下一步:")
        print("  1. 运行数据库迁移脚本创建表结构")
        print("  2. 实现核心服务（数据库服务、会话管理器等）")
        return 0
    else:
        print("="*70)
        print("✗ 部分验证项失败，请检查上述错误")
        print("="*70)
        return 1


if __name__ == '__main__':
    sys.exit(main())
