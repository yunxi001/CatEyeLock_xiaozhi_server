#!/usr/bin/env python3
"""
测试 App 端命令功能的简单脚本
用于验证 start_monitor、stop_monitor 等命令是否正常工作
"""
import asyncio
import websockets
import json

async def test_app_commands():
    """测试 App 端命令"""
    
    # 连接到 App 端点
    uri = "ws://localhost:8000/ws/app"
    device_id = "AA:BB:CC:DD:EE:FF"
    
    print(f"正在连接到 {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ WebSocket 连接已建立")
            
            # 1. 发送 hello 消息进行认证
            hello_msg = {
                "type": "hello",
                "device_id": device_id,
                "client_type": "app"
            }
            await websocket.send(json.dumps(hello_msg))
            print(f"→ 发送认证消息: {hello_msg}")
            
            # 接收认证响应
            response = await websocket.recv()
            print(f"← 收到响应: {response}")
            
            auth_response = json.loads(response)
            if auth_response.get("status") != "ok":
                print(f"✗ 认证失败: {auth_response.get('message')}")
                return
            
            print("✓ 认证成功")
            
            # 2. 测试启动监控模式
            print("\n--- 测试启动监控模式 ---")
            start_monitor_msg = {
                "type": "system",
                "command": "start_monitor"
            }
            await websocket.send(json.dumps(start_monitor_msg))
            print(f"→ 发送命令: {start_monitor_msg}")
            
            response = await websocket.recv()
            print(f"← 收到响应: {response}")
            
            # 3. 等待一下
            await asyncio.sleep(2)
            
            # 4. 测试停止监控模式
            print("\n--- 测试停止监控模式 ---")
            stop_monitor_msg = {
                "type": "system",
                "command": "stop_monitor"
            }
            await websocket.send(json.dumps(stop_monitor_msg))
            print(f"→ 发送命令: {stop_monitor_msg}")
            
            response = await websocket.recv()
            print(f"← 收到响应: {response}")
            
            print("\n✓ 所有测试完成")
            
    except websockets.exceptions.ConnectionRefused:
        print("✗ 连接被拒绝，请确保服务器正在运行")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=== App 命令测试脚本 ===\n")
    print("注意：运行此脚本前，请确保：")
    print("1. 服务器正在运行 (python app.py)")
    print("2. 有一个 ESP32 设备已连接 (device-id: AA:BB:CC:DD:EE:FF)")
    print()
    
    asyncio.run(test_app_commands())
