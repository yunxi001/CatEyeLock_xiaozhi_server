"""检查访客意图数据并插入测试数据"""
import asyncio
import json
from datetime import datetime, timedelta
from core.providers.doorlock.doorlock_database import DoorlockDatabase
from core.providers.doorlock.models import VisitorIntent

async def create_visit_record(db, visit_id: int, person_id: int = None, visit_time: datetime = None):
    """创建访问记录"""
    conn = None
    cursor = None
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        if visit_time is None:
            visit_time = datetime.now()
        
        cursor.execute("""
            INSERT INTO visit_records 
            (id, person_id, recognition_result, access_granted, photo_path, visit_time, notified)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE id=id
        """, (
            visit_id,
            person_id,
            'unknown' if person_id is None else 'known',
            False,
            f'visits/test_{visit_id}.jpg',
            visit_time,
            False
        ))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"创建访问记录失败: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

async def main():
    db = DoorlockDatabase()
    device_id = "e8:f6:0a:83:8f:50"
    
    # 检查现有数据
    print("=" * 70)
    print("检查现有访客意图数据...")
    print("=" * 70)
    intents, total = await db.get_visitor_intents(device_id, limit=10)
    print(f"\n找到 {total} 条记录\n")
    
    if total > 0:
        for i, intent in enumerate(intents, 1):
            print(f"{i}. [{intent.intent_type}] {intent.intent_summary.get('summary', '')}")
            print(f"   时间: {intent.created_at}")
            print()
    else:
        print("数据库中没有访客意图记录，准备插入测试数据...\n")
        
        # 插入真实的测试数据
        test_intents = [
            # 1. 快递员送快递
            VisitorIntent(
                visit_id=1001,
                session_id=f"{device_id}_{int((datetime.now() - timedelta(hours=2)).timestamp() * 1000)}",
                person_id=None,
                intent_type="delivery",
                intent_summary={
                    "intent_type": "delivery",
                    "summary": "顺丰快递员送快递，已放门口",
                    "important_notes": ["【留言】您的快递已放在门口，请及时取件"],
                    "ai_analysis": "访客是顺丰快递员，来送快递。快递员表示快递已经放在门口了，请求签收。态度友好，语气专业。"
                },
                dialogue_history=[
                    {"role": "assistant", "content": "您好，请问有什么可以帮您？"},
                    {"role": "user", "content": "你好，我是顺丰快递的，给你送快递来了"},
                    {"role": "assistant", "content": "好的，请问快递放在哪里？"},
                    {"role": "user", "content": "我放门口了，麻烦签收一下"},
                    {"role": "assistant", "content": "好的，已经记录了，谢谢您"}
                ]
            ),
            
            # 2. 外卖员送餐
            VisitorIntent(
                visit_id=1002,
                session_id=f"{device_id}_{int((datetime.now() - timedelta(hours=5)).timestamp() * 1000)}",
                person_id=None,
                intent_type="delivery",
                intent_summary={
                    "intent_type": "delivery",
                    "summary": "美团外卖送餐，已挂门把手",
                    "important_notes": ["【留言】外卖挂在门把手上了，趁热吃"],
                    "ai_analysis": "访客是美团外卖骑手，来送外卖。骑手表示外卖已经挂在门把手上了，提醒趁热吃。语气急促，可能赶时间。"
                },
                dialogue_history=[
                    {"role": "assistant", "content": "您好，请问有什么事吗？"},
                    {"role": "user", "content": "外卖，你的外卖到了"},
                    {"role": "assistant", "content": "好的，请问放在哪里？"},
                    {"role": "user", "content": "我挂门把手上了啊，趁热吃"},
                    {"role": "assistant", "content": "好的，谢谢"}
                ]
            ),
            
            # 3. 朋友来访
            VisitorIntent(
                visit_id=1003,
                session_id=f"{device_id}_{int((datetime.now() - timedelta(days=1, hours=3)).timestamp() * 1000)}",
                person_id=None,
                intent_type="visit",
                intent_summary={
                    "intent_type": "visit",
                    "summary": "朋友来访，约好一起吃饭",
                    "important_notes": ["【留言】我在楼下等你，快点下来"],
                    "ai_analysis": "访客是朋友，来找主人一起吃饭。朋友表示已经在楼下等了，催促主人快点下来。语气轻松随意，关系应该比较亲密。"
                },
                dialogue_history=[
                    {"role": "assistant", "content": "您好，请问找谁？"},
                    {"role": "user", "content": "是我啊，我们不是约好一起吃饭吗"},
                    {"role": "assistant", "content": "请问您是？"},
                    {"role": "user", "content": "我是小李啊，快点下来，我在楼下等你呢"},
                    {"role": "assistant", "content": "好的，我已经通知主人了"}
                ]
            ),
            
            # 4. 推销员
            VisitorIntent(
                visit_id=1004,
                session_id=f"{device_id}_{int((datetime.now() - timedelta(days=2, hours=10)).timestamp() * 1000)}",
                person_id=None,
                intent_type="sales",
                intent_summary={
                    "intent_type": "sales",
                    "summary": "推销净水器，被婉拒",
                    "important_notes": ["【警示】推销人员，已拒绝"],
                    "ai_analysis": "访客是推销净水器的销售人员，想要推销产品。在被告知主人不在家后，留下了联系方式。语气热情但略显急切。"
                },
                dialogue_history=[
                    {"role": "assistant", "content": "您好，请问有什么事吗？"},
                    {"role": "user", "content": "你好，我是XX净水器公司的，想给您介绍一下我们的产品"},
                    {"role": "assistant", "content": "不好意思，主人现在不在家"},
                    {"role": "user", "content": "那没关系，我可以留个电话，您方便的时候联系我"},
                    {"role": "assistant", "content": "好的，我会转告主人的"}
                ]
            ),
            
            # 5. 物业维修
            VisitorIntent(
                visit_id=1005,
                session_id=f"{device_id}_{int((datetime.now() - timedelta(days=3, hours=8)).timestamp() * 1000)}",
                person_id=None,
                intent_type="maintenance",
                intent_summary={
                    "intent_type": "maintenance",
                    "summary": "物业维修空调，已预约明天上午",
                    "important_notes": ["【预约】明天上午9点维修空调"],
                    "ai_analysis": "访客是物业维修人员，来确认空调维修预约。维修人员表示明天上午9点会来维修，提醒主人在家等候。语气专业礼貌。"
                },
                dialogue_history=[
                    {"role": "assistant", "content": "您好，请问有什么事？"},
                    {"role": "user", "content": "你好，我是物业的，来确认一下空调维修的时间"},
                    {"role": "assistant", "content": "好的，请说"},
                    {"role": "user", "content": "我们约的是明天上午9点，您在家吗？"},
                    {"role": "assistant", "content": "好的，我会转告主人的，谢谢"}
                ]
            ),
            
            # 6. 邻居借东西
            VisitorIntent(
                visit_id=1006,
                session_id=f"{device_id}_{int((datetime.now() - timedelta(days=4, hours=15)).timestamp() * 1000)}",
                person_id=None,
                intent_type="visit",
                intent_summary={
                    "intent_type": "visit",
                    "summary": "邻居来借工具，主人不在",
                    "important_notes": ["【留言】楼上邻居想借电钻，晚上再来"],
                    "ai_analysis": "访客是楼上的邻居，想借电钻用一下。在得知主人不在家后，表示晚上再来。语气客气，邻里关系良好。"
                },
                dialogue_history=[
                    {"role": "assistant", "content": "您好，请问找谁？"},
                    {"role": "user", "content": "我是楼上的邻居，想借个电钻用一下"},
                    {"role": "assistant", "content": "不好意思，主人现在不在家"},
                    {"role": "user", "content": "那没事，我晚上再来吧"},
                    {"role": "assistant", "content": "好的，我会告诉主人的"}
                ]
            )
        ]
        
        print("开始插入测试数据...\n")
        for i, intent in enumerate(test_intents, 1):
            # 先创建访问记录
            visit_time = datetime.now() - timedelta(hours=2*i)
            if await create_visit_record(db, intent.visit_id, intent.person_id, visit_time):
                # 再插入意图记录
                intent_id = await db.save_visitor_intent(intent)
                if intent_id > 0:
                    print(f"✓ 插入成功 [{i}/6]: {intent.intent_type} - {intent.intent_summary['summary']}")
                else:
                    print(f"✗ 插入失败 [{i}/6]: {intent.intent_type}")
            else:
                print(f"✗ 创建访问记录失败 [{i}/6]: visit_id={intent.visit_id}")
        
        print("\n" + "=" * 70)
        print("测试数据插入完成！")
        print("=" * 70)
        
        # 再次查询验证
        print("\n验证插入结果...\n")
        intents, total = await db.get_visitor_intents(device_id, limit=10)
        print(f"现在共有 {total} 条记录\n")
        for i, intent in enumerate(intents, 1):
            print(f"{i}. [{intent.intent_type}] {intent.intent_summary.get('summary', '')}")
            print(f"   时间: {intent.created_at}")
            print()

if __name__ == "__main__":
    asyncio.run(main())
