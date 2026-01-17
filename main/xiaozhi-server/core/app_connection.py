"""
App 端连接处理器

协议版本: v2.2
- 支持 app_id 身份标识
- 支持 server_ack 消息确认机制
- 支持 seq_id 防重放
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
from core.utils.seq_id_cache import SeqIdCache

TAG = __name__


class AppConnectionHandler:
    """App 端连接处理器"""
    
    # 类级别的 seq_id 缓存（所有连接共享）
    _seq_id_cache = SeqIdCache(max_size=100)

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

            self.logger.bind(tag=TAG).info(f"App 认证成功: device_id={device_id}, app_id={app_id}")
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
        """处理文本消息
        
        协议 v2.2:
        - 所有消息统一走 Handler 处理
        - 支持 seq_id 防重放
        - 返回 server_ack 确认
        """
        try:
            msg_json = json.loads(message)
            seq_id = msg_json.get("seq_id")
            
            # 如果有 seq_id，进行防重放检查并返回 server_ack
            if seq_id:
                # 检查是否重复消息
                if not self._seq_id_cache.check_and_add(self.app_id, seq_id):
                    await self._send_server_ack(seq_id, code=5, msg="重复消息")
                    self.logger.bind(tag=TAG).debug(f"忽略重复消息: seq_id={seq_id}")
                    return
                
                # 先发送 ACK 确认收到
                await self._send_server_ack(seq_id, code=0, msg="已接收")
            
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

    async def _send_server_ack(self, seq_id: str, code: int, msg: str):
        """发送服务器 ACK 确认
        
        Args:
            seq_id: App 发送的消息序列号
            code: 状态码（0=成功, 1=设备离线, 2=参数错误, 3=未认证, 4=内部错误, 5=重复消息）
            msg: 状态描述
        """
        try:
            await self.websocket.send(json.dumps({
                "type": "server_ack",
                "seq_id": seq_id,
                "code": code,
                "msg": msg,
                "ts": int(time.time() * 1000)
            }))
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"发送 server_ack 失败: {e}")

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
