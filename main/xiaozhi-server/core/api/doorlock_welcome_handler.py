"""门锁欢迎词配置API处理器

提供欢迎词的配置、查询和模板获取接口
"""
import json
from aiohttp import web
from loguru import logger
from core.providers.doorlock.doorlock_database import DoorlockDatabase
from ruamel.yaml import YAML


class DoorlockWelcomeHandler:
    """门锁欢迎词配置API处理器"""

    def __init__(self, config: dict):
        """初始化处理器
        
        Args:
            config: 系统配置字典
        """
        self.config = config
        self.db = DoorlockDatabase(config)
        self.yaml = YAML()

    def _validate_greeting_format(self, greeting: dict) -> tuple[bool, str]:
        """验证欢迎词格式
        
        Args:
            greeting: 欢迎词配置字典
            
        Returns:
            (是否有效, 错误信息)
        """
        if not isinstance(greeting, dict):
            return False, "欢迎词配置必须是字典格式"
        
        # 允许的时段键
        valid_keys = {"morning", "afternoon", "evening", "night", "default"}
        
        # 检查是否有无效的键
        invalid_keys = set(greeting.keys()) - valid_keys
        if invalid_keys:
            return False, f"包含无效的时段键: {', '.join(invalid_keys)}"
        
        # 检查所有值是否为字符串
        for key, value in greeting.items():
            if not isinstance(value, str):
                return False, f"时段 {key} 的欢迎词必须是字符串"
        
        return True, ""

    async def handle_post_config(self, request: web.Request) -> web.Response:
        """处理配置欢迎词请求
        
        POST /api/doorlock/welcome/config
        请求体: {
            "person_id": 5,
            "custom_greeting": {
                "morning": "早上好，张三",
                "afternoon": "下午好，张三",
                "evening": "晚上好，张三",
                "night": "夜深了，张三",
                "default": "欢迎回家"
            }
        }
        
        Args:
            request: HTTP请求对象
            
        Returns:
            JSON响应，包含配置结果
        """
        try:
            # 解析请求体
            data = await request.json()
            
            # 验证必填参数
            person_id = data.get("person_id")
            custom_greeting = data.get("custom_greeting")
            
            if person_id is None:
                return web.json_response(
                    {
                        "success": False,
                        "message": "缺少必填参数: person_id"
                    },
                    status=400
                )
            
            if not isinstance(person_id, int):
                return web.json_response(
                    {
                        "success": False,
                        "message": "参数类型错误: person_id 必须是整数"
                    },
                    status=400
                )
            
            if custom_greeting is None:
                return web.json_response(
                    {
                        "success": False,
                        "message": "缺少必填参数: custom_greeting"
                    },
                    status=400
                )

            # 验证欢迎词格式
            is_valid, error_msg = self._validate_greeting_format(custom_greeting)
            if not is_valid:
                return web.json_response(
                    {
                        "success": False,
                        "message": f"欢迎词格式错误: {error_msg}"
                    },
                    status=400
                )

            # 更新欢迎词配置
            success = await self.db.update_person_greeting(person_id, custom_greeting)
            
            if success:
                logger.info(f"欢迎词配置成功: person_id={person_id}")
                return web.json_response(
                    {
                        "success": True,
                        "message": "欢迎词配置成功"
                    },
                    status=200
                )
            else:
                return web.json_response(
                    {
                        "success": False,
                        "message": "欢迎词配置失败，用户可能不存在"
                    },
                    status=404
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
            logger.error(f"配置欢迎词失败: {e}")
            return web.json_response(
                {
                    "success": False,
                    "message": f"服务器内部错误: {str(e)}"
                },
                status=500
            )

    async def handle_get_config(self, request: web.Request) -> web.Response:
        """处理查询欢迎词配置请求
        
        GET /api/doorlock/welcome/config?person_id={person_id}
        
        Args:
            request: HTTP请求对象
            
        Returns:
            JSON响应，包含欢迎词配置
        """
        try:
            # 获取并验证person_id参数
            person_id_str = request.query.get("person_id")
            if not person_id_str:
                return web.json_response(
                    {
                        "success": False,
                        "message": "缺少必填参数: person_id"
                    },
                    status=400
                )

            try:
                person_id = int(person_id_str)
            except ValueError:
                return web.json_response(
                    {
                        "success": False,
                        "message": "参数类型错误: person_id 必须是整数"
                    },
                    status=400
                )

            # 查询欢迎词配置
            greeting = await self.db.get_person_greeting(person_id)
            
            if greeting is None:
                return web.json_response(
                    {
                        "success": False,
                        "message": f"用户不存在: person_id={person_id}"
                    },
                    status=404
                )

            # 返回配置信息
            return web.json_response(
                {
                    "success": True,
                    "data": {
                        "person_id": person_id,
                        "custom_greeting": greeting
                    }
                },
                status=200
            )

        except Exception as e:
            logger.error(f"查询欢迎词配置失败: {e}")
            return web.json_response(
                {
                    "success": False,
                    "message": f"服务器内部错误: {str(e)}"
                },
                status=500
            )

    async def handle_get_templates(self, request: web.Request) -> web.Response:
        """处理获取预设模板请求
        
        GET /api/doorlock/welcome/templates
        
        Args:
            request: HTTP请求对象
            
        Returns:
            JSON响应，包含预设模板列表
        """
        try:
            # 从配置文件加载模板
            with open("config/doorlock_prompts.yaml", "r", encoding="utf-8") as f:
                prompts_config = self.yaml.load(f)
            
            templates = prompts_config.get("welcome_templates", [])
            
            return web.json_response(
                {
                    "success": True,
                    "data": {
                        "templates": templates
                    }
                },
                status=200
            )

        except FileNotFoundError:
            logger.error("欢迎词模板配置文件不存在")
            return web.json_response(
                {
                    "success": False,
                    "message": "欢迎词模板配置文件不存在"
                },
                status=500
            )
        except Exception as e:
            logger.error(f"获取欢迎词模板失败: {e}")
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
