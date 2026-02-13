#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能门锁AI功能集成测试脚本

测试内容：
1. 数据模型导入
2. API处理器导入
3. 核心服务导入
4. 配置文件加载
5. 提示词配置加载
6. 数据库连接（可选）
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试所有关键模块的导入"""
    print("=" * 70)
    print("1. 测试模块导入")
    print("=" * 70)
    
    tests = []
    
    # 测试数据模型
    try:
        from core.providers.doorlock.models import (
            DoorlockConfig, VisitorIntent, PackageAlert, DoorlockSession
        )
        print("✓ 数据模型导入成功")
        tests.append(("数据模型", True))
    except Exception as e:
        print(f"✗ 数据模型导入失败: {e}")
        tests.append(("数据模型", False))
    
    # 测试数据库服务
    try:
        from core.providers.doorlock.doorlock_database import DoorlockDatabase
        print("✓ 数据库服务导入成功")
        tests.append(("数据库服务", True))
    except Exception as e:
        print(f"✗ 数据库服务导入失败: {e}")
        tests.append(("数据库服务", False))
    
    # 测试会话管理器
    try:
        from core.providers.doorlock.session_manager import SessionManager
        print("✓ 会话管理器导入成功")
        tests.append(("会话管理器", True))
    except Exception as e:
        print(f"✗ 会话管理器导入失败: {e}")
        tests.append(("会话管理器", False))
    
    # 测试看护模式管理器
    try:
        from core.providers.doorlock.package_guard_manager import PackageGuardManager
        print("✓ 看护模式管理器导入成功")
        tests.append(("看护模式管理器", True))
    except Exception as e:
        print(f"✗ 看护模式管理器导入失败: {e}")
        tests.append(("看护模式管理器", False))
    
    # 测试通知服务
    try:
        from core.providers.doorlock.notification_service import NotificationService
        print("✓ 通知服务导入成功")
        tests.append(("通知服务", True))
    except Exception as e:
        print(f"✗ 通知服务导入失败: {e}")
        tests.append(("通知服务", False))
    
    # 测试工具函数
    try:
        from core.providers.doorlock.doorlock_tools import DoorlockTools
        print("✓ 工具函数导入成功")
        tests.append(("工具函数", True))
    except Exception as e:
        print(f"✗ 工具函数导入失败: {e}")
        tests.append(("工具函数", False))
    
    # 测试人脸识别处理器
    try:
        from core.providers.doorlock.face_recognition_handler import FaceRecognitionHandler
        print("✓ 人脸识别处理器导入成功")
        tests.append(("人脸识别处理器", True))
    except Exception as e:
        print(f"✗ 人脸识别处理器导入失败: {e}")
        tests.append(("人脸识别处理器", False))
    
    # 测试欢迎词处理器
    try:
        from core.providers.doorlock.greeting_handler import GreetingHandler
        print("✓ 欢迎词处理器导入成功")
        tests.append(("欢迎词处理器", True))
    except Exception as e:
        print(f"✗ 欢迎词处理器导入失败: {e}")
        tests.append(("欢迎词处理器", False))
    
    # 测试意图识别处理器
    try:
        from core.handle.doorlock_intent_handler import DoorlockIntentHandler
        print("✓ 意图识别处理器导入成功")
        tests.append(("意图识别处理器", True))
    except Exception as e:
        print(f"✗ 意图识别处理器导入失败: {e}")
        tests.append(("意图识别处理器", False))
    
    # 测试API处理器
    try:
        from core.api.doorlock_config_handler import DoorlockConfigHandler
        from core.api.doorlock_guard_handler import DoorlockGuardHandler
        from core.api.doorlock_welcome_handler import DoorlockWelcomeHandler
        from core.api.doorlock_history_handler import DoorlockHistoryHandler
        print("✓ API处理器导入成功")
        tests.append(("API处理器", True))
    except Exception as e:
        print(f"✗ API处理器导入失败: {e}")
        tests.append(("API处理器", False))
    
    # 测试HTTP服务器集成
    try:
        from core.http_server import SimpleHttpServer
        print("✓ HTTP服务器导入成功")
        tests.append(("HTTP服务器", True))
    except Exception as e:
        print(f"✗ HTTP服务器导入失败: {e}")
        tests.append(("HTTP服务器", False))
    
    print()
    return tests


def test_config():
    """测试配置文件加载"""
    print("=" * 70)
    print("2. 测试配置文件")
    print("=" * 70)
    
    tests = []
    
    # 测试主配置文件
    try:
        import yaml
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if 'doorlock' in config:
            print("✓ config.yaml 包含 doorlock 配置")
            
            # 检查必需的配置项
            required_keys = ['package_guard', 'intent_recognition', 'face_recognition', 'performance']
            missing_keys = [k for k in required_keys if k not in config['doorlock']]
            
            if not missing_keys:
                print("✓ doorlock 配置项完整")
                tests.append(("主配置文件", True))
            else:
                print(f"✗ doorlock 配置缺少: {missing_keys}")
                tests.append(("主配置文件", False))
        else:
            print("✗ config.yaml 缺少 doorlock 配置")
            tests.append(("主配置文件", False))
    except Exception as e:
        print(f"✗ 配置文件加载失败: {e}")
        tests.append(("主配置文件", False))
    
    # 测试提示词配置文件
    try:
        import yaml
        with open('config/doorlock_prompts.yaml', 'r', encoding='utf-8') as f:
            prompts = yaml.safe_load(f)
        
        required_prompts = ['intent_recognition_prompt', 'package_guard_prompt', 'welcome_templates']
        missing_prompts = [p for p in required_prompts if p not in prompts]
        
        if not missing_prompts:
            print("✓ doorlock_prompts.yaml 配置完整")
            tests.append(("提示词配置", True))
        else:
            print(f"✗ doorlock_prompts.yaml 缺少: {missing_prompts}")
            tests.append(("提示词配置", False))
    except Exception as e:
        print(f"✗ 提示词配置加载失败: {e}")
        tests.append(("提示词配置", False))
    
    print()
    return tests


def test_data_models():
    """测试数据模型的基本功能"""
    print("=" * 70)
    print("3. 测试数据模型功能")
    print("=" * 70)
    
    tests = []
    
    try:
        from core.providers.doorlock.models import (
            DoorlockConfig, VisitorIntent, PackageAlert, DoorlockSession
        )
        from datetime import datetime
        
        # 测试 DoorlockConfig
        config = DoorlockConfig(
            device_id="test_device",
            intent_recognition_enabled=True,
            package_guard_available=True
        )
        config_dict = config.to_dict()
        config_json = config.to_json()
        config_restored = DoorlockConfig.from_json(config_json)
        
        if config_restored.device_id == "test_device":
            print("✓ DoorlockConfig 序列化/反序列化正常")
            tests.append(("DoorlockConfig", True))
        else:
            print("✗ DoorlockConfig 序列化/反序列化失败")
            tests.append(("DoorlockConfig", False))
        
        # 测试 VisitorIntent
        intent = VisitorIntent(
            session_id="test_session",
            intent_type="delivery",
            intent_summary={"purpose": "送快递"}
        )
        intent_dict = intent.to_dict()
        intent_json = intent.to_json()
        
        print("✓ VisitorIntent 序列化正常")
        tests.append(("VisitorIntent", True))
        
        # 测试 PackageAlert
        alert = PackageAlert(
            device_id="test_device",
            session_id="test_session",
            threat_level="high",
            action="taking",
            description="检测到陌生人拿走快递"
        )
        alert_dict = alert.to_dict()
        alert_json = alert.to_json()
        
        print("✓ PackageAlert 序列化正常")
        tests.append(("PackageAlert", True))
        
        # 测试 DoorlockSession
        session = DoorlockSession(
            session_id="test_session",
            device_id="test_device"
        )
        session.add_dialogue("user", "你好")
        session.add_dialogue("assistant", "您好，请问有什么可以帮您？")
        
        if len(session.dialogue_history) == 2:
            print("✓ DoorlockSession 对话管理正常")
            tests.append(("DoorlockSession", True))
        else:
            print("✗ DoorlockSession 对话管理失败")
            tests.append(("DoorlockSession", False))
        
    except Exception as e:
        print(f"✗ 数据模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        tests.append(("数据模型功能", False))
    
    print()
    return tests


def test_file_structure():
    """测试文件结构完整性"""
    print("=" * 70)
    print("4. 测试文件结构")
    print("=" * 70)
    
    tests = []
    
    required_files = [
        'core/providers/doorlock/__init__.py',
        'core/providers/doorlock/models.py',
        'core/providers/doorlock/doorlock_database.py',
        'core/providers/doorlock/session_manager.py',
        'core/providers/doorlock/package_guard_manager.py',
        'core/providers/doorlock/notification_service.py',
        'core/providers/doorlock/doorlock_tools.py',
        'core/providers/doorlock/face_recognition_handler.py',
        'core/providers/doorlock/greeting_handler.py',
        'core/handle/doorlock_intent_handler.py',
        'core/api/doorlock_config_handler.py',
        'core/api/doorlock_guard_handler.py',
        'core/api/doorlock_welcome_handler.py',
        'core/api/doorlock_history_handler.py',
        'config/doorlock_prompts.yaml',
        'config/doorlock_prompts.yaml.example',
        'migrations/run_doorlock_ai_migration.py',
        'migrations/verify_doorlock_ai_migration.py',
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
            print(f"✗ 缺少文件: {file_path}")
        else:
            print(f"✓ {file_path}")
    
    if not missing_files:
        print("\n✓ 所有必需文件都存在")
        tests.append(("文件结构", True))
    else:
        print(f"\n✗ 缺少 {len(missing_files)} 个文件")
        tests.append(("文件结构", False))
    
    print()
    return tests


def print_summary(all_tests):
    """打印测试总结"""
    print("=" * 70)
    print("测试总结")
    print("=" * 70)
    
    total = len(all_tests)
    passed = sum(1 for _, result in all_tests if result)
    failed = total - passed
    
    print(f"\n总计: {total} 项测试")
    print(f"通过: {passed} 项 ✓")
    print(f"失败: {failed} 项 ✗")
    print(f"成功率: {passed/total*100:.1f}%")
    
    if failed > 0:
        print("\n失败的测试:")
        for name, result in all_tests:
            if not result:
                print(f"  ✗ {name}")
    
    print("\n" + "=" * 70)
    
    return failed == 0


def main():
    """主函数"""
    print("\n智能门锁AI功能集成测试")
    print("=" * 70)
    print()
    
    all_tests = []
    
    # 运行所有测试
    all_tests.extend(test_file_structure())
    all_tests.extend(test_imports())
    all_tests.extend(test_config())
    all_tests.extend(test_data_models())
    
    # 打印总结
    success = print_summary(all_tests)
    
    if success:
        print("\n✓ 所有测试通过！智能门锁AI功能集成正常。")
        return 0
    else:
        print("\n✗ 部分测试失败，请检查上述错误信息。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
