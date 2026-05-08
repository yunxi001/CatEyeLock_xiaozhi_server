"""
人脸识别消息处理器
"""
import json
import time
import base64
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.connection_manager import ConnectionManager

TAG = __name__

# 全局 FaceService 实例（延迟初始化）
_face_service = None


def get_face_service(logger=None):
    """获取 FaceService 单例"""
    global _face_service
    if _face_service is None:
        from core.providers.doorlock import FaceService
        _face_service = FaceService(logger=logger)
    return _face_service


class FaceRecognitionHandler(TextMessageHandler):
    """处理 ESP32 人脸识别请求"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.FACE_RECOGNITION

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        action = msg_json.get("action")
        
        if action == "recognize":
            await self._handle_recognize(conn, msg_json)
        else:
            conn.logger.bind(tag=TAG).warning(f"未知人脸识别动作: {action}")
            await self._send_error(conn, f"未知动作: {action}")

    async def _handle_recognize(self, conn, msg_json: Dict[str, Any]):
        """处理人脸识别请求"""
        try:
            face_service = get_face_service(conn.logger)
            
            # 获取图像数据
            image_data = msg_json.get("image")
            if not image_data:
                await self._send_result(conn, {"type": "face_recognition", "result": "no_face"})
                return
            
            # 解析图像数据（JSON 方式发送时使用 base64 编码）
            # 注意：ESP32 现在推荐直接发送二进制数据（type=2），此处保留 JSON 方式的兼容性
            try:
                jpeg_data = base64.b64decode(image_data)
            except Exception as e:
                conn.logger.bind(tag=TAG).error(f"图像解析失败: {e}")
                await self._send_result(conn, {"type": "face_recognition", "result": "no_face"})
                return
            
            # 执行人脸识别
            result = face_service.recognize(jpeg_data)
            
            # 检查权限
            access_granted = False
            deny_reason = None
            
            if result.result == "known" and result.person:
                access_granted, deny_reason = face_service.check_permission(result.person.id)
            
            # 生成问候语
            greeting = face_service.generate_greeting(result, access_granted, deny_reason)
            
            # 保存到访记录
            visit_id = face_service.save_visit_record(result, access_granted, deny_reason, jpeg_data)
            
            # 保存人脸图片到文件系统（仅成功识别时保存）
            image_path = None
            if result.result == "known" and result.person:
                image_path = await self._save_face_image(conn, jpeg_data, result.person.id)
            
            # 构建响应（符合 v5.0 协议：face_result）
            response = self._build_face_result(result, access_granted, deny_reason)
            
            # 缓存识别结果到连接对象，供 logReportHandler 填充 uid 使用
            self._cache_face_result(conn, result, access_granted)
            
            # 发送 JSON 响应
            await self._send_result(conn, response)
            
            # 发送 TTS 语音（如果有问候语）
            if greeting:
                await self._send_tts(conn, greeting)
            
            # 推送通知给 App（含人脸图片）
            await self._notify_apps(conn, result, access_granted, visit_id, jpeg_data, image_path)
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"人脸识别处理失败: {e}")
            await self._send_error(conn, str(e))

    def _cache_face_result(self, conn, result, access_granted: bool):
        """缓存人脸识别结果到连接对象
        
        供 logReportHandler 在处理 face 开锁日志时填充 uid
        
        Args:
            conn: 连接对象
            result: 识别结果
            access_granted: 是否授权开锁
        """
        conn.last_face_result = {
            "ts": int(time.time() * 1000),
            "result": result.result,
            "user_id": result.person.id if result.person else None,
            "person_name": result.person.name if result.person else None,
            "access_granted": access_granted
        }
        conn.logger.bind(tag=TAG).debug(
            f"缓存人脸识别结果: user_id={conn.last_face_result.get('user_id')}"
        )

    def _build_face_result(self, result, access_granted: bool, deny_reason: str = None) -> dict:
        """构建符合 v5.2 协议的人脸识别响应
        
        响应格式:
        {
            "type": "face_result",
            "result": "known|unknown|no_face|error",
            "user_id": 5,
            "access": {"granted": true, "reason": "authorized_user"}
        }
        
        注意：face_result 是主动上报，不携带 seq_id
        """
        response = {
            "type": "face_result",
            "result": result.result,
            "user_id": result.person.id if result.person else None,
            "access": {
                "granted": access_granted,
                "reason": self._get_access_reason(result, access_granted, deny_reason)
            }
        }
        return response
    
    def _get_access_reason(self, result, access_granted: bool, deny_reason: str = None) -> str:
        """获取访问原因"""
        if access_granted:
            return "authorized_user"
        
        if deny_reason:
            # 映射内部原因到协议定义
            reason_map = {
                "time_restricted": "time_restricted",
                "not_in_time_range": "time_restricted",
                "blacklisted": "blacklisted",
                "expired": "guest_expired",
            }
            return reason_map.get(deny_reason, "unauthorized_user")
        
        if result.result == "unknown":
            return "unauthorized_user"
        
        return "unauthorized_user"

    async def _send_result(self, conn, response: dict):
        """发送识别结果"""
        await conn.websocket.send(json.dumps(response))

    async def _send_tts(self, conn, text: str):
        """发送 TTS 语音"""
        try:
            if hasattr(conn, 'tts') and conn.tts:
                # 复用现有 TTS 模块
                from core.providers.tts.dto.dto import ContentType, TTSMessageDTO, SentenceType
                import uuid
                
                sentence_id = str(uuid.uuid4().hex)
                conn.tts.tts_text_queue.put(
                    TTSMessageDTO(
                        sentence_id=sentence_id,
                        sentence_type=SentenceType.FIRST,
                        content_type=ContentType.TEXT,
                        content=text
                    )
                )
                conn.tts.tts_text_queue.put(
                    TTSMessageDTO(
                        sentence_id=sentence_id,
                        sentence_type=SentenceType.LAST,
                        content_type=ContentType.ACTION,
                    )
                )
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"TTS 发送失败: {e}")

    async def _notify_apps(self, conn, result, access_granted: bool, visit_id: int, 
                          jpeg_data: bytes = None, image_path: str = None):
        """推送到访通知给 App（含人脸图片）
        
        Args:
            conn: 连接对象
            result: 识别结果
            access_granted: 是否授权开锁
            visit_id: 到访记录 ID
            jpeg_data: JPEG 图片数据（可选）
            image_path: 图片存储路径（可选）
        """
        try:
            manager = ConnectionManager.get_instance()
            app_conns = manager.get_app_conns(conn.device_id)
            
            if not app_conns:
                return
            
            # 构建通知消息（图片通过 HTTP API 下载，不嵌入 Base64）
            notification = {
                "type": "visit_notification",
                "ts": int(time.time() * 1000),
                "data": {
                    "visit_id": visit_id,
                    "person_id": result.person.id if result.person else None,
                    "person_name": result.person.name if result.person else "陌生人",
                    "relation": result.person.relation_type if result.person else None,
                    "result": result.result,
                    "access_granted": access_granted,
                    "image_path": image_path
                }
            }
            
            msg = json.dumps(notification)
            
            for app_conn in app_conns:
                if app_conn.websocket:
                    await app_conn.websocket.send(msg)
                    
            conn.logger.bind(tag=TAG).debug(f"已推送到访通知给 {len(app_conns)} 个 App")
                    
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"推送通知失败: {e}")

    async def _save_face_image(self, conn, jpeg_data: bytes, user_id: int) -> str:
        """保存人脸图片到文件系统
        
        Returns:
            保存的文件路径，失败返回 None
        """
        try:
            if hasattr(conn, "media_storage") and conn.media_storage:
                # 保存图片
                file_path = await conn.media_storage.save_face_image(
                    device_id=conn.device_id,
                    image_data=jpeg_data,
                    user_id=user_id
                )
                
                # 记录元数据到数据库
                face_service = get_face_service(conn.logger)
                if face_service and face_service.db:
                    file_size = len(jpeg_data)
                    face_service.db.save_media_file(
                        device_id=conn.device_id,
                        file_type="face",
                        file_path=file_path,
                        file_size=file_size,
                        user_id=user_id
                    )
                    
                conn.logger.bind(tag=TAG).debug(f"保存人脸图片: {file_path}")
                return file_path
        except Exception as e:
            conn.logger.bind(tag=TAG).warning(f"保存人脸图片失败: {e}")
        return None

    async def _send_error(self, conn, message: str):
        """发送错误响应"""
        await conn.websocket.send(json.dumps({
            "type": "face_recognition",
            "status": "error",
            "error": message
        }))
