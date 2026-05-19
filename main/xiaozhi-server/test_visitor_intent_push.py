"""测试访客意图通知推送功能"""
import asyncio
import json
import websockets
from datetime import datetime

async def test_app_connection():
    """模拟 App 连接并接收推送消息"""
    uri = "ws://localhost:8000"
    device_id = "e8:f6:0a:83:8f:50"
    app_id = "app_test_" + str(int(datetime.now().timestamp()))
    
    print("=" * 70)
    print("测试访客意图通知推送功能")
    print("=" * 70)
    print(f"\n连接到服务器: {uri}")
    print(f"设备ID: {device_id}")
    print(f"App ID: {app_id}\n")
    
    try:
        async with websockets.connect(uri) as websocket:
            # 发送 hello 消息进行认证
            hello_msg = {
                "type": "hello",
                "client_type": "app",
                "device_id": device_id,
                "app_id": app_id
            }
            
            print("发送认证消息...")
            await websocket.send(json.dumps(hello_msg))
            
            # 接收并打印所有推送消息
            print("\n等待接收推送消息...\n")
            print("-" * 70)
            
            message_count = 0
            visitor_intent_count = 0
            
            # 设置超时时间（10秒）
            timeout = 10
            start_time = asyncio.get_event_loop().time()
            
            while True:
                try:
                    # 计算剩余超时时间
                    elapsed = asyncio.get_event_loop().time() - start_time
                    remaining = timeout - elapsed
                    
                    if remaining <= 0:
                        print("\n超时，停止接收")
                        break
                    
                    # 接收消息（带超时）
                    message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=remaining
                    )
                    
                    message_count += 1
                    msg_json = json.loads(message)
                    msg_type = msg_json.get("type")
                    
                    print(f"\n[消息 {message_count}] 类型: {msg_type}")
                    
                    if msg_type == "hello":
                        print(f"  状态: {msg_json.get('status')}")
                        device_info = msg_json.get('device_info', {})
                        print(f"  设备在线: {device_info.get('online')}")
                        print(f"  设备模式: {device_info.get('mode')}")
                    
                    elif msg_type == "device_status":
                        print(f"  状态: {msg_json.get('status')}")
                        print(f"  原因: {msg_json.get('reason', 'N/A')}")
                    
                    elif msg_type == "status_report":
                        data = msg_json.get('data', {})
                        print(f"  电池: {data.get('bat')}%")
                        print(f"  光照: {data.get('lux')} lux")
                        print(f"  门锁: {'已锁' if data.get('lock') else '未锁'}")
                        print(f"  灯光: {'开启' if data.get('light') else '关闭'}")
                    
                    elif msg_type == "log_report":
                        data = msg_json.get('data', {})
                        print(f"  开锁方式: {data.get('method')}")
                        print(f"  用户ID: {data.get('uid')}")
                        print(f"  状态: {data.get('status')}")
                    
                    elif msg_type == "visit_notification":
                        data = msg_json.get('data', {})
                        print(f"  访客: {data.get('person_name', '陌生人')}")
                        print(f"  关系: {data.get('relation', 'unknown')}")
                        print(f"  识别结果: {data.get('result')}")
                        print(f"  是否授权: {data.get('access_granted')}")
                    
                    elif msg_type == "visitor_intent_notification":
                        visitor_intent_count += 1
                        print(f"  ✨ 访客意图通知 #{visitor_intent_count}")
                        print(f"  访问ID: {msg_json.get('visit_id')}")
                        print(f"  会话ID: {msg_json.get('session_id')}")
                        
                        intent_summary = msg_json.get('intent_summary', {})
                        print(f"  意图类型: {intent_summary.get('intent_type')}")
                        print(f"  简要总结: {intent_summary.get('summary')}")
                        
                        important_notes = intent_summary.get('important_notes', [])
                        if important_notes:
                            print(f"  重要信息:")
                            for note in important_notes:
                                print(f"    - {note}")
                        
                        dialogue_history = msg_json.get('dialogue_history', [])
                        if dialogue_history:
                            print(f"  对话历史 ({len(dialogue_history)} 条):")
                            for i, msg in enumerate(dialogue_history[:3], 1):  # 只显示前3条
                                role = "助手" if msg['role'] == 'assistant' else "访客"
                                print(f"    {i}. [{role}] {msg['content']}")
                            if len(dialogue_history) > 3:
                                print(f"    ... (还有 {len(dialogue_history) - 3} 条)")
                        
                        person_info = msg_json.get('person_info')
                        if person_info:
                            print(f"  人员信息:")
                            print(f"    姓名: {person_info.get('name')}")
                            print(f"    关系: {person_info.get('relation_type')}")
                    
                    else:
                        print(f"  原始数据: {json.dumps(msg_json, ensure_ascii=False, indent=2)}")
                    
                except asyncio.TimeoutError:
                    print("\n接收超时，停止接收")
                    break
                except json.JSONDecodeError as e:
                    print(f"\n解析消息失败: {e}")
                    print(f"原始消息: {message}")
            
            print("\n" + "-" * 70)
            print(f"\n接收完成！")
            print(f"  总消息数: {message_count}")
            print(f"  访客意图通知数: {visitor_intent_count}")
            print("\n" + "=" * 70)
            
    except websockets.exceptions.ConnectionClosed:
        print("\n连接已关闭")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_app_connection())
