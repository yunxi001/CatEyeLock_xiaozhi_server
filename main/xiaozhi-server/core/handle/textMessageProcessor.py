import json
from typing import Dict, Any

from core.handle.textMessageHandlerRegistry import TextMessageHandlerRegistry
from core.connection_manager import ConnectionManager

TAG = __name__


class TextMessageProcessor:
    """消息处理器主类"""

    def __init__(self, registry: TextMessageHandlerRegistry):
        self.registry = registry

    async def process_message(self, conn, message: str) -> None:
        """处理消息的主入口"""
        try:
            # 解析JSON消息
            msg_json = json.loads(message)

            # 处理JSON消息
            if isinstance(msg_json, dict):
                # 优先处理 forward 字段
                if msg_json.get("forward") == True:
                    await self._handle_forward(conn, msg_json)
                    return

                # 再进行 type 分发处理
                message_type = msg_json.get("type")

                # 记录日志
                conn.logger.bind(tag=TAG).info(f"收到{message_type}消息：{message}")

                # 获取并执行处理器
                handler = self.registry.get_handler(message_type)
                if handler:
                    await handler.handle(conn, msg_json)
                else:
                    conn.logger.bind(tag=TAG).error(f"收到未知类型消息：{message}")
            # 处理纯数字消息
            elif isinstance(msg_json, int):
                conn.logger.bind(tag=TAG).info(f"收到数字消息：{message}")
                await conn.websocket.send(message)

        except json.JSONDecodeError:
            # 非JSON消息直接转发
            conn.logger.bind(tag=TAG).error(f"解析到错误的消息：{message}")
            await conn.websocket.send(message)

    async def _handle_forward(self, conn, msg_json: Dict[str, Any]):
        """处理需要转发的消息"""
        try:
            # 删除 forward 字段
            del msg_json["forward"]
            forward_msg = json.dumps(msg_json, ensure_ascii=False)

            manager = ConnectionManager.get_instance()

            # 判断消息来源并转发
            if hasattr(conn, "client_type") and conn.client_type == "app":
                # App → ESP32
                esp32_conn = manager.get_esp32_conn(conn.device_id)
                if esp32_conn and esp32_conn.websocket:
                    await esp32_conn.websocket.send(forward_msg)
                    conn.logger.bind(tag=TAG).debug(f"转发消息到 ESP32: {forward_msg}")
                else:
                    conn.logger.bind(tag=TAG).warning(
                        f"ESP32 连接不可用: {conn.device_id}"
                    )
            else:
                # ESP32 → App
                app_conns = manager.get_app_conns(conn.device_id)
                for app_conn in app_conns:
                    if app_conn.websocket:
                        await app_conn.websocket.send(forward_msg)
                conn.logger.bind(tag=TAG).debug(
                    f"转发消息到 {len(app_conns)} 个 App: {forward_msg}"
                )

        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发消息失败: {e}")
