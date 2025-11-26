import struct
import json
from typing import Tuple, Optional
from enum import Enum

# 音视频数据包格式定义
class MediaPacketType(Enum):
    """音视频数据包类型枚举"""
    AUDIO = b'AUDD'  # Audio Data
    VIDEO = b'VIDD'  # Video Data
    CONTROL = b'CTRL'  # Control Command
    HEARTBEAT = b'HBDD'  # Heartbeat
    
    @classmethod
    def from_bytes(cls, header_bytes: bytes) -> Optional['MediaPacketType']:
        """从字节数据获取数据包类型"""
        for packet_type in cls:
            if packet_type.value == header_bytes:
                return packet_type
        return None


class MediaProtocolHelper:
    """音视频协议处理工具类"""
    
    # 数据包格式: [标识(4字节)][时间戳(8字节)][序列号(4字节)][数据长度(4字节)][数据]
    HEADER_SIZE = 20  # 4 + 8 + 4 + 4 = 20字节
    TIMESTAMP_OFFSET = 4
    SEQUENCE_OFFSET = 12
    LENGTH_OFFSET = 16
    
    @staticmethod
    def create_audio_packet(audio_data: bytes, timestamp: int = None, sequence: int = None) -> bytes:
        """创建音频数据包"""
        import time
        
        if timestamp is None:
            timestamp = int(time.time() * 1000)  # 毫秒时间戳
        
        if sequence is None:
            sequence = 0  # 序列号，可以根据需要实现递增逻辑
        
        # 打包：标识 + 时间戳 + 序列号 + 数据长度 + 数据
        header = MediaPacketType.AUDIO.value
        timestamp_bytes = struct.pack('>Q', timestamp)  # 8字节大端序时间戳
        sequence_bytes = struct.pack('>I', sequence)    # 4字节大端序序列号
        length_bytes = struct.pack('>I', len(audio_data))  # 4字节大端序数据长度
        
        return header + timestamp_bytes + sequence_bytes + length_bytes + audio_data
    
    @staticmethod
    def create_video_packet(video_data: bytes, timestamp: int = None, sequence: int = None) -> bytes:
        """创建视频数据包"""
        import time
        
        if timestamp is None:
            timestamp = int(time.time() * 1000)  # 毫秒时间戳
        
        if sequence is None:
            sequence = 0  # 序列号
        
        # 打包：标识 + 时间戳 + 序列号 + 数据长度 + 数据
        header = MediaPacketType.VIDEO.value
        timestamp_bytes = struct.pack('>Q', timestamp)  # 8字节大端序时间戳
        sequence_bytes = struct.pack('>I', sequence)    # 4字节大端序序列号
        length_bytes = struct.pack('>I', len(video_data))  # 4字节大端序数据长度
        
        return header + timestamp_bytes + sequence_bytes + length_bytes + video_data
    
    @staticmethod
    def create_control_packet(control_data: dict, timestamp: int = None) -> bytes:
        """创建控制数据包"""
        import time
        
        if timestamp is None:
            timestamp = int(time.time() * 1000)  # 毫秒时间戳
        
        # 将控制数据转换为JSON字符串，再编码为字节
        control_json = json.dumps(control_data, ensure_ascii=False)
        control_bytes = control_json.encode('utf-8')
        
        # 打包：标识 + 时间戳 + 序列号(0) + 数据长度 + 数据
        header = MediaPacketType.CONTROL.value
        timestamp_bytes = struct.pack('>Q', timestamp)  # 8字节大端序时间戳
        sequence_bytes = struct.pack('>I', 0)           # 4字节大端序序列号（控制包通常不需要）
        length_bytes = struct.pack('>I', len(control_bytes))  # 4字节大端序数据长度
        
        return header + timestamp_bytes + sequence_bytes + length_bytes + control_bytes
    
    @staticmethod
    def create_heartbeat_packet() -> bytes:
        """创建心跳数据包"""
        import time
        timestamp = int(time.time() * 1000)
        
        header = MediaPacketType.HEARTBEAT.value
        timestamp_bytes = struct.pack('>Q', timestamp)  # 8字节大端序时间戳
        sequence_bytes = struct.pack('>I', 0)           # 4字节大端序序列号
        length_bytes = struct.pack('>I', 0)             # 4字节大端序数据长度（心跳包无数据）
        
        return header + timestamp_bytes + sequence_bytes + length_bytes
    
    @classmethod
    def parse_packet(cls, packet_bytes: bytes) -> Optional[Tuple[MediaPacketType, int, int, int, bytes]]:
        """
        解析数据包
        返回: (数据包类型, 时间戳, 序列号, 数据长度, 数据)
        """
        if len(packet_bytes) < cls.HEADER_SIZE:
            return None
        
        # 解析头部
        header = packet_bytes[:4]
        packet_type = MediaPacketType.from_bytes(header)
        if packet_type is None:
            return None
        
        timestamp = struct.unpack('>Q', packet_bytes[cls.TIMESTAMP_OFFSET:cls.SEQUENCE_OFFSET])[0]
        sequence = struct.unpack('>I', packet_bytes[cls.SEQUENCE_OFFSET:cls.LENGTH_OFFSET])[0]
        data_length = struct.unpack('>I', packet_bytes[cls.LENGTH_OFFSET:cls.HEADER_SIZE])[0]
        
        # 提取数据部分
        if len(packet_bytes) < cls.HEADER_SIZE + data_length:
            # 数据包不完整
            return None
        
        data = packet_bytes[cls.HEADER_SIZE:cls.HEADER_SIZE + data_length]
        
        return packet_type, timestamp, sequence, data_length, data
    
    @classmethod
    def is_complete_packet(cls, packet_bytes: bytes) -> bool:
        """检查数据包是否完整"""
        if len(packet_bytes) < cls.HEADER_SIZE:
            return False
        
        # 解析头部获取数据长度
        data_length = struct.unpack('>I', packet_bytes[cls.LENGTH_OFFSET:cls.HEADER_SIZE])[0]
        
        # 检查总长度是否等于头部长度加数据长度
        return len(packet_bytes) >= cls.HEADER_SIZE + data_length
    
    @staticmethod
    def get_packet_type(packet_bytes: bytes) -> Optional[MediaPacketType]:
        """获取数据包类型（快速判断）"""
        if len(packet_bytes) < 4:
            return None
        return MediaPacketType.from_bytes(packet_bytes[:4])
    
    @staticmethod
    def validate_audio_data(audio_data: bytes) -> bool:
        """验证音频数据格式"""
        # 可以根据实际音频格式添加验证逻辑
        # 这里简单检查数据是否存在
        return audio_data is not None and len(audio_data) > 0
    
    @staticmethod
    def validate_video_data(video_data: bytes) -> bool:
        """验证视频数据格式"""
        # 可以根据实际视频格式添加验证逻辑
        # 这里简单检查数据是否存在
        return video_data is not None and len(video_data) > 0


# 便捷函数
def create_audio_packet(audio_data: bytes, timestamp: int = None, sequence: int = None) -> bytes:
    """便捷函数：创建音频数据包"""
    return MediaProtocolHelper.create_audio_packet(audio_data, timestamp, sequence)


def create_video_packet(video_data: bytes, timestamp: int = None, sequence: int = None) -> bytes:
    """便捷函数：创建视频数据包"""
    return MediaProtocolHelper.create_video_packet(video_data, timestamp, sequence)


def parse_packet(packet_bytes: bytes) -> Optional[Tuple[MediaPacketType, int, int, int, bytes]]:
    """便捷函数：解析数据包"""
    return MediaProtocolHelper.parse_packet(packet_bytes)


def get_packet_type(packet_bytes: bytes) -> Optional[MediaPacketType]:
    """便捷函数：获取数据包类型"""
    return MediaProtocolHelper.get_packet_type(packet_bytes)