"""
媒体文件存储服务

负责人脸图片和监控录像的本地存储管理
"""
import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

TAG = __name__


class MediaStorage:
    """媒体文件存储管理器"""
    
    def __init__(self, base_path: str = "data/media", logger=None):
        """初始化存储管理器
        
        Args:
            base_path: 媒体文件根目录
            logger: 日志记录器
        """
        self.base_path = Path(base_path)
        self.logger = logger
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """确保目录结构存在"""
        (self.base_path / "faces").mkdir(parents=True, exist_ok=True)
        (self.base_path / "recordings").mkdir(parents=True, exist_ok=True)
    
    def _get_date_dir(self, device_id: str, file_type: str) -> Path:
        """获取按日期分类的目录路径"""
        today = datetime.now().strftime("%Y-%m-%d")
        if file_type == "face":
            dir_path = self.base_path / "faces" / device_id / today
        else:
            dir_path = self.base_path / "recordings" / device_id / today
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path
    
    async def save_face_image(self, device_id: str, image_data: bytes,
                               user_id: int = None, timestamp: int = None) -> str:
        """保存人脸识别图片
        
        Args:
            device_id: 设备 ID
            image_data: JPEG 图片数据
            user_id: 识别到的用户 ID（可选）
            timestamp: 时间戳（可选，默认当前时间）
            
        Returns:
            保存的文件相对路径
        """
        ts = timestamp or int(datetime.now().timestamp() * 1000)
        dir_path = self._get_date_dir(device_id, "face")
        
        # 文件名格式: face_{timestamp}_{user_id}.jpg
        if user_id:
            filename = f"face_{ts}_{user_id}.jpg"
        else:
            filename = f"face_{ts}.jpg"
        
        file_path = dir_path / filename
        
        # 异步写入文件
        await asyncio.to_thread(self._write_file, file_path, image_data)
        
        # 返回相对路径
        relative_path = str(file_path.relative_to(self.base_path))
        
        if self.logger:
            self.logger.bind(tag=TAG).debug(f"保存人脸图片: {relative_path}")
        
        return relative_path
    
    async def save_recording(self, device_id: str, video_data: bytes,
                              duration: int = None, timestamp: int = None) -> str:
        """保存监控录像
        
        Args:
            device_id: 设备 ID
            video_data: 视频数据（MP4 格式）
            duration: 录像时长（秒）
            timestamp: 时间戳（可选，默认当前时间）
            
        Returns:
            保存的文件相对路径
        """
        ts = timestamp or int(datetime.now().timestamp() * 1000)
        dir_path = self._get_date_dir(device_id, "recording")
        
        filename = f"rec_{ts}.mp4"
        file_path = dir_path / filename
        
        # 异步写入文件
        await asyncio.to_thread(self._write_file, file_path, video_data)
        
        relative_path = str(file_path.relative_to(self.base_path))
        
        if self.logger:
            self.logger.bind(tag=TAG).info(
                f"保存监控录像: {relative_path}, 时长: {duration}秒"
            )
        
        return relative_path
    
    def _write_file(self, file_path: Path, data: bytes):
        """同步写入文件（在线程池中执行）"""
        with open(file_path, 'wb') as f:
            f.write(data)
    
    def get_full_path(self, relative_path: str) -> Path:
        """获取文件的完整路径"""
        return self.base_path / relative_path
    
    async def delete_file(self, relative_path: str) -> bool:
        """删除文件
        
        Args:
            relative_path: 文件相对路径
            
        Returns:
            是否删除成功
        """
        try:
            file_path = self.base_path / relative_path
            if file_path.exists():
                await asyncio.to_thread(os.remove, file_path)
                if self.logger:
                    self.logger.bind(tag=TAG).debug(f"删除文件: {relative_path}")
                return True
            return False
        except Exception as e:
            if self.logger:
                self.logger.bind(tag=TAG).error(f"删除文件失败: {e}")
            return False
    
    async def cleanup_old_files(self, file_paths: list) -> int:
        """批量删除过期文件
        
        Args:
            file_paths: 要删除的文件相对路径列表
            
        Returns:
            成功删除的文件数
        """
        deleted = 0
        for path in file_paths:
            if await self.delete_file(path):
                deleted += 1
        
        if self.logger:
            self.logger.bind(tag=TAG).info(f"清理过期文件: {deleted}/{len(file_paths)}")
        
        return deleted
    
    def get_file_size(self, relative_path: str) -> Optional[int]:
        """获取文件大小（字节）"""
        try:
            file_path = self.base_path / relative_path
            if file_path.exists():
                return file_path.stat().st_size
            return None
        except Exception:
            return None
