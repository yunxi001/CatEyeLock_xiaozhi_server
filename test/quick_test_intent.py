"""
快速意图识别测试脚本

简化版测试工具，用于快速验证意图识别功能
"""

import asyncio
import websockets
import json
import time


async def quick_test():
    """快速测试函数"""
    
    # 配置
    server_url = "ws://localhost:8000/xiaozhi/v1/"
    device_id = "TEST:DE:VI:CE:00:01"
    
    print("="*60)
    print("快速意图识别测试")
    print("="*60)
    print(f"服务器: {server_url}")
    print(f"设备ID: {device_id}")
    print("="*60 + "\n")
    
    try:
        # 连接服务器
        print("正在连接服务器...")
        ws = await websockets.connect(server_url)
        print("✓ 连接成功\n")
        
        # 1. 发送hello消息
        hello_msg = {
            "type": "hello",
            "version": 1,
            "device_id": device_id,
            "transport": "websocket"
        }
        await ws.send(json.dumps(hello_msg))
        print("✓ 已发送hello消息")
        
        # 等待响应
        response = await ws.recv()
        print(f"收到响应: {response}\n")
        
        # 2. 模拟快递员场景
        print("="*60)
        print("测试场景: 快递员送货")
        print("="*60 + "\n")
        
        # 模拟访客语音输入
        visitor_messages = [
            "你好，我是快递员",
            "有个包裹要送给张先生",
            "是顺丰快递的",
            "包裹比较大，需要本人签收",
            "麻烦帮我转告一下",
            "那我先把包裹放在门口了"
        ]
        
        for i, msg in enumerate(visitor_messages, 1):
            print(f"[访客 {i}] {msg}")
            
            # 发送文本消息
            text_msg = {
                "type": "text",
                "timestamp": int(time.time() * 1000),
                "device_id": device_id,
                "text": msg,
                "source": "visitor"
            }
            
            await ws.send(json.dumps(text_msg))
            
            # 等待处理
            await asyncio.sleep(1.5)
        
        print("\n" + "="*60)
        print("对话结束，等待意图识别结果...")
        print("="*60 + "\n")
        
        # 等待意图识别结果
        await asyncio.sleep(3)
        
        # 尝试接收结果
        try:
            result = await asyncio.wait_for(ws.recv(), timeout=5)
            print("收到服务器响应:")
            print(json.dumps(json.loads(result), indent=2, ensure_ascii=False))
        except asyncio.TimeoutError:
            print("未收到意图识别结果（可能需要在服务器端配置）")
        
        # 关闭连接
        await ws.close()
        print("\n✓ 测试完成")
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n提示: 请确保服务器已启动 (python app.py)\n")
    
    try:
        asyncio.run(quick_test())
    except KeyboardInterrupt:
        print("\n测试被中断")
