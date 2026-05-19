#!/usr/bin/env python3
"""
测试 App 上线推送功能

测试场景：
1. App 连接并认证成功
2. 验证立即推送的消息（设备状态、传感器状态）
3. 验证延迟推送的消息（开锁日志、到访记录）
"""
import asyncio
import json
import websockets
from datetime import datetime


class AppPushTester:
    """App 推送功能测试器"""
    
    def __init__(self, server_url: str, device_id: str, app_id: str):
        self.server_url = server_url
        self.device_id = device_id
        self.app_id = app_id
        self.received_messages = []
        
    async def test_connection(self):
        """测试连接和推送"""
        print("="*60)
        print("App 上线推送功能测试")
        print("="*60)
        print(f"服务器: {self.server_url}")
        print(f"设备ID: {self.device_id}")
        print(f"AppID: {self.app_id}")
        print()
        
        try:
            async with websockets.connect(self.server_url) as ws:
                print("✓ WebSocket 连接成功")
                
                # 发送 hello 消息
                hello_msg = {
                    "type": "hello",
                    "device_id": self.device_id,
                    "app_id": self.app_id,
                    "client_type": "app"
                }
                
                print(f"\n发送 hello 消息: {json.dumps(hello_msg, ensure_ascii=False)}")
                await ws.send(json.dumps(hello_msg))
                
                # 接收消息（最多等待 10 秒，因为有延迟推送）
                print("\n等待服务器推送消息...")
                print("-"*60)
                
                timeout = 10
                start_time = asyncio.get_event_loop().time()
                
                while asyncio.get_event_loop().time() - start_time < timeout:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        msg_json = json.loads(msg)
                        self.received_messages.append(msg_json)
                        
                        # 打印收到的消息
                        msg_type = msg_json.get("type")
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        
                        print(f"[{timestamp}] 收到消息: {msg_type}")
                        
                        # 打印消息详情
                        if msg_type == "hello":
                            status = msg_json.get("status")
                            device_info = msg_json.get("device_info", {})
                            print(f"  └─ 认证状态: {status}")
                            print(f"  └─ 设备在线: {device_info.get('online')}")
                            print(f"  └─ 工作模式: {device_info.get('mode')}")
                        
                        elif msg_type == "device_status":
                            status = msg_json.get("status")
                            reason = msg_json.get("reason", "")
                            print(f"  └─ 设备状态: {status} {reason}")
                        
                        elif msg_type == "status_report":
                            data = msg_json.get("data", {})
                            print(f"  └─ 电量: {data.get('bat')}%")
                            print(f"  └─ 光照: {data.get('lux')} Lux")
                            print(f"  └─ 锁状态: {data.get('lock')}")
                            print(f"  └─ 补光灯: {data.get('light')}")
                        
                        elif msg_type == "log_report":
                            data = msg_json.get("data", {})
                            print(f"  └─ 方式: {data.get('method')}")
                            print(f"  └─ 用户: {data.get('uid')}")
                            print(f"  └─ 状态: {data.get('status')}")
                        
                        elif msg_type == "visit_notification":
                            data = msg_json.get("data", {})
                            print(f"  └─ 访客: {data.get('person_name')}")
                            print(f"  └─ 关系: {data.get('relation')}")
                            print(f"  └─ 结果: {data.get('result')}")
                            print(f"  └─ 授权: {data.get('access_granted')}")
                        
                        print()
                        
                    except asyncio.TimeoutError:
                        continue
                
                print("-"*60)
                print(f"\n✓ 测试完成，共收到 {len(self.received_messages)} 条消息")
                
                # 统计消息类型
                self._print_summary()
                
        except websockets.exceptions.WebSocketException as e:
            print(f"✗ WebSocket 连接失败: {e}")
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _print_summary(self):
        """打印消息统计"""
        print("\n消息统计:")
        print("-"*60)
        
        msg_types = {}
        for msg in self.received_messages:
            msg_type = msg.get("type")
            msg_types[msg_type] = msg_types.get(msg_type, 0) + 1
        
        for msg_type, count in sorted(msg_types.items()):
            print(f"  {msg_type}: {count} 条")
        
        print()
        
        # 验证推送顺序
        print("推送顺序验证:")
        print("-"*60)
        
        expected_order = [
            ("hello", "认证响应"),
            ("device_status", "设备在线状态"),
            ("status_report", "传感器状态"),
            ("log_report", "开锁日志（延迟1秒）"),
            ("visit_notification", "到访记录（延迟1秒）")
        ]
        
        for i, (expected_type, description) in enumerate(expected_order):
            if i < len(self.received_messages):
                actual_type = self.received_messages[i].get("type")
                if actual_type == expected_type:
                    print(f"  ✓ {description}: {actual_type}")
                else:
                    print(f"  ✗ {description}: 期望 {expected_type}, 实际 {actual_type}")
            else:
                print(f"  ✗ {description}: 未收到")
        
        print()


async def main():
    """主函数"""
    # 配置参数
    server_url = "ws://localhost:8000/ws/app"
    device_id = "AA:BB:CC:DD:EE:FF"  # 替换为实际的设备 ID
    app_id = "test_user_001"
    
    # 创建测试器
    tester = AppPushTester(server_url, device_id, app_id)
    
    # 运行测试
    await tester.test_connection()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n测试已中断")
