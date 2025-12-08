"""
系统命令消息处理器
"""
import json
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.connection_manager import ConnectionManager

TAG = __name__


class SystemTextMessageHandler(TextMessageHandler):
    """系统命令消息处理器"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.SYSTEM

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        command = msg_json.get("command")

        if command == "start_monitor":
            await self._start_monitor(conn)
        elif command == "stop_monitor":
            await self._stop_monitor(conn)
        else:
            conn.logger.bind(tag=TAG).warning(f"未知系统命令: {command}")
            await self._send_error(conn, f"未知命令: {command}")

    async def _start_monitor(self, conn):
        """启动监控模式"""
        try:
            # 判断连接类型并获取 ESP32 连接
            manager = ConnectionManager.get_instance()
            
            if hasattr(conn, "client_type") and conn.client_type == "app":
                # App 发起的命令，需要切换 ESP32 的模式
                esp32_conn = manager.get_esp32_conn(conn.device_id)
                if esp32_conn:
                    esp32_conn.current_mode = "monitor"
                    conn.logger.bind(tag=TAG).info(f"ESP32 {conn.device_id} 监控模式已启动")
                    
                    # 停止 ESP32 的 TTS 音频发送
                    if hasattr(esp32_conn, "tts") and esp32_conn.tts:
                        if hasattr(esp32_conn.tts, "tts_audio_queue"):
                            try:
                                while not esp32_conn.tts.tts_audio_queue.empty():
                                    esp32_conn.tts.tts_audio_queue.get_nowait()
                            except Exception:
                                pass
                    
                    # 通知 ESP32 进入监控模式
                    await self._notify_esp32(conn, "start_monitor")
                else:
                    conn.logger.bind(tag=TAG).warning(f"ESP32 连接不可用: {conn.device_id}")
            else:
                # ESP32 自己发起的命令
                conn.current_mode = "monitor"
                conn.logger.bind(tag=TAG).info("监控模式已启动")
                
                # 停止 TTS 音频发送
                if hasattr(conn, "tts") and conn.tts:
                    if hasattr(conn.tts, "tts_audio_queue"):
                        try:
                            while not conn.tts.tts_audio_queue.empty():
                                conn.tts.tts_audio_queue.get_nowait()
                        except Exception:
                            pass

            # 返回成功响应
            await conn.websocket.send(
                json.dumps(
                    {"type": "system", "status": "success", "command": "start_monitor"}
                )
            )

        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"启动监控模式失败: {e}")
            await self._send_error(conn, f"启动监控模式失败: {str(e)}")

    async def _stop_monitor(self, conn):
        """停止监控模式"""
        try:
            # 判断连接类型并获取 ESP32 连接
            manager = ConnectionManager.get_instance()
            
            if hasattr(conn, "client_type") and conn.client_type == "app":
                # App 发起的命令，需要切换 ESP32 的模式
                esp32_conn = manager.get_esp32_conn(conn.device_id)
                if esp32_conn:
                    esp32_conn.current_mode = "normal"
                    conn.logger.bind(tag=TAG).info(f"ESP32 {conn.device_id} 监控模式已停止")
                    
                    # 通知 ESP32 退出监控模式
                    await self._notify_esp32(conn, "stop_monitor")
                else:
                    conn.logger.bind(tag=TAG).warning(f"ESP32 连接不可用: {conn.device_id}")
            else:
                # ESP32 自己发起的命令
                conn.current_mode = "normal"
                conn.logger.bind(tag=TAG).info("监控模式已停止")

            # 返回成功响应
            await conn.websocket.send(
                json.dumps(
                    {"type": "system", "status": "success", "command": "stop_monitor"}
                )
            )

        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"停止监控模式失败: {e}")
            await self._send_error(conn, f"停止监控模式失败: {str(e)}")

    async def _notify_esp32(self, conn, command: str):
        """通知 ESP32 模式切换

        Args:
            conn: 连接对象（可能是 ESP32 或 App）
            command: 命令（start_monitor 或 stop_monitor）
        """
        try:
            # 判断连接类型
            if hasattr(conn, "client_type") and conn.client_type == "app":
                # 如果是 App 发起的命令，需要转发给 ESP32
                manager = ConnectionManager.get_instance()
                esp32_conn = manager.get_esp32_conn(conn.device_id)

                if esp32_conn and esp32_conn.websocket:
                    await esp32_conn.websocket.send(
                        json.dumps({"type": "system", "command": command})
                    )
                    conn.logger.bind(tag=TAG).info(f"已通知 ESP32: {command}")
                else:
                    conn.logger.bind(tag=TAG).warning(
                        f"ESP32 连接不可用: {conn.device_id}"
                    )
            # 如果是 ESP32 自己发起的命令，不需要通知自己

        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"通知 ESP32 失败: {e}")

    async def _send_error(self, conn, message: str):
        """发送错误响应"""
        try:
            await conn.websocket.send(
                json.dumps({"type": "system", "status": "error", "message": message})
            )
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"发送错误响应失败: {e}")
