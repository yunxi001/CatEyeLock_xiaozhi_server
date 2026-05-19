"""
App 端连接处理器

协议版本: v2.2
- 支持 app_id 身份标识
- 支持 server_ack 消息确认机制
- 支持 seq_id 防重放
- 支持增量推送（仅推送 App 断开期间的新数据）
"""
import json
import time
import asyncio
import websockets
from datetime import datetime
from typing import Dict, Any, Optional
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
        
        # 上次断开时间（用于增量推送）
        self.last_disconnect_time: Optional[datetime] = None
        
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

            # 发送成功响应（无论设备是否在线都允许连接）
            await self.websocket.send(
                json.dumps(
                    {
                        "type": "hello",
                        "status": "ok",
                        "device_info": {
                            "online": is_online,
                            "mode": current_mode
                        },
                    }
                )
            )

            self.logger.bind(tag=TAG).info(
                f"App 认证成功: device_id={device_id}, app_id={app_id}, "
                f"设备在线={is_online}"
            )

            # 读取上次断开时间（用于增量推送）
            self.last_disconnect_time = await self._get_last_disconnect_time()
            if self.last_disconnect_time:
                self.logger.bind(tag=TAG).info(
                    f"上次断开时间: {self.last_disconnect_time}, 将进行增量推送"
                )
            else:
                self.logger.bind(tag=TAG).info("首次连接或无断开记录，将进行全量推送")

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
        
        推送策略：
        - P0（立即）：设备在线状态 + 传感器状态
        - P1（延迟1秒）：最近 5 条开锁日志 + 最近 5 条到访记录
        - P2（按需）：历史事件、访客意图、快递警报（通过 query 接口）
        
        Args:
            is_online: 设备是否在线
            esp32_conn: ESP32 连接对象（如果在线）
        """
        try:
            # P0: 推送设备在线/离线通知
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
            
            # P0: 推送传感器状态（从 ESP32 或数据库）
            await self._push_sensor_status(is_online, esp32_conn)
            
            # P1: 延迟推送历史数据（避免阻塞认证响应）
            asyncio.create_task(self._push_history_data_delayed())
                
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
        
        协议 v2.2:
        - 所有消息统一走 Handler 处理
        - 支持 seq_id 防重放
        - 返回 server_ack 确认
        """
        try:
            msg_json = json.loads(message)
            seq_id = msg_json.get("seq_id")
            msg_type = msg_json.get("type")
            
            # 如果有 seq_id，进行防重放检查并返回 server_ack
            if seq_id:
                # 检查是否重复消息
                if not self._seq_id_cache.check_and_add(self.app_id, seq_id):
                    await self._send_server_ack(seq_id, code=5, msg="重复消息")
                    self.logger.bind(tag=TAG).debug(f"忽略重复消息: seq_id={seq_id}")
                    return
                
                # 先发送 ACK 确认收到
                await self._send_server_ack(seq_id, code=0, msg="已接收")
            
            # 处理特殊消息类型
            if msg_type == "get_device_status":
                # App 请求获取设备状态
                await self._handle_get_device_status(seq_id)
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

    async def _handle_get_device_status(self, seq_id: str = None):
        """处理获取设备状态请求
        
        Args:
            seq_id: 消息序列号（可选）
        """
        try:
            manager = ConnectionManager.get_instance()
            esp32_conn = manager.get_esp32_conn(self.device_id)
            is_online = esp32_conn is not None
            
            self.logger.bind(tag=TAG).info(
                f"处理设备状态查询: device_id={self.device_id}, "
                f"app_id={self.app_id}, seq_id={seq_id}, 设备在线={is_online}"
            )
            
            # 构建设备状态信息
            status_data = {
                "type": "device_status_response",
                "ts": int(time.time() * 1000),
                "device_id": self.device_id,
                "online": is_online,
            }
            
            if seq_id:
                status_data["seq_id"] = seq_id
            
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

    async def _push_sensor_status(self, is_online: bool, esp32_conn):
        """推送传感器状态
        
        优先从 ESP32 连接对象获取实时状态，如果没有则从数据库查询最后一次上报的状态
        
        Args:
            is_online: 设备是否在线
            esp32_conn: ESP32 连接对象
        """
        try:
            self.logger.bind(tag=TAG).info(
                f"开始推送传感器状态: device_id={self.device_id}, is_online={is_online}"
            )
            
            device_state = None
            
            # 优先从 ESP32 连接对象获取实时状态
            if is_online and esp32_conn:
                device_state = getattr(esp32_conn, "device_state", None)
                self.logger.bind(tag=TAG).debug(
                    f"从 ESP32 获取状态: device_state={device_state}"
                )
            
            # 如果没有实时状态，从数据库查询最后一次上报的状态
            if not device_state or not device_state.get("last_update"):
                self.logger.bind(tag=TAG).info("从数据库查询传感器状态")
                
                from core.handle.textHandler.queryHandler import _get_base_database
                db = _get_base_database(self)
                
                if not db:
                    self.logger.bind(tag=TAG).warning("数据库实例获取失败，跳过传感器状态推送")
                    return
                
                self.logger.bind(tag=TAG).debug("数据库实例获取成功")
                
                # 查询最新状态
                conn = None
                cursor = None
                try:
                    conn = db.get_connection()
                    cursor = conn.cursor(dictionary=True)
                    
                    cursor.execute("""
                        SELECT battery, lux, lock_state, light_state, created_at
                        FROM device_status
                        WHERE device_id = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                    """, (self.device_id,))
                    
                    row = cursor.fetchone()
                    
                    if row:
                        device_state = {
                            "bat": row.get('battery', 0),
                            "lux": row.get('lux', 0),
                            "lock": row.get('lock_state', 0),
                            "light": row.get('light_state', 0),
                            "last_update": int(row['created_at'].timestamp() * 1000) if row.get('created_at') else 0
                        }
                        self.logger.bind(tag=TAG).info(
                            f"从数据库查询到状态: {device_state}"
                        )
                    else:
                        self.logger.bind(tag=TAG).warning(
                            f"数据库中没有设备状态记录: device_id={self.device_id}"
                        )
                            
                except Exception as e:
                    self.logger.bind(tag=TAG).error(f"查询最新传感器状态失败: {e}")
                    import traceback
                    self.logger.bind(tag=TAG).error(traceback.format_exc())
                finally:
                    if cursor:
                        cursor.close()
                    if conn:
                        conn.close()
            
            # 推送状态
            if device_state:
                status_report = {
                    "type": "status_report",
                    "ts": device_state.get("last_update", int(time.time() * 1000)),
                    "data": {
                        "bat": device_state.get("bat", 0),
                        "lux": device_state.get("lux", 0),
                        "lock": device_state.get("lock", 0),
                        "light": device_state.get("light", 0)
                    }
                }
                
                await self.websocket.send(json.dumps(status_report))
                self.logger.bind(tag=TAG).info(
                    f"已推送传感器状态: device_id={self.device_id}, "
                    f"source={'实时' if is_online else '数据库'}"
                )
            else:
                self.logger.bind(tag=TAG).warning(
                    f"无传感器状态数据: device_id={self.device_id}"
                )
                
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"推送传感器状态失败: {e}")
            import traceback
            self.logger.bind(tag=TAG).error(traceback.format_exc())

    async def _push_history_data_delayed(self):
        """延迟推送历史数据（避免阻塞认证响应）
        
        延迟 1 秒后推送：
        - 增量模式（有断开时间记录）：仅推送断开期间的新数据
        - 全量模式（首次连接）：推送最近 5 条记录
        """
        try:
            push_mode = "增量" if self.last_disconnect_time else "全量"
            self.logger.bind(tag=TAG).info(
                f"开始延迟推送历史数据（{push_mode}模式）: "
                f"device_id={self.device_id}, "
                f"since={self.last_disconnect_time}"
            )
            
            # 延迟 1 秒，确保 hello 响应已发送
            await asyncio.sleep(1)
            
            self.logger.bind(tag=TAG).debug("延迟1秒后开始推送")
            
            from core.handle.textHandler.queryHandler import _get_base_database
            db = _get_base_database(self)
            
            if not db:
                self.logger.bind(tag=TAG).warning("数据库不可用，跳过历史数据推送")
                return
            
            self.logger.bind(tag=TAG).debug("数据库实例获取成功")
            
            # 推送最近 5 条开锁日志
            await self._push_recent_unlock_logs(db, limit=5)
            
            # 推送最近 5 条到访记录
            await self._push_recent_visits(db, limit=5)
            
            # 推送最近 5 条访客意图通知
            await self._push_recent_visitor_intents(limit=5)
            
            self.logger.bind(tag=TAG).info(
                f"历史数据推送完成: device_id={self.device_id}"
            )
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"推送历史数据失败: {e}")
            import traceback
            self.logger.bind(tag=TAG).error(traceback.format_exc())

    async def _push_recent_unlock_logs(self, db, limit: int = 5):
        """推送最近的开锁日志（支持增量推送）
        
        Args:
            db: 数据库实例
            limit: 返回记录数量
        """
        conn = None
        cursor = None
        try:
            conn = db.get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # 根据是否有断开时间决定查询条件
            if self.last_disconnect_time:
                cursor.execute("""
                    SELECT method, user_id, status, fail_count, lock_time, created_at
                    FROM unlock_logs
                    WHERE device_id = %s AND created_at > %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (self.device_id, self.last_disconnect_time, limit))
            else:
                cursor.execute("""
                    SELECT method, user_id, status, fail_count, lock_time, created_at
                    FROM unlock_logs
                    WHERE device_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (self.device_id, limit))
            
            count = 0
            for row in cursor.fetchall():
                log_report = {
                    "type": "log_report",
                    "ts": int(row['created_at'].timestamp() * 1000) if row.get('created_at') else 0,
                    "data": {
                        "method": row['method'],
                        "uid": row.get('user_id', 0),
                        "status": row.get('status', 'success'),
                        "fail_count": row.get('fail_count', 0),
                        "lock_time": row.get('lock_time', 0)
                    }
                }
                
                await self.websocket.send(json.dumps(log_report))
                count += 1
            
            if count > 0:
                self.logger.bind(tag=TAG).info(
                    f"已推送最近开锁日志: device_id={self.device_id}, count={count}"
                )
            else:
                self.logger.bind(tag=TAG).debug(
                    f"无开锁日志数据: device_id={self.device_id}"
                )
                
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"推送开锁日志失败: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    async def _push_recent_visits(self, db, limit: int = 5):
        """推送最近的到访记录（支持增量推送）
        
        Args:
            db: 数据库实例
            limit: 返回记录数量
        """
        conn = None
        cursor = None
        try:
            conn = db.get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # 根据是否有断开时间决定查询条件
            if self.last_disconnect_time:
                cursor.execute("""
                    SELECT vr.id, vr.person_id, p.name as person_name, p.relation_type,
                           vr.recognition_result, vr.access_granted, vr.photo_path, vr.visit_time
                    FROM visit_records vr
                    LEFT JOIN persons p ON vr.person_id = p.id
                    WHERE vr.visit_time > %s
                    ORDER BY vr.visit_time DESC
                    LIMIT %s
                """, (self.last_disconnect_time, limit))
            else:
                cursor.execute("""
                    SELECT vr.id, vr.person_id, p.name as person_name, p.relation_type,
                           vr.recognition_result, vr.access_granted, vr.photo_path, vr.visit_time
                    FROM visit_records vr
                    LEFT JOIN persons p ON vr.person_id = p.id
                    ORDER BY vr.visit_time DESC
                    LIMIT %s
                """, (limit,))
            
            count = 0
            for row in cursor.fetchall():
                visit_notification = {
                    "type": "visit_notification",
                    "ts": int(row['visit_time'].timestamp() * 1000) if row.get('visit_time') else 0,
                    "data": {
                        "visit_id": row['id'],
                        "person_id": row.get('person_id'),
                        "person_name": row.get('person_name', '陌生人'),
                        "relation": row.get('relation_type'),
                        "result": row.get('recognition_result', 'unknown'),
                        "access_granted": bool(row.get('access_granted', False)),
                        "image": None,  # 历史记录不包含图片数据
                        "image_path": row.get('photo_path')
                    }
                }
                
                await self.websocket.send(json.dumps(visit_notification))
                count += 1
            
            if count > 0:
                self.logger.bind(tag=TAG).info(
                    f"已推送最近到访记录: device_id={self.device_id}, count={count}"
                )
            else:
                self.logger.bind(tag=TAG).debug(
                    f"无到访记录数据: device_id={self.device_id}"
                )
                
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"推送到访记录失败: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    async def _push_recent_visitor_intents(self, limit: int = 5):
        """推送最近的访客意图通知
        
        根据协议 v2.5 规范，完整推送访客意图通知，包括：
        - 基本信息：visit_id, session_id, ts
        - 人员信息：person_info (如果识别成功)
        - 意图总结：intent_summary (intent_type, summary, important_notes, ai_analysis)
        - 对话历史：dialogue_history
        - 快递检查：package_check (如果有快递看护)
        
        Args:
            limit: 返回记录数量
        """
        try:
            self.logger.bind(tag=TAG).info(
                f"开始推送访客意图通知: device_id={self.device_id}"
            )
            
            # 获取门锁数据库实例
            from core.providers.doorlock.doorlock_database import DoorlockDatabase
            doorlock_db = DoorlockDatabase()
            
            # 查询最近的访客意图记录（支持增量推送）
            intents, total = await doorlock_db.get_visitor_intents(
                device_id=self.device_id,
                limit=limit,
                offset=0,
                start_date=self.last_disconnect_time  # None 时查全部
            )
            
            if not intents:
                self.logger.bind(tag=TAG).debug(
                    f"无访客意图数据: device_id={self.device_id}"
                )
                return
            
            # 推送每条访客意图通知
            count = 0
            for intent in intents:
                # 构建访客意图通知消息（按协议 v2.5 规范）
                notification = {
                    "type": "visitor_intent_notification",
                    "ts": int(intent.created_at.timestamp() * 1000) if intent.created_at else int(time.time() * 1000),
                    "visit_id": intent.visit_id,
                    "session_id": intent.session_id,
                    "intent_summary": intent.intent_summary or {
                        "intent_type": intent.intent_type or "other",
                        "summary": "访客意图识别",
                        "important_notes": [],
                        "ai_analysis": ""
                    },
                    "dialogue_history": intent.dialogue_history or []
                }
                
                # 如果有人员信息，添加到通知中
                if intent.person_id:
                    # 查询人员信息
                    from core.handle.textHandler.queryHandler import _get_base_database
                    db = _get_base_database(self)
                    if db:
                        conn = None
                        cursor = None
                        try:
                            conn = db.get_connection()
                            cursor = conn.cursor(dictionary=True)
                            cursor.execute("""
                                SELECT id, name, relation_type
                                FROM persons
                                WHERE id = %s
                            """, (intent.person_id,))
                            person = cursor.fetchone()
                            
                            if person:
                                notification["person_info"] = {
                                    "person_id": person['id'],
                                    "name": person['name'],
                                    "relation_type": person.get('relation_type', 'unknown')
                                }
                        except Exception as e:
                            self.logger.bind(tag=TAG).warning(f"查询人员信息失败: {e}")
                        finally:
                            if cursor:
                                cursor.close()
                            if conn:
                                conn.close()
                
                # 查询是否有关联的快递警报（package_check）
                try:
                    alerts, _ = await doorlock_db.get_package_alerts(
                        device_id=self.device_id,
                        limit=1,
                        offset=0
                    )
                    
                    # 查找与当前 session_id 匹配的警报
                    matching_alert = None
                    for alert in alerts:
                        if alert.session_id == intent.session_id:
                            matching_alert = alert
                            break
                    
                    if matching_alert:
                        notification["package_check"] = {
                            "threat_level": matching_alert.threat_level,
                            "action": matching_alert.action,
                            "description": matching_alert.description
                        }
                except Exception as e:
                    self.logger.bind(tag=TAG).debug(f"查询快递警报失败（可能不存在）: {e}")
                
                # 发送通知
                await self.websocket.send(json.dumps(notification, ensure_ascii=False))
                count += 1
                
                self.logger.bind(tag=TAG).debug(
                    f"已推送访客意图通知: visit_id={intent.visit_id}, "
                    f"intent_type={intent.intent_summary.get('intent_type', 'unknown')}, "
                    f"has_person_info={intent.person_id is not None}, "
                    f"has_package_check={'package_check' in notification}"
                )
            
            self.logger.bind(tag=TAG).info(
                f"已推送访客意图通知: device_id={self.device_id}, count={count}, total={total}"
            )
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"推送访客意图通知失败: {e}")
            import traceback
            self.logger.bind(tag=TAG).error(traceback.format_exc())

    async def _cleanup(self):
        """清理资源"""
        try:
            # 记录断开时间到数据库（用于下次连接时增量推送）
            if self.device_id and self.app_id:
                await self._save_disconnect_time()

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

    async def _get_last_disconnect_time(self) -> Optional[datetime]:
        """从数据库获取上次断开时间
        
        Returns:
            上次断开时间的 datetime 对象，如果没有记录则返回 None（首次连接）
        """
        try:
            from core.handle.textHandler.queryHandler import _get_base_database
            db = _get_base_database(self)
            
            if not db:
                self.logger.bind(tag=TAG).warning("数据库不可用，无法获取断开时间")
                return None
            
            conn = None
            cursor = None
            try:
                conn = db.get_connection()
                cursor = conn.cursor(dictionary=True)
                
                cursor.execute("""
                    SELECT disconnect_time
                    FROM app_disconnect_log
                    WHERE device_id = %s AND app_id = %s
                """, (self.device_id, self.app_id))
                
                row = cursor.fetchone()
                if row and row.get('disconnect_time'):
                    return row['disconnect_time']
                return None
                
            except Exception as e:
                self.logger.bind(tag=TAG).error(f"查询断开时间失败: {e}")
                return None
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
                    
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"获取断开时间异常: {e}")
            return None

    async def _save_disconnect_time(self):
        """将当前时间作为断开时间写入数据库
        
        使用 INSERT ... ON DUPLICATE KEY UPDATE 实现 upsert，
        确保每个 (device_id, app_id) 只保留一条记录。
        """
        try:
            from core.handle.textHandler.queryHandler import _get_base_database
            db = _get_base_database(self)
            
            if not db:
                self.logger.bind(tag=TAG).warning("数据库不可用，无法保存断开时间")
                return
            
            conn = None
            cursor = None
            try:
                conn = db.get_connection()
                cursor = conn.cursor()
                
                now = datetime.now()
                cursor.execute("""
                    INSERT INTO app_disconnect_log (device_id, app_id, disconnect_time)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE disconnect_time = VALUES(disconnect_time)
                """, (self.device_id, self.app_id, now))
                
                conn.commit()
                self.logger.bind(tag=TAG).info(
                    f"已记录断开时间: device_id={self.device_id}, "
                    f"app_id={self.app_id}, time={now}"
                )
                
            except Exception as e:
                self.logger.bind(tag=TAG).error(f"保存断开时间失败: {e}")
                if conn:
                    conn.rollback()
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
                    
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"保存断开时间异常: {e}")
