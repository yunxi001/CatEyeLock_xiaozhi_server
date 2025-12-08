"""
人脸识别消息处理器
"""
import json
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
            
            # 解析 BinaryProtocol2 格式图像
            try:
                jpeg_data = face_service.parse_image(image_data)
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
            
            # 构建响应
            response = {
                "type": "face_recognition",
                "result": result.result
            }
            
            if result.person:
                response["person"] = {
                    "id": result.person.id,
                    "name": result.person.name,
                    "relation": result.person.relation_type
                }
            
            response["access"] = {
                "granted": access_granted
            }
            if not access_granted and deny_reason:
                response["access"]["reason"] = deny_reason
            if access_granted:
                response["access"]["action"] = "open_door"
            
            # 发送 JSON 响应
            await self._send_result(conn, response)
            
            # 发送 TTS 语音（如果有问候语）
            if greeting:
                await self._send_tts(conn, greeting)
            
            # 推送通知给 App
            await self._notify_apps(conn, result, access_granted, visit_id)
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"人脸识别处理失败: {e}")
            await self._send_error(conn, str(e))

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

    async def _notify_apps(self, conn, result, access_granted: bool, visit_id: int):
        """推送到访通知给 App"""
        try:
            manager = ConnectionManager.get_instance()
            app_conns = manager.get_app_conns(conn.device_id)
            
            if not app_conns:
                return
            
            notification = {
                "type": "visit_notification",
                "data": {
                    "visit_id": visit_id,
                    "person_id": result.person.id if result.person else None,
                    "person_name": result.person.name if result.person else None,
                    "relation": result.person.relation_type if result.person else None,
                    "result": result.result,
                    "access_granted": access_granted
                }
            }
            
            for app_conn in app_conns:
                if app_conn.websocket:
                    await app_conn.websocket.send(json.dumps(notification))
                    
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"推送通知失败: {e}")

    async def _send_error(self, conn, message: str):
        """发送错误响应"""
        await conn.websocket.send(json.dumps({
            "type": "face_recognition",
            "status": "error",
            "error": message
        }))


class FaceManagementHandler(TextMessageHandler):
    """处理 App 人脸管理请求"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.FACE_MANAGEMENT

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        action = msg_json.get("action")
        
        handlers = {
            "register": self._handle_register,
            "get_persons": self._handle_get_persons,
            "get_person": self._handle_get_person,
            "delete_person": self._handle_delete_person,
            "update_permission": self._handle_update_permission,
            "get_visits": self._handle_get_visits
        }
        
        handler = handlers.get(action)
        if handler:
            await handler(conn, msg_json)
        else:
            conn.logger.bind(tag=TAG).warning(f"未知人脸管理动作: {action}")
            await self._send_response(conn, action, "error", error="unknown_action")

    async def _handle_register(self, conn, msg_json: Dict[str, Any]):
        """处理人脸录入"""
        try:
            face_service = get_face_service(conn.logger)
            data = msg_json.get("data", {})
            
            name = data.get("name")
            relation_type = data.get("relation_type", "other")
            images_b64 = data.get("images", [])
            permission = data.get("permission")
            
            if not name or not images_b64:
                await self._send_response(conn, "register", "error", error="missing_data")
                return
            
            # 解码图像
            images = []
            for img_b64 in images_b64:
                try:
                    # 尝试解析 BinaryProtocol2 格式
                    jpeg_data = face_service.parse_image(img_b64)
                    images.append(jpeg_data)
                except:
                    # 如果不是 BinaryProtocol2 格式，尝试直接 base64 解码
                    try:
                        images.append(base64.b64decode(img_b64))
                    except:
                        pass
            
            if not images:
                await self._send_response(conn, "register", "error", error="invalid_images")
                return
            
            # 录入人脸
            person_id, error = face_service.register_face(name, relation_type, images, permission)
            
            if error:
                await self._send_response(conn, "register", "error", error=error)
            else:
                await self._send_response(conn, "register", "success", person_id=person_id)
                
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"人脸录入失败: {e}")
            await self._send_response(conn, "register", "error", error=str(e))

    async def _handle_get_persons(self, conn, msg_json: Dict[str, Any]):
        """获取人员列表"""
        try:
            face_service = get_face_service(conn.logger)
            persons = face_service.get_persons()
            await self._send_response(conn, "get_persons", "success", data=persons)
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"获取人员列表失败: {e}")
            await self._send_response(conn, "get_persons", "error", error=str(e))

    async def _handle_get_person(self, conn, msg_json: Dict[str, Any]):
        """获取单个人员详情"""
        try:
            face_service = get_face_service(conn.logger)
            data = msg_json.get("data", {})
            person_id = data.get("person_id")
            
            if not person_id:
                await self._send_response(conn, "get_person", "error", error="missing_person_id")
                return
            
            person = face_service.get_person(person_id)
            if person:
                await self._send_response(conn, "get_person", "success", data=person)
            else:
                await self._send_response(conn, "get_person", "error", error="person_not_found")
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"获取人员详情失败: {e}")
            await self._send_response(conn, "get_person", "error", error=str(e))

    async def _handle_delete_person(self, conn, msg_json: Dict[str, Any]):
        """删除人员"""
        try:
            face_service = get_face_service(conn.logger)
            data = msg_json.get("data", {})
            person_id = data.get("person_id")
            
            if not person_id:
                await self._send_response(conn, "delete_person", "error", error="missing_person_id")
                return
            
            success = face_service.delete_person(person_id)
            if success:
                await self._send_response(conn, "delete_person", "success")
            else:
                await self._send_response(conn, "delete_person", "error", error="delete_failed")
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"删除人员失败: {e}")
            await self._send_response(conn, "delete_person", "error", error=str(e))

    async def _handle_update_permission(self, conn, msg_json: Dict[str, Any]):
        """更新权限"""
        try:
            face_service = get_face_service(conn.logger)
            data = msg_json.get("data", {})
            person_id = data.get("person_id")
            permission = data.get("permission")
            
            if not person_id or not permission:
                await self._send_response(conn, "update_permission", "error", error="missing_data")
                return
            
            success = face_service.update_permission(person_id, permission)
            if success:
                await self._send_response(conn, "update_permission", "success")
            else:
                await self._send_response(conn, "update_permission", "error", error="update_failed")
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"更新权限失败: {e}")
            await self._send_response(conn, "update_permission", "error", error=str(e))

    async def _handle_get_visits(self, conn, msg_json: Dict[str, Any]):
        """获取到访记录"""
        try:
            face_service = get_face_service(conn.logger)
            data = msg_json.get("data", {})
            
            page = data.get("page", 1)
            page_size = data.get("page_size", 20)
            date_from = data.get("date_from")
            date_to = data.get("date_to")
            
            result = face_service.get_visits(page, page_size, date_from, date_to)
            await self._send_response(conn, "get_visits", "success", data=result)
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"获取到访记录失败: {e}")
            await self._send_response(conn, "get_visits", "error", error=str(e))

    async def _send_response(self, conn, action: str, status: str, **kwargs):
        """发送响应"""
        response = {
            "type": "face_management",
            "action": action,
            "status": status
        }
        response.update(kwargs)
        await conn.websocket.send(json.dumps(response))
