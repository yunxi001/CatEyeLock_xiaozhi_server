"""
关键事件上报处理器
"""
import json
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.connection_manager import ConnectionManager
from core.handle.textHandler.faceRecognitionHandler import get_face_service

TAG = __name__


def _get_database(conn):
    """获取数据库实例"""
    try:
        face_service = get_face_service(conn.logger)
        return face_service.db
    except Exception:
        return None


class EventReportHandler(TextMessageHandler):
    """处理 ESP32 关键事件上报"""
    
    # 类级别缓存：存储已初始化的数据库实例和意图处理器
    _db_instances = {}  # {device_id: DoorlockDatabase}
    _intent_handlers = {}  # {device_id: DoorlockIntentHandler}
    _last_cleanup_time = 0  # 上次清理缓存的时间戳

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.EVENT_REPORT

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理事件上报
        
        消息格式:
        {
            "type": "event_report",
            "ts": 1702234567890,
            "event": "bell",      # 事件类型
            "param": 1            # 事件参数
        }
        
        事件类型:
        - bell: 门铃按下
        - pir_trigger: PIR 人体检测
        - tamper: 撬锁报警
        - door_open: 门未关超时
        - low_battery: 低电量警告
        - door_closed: 门已关闭 (v5.2 新增)
        - lock_success: 上锁成功 (v5.2 新增)
        - bolt_alarm: 反锁报警 (v5.2 新增)
        """
        try:
            ts = msg_json.get("ts")
            event = msg_json.get("event")
            param = msg_json.get("param")
            
            # 验证事件类型
            valid_events = [
                "bell", "pir_trigger", "tamper", "door_open", "low_battery",
                "door_closed", "lock_success", "bolt_alarm"  # v5.2 新增
            ]
            
            if event not in valid_events:
                conn.logger.bind(tag=TAG).warning(f"未知事件类型: {event}")
                # 仍然转发，但记录警告
            
            conn.logger.bind(tag=TAG).info(f"事件上报: event={event}, param={param}")
            
            # 持久化到数据库
            await self._save_to_database(conn, event, param)
            
            # 根据事件类型处理
            if event == "bell":
                await self._handle_bell_event(conn, ts, param)
            elif event == "pir_trigger":
                await self._handle_pir_event(conn, ts, param)
            elif event == "tamper":
                await self._handle_tamper_event(conn, ts, param)
            elif event == "door_open":
                await self._handle_door_open_event(conn, ts, param)
            elif event == "low_battery":
                await self._handle_low_battery_event(conn, ts, param)
            elif event == "door_closed":
                await self._handle_door_closed_event(conn, ts, param)
            elif event == "lock_success":
                await self._handle_lock_success_event(conn, ts, param)
            elif event == "bolt_alarm":
                await self._handle_bolt_alarm_event(conn, ts, param)
            
            # 转发给关联的 App
            await self._forward_to_apps(conn, msg_json)
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理事件上报失败: {e}")
    
    async def _save_to_database(self, conn, event_type: str, param: int):
        """保存事件到数据库"""
        try:
            db = _get_database(conn)
            if db:
                db.save_device_event(
                    device_id=conn.device_id,
                    event_type=event_type,
                    param=param
                )
        except Exception as e:
            conn.logger.bind(tag=TAG).warning(f"保存事件到数据库失败: {e}")

    async def _handle_bell_event(self, conn, ts: int, param):
        """处理门铃事件
        
        门铃按下时触发人脸识别流程
        """
        conn.logger.bind(tag=TAG).info("门铃按下")
        
        # 触发人脸识别流程
        await self._trigger_face_recognition(
            conn=conn,
            ts=ts,
            param=param,
            trigger_type="bell"
        )

    async def _handle_pir_event(self, conn, ts: int, param):
        """处理 PIR 人体检测事件
        
        PIR检测到人体时触发人脸识别流程
        
        优化说明：
        1. 每次PIR上报都更新状态（pir_detected, last_pir_time, pir_duration）
        2. 检查visitor_processing标志，避免重复触发
        3. 只在停留时间>=阈值时触发（默认3秒，过滤路人）
        4. 只在首次达到阈值时触发一次（避免重复触发）
        5. 当PIR检测不到人体时（param=0），重置触发标志
        """
        from core.utils.pir_utils import update_pir_state
        
        duration = param  # 持续时间（秒）
        
        # 1. 更新PIR状态（每次上报都更新）
        update_pir_state(conn, param, ts)
        conn.logger.bind(tag=TAG).info(f"PIR 检测到人体，持续 {duration} 秒")
        
        # 2. 如果PIR检测不到人体（人已离开），重置触发标志
        if duration == 0:
            if hasattr(conn, 'pir_triggered') and conn.pir_triggered:
                conn.pir_triggered = False
                conn.logger.bind(tag=TAG).debug(
                    f"PIR检测不到人体，重置触发标志 - 设备: {conn.device_id}"
                )
            return
        
        # 2. 检查是否正在处理访客（防止重复触发）
        if hasattr(conn, 'visitor_processing') and conn.visitor_processing:
            conn.logger.bind(tag=TAG).debug(
                f"访客处理中，忽略重复的PIR事件 - 设备: {conn.device_id}, "
                f"持续时间: {duration}秒"
            )
            return
        
        # 3. 检查停留阈值（默认3秒，过滤路人路过）
        pir_stay_threshold = conn.config.get('doorlock', {}).get(
            'visitor_management', {}
        ).get('pir_stay_threshold', 3)
        
        if duration < pir_stay_threshold:
            conn.logger.bind(tag=TAG).debug(
                f"PIR停留时间不足 {pir_stay_threshold} 秒，跳过触发 - "
                f"设备: {conn.device_id}, 当前: {duration}秒"
            )
            return
        
        # 4. 检查是否已触发过（只在首次达到阈值时触发）
        if hasattr(conn, 'pir_triggered') and conn.pir_triggered:
            conn.logger.bind(tag=TAG).debug(
                f"PIR已触发过访客处理，忽略后续事件 - 设备: {conn.device_id}, "
                f"持续时间: {duration}秒"
            )
            return
        
        # 5. 设置触发标志（防止重复触发）
        conn.pir_triggered = True
        conn.visitor_processing = True
        
        conn.logger.bind(tag=TAG).info(
            f"PIR停留时间达到阈值，触发访客处理 - "
            f"设备: {conn.device_id}, 停留: {duration}秒"
        )
        
        # 6. 触发人脸识别流程（后台任务，不阻塞消息处理循环）
        # 这样后续的 PIR 事件仍能被处理，update_pir_state 能持续更新
        import asyncio
        
        async def _run_face_recognition():
            try:
                await self._trigger_face_recognition(
                    conn=conn,
                    ts=ts,
                    param=param,
                    trigger_type="pir"
                )
            finally:
                # 清除访客处理标志
                conn.visitor_processing = False
                conn.logger.bind(tag=TAG).debug(
                    f"清除访客处理标志 - 设备: {conn.device_id}"
                )
        
        asyncio.create_task(_run_face_recognition())
    
    async def _trigger_face_recognition(
        self,
        conn,
        ts: int,
        param: int,
        trigger_type: str
    ):
        """统一的人脸识别触发方法
        
        集成智能门锁AI功能：
        1. 检查设备配置（face_recognition_enabled, intent_recognition_enabled）
        2. 检查看护模式状态（package_guard_active）
        3. 触发意图识别处理器
        4. 如果看护模式激活，同时启动监控和对话
        
        优化：使用类级别缓存，避免每次PIR事件都重新加载配置和创建实例
        
        Args:
            conn: 连接对象
            ts: 时间戳
            param: 事件参数
            trigger_type: 触发类型（bell/pir）
        """
        try:
            from core.providers.doorlock.doorlock_database import DoorlockDatabase
            from core.handle.doorlock_intent_handler import DoorlockIntentHandler
            import time
            
            device_id = conn.device_id
            
            # 定期清理缓存（每小时清理一次，避免内存泄漏）
            current_time = time.time()
            if current_time - self._last_cleanup_time > 3600:
                self._db_instances.clear()
                self._intent_handlers.clear()
                self._last_cleanup_time = current_time
                conn.logger.bind(tag=TAG).debug("清理门锁处理器缓存")
            
            # 1. 获取或创建数据库实例（使用缓存）
            if device_id not in self._db_instances:
                conn.logger.bind(tag=TAG).debug(
                    f"创建数据库实例 - 设备: {device_id}"
                )
                self._db_instances[device_id] = DoorlockDatabase(conn.logger)
            
            db = self._db_instances[device_id]
            
            # 2. 获取设备配置（数据库层面应该有缓存）
            config = await db.get_config(device_id)
            
            if not config:
                conn.logger.bind(tag=TAG).debug(
                    f"设备 {device_id} 未配置智能门锁AI功能"
                )
                return
            
            # 3. 检查是否启用人脸识别功能
            if not config.face_recognition_enabled:
                conn.logger.bind(tag=TAG).debug(
                    f"设备 {device_id} 未启用人脸识别功能"
                )
                return
            
            # 4. 检查是否启用意图识别
            if not config.intent_recognition_enabled:
                conn.logger.bind(tag=TAG).debug(
                    f"设备 {device_id} 未启用意图识别功能"
                )
                return
            
            conn.logger.bind(tag=TAG).info(
                f"设备 {device_id} 触发智能门锁AI处理流程 - "
                f"触发类型: {trigger_type}"
            )
            
            # 5. 获取或创建意图识别处理器（使用缓存）
            if device_id not in self._intent_handlers:
                conn.logger.bind(tag=TAG).debug(
                    f"创建意图识别处理器 - 设备: {device_id}"
                )
                self._intent_handlers[device_id] = await DoorlockIntentHandler.create_from_config(
                    config=conn.config,
                    logger_instance=conn.logger
                )
            
            intent_handler = self._intent_handlers[device_id]
            
            # 6. 检查看护模式状态（直接查询数据库配置，无需创建完整的管理器）
            is_guard_active = config.package_guard_active
            
            # 7. 处理访客到访（会自动处理人脸识别、意图识别对话等）
            # 如果看护模式激活，会同时启动监控和对话
            result = await intent_handler.handle_visitor(
                device_id=device_id,
                conn=conn,
                guard_active=is_guard_active
            )
            
            if result.get("success"):
                conn.logger.bind(tag=TAG).info(
                    f"设备 {device_id} 智能门锁AI处理完成 - "
                    f"触发类型: {trigger_type}, action={result.get('action')}"
                )
            else:
                conn.logger.bind(tag=TAG).warning(
                    f"设备 {device_id} 智能门锁AI处理失败 - "
                    f"触发类型: {trigger_type}, error={result.get('error')}"
                )
            
        except ImportError as e:
            conn.logger.bind(tag=TAG).warning(f"智能门锁AI模块导入失败: {e}")
        except Exception as e:
            conn.logger.bind(tag=TAG).error(
                f"处理智能门锁AI功能失败 - 触发类型: {trigger_type}, 错误: {e}"
            )
            import traceback
            conn.logger.bind(tag=TAG).error(traceback.format_exc())

    async def _handle_tamper_event(self, conn, ts: int, param):
        """处理撬锁报警事件"""
        level = param  # 报警级别 1-3
        conn.logger.bind(tag=TAG).warning(f"撬锁报警！级别: {level}")

    async def _handle_door_open_event(self, conn, ts: int, param):
        """处理门未关超时事件"""
        timeout_minutes = param
        conn.logger.bind(tag=TAG).warning(f"门未关超时: {timeout_minutes} 分钟")

    async def _handle_low_battery_event(self, conn, ts: int, param):
        """处理低电量警告事件"""
        battery_level = param
        conn.logger.bind(tag=TAG).warning(f"低电量警告: {battery_level}%")

    async def _handle_door_closed_event(self, conn, ts: int, param):
        """处理门已关闭事件 (v5.2 新增)"""
        conn.logger.bind(tag=TAG).info("门已关闭")

    async def _handle_lock_success_event(self, conn, ts: int, param):
        """处理上锁成功事件 (v5.2 新增)"""
        conn.logger.bind(tag=TAG).info("上锁成功")

    async def _handle_bolt_alarm_event(self, conn, ts: int, param):
        """处理反锁报警事件 (v5.2 新增)"""
        alarm_type = param  # 报警类型
        conn.logger.bind(tag=TAG).warning(f"反锁报警！类型: {alarm_type}")

    async def _forward_to_apps(self, conn, msg_json: Dict[str, Any]):
        """转发事件到所有关联的 App"""
        try:
            manager = ConnectionManager.get_instance()
            app_conns = manager.get_app_conns(conn.device_id)
            
            if not app_conns:
                return
            
            for app_conn in app_conns:
                if app_conn.websocket:
                    await app_conn.websocket.send(json.dumps(msg_json))
                    
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发事件失败: {e}")
