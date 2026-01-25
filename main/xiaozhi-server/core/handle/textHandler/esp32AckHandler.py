"""
ESP32 第一级确认处理器（v5.2 协议）

处理 ESP32 发送的 esp32_ack 消息，表示"命令已收到，开始处理"。
这是两级确认机制的第一级，用于 Server 内部重试判断。

注意：esp32_ack 不转发给 App，仅用于 Server 内部逻辑。
"""
import json
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.constants.error_codes import is_valid_error_code, get_error_message

TAG = __name__


class Esp32AckHandler(TextMessageHandler):
    """处理 ESP32 第一级确认（命令已收到）"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.ESP32_ACK

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理 esp32_ack 消息
        
        消息格式:
        {
            "type": "esp32_ack",
            "seq_id": "1702234567890_0",
            "code": 0,
            "msg": "received"
        }
        
        处理逻辑:
        1. 解析 seq_id、code、msg 字段
        2. 验证错误码范围（0-10）
        3. 记录 DEBUG 级别日志
        4. 触发等待的 Future（用于停止重试）
        5. 不转发给 App（仅用于 Server 内部）
        
        Args:
            conn: ESP32 连接对象
            msg_json: 消息 JSON 对象
        """
        try:
            # 解析必需字段
            seq_id = msg_json.get("seq_id")
            if not seq_id:
                conn.logger.bind(tag=TAG).error("esp32_ack 缺少 seq_id 字段")
                return
            
            code = msg_json.get("code", 0)
            msg = msg_json.get("msg", "")
            
            # 验证错误码范围
            if not is_valid_error_code(code):
                conn.logger.bind(tag=TAG).warning(
                    f"esp32_ack 错误码超出范围: seq_id={seq_id}, code={code}"
                )
            
            # 记录日志（DEBUG 级别）
            if code == 0:
                conn.logger.bind(tag=TAG).debug(
                    f"ESP32 已接收命令: seq_id={seq_id}"
                )
            else:
                error_msg = get_error_message(code)
                conn.logger.bind(tag=TAG).debug(
                    f"ESP32 拒绝命令: seq_id={seq_id}, code={code}, "
                    f"msg={msg}, error={error_msg}"
                )
            
            # 触发等待的 Future（用于通知 CommandProxyHandler 停止重试）
            if hasattr(conn, "_pending_esp32_acks") and seq_id in conn._pending_esp32_acks:
                future = conn._pending_esp32_acks[seq_id]
                if not future.done():
                    # code == 0 表示成功接收，code != 0 表示拒绝
                    future.set_result(code == 0)
                    conn.logger.bind(tag=TAG).debug(
                        f"已触发 Future: seq_id={seq_id}, success={code == 0}"
                    )
            
            # 注意：esp32_ack 不转发给 App
            # 这是 Server 内部使用的消息，用于判断是否需要重试
            # App 只需要知道最终的 ack 结果
                    
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理 esp32_ack 失败: {e}")
