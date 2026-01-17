"""
心跳处理器（预留功能）
"""
import json
import time
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType

TAG = __name__


class HeartbeatHandler(TextMessageHandler):
    """处理 ESP32 心跳请求（预留功能）"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.HEARTBEAT

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理心跳请求
        
        请求格式:
        {
            "type": "heartbeat",
            "ts": 1702234567890,
            "uptime": 3600
        }
        
        响应格式:
        {
            "type": "heartbeat_ack",
            "ts": 1702234567891,
            "server_time": 1702234567891
        }
        """
        try:
            device_ts = msg_json.get("ts")
            uptime = msg_json.get("uptime")
            
            conn.logger.bind(tag=TAG).debug(
                f"心跳: device_ts={device_ts}, uptime={uptime}s"
            )
            
            # 发送心跳响应
            server_time = int(time.time() * 1000)
            await conn.websocket.send(json.dumps({
                "type": "heartbeat_ack",
                "ts": server_time,
                "server_time": server_time
            }))
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理心跳失败: {e}")
