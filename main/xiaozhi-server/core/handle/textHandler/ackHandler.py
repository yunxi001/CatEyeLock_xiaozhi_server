"""
ACK 响应处理器

协议 v6.0: ack 只包含 {type, code, msg}，code 为 0（成功）或 1（失败）
"""
import json
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.connection_manager import ConnectionManager

TAG = __name__


class AckHandler(TextMessageHandler):
    """处理 ESP32 ACK 响应"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.ACK

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理 ACK 响应

        消息格式 (v6.0):
        {
            "type": "ack",
            "code": 0,    # 0=成功, 1=失败
            "msg": "OK"
        }
        """
        try:
            code = msg_json.get("code", 0)
            msg = msg_json.get("msg", "")

            # 记录日志
            if code == 0:
                conn.logger.bind(tag=TAG).debug("ACK 成功")
            else:
                conn.logger.bind(tag=TAG).warning(
                    f"ACK 失败: code={code}, msg={msg}"
                )

            # 转发 ACK 给关联的 App
            await self._forward_to_apps(conn, msg_json)

        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理 ACK 失败: {e}")

    async def _forward_to_apps(self, conn, msg_json: Dict[str, Any]):
        """转发 ACK 到所有关联的 App"""
        try:
            manager = ConnectionManager.get_instance()
            app_conns = manager.get_app_conns(conn.device_id)

            if not app_conns:
                return

            msg = json.dumps(msg_json)
            for app_conn in app_conns:
                if app_conn.websocket:
                    await app_conn.websocket.send(msg)

            conn.logger.bind(tag=TAG).debug(f"ACK 已转发给 {len(app_conns)} 个 App")

        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发 ACK 失败: {e}")
