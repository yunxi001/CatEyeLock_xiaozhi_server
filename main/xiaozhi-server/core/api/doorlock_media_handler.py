"""
媒体文件下载 API 处理器

替代 WebSocket media_download 和 media_download_chunk
协议 v6.0 第二阶段

与旧 WebSocket 方式的关键区别：
- HTTP 直接返回原始二进制流（web.StreamResponse），不使用 Base64 编码
- 按路径下载接口用于 App 从 visit_notification 的 image_path 获取图片

端点：
  GET /api/doorlock/media               - 媒体文件列表
  GET /api/doorlock/media/{file_id}     - 按ID下载文件
  GET /api/doorlock/media/download      - 按路径下载文件（?path=...）
"""
import os
from aiohttp import web
from loguru import logger
from core.handle.textHandler.faceRecognitionHandler import get_face_service
from core.utils.auth import AuthToken

TAG = __name__

# 媒体文件根目录（与 mediaDownloadHandler.py 保持一致）
MEDIA_ROOT = "data/media"


class DoorlockMediaHandler:
    """媒体文件下载 API 处理器"""

    def __init__(self, config: dict):
        self.config = config
        auth_key = config.get("server", {}).get("auth_key", "")
        self.auth = AuthToken(auth_key) if auth_key else None

    def _verify_auth(self, request: web.Request) -> tuple:
        """验证 JWT 认证

        Returns:
            (success: bool, device_id_or_error_msg: str)
        """
        if not self.auth:
            return True, None

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False, "缺少认证 token"

        token = auth_header[7:]
        valid, device_id = self.auth.verify_token(token)
        if not valid:
            return False, "无效的认证 token"

        return True, device_id

    def _get_database(self):
        """获取数据库实例"""
        try:
            face_service = get_face_service()
            return face_service.db
        except Exception as e:
            logger.error(f"获取数据库实例失败: {e}")
            return None

    def _get_mime_type(self, file_path: str) -> str:
        """根据扩展名返回 MIME 类型"""
        ext = os.path.splitext(file_path)[1].lower()
        return {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".mp4": "video/mp4",
            ".avi": "video/x-msvideo",
            ".mkv": "video/x-matroska",
            ".webm": "video/webm",
        }.get(ext, "application/octet-stream")

    def _resolve_safe_path(self, file_path: str) -> str:
        """解析安全路径，检查路径遍历攻击

        Returns:
            文件完整路径（已通过安全检查）

        Raises:
            ValueError: 路径不安全
        """
        full_path = os.path.join(MEDIA_ROOT, file_path)
        real_path = os.path.realpath(full_path)
        real_root = os.path.realpath(MEDIA_ROOT)
        if not real_path.startswith(real_root + os.sep) and real_path != real_root:
            raise ValueError("路径遍历攻击被拦截")
        return real_path

    async def handle_get_list(self, request: web.Request) -> web.Response:
        """GET /api/doorlock/media?device_id=...&file_type=...&date_from=...&limit=50&offset=0"""
        try:
            valid, msg = self._verify_auth(request)
            if not valid:
                return web.json_response({"success": False, "message": msg}, status=401)

            device_id = request.query.get("device_id")
            if not device_id:
                return web.json_response(
                    {"success": False, "message": "缺少必填参数: device_id"}, status=400
                )

            file_type = request.query.get("file_type")
            date_from = request.query.get("date_from")
            date_to = request.query.get("date_to")
            limit = min(int(request.query.get("limit", 100)), 500)
            offset = int(request.query.get("offset", 0))

            db = self._get_database()
            if not db:
                return web.json_response(
                    {"success": False, "message": "数据库不可用"}, status=500
                )

            records, total = db.get_media_files(
                device_id,
                file_type=file_type,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                offset=offset
            )

            return web.json_response({
                "success": True,
                "data": {"records": records, "total": total, "limit": limit, "offset": offset}
            }, status=200)

        except Exception as e:
            logger.error(f"查询媒体文件列表失败: {e}")
            return web.json_response(
                {"success": False, "message": f"服务器内部错误: {str(e)}"}, status=500
            )

    async def handle_download(self, request: web.Request) -> web.Response:
        """GET /api/doorlock/media/{file_id} — 按ID下载文件，返回二进制流"""
        try:
            valid, msg = self._verify_auth(request)
            if not valid:
                return web.json_response({"success": False, "message": msg}, status=401)

            file_id_str = request.match_info.get("file_id")
            if not file_id_str:
                return web.json_response(
                    {"success": False, "message": "缺少 file_id"}, status=400
                )

            db = self._get_database()
            if not db:
                return web.json_response(
                    {"success": False, "message": "数据库不可用"}, status=500
                )

            file_info = db.get_media_file_by_id(int(file_id_str))
            if not file_info:
                return web.json_response(
                    {"success": False, "message": "文件记录不存在"}, status=404
                )

            file_path = file_info.get("file_path")
            if not file_path:
                return web.json_response(
                    {"success": False, "message": "文件路径无效"}, status=500
                )

            full_path = self._resolve_safe_path(file_path)
            if not os.path.exists(full_path):
                return web.json_response(
                    {"success": False, "message": "文件不存在或已被删除"}, status=404
                )

            file_size = os.path.getsize(full_path)
            mime_type = self._get_mime_type(file_path)
            file_name = os.path.basename(file_path)

            response = web.StreamResponse(
                status=200,
                headers={
                    "Content-Type": mime_type,
                    "Content-Disposition": f'inline; filename="{file_name}"',
                    "Content-Length": str(file_size),
                }
            )
            await response.prepare(request)

            with open(full_path, "rb") as f:
                while True:
                    chunk = f.read(64 * 1024)  # 64KB 分块
                    if not chunk:
                        break
                    await response.write(chunk)

            await response.write_eof()
            return response

        except ValueError as e:
            logger.warning(f"路径安全检查失败: {e}")
            return web.json_response(
                {"success": False, "message": "无权访问该文件"}, status=403
            )
        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            return web.json_response(
                {"success": False, "message": f"服务器内部错误: {str(e)}"}, status=500
            )

    async def handle_download_by_path(self, request: web.Request) -> web.Response:
        """GET /api/doorlock/media/download?path=... — 按路径下载图片，返回二进制流

        供 App 从 visit_notification 中的 image_path 直接下载人脸图片
        """
        try:
            valid, msg = self._verify_auth(request)
            if not valid:
                return web.json_response({"success": False, "message": msg}, status=401)

            file_path = request.query.get("path")
            if not file_path:
                return web.json_response(
                    {"success": False, "message": "缺少必填参数: path"}, status=400
                )

            full_path = self._resolve_safe_path(file_path)
            if not os.path.exists(full_path):
                return web.json_response(
                    {"success": False, "message": "文件不存在或已被删除"}, status=404
                )

            file_size = os.path.getsize(full_path)
            mime_type = self._get_mime_type(file_path)
            file_name = os.path.basename(file_path)

            response = web.StreamResponse(
                status=200,
                headers={
                    "Content-Type": mime_type,
                    "Content-Disposition": f'inline; filename="{file_name}"',
                    "Content-Length": str(file_size),
                }
            )
            await response.prepare(request)

            with open(full_path, "rb") as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    await response.write(chunk)

            await response.write_eof()
            return response

        except ValueError as e:
            logger.warning(f"路径安全检查失败: {e}")
            return web.json_response(
                {"success": False, "message": "无权访问该文件"}, status=403
            )
        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            return web.json_response(
                {"success": False, "message": f"服务器内部错误: {str(e)}"}, status=500
            )

    async def handle_options(self, request: web.Request) -> web.Response:
        """处理 CORS 预检请求"""
        return web.Response(
            status=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            }
        )
