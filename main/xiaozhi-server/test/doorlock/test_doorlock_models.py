#!/usr/bin/env python3
"""
数据模型验证脚本

测试门锁AI功能的数据模型是否正确定义
"""

import sys
from datetime import datetime
from core.providers.doorlock.models import (
    DoorlockConfig,
    VisitorIntent,
    PackageAlert,
    DoorlockSession
)


def test_doorlock_config():
    """测试 DoorlockConfig 数据类"""
    print("测试 DoorlockConfig...")
    
    # 创建实例
    config = DoorlockConfig(
        device_id="test_device_001",
        intent_recognition_enabled=True,
        package_guard_available=True,
        package_guard_active=False
    )
    
    # 测试 to_dict
    config_dict = config.to_dict()
    assert config_dict['device_id'] == "test_device_001"
    assert config_dict['intent_recognition_enabled'] is True
    
    # 测试 to_json 和 from_json
    config_json = config.to_json()
    config_restored = DoorlockConfig.from_json(config_json)
    assert config_restored.device_id == config.device_id
    
    print("  ✓ DoorlockConfig 测试通过")


def test_visitor_intent():
    """测试 VisitorIntent 数据类"""
    print("测试 VisitorIntent...")
    
    # 创建实例
    intent = VisitorIntent(
        session_id="device001_1707379822000",
        person_id=5,
        intent_type="visit",
        intent_summary={
            "important_notes": ["【留言】明天下午3点再来"],
            "purpose": "拜访朋友",
            "full_summary": "访客来拜访"
        },
        dialogue_history=[
            {"role": "assistant", "content": "您好"},
            {"role": "user", "content": "我找李四"}
        ]
    )
    
    # 测试 to_dict
    intent_dict = intent.to_dict()
    assert intent_dict['session_id'] == "device001_1707379822000"
    assert intent_dict['intent_type'] == "visit"
    
    # 测试 JSON 序列化
    summary_json = intent.get_intent_summary_json()
    assert "important_notes" in summary_json
    
    history_json = intent.get_dialogue_history_json()
    assert "assistant" in history_json
    
    # 测试 to_json 和 from_json
    intent_json = intent.to_json()
    intent_restored = VisitorIntent.from_json(intent_json)
    assert intent_restored.session_id == intent.session_id
    assert len(intent_restored.dialogue_history) == 2
    
    print("  ✓ VisitorIntent 测试通过")


def test_package_alert():
    """测试 PackageAlert 数据类"""
    print("测试 PackageAlert...")
    
    # 创建实例
    alert = PackageAlert(
        device_id="test_device_001",
        session_id="device001_1707380410000",
        threat_level="high",
        action="taking",
        description="陌生人拿走快递",
        photo_path="visits/2026-02/alert_456.jpg"
    )
    
    # 测试威胁等级判断
    assert alert.is_high_threat() is True
    assert alert.is_medium_threat() is False
    assert alert.is_low_threat() is False
    assert alert.needs_notification() is True
    
    # 测试 to_dict
    alert_dict = alert.to_dict()
    assert alert_dict['threat_level'] == "high"
    assert alert_dict['action'] == "taking"
    
    # 测试 to_json 和 from_json
    alert_json = alert.to_json()
    alert_restored = PackageAlert.from_json(alert_json)
    assert alert_restored.device_id == alert.device_id
    assert alert_restored.threat_level == alert.threat_level
    
    print("  ✓ PackageAlert 测试通过")


def test_doorlock_session():
    """测试 DoorlockSession 数据类"""
    print("测试 DoorlockSession...")
    
    # 创建实例
    session = DoorlockSession(
        session_id="device001_1707379822000",
        device_id="test_device_001",
        person_id=5,
        person_name="张三",
        is_owner=True
    )
    
    # 测试添加对话
    session.add_dialogue("assistant", "您好")
    session.add_dialogue("user", "我找李四")
    assert len(session.dialogue_history) == 2
    
    # 测试添加照片
    session.add_photo("photo1.jpg", "访客照片")
    assert len(session.photo_records) == 1
    
    # 测试获取最近对话
    recent = session.get_recent_dialogue(max_rounds=1)
    assert len(recent) == 2
    
    # 测试清理旧对话
    for i in range(20):
        session.add_dialogue("assistant", f"消息{i}")
        session.add_dialogue("user", f"回复{i}")
    
    session.clear_old_dialogue(max_rounds=10)
    assert len(session.dialogue_history) == 20  # 10轮 * 2条消息
    
    # 测试超时判断
    assert session.is_timeout(timeout_seconds=30) is False
    
    # 测试 to_dict
    session_dict = session.to_dict()
    assert session_dict['session_id'] == "device001_1707379822000"
    assert session_dict['person_name'] == "张三"
    
    # 测试 to_json 和 from_json
    session_json = session.to_json()
    session_restored = DoorlockSession.from_json(session_json)
    assert session_restored.session_id == session.session_id
    assert len(session_restored.dialogue_history) == len(session.dialogue_history)
    
    print("  ✓ DoorlockSession 测试通过")


def main():
    """主函数"""
    print("="*70)
    print("数据模型验证测试")
    print("="*70)
    print()
    
    try:
        test_doorlock_config()
        test_visitor_intent()
        test_package_alert()
        test_doorlock_session()
        
        print()
        print("="*70)
        print("✓ 所有数据模型测试通过")
        print("="*70)
        return 0
        
    except Exception as e:
        print()
        print("="*70)
        print(f"✗ 测试失败: {e}")
        print("="*70)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
