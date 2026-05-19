"""展示访客意图通知的完整格式（按协议 v2.5 规范）"""
import json
from datetime import datetime

# 按照协议 v2.5 规范的完整访客意图通知格式
visitor_intent_notification = {
    "type": "visitor_intent_notification",
    "ts": int(datetime.now().timestamp() * 1000),
    "visit_id": 12345,
    "session_id": "e8:f6:0a:83:8f:50_1702234567890",
    
    # 人员信息（如果识别成功）
    "person_info": {
        "person_id": 10,
        "name": "张三",
        "relation_type": "family"
    },
    
    # 意图总结（必填）
    "intent_summary": {
        "intent_type": "delivery",  # delivery/visit/sales/maintenance/other
        "summary": "快递员送快递，已放门口",  # 一句话总结
        "important_notes": [  # 重要信息列表
            "【留言】快递放门口了，麻烦签收一下"
        ],
        "ai_analysis": "访客是快递员，来送快递，表示快递已放在门口，请求签收。态度友好，语气专业。"  # 详细AI分析
    },
    
    # 完整对话历史（必填）
    "dialogue_history": [
        {
            "role": "assistant",
            "content": "您好，请问有什么可以帮您？"
        },
        {
            "role": "user",
            "content": "我是来送快递的"
        },
        {
            "role": "assistant",
            "content": "好的，请问快递放在哪里？"
        },
        {
            "role": "user",
            "content": "我放门口了，麻烦签收一下"
        }
    ],
    
    # 快递检查结果（如果启用了快递看护模式）
    "package_check": {
        "threat_level": "low",  # low/medium/high
        "action": "normal",  # normal/passing/searching/taking/damaging
        "description": "快递安全，未被触碰"
    }
}

print("=" * 80)
print("访客意图通知完整格式（协议 v2.5）")
print("=" * 80)
print("\n完整 JSON 格式：\n")
print(json.dumps(visitor_intent_notification, ensure_ascii=False, indent=2))

print("\n" + "=" * 80)
print("字段说明")
print("=" * 80)

fields = [
    ("type", "string", "是", "固定为 'visitor_intent_notification'"),
    ("ts", "int", "是", "时间戳（毫秒）"),
    ("visit_id", "int", "是", "访问记录ID"),
    ("session_id", "string", "是", "会话ID"),
    ("person_info", "object", "否", "人员信息（识别成功时有值）"),
    ("person_info.person_id", "int", "否", "人员ID"),
    ("person_info.name", "string", "否", "人员姓名"),
    ("person_info.relation_type", "string", "否", "关系类型：family/friend/unknown"),
    ("intent_summary", "object", "是", "意图总结"),
    ("intent_summary.intent_type", "string", "是", "意图类型：delivery/visit/sales/maintenance/other"),
    ("intent_summary.summary", "string", "是", "简洁总结（一句话）"),
    ("intent_summary.important_notes", "array", "是", "重要信息列表"),
    ("intent_summary.ai_analysis", "string", "是", "详细AI分析"),
    ("dialogue_history", "array", "是", "完整对话历史"),
    ("dialogue_history[].role", "string", "是", "角色：assistant/user"),
    ("dialogue_history[].content", "string", "是", "对话内容"),
    ("package_check", "object", "否", "快递检查结果（看护模式激活时有值）"),
    ("package_check.threat_level", "string", "否", "威胁等级：low/medium/high"),
    ("package_check.action", "string", "否", "行为类型：normal/passing/searching/taking/damaging"),
    ("package_check.description", "string", "否", "详细描述"),
]

print("\n{:<35} {:<10} {:<6} {}".format("字段", "类型", "必填", "说明"))
print("-" * 80)
for field, type_, required, desc in fields:
    print("{:<35} {:<10} {:<6} {}".format(field, type_, required, desc))

print("\n" + "=" * 80)
print("意图类型说明")
print("=" * 80)

intent_types = [
    ("delivery", "送快递/外卖", "快递员、外卖员送货"),
    ("visit", "拜访朋友/家人", "朋友来访、邻居串门"),
    ("sales", "推销产品/服务", "推销员、广告宣传"),
    ("maintenance", "维修/物业工作", "维修工、抄表员"),
    ("other", "其他情况", "未列出的意图识别"),
]

print("\n{:<15} {:<20} {}".format("intent_type", "说明", "示例场景"))
print("-" * 80)
for type_, desc, example in intent_types:
    print("{:<15} {:<20} {}".format(type_, desc, example))

print("\n" + "=" * 80)
print("威胁等级说明")
print("=" * 80)

threat_levels = [
    ("low", "低威胁", "快递未被触碰、主人取快递、路人经过"),
    ("medium", "中威胁", "快递被移动但未拿走、访客翻看快递"),
    ("high", "高威胁", "快递被非主人拿走、快递被破坏"),
]

print("\n{:<15} {:<15} {}".format("threat_level", "说明", "触发条件"))
print("-" * 80)
for level, desc, condition in threat_levels:
    print("{:<15} {:<15} {}".format(level, desc, condition))

print("\n" + "=" * 80)
print("行为类型说明")
print("=" * 80)

actions = [
    ("normal", "正常状态，快递未被触碰"),
    ("passing", "路人经过，未触碰快递"),
    ("searching", "翻看或移动快递"),
    ("taking", "拿走快递"),
    ("damaging", "破坏快递"),
]

print("\n{:<15} {}".format("action", "说明"))
print("-" * 80)
for action, desc in actions:
    print("{:<15} {}".format(action, desc))

print("\n" + "=" * 80)
print("使用场景")
print("=" * 80)
print("""
1. App 接收到此消息后，在通知栏显示访客意图
2. 如果有重要信息（important_notes），高亮显示
3. 如果威胁等级为 medium 或 high，发送警报通知
4. 保存对话历史供用户查看
5. 如果有 person_info，显示访客身份信息
6. 如果有 package_check，根据威胁等级显示不同颜色（绿/黄/红）
""")

print("=" * 80)
