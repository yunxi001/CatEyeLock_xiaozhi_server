"""门锁看护模式控制API处理器

提供看护模式的启动和停止接口
"""
from aiohttp import web
from loguru import logger
from pathlib import Path
from ruamel.yaml import YAML

from core.providers.doorlock.package_guard_manager import PackageGuardManager
from core.providers.doorlock.doorlock_database import DoorlockDatabase
from core.providers.doorlock.notification_service import NotificationService
from core.providers.vllm.doorlock_vllm import DoorlockVLLMProvider


class DoorlockGuardHandler:
    """门锁看护模式控制API处理器"""

    def __init__(self, config: dict):
        """初始化处理器（在系统配置加载完成后调用）
        
        Args:
            config: 系统配置字典（已从 manage-api 或本地加载完成）
        
        说明：
            - 此类在 HTTP 服务器初始化时创建
            - 系统配置已完全加载，可以安全使用
            - 门锁配置在延迟初始化时加载，不影响系统启动
        """
        self.config = config
        
        # 初始化数据库服务（使用门锁独立配置）
        self.db = DoorlockDatabase(config)
        
        # 延迟初始化标志
        self._guard_manager = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """确保看护管理器已初始化（延迟初始化，首次 API 调用时触发）
        
        说明：
            - 延迟初始化避免影响系统启动速度
            - VLLM 提供者复用系统已加载的配置
            - 门锁业务配置从独立文件加载
        """
        if self._initialized:
            return
        
        try:
            # 初始化通知服务
            notification_service = NotificationService()
            
            # 初始化VLLM提供者（复用系统已加载的配置）
            vllm_provider = DoorlockVLLMProvider(self.config, logger)
            
            # 初始化TTS提供者（暂时为None，后续集成）
            tts_provider = None
            
            # 加载门锁独立配置（仅用于业务配置）
            doorlock_config = self._load_doorlock_config()
            
            # 提取看护模式配置
            guard_config = doorlock_config.get("package_guard", {})
            
            # 初始化看护模式管理器
            self._guard_manager = PackageGuardManager(
                db=self.db,
                vllm_provider=vllm_provider,
                tts_provider=tts_provider,
                notification_service=notification_service,
                config=guard_config
            )
            
            self._initialized = True
            logger.info("门锁看护管理器延迟初始化成功（复用系统 VLLM 配置）")
            
        except Exception as e:
            logger.error(f"门锁看护管理器初始化失败: {e}")
            raise
    
    def _load_doorlock_config(self) -> dict:
        """加载门锁独立配置（仅用于业务配置）
        
        Returns:
            门锁配置字典，加载失败返回空字典
        """
        try:
            doorlock_config_path = Path(__file__).parent.parent.parent / "config" / "doorlock_config.yaml"
            if not doorlock_config_path.exists():
                logger.warning("门锁配置文件不存在，使用默认配置")
                return {}
            
            from ruamel.yaml import YAML
            yaml = YAML()
            with open(doorlock_config_path, 'r', encoding='utf-8') as f:
                config = yaml.load(f)
            
            logger.debug("门锁业务配置加载成功")
            return config
        except Exception as e:
            logger.error(f"加载门锁配置失败: {e}，使用默认配置")
            return {}
    
    @property
    def guard_manager(self):
        """获取看护管理器（自动触发延迟初始化）"""
        self._ensure_initialized()
        return self._guard_manager

    async def handle_start(self, request: web.Request) -> web.Response:
        """处理启动看护模式请求
        
        POST /api/doorlock/package_guard/start
        请求体: {
            "device_id": "device001",
            "reason": "手动启动看护"
        }
        
        Args:
            request: HTTP请求对象
            
        Returns:
            JSON响应，包含启动结果
        """
        try:
            # 解析请求体
            data = await request.json()
            
            # 验证必填参数
            device_id = data.get("device_id")
            reason = data.get("reason")
            
            if not device_id:
                return web.json_response(
                    {
                        "success": False,
                        "message": "缺少必填参数: device_id"
                    },
                    status=400
                )
            
            if not reason:
                return web.json_response(
                    {
                        "success": False,
                        "message": "缺少必填参数: reason"
                    },
                    status=400
                )

            # 检查设备配置
            config = await self.db.get_config(device_id)
            if config is None:
                return web.json_response(
                    {
                        "success": False,
                        "message": f"设备配置不存在: {device_id}"
                    },
                    status=404
                )

            # 验证 package_guard_available 开关
            if not config.package_guard_available:
                return web.json_response(
                    {
                        "success": False,
                        "message": "看护模式功能未启用，请先在设备配置中启用"
                    },
                    status=400
                )

            # 启动看护模式
            success = await self.guard_manager.enable_guard(device_id, reason)
            
            if success:
                logger.info(f"看护模式启动成功: {device_id}, 原因: {reason}")
                return web.json_response(
                    {
                        "success": True,
                        "message": "看护模式已启动"
                    },
                    status=200
                )
            else:
                return web.json_response(
                    {
                        "success": False,
                        "message": "看护模式启动失败"
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
            logger.error(f"启动看护模式失败: {e}")
            return web.json_response(
                {
                    "success": False,
                    "message": f"服务器内部错误: {str(e)}"
                },
                status=500
            )

    async def handle_stop(self, request: web.Request) -> web.Response:
        """处理停止看护模式请求
        
        POST /api/doorlock/package_guard/stop
        请求体: {
            "device_id": "device001",
            "reason": "手动停止看护"
        }
        
        Args:
            request: HTTP请求对象
            
        Returns:
            JSON响应，包含停止结果
        """
        try:
            # 解析请求体
            data = await request.json()
            
            # 验证必填参数
            device_id = data.get("device_id")
            reason = data.get("reason")
            
            if not device_id:
                return web.json_response(
                    {
                        "success": False,
                        "message": "缺少必填参数: device_id"
                    },
                    status=400
                )
            
            if not reason:
                return web.json_response(
                    {
                        "success": False,
                        "message": "缺少必填参数: reason"
                    },
                    status=400
                )

            # 检查设备配置
            config = await self.db.get_config(device_id)
            if config is None:
                return web.json_response(
                    {
                        "success": False,
                        "message": f"设备配置不存在: {device_id}"
                    },
                    status=404
                )

            # 停止看护模式
            success = await self.guard_manager.disable_guard(device_id, reason)
            
            if success:
                logger.info(f"看护模式停止成功: {device_id}, 原因: {reason}")
                return web.json_response(
                    {
                        "success": True,
                        "message": "看护模式已停止"
                    },
                    status=200
                )
            else:
                return web.json_response(
                    {
                        "success": False,
                        "message": "看护模式停止失败"
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
            logger.error(f"停止看护模式失败: {e}")
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
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
