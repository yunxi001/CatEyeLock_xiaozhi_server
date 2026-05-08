"""
门锁核心 API 处理器

提供替代 WebSocket face_management 和 query 的 HTTP API
协议 v6.0

端点：
  第一阶段（已实现）
  GET  /api/doorlock/status               - 查询设备状态
  GET  /api/doorlock/faces                - 人员列表
  POST /api/doorlock/faces                - 注册人脸
  DELETE /api/doorlock/faces/{face_id}     - 删除人脸
  PUT  /api/doorlock/faces/{face_id}/permission - 更新权限
  GET  /api/doorlock/visits               - 到访记录
  第二阶段（已实现）
  GET  /api/doorlock/events               - 查询事件历史
  GET  /api/doorlock/unlock_logs          - 查询开锁日志
  GET  /api/doorlock/password             - 查询设备密码
"""
import base64
from aiohttp import web
from loguru import logger
from core.connection_manager import ConnectionManager
from core.handle.textHandler.faceRecognitionHandler import get_face_service
from core.utils.auth import AuthToken

TAG = __name__


class DoorlockApiHandler:
    """门锁核心 API 处理器"""

    def __init__(self, config: dict):
        self.config = config
        auth_key = config.get("server", {}).get("auth_key", "")
        self.auth = AuthToken(auth_key) if auth_key else None

    def _get_service(self, logger_instance=None):
        """获取 FaceService 单例"""
        return get_face_service(logger_instance)

    def _verify_auth(self, request: web.Request) -> tuple:
        """验证 JWT 认证

        Returns:
            (success: bool, device_id_or_error_msg: str)
        """
        if not self.auth:
            return True, None  # 无 auth_key 时允许所有请求

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False, "缺少认证 token"

        token = auth_header[7:]
        valid, device_id = self.auth.verify_token(token)
        if not valid:
            return False, "无效的认证 token"

        return True, device_id

    async def handle_get_status(self, request: web.Request) -> web.Response:
        """GET /api/doorlock/status?device_id=..."""
        try:
            valid, msg = self._verify_auth(request)
            if not valid:
                return web.json_response({"success": False, "message": msg}, status=401)

            device_id = request.query.get("device_id")
            if not device_id:
                return web.json_response(
                    {"success": False, "message": "缺少必填参数: device_id"}, status=400
                )

            manager = ConnectionManager.get_instance()
            esp32_conn = manager.get_esp32_conn(device_id)
            is_online = esp32_conn is not None

            status_data = {
                "device_id": device_id,
                "online": is_online,
            }

            if esp32_conn:
                status_data["mode"] = getattr(esp32_conn, "current_mode", "normal")
                device_state = getattr(esp32_conn, "device_state", {})
                status_data["state"] = device_state

            return web.json_response({"success": True, "data": status_data}, status=200)

        except Exception as e:
            logger.error(f"查询设备状态失败: {e}")
            return web.json_response(
                {"success": False, "message": f"服务器内部错误: {str(e)}"}, status=500
            )

    async def handle_get_faces(self, request: web.Request) -> web.Response:
        """GET /api/doorlock/faces?page=1&page_size=20"""
        try:
            valid, msg = self._verify_auth(request)
            if not valid:
                return web.json_response({"success": False, "message": msg}, status=401)

            page = int(request.query.get("page", 1))
            page_size = int(request.query.get("page_size", 20))

            face_service = self._get_service()
            persons = face_service.get_persons()

            # 简单分页（FaceService.get_persons 返回全部，在内存中分页）
            total = len(persons)
            start = (page - 1) * page_size
            end = start + page_size
            records = persons[start:end]

            return web.json_response({
                "success": True,
                "data": {
                    "records": records,
                    "total": total,
                    "page": page,
                    "page_size": page_size
                }
            }, status=200)

        except Exception as e:
            logger.error(f"查询人员列表失败: {e}")
            return web.json_response(
                {"success": False, "message": f"服务器内部错误: {str(e)}"}, status=500
            )

    async def handle_post_faces(self, request: web.Request) -> web.Response:
        """POST /api/doorlock/faces (multipart/form-data)"""
        try:
            valid, msg = self._verify_auth(request)
            if not valid:
                return web.json_response({"success": False, "message": msg}, status=401)

            reader = await request.multipart()

            name = None
            relation_type = "other"
            permission = None
            images = []

            async for part in reader:
                field_name = part.name
                if field_name == "name":
                    name = await part.text()
                elif field_name == "relation_type":
                    relation_type = await part.text()
                elif field_name == "permission":
                    import json
                    permission = json.loads(await part.text())
                elif field_name == "images":
                    image_data = await part.read()
                    images.append(image_data)

            if not name:
                return web.json_response(
                    {"success": False, "message": "缺少必填字段: name"}, status=400
                )

            if not images:
                return web.json_response(
                    {"success": False, "message": "缺少人脸图片"}, status=400
                )

            # 限制图片数量
            if len(images) > 5:
                return web.json_response(
                    {"success": False, "message": "最多上传5张图片"}, status=400
                )

            face_service = self._get_service()
            person_id, error = face_service.register_face(name, relation_type, images, permission)

            if error:
                return web.json_response(
                    {"success": False, "message": error}, status=400
                )

            return web.json_response({
                "success": True,
                "data": {
                    "person_id": person_id,
                    "message": "录入成功"
                }
            }, status=200)

        except Exception as e:
            logger.error(f"注册人脸失败: {e}")
            return web.json_response(
                {"success": False, "message": f"服务器内部错误: {str(e)}"}, status=500
            )

    async def handle_delete_face(self, request: web.Request) -> web.Response:
        """DELETE /api/doorlock/faces/{face_id}"""
        try:
            valid, msg = self._verify_auth(request)
            if not valid:
                return web.json_response({"success": False, "message": msg}, status=401)

            face_id = request.match_info.get("face_id")
            if not face_id:
                return web.json_response(
                    {"success": False, "message": "缺少 face_id"}, status=400
                )

            face_service = self._get_service()
            success = face_service.delete_person(int(face_id))

            if success:
                return web.json_response(
                    {"success": True, "message": "删除成功"}, status=200
                )
            else:
                return web.json_response(
                    {"success": False, "message": "删除失败"}, status=400
                )

        except Exception as e:
            logger.error(f"删除人脸失败: {e}")
            return web.json_response(
                {"success": False, "message": f"服务器内部错误: {str(e)}"}, status=500
            )

    async def handle_update_permission(self, request: web.Request) -> web.Response:
        """PUT /api/doorlock/faces/{face_id}/permission"""
        try:
            valid, msg = self._verify_auth(request)
            if not valid:
                return web.json_response({"success": False, "message": msg}, status=401)

            face_id = request.match_info.get("face_id")
            if not face_id:
                return web.json_response(
                    {"success": False, "message": "缺少 face_id"}, status=400
                )

            try:
                body = await request.json()
            except Exception:
                return web.json_response(
                    {"success": False, "message": "请求体格式错误"}, status=400
                )

            permission = body.get("permission")
            if not permission:
                return web.json_response(
                    {"success": False, "message": "缺少 permission 字段"}, status=400
                )

            face_service = self._get_service()
            success = face_service.update_permission(int(face_id), permission)

            if success:
                return web.json_response(
                    {"success": True, "message": "权限更新成功"}, status=200
                )
            else:
                return web.json_response(
                    {"success": False, "message": "权限更新失败"}, status=400
                )

        except Exception as e:
            logger.error(f"更新权限失败: {e}")
            return web.json_response(
                {"success": False, "message": f"服务器内部错误: {str(e)}"}, status=500
            )

    async def handle_get_visits(self, request: web.Request) -> web.Response:
        """GET /api/doorlock/visits?page=1&page_size=20&date_from=...&date_to=..."""
        try:
            valid, msg = self._verify_auth(request)
            if not valid:
                return web.json_response({"success": False, "message": msg}, status=401)

            page = int(request.query.get("page", 1))
            page_size = int(request.query.get("page_size", 20))
            date_from = request.query.get("date_from")
            date_to = request.query.get("date_to")

            face_service = self._get_service()
            result = face_service.get_visits(page, page_size, date_from, date_to)

            return web.json_response({
                "success": True,
                "data": result
            }, status=200)

        except Exception as e:
            logger.error(f"查询到访记录失败: {e}")
            return web.json_response(
                {"success": False, "message": f"服务器内部错误: {str(e)}"}, status=500
            )

    async def handle_get_events(self, request: web.Request) -> web.Response:
        """GET /api/doorlock/events?device_id=...&event_type=...&limit=50&offset=0"""
        try:
            valid, msg = self._verify_auth(request)
            if not valid:
                return web.json_response({"success": False, "message": msg}, status=401)

            device_id = request.query.get("device_id")
            if not device_id:
                return web.json_response(
                    {"success": False, "message": "缺少必填参数: device_id"}, status=400
                )

            event_type = request.query.get("event_type")
            limit = min(int(request.query.get("limit", 100)), 500)
            offset = int(request.query.get("offset", 0))

            face_service = self._get_service()
            if not face_service or not face_service.db:
                return web.json_response(
                    {"success": False, "message": "数据库不可用"}, status=500
                )

            records, total = face_service.db.get_events(
                device_id, event_type=event_type, limit=limit, offset=offset
            )

            return web.json_response({
                "success": True,
                "data": {"records": records, "total": total, "limit": limit, "offset": offset}
            }, status=200)

        except Exception as e:
            logger.error(f"查询事件历史失败: {e}")
            return web.json_response(
                {"success": False, "message": f"服务器内部错误: {str(e)}"}, status=500
            )

    async def handle_get_unlock_logs(self, request: web.Request) -> web.Response:
        """GET /api/doorlock/unlock_logs?device_id=...&method=...&result=...&limit=50&offset=0"""
        try:
            valid, msg = self._verify_auth(request)
            if not valid:
                return web.json_response({"success": False, "message": msg}, status=401)

            device_id = request.query.get("device_id")
            if not device_id:
                return web.json_response(
                    {"success": False, "message": "缺少必填参数: device_id"}, status=400
                )

            method = request.query.get("method")
            result_str = request.query.get("result")
            result = int(result_str) if result_str is not None else None
            limit = min(int(request.query.get("limit", 100)), 500)
            offset = int(request.query.get("offset", 0))

            face_service = self._get_service()
            if not face_service or not face_service.db:
                return web.json_response(
                    {"success": False, "message": "数据库不可用"}, status=500
                )

            records, total = face_service.db.get_unlock_logs(
                device_id, method=method, result=result, limit=limit, offset=offset
            )

            return web.json_response({
                "success": True,
                "data": {"records": records, "total": total, "limit": limit, "offset": offset}
            }, status=200)

        except Exception as e:
            logger.error(f"查询开锁日志失败: {e}")
            return web.json_response(
                {"success": False, "message": f"服务器内部错误: {str(e)}"}, status=500
            )

    async def handle_get_password(self, request: web.Request) -> web.Response:
        """GET /api/doorlock/password?device_id=..."""
        try:
            valid, msg = self._verify_auth(request)
            if not valid:
                return web.json_response({"success": False, "message": msg}, status=401)

            device_id = request.query.get("device_id")
            if not device_id:
                return web.json_response(
                    {"success": False, "message": "缺少必填参数: device_id"}, status=400
                )

            face_service = self._get_service()
            if not face_service or not face_service.db:
                return web.json_response(
                    {"success": False, "message": "数据库不可用"}, status=500
                )

            password = face_service.db.get_device_password(device_id)

            return web.json_response({
                "success": True,
                "data": {"password": password or "123456"}
            }, status=200)

        except Exception as e:
            logger.error(f"查询密码失败: {e}")
            return web.json_response(
                {"success": False, "message": f"服务器内部错误: {str(e)}"}, status=500
            )

    async def handle_options(self, request: web.Request) -> web.Response:
        """处理 CORS 预检请求"""
        return web.Response(
            status=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Access-Control-Allow-Content-Type": "application/json, multipart/form-data",
            }
        )
