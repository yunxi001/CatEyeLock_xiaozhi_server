"""
传感器状态上报处理器
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


class StatusReportHandler(TextMessageHandler):
    """处理 ESP32 传感器状态上报"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.STATUS_REPORT

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理状态上报
        
        消息格式:
        {
            "type": "status_report",
            "ts": 1702234567890,
            "data": {
                "bat": 85,      # 电量百分比
                "lux": 300,     # 光照值
                "lock": 0,      # 锁状态: 0=关闭, 1=打开
                "light": 1      # 补光灯: 0=灭, 1=亮
            }
        }
        """
        try:
            ts = msg_json.get("ts")
            data = msg_json.get("data", {})
            
            battery = data.get("bat")
            lux = data.get("lux")
            lock_state = data.get("lock", 0)
            light_state = data.get("light", 0)
            
            # 存储到 iot_descriptors（内存缓存）
            if not hasattr(conn, "iot_descriptors"):
                conn.iot_descriptors = {}
            
            conn.iot_descriptors["smart_doorlock"] = {
                "battery": battery,
                "lux": lux,
                "lock_state": "open" if lock_state == 1 else "closed",
                "light_state": "on" if light_state == 1 else "off",
                "last_update": ts
            }
            
            conn.logger.bind(tag=TAG).debug(
                f"状态上报: bat={battery}%, lock={lock_state}"
            )
            
            # 持久化到数据库
            await self._save_to_database(conn, battery, lux, lock_state, light_state)
            
            # 使用新的状态更新机制推送给 App
            # 更新灯状态
            if light_state is not None:
                await conn.update_device_state("light", {
                    "status": "on" if light_state == 1 else "off"
                })
            
            # 更新门锁状态
            if lock_state is not None:
                await conn.update_device_state("door", {
                    "status": "open" if lock_state == 1 else "closed",
                    "locked": lock_state == 0
                })
            
            # 更新传感器数据
            if battery is not None:
                await conn.update_device_state("sensor", {
                    "name": "battery",
                    "value": battery,
                    "unit": "%"
                })
            
            if lux is not None:
                await conn.update_device_state("sensor", {
                    "name": "lux",
                    "value": lux,
                    "unit": "lux"
                })
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理状态上报失败: {e}")
    
    async def _save_to_database(self, conn, battery: int, lux: int, 
                                 lock_state: int, light_state: int):
        """保存状态到数据库"""
        try:
            db = _get_database(conn)
            if db:
                db.save_device_status(
                    device_id=conn.device_id,
                    battery=battery,
                    lux=lux,
                    lock_state=lock_state,
                    light_state=light_state
                )
        except Exception as e:
            conn.logger.bind(tag=TAG).warning(f"保存状态到数据库失败: {e}")

    async def _forward_to_apps(self, conn, msg_json: Dict[str, Any]):
        """转发状态到所有关联的 App"""
        try:
            manager = ConnectionManager.get_instance()
            app_conns = manager.get_app_conns(conn.device_id)
            
            if not app_conns:
                return
            
            for app_conn in app_conns:
                if app_conn.websocket:
                    await app_conn.websocket.send(json.dumps(msg_json))
                    
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发状态失败: {e}")
