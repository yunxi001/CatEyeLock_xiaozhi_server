"""
图片上传处理器

处理ESP32上传的图片数据
"""
import json
from aiohttp import web
from typing import Dict, Any
from loguru import logger

TAG = "ImageUploadHandler"


class ImageUploadHandler:
    """图片上传处理器"""
    
    def __init__(self, config: dict, logger_instance=None):
        """初始化处理器
        
        Args:
            config: 配置字典
            logger_instance: 日志实例
        """
        self.config = config
        self.logger = logger_instance or logger
        
        # 图片上传回调（由外部设置）
        self.upload_callbacks = {}
        
        self.logger.bind(tag=TAG).info("图片上传处理器初始化完成")
    
    def register_callback(self, device_id: str, callback):
        """注册图片上传回调
        
        Args:
            device_id: 设备ID
            callback: 回调函数，接收 (device_id, image_data, timestamp, width, height)
        """
        self.upload_callbacks[device_id] = callback
        self.logger.bind(tag=TAG).debug(f"注册图片上传回调 - 设备: {device_id}")
    
    def unregister_callback(self, device_id: str):
        """注销图片上传回调
        
        Args:
            device_id: 设备ID
        """
        if device_id in self.upload_callbacks:
            del self.upload_callbacks[device_id]
            self.logger.bind(tag=TAG).debug(f"注销图片上传回调 - 设备: {device_id}")
    
    async def handle_post(self, request: web.Request) -> web.Response:
        """处理POST请求（图片上传）
        
        请求格式:
        - Content-Type: multipart/form-data 或 application/octet-stream
        - Headers:
            - device-id: 设备ID
            - timestamp: 时间戳（毫秒）
            - width: 图片宽度（可选）
            - height: 图片高度（可选）
        - Body: JPEG图片数据
        
        响应格式:
        {
            "success": true/false,
            "message": "消息"
        }
        """
        try:
            # 获取设备ID
            device_id = request.headers.get('device-id')
            if not device_id:
                return web.json_response({
                    "success": False,
                    "message": "缺少device-id头部"
                }, status=400)
            
            # 获取时间戳
            timestamp_str = request.headers.get('timestamp')
            if timestamp_str:
                timestamp = int(timestamp_str)
            else:
                import time
                timestamp = int(time.time() * 1000)
            
            # 获取图片尺寸
            width = int(request.headers.get('width', 640))
            height = int(request.headers.get('height', 480))
            
            # 读取图片数据
            image_data = await request.read()
            
            if not image_data:
                return web.json_response({
                    "success": False,
                    "message": "图片数据为空"
                }, status=400)
            
            self.logger.bind(tag=TAG).info(
                f"收到图片上传 - 设备: {device_id}, 大小: {len(image_data)} bytes, "
                f"尺寸: {width}x{height}, 时间戳: {timestamp}"
            )
            
            # 调用回调函数
            if device_id in self.upload_callbacks:
                callback = self.upload_callbacks[device_id]
                try:
                    await callback(device_id, image_data, timestamp, width, height)
                except Exception as e:
                    self.logger.bind(tag=TAG).error(
                        f"图片上传回调执行失败: {e}"
                    )
            else:
                self.logger.bind(tag=TAG).warning(
                    f"未找到图片上传回调 - 设备: {device_id}"
                )
            
            return web.json_response({
                "success": True,
                "message": "图片上传成功"
            })
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"处理图片上传失败: {e}")
            return web.json_response({
                "success": False,
                "message": f"处理失败: {str(e)}"
            }, status=500)
    
    async def handle_options(self, request: web.Request) -> web.Response:
        """处理OPTIONS请求（CORS预检）"""
        return web.Response(
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'device-id, timestamp, width, height, Content-Type'
            }
        )
