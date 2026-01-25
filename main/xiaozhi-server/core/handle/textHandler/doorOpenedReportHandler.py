"""
开门日志上报处理器
"""
import json
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.connection_manager import ConnectionManager
from core.handle.textHandler.faceRecognitionHandler import get_face_service

TAG = __name__


def _get_database(conn):
    """获取数据库实例"""
    try:
        face_service = get_face_service(conn.logger)
        return face_service.db
    except Exception:
        return None


class DoorOpenedReportHandler(TextMessageHandler):
    """处理 ESP32 开门日志上报"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.DOOR_OPENED_REPORT

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理开门日志上报
        
        消息格式:
        {
            "type": "door_opened_report",
            "ts": 1702234567890,
            "data": {
                "method": "finger",   # 开锁方式
                "source": "outside"   # 开门来源: outside/inside/unknown
            }
        }
        
        method 取值:
        - finger: 指纹开锁
        - nfc: NFC 开锁
        - face: 人脸开锁
        - pwd: 密码开锁
        - temp_pwd: 临时密码开锁
        - key: 机械钥匙
        - remote: 远程开锁
        
        source 取值:
        - outside: 从外侧开门
        - inside: 从内侧开门
        - unknown: 未知来源
        """
        try:
            ts = msg_json.get("ts")
            data = msg_json.get("data", {})
            
            method = data.get("method")
            source = data.get("source")
            
            # 验证必需字段
            if not method:
                conn.logger.bind(tag=TAG).error("缺少 method 字段")
                return
            
            if not source:
                conn.logger.bind(tag=TAG).error("缺少 source 字段")
                return
            
            # 验证 method 取值范围
            valid_methods = ["finger", "nfc", "face", "pwd", "temp_pwd", "key", "remote"]
            if method not in valid_methods:
                conn.logger.bind(tag=TAG).warning(
                    f"无效的 method: {method}，有效值: {valid_methods}"
                )
            
            # 验证 source 取值范围
            valid_sources = ["outside", "inside", "unknown"]
            if source not in valid_sources:
                conn.logger.bind(tag=TAG).warning(
                    f"无效的 source: {source}，有效值: {valid_sources}"
                )
            
            # 记录日志
            conn.logger.bind(tag=TAG).info(
                f"开门日志: method={method}, source={source}, ts={ts}"
            )
            
            # 持久化到数据库
            await self._save_to_database(conn, method, source)
            
            # 转发给关联的 App
            await self._forward_to_apps(conn, msg_json)
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理开门日志失败: {e}")

    async def _save_to_database(self, conn, method: str, source: str):
        """保存开门日志到数据库
        
        Args:
            conn: 连接对象
            method: 开锁方式
            source: 开门来源
        """
        try:
            db = _get_database(conn)
            if db:
                db.save_door_opened_log(
                    device_id=conn.device_id,
                    method=method,
                    source=source
                )
        except Exception as e:
            # 数据库失败不影响转发
            conn.logger.bind(tag=TAG).warning(f"保存开门日志到数据库失败: {e}")

    async def _forward_to_apps(self, conn, msg_json: Dict[str, Any]):
        """转发日志到所有关联的 App
        
        Args:
            conn: 连接对象
            msg_json: 消息 JSON
        """
        try:
            manager = ConnectionManager.get_instance()
            app_conns = manager.get_app_conns(conn.device_id)
            
            if not app_conns:
                return
            
            for app_conn in app_conns:
                if app_conn.websocket:
                    await app_conn.websocket.send(json.dumps(msg_json))
                    
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发开门日志失败: {e}")
