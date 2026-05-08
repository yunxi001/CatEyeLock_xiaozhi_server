import asyncio
from aiohttp import web
from config.logger import setup_logging
from core.api.ota_handler import OTAHandler
from core.api.vision_handler import VisionHandler
from core.handle.image_upload_handler import ImageUploadHandler
from core.api.doorlock_config_handler import DoorlockConfigHandler
from core.api.doorlock_guard_handler import DoorlockGuardHandler
from core.api.doorlock_welcome_handler import DoorlockWelcomeHandler
from core.api.doorlock_history_handler import DoorlockHistoryHandler
from core.api.doorlock_api_handler import DoorlockApiHandler
from core.api.doorlock_media_handler import DoorlockMediaHandler

TAG = __name__


class SimpleHttpServer:
    _instance = None  # 单例实例
    
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()
        self.ota_handler = OTAHandler(config)
        self.vision_handler = VisionHandler(config)
        self.image_upload_handler = ImageUploadHandler(config, self.logger)
        
        # 保存单例
        SimpleHttpServer._instance = self
        
        # 门锁AI功能API处理器
        self.doorlock_config_handler = DoorlockConfigHandler(config)
        self.doorlock_guard_handler = DoorlockGuardHandler(config)
        self.doorlock_welcome_handler = DoorlockWelcomeHandler(config)
        self.doorlock_history_handler = DoorlockHistoryHandler(config)
        self.doorlock_api_handler = DoorlockApiHandler(config)
        self.doorlock_media_handler = DoorlockMediaHandler(config)
    
    @classmethod
    def get_instance(cls):
        """获取HTTP服务器单例
        
        Returns:
            SimpleHttpServer实例，如果未初始化则返回None
        """
        return cls._instance

    def _get_websocket_url(self, local_ip: str, port: int) -> str:
        """获取websocket地址

        Args:
            local_ip: 本地IP地址
            port: 端口号

        Returns:
            str: websocket地址
        """
        server_config = self.config["server"]
        websocket_config = server_config.get("websocket")

        if websocket_config and "你" not in websocket_config:
            return websocket_config
        else:
            return f"ws://{local_ip}:{port}/xiaozhi/v1/"

    async def start(self):
        server_config = self.config["server"]
        read_config_from_api = self.config.get("read_config_from_api", False)
        host = server_config.get("ip", "0.0.0.0")
        port = int(server_config.get("http_port", 8003))

        if port:
            app = web.Application()

            if not read_config_from_api:
                # 如果没有开启智控台，只是单模块运行，就需要再添加简单OTA接口，用于下发websocket接口
                app.add_routes(
                    [
                        web.get("/xiaozhi/ota/", self.ota_handler.handle_get),
                        web.post("/xiaozhi/ota/", self.ota_handler.handle_post),
                        web.options("/xiaozhi/ota/", self.ota_handler.handle_post),
                    ]
                )
            # 添加路由
            app.add_routes(
                [
                    web.get("/mcp/vision/explain", self.vision_handler.handle_get),
                    web.post("/mcp/vision/explain", self.vision_handler.handle_post),
                    web.options("/mcp/vision/explain", self.vision_handler.handle_post),
                    # 图片上传接口
                    web.post("/api/doorlock/image/upload", self.image_upload_handler.handle_post),
                    web.options("/api/doorlock/image/upload", self.image_upload_handler.handle_options),
                    # 门锁配置API
                    web.get("/api/doorlock/config", self.doorlock_config_handler.handle_get),
                    web.post("/api/doorlock/config", self.doorlock_config_handler.handle_post),
                    web.options("/api/doorlock/config", self.doorlock_config_handler.handle_options),
                    # 看护模式控制API
                    web.post("/api/doorlock/package_guard/start", self.doorlock_guard_handler.handle_start),
                    web.post("/api/doorlock/package_guard/stop", self.doorlock_guard_handler.handle_stop),
                    web.options("/api/doorlock/package_guard/start", self.doorlock_guard_handler.handle_options),
                    web.options("/api/doorlock/package_guard/stop", self.doorlock_guard_handler.handle_options),
                    # 欢迎词配置API
                    web.get("/api/doorlock/welcome/config", self.doorlock_welcome_handler.handle_get_config),
                    web.post("/api/doorlock/welcome/config", self.doorlock_welcome_handler.handle_post_config),
                    web.get("/api/doorlock/welcome/templates", self.doorlock_welcome_handler.handle_get_templates),
                    web.options("/api/doorlock/welcome/config", self.doorlock_welcome_handler.handle_options),
                    web.options("/api/doorlock/welcome/templates", self.doorlock_welcome_handler.handle_options),
                    # 历史记录查询API
                    web.get("/api/doorlock/intents/history", self.doorlock_history_handler.handle_get_intents),
                    web.get("/api/doorlock/alerts/history", self.doorlock_history_handler.handle_get_alerts),
                    web.options("/api/doorlock/intents/history", self.doorlock_history_handler.handle_options),
                    web.options("/api/doorlock/alerts/history", self.doorlock_history_handler.handle_options),
                    # 门锁核心 API (v6.0 第一阶段)
                    web.get("/api/doorlock/status", self.doorlock_api_handler.handle_get_status),
                    web.options("/api/doorlock/status", self.doorlock_api_handler.handle_options),
                    web.get("/api/doorlock/faces", self.doorlock_api_handler.handle_get_faces),
                    web.post("/api/doorlock/faces", self.doorlock_api_handler.handle_post_faces),
                    web.delete("/api/doorlock/faces/{face_id}", self.doorlock_api_handler.handle_delete_face),
                    web.put("/api/doorlock/faces/{face_id}/permission", self.doorlock_api_handler.handle_update_permission),
                    web.options("/api/doorlock/faces", self.doorlock_api_handler.handle_options),
                    web.get("/api/doorlock/visits", self.doorlock_api_handler.handle_get_visits),
                    web.options("/api/doorlock/visits", self.doorlock_api_handler.handle_options),
                    # 门锁核心 API (v6.0 第二阶段) — 数据查询
                    web.get("/api/doorlock/events", self.doorlock_api_handler.handle_get_events),
                    web.options("/api/doorlock/events", self.doorlock_api_handler.handle_options),
                    web.get("/api/doorlock/unlock_logs", self.doorlock_api_handler.handle_get_unlock_logs),
                    web.options("/api/doorlock/unlock_logs", self.doorlock_api_handler.handle_options),
                    web.get("/api/doorlock/password", self.doorlock_api_handler.handle_get_password),
                    web.options("/api/doorlock/password", self.doorlock_api_handler.handle_options),
                    # 门锁核心 API (v6.0 第二阶段) — 媒体文件下载
                    web.get("/api/doorlock/media", self.doorlock_media_handler.handle_get_list),
                    web.options("/api/doorlock/media", self.doorlock_media_handler.handle_options),
                    web.get("/api/doorlock/media/{file_id}", self.doorlock_media_handler.handle_download),
                    web.get("/api/doorlock/media/download", self.doorlock_media_handler.handle_download_by_path),
                ]
            )

            # 运行服务
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host, port)
            await site.start()

            # 保持服务运行
            while True:
                await asyncio.sleep(3600)  # 每隔 1 小时检查一次
