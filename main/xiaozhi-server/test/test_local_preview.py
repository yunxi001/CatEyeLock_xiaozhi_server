"""
本地预览功能测试脚本

测试本地预览控制插件的功能，包括：
1. 语音命令识别
2. WebSocket 命令发送
3. 响应处理
4. 错误处理

使用方法：
    python test/test_local_preview.py

作者：毕业设计项目组
创建日期：2026-05-04
"""

import asyncio
import json
import websockets
import time


async def test_local_preview_voice_command():
    """测试语音命令控制本地预览"""
    
    uri = "ws://localhost:8000"
    device_id = "test_device_001"
    
    print("=" * 60)
    print("测试场景1：语音命令控制本地预览")
    print("=" * 60)
    
    try:
        async with websockets.connect(uri) as websocket:
            # 1. 发送 hello 消息
            hello_msg = {
                "type": "hello",
                "device_id": device_id,
                "client_type": "esp32"
            }
            await websocket.send(json.dumps(hello_msg))
            print(f"→ 发送认证消息: {hello_msg}")
            
            # 接收 hello 响应
            response = await websocket.recv()
            print(f"← 收到响应: {response}\n")
            
            # 2. 模拟语音输入："显示监控画面"
            print("测试用例 1: 启动本地预览")
            print("-" * 60)
            
            text_msg = {
                "type": "text",
                "text": "显示监控画面"
            }
            await websocket.send(json.dumps(text_msg))
            print(f"→ 发送语音文本: {text_msg}")
            
            # 等待服务器处理（意图识别 + 插件调用 + WebSocket 命令）
            await asyncio.sleep(1)
            
            # 3. 模拟 ESP32 返回成功响应
            esp32_response = {
                "type": "local_preview",
                "action": "start",
                "status": "success"
            }
            await websocket.send(json.dumps(esp32_response))
            print(f"→ 模拟 ESP32 响应: {esp32_response}")
            
            # 等待 TTS 语音反馈
            await asyncio.sleep(2)
            print("✓ 预期语音反馈: '已打开本地预览'\n")
            
            # 4. 测试停止本地预览
            print("测试用例 2: 停止本地预览")
            print("-" * 60)
            
            text_msg = {
                "type": "text",
                "text": "关闭监控画面"
            }
            await websocket.send(json.dumps(text_msg))
            print(f"→ 发送语音文本: {text_msg}")
            
            await asyncio.sleep(1)
            
            esp32_response = {
                "type": "local_preview",
                "action": "stop",
                "status": "success"
            }
            await websocket.send(json.dumps(esp32_response))
            print(f"→ 模拟 ESP32 响应: {esp32_response}")
            
            await asyncio.sleep(2)
            print("✓ 预期语音反馈: '已关闭本地预览'\n")
            
            # 5. 测试错误情况：监控模式冲突
            print("测试用例 3: 监控模式冲突")
            print("-" * 60)
            
            text_msg = {
                "type": "text",
                "text": "打开本地预览"
            }
            await websocket.send(json.dumps(text_msg))
            print(f"→ 发送语音文本: {text_msg}")
            
            await asyncio.sleep(1)
            
            esp32_response = {
                "type": "local_preview",
                "action": "start",
                "status": "error",
                "error": "Monitor mode active"
            }
            await websocket.send(json.dumps(esp32_response))
            print(f"→ 模拟 ESP32 错误响应: {esp32_response}")
            
            await asyncio.sleep(2)
            print("✓ 预期语音反馈: '监控模式正在运行，无法启动本地预览'\n")
            
            print("=" * 60)
            print("测试完成！")
            print("=" * 60)
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_trigger_word_variants():
    """测试触发词变体识别"""
    
    print("\n" + "=" * 60)
    print("测试场景2：触发词变体识别")
    print("=" * 60)
    
    trigger_words = [
        # 启动本地预览
        "显示监控画面",
        "打开监控画面",
        "让我看看门口",
        "打开本地预览",
        "屏幕显示摄像头",
        "打开屏幕",
        "显示摄像头",
        # 停止本地预览
        "关闭监控画面",
        "隐藏监控画面",
        "关闭本地预览",
        "关闭屏幕显示",
        "关闭屏幕",
        "隐藏摄像头"
    ]
    
    print("以下触发词应该都能被正确识别：")
    print("-" * 60)
    for i, word in enumerate(trigger_words, 1):
        expected_action = "start" if i <= 7 else "stop"
        print(f"{i:2d}. '{word}' → 预期识别为: {expected_action}")
    
    print("\n注意：实际识别由 LLM 完成，以上仅为预期结果")
    print("=" * 60)


async def test_error_handling():
    """测试错误处理"""
    
    print("\n" + "=" * 60)
    print("测试场景3：错误处理")
    print("=" * 60)
    
    error_cases = [
        {
            "error": "Camera not available",
            "expected": "摄像头暂时不可用"
        },
        {
            "error": "Monitor mode active",
            "expected": "监控模式正在运行，无法启动本地预览"
        },
        {
            "error": "Face recognition active",
            "expected": "人脸识别正在进行，请稍后再试"
        },
        {
            "error": "System error",
            "expected": "系统错误，请稍后再试"
        },
        {
            "error": "timeout",
            "expected": "操作超时，请稍后再试"
        }
    ]
    
    print("错误码映射测试：")
    print("-" * 60)
    for i, case in enumerate(error_cases, 1):
        print(f"{i}. ESP32 错误: '{case['error']}'")
        print(f"   → 语音反馈: '{case['expected']}'")
    
    print("\n=" * 60)


async def main():
    """主测试函数"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "本地预览功能测试套件" + " " * 15 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    # 测试1：语音命令控制
    # 注意：需要服务器运行才能执行此测试
    # await test_local_preview_voice_command()
    
    # 测试2：触发词变体
    await test_trigger_word_variants()
    
    # 测试3：错误处理
    await test_error_handling()
    
    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)
    print("\n提示：")
    print("1. 要测试完整功能，请启动服务器后取消注释 test_local_preview_voice_command()")
    print("2. 确保 ESP32 端已实现 local_preview 消息处理")
    print("3. 检查日志文件以查看详细的执行过程")
    print()


if __name__ == "__main__":
    asyncio.run(main())
