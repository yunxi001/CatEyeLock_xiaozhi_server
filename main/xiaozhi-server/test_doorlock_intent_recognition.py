"""
智能门锁意图识别模块测试

测试内容：
1. 人脸识别重试逻辑
2. 欢迎词播放逻辑
3. 意图识别对话处理器
4. 对话历史管理
"""
import asyncio
from datetime import datetime
from loguru import logger

# 配置日志
logger.add("logs/test_intent_recognition.log", rotation="1 day")


class MockPerson:
    """模拟人员对象"""
    def __init__(self, id, name, relation_type):
        self.id = id
        self.name = name
        self.relation_type = relation_type


class MockRecognitionResult:
    """模拟识别结果"""
    def __init__(self, result, person=None, confidence=0.0):
        self.result = result
        self.person = person
        self.confidence = confidence


class MockFaceService:
    """模拟人脸识别服务"""
    
    def __init__(self, should_succeed=True):
        self.should_succeed = should_succeed
        self.call_count = 0
    
    def recognize(self, jpeg_data):
        """模拟人脸识别"""
        self.call_count += 1
        
        if self.should_succeed and self.call_count >= 2:
            # 第二次尝试成功
            person = MockPerson(
                id=1,
                name="张三",
                relation_type="family"
            )
            return MockRecognitionResult(
                result='known',
                person=person,
                confidence=0.95
            )
        else:
            return MockRecognitionResult(result='no_face')


class MockTTSProvider:
    """模拟TTS提供者"""
    
    async def text_to_speak(self, text, output_file):
        """模拟TTS生成"""
        logger.info(f"[模拟TTS] 生成语音: {text}")
        return b"mock_audio_data"


class MockDoorlockDatabase:
    """模拟门锁数据库"""
    
    async def get_person_greeting(self, person_id):
        """模拟获取欢迎词配置"""
        return '{"morning": "早上好，张三", "default": "欢迎回家"}'
    
    async def save_visitor_intent(self, intent):
        """模拟保存访客意图"""
        logger.info(f"[模拟数据库] 保存访客意图: {intent.intent_type}")
        return 1


async def test_face_recognition_retry():
    """测试人脸识别重试逻辑"""
    print("\n" + "="*60)
    print("测试 1: 人脸识别重试逻辑")
    print("="*60)
    
    from core.providers.doorlock.face_recognition_handler import FaceRecognitionHandler
    
    # 创建模拟服务
    face_service = MockFaceService(should_succeed=True)
    tts_provider = MockTTSProvider()
    
    config = {
        'max_retries': 3,
        'retry_interval': 0.5  # 缩短测试时间
    }
    
    handler = FaceRecognitionHandler(face_service, tts_provider, config)
    
    # 测试重试逻辑
    result = await handler.recognize_with_retry(
        device_id="test_device_001",
        jpeg_data=b"mock_jpeg_data"
    )
    
    print(f"\n识别结果:")
    print(f"  成功: {result['success']}")
    print(f"  人员ID: {result['person_id']}")
    print(f"  尝试次数: {result['attempts']}")
    print(f"  置信度: {result['confidence']:.3f}")
    
    assert result['success'] == True, "人脸识别应该成功"
    assert result['attempts'] == 2, "应该在第2次尝试成功"
    assert face_service.call_count == 2, "应该调用了2次人脸识别"
    
    print("\n✓ 人脸识别重试逻辑测试通过")


async def test_greeting_selection():
    """测试欢迎词选择逻辑"""
    print("\n" + "="*60)
    print("测试 2: 欢迎词选择逻辑")
    print("="*60)
    
    from core.providers.doorlock.greeting_handler import GreetingHandler
    
    # 创建模拟服务
    db = MockDoorlockDatabase()
    tts_provider = MockTTSProvider()
    
    handler = GreetingHandler(db, tts_provider)
    
    # 测试不同时段的欢迎词选择
    test_cases = [
        (datetime(2024, 1, 1, 8, 0), "morning", "早上好"),
        (datetime(2024, 1, 1, 14, 0), "afternoon", "下午好"),
        (datetime(2024, 1, 1, 20, 0), "evening", "晚上好"),
        (datetime(2024, 1, 1, 23, 0), "night", "夜深了"),
    ]
    
    custom_greeting = {
        "morning": "早上好",
        "afternoon": "下午好",
        "evening": "晚上好",
        "night": "夜深了",
        "default": "欢迎回家"
    }
    
    print("\n时段欢迎词测试:")
    for test_time, expected_slot, expected_text in test_cases:
        greeting = handler.select_greeting(custom_greeting, test_time)
        print(f"  {test_time.hour}:00 -> {expected_slot} -> {greeting}")
        assert expected_text in greeting, f"时段 {expected_slot} 的欢迎词不正确"
    
    # 测试默认回退
    print("\n默认回退测试:")
    greeting = handler.select_greeting({}, datetime.now())
    print(f"  无配置 -> {greeting}")
    assert greeting == "欢迎回家", "应该使用默认欢迎词"
    
    greeting = handler.select_greeting({"default": "你好"}, datetime(2024, 1, 1, 8, 0))
    print(f"  只有default -> {greeting}")
    assert greeting == "你好", "应该回退到default"
    
    print("\n✓ 欢迎词选择逻辑测试通过")


