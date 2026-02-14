"""
ESP32摄像头服务

通过MCP协议调用ESP32的拍照功能
"""
import json
import base64
import asyncio
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger

TAG = "ESP32Camera"


class ESP32CameraService:
    """ESP32摄像头服务（基于MCP协议）"""
    
    def __init__(self, config: dict, logger_instance=None):
        """初始化摄像头服务
        
        Args:
            config: 配置字典
            logger_instance: 日志实例
        """
        self.logger = logger_instance or logger
        self.config = config
        
        # 待处理的拍照请求 {device_id: Future}
        self.pending_captures = {}
        
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
        
        self.logger.bind(tag=TAG).info("ESP32摄像头服务初始化完成（MCP模式）")
    
    async def capture_image(
        self,
        device_id: str,
        conn,
        question: str = "拍照",
        timeout: int = 10
    ) -> Optional[bytes]:
        """拍摄照片（通过MCP协议）
        
        Args:
            device_id: 设备ID
            conn: 连接对象（必须有mcp_client）
            question: 拍照问题描述
            timeout: 超时时间（秒）
            
        Returns:
            JPEG图片数据，失败返回None
        """
        try:
            # 检查MCP客户端
            if not hasattr(conn, 'mcp_client') or not conn.mcp_client:
                self.logger.bind(tag=TAG).error(
                    f"设备 {device_id} 未初始化MCP客户端"
                )
                return None
            
            if not await conn.mcp_client.is_ready():
                self.logger.bind(tag=TAG).error(
                    f"设备 {device_id} MCP客户端未就绪"
                )
                return None
            
            # 检查是否有capture_image工具
            if not conn.mcp_client.has_tool('capture_image'):
                self.logger.bind(tag=TAG).error(
                    f"设备 {device_id} 不支持capture_image工具"
                )
                return None
            
            self.logger.bind(tag=TAG).info(
                f"开始拍照 - 设备: {device_id}, 问题: {question}"
            )
            
            # 1. 创建Future对象等待照片上传
            future = asyncio.Future()
            self.pending_captures[device_id] = future
            
            # 2. 注册图片上传回调
            from core.http_server import SimpleHttpServer
            http_server = SimpleHttpServer.get_instance()
            
            if not http_server:
                self.logger.bind(tag=TAG).error(
                    f"无法获取HTTP服务器实例 - 设备: {device_id}"
                )
                self.pending_captures.pop(device_id, None)
                return None
            
            async def upload_callback(dev_id, image_data, ts, w, h):
                """图片上传回调"""
                if dev_id == device_id and dev_id in self.pending_captures:
                    self.logger.bind(tag=TAG).info(
                        f"收到拍照结果 - 设备: {dev_id}, "
                        f"大小: {len(image_data)} bytes, 尺寸: {w}x{h}"
                    )
                    if not self.pending_captures[dev_id].done():
                        self.pending_captures[dev_id].set_result(image_data)
            
            http_server.image_upload_handler.register_callback(
                device_id, upload_callback
            )
            
            # 3. 通过MCP调用capture_image工具
            from core.providers.tools.device_mcp import call_mcp_tool
            
            try:
                # 调用MCP工具（这会发送拍照请求给ESP32）
                # 注意：call_mcp_tool返回的是文本结果，不是照片
                mcp_result = await call_mcp_tool(
                    conn=conn,
                    mcp_client=conn.mcp_client,
                    tool_name='capture_image',
                    args=json.dumps({"question": question}),
                    timeout=timeout
                )
                
                self.logger.bind(tag=TAG).debug(
                    f"MCP拍照请求已发送 - 设备: {device_id}, "
                    f"MCP返回: {mcp_result}"
                )
                
            except Exception as e:
                self.logger.bind(tag=TAG).error(
                    f"MCP拍照请求失败 - 设备: {device_id}, 错误: {e}"
                )
                # 清理并返回
                self.pending_captures.pop(device_id, None)
                http_server.image_upload_handler.unregister_callback(device_id)
                return None
            
            # 4. 等待照片上传（带超时）
            try:
                jpeg_data = await asyncio.wait_for(future, timeout=timeout)
                
                self.logger.bind(tag=TAG).info(
                    f"拍照成功 - 设备: {device_id}, "
                    f"大小: {len(jpeg_data)} bytes"
                )
                
                return jpeg_data
                
            except asyncio.TimeoutError:
                self.logger.bind(tag=TAG).error(
                    f"等待照片上传超时 - 设备: {device_id}, "
                    f"超时时间: {timeout}秒"
                )
                return None
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(
                f"拍照失败 - 设备: {device_id}, 错误: {e}"
            )
            import traceback
            self.logger.bind(tag=TAG).error(traceback.format_exc())
            return None
            
        finally:
            # 5. 清理资源
            self.pending_captures.pop(device_id, None)
            from core.http_server import SimpleHttpServer
            http_server = SimpleHttpServer.get_instance()
            if http_server:
                http_server.image_upload_handler.unregister_callback(device_id)
    
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
