"""
访客意图识别测试脚本

用于测试基于大语言模型的访客交互功能：
- 模拟不同意图的访客语音输入（快递员、朋友拜访、求助等）
- 通过WebSocket发送到服务器
- 观察服务器端的意图识别结果
- 验证小程序通知功能

测试场景：
1. 快递员送货
2. 朋友拜访
3. 推销人员
4. 维修人员
5. 求助场景
"""

import asyncio
import websockets
import json
import base64
import time
from pathlib import Path
from typing import Dict, Any, List
import sys

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent / "main" / "xiaozhi-server"))


class VisitorIntentTester:
    """访客意图识别测试器"""
    
    def __init__(
        self,
        server_url: str = "ws://localhost:8000/xiaozhi/v1/",
        device_id: str = "TEST:DE:VI:CE:00:01"
    ):
        """初始化测试器
        
        Args:
            server_url: WebSocket服务器地址
            device_id: 测试设备ID
        """
        self.server_url = server_url
        self.device_id = device_id
        self.ws = None
        self.session_id = None
        
        # 测试场景配置
        self.test_scenarios = [
            {
                "name": "快递员送货",
                "intent_type": "delivery",
                "dialogues": [
                    {"role": "assistant", "content": "您好，请问您找谁？"},
                    {"role": "user", "content": "你好，我是快递员，有个包裹要送给张先生"},
                    {"role": "assistant", "content": "好的，请问是什么快递公司的？"},
                    {"role": "user", "content": "顺丰快递，麻烦帮我转告一下，包裹比较大，需要本人签收"},
                    {"role": "assistant", "content": "好的，我已经记录下来了，会转告张先生的"},
                    {"role": "user", "content": "谢谢，那我先把包裹放在门口了"}
                ],
                "expected_intent": "delivery",
                "expected_notes": ["快递", "顺丰", "需要本人签收"]
            },
            {
                "name": "朋友拜访",
                "intent_type": "visit",
                "dialogues": [
                    {"role": "assistant", "content": "您好，请问您找谁？"},
                    {"role": "user", "content": "你好，我是李明，来找张伟的"},
                    {"role": "assistant", "content": "好的，请问您和张伟是什么关系呢？"},
                    {"role": "user", "content": "我们是大学同学，约好今天一起吃饭"},
                    {"role": "assistant", "content": "明白了，我帮您通知一下张伟"},
                    {"role": "user", "content": "好的，谢谢"}
                ],
                "expected_intent": "visit",
                "expected_notes": ["李明", "大学同学", "约好吃饭"]
            },
            {
                "name": "推销人员",
                "intent_type": "sales",
                "dialogues": [
                    {"role": "assistant", "content": "您好，请问您找谁？"},
                    {"role": "user", "content": "你好，我是XX保险公司的，想了解一下您家是否需要保险服务"},
                    {"role": "assistant", "content": "不好意思，我们暂时不需要"},
                    {"role": "user", "content": "没关系，我可以留个联系方式吗？"},
                    {"role": "assistant", "content": "抱歉，我们真的不需要"}
                ],
                "expected_intent": "sales",
                "expected_notes": ["保险", "推销"]
            },
            {
                "name": "物业维修",
                "intent_type": "maintenance",
                "dialogues": [
                    {"role": "assistant", "content": "您好，请问您找谁？"},
                    {"role": "user", "content": "你好，我是物业的，来检查一下水表"},
                    {"role": "assistant", "content": "好的，请稍等，我帮您联系业主"},
                    {"role": "user", "content": "好的，麻烦了，我在门口等"}
                ],
                "expected_intent": "maintenance",
                "expected_notes": ["物业", "检查水表"]
            },
            {
                "name": "紧急求助",
                "intent_type": "emergency",
                "dialogues": [
                    {"role": "assistant", "content": "您好，请问您找谁？"},
                    {"role": "user", "content": "你好，我是楼上的邻居，家里水管爆了，水漏到你家了吗？"},
                    {"role": "assistant", "content": "这个情况比较紧急，我马上通知业主"},
                    {"role": "user", "content": "好的，麻烦快点，我已经关了总阀门"}
                ],
                "expected_intent": "emergency",
                "expected_notes": ["邻居", "水管爆了", "紧急"]
            }
        ]
    
    async def connect(self):
        """连接到WebSocket服务器"""
        try:
            print(f"正在连接到服务器: {self.server_url}")
            self.ws = await websockets.connect(self.server_url)
            print("✓ 连接成功")
            
            # 发送hello消息
            await self.send_hello()
            
            # 等待服务器响应
            response = await self.ws.recv()
            print(f"收到服务器响应: {response}")
            
            return True
            
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            return False
    
    async def send_hello(self):
        """发送hello消息（建立连接）"""
        hello_msg = {
            "type": "hello",
            "version": 1,
            "device_id": self.device_id,
            "transport": "websocket",
            "audio_params": {
                "format": "opus",
                "sample_rate": 16000,
                "channels": 1,
                "frame_duration": 60
            }
        }
        
        await self.ws.send(json.dumps(hello_msg))
        print(f"已发送hello消息: device_id={self.device_id}")
    
    async def simulate_pir_trigger(self):
        """模拟PIR触发（访客到达）"""
        print("\n" + "="*60)
        print("模拟PIR触发 - 访客到达")
        print("="*60)
        
        pir_msg = {
            "type": "pir_trigger",
            "timestamp": int(time.time() * 1000),
            "device_id": self.device_id
        }
        
        await self.ws.send(json.dumps(pir_msg))
        print("✓ 已发送PIR触发消息")
        
        # 等待服务器响应
        await asyncio.sleep(1)
    
    async def send_visitor_image(self, image_path: str = None):
        """发送访客照片
        
        Args:
            image_path: 照片路径，如果为None则使用测试图片
        """
        print("\n发送访客照片...")
        
        # 如果没有指定图片，创建一个测试图片
        if not image_path:
            # 创建一个简单的测试图片（1x1像素的JPEG）
            test_image_data = base64.b64decode(
                "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
                "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIy"
                "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIA"
                "AhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEB"
                "AQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwABmQ/9k="
            )
        else:
            with open(image_path, 'rb') as f:
                test_image_data = f.read()
        
        # Base64编码
        image_base64 = base64.b64encode(test_image_data).decode('utf-8')
        
        # 发送图片消息
        image_msg = {
            "type": "visitor_image",
            "timestamp": int(time.time() * 1000),
            "device_id": self.device_id,
            "image_data": image_base64,
            "format": "jpeg"
        }
        
        await self.ws.send(json.dumps(image_msg))
        print(f"✓ 已发送访客照片 (大小: {len(test_image_data)} bytes)")
        
        # 等待人脸识别结果
        await asyncio.sleep(2)
    
    async def simulate_dialogue(self, scenario: Dict[str, Any]):
        """模拟对话场景
        
        Args:
            scenario: 测试场景配置
        """
        print(f"\n{'='*60}")
        print(f"测试场景: {scenario['name']}")
        print(f"预期意图类型: {scenario['intent_type']}")
        print(f"{'='*60}\n")
        
        dialogues = scenario['dialogues']
        
        for i, dialogue in enumerate(dialogues):
            role = dialogue['role']
            content = dialogue['content']
            
            if role == "user":
                # 访客说话 - 发送文本消息（模拟ASR结果）
                print(f"[访客] {content}")
                
                text_msg = {
                    "type": "text",
                    "timestamp": int(time.time() * 1000),
                    "device_id": self.device_id,
                    "text": content,
                    "source": "visitor"  # 标记为访客输入
                }
                
                await self.ws.send(json.dumps(text_msg))
                
                # 等待AI处理和回复
                await asyncio.sleep(2)
                
            elif role == "assistant":
                # AI回复 - 这里只是打印预期回复，实际回复由服务器生成
                print(f"[AI预期] {content}")
                await asyncio.sleep(1)
        
        print(f"\n{'='*60}")
        print(f"对话结束 - 等待意图识别结果...")
        print(f"{'='*60}\n")
        
        # 等待意图识别完成
        await asyncio.sleep(3)
    
    async def wait_for_intent_result(self, timeout: int = 10):
        """等待意图识别结果
        
        Args:
            timeout: 超时时间（秒）
        """
        print("\n等待服务器返回意图识别结果...")
        
        try:
            # 设置超时
            response = await asyncio.wait_for(
                self.ws.recv(),
                timeout=timeout
            )
            
            result = json.loads(response)
            
            if result.get("type") == "intent_result":
                print("\n" + "="*60)
                print("收到意图识别结果:")
                print("="*60)
                print(json.dumps(result, indent=2, ensure_ascii=False))
                print("="*60 + "\n")
                
                return result
            else:
                print(f"收到其他消息: {result.get('type')}")
                return None
                
        except asyncio.TimeoutError:
            print(f"✗ 等待超时（{timeout}秒）")
            return None
        except Exception as e:
            print(f"✗ 接收消息失败: {e}")
            return None
    
    async def run_test_scenario(self, scenario: Dict[str, Any]):
        """运行单个测试场景
        
        Args:
            scenario: 测试场景配置
        """
        try:
            # 1. 模拟PIR触发
            await self.simulate_pir_trigger()
            
            # 2. 发送访客照片
            await self.send_visitor_image()
            
            # 3. 模拟对话
            await self.simulate_dialogue(scenario)
            
            # 4. 等待意图识别结果
            result = await self.wait_for_intent_result()
            
            # 5. 验证结果
            if result:
                self.verify_result(scenario, result)
            
            print("\n" + "="*60)
            print(f"场景 '{scenario['name']}' 测试完成")
            print("="*60 + "\n")
            
            # 等待一段时间再进行下一个测试
            await asyncio.sleep(3)
            
        except Exception as e:
            print(f"✗ 测试场景失败: {e}")
            import traceback
            traceback.print_exc()
    
    def verify_result(self, scenario: Dict[str, Any], result: Dict[str, Any]):
        """验证测试结果
        
        Args:
            scenario: 测试场景配置
            result: 服务器返回的结果
        """
        print("\n" + "="*60)
        print("结果验证:")
        print("="*60)
        
        expected_intent = scenario['expected_intent']
        actual_intent = result.get('intent_summary', {}).get('intent_type')
        
        # 验证意图类型
        if actual_intent == expected_intent:
            print(f"✓ 意图类型匹配: {actual_intent}")
        else:
            print(f"✗ 意图类型不匹配: 预期={expected_intent}, 实际={actual_intent}")
        
        # 验证关键信息
        important_notes = result.get('intent_summary', {}).get('important_notes', [])
        expected_notes = scenario['expected_notes']
        
        print(f"\n关键信息提取:")
        for note in important_notes:
            print(f"  - {note}")
        
        print(f"\n预期包含的关键词:")
        for keyword in expected_notes:
            found = any(keyword in note for note in important_notes)
            status = "✓" if found else "✗"
            print(f"  {status} {keyword}")
        
        print("="*60 + "\n")
    
    async def run_all_tests(self):
        """运行所有测试场景"""
        print("\n" + "="*60)
        print("开始访客意图识别测试")
        print(f"服务器地址: {self.server_url}")
        print(f"设备ID: {self.device_id}")
        print(f"测试场景数量: {len(self.test_scenarios)}")
        print("="*60 + "\n")
        
        # 连接到服务器
        if not await self.connect():
            print("无法连接到服务器，测试终止")
            return
        
        try:
            # 依次运行每个测试场景
            for i, scenario in enumerate(self.test_scenarios, 1):
                print(f"\n{'#'*60}")
                print(f"# 测试场景 {i}/{len(self.test_scenarios)}")
                print(f"{'#'*60}\n")
                
                await self.run_test_scenario(scenario)
            
            print("\n" + "="*60)
            print("所有测试场景完成")
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"测试过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # 关闭连接
            if self.ws:
                await self.ws.close()
                print("已关闭WebSocket连接")
    
    async def run_single_test(self, scenario_name: str):
        """运行单个测试场景
        
        Args:
            scenario_name: 场景名称
        """
        # 查找场景
        scenario = None
        for s in self.test_scenarios:
            if s['name'] == scenario_name:
                scenario = s
                break
        
        if not scenario:
            print(f"找不到测试场景: {scenario_name}")
            print(f"可用场景: {[s['name'] for s in self.test_scenarios]}")
            return
        
        # 连接到服务器
        if not await self.connect():
            print("无法连接到服务器，测试终止")
            return
        
        try:
            await self.run_test_scenario(scenario)
        finally:
            if self.ws:
                await self.ws.close()


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='访客意图识别测试工具')
    parser.add_argument(
        '--server',
        default='ws://localhost:8000/xiaozhi/v1/',
        help='WebSocket服务器地址'
    )
    parser.add_argument(
        '--device-id',
        default='TEST:DE:VI:CE:00:01',
        help='测试设备ID'
    )
    parser.add_argument(
        '--scenario',
        help='指定测试场景名称（不指定则运行所有场景）'
    )
    
    args = parser.parse_args()
    
    # 创建测试器
    tester = VisitorIntentTester(
        server_url=args.server,
        device_id=args.device_id
    )
    
    # 运行测试
    if args.scenario:
        await tester.run_single_test(args.scenario)
    else:
        await tester.run_all_tests()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