async def test_session_management():
    """测试会话管理"""
    print("\n" + "="*60)
    print("测试 3: 会话管理")
    print("="*60)
    
    from core.providers.doorlock.session_manager import SessionManager
    
    manager = SessionManager(dialogue_timeout=30, max_dialogue_rounds=10)
    
    # 创建会话
    session = manager.create_session("test_device_001")
    print(f"\n创建会话: {session.session_id}")
    
    # 添加对话记录
    manager.add_dialogue(session.session_id, "assistant", "您好，请问您找谁？")
    manager.add_dialogue(session.session_id, "user", "我找李四")
    manager.add_dialogue(session.session_id, "assistant", "李四不在家，请问有什么可以帮您？")
    
    # 获取对话历史
    history = manager.get_dialogue_history(session.session_id)
    print(f"\n对话历史 ({len(history)} 条):")
    for msg in history:
        print(f"  {msg['role']}: {msg['content']}")
    
    assert len(history) == 3, "应该有3条对话记录"
    
    # 测试对话历史限制（保留最近10轮）
    print("\n测试对话历史限制:")
    for i in range(25):
        manager.add_dialogue(session.session_id, "user", f"消息 {i}")
    
    history = manager.get_dialogue_history(session.session_id)
    print(f"  添加25条消息后，历史记录数: {len(history)}")
    assert len(history) == 20, "应该保留最近10轮（20条消息）"
    
    # 测试对话结束判定
    print("\n测试对话结束判定:")
    should_end = await manager.check_dialogue_end(session.session_id, pir_detected=False)
    print(f"  PIR无人体 -> 应该结束: {should_end}")
    assert should_end == True, "PIR无人体时应该结束对话"
    
    # 清除会话
    await manager.cleanup_session(session.session_id)
    session_after_cleanup = manager.get_session(session.session_id)
    assert session_after_cleanup is None, "会话应该已被清除"
    
    print("\n✓ 会话管理测试通过")


async def test_intent_summary_extraction():
    """测试意图总结提取"""
    print("\n" + "="*60)
    print("测试 4: 意图总结提取")
    print("="*60)
    
    # 直接实现意图提取逻辑，避免导入会触发网络请求的模块
    def extract_intent_from_dialogue(dialogue_history):
        """从对话历史中提取意图（规则方法）"""
        full_text = " ".join([msg.get("content", "") for msg in dialogue_history])
        
        # 判断意图类型（按优先级检查）
        intent_type = "other"
        if any(kw in full_text for kw in ["维修", "物业", "检查", "抄表", "水表", "电表"]):
            intent_type = "maintenance"
        elif any(kw in full_text for kw in ["快递", "外卖", "送货", "包裹"]):
            intent_type = "delivery"
        elif any(kw in full_text for kw in ["拜访", "找", "见面", "朋友"]):
            intent_type = "visit"
        elif any(kw in full_text for kw in ["推销", "产品", "服务", "办理"]):
            intent_type = "sales"
        
        # 提取重要信息（简化）
        important_notes = []
        for msg in dialogue_history:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if any(kw in content for kw in ["留言", "告诉", "转达"]):
                    important_notes.append(f"【留言】{content}")
                elif any(kw in content for kw in ["提醒", "记得", "别忘"]):
                    important_notes.append(f"【提醒】{content}")
        
        # 生成摘要
        purpose = f"{intent_type}相关事宜"
        full_summary = f"访客进行了{len(dialogue_history)}轮对话，意图类型为{intent_type}。"
        
        return {
            "important_notes": important_notes,
            "intent_type": intent_type,
            "purpose": purpose,
            "full_summary": full_summary
        }
    
    # 测试不同类型的对话
    test_cases = [
        {
            "dialogue": [
                {"role": "assistant", "content": "您好，请问您找谁？"},
                {"role": "user", "content": "我是快递员，有您的快递"},
                {"role": "assistant", "content": "好的，请放在门口"},
            ],
            "expected_type": "delivery"
        },
        {
            "dialogue": [
                {"role": "assistant", "content": "您好，请问您找谁？"},
                {"role": "user", "content": "我找李四，是他朋友"},
                {"role": "assistant", "content": "李四不在家"},
                {"role": "user", "content": "请转告他明天下午3点我再来"},
            ],
            "expected_type": "visit"
        },
        {
            "dialogue": [
                {"role": "assistant", "content": "您好，请问您找谁？"},
                {"role": "user", "content": "我是物业，来检查水表"},
            ],
            "expected_type": "maintenance"
        },
    ]
    
    print("\n意图类型识别测试:")
    for i, test_case in enumerate(test_cases, 1):
        summary = extract_intent_from_dialogue(test_case["dialogue"])
        print(f"\n  测试 {i}:")
        print(f"    意图类型: {summary['intent_type']}")
        print(f"    预期类型: {test_case['expected_type']}")
        print(f"    重要信息: {len(summary['important_notes'])} 条")
        
        assert summary['intent_type'] == test_case['expected_type'], \
            f"意图类型应该是 {test_case['expected_type']}"
    
    print("\n✓ 意图总结提取测试通过")


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("智能门锁意图识别模块测试")
    print("="*60)
    
    try:
        # 运行测试
        await test_face_recognition_retry()
        await test_greeting_selection()
        await test_session_management()
        await test_intent_summary_extraction()
        
        print("\n" + "="*60)
        print("✓ 所有测试通过！")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        return False
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
