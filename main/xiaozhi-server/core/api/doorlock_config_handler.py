"""门锁配置API处理器

提供设备配置的查询和更新接口
"""
from aiohttp import web
from loguru import logger
from core.providers.doorlock.doorlock_database import DoorlockDatabase


class DoorlockConfigHandler:
    """门锁配置API处理器"""

    def __init__(self, config: dict):
        """初始化处理器
        
        Args:
            config: 系统配置字典
        """
        self.config = config
        self.db = DoorlockDatabase(config)

    async def handle_get(self, request: web.Request) -> web.Response:
        """处理GET请求 - 获取设备配置
        
        GET /api/doorlock/config?device_id={device_id}
        
        Args:
            request: HTTP请求对象
            
        Returns:
            JSON响应，包含设备配置信息
        """
        try:
            # 获取并验证device_id参数
            device_id = request.query.get("device_id")
            if not device_id:
                return web.json_response(
                    {
                        "success": False,
                        "message": "缺少必填参数: device_id"
                    },
                    status=400
                )

            # 查询设备配置
            config = await self.db.get_config(device_id)
            
            if config is None:
                return web.json_response(
                    {
                        "success": False,
                        "message": f"设备配置不存在: {device_id}"
                    },
                    status=404
                )

            # 返回配置信息
            return web.json_response(
                {
                    "success": True,
                    "data": {
                        "device_id": config.device_id,
                        "intent_recognition_enabled": config.intent_recognition_enabled,
                        "package_guard_available": config.package_guard_available,
                        "package_guard_active": config.package_guard_active,
                        "package_baseline_image": config.package_baseline_image,
                        "package_guard_start_time": config.package_guard_start_time.isoformat() if config.package_guard_start_time else None
                    }
                },
                status=200
            )

        except Exception as e:
            logger.error(f"获取设备配置失败: {e}")
            return web.json_response(
                {
                    "success": False,
                    "message": f"服务器内部错误: {str(e)}"
                },
                status=500
            )

    async def handle_post(self, request: web.Request) -> web.Response:
        """处理POST请求 - 更新设备配置
        
        POST /api/doorlock/config
        请求体: {
            "device_id": "device001",
            "intent_recognition_enabled": true,
            "package_guard_available": true
        }
        
        Args:
            request: HTTP请求对象
            
        Returns:
            JSON响应，包含更新结果
        """
        try:
            # 解析请求体
            data = await request.json()
            
            # 验证必填参数
            device_id = data.get("device_id")
            if not device_id:
                return web.json_response(
                    {
                        "success": False,
                        "message": "缺少必填参数: device_id"
                    },
                    status=400
                )

            # 获取现有配置
            config = await self.db.get_config(device_id)
            if config is None:
                return web.json_response(
                    {
                        "success": False,
                        "message": f"设备配置不存在: {device_id}"
                    },
                    status=404
                )

            # 更新配置字段
            if "intent_recognition_enabled" in data:
                if not isinstance(data["intent_recognition_enabled"], bool):
                    return web.json_response(
                        {
                            "success": False,
                            "message": "参数类型错误: intent_recognition_enabled 必须是布尔值"
                        },
                        status=400
                    )
                config.intent_recognition_enabled = data["intent_recognition_enabled"]

            if "package_guard_available" in data:
                if not isinstance(data["package_guard_available"], bool):
                    return web.json_response(
                        {
                            "success": False,
                            "message": "参数类型错误: package_guard_available 必须是布尔值"
                        },
                        status=400
                    )
                config.package_guard_available = data["package_guard_available"]

            # 保存更新
            success = await self.db.update_config(config)
            
            if success:
                logger.info(f"设备配置更新成功: {device_id}")
                return web.json_response(
                    {
                        "success": True,
                        "message": "配置更新成功"
                    },
                    status=200
                )
            else:
                return web.json_response(
                    {
                        "success": False,
                        "message": "配置更新失败"
                    },
                    status=500
                )

        except ValueError as e:
            return web.json_response(
                {
                    "success": False,
                    "message": f"请求体格式错误: {str(e)}"
                },
                status=400
            )
        except Exception as e:
            logger.error(f"更新设备配置失败: {e}")
            return web.json_response(
                {
                    "success": False,
                    "message": f"服务器内部错误: {str(e)}"
                },
                status=500
            )

    async def handle_options(self, request: web.Request) -> web.Response:
        """处理OPTIONS请求 - CORS预检
        
        Args:
            request: HTTP请求对象
            
        Returns:
            空响应，包含CORS头
        """
        return web.Response(
            status=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
