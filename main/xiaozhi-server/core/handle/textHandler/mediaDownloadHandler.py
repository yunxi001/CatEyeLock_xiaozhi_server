"""
媒体文件下载处理器

协议版本: v2.2
支持:
- media_download: 下载完整文件（小于 50MB）
- media_download_chunk: 分片下载大文件
"""
import json
import base64
import os
import math
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.handle.textHandler.faceRecognitionHandler import get_face_service

TAG = __name__


def _get_database(conn):
    """获取数据库实例"""
    try:
        face_service = get_face_service(conn.logger)
        return face_service.db
    except Exception:
        return None

# 媒体文件根目录
MEDIA_ROOT = "data/media"

# 文件大小限制
MAX_DOWNLOAD_SIZE = 50 * 1024 * 1024  # 50MB
MAX_CHUNK_SIZE = 5 * 1024 * 1024  # 5MB
DEFAULT_CHUNK_SIZE = 1 * 1024 * 1024  # 1MB


class MediaDownloadHandler(TextMessageHandler):
    """处理媒体文件下载请求"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.MEDIA_DOWNLOAD

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        # 仅处理 App 发送的请求
        if not hasattr(conn, "client_type") or conn.client_type != "app":
            return
        
        file_id = msg_json.get("file_id")
        file_path = msg_json.get("file_path")
        
        if not file_id and not file_path:
            await self._send_error(conn, "missing_params", "需要 file_id 或 file_path")
            return
        
        conn.logger.bind(tag=TAG).info(f"收到媒体下载请求: file_id={file_id}, file_path={file_path}")
        
        await self._download_file(conn, file_id, file_path)

    async def _download_file(self, conn, file_id: int = None, file_path: str = None):
        """下载文件"""
        try:
            # 如果提供 file_id，从数据库查询文件路径
            if file_id and not file_path:
                db = _get_database(conn)
                if db:
                    file_info = db.get_media_file_by_id(file_id)
                    if file_info:
                        file_path = file_info.get("file_path")
                    else:
                        await self._send_error(conn, "file_not_found", "文件记录不存在")
                        return
                else:
                    await self._send_error(conn, "internal_error", "数据库不可用")
                    return
            
            if not file_path:
                await self._send_error(conn, "missing_params", "无法确定文件路径")
                return
            
            # 构建完整路径
            full_path = os.path.join(MEDIA_ROOT, file_path)
            
            # 安全检查：防止路径遍历攻击
            real_path = os.path.realpath(full_path)
            real_root = os.path.realpath(MEDIA_ROOT)
            if not real_path.startswith(real_root):
                await self._send_error(conn, "access_denied", "无权访问该文件")
                return
            
            # 检查文件是否存在
            if not os.path.exists(full_path):
                await self._send_error(conn, "file_not_found", "文件不存在或已被删除")
                return
            
            # 检查文件大小
            file_size = os.path.getsize(full_path)
            if file_size > MAX_DOWNLOAD_SIZE:
                await self._send_error(conn, "file_too_large", "文件过大，请使用分片下载")
                return
            
            # 读取并编码文件
            with open(full_path, "rb") as f:
                content = base64.b64encode(f.read()).decode()
            
            # 确定文件类型
            file_type = "face" if "face" in file_path else "recording"
            mime_type = self._get_mime_type(file_path)
            file_name = os.path.basename(file_path)
            
            await conn.websocket.send(json.dumps({
                "type": "media_download",
                "status": "success",
                "data": {
                    "file_id": file_id,
                    "file_type": file_type,
                    "file_name": file_name,
                    "file_size": file_size,
                    "mime_type": mime_type,
                    "content": content
                }
            }))
            
            conn.logger.bind(tag=TAG).info(f"文件下载完成: {file_path}, 大小: {file_size} bytes")
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"下载文件失败: {e}")
            await self._send_error(conn, "internal_error", str(e))

    def _get_mime_type(self, file_path: str) -> str:
        """获取 MIME 类型"""
        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".mp4": "video/mp4",
            ".avi": "video/x-msvideo",
            ".mkv": "video/x-matroska",
            ".webm": "video/webm",
        }
        return mime_map.get(ext, "application/octet-stream")

    async def _send_error(self, conn, error: str, message: str):
        """发送错误响应"""
        try:
            await conn.websocket.send(json.dumps({
                "type": "media_download",
                "status": "error",
                "error": error,
                "message": message
            }))
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"发送错误响应失败: {e}")


class MediaDownloadChunkHandler(TextMessageHandler):
    """处理大文件分片下载"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.MEDIA_DOWNLOAD_CHUNK

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        # 仅处理 App 发送的请求
        if not hasattr(conn, "client_type") or conn.client_type != "app":
            return
        
        file_id = msg_json.get("file_id")
        chunk_index = msg_json.get("chunk_index", 0)
        chunk_size = min(msg_json.get("chunk_size", DEFAULT_CHUNK_SIZE), MAX_CHUNK_SIZE)
        
        if not file_id:
            await self._send_error(conn, "missing_params", "需要 file_id")
            return
        
        conn.logger.bind(tag=TAG).info(
            f"收到分片下载请求: file_id={file_id}, chunk_index={chunk_index}"
        )
        
        await self._download_chunk(conn, file_id, chunk_index, chunk_size)

    async def _download_chunk(self, conn, file_id: int, chunk_index: int, chunk_size: int):
        """下载文件分片"""
        try:
            # 从数据库查询文件信息
            db = _get_database(conn)
            if not db:
                await self._send_error(conn, "internal_error", "数据库不可用")
                return
            
            file_info = db.get_media_file_by_id(file_id)
            if not file_info:
                await self._send_error(conn, "file_not_found", "文件记录不存在")
                return
            
            file_path = file_info.get("file_path")
            full_path = os.path.join(MEDIA_ROOT, file_path)
            
            # 安全检查
            real_path = os.path.realpath(full_path)
            real_root = os.path.realpath(MEDIA_ROOT)
            if not real_path.startswith(real_root):
                await self._send_error(conn, "access_denied", "无权访问该文件")
                return
            
            if not os.path.exists(full_path):
                await self._send_error(conn, "file_not_found", "文件不存在或已被删除")
                return
            
            # 计算分片信息
            file_size = os.path.getsize(full_path)
            total_chunks = math.ceil(file_size / chunk_size)
            
            if chunk_index >= total_chunks:
                await self._send_error(conn, "invalid_chunk", f"分片索引超出范围 (0-{total_chunks-1})")
                return
            
            # 读取指定分片
            offset = chunk_index * chunk_size
            actual_chunk_size = min(chunk_size, file_size - offset)
            
            with open(full_path, "rb") as f:
                f.seek(offset)
                chunk_data = f.read(actual_chunk_size)
            
            content = base64.b64encode(chunk_data).decode()
            
            await conn.websocket.send(json.dumps({
                "type": "media_download_chunk",
                "status": "success",
                "data": {
                    "file_id": file_id,
                    "chunk_index": chunk_index,
                    "total_chunks": total_chunks,
                    "file_size": file_size,
                    "chunk_size": actual_chunk_size,
                    "content": content
                }
            }))
            
            conn.logger.bind(tag=TAG).debug(
                f"分片下载完成: file_id={file_id}, chunk={chunk_index}/{total_chunks}"
            )
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"分片下载失败: {e}")
            await self._send_error(conn, "internal_error", str(e))

    async def _send_error(self, conn, error: str, message: str):
        """发送错误响应"""
        try:
            await conn.websocket.send(json.dumps({
                "type": "media_download_chunk",
                "status": "error",
                "error": error,
                "message": message
            }))
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"发送错误响应失败: {e}")
