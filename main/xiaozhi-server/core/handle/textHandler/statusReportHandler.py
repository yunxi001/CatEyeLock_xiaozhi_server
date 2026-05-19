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
            lock_state = data.get("lock")
            light_state = data.get("light")
            
            # 检查状态是否变化
            state_changed = self._check_state_changed(conn, battery, lux, lock_state, light_state)
            
            # 更新内存缓存
            if not hasattr(conn, "iot_descriptors"):
                conn.iot_descriptors = {}
            
            conn.iot_descriptors["smart_doorlock"] = {
                "battery": battery,
                "lux": lux,
                "lock_state": lock_state,
                "light_state": light_state,
                "last_update": ts
            }
            
            conn.logger.bind(tag=TAG).debug(
                f"状态上报: bat={battery}%, lock={lock_state}, light={light_state}, lux={lux}, changed={state_changed}"
            )
            
            # 持久化到数据库
            await self._save_to_database(conn, battery, lux, lock_state, light_state)
            
            # 只有状态变化时才转发给 App
            if state_changed:
                conn.logger.bind(tag=TAG).info(
                    f"检测到状态变化，转发 status_report 给 App"
                )
                await self._forward_to_apps(conn, msg_json)
            else:
                conn.logger.bind(tag=TAG).debug(
                    f"状态未变化，不转发"
                )
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理状态上报失败: {e}")
    
    def _check_state_changed(self, conn, battery: int, lux: int, 
                             lock_state: int, light_state: int) -> bool:
        """检查状态是否发生变化
        
        Args:
            conn: 连接对象
            battery: 电量
            lux: 光照值
            lock_state: 锁状态
            light_state: 灯状态
            
        Returns:
            bool: 是否有状态变化
        """
        # 如果是第一次上报，认为状态变化
        if not hasattr(conn, "iot_descriptors") or "smart_doorlock" not in conn.iot_descriptors:
            return True
        
        old_state = conn.iot_descriptors["smart_doorlock"]
        
        # 比较各个字段
        if old_state.get("battery") != battery:
            return True
        if old_state.get("lux") != lux:
            return True
        if old_state.get("lock_state") != lock_state:
            return True
        if old_state.get("light_state") != light_state:
            return True
        
        return False
    
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
