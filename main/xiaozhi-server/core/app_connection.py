"""
App 端连接处理器

协议版本: v6.0
- 支持 app_id 身份标识
- hello 认证成功后返回 JWT token（供 HTTP API 认证）
"""
import json
import time
import asyncio
import websockets
from typing import Dict, Any
from config.logger import setup_logging
from core.connection_manager import ConnectionManager
from core.handle.textHandle import handleTextMessage
from core.utils.opus_encoder_utils import OpusEncoderUtils
from core.utils.auth import AuthToken

TAG = __name__


class AppConnectionHandler:
    """App 端连接处理器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.websocket = None
        self.device_id = None
        self.app_id = None  # App 用户标识
        self.authenticated = False
        self.logger = setup_logging()
        self.client_type = "app"
        
        # OPUS 编码器，用于将 App 发送的 PCM 音频编码为 OPUS
        self.opus_encoder = None

        # JWT token 生成器（用于 HTTP API 认证）
        auth_key = config.get("server", {}).get("auth_key", "")
        self.auth = AuthToken(auth_key) if auth_key else None

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

            # 提取 app_id
            app_id = msg_json.get("app_id")
            if not app_id:
                await self._send_error("缺少 app_id")
                return False

            # 认证成功
            self.device_id = device_id
            self.app_id = app_id
            self.authenticated = True

            # 注册到 ConnectionManager
            manager = ConnectionManager.get_instance()
            manager.register_app(device_id, self)

            # 检查 ESP32 是否在线，并获取设备信息
            is_online = manager.is_esp32_online(device_id)
            esp32_conn = manager.get_esp32_conn(device_id)
            current_mode = getattr(esp32_conn, "current_mode", "normal") if esp32_conn else "normal"

            # 生成 JWT token（供 App 后续 HTTP API 请求认证使用）
            token = None
            if self.auth:
                token = self.auth.generate_token(self.device_id)

            # 发送成功响应（无论设备是否在线都允许连接）
            response = {
                "type": "hello",
                "status": "ok",
                "device_info": {
                    "online": is_online,
                    "mode": current_mode
                },
            }
            if token:
                response["token"] = token

            await self.websocket.send(json.dumps(response))

            self.logger.bind(tag=TAG).info(
                f"App 认证成功: device_id={device_id}, app_id={app_id}, "
                f"设备在线={is_online}"
            )

            # 认证成功后，主动推送设备状态信息
            await self._push_initial_device_status(is_online, esp32_conn)

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

    async def _push_initial_device_status(self, is_online: bool, esp32_conn):
        """App 连接成功后，主动推送设备状态信息
        
        Args:
            is_online: 设备是否在线
            esp32_conn: ESP32 连接对象（如果在线）
        """
        try:
            # 1. 推送设备在线/离线通知
            status_notification = {
                "type": "device_status",
                "status": "online" if is_online else "offline",
                "device_id": self.device_id,
                "ts": int(time.time() * 1000)
            }
            
            if not is_online:
                status_notification["reason"] = "device_offline"
            
            await self.websocket.send(json.dumps(status_notification))
            self.logger.bind(tag=TAG).info(
                f"已推送设备状态通知: device_id={self.device_id}, "
                f"status={'在线' if is_online else '离线'}"
            )
            
            # 2. 如果设备在线，推送详细的设备状态信息
            if is_online and esp32_conn:
                device_state = getattr(esp32_conn, "device_state", None)
                
                if device_state:
                    # 推送完整的设备状态
                    state_response = {
                        "type": "device_state_full",
                        "ts": int(time.time() * 1000),
                        "device_id": self.device_id,
                        "state": device_state
                    }
                    
                    await self.websocket.send(json.dumps(state_response))
                    self.logger.bind(tag=TAG).info(
                        f"已推送完整设备状态: device_id={self.device_id}, "
                        f"state_keys={list(device_state.keys())}"
                    )
                else:
                    self.logger.bind(tag=TAG).debug(
                        f"设备在线但暂无状态数据: device_id={self.device_id}"
                    )
            else:
                # 设备离线，推送空状态或最后已知状态
                self.logger.bind(tag=TAG).info(
                    f"设备离线，无法推送详细状态: device_id={self.device_id}"
                )
                
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"推送初始设备状态失败: {e}")

    async def _route_message(self, message):
        """消息路由"""
        if isinstance(message, str):
            await self._handle_text_message(message)
        elif isinstance(message, bytes):
            await self._handle_binary_message(message)

    async def _handle_text_message(self, message: str):
        """处理文本消息

        协议 v6.0:
        - 不再检查 seq_id 防重放
        - 不再发送 server_ack
        """
        try:
            msg_json = json.loads(message)
            msg_type = msg_json.get("type")

            # 认证检查（非hello消息需要先认证）
            if msg_type != "hello" and not self.authenticated:
                await self.websocket.send(json.dumps({
                    "type": "error", "message": "请先认证"
                }))
                return

            # 统一使用 Handler 处理消息
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

    async def _handle_get_device_status(self):
        """处理获取设备状态请求"""
        try:
            manager = ConnectionManager.get_instance()
            esp32_conn = manager.get_esp32_conn(self.device_id)
            is_online = esp32_conn is not None
            
            self.logger.bind(tag=TAG).info(
                f"处理设备状态查询: device_id={self.device_id}, "
                f"app_id={self.app_id}, 设备在线={is_online}"
            )

            # 构建设备状态信息
            status_data = {
                "type": "device_status_response",
                "ts": int(time.time() * 1000),
                "device_id": self.device_id,
                "online": is_online,
            }

            # 如果设备在线，获取更多状态信息
            if esp32_conn:
                status_data["mode"] = getattr(esp32_conn, "current_mode", "normal")
                
                # 获取设备状态（灯、门、传感器等）
                device_state = getattr(esp32_conn, "device_state", {})
                status_data["state"] = device_state
                
                self.logger.bind(tag=TAG).info(
                    f"设备在线，返回状态: mode={status_data['mode']}, "
                    f"state_keys={list(device_state.keys())}"
                )
            else:
                self.logger.bind(tag=TAG).info(
                    f"设备离线，返回基本信息: device_id={self.device_id}"
                )
            
            # 发送状态响应
            await self.websocket.send(json.dumps(status_data))
            self.logger.bind(tag=TAG).info(
                f"已发送设备状态响应: device_id={self.device_id}, "
                f"online={is_online}, data_size={len(json.dumps(status_data))} bytes"
            )
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"处理设备状态请求失败: {e}")

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
