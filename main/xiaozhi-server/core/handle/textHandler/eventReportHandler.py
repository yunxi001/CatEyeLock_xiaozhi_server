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
        """处理门铃事件"""
        conn.logger.bind(tag=TAG).info("门铃按下")

    async def _handle_pir_event(self, conn, ts: int, param):
        """处理 PIR 人体检测事件
        
        集成智能门锁AI功能：
        1. 检查设备配置（intent_recognition_enabled）
        2. 检查看护模式状态（package_guard_active）
        3. 触发意图识别处理器
        4. 如果看护模式激活，同时启动监控和对话
        """
        duration = param  # 持续时间（秒）
        conn.logger.bind(tag=TAG).info(f"PIR 检测到人体，持续 {duration} 秒")
        
        # 检查是否启用了智能门锁AI功能
        try:
            from core.providers.doorlock.doorlock_database import DoorlockDatabase
            from core.handle.doorlock_intent_handler import DoorlockIntentHandler
            from core.providers.doorlock.package_guard_manager import PackageGuardManager
            
            # 获取设备配置
            db = DoorlockDatabase(conn.logger)
            config = await db.get_config(conn.device_id)
            
            if not config:
                conn.logger.bind(tag=TAG).debug(f"设备 {conn.device_id} 未配置智能门锁AI功能")
                return
            
            # 检查是否启用意图识别
            if not config.intent_recognition_enabled:
                conn.logger.bind(tag=TAG).debug(f"设备 {conn.device_id} 未启用意图识别功能")
                return
            
            conn.logger.bind(tag=TAG).info(f"设备 {conn.device_id} 触发智能门锁AI处理流程")
            
            # 创建意图识别处理器（使用工厂方法）
            intent_handler = await DoorlockIntentHandler.create_from_config(
                config=conn.config,
                logger_instance=conn.logger
            )
            
            # 检查看护模式状态
            guard_manager = PackageGuardManager(conn.config, conn.logger)
            is_guard_active = await guard_manager.is_active(conn.device_id)
            
            # 处理访客到访（会自动处理人脸识别、意图识别对话等）
            # 如果看护模式激活，会同时启动监控和对话
            result = await intent_handler.handle_visitor(
                device_id=conn.device_id,
                conn=conn,
                guard_active=is_guard_active
            )
            
            if result.get("success"):
                conn.logger.bind(tag=TAG).info(
                    f"设备 {conn.device_id} 智能门锁AI处理完成: action={result.get('action')}"
                )
            else:
                conn.logger.bind(tag=TAG).warning(
                    f"设备 {conn.device_id} 智能门锁AI处理失败: {result.get('error')}"
                )
            
        except ImportError as e:
            conn.logger.bind(tag=TAG).debug(f"智能门锁AI模块未安装: {e}")
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理智能门锁AI功能失败: {e}")
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
