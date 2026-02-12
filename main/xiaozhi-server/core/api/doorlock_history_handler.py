"""门锁历史记录查询API处理器

提供意图识别历史和快递警报历史的查询接口
"""
from datetime import datetime
from aiohttp import web
from loguru import logger
from core.providers.doorlock.doorlock_database import DoorlockDatabase


class DoorlockHistoryHandler:
    """门锁历史记录查询API处理器"""

    def __init__(self, config: dict):
        """初始化处理器
        
        Args:
            config: 系统配置字典
        """
        self.config = config
        self.db = DoorlockDatabase(config)

    def _parse_int_param(self, value: str, param_name: str, default: int = None) -> tuple[int, str]:
        """解析整数参数
        
        Args:
            value: 参数值字符串
            param_name: 参数名称
            default: 默认值
            
        Returns:
            (解析后的整数, 错误信息)
        """
        if value is None:
            if default is not None:
                return default, ""
            return None, f"缺少必填参数: {param_name}"
        
        try:
            return int(value), ""
        except ValueError:
            return None, f"参数类型错误: {param_name} 必须是整数"

    def _parse_datetime_param(self, value: str, param_name: str) -> tuple[datetime, str]:
        """解析日期时间参数
        
        Args:
            value: 参数值字符串（格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS）
            param_name: 参数名称
            
        Returns:
            (解析后的datetime对象, 错误信息)
        """
        if value is None:
            return None, ""
        
        try:
            # 尝试解析日期格式
            if len(value) == 10:  # YYYY-MM-DD
                return datetime.strptime(value, "%Y-%m-%d"), ""
            else:  # YYYY-MM-DD HH:MM:SS
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S"), ""
        except ValueError:
            return None, f"参数格式错误: {param_name} 必须是日期格式 (YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS)"

    async def handle_get_intents(self, request: web.Request) -> web.Response:
        """处理查询意图识别历史请求
        
        GET /api/doorlock/intents/history?device_id={device_id}&limit=20&offset=0&start_date=2026-01-01&end_date=2026-12-31
        
        Args:
            request: HTTP请求对象
            
        Returns:
            JSON响应，包含意图识别历史记录
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

            # 解析分页参数
            limit, error = self._parse_int_param(request.query.get("limit"), "limit", 20)
            if error:
                return web.json_response({"success": False, "message": error}, status=400)
            
            offset, error = self._parse_int_param(request.query.get("offset"), "offset", 0)
            if error:
                return web.json_response({"success": False, "message": error}, status=400)

            # 验证分页参数范围
            if limit < 1 or limit > 100:
                return web.json_response(
                    {
                        "success": False,
                        "message": "参数范围错误: limit 必须在 1-100 之间"
                    },
                    status=400
                )
            
            if offset < 0:
                return web.json_response(
                    {
                        "success": False,
                        "message": "参数范围错误: offset 必须大于等于 0"
                    },
                    status=400
                )

            # 解析时间范围参数（可选）
            start_date, error = self._parse_datetime_param(request.query.get("start_date"), "start_date")
            if error:
                return web.json_response({"success": False, "message": error}, status=400)
            
            end_date, error = self._parse_datetime_param(request.query.get("end_date"), "end_date")
            if error:
                return web.json_response({"success": False, "message": error}, status=400)

            # 查询意图识别历史
            intents, total = await self.db.get_visitor_intents(
                device_id=device_id,
                limit=limit,
                offset=offset,
                start_date=start_date,
                end_date=end_date
            )

            # 格式化返回数据
            data = []
            for intent in intents:
                data.append({
                    "id": intent.id,
                    "visit_id": intent.visit_id,
                    "session_id": intent.session_id,
                    "person_id": intent.person_id,
                    "intent_type": intent.intent_type,
                    "intent_summary": intent.intent_summary,
                    "dialogue_history": intent.dialogue_history,
                    "created_at": intent.created_at.isoformat() if intent.created_at else None
                })

            return web.json_response(
                {
                    "success": True,
                    "data": data,
                    "total": total,
                    "limit": limit,
                    "offset": offset
                },
                status=200
            )

        except Exception as e:
            logger.error(f"查询意图识别历史失败: {e}")
            return web.json_response(
                {
                    "success": False,
                    "message": f"服务器内部错误: {str(e)}"
                },
                status=500
            )

    async def handle_get_alerts(self, request: web.Request) -> web.Response:
        """处理查询快递警报历史请求
        
        GET /api/doorlock/alerts/history?device_id={device_id}&limit=20&offset=0&start_date=2026-01-01&end_date=2026-12-31
        
        Args:
            request: HTTP请求对象
            
        Returns:
            JSON响应，包含快递警报历史记录
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

            # 解析分页参数
            limit, error = self._parse_int_param(request.query.get("limit"), "limit", 20)
            if error:
                return web.json_response({"success": False, "message": error}, status=400)
            
            offset, error = self._parse_int_param(request.query.get("offset"), "offset", 0)
            if error:
                return web.json_response({"success": False, "message": error}, status=400)

            # 验证分页参数范围
            if limit < 1 or limit > 100:
                return web.json_response(
                    {
                        "success": False,
                        "message": "参数范围错误: limit 必须在 1-100 之间"
                    },
                    status=400
                )
            
            if offset < 0:
                return web.json_response(
                    {
                        "success": False,
                        "message": "参数范围错误: offset 必须大于等于 0"
                    },
                    status=400
                )

            # 解析时间范围参数（可选）
            start_date, error = self._parse_datetime_param(request.query.get("start_date"), "start_date")
            if error:
                return web.json_response({"success": False, "message": error}, status=400)
            
            end_date, error = self._parse_datetime_param(request.query.get("end_date"), "end_date")
            if error:
                return web.json_response({"success": False, "message": error}, status=400)

            # 查询快递警报历史
            alerts, total = await self.db.get_package_alerts(
                device_id=device_id,
                limit=limit,
                offset=offset,
                start_date=start_date,
                end_date=end_date
            )

            # 格式化返回数据
            data = []
            for alert in alerts:
                data.append({
                    "id": alert.id,
                    "device_id": alert.device_id,
                    "session_id": alert.session_id,
                    "threat_level": alert.threat_level,
                    "action": alert.action,
                    "description": alert.description,
                    "photo_path": alert.photo_path,
                    "voice_warning_sent": alert.voice_warning_sent,
                    "notified": alert.notified,
                    "created_at": alert.created_at.isoformat() if alert.created_at else None
                })

            return web.json_response(
                {
                    "success": True,
                    "data": data,
                    "total": total,
                    "limit": limit,
                    "offset": offset
                },
                status=200
            )

        except Exception as e:
            logger.error(f"查询快递警报历史失败: {e}")
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
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
