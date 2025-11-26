import json
from aiohttp import web
from config.logger import setup_logging

TAG = __name__


class ModeControlAPI:
    """模式控制API处理器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()
        
    async def handle_mode_status(self, request):
        """获取模式状态"""
        try:
            # 这里需要获取当前连接的模式状态
            # 由于模式状态是与特定WebSocket连接相关的，
            # 这个API可能需要从全局连接管理器获取信息
            # 或者返回服务器级别的配置信息
            
            response_data = {
                "enabled": self.config.get("audio_video_stream", {}).get("enabled", False),
                "max_switch_frequency": self.config.get("audio_video_stream", {}).get("max_switch_frequency", 5),
                "enable_audio_forwarding": self.config.get("audio_video_stream", {}).get("enable_audio_forwarding", False),
                "enable_video_forwarding": self.config.get("audio_video_stream", {}).get("enable_video_forwarding", False),
                "status": "running"
            }
            
            return web.json_response(response_data)
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"获取模式状态失败: {str(e)}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def handle_mode_switch(self, request):
        """处理模式切换请求（运行时控制）"""
        try:
            if request.method == 'POST':
                data = await request.json()
                mode = data.get('mode')
                
                if not mode or mode not in ['control', 'media']:
                    return web.json_response({
                        "success": False,
                        "error": "Invalid mode. Use 'control' or 'media'"
                    }, status=400)
                
                # 这里的模式切换需要通过WebSocket连接进行
                # 实际上，模式切换应该由ESP32设备通过WebSocket发起
                # HTTP API可以用来控制全局配置或触发某些操作
                
                # 对于特定设备的模式切换，需要知道设备ID和WebSocket连接
                device_id = data.get('device_id')
                
                if not device_id:
                    return web.json_response({
                        "success": False,
                        "error": "Device ID is required for mode switching"
                    }, status=400)
                
                # 发送模式切换指令给特定设备
                # 这需要连接管理器来处理
                # 目前我们只是提供一个响应
                response_data = {
                    "success": True,
                    "message": f"Mode switch request for {device_id} to {mode} mode has been received",
                    "target_mode": mode,
                    "device_id": device_id
                }
                
                return web.json_response(response_data)
            
            elif request.method == 'GET':
                # 返回当前模式切换配置
                return await self.handle_mode_status(request)
                
        except json.JSONDecodeError:
            return web.json_response({
                "success": False,
                "error": "Invalid JSON in request body"
            }, status=400)
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"处理模式切换请求失败: {str(e)}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def handle_global_config(self, request):
        """处理全局配置控制"""
        try:
            if request.method == 'GET':
                # 返回当前全局配置
                av_config = self.config.get("audio_video_stream", {})
                response_data = {
                    "audio_video_stream": av_config
                }
                return web.json_response(response_data)
                
            elif request.method == 'POST':
                # 更新全局配置
                data = await request.json()
                
                # 验证和更新配置
                updated_config = {}
                
                if 'enabled' in data:
                    updated_config['enabled'] = bool(data['enabled'])
                
                if 'max_switch_frequency' in data:
                    updated_config['max_switch_frequency'] = int(data['max_switch_frequency'])
                
                if 'enable_audio_forwarding' in data:
                    updated_config['enable_audio_forwarding'] = bool(data['enable_audio_forwarding'])
                
                if 'enable_video_forwarding' in data:
                    updated_config['enable_video_forwarding'] = bool(data['enable_video_forwarding'])
                
                # 更新配置
                if 'audio_video_stream' not in self.config:
                    self.config['audio_video_stream'] = {}
                
                self.config['audio_video_stream'].update(updated_config)
                
                response_data = {
                    "success": True,
                    "message": "Global configuration updated",
                    "updated_config": updated_config
                }
                
                return web.json_response(response_data)
                
        except json.JSONDecodeError:
            return web.json_response({
                "success": False,
                "error": "Invalid JSON in request body"
            }, status=400)
        except ValueError as e:
            return web.json_response({
                "success": False,
                "error": f"Invalid value: {str(e)}"
            }, status=400)
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"处理全局配置失败: {str(e)}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)