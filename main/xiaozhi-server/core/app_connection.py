"""
App 端连接处理器
"""
import json
import asyncio
import websockets
from typing import Dict, Any
from config.logger import setup_logging
from core.connection_manager import ConnectionManager
from core.handle.textHandle import handleTextMessage
from core.utils.opus_encoder_utils import OpusEncoderUtils

TAG = __name__


class AppConnectionHandler:
    """App 端连接处理器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.websocket = None
        self.device_id = None
        self.authenticated = False
        self.logger = setup_logging()
        self.client_type = "app"
        
        # OPUS 编码器，用于将 App 发送的 PCM 音频编码为 OPUS
        self.opus_encoder = None

    async def handle_connection(self, ws):
        """处理 App WebSocket 连接"""
        try:
            self.websocket = ws
            self.logger.bind(tag=TAG).info(f"App 客户端连接: {ws.remote_address}")

            # 等待 hello 消息进行认证
            try:
                hello_msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                if not await self._authenticate(hello_msg):
                    await ws.close()
                    return
            except asyncio.TimeoutError:
                self.logger.bind(tag=TAG).warning("App 认证超时")
                await ws.close()
                return

            # 认证成功，开始处理消息
            try:
                async for message in ws:
                    await self._route_message(message)
            except websockets.exceptions.ConnectionClosed:
                self.logger.bind(tag=TAG).info("App 客户端断开连接")

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"App 连接处理错误: {e}")
        finally:
            await self._cleanup()

    async def _authenticate(self, message: str) -> bool:
        """认证 App 连接

        Args:
            message: hello 消息

        Returns:
            True 如果认证成功，否则 False
        """
        try:
            msg_json = json.loads(message)

            # 验证消息格式
            if msg_json.get("type") != "hello":
                await self._send_error("期望收到 hello 消息")
                return False

            if msg_json.get("client_type") != "app":
                await self._send_error("client_type 必须为 app")
                return False

            device_id = msg_json.get("device_id")
            if not device_id:
                await self._send_error("缺少 device_id")
                return False

            # 验证对应的 ESP32 是否在线
            manager = ConnectionManager.get_instance()
            if not manager.is_esp32_online(device_id):
                await self._send_error(f"设备 {device_id} 不在线")
                return False

            # 认证成功
            self.device_id = device_id
            self.authenticated = True

            # 注册到 ConnectionManager
            manager.register_app(device_id, self)

            # 获取 ESP32 连接信息
            esp32_conn = manager.get_esp32_conn(device_id)
            current_mode = getattr(esp32_conn, "current_mode", "normal")

            # 发送成功响应
            await self.websocket.send(
                json.dumps(
                    {
                        "type": "hello",
                        "status": "ok",
                        "device_info": {"online": True, "mode": current_mode},
                    }
                )
            )

            self.logger.bind(tag=TAG).info(f"App 认证成功: device_id={device_id}")
            return True

        except json.JSONDecodeError:
            await self._send_error("消息格式错误")
            return False
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"认证失败: {e}")
            await self._send_error(f"认证失败: {str(e)}")
            return False

    async def _send_error(self, message: str):
        """发送错误响应"""
        try:
            await self.websocket.send(
                json.dumps({"type": "hello", "status": "error", "message": message})
            )
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"发送错误响应失败: {e}")

    async def _route_message(self, message):
        """消息路由"""
        if isinstance(message, str):
            await self._handle_text_message(message)
        elif isinstance(message, bytes):
            await self._handle_binary_message(message)

    async def _handle_text_message(self, message: str):
        """处理文本消息"""
        try:
            msg_json = json.loads(message)

            # 检查 forward 字段
            if msg_json.get("forward") == True:
                await self._forward_to_esp32(msg_json)
            else:
                # 其他消息类型处理（如系统命令、查询状态等）
                # 使用统一的文本消息处理器
                await handleTextMessage(self, message)

        except json.JSONDecodeError:
            self.logger.bind(tag=TAG).error(f"解析 App 消息失败: {message}")
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"处理 App 文本消息失败: {e}")

    async def _handle_binary_message(self, message: bytes):
        """处理二进制消息（App 发送的 PCM 音频，用于对讲）
        
        App 发送的是 16-bit PCM 音频（24kHz, 单声道）
        需要编码为 OPUS 后发送给 ESP32
        ESP32 接收的音频格式：24kHz, 单声道, 60ms 帧
        """
        try:
            manager = ConnectionManager.get_instance()
            esp32_conn = manager.get_esp32_conn(self.device_id)

            if not esp32_conn or not esp32_conn.websocket:
                self.logger.bind(tag=TAG).warning(
                    f"ESP32 连接不可用: {self.device_id}"
                )
                return
            
            # 初始化 OPUS 编码器（延迟初始化）
            # 使用 24kHz 采样率，与服务器 TTS 发送给 ESP32 的格式一致
            if self.opus_encoder is None:
                self.opus_encoder = OpusEncoderUtils(
                    sample_rate=24000, channels=1, frame_size_ms=60
                )
                self.logger.bind(tag=TAG).info("OPUS 编码器已初始化 (24kHz)")
            
            # 将 App 发送的 PCM 编码为 OPUS 后发送给 ESP32
            def send_opus_callback(opus_data):
                """OPUS 编码回调，发送给 ESP32"""
                # 发送给 ESP32
                asyncio.run_coroutine_threadsafe(
                    esp32_conn.websocket.send(opus_data),
                    asyncio.get_event_loop()
                )
            
            # 编码 PCM 为 OPUS
            self.opus_encoder.encode_pcm_to_opus_stream(
                message, 
                end_of_stream=False, 
                callback=send_opus_callback
            )
            
            self.logger.bind(tag=TAG).debug(
                f"App PCM 音频已编码并转发: {len(message)} bytes"
            )

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"处理 App 音频失败: {e}")

    async def _forward_to_esp32(self, msg_json: Dict[str, Any]):
        """转发消息到 ESP32"""
        try:
            # 删除 forward 字段
            if "forward" in msg_json:
                del msg_json["forward"]

            forward_msg = json.dumps(msg_json, ensure_ascii=False)

            # 获取 ESP32 连接
            manager = ConnectionManager.get_instance()
            esp32_conn = manager.get_esp32_conn(self.device_id)

            if esp32_conn and esp32_conn.websocket:
                await esp32_conn.websocket.send(forward_msg)
                self.logger.bind(tag=TAG).debug(f"转发消息到 ESP32: {forward_msg}")
            else:
                self.logger.bind(tag=TAG).warning(
                    f"ESP32 连接不可用: {self.device_id}"
                )

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"转发消息到 ESP32 失败: {e}")

    async def _cleanup(self):
        """清理资源"""
        try:
            # 从 ConnectionManager 注销
            if self.device_id:
                manager = ConnectionManager.get_instance()
                manager.unregister_app(self.device_id, self)

            # 关闭 OPUS 编码器
            if self.opus_encoder:
                self.opus_encoder.close()
                self.opus_encoder = None

            # 关闭 WebSocket
            if self.websocket:
                try:
                    await self.websocket.close()
                except Exception:
                    pass

            self.logger.bind(tag=TAG).info("App 连接资源已清理")

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"清理 App 连接资源失败: {e}")
