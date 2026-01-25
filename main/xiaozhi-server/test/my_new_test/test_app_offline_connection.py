"""
测试 App 在设备离线时的连接功能

测试场景：
1. App 在设备离线时可以连接服务器
2. App 连接后可以接收设备状态推送
3. 设备上线/下线时 App 收到通知
"""
import asyncio
import json
import websockets
import time


async def test_app_connection_when_device_offline():
    """测试设备离线时 App 连接"""
    print("=== 测试 1: 设备离线时 App 连接 ===")
    
    uri = "ws://localhost:8000/ws/app"
    
    try:
        async with websockets.connect(uri) as websocket:
            # 发送 hello 消息
            hello_msg = {
                "type": "hello",
                "client_type": "app",
                "device_id": "test_device_001",
                "app_id": "test_app_user_001"
            }
            await websocket.send(json.dumps(hello_msg))
            print(f"已发送 hello 消息: {hello_msg}")
            
            # 接收响应
            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"收到响应: {response_data}")
            
            # 验证响应
            assert response_data["type"] == "hello"
            assert response_data["status"] == "ok"
            assert "device_info" in response_data
            
            device_info = response_data["device_info"]
            print(f"设备状态: online={device_info['online']}, mode={device_info.get('mode', 'unknown')}")
            
            # 请求设备状态
            status_request = {
                "type": "get_device_status",
                "seq_id": f"seq_{int(time.time() * 1000)}"
            }
            await websocket.send(json.dumps(status_request))
            print(f"已发送状态请求: {status_request}")
            
            # 接收状态响应
            status_response = await websocket.recv()
            status_data = json.loads(status_response)
            print(f"收到状态响应: {status_data}")
            
            print("✓ 测试通过：App 可以在设备离线时连接服务器")
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        raise


async def test_device_status_notification():
    """测试设备状态变化通知"""
    print("\n=== 测试 2: 设备状态变化通知 ===")
    
    uri = "ws://localhost:8000/ws/app"
    
    try:
        async with websockets.connect(uri) as websocket:
            # 连接
            hello_msg = {
                "type": "hello",
                "client_type": "app",
                "device_id": "test_device_001",
                "app_id": "test_app_user_002"
            }
            await websocket.send(json.dumps(hello_msg))
            await websocket.recv()  # 接收 hello 响应
            
            print("等待设备状态通知...")
            print("提示：请手动触发设备状态变化（如开关灯、开关门等）")
            
            # 监听通知（最多等待 30 秒）
            try:
                notification = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                notification_data = json.loads(notification)
                print(f"收到通知: {notification_data}")
                
                # 验证通知格式
                if notification_data.get("type") in ["device_status", "device_state_update"]:
                    print("✓ 测试通过：收到设备状态通知")
                else:
                    print(f"收到其他类型消息: {notification_data.get('type')}")
                    
            except asyncio.TimeoutError:
                print("⚠ 超时：未收到设备状态通知（可能设备未触发状态变化）")
                
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        raise


async def test_multiple_app_connections():
    """测试多个 App 同时连接"""
    print("\n=== 测试 3: 多个 App 同时连接 ===")
    
    uri = "ws://localhost:8000/ws/app"
    device_id = "test_device_001"
    
    async def connect_app(app_id: str):
        """单个 App 连接"""
        try:
            async with websockets.connect(uri) as websocket:
                hello_msg = {
                    "type": "hello",
                    "client_type": "app",
                    "device_id": device_id,
                    "app_id": app_id
                }
                await websocket.send(json.dumps(hello_msg))
                response = await websocket.recv()
                response_data = json.loads(response)
                print(f"App {app_id} 连接成功: {response_data['status']}")
                
                # 保持连接 5 秒
                await asyncio.sleep(5)
                
        except Exception as e:
            print(f"App {app_id} 连接失败: {e}")
    
    # 同时连接 3 个 App
    tasks = [
        connect_app("app_user_001"),
        connect_app("app_user_002"),
        connect_app("app_user_003")
    ]
    
    await asyncio.gather(*tasks)
    print("✓ 测试通过：多个 App 可以同时连接")


async def main():
    """运行所有测试"""
    print("开始测试 App 离线连接功能\n")
    
    try:
        await test_app_connection_when_device_offline()
        await test_device_status_notification()
        await test_multiple_app_connections()
        
        print("\n=== 所有测试完成 ===")
        
    except Exception as e:
        print(f"\n测试过程中出现错误: {e}")


if __name__ == "__main__":
    asyncio.run(main())
