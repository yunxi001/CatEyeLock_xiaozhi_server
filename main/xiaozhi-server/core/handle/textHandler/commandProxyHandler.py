"""
命令代理处理器 - 处理 App 发送的设备控制命令

协议版本: v2.2
- App 发送的 lock_control、dev_control、user_mgmt 命令
- 服务器记录操作日志后转发给 ESP32
- 支持 app_id 追踪
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


class LockControlProxyHandler(TextMessageHandler):
    """处理 App 发送的锁控命令
    
    支持的命令:
    - unlock: 远程开锁
    - lock: 远程关锁
    - temp_code: 设置临时密码
    """

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.LOCK_CONTROL

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        # 仅处理 App 发送的命令
        if not hasattr(conn, "client_type") or conn.client_type != "app":
            return
        
        command = msg_json.get("command")
        conn.logger.bind(tag=TAG).info(f"收到 App 锁控命令: {command}, app_id={conn.app_id}")
        
        # 检查 ESP32 是否在线
        manager = ConnectionManager.get_instance()
        esp32_conn = manager.get_esp32_conn(conn.device_id)
        
        if not esp32_conn or not esp32_conn.websocket:
            await self._send_error(conn, "设备离线")
            return
        
        # 记录操作日志（开锁命令）
        if command == "unlock":
            await self._log_unlock_operation(conn, msg_json)
        
        # 转发给 ESP32
        await self._forward_to_esp32(conn, esp32_conn, msg_json)

    async def _log_unlock_operation(self, conn, msg_json: Dict[str, Any]):
        """记录开锁操作日志"""
        try:
            db = _get_database(conn)
            if db:
                db.save_unlock_log(
                    device_id=conn.device_id,
                    method="remote",
                    user_id=0,
                    result=True,
                    fail_count=0
                )
                conn.logger.bind(tag=TAG).info(f"已记录远程开锁日志: app_id={conn.app_id}")
        except Exception as e:
            conn.logger.bind(tag=TAG).warning(f"记录开锁日志失败: {e}")

    async def _forward_to_esp32(self, conn, esp32_conn, msg_json: Dict[str, Any]):
        """转发命令到 ESP32"""
        try:
            # 添加 msg_id（ESP32 协议需要）
            msg_json["msg_id"] = f"cmd_{int(time.time() * 1000)}"
            
            # 移除 App 协议特有字段
            msg_json.pop("seq_id", None)
            
            # 如果是开锁命令，缓存 app_id 到 ESP32 连接对象
            # 供 logReportHandler 填充 remote 开锁日志的 uid
            command = msg_json.get("command")
            if command == "unlock":
                esp32_conn.last_remote_unlock = {
                    "ts": int(time.time() * 1000),
                    "app_id": conn.app_id,
                    "msg_id": msg_json["msg_id"]
                }
                conn.logger.bind(tag=TAG).debug(
                    f"缓存远程开锁命令: app_id={conn.app_id}"
                )
            
            await esp32_conn.websocket.send(json.dumps(msg_json, ensure_ascii=False))
            conn.logger.bind(tag=TAG).debug(f"命令已转发到 ESP32: {msg_json}")
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发命令失败: {e}")
            await self._send_error(conn, f"转发失败: {str(e)}")

    async def _send_error(self, conn, message: str):
        """发送错误响应"""
        try:
            await conn.websocket.send(json.dumps({
                "type": "lock_control",
                "status": "error",
                "message": message
            }))
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"发送错误响应失败: {e}")


class DevControlProxyHandler(TextMessageHandler):
    """处理 App 发送的设备控制命令
    
    支持的目标:
    - beep: 蜂鸣器控制
    - light: 补光灯控制
    - oled: OLED 显示控制
    """

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.DEV_CONTROL

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        # 仅处理 App 发送的命令
        if not hasattr(conn, "client_type") or conn.client_type != "app":
            return
        
        target = msg_json.get("target")
        conn.logger.bind(tag=TAG).info(f"收到 App 设备控制命令: target={target}, app_id={conn.app_id}")
        
        # 检查 ESP32 是否在线
        manager = ConnectionManager.get_instance()
        esp32_conn = manager.get_esp32_conn(conn.device_id)
        
        if not esp32_conn or not esp32_conn.websocket:
            await self._send_error(conn, "设备离线")
            return
        
        # 转发给 ESP32
        await self._forward_to_esp32(conn, esp32_conn, msg_json)

    async def _forward_to_esp32(self, conn, esp32_conn, msg_json: Dict[str, Any]):
        """转发命令到 ESP32"""
        try:
            msg_json["msg_id"] = f"cmd_{int(time.time() * 1000)}"
            msg_json.pop("seq_id", None)
            
            await esp32_conn.websocket.send(json.dumps(msg_json, ensure_ascii=False))
            conn.logger.bind(tag=TAG).debug(f"设备控制命令已转发: {msg_json}")
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发命令失败: {e}")
            await self._send_error(conn, f"转发失败: {str(e)}")

    async def _send_error(self, conn, message: str):
        """发送错误响应"""
        try:
            await conn.websocket.send(json.dumps({
                "type": "dev_control",
                "status": "error",
                "message": message
            }))
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"发送错误响应失败: {e}")


class UserMgmtProxyHandler(TextMessageHandler):
    """处理 App 发送的用户管理命令
    
    支持的类别:
    - finger: 指纹管理
    - nfc: NFC 卡管理
    - password: 密码管理
    """

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.USER_MGMT

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        # 仅处理 App 发送的命令
        if not hasattr(conn, "client_type") or conn.client_type != "app":
            return
        
        category = msg_json.get("category")
        command = msg_json.get("command")
        conn.logger.bind(tag=TAG).info(
            f"收到 App 用户管理命令: category={category}, command={command}, app_id={conn.app_id}"
        )
        
        # 检查 ESP32 是否在线
        manager = ConnectionManager.get_instance()
        esp32_conn = manager.get_esp32_conn(conn.device_id)
        
        if not esp32_conn or not esp32_conn.websocket:
            await self._send_error(conn, "设备离线")
            return
        
        # 转发给 ESP32
        await self._forward_to_esp32(conn, esp32_conn, msg_json)

    async def _forward_to_esp32(self, conn, esp32_conn, msg_json: Dict[str, Any]):
        """转发命令到 ESP32"""
        try:
            msg_json["msg_id"] = f"cmd_{int(time.time() * 1000)}"
            msg_json.pop("seq_id", None)
            
            await esp32_conn.websocket.send(json.dumps(msg_json, ensure_ascii=False))
            conn.logger.bind(tag=TAG).debug(f"用户管理命令已转发: {msg_json}")
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发命令失败: {e}")
            await self._send_error(conn, f"转发失败: {str(e)}")

    async def _send_error(self, conn, message: str):
        """发送错误响应"""
        try:
            await conn.websocket.send(json.dumps({
                "type": "user_mgmt",
                "status": "error",
                "message": message
            }))
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"发送错误响应失败: {e}")
