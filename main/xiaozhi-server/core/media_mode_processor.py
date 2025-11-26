import asyncio
import struct
import time
from typing import Dict, Any, Optional, Set
from config.logger import setup_logging

TAG = __name__


class MediaModeProcessor:
    """音视频模式处理器 - 专门处理音视频流数据"""
    
    def __init__(self, websocket, mode_switcher, config: Dict[str, Any]):
        self.websocket = websocket
        self.mode_switcher = mode_switcher
        self.config = config
        self.logger = setup_logging()
        
        # 音视频数据处理相关
        self._audio_buffer = bytearray()
        self._video_buffer = bytearray()
        self._audio_connections: Set = set()  # 存储需要转发音频的连接
        self._video_connections: Set = set()  # 存储需要转发视频的连接
        
        # 性能监控
        self._last_audio_timestamp = 0
        self._last_video_timestamp = 0
        self._audio_packet_count = 0
        self._video_packet_count = 0
        
        # 配置参数
        self._max_buffer_size = config.get("audio_video_stream", {}).get("max_buffer_size", 8192 * 10)  # 80KB
        self._enable_audio_forwarding = config.get("audio_video_stream", {}).get("enable_audio_forwarding", True)
        self._enable_video_forwarding = config.get("audio_video_stream", {}).get("enable_video_forwarding", False)
        
        # 任务控制
        self._running = False
        self._processor_task = None
        
    async def start_processing(self):
        """开始处理音视频数据"""
        self._running = True
        self.logger.bind(tag=TAG).info("音视频处理器已启动")
        
    async def stop_processing(self):
        """停止处理音视频数据"""
        self._running = False
        if self._processor_task and not self._processor_task.done():
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        self.logger.bind(tag=TAG).info("音视频处理器已停止")
        
    async def process_audio_data(self, audio_data: bytes, timestamp: Optional[int] = None):
        """处理接收到的音频数据"""
        try:
            if not self._running:
                return False
                
            # 增加音频包计数
            self._audio_packet_count += 1
            
            # 处理时间戳（如果提供）
            if timestamp is None:
                timestamp = int(time.time() * 1000)  # 使用当前时间戳
            
            # 验证音频数据
            if not audio_data:
                self.logger.bind(tag=TAG).warning("接收到空音频数据")
                return False
                
            # 转发音频数据到指定连接（如果启用转发）
            if self._enable_audio_forwarding:
                await self._forward_audio_data(audio_data, timestamp)
                
            # 更新性能监控数据
            self._last_audio_timestamp = timestamp
            
            # 检查缓冲区大小，避免过度增长
            if len(self._audio_buffer) > self._max_buffer_size:
                # 清空缓冲区或只保留最新的数据
                self._audio_buffer = bytearray()
                
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"处理音频数据时出错: {str(e)}")
            return False

    async def process_video_data(self, video_data: bytes, timestamp: Optional[int] = None):
        """处理接收到的视频数据"""
        try:
            if not self._running:
                return False
                
            # 增加视频包计数
            self._video_packet_count += 1
            
            # 处理时间戳（如果提供）
            if timestamp is None:
                timestamp = int(time.time() * 1000)  # 使用当前时间戳
            
            # 验证视频数据
            if not video_data:
                self.logger.bind(tag=TAG).warning("接收到空视频数据")
                return False
                
            # 转发视频数据到指定连接（如果启用转发）
            if self._enable_video_forwarding:
                await self._forward_video_data(video_data, timestamp)
                
            # 更新性能监控数据
            self._last_video_timestamp = timestamp
            
            # 检查缓冲区大小，避免过度增长
            if len(self._video_buffer) > self._max_buffer_size:
                # 清空缓冲区或只保留最新的数据
                self._video_buffer = bytearray()
                
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"处理视频数据时出错: {str(e)}")
            return False

    async def broadcast_audio(self, audio_data: bytes, source_device_id: str = None):
        """广播音频数据到所有连接"""
        try:
            if not self._running or not audio_data:
                return False
                
            # 添加音频数据标识头
            timestamp = int(time.time() * 1000)
            message = self._create_audio_packet(audio_data, timestamp)
            
            # 发送到所有连接
            disconnected = set()
            for connection in self._audio_connections.copy():
                try:
                    if connection != self.websocket:  # 避免回环
                        await connection.send(message)
                except Exception as e:
                    self.logger.bind(tag=TAG).warning(f"发送音频数据到连接失败: {str(e)}")
                    disconnected.add(connection)
            
            # 清理断开的连接
            for conn in disconnected:
                self._audio_connections.discard(conn)
                
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"广播音频数据时出错: {str(e)}")
            return False

    async def receive_audio_from_other_source(self, audio_data: bytes, source_info: Dict[str, Any] = None):
        """从其他源接收音频数据并转发到ESP32"""
        try:
            if not self._running or not audio_data:
                return False
                
            # 直接发送到当前ESP32连接
            timestamp = int(time.time() * 1000)
            message = self._create_audio_packet(audio_data, timestamp)
            
            try:
                await self.websocket.send(message)
            except Exception as e:
                self.logger.bind(tag=TAG).error(f"发送音频数据到ESP32失败: {str(e)}")
                return False
                
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"从其他源接收并转发音频时出错: {str(e)}")
            return False

    def _create_audio_packet(self, audio_data: bytes, timestamp: int) -> bytes:
        """创建音频数据包"""
        # 音频数据包格式: 标识(4字节) + 时间戳(8字节) + 音频数据
        header = b'AUDD'  # Audio Data标识
        timestamp_bytes = struct.pack('>Q', timestamp)  # 8字节大端序时间戳
        return header + timestamp_bytes + audio_data

    def _create_video_packet(self, video_data: bytes, timestamp: int) -> bytes:
        """创建视频数据包"""
        # 视频数据包格式: 标识(4字节) + 时间戳(8字节) + 视频数据
        header = b'VIDD'  # Video Data标识
        timestamp_bytes = struct.pack('>Q', timestamp)  # 8字节大端序时间戳
        return header + timestamp_bytes + video_data

    async def _forward_audio_data(self, audio_data: bytes, timestamp: int):
        """转发音频数据到其他连接"""
        try:
            message = self._create_audio_packet(audio_data, timestamp)
            
            # 发送到已注册的音频连接
            disconnected = set()
            for connection in self._audio_connections.copy():
                try:
                    await connection.send(message)
                except Exception as e:
                    self.logger.bind(tag=TAG).warning(f"转发音频数据失败: {str(e)}")
                    disconnected.add(connection)
            
            # 清理断开的连接
            for conn in disconnected:
                self._audio_connections.discard(conn)
                
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"转发音频数据时出错: {str(e)}")

    async def _forward_video_data(self, video_data: bytes, timestamp: int):
        """转发视频数据到其他连接"""
        try:
            message = self._create_video_packet(video_data, timestamp)
            
            # 发送到已注册的视频连接
            disconnected = set()
            for connection in self._video_connections.copy():
                try:
                    await connection.send(message)
                except Exception as e:
                    self.logger.bind(tag=TAG).warning(f"转发视频数据失败: {str(e)}")
                    disconnected.add(connection)
            
            # 清理断开的连接
            for conn in disconnected:
                self._video_connections.discard(conn)
                
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"转发视频数据时出错: {str(e)}")

    def add_audio_connection(self, connection):
        """添加音频转发连接"""
        self._audio_connections.add(connection)

    def remove_audio_connection(self, connection):
        """移除音频转发连接"""
        self._audio_connections.discard(connection)

    def add_video_connection(self, connection):
        """添加视频转发连接"""
        self._video_connections.add(connection)

    def remove_video_connection(self, connection):
        """移除视频转发连接"""
        self._video_connections.discard(connection)

    def get_processing_stats(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        return {
            "audio_packet_count": self._audio_packet_count,
            "video_packet_count": self._video_packet_count,
            "last_audio_timestamp": self._last_audio_timestamp,
            "last_video_timestamp": self._last_video_timestamp,
            "audio_connections_count": len(self._audio_connections),
            "video_connections_count": len(self._video_connections),
            "audio_buffer_size": len(self._audio_buffer),
            "video_buffer_size": len(self._video_buffer),
            "running": self._running
        }

    async def reset_stats(self):
        """重置统计信息"""
        self._audio_packet_count = 0
        self._video_packet_count = 0
        self._last_audio_timestamp = 0
        self._last_video_timestamp = 0
        self._audio_buffer = bytearray()
        self._video_buffer = bytearray()