"""
ACK 响应处理器
"""
import json
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.connection_manager import ConnectionManager
from core.constants.error_codes import is_valid_error_code, get_error_message

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
            
            # 转发 ACK 给关联的 App（协议 v2.2）
            await self._forward_to_apps(conn, msg_json)
                    
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理 ACK 失败: {e}")

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
