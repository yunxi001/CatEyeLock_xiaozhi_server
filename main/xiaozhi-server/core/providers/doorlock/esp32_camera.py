"""
ESP32摄像头服务

通过MCP协议调用ESP32的拍照功能
"""
import json
import base64
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger

TAG = "ESP32Camera"


class ESP32CameraService:
    """ESP32摄像头服务"""
    
    def __init__(self, config: dict, logger_instance=None):
        """初始化摄像头服务
        
        Args:
            config: 配置字典
            logger_instance: 日志实例
        """
        self.logger = logger_instance or logger
        self.config = config
        
        # 图片保存路径配置
        doorlock_config = config.get('doorlock', {})
        package_guard_config = doorlock_config.get('package_guard', {})
        
        self.baseline_dir = Path(package_guard_config.get(
            'baseline_dir',
            'data/face_recognition/package_baseline/'
        ))
        self.visits_dir = Path('data/visits/')
        
        # 确保目录存在
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.visits_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.bind(tag=TAG).info(
            f"ESP32摄像头服务初始化完成: baseline_dir={self.baseline_dir}"
        )
    
    async def capture_image(
        self,
        device_id: str,
        question: str = "拍照",
        conn=None
    ) -> Optional[Dict[str, Any]]:
        """拍摄照片
        
        Args:
            device_id: 设备ID
            question: 拍照问题描述
            conn: 连接对象（用于MCP调用）
            
        Returns:
            拍照结果字典:
            {
                "success": True/False,
                "image_data": bytes,  # JPEG数据
                "timestamp": int,     # 时间戳（毫秒）
                "width": int,         # 图片宽度
                "height": int         # 图片高度
            }
        """
        try:
            self.logger.bind(tag=TAG).info(
                f"开始拍照 - 设备: {device_id}, 问题: {question}"
            )
            
            # TODO: 通过MCP协议调用ESP32的capture_image工具
            # 这里需要集成MCP客户端
            # 暂时返回模拟结果
            
            # 如果有conn对象，尝试通过WebSocket发送拍照请求
            if conn and hasattr(conn, 'websocket'):
                # 发送拍照请求
                request = {
                    "type": "capture_request",
                    "question": question,
                    "ts": int(datetime.now().timestamp() * 1000)
                }
                
                await conn.websocket.send(json.dumps(request))
                
                self.logger.bind(tag=TAG).info(
                    f"已发送拍照请求 - 设备: {device_id}"
                )
                
                # 等待ESP32上传图片（通过HTTP POST）
                # 这里需要配合HTTP服务器的图片上传接口
                # 暂时返回None，表示需要等待异步上传
                return None
            
            self.logger.bind(tag=TAG).warning(
                f"无法发送拍照请求 - 设备: {device_id}, conn不可用"
            )
            
            return {
                "success": False,
                "error": "连接不可用"
            }
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"拍照失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def save_baseline_image(
        self,
        device_id: str,
        image_data: bytes,
        timestamp: Optional[int] = None
    ) -> str:
        """保存基准图片
        
        Args:
            device_id: 设备ID
            image_data: 图片数据（JPEG）
            timestamp: 时间戳（毫秒），如果不提供则使用当前时间
            
        Returns:
            图片保存路径
        """
        try:
            if timestamp is None:
                timestamp = int(datetime.now().timestamp() * 1000)
            
            # 使用命名规则: device_{device_id}_baseline_{timestamp}.jpg
            filename = f"device_{device_id}_baseline_{timestamp}.jpg"
            filepath = self.baseline_dir / filename
            
            # 保存图片
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            self.logger.bind(tag=TAG).info(
                f"基准图片已保存 - 设备: {device_id}, 路径: {filepath}"
            )
            
            return str(filepath)
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"保存基准图片失败: {e}")
            raise
    
    async def save_visit_image(
        self,
        device_id: str,
        image_data: bytes,
        visit_id: Optional[int] = None,
        timestamp: Optional[int] = None
    ) -> str:
        """保存访客图片
        
        Args:
            device_id: 设备ID
            image_data: 图片数据（JPEG）
            visit_id: 访问记录ID
            timestamp: 时间戳（毫秒）
            
        Returns:
            图片保存路径
        """
        try:
            if timestamp is None:
                timestamp = int(datetime.now().timestamp() * 1000)
            
            # 按日期组织目录
            date_str = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m')
            date_dir = self.visits_dir / date_str
            date_dir.mkdir(parents=True, exist_ok=True)
            
            # 使用命名规则: visit_{visit_id}_{timestamp}.jpg
            if visit_id:
                filename = f"visit_{visit_id}_{timestamp}.jpg"
            else:
                filename = f"device_{device_id}_{timestamp}.jpg"
            
            filepath = date_dir / filename
            
            # 保存图片
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            self.logger.bind(tag=TAG).info(
                f"访客图片已保存 - 设备: {device_id}, 路径: {filepath}"
            )
            
            return str(filepath)
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"保存访客图片失败: {e}")
            raise
    
    async def save_alert_image(
        self,
        device_id: str,
        image_data: bytes,
        alert_id: Optional[int] = None,
        timestamp: Optional[int] = None
    ) -> str:
        """保存警报图片
        
        Args:
            device_id: 设备ID
            image_data: 图片数据（JPEG）
            alert_id: 警报ID
            timestamp: 时间戳（毫秒）
            
        Returns:
            图片保存路径
        """
        try:
            if timestamp is None:
                timestamp = int(datetime.now().timestamp() * 1000)
            
            # 按日期组织目录
            date_str = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m')
            date_dir = self.visits_dir / date_str
            date_dir.mkdir(parents=True, exist_ok=True)
            
            # 使用命名规则: alert_{alert_id}_{timestamp}.jpg
            if alert_id:
                filename = f"alert_{alert_id}_{timestamp}.jpg"
            else:
                filename = f"device_{device_id}_alert_{timestamp}.jpg"
            
            filepath = date_dir / filename
            
            # 保存图片
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            self.logger.bind(tag=TAG).info(
                f"警报图片已保存 - 设备: {device_id}, 路径: {filepath}"
            )
            
            return str(filepath)
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"保存警报图片失败: {e}")
            raise
    
    def load_baseline_image(
        self,
        device_id: str
    ) -> Optional[bytes]:
        """加载最新的基准图片
        
        Args:
            device_id: 设备ID
            
        Returns:
            图片数据（JPEG），如果不存在返回None
        """
        try:
            # 查找该设备的所有基准图片
            pattern = f"device_{device_id}_baseline_*.jpg"
            baseline_files = list(self.baseline_dir.glob(pattern))
            
            if not baseline_files:
                self.logger.bind(tag=TAG).warning(
                    f"未找到基准图片 - 设备: {device_id}"
                )
                return None
            
            # 按时间戳排序，获取最新的
            latest_file = max(baseline_files, key=lambda p: p.stat().st_mtime)
            
            # 读取图片
            with open(latest_file, 'rb') as f:
                image_data = f.read()
            
            self.logger.bind(tag=TAG).info(
                f"加载基准图片 - 设备: {device_id}, 路径: {latest_file}"
            )
            
            return image_data
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"加载基准图片失败: {e}")
            return None
