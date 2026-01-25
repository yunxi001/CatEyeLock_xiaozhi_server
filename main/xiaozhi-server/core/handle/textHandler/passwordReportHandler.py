"""
密码查询结果上报处理器
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
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"获取数据库实例失败: {e}")
        return None


class PasswordReportHandler(TextMessageHandler):
    """处理 ESP32 密码查询结果上报
    
    注意：密码查询结果会更新到服务器数据库，并转发给请求查询的 App
    """

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.PASSWORD_REPORT

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理密码查询结果上报
        
        消息格式:
        {
            "type": "password_report",
            "ts": 1702234567890,
            "data": {
                "password": "123456"
            }
        }
        
        处理逻辑:
        1. 解析 ts 和 data.password 字段
        2. 记录 INFO 级别日志（不记录密码明文）
        3. 更新服务器数据库中的密码
        4. 转发到请求查询的 App
        """
        try:
            ts = msg_json.get("ts")
            data = msg_json.get("data", {})
            
            password = data.get("password")
            
            # 验证必需字段
            if password is None:
                conn.logger.bind(tag=TAG).error("缺少 password 字段")
                return
            
            # 记录日志（不记录密码明文，仅记录是否存在）
            conn.logger.bind(tag=TAG).info(
                f"收到密码上报: device_id={conn.device_id}, password_length={len(str(password))}, ts={ts}"
            )
            
            # 更新服务器数据库中的密码
            await self._update_password_to_database(conn, password)
            
            # 转发给关联的 App
            await self._forward_to_apps(conn, msg_json)
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理密码查询结果失败: {e}")

    async def _update_password_to_database(self, conn, password: str):
        """更新密码到数据库
        
        Args:
            conn: 连接对象
            password: 密码明文
        """
        try:
            db = _get_database(conn)
            if not db:
                conn.logger.bind(tag=TAG).warning("数据库不可用，无法更新密码")
                return
            
            # 更新设备密码
            success = db.update_device_password(conn.device_id, password)
            if success:
                conn.logger.bind(tag=TAG).info(f"设备 {conn.device_id} 密码已更新到数据库")
            else:
                conn.logger.bind(tag=TAG).warning(f"设备 {conn.device_id} 密码更新失败")
                
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"更新密码到数据库失败: {e}")

    async def _forward_to_apps(self, conn, msg_json: Dict[str, Any]):
        """转发密码查询结果到所有关联的 App
        
        Args:
            conn: 连接对象
            msg_json: 消息 JSON
        """
        try:
            manager = ConnectionManager.get_instance()
            app_conns = manager.get_app_conns(conn.device_id)
            
            if not app_conns:
                conn.logger.bind(tag=TAG).debug("没有关联的 App 连接，无需转发")
                return
            
            for app_conn in app_conns:
                if app_conn.websocket:
                    await app_conn.websocket.send(json.dumps(msg_json))
                    conn.logger.bind(tag=TAG).debug(f"密码已转发到 App: app_id={app_conn.app_id}")
                    
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发密码查询结果失败: {e}")
