"""
ACK 响应处理器
"""
import json
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.connection_manager import ConnectionManager
from core.constants.error_codes import is_valid_error_code, get_error_message
from core.handle.textHandler.queryHandler import _get_base_database

TAG = __name__


class AckHandler(TextMessageHandler):
    """处理 ESP32 ACK 响应"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.ACK

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理 ACK 响应
        
        消息格式 (v5.2):
        {
            "type": "ack",
            "seq_id": "1702234567890_0",  # v5.2 统一使用 seq_id
            "code": 0,
            "msg": "OK"
        }
        
        兼容旧版格式:
        {
            "type": "ack",
            "msg_id": "cmd_88293",  # v5.0 使用 msg_id
            "code": 0,
            "msg": "OK"
        }
        
        统一错误码 (0-10):
        - 0: 成功
        - 1: 设备离线
        - 2: 设备忙碌
        - 3: 参数错误
        - 4: 不支持
        - 5: 超时
        - 6: 硬件故障
        - 7: 资源已满
        - 8: 未认证
        - 9: 重复消息
        - 10: 内部错误
        """
        try:
            # 子任务 6.1: 支持 seq_id 字段，兼容旧版 msg_id
            seq_id = msg_json.get("seq_id") or msg_json.get("msg_id")
            code = msg_json.get("code", 0)
            msg = msg_json.get("msg", "")
            
            # 子任务 6.2: 添加错误码验证
            if not is_valid_error_code(code):
                conn.logger.bind(tag=TAG).warning(
                    f"无效的错误码: seq_id={seq_id}, code={code}，错误码应在 0-10 范围内"
                )
            
            # 子任务 6.3: 增强日志输出
            if code == 0:
                # 成功时记录 DEBUG 日志（包含 seq_id）
                conn.logger.bind(tag=TAG).debug(f"ACK 成功: seq_id={seq_id}")
            else:
                # 失败时记录 WARNING 日志（包含 seq_id、code、错误消息）
                error_message = get_error_message(code)
                conn.logger.bind(tag=TAG).warning(
                    f"ACK 失败: seq_id={seq_id}, code={code}, msg={msg}, 错误说明={error_message}"
                )
            
            # 执行等待回调（如果有）
            # 兼容旧版 msg_id 和新版 seq_id
            if hasattr(conn, "_pending_commands"):
                callback = None
                if seq_id and seq_id in conn._pending_commands:
                    callback = conn._pending_commands.pop(seq_id)
                
                if callback:
                    await callback(code, msg)
            
            # 如果是设备控制命令成功，构造 status_report 上报状态变化
            if code == 0:
                await self._update_device_state_from_ack(conn, seq_id)
                # 如果是用户管理的 del/clear 命令成功，同步数据库
                await self._handle_user_mgmt_delete(conn, seq_id)
            
            # 转发 ACK 给关联的 App（协议 v2.2）
            await self._forward_to_apps(conn, msg_json)
                    
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理 ACK 失败: {e}")

    async def _update_device_state_from_ack(self, conn, seq_id: str):
        """根据 ACK 响应更新设备状态并推送给 App
        
        当收到设备控制命令的成功 ACK 时：
        - 检查是否有缓存的控制命令（如灯控制）
        - 构造 status_report 消息
        - 发送给所有关联的 App
        
        Args:
            conn: ESP32 连接对象
            seq_id: 消息序列 ID
        """
        try:
            import time
            
            # 检查是否是灯控制命令
            if hasattr(conn, "last_light_control") and conn.last_light_control:
                last_control = conn.last_light_control
                
                # 检查 seq_id 是否匹配
                if last_control.get("seq_id") == seq_id:
                    action = last_control.get("action")
                    
                    # 从缓存中获取其他状态数据
                    old_state = {}
                    if hasattr(conn, "iot_descriptors") and "smart_doorlock" in conn.iot_descriptors:
                        old_state = conn.iot_descriptors["smart_doorlock"]
                    
                    # 确定新的灯状态
                    new_light_state = 1 if action == "on" else 0
                    
                    # 构造 status_report 消息（使用默认值避免 null）
                    status_report = {
                        "type": "status_report",
                        "ts": int(time.time() * 1000),
                        "data": {
                            "bat": old_state.get("battery") if old_state.get("battery") is not None else 0,
                            "lux": old_state.get("lux") if old_state.get("lux") is not None else 0,
                            "lock": old_state.get("lock_state") if old_state.get("lock_state") is not None else 0,
                            "light": new_light_state
                        }
                    }
                    
                    # 更新内存缓存
                    if not hasattr(conn, "iot_descriptors"):
                        conn.iot_descriptors = {}
                    
                    conn.iot_descriptors["smart_doorlock"] = {
                        "battery": status_report["data"]["bat"],
                        "lux": status_report["data"]["lux"],
                        "lock_state": status_report["data"]["lock"],
                        "light_state": new_light_state,
                        "last_update": status_report["ts"]
                    }
                    
                    conn.logger.bind(tag=TAG).info(
                        f"根据灯控制 ACK 构造 status_report: light={new_light_state} ({action}), "
                        f"bat={status_report['data']['bat']}, lux={status_report['data']['lux']}, lock={status_report['data']['lock']}"
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
                    
                    # 清除缓存
                    conn.last_light_control = None
            
        except Exception as e:
            conn.logger.bind(tag=TAG).warning(f"根据 ACK 更新设备状态失败: {e}")

    async def _handle_user_mgmt_delete(self, conn, seq_id: str):
        """处理用户管理删除/清空命令的数据库同步
        
        ESP32 对 del/clear 命令返回 ack（而非 user_mgmt_result），
        因此需要在 ack 处理中执行数据库软删除。
        """
        try:
            if not hasattr(conn, "last_user_mgmt_cmd") or not conn.last_user_mgmt_cmd:
                return
            
            last_cmd = conn.last_user_mgmt_cmd
            # 检查 seq_id 是否匹配
            if last_cmd.get("seq_id") != seq_id:
                return
            
            command = last_cmd.get("command")
            category = last_cmd.get("category")
            
            # 只处理 del 和 clear 命令
            if command not in ("del", "clear"):
                return
            
            db = _get_base_database(conn)
            if not db:
                conn.logger.bind(tag=TAG).warning("无法获取数据库实例，跳过删除同步")
                return
            
            if command == "del":
                user_id = last_cmd.get("user_id")
                if user_id is not None:
                    db.delete_doorlock_user(
                        device_id=conn.device_id,
                        user_type=category,
                        user_id=user_id
                    )
                    conn.logger.bind(tag=TAG).info(
                        f"已从数据库软删除{category}用户: device_id={conn.device_id}, user_id={user_id}"
                    )
            
            elif command == "clear":
                count = db.clear_doorlock_users(
                    device_id=conn.device_id,
                    user_type=category
                )
                conn.logger.bind(tag=TAG).info(
                    f"已清空数据库中{category}用户: device_id={conn.device_id}, 共 {count} 条"
                )
            
            # 清除缓存，避免重复处理
            conn.last_user_mgmt_cmd = None
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理用户管理删除同步失败: {e}")

    async def _forward_to_apps(self, conn, msg_json: Dict[str, Any]):
        """转发 ACK 到所有关联的 App"""
        try:
            manager = ConnectionManager.get_instance()
            app_conns = manager.get_app_conns(conn.device_id)
            
            if not app_conns:
                return
            
            msg = json.dumps(msg_json)
            for app_conn in app_conns:
                if app_conn.websocket:
                    await app_conn.websocket.send(msg)
                    
            conn.logger.bind(tag=TAG).debug(f"ACK 已转发给 {len(app_conns)} 个 App")
                    
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发 ACK 失败: {e}")
