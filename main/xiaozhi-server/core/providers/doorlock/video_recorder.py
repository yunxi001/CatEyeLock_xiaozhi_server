"""
监控录像记录器

负责在监控模式下缓存音视频帧，并在后台合成 MP4 文件。
采用异步设计，不阻塞主消息循环。
"""
import os
import io
import time
import asyncio
import threading
from queue import Queue, Empty
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass, field

TAG = __name__

# 录像分段时长（秒）
SEGMENT_DURATION = 300  # 5 分钟

# 最大缓存帧数（防止内存溢出）
MAX_BUFFER_FRAMES = 6000  # 约 10 分钟 @ 10fps


@dataclass
class VideoFrame:
    """视频帧数据"""
    timestamp: int  # 毫秒时间戳
    jpeg_data: bytes  # JPEG 图像数据
    width: int = 640
    height: int = 480


@dataclass
class AudioFrame:
    """音频帧数据"""
    timestamp: int  # 毫秒时间戳
    pcm_data: bytes  # PCM 音频数据（16kHz, 单声道, 16bit）


@dataclass
class RecordingSession:
    """录像会话"""
    device_id: str
    start_time: int  # 开始时间戳（毫秒）
    video_frames: List[VideoFrame] = field(default_factory=list)
    audio_frames: List[AudioFrame] = field(default_factory=list)
    is_recording: bool = True


