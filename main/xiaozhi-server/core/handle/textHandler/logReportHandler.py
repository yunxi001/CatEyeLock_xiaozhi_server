"""
开锁日志上报处理器
"""
import json
import time
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


class LogReportHandler(TextMessageHandler):
    """处理 ESP32 开锁日志上报"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.LOG_REPORT

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理开锁日志上报
        
        v5.2 消息格式:
        {
            "type": "log_report",
            "ts": 1702234567890,
            "data": {
                "method": "finger",      # 开锁方式
                "uid": 5,                # 用户 ID
                "status": "success",     # 开锁状态: success/fail/locked
                "lock_time": 0,          # 剩余锁定时间（分钟），仅 locked 状态时 > 0
                "fail_count": 0          # 连续失败次数
            }
        }
        
        v5.0 兼容格式（旧版）:
        {
            "type": "log_report",
            "ts": 1702234567890,
            "data": {
                "method": "finger",
                "uid": 5,
                "result": true,          # 旧版字段，true=成功，false=失败
                "fail_count": 0
            }
        }
        
        method 取值:
        - finger: 指纹开锁
        - nfc: NFC 开锁
        - face: 人脸开锁（ESP32 不传 uid，服务器从最近识别结果填充）
        - pwd: 密码开锁
        - temp_pwd: 临时密码开锁（无关联用户，uid 默认为 0）
        - key: 机械钥匙
        - remote: 远程开锁（ESP32 不传 uid，服务器从最近开锁命令填充 App 用户 ID）
        """
        try:
            ts = msg_json.get("ts")
            data = msg_json.get("data", {})
            
            method = data.get("method")
            uid = data.get("uid", 0)
            fail_count = data.get("fail_count", 0)
            
            # 子任务 7.1: 支持 status 字段
            # 子任务 7.2: 兼容旧版 result 字段
            if "status" in data:
                # v5.2 新版格式
                status = data["status"]
                lock_time = data.get("lock_time", 0)
            elif "result" in data:
                # v5.0 旧版格式兼容
                result = data["result"]
                status = "success" if result else "fail"
                lock_time = 0
                conn.logger.bind(tag=TAG).debug(
                    f"兼容旧版 result 字段: result={result} -> status={status}"
                )
            else:
                conn.logger.bind(tag=TAG).error("缺少 status 或 result 字段")
                return
            
            # 子任务 7.3: 验证字段取值
            if status not in ["success", "fail", "locked"]:
                conn.logger.bind(tag=TAG).error(f"无效的 status 值: {status}")
                return
            
            # 验证 locked 状态时 lock_time 必须 > 0
            if status == "locked" and lock_time <= 0:
                conn.logger.bind(tag=TAG).warning(
                    f"locked 状态但 lock_time 无效: {lock_time}，应该 > 0"
                )
            
            # 验证 success/fail 状态时 lock_time 应该为 0
            if status in ["success", "fail"] and lock_time != 0:
                conn.logger.bind(tag=TAG).warning(
                    f"{status} 状态但 lock_time 不为 0: {lock_time}，应该为 0"
                )
            
            # ESP32 上传 face 和 temp_pwd 时不附带 uid，服务器需要填充
            uid = self._fill_user_id(conn, method, uid)
            
            # 更新 msg_json 中的 uid，确保转发给 App 时包含正确的 uid
            if "data" in msg_json:
                msg_json["data"]["uid"] = uid
            
            # 子任务 7.5: 增强日志输出（包含 status 和 lock_time）
            if status == "success":
                conn.logger.bind(tag=TAG).info(
                    f"开锁成功: method={method}, uid={uid}, status={status}"
                )
            elif status == "locked":
                conn.logger.bind(tag=TAG).warning(
                    f"设备已锁定: method={method}, uid={uid}, status={status}, lock_time={lock_time}分钟"
                )
            else:  # fail
                conn.logger.bind(tag=TAG).warning(
                    f"开锁失败: method={method}, uid={uid}, status={status}, fail_count={fail_count}"
                )
                
                # 连续失败次数过多，触发警报
                if fail_count >= 5:
                    conn.logger.bind(tag=TAG).error(
                        f"连续开锁失败 {fail_count} 次，触发警报"
                    )
            
            # 子任务 7.4: 持久化到数据库（传入 status 和 lock_time）
            await self._save_to_database(conn, method, uid, status, lock_time, fail_count)
            
            # 方案 2: 根据开锁结果更新锁状态并推送给 App
            await self._update_lock_state_from_log(conn, status)
            
            # 转发给关联的 App
            await self._forward_to_apps(conn, msg_json)
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理开锁日志失败: {e}")

    def _fill_user_id(self, conn, method: str, uid: int) -> int:
        """填充用户 ID
        
        ESP32 上传 face 和 remote 开锁日志时不附带 uid，服务器需要填充：
        - face: 从连接缓存的最近人脸识别结果中获取
        - remote: 远程开锁无关联用户，默认为 0（App 用户 ID 是字符串，不存储到 user_id 字段）
        - temp_pwd: 临时密码无关联用户，默认为 0
        
        Args:
            conn: 连接对象
            method: 开锁方式
            uid: ESP32 上传的 uid（可能为 0）
            
        Returns:
            填充后的 uid
        """
        # 如果 ESP32 已经提供了有效的 uid，直接使用
        if uid and uid > 0:
            return uid
        
        if method == "face":
            # 从连接缓存获取最近的人脸识别结果
            # 人脸识别成功后会缓存到 conn.last_face_result
            if hasattr(conn, "last_face_result") and conn.last_face_result:
                last_result = conn.last_face_result
                # 检查识别结果是否在有效时间内（30秒）
                result_time = last_result.get("ts", 0)
                current_time = int(time.time() * 1000)
                if current_time - result_time < 30000:  # 30秒有效期
                    filled_uid = last_result.get("user_id", 0)
                    if filled_uid:
                        conn.logger.bind(tag=TAG).debug(
                            f"人脸开锁日志填充 uid: {filled_uid}"
                        )
                        return filled_uid
            
            conn.logger.bind(tag=TAG).warning(
                "人脸开锁日志无法填充 uid：未找到有效的识别结果"
            )
            return 0
        
        elif method == "remote":
            # 远程开锁：App 用户 ID 是字符串（如 app_1777960149873_qicvyypr0）
            # 数据库 user_id 字段是 INT 类型，无法存储字符串
            # 因此远程开锁的 user_id 统一设置为 0
            # App 用户信息可以通过其他方式关联（如通过 seq_id 或时间戳）
            if hasattr(conn, "last_remote_unlock") and conn.last_remote_unlock:
                last_unlock = conn.last_remote_unlock
                app_id = last_unlock.get("app_id", "")
                conn.logger.bind(tag=TAG).debug(
                    f"远程开锁日志: app_id={app_id}, user_id=0（App ID 为字符串，不存储到 user_id 字段）"
                )
            else:
                conn.logger.bind(tag=TAG).warning(
                    "远程开锁日志无法获取 app_id：未找到有效的开锁命令"
                )
            return 0
        
        # temp_pwd 和其他方式返回原始 uid（temp_pwd 默认为 0）
        return uid
    
    async def _save_to_database(self, conn, method: str, user_id: int,
                                 status: str, lock_time: int, fail_count: int):
        """保存开锁日志到数据库
        
        Args:
            conn: 连接对象
            method: 开锁方式
            user_id: 用户 ID
            status: 开锁状态 (success/fail/locked)
            lock_time: 剩余锁定时间（分钟）
            fail_count: 连续失败次数
        """
        try:
            db = _get_database(conn)
            if db:
                db.save_unlock_log(
                    device_id=conn.device_id,
                    method=method,
                    user_id=user_id,
                    status=status,
                    lock_time=lock_time,
                    fail_count=fail_count
                )
        except Exception as e:
            conn.logger.bind(tag=TAG).warning(f"保存开锁日志到数据库失败: {e}")

    async def _update_lock_state_from_log(self, conn, status: str):
        """根据开锁日志更新锁状态并推送给 App
        
        方案 2: 服务器端补充逻辑
        - 当收到 status=success 的开锁日志时，推断锁状态为 open
        - 构造 status_report 消息并发送给 App
        
        Args:
            conn: 连接对象
            status: 开锁状态 (success/fail/locked)
        """
        try:
            if status == "success":
                # 开锁成功，锁状态变为 open (1)
                # 从缓存中获取其他状态数据
                old_state = {}
                if hasattr(conn, "iot_descriptors") and "smart_doorlock" in conn.iot_descriptors:
                    old_state = conn.iot_descriptors["smart_doorlock"]
                
                # 更新锁状态
                new_lock_state = 1  # 1 = open
                
                # 构造 status_report 消息（使用默认值避免 null）
                status_report = {
                    "type": "status_report",
                    "ts": int(time.time() * 1000),
                    "data": {
                        "bat": old_state.get("battery") if old_state.get("battery") is not None else 0,
                        "lux": old_state.get("lux") if old_state.get("lux") is not None else 0,
                        "lock": new_lock_state,
                        "light": old_state.get("light_state") if old_state.get("light_state") is not None else 0
                    }
                }
                
                # 更新内存缓存
                if not hasattr(conn, "iot_descriptors"):
                    conn.iot_descriptors = {}
                
                conn.iot_descriptors["smart_doorlock"] = {
                    "battery": status_report["data"]["bat"],
                    "lux": status_report["data"]["lux"],
                    "lock_state": new_lock_state,
                    "light_state": status_report["data"]["light"],
                    "last_update": status_report["ts"]
                }
                
                conn.logger.bind(tag=TAG).info(
                    f"根据开锁日志构造 status_report: lock=1 (open), "
                    f"bat={status_report['data']['bat']}, lux={status_report['data']['lux']}, light={status_report['data']['light']}"
                )
                
                # 发送给所有关联的 App
                manager = ConnectionManager.get_instance()
                app_conns = manager.get_app_conns(conn.device_id)
                
                if app_conns:
                    msg = json.dumps(status_report)
                    for app_conn in app_conns:
                        if app_conn.websocket:
                            await app_conn.websocket.send(msg)
                    
                    conn.logger.bind(tag=TAG).info(
                        f"已发送 status_report 到 {len(app_conns)} 个 App"
                    )
            
            # 注意：fail 和 locked 状态不改变锁的物理状态，所以不发送 status_report
            
        except Exception as e:
            conn.logger.bind(tag=TAG).warning(f"根据开锁日志更新锁状态失败: {e}")

    async def _forward_to_apps(self, conn, msg_json: Dict[str, Any]):
        """转发日志到所有关联的 App"""
        try:
            manager = ConnectionManager.get_instance()
            app_conns = manager.get_app_conns(conn.device_id)
            
            if not app_conns:
                return
            
            for app_conn in app_conns:
                if app_conn.websocket:
                    await app_conn.websocket.send(json.dumps(msg_json))
                    
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发日志失败: {e}")
