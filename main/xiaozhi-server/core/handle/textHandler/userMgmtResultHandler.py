"""
用户管理结果处理器
"""
import json
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.connection_manager import ConnectionManager

TAG = __name__


class UserMgmtResultHandler(TextMessageHandler):
    """处理 ESP32 用户管理结果上报"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.USER_MGMT_RESULT

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理用户管理结果
        
        消息格式:
        {
            "type": "user_mgmt_result",
            "category": "finger",
            "command": "add",
            "result": true,
            "val": 6,
            "msg": "Success"
        }
        
        category: finger/nfc/password
        command: add/del/clear/query/set
        val: 成功时=分配的ID/查询数量，失败时=错误码
        """
        try:
            category = msg_json.get("category")
            command = msg_json.get("command")
            result = msg_json.get("result")
            val = msg_json.get("val")
            msg = msg_json.get("msg", "")
            
            if result:
                conn.logger.bind(tag=TAG).info(
                    f"用户管理成功: {category}/{command}, val={val}"
                )
            else:
                conn.logger.bind(tag=TAG).warning(
                    f"用户管理失败: {category}/{command}, error={val}, msg={msg}"
                )
            
            # 转发给关联的 App
            await self._forward_to_apps(conn, msg_json)
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理用户管理结果失败: {e}")

    async def _forward_to_apps(self, conn, msg_json: Dict[str, Any]):
        """转发结果到所有关联的 App"""
        try:
            manager = ConnectionManager.get_instance()
            app_conns = manager.get_app_conns(conn.device_id)
            
            if not app_conns:
                return
            
            for app_conn in app_conns:
                if app_conn.websocket:
                    await app_conn.websocket.send(json.dumps(msg_json))
                    
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发结果失败: {e}")