class VideoRecorder:
    """监控录像记录器
    
    使用方式：
    1. start_recording() - 开始录制
    2. add_video_frame() / add_audio_frame() - 添加帧数据
    3. stop_recording() - 停止录制并触发后台合成
    """
    
    def __init__(self, media_storage, database=None, logger=None):
        """初始化录像记录器
        
        Args:
            media_storage: MediaStorage 实例，用于保存文件
            database: Database 实例，用于记录元数据（可选）
            logger: 日志记录器
        """
        self.media_storage = media_storage
        self.database = database
        self.logger = logger
        
        # 当前录像会话（每个设备一个）
        self._sessions: dict[str, RecordingSession] = {}
        
        # 后台合成任务队列
        self._synthesis_queue: Queue = Queue()
        
        # 后台合成线程
        self._synthesis_thread: Optional[threading.Thread] = None
        self._stop_synthesis = threading.Event()
        
        # 启动后台合成线程
        self._start_synthesis_thread()
    
    def _start_synthesis_thread(self):
        """启动后台合成线程"""
        if self._synthesis_thread is None or not self._synthesis_thread.is_alive():
            self._stop_synthesis.clear()
            self._synthesis_thread = threading.Thread(
                target=self._synthesis_worker,
                daemon=True,
                name="VideoSynthesisWorker"
            )
            self._synthesis_thread.start()
            if self.logger:
                self.logger.bind(tag=TAG).info("视频合成后台线程已启动")
    
    def _synthesis_worker(self):
        """后台合成工作线程"""
        while not self._stop_synthesis.is_set():
            try:
                # 等待合成任务（超时 1 秒）
                session = self._synthesis_queue.get(timeout=1.0)
                
                # 执行合成
                self._do_synthesis(session)
                
            except Empty:
                continue
            except Exception as e:
                if self.logger:
                    self.logger.bind(tag=TAG).error(f"视频合成失败: {e}")
    
    def start_recording(self, device_id: str) -> bool:
        """开始录制
        
        Args:
            device_id: 设备 ID
            
        Returns:
            是否成功开始
        """
        if device_id in self._sessions and self._sessions[device_id].is_recording:
            if self.logger:
                self.logger.bind(tag=TAG).warning(f"设备 {device_id} 已在录制中")
            return False
        
        self._sessions[device_id] = RecordingSession(
            device_id=device_id,
            start_time=int(time.time() * 1000)
        )
        
        if self.logger:
            self.logger.bind(tag=TAG).info(f"开始录制: {device_id}")
        
        return True
    
    def add_video_frame(self, device_id: str, jpeg_data: bytes, 
                        timestamp: int = None, width: int = 640, height: int = 480):
        """添加视频帧
        
        Args:
            device_id: 设备 ID
            jpeg_data: JPEG 图像数据
            timestamp: 时间戳（毫秒），默认当前时间
            width: 图像宽度
            height: 图像高度
        """
        session = self._sessions.get(device_id)
        if not session or not session.is_recording:
            return
        
        # 检查缓存是否已满
        if len(session.video_frames) >= MAX_BUFFER_FRAMES:
            if self.logger:
                self.logger.bind(tag=TAG).warning(
                    f"视频缓存已满，触发自动分段: {device_id}"
                )
            # 触发自动分段
            self._auto_segment(device_id)
            session = self._sessions.get(device_id)
            if not session:
                return
        
        frame = VideoFrame(
            timestamp=timestamp or int(time.time() * 1000),
            jpeg_data=jpeg_data,
            width=width,
            height=height
        )
        session.video_frames.append(frame)
    
    def add_audio_frame(self, device_id: str, pcm_data: bytes, timestamp: int = None):
        """添加音频帧
        
        Args:
            device_id: 设备 ID
            pcm_data: PCM 音频数据
            timestamp: 时间戳（毫秒），默认当前时间
        """
        session = self._sessions.get(device_id)
        if not session or not session.is_recording:
            return
        
        frame = AudioFrame(
            timestamp=timestamp or int(time.time() * 1000),
            pcm_data=pcm_data
        )
        session.audio_frames.append(frame)
    
    def stop_recording(self, device_id: str) -> bool:
        """停止录制并触发后台合成
        
        Args:
            device_id: 设备 ID
            
        Returns:
            是否成功停止
        """
        session = self._sessions.pop(device_id, None)
        if not session:
            if self.logger:
                self.logger.bind(tag=TAG).warning(f"设备 {device_id} 未在录制")
            return False
        
        session.is_recording = False
        
        # 检查是否有数据
        if not session.video_frames:
            if self.logger:
                self.logger.bind(tag=TAG).info(f"无视频数据，跳过合成: {device_id}")
            return True
        
        # 提交到后台合成队列
        self._synthesis_queue.put(session)
        
        if self.logger:
            self.logger.bind(tag=TAG).info(
                f"停止录制，提交合成任务: {device_id}, "
                f"视频帧={len(session.video_frames)}, 音频帧={len(session.audio_frames)}"
            )
        
        return True
    
    def _auto_segment(self, device_id: str):
        """自动分段：保存当前数据并开始新会话"""
        session = self._sessions.pop(device_id, None)
        if session:
            session.is_recording = False
            self._synthesis_queue.put(session)
        
        # 开始新会话
        self._sessions[device_id] = RecordingSession(
            device_id=device_id,
            start_time=int(time.time() * 1000)
        )
    
    def _do_synthesis(self, session: RecordingSession):
        """执行视频合成（在后台线程中运行）
        
        使用 OpenCV + 简单方式合成，不依赖 ffmpeg
        """
        try:
            if self.logger:
                self.logger.bind(tag=TAG).info(
                    f"开始合成视频: {session.device_id}, "
                    f"视频帧={len(session.video_frames)}"
                )
            
            # 计算时长
            if len(session.video_frames) >= 2:
                duration_ms = session.video_frames[-1].timestamp - session.video_frames[0].timestamp
                duration_sec = max(1, duration_ms // 1000)
            else:
                duration_sec = 1
            
            # 生成文件路径
            timestamp = session.start_time
            today = datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d")
            
            # 确保目录存在
            dir_path = self.media_storage.base_path / "recordings" / session.device_id / today
            dir_path.mkdir(parents=True, exist_ok=True)
            
            filename = f"rec_{timestamp}.mp4"
            file_path = dir_path / filename
            
            # 尝试使用 OpenCV 合成
            video_size = self._synthesize_with_opencv(session, file_path)
            
            if video_size and video_size > 0:
                # 记录到数据库
                relative_path = f"recordings/{session.device_id}/{today}/{filename}"
                
                if self.database:
                    try:
                        self.database.save_media_file(
                            device_id=session.device_id,
                            file_type="recording",
                            file_path=relative_path,
                            file_size=video_size,
                            duration=duration_sec
                        )
                    except Exception as e:
                        if self.logger:
                            self.logger.bind(tag=TAG).warning(f"保存媒体记录失败: {e}")
                
                if self.logger:
                    self.logger.bind(tag=TAG).info(
                        f"视频合成完成: {relative_path}, "
                        f"大小={video_size // 1024}KB, 时长={duration_sec}秒"
                    )
            else:
                if self.logger:
                    self.logger.bind(tag=TAG).warning(f"视频合成失败: {session.device_id}")
                    
        except Exception as e:
            if self.logger:
                self.logger.bind(tag=TAG).error(f"视频合成异常: {e}")
    
    def _synthesize_with_opencv(self, session: RecordingSession, 
                                 output_path: Path) -> Optional[int]:
        """使用 OpenCV 合成视频（无音频）
        
        Args:
            session: 录像会话
            output_path: 输出文件路径
            
        Returns:
            文件大小（字节），失败返回 None
        """
        try:
            import cv2
            import numpy as np
            
            if not session.video_frames:
                return None
            
            # 获取第一帧的尺寸
            first_frame = session.video_frames[0]
            width, height = first_frame.width, first_frame.height
            
            # 计算帧率
            if len(session.video_frames) >= 2:
                total_time_ms = session.video_frames[-1].timestamp - session.video_frames[0].timestamp
                fps = len(session.video_frames) / max(1, total_time_ms / 1000)
                fps = max(1, min(30, fps))  # 限制在 1-30 fps
            else:
                fps = 10
            
            # 创建视频写入器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
            
            if not writer.isOpened():
                if self.logger:
                    self.logger.bind(tag=TAG).error("无法创建视频写入器")
                return None
            
            # 写入帧
            for frame in session.video_frames:
                try:
                    # 解码 JPEG
                    nparr = np.frombuffer(frame.jpeg_data, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if img is not None:
                        # 确保尺寸一致
                        if img.shape[1] != width or img.shape[0] != height:
                            img = cv2.resize(img, (width, height))
                        writer.write(img)
                except Exception as e:
                    if self.logger:
                        self.logger.bind(tag=TAG).debug(f"跳过损坏帧: {e}")
                    continue
            
            writer.release()
            
            # 返回文件大小
            if output_path.exists():
                return output_path.stat().st_size
            return None
            
        except ImportError:
            if self.logger:
                self.logger.bind(tag=TAG).warning(
                    "OpenCV 未安装，无法合成视频。请安装: pip install opencv-python"
                )
            # 降级：只保存 JPEG 序列
            return self._save_jpeg_sequence(session, output_path)
        except Exception as e:
            if self.logger:
                self.logger.bind(tag=TAG).error(f"OpenCV 合成失败: {e}")
            return None
    
    def _save_jpeg_sequence(self, session: RecordingSession, 
                            output_path: Path) -> Optional[int]:
        """降级方案：保存 JPEG 序列（当 OpenCV 不可用时）
        
        Args:
            session: 录像会话
            output_path: 输出路径（会改为目录）
            
        Returns:
            总文件大小
        """
        try:
            # 创建序列目录
            seq_dir = output_path.parent / f"seq_{session.start_time}"
            seq_dir.mkdir(parents=True, exist_ok=True)
            
            total_size = 0
            for i, frame in enumerate(session.video_frames):
                frame_path = seq_dir / f"frame_{i:06d}.jpg"
                with open(frame_path, 'wb') as f:
                    f.write(frame.jpeg_data)
                total_size += len(frame.jpeg_data)
            
            if self.logger:
                self.logger.bind(tag=TAG).info(
                    f"保存 JPEG 序列: {seq_dir}, 帧数={len(session.video_frames)}"
                )
            
            return total_size
            
        except Exception as e:
            if self.logger:
                self.logger.bind(tag=TAG).error(f"保存 JPEG 序列失败: {e}")
            return None
    
    def is_recording(self, device_id: str) -> bool:
        """检查设备是否正在录制"""
        session = self._sessions.get(device_id)
        return session is not None and session.is_recording
    
    def get_recording_info(self, device_id: str) -> Optional[dict]:
        """获取录制信息"""
        session = self._sessions.get(device_id)
        if not session:
            return None
        
        return {
            "device_id": device_id,
            "start_time": session.start_time,
            "video_frames": len(session.video_frames),
            "audio_frames": len(session.audio_frames),
            "is_recording": session.is_recording
        }
    
    def shutdown(self):
        """关闭录像记录器"""
        # 停止所有录制
        for device_id in list(self._sessions.keys()):
            self.stop_recording(device_id)
        
        # 等待合成队列清空
        self._synthesis_queue.join()
        
        # 停止后台线程
        self._stop_synthesis.set()
        if self._synthesis_thread:
            self._synthesis_thread.join(timeout=5.0)
        
        if self.logger:
            self.logger.bind(tag=TAG).info("视频录像记录器已关闭")
