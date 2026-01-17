"""
ACK 响应处理器
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
        
        消息格式:
        {
            "type": "ack",
            "msg_id": "cmd_88293",
            "code": 0,
            "msg": "OK"
        }
        
        错误码:
        - 0: 成功
        - 1: 设备忙碌
        - 2: 参数错误
        - 3: 硬件故障
        - 4: 超时
        - 5: 未授权
        - 6: 资源不足
        - 7: 不支持
        """
        try:
            msg_id = msg_json.get("msg_id")
            code = msg_json.get("code", 0)
            msg = msg_json.get("msg", "")
            
            if code == 0:
                conn.logger.bind(tag=TAG).debug(f"ACK 成功: msg_id={msg_id}")
            else:
                conn.logger.bind(tag=TAG).warning(
                    f"ACK 失败: msg_id={msg_id}, code={code}, msg={msg}"
                )
            
            # 执行等待回调（如果有）
            if hasattr(conn, "_pending_commands") and msg_id in conn._pending_commands:
                callback = conn._pending_commands.pop(msg_id)
                if callback:
                    await callback(code, msg)
            
            # 转发 ACK 给关联的 App（协议 v2.2）
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
