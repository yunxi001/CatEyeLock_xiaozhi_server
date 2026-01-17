"""
数据查询消息处理器

协议版本: v2.2
支持查询:
- status: 当前设备状态
- status_history: 历史状态
- events: 事件历史
- unlock_logs: 开锁日志
- media_files: 媒体文件列表
"""
import json
from typing import Dict, Any, Optional
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.connection_manager import ConnectionManager
from core.handle.textHandler.faceRecognitionHandler import get_face_service

TAG = __name__


def _get_database(conn):
    """获取数据库实例
    
    优先从 FaceService 获取，确保使用同一个数据库连接池
    """
    try:
        face_service = get_face_service(conn.logger)
        return face_service.db
    except Exception:
        return None


class QueryHandler(TextMessageHandler):
    """处理 App 数据查询请求"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.QUERY

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        # 仅处理 App 发送的查询
        if not hasattr(conn, "client_type") or conn.client_type != "app":
            return
        
        target = msg_json.get("target")
        data = msg_json.get("data", {})
        
        conn.logger.bind(tag=TAG).info(f"收到数据查询请求: target={target}")
        
        handlers = {
            "status": self._query_status,
            "status_history": self._query_status_history,
            "events": self._query_events,
            "unlock_logs": self._query_unlock_logs,
            "media_files": self._query_media_files,
        }
        
        handler = handlers.get(target)
        if handler:
            await handler(conn, data)
        else:
            await self._send_error(conn, target, f"未知查询目标: {target}")

    async def _query_status(self, conn, data: Dict):
        """查询当前设备状态（从内存缓存读取）"""
        try:
            # 获取 ESP32 连接，读取缓存的状态
            manager = ConnectionManager.get_instance()
            esp32_conn = manager.get_esp32_conn(conn.device_id)
            
            if esp32_conn and hasattr(esp32_conn, "device_status"):
                status = esp32_conn.device_status
                await self._send_response(conn, "status", {
                    "battery": status.get("bat", 0),
                    "lux": status.get("lux", 0),
                    "lock_state": status.get("lock", 0),
                    "light_state": status.get("light", 0),
                    "last_update": status.get("ts", 0)
                })
            else:
                # 尝试从数据库读取最新状态
                db = _get_database(conn)
                if db:
                    status = db.get_latest_status(conn.device_id)
                    if status:
                        await self._send_response(conn, "status", status)
                        return
                
                await self._send_error(conn, "status", "暂无设备状态数据")
                
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"查询设备状态失败: {e}")
            await self._send_error(conn, "status", str(e))

    async def _query_status_history(self, conn, data: Dict):
        """查询历史状态"""
        try:
            limit = min(data.get("limit", 100), 500)
            offset = data.get("offset", 0)
            
            db = _get_database(conn)
            if not db:
                await self._send_error(conn, "status_history", "数据库不可用")
                return
            
            records, total = db.get_status_history(
                device_id=conn.device_id,
                limit=limit,
                offset=offset
            )
            
            await self._send_response(conn, "status_history", {
                "records": records,
                "total": total,
                "limit": limit,
                "offset": offset
            })
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"查询历史状态失败: {e}")
            await self._send_error(conn, "status_history", str(e))

    async def _query_events(self, conn, data: Dict):
        """查询事件历史"""
        try:
            event_type = data.get("event_type")
            limit = min(data.get("limit", 100), 500)
            offset = data.get("offset", 0)
            
            db = _get_database(conn)
            if not db:
                await self._send_error(conn, "events", "数据库不可用")
                return
            
            records, total = db.get_events(
                device_id=conn.device_id,
                event_type=event_type,
                limit=limit,
                offset=offset
            )
            
            await self._send_response(conn, "events", {
                "records": records,
                "total": total,
                "limit": limit,
                "offset": offset
            })
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"查询事件历史失败: {e}")
            await self._send_error(conn, "events", str(e))

    async def _query_unlock_logs(self, conn, data: Dict):
        """查询开锁日志"""
        try:
            method = data.get("method")
            result = data.get("result")
            limit = min(data.get("limit", 100), 500)
            offset = data.get("offset", 0)
            
            db = _get_database(conn)
            if not db:
                await self._send_error(conn, "unlock_logs", "数据库不可用")
                return
            
            records, total = db.get_unlock_logs(
                device_id=conn.device_id,
                method=method,
                result=result,
                limit=limit,
                offset=offset
            )
            
            await self._send_response(conn, "unlock_logs", {
                "records": records,
                "total": total,
                "limit": limit,
                "offset": offset
            })
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"查询开锁日志失败: {e}")
            await self._send_error(conn, "unlock_logs", str(e))

    async def _query_media_files(self, conn, data: Dict):
        """查询媒体文件列表"""
        try:
            file_type = data.get("file_type")
            date_from = data.get("date_from")
            date_to = data.get("date_to")
            limit = min(data.get("limit", 100), 500)
            offset = data.get("offset", 0)
            
            db = _get_database(conn)
            if not db:
                await self._send_error(conn, "media_files", "数据库不可用")
                return
            
            records, total = db.get_media_files(
                device_id=conn.device_id,
                file_type=file_type,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                offset=offset
            )
            
            await self._send_response(conn, "media_files", {
                "records": records,
                "total": total,
                "limit": limit,
                "offset": offset
            })
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"查询媒体文件失败: {e}")
            await self._send_error(conn, "media_files", str(e))

    async def _send_response(self, conn, target: str, data: Any):
        """发送查询响应"""
        try:
            await conn.websocket.send(json.dumps({
                "type": "query_result",
                "target": target,
                "status": "success",
                "data": data
            }))
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"发送查询响应失败: {e}")

    async def _send_error(self, conn, target: str, error: str):
        """发送错误响应"""
        try:
            await conn.websocket.send(json.dumps({
                "type": "query_result",
                "target": target,
                "status": "error",
                "error": error
            }))
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"发送错误响应失败: {e}")
