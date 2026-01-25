#!/usr/bin/env python3
"""
测试监控模式下 opus 解码逻辑的修复

验证 BinaryProtocol2 协议头解析是否正确
"""

def test_binary_protocol2_parsing():
    """测试 BinaryProtocol2 头部解析"""
    
    # 模拟一个 BinaryProtocol2 音频帧
    # 头部结构：version(2) + type(2) + reserved(4) + timestamp(4) + payload_size(4)
    version = 2
    msg_type = 0
    reserved = 0  # 音频帧 reserved=0
    timestamp = 1000
    payload_size = 100  # 假设 opus payload 为 100 字节
    
    # 构造头部（大端序）
    header = (
        version.to_bytes(2, 'big') +
        msg_type.to_bytes(2, 'big') +
        reserved.to_bytes(4, 'big') +
        timestamp.to_bytes(4, 'big') +
        payload_size.to_bytes(4, 'big')
    )
    
    # 模拟 opus payload（实际应该是有效的 opus 数据）
    opus_payload = b'\x00' * payload_size
    
    # 完整帧
    full_frame = header + opus_payload
    
    print(f"完整帧长度: {len(full_frame)} 字节")
    print(f"头部长度: {len(header)} 字节")
    print(f"Payload 长度: {len(opus_payload)} 字节")
    print(f"头部十六进制: {header.hex()}")
    
    # 解析头部（模拟修复后的代码）
    if len(full_frame) < 16:
        print("❌ 数据长度不足 16 字节")
        return False
    
    parsed_payload_size = int.from_bytes(full_frame[12:16], 'big')
    print(f"\n解析的 payload_size: {parsed_payload_size}")
    
    if len(full_frame) < 16 + parsed_payload_size:
        print(f"❌ 数据长度不匹配: 期望 {16 + parsed_payload_size}，实际 {len(full_frame)}")
        return False
    
    extracted_payload = full_frame[16:16 + parsed_payload_size]
    print(f"提取的 payload 长度: {len(extracted_payload)} 字节")
    
    # 验证
    if extracted_payload == opus_payload:
        print("✅ Payload 提取正确！")
        return True
    else:
        print("❌ Payload 提取错误！")
        return False


def test_video_frame_parsing():
    """测试视频帧解析（reserved 包含分辨率）"""
    
    version = 2
    msg_type = 0
    width = 640
    height = 480
    reserved = (width << 16) | height  # 高 16 位存宽度，低 16 位存高度
    timestamp = 2000
    payload_size = 5000  # JPEG 数据
    
    header = (
        version.to_bytes(2, 'big') +
        msg_type.to_bytes(2, 'big') +
        reserved.to_bytes(4, 'big') +
        timestamp.to_bytes(4, 'big') +
        payload_size.to_bytes(4, 'big')
    )
    
    print(f"\n视频帧测试:")
    print(f"原始分辨率: {width}x{height}")
    print(f"Reserved 字段: 0x{reserved:08x}")
    
    # 解析 reserved
    parsed_reserved = int.from_bytes(header[4:8], 'big')
    parsed_width = (parsed_reserved >> 16) & 0xFFFF
    parsed_height = parsed_reserved & 0xFFFF
    
    print(f"解析的分辨率: {parsed_width}x{parsed_height}")
    
    if parsed_width == width and parsed_height == height:
        print("✅ 视频帧分辨率解析正确！")
        return True
    else:
        print("❌ 视频帧分辨率解析错误！")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("测试 BinaryProtocol2 协议解析")
    print("=" * 60)
    
    result1 = test_binary_protocol2_parsing()
    result2 = test_video_frame_parsing()
    
    print("\n" + "=" * 60)
    if result1 and result2:
        print("✅ 所有测试通过！")
    else:
        print("❌ 部分测试失败！")
    print("=" * 60)
