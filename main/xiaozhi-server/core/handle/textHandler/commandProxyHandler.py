"""
命令代理处理器 - 处理 App 发送的设备控制命令

协议版本: v5.2
- App 发送的 lock_control、dev_control、user_mgmt 命令
- 服务器记录操作日志后转发给 ESP32
- 支持 app_id 追踪
- 支持命令下发重试机制（等待 esp32_ack）
"""
import json
import time
import asyncio
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.connection_manager import ConnectionManager
from core.handle.textHandler.faceRecognitionHandler import get_face_service
from core.constants.error_codes import ErrorCode

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
            await self._send_error(conn, "设备离线", code=ErrorCode.DEVICE_OFFLINE)
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
        """转发命令到 ESP32（带重试机制）"""
        try:
            # 透传 App 的 seq_id（v5.2 协议）
            seq_id = msg_json.get("seq_id")
            if not seq_id:
                # 如果 App 没有提供 seq_id，生成新的（兼容旧版）
                seq_id = f"{int(time.time() * 1000)}_0"
                msg_json["seq_id"] = seq_id
                conn.logger.bind(tag=TAG).warning(f"App 未提供 seq_id，已生成: {seq_id}")
            
            # 移除 App 协议特有字段（兼容旧版）
            msg_json.pop("msg_id", None)
            
            # 如果是开锁命令，缓存 app_id 到 ESP32 连接对象
            # 供 logReportHandler 填充 remote 开锁日志的 uid
            command = msg_json.get("command")
            if command == "unlock":
                esp32_conn.last_remote_unlock = {
                    "ts": int(time.time() * 1000),
                    "app_id": conn.app_id,
                    "seq_id": seq_id
                }
                conn.logger.bind(tag=TAG).debug(
                    f"缓存远程开锁命令: app_id={conn.app_id}"
                )
            
            # 使用重试机制转发命令
            success = await self._forward_with_retry(conn, esp32_conn, msg_json)
            
            if success:
                conn.logger.bind(tag=TAG).debug(f"命令已成功转发到 ESP32: seq_id={seq_id}")
            else:
                conn.logger.bind(tag=TAG).warning(f"命令转发失败（重试耗尽）: seq_id={seq_id}")
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发命令失败: {e}")
            await self._send_error(conn, f"转发失败: {str(e)}", code=ErrorCode.INTERNAL_ERROR)

    async def _forward_with_retry(self, conn, esp32_conn, msg_json: Dict[str, Any]) -> bool:
        """转发命令到 ESP32，带重试机制
        
        Args:
            conn: App 连接对象
            esp32_conn: ESP32 连接对象
            msg_json: 命令消息
            
        Returns:
            bool: 是否成功收到 esp32_ack
        """
        seq_id = msg_json.get("seq_id")
        max_retries = 3
        
        for retry in range(max_retries):
            try:
                # 发送命令到 ESP32
                await esp32_conn.websocket.send(json.dumps(msg_json, ensure_ascii=False))
                conn.logger.bind(tag=TAG).debug(
                    f"命令已发送到 ESP32（第 {retry + 1} 次）: seq_id={seq_id}"
                )
                
                # 等待 esp32_ack
                ack_received = await self._wait_for_esp32_ack(esp32_conn, seq_id, timeout=2.0)
                
                if ack_received:
                    conn.logger.bind(tag=TAG).info(
                        f"收到 ESP32 确认: seq_id={seq_id}, 重试次数={retry + 1}"
                    )
                    return True
                else:
                    conn.logger.bind(tag=TAG).warning(
                        f"等待 ESP32 确认超时（第 {retry + 1} 次）: seq_id={seq_id}"
                    )
                    
            except Exception as e:
                conn.logger.bind(tag=TAG).warning(
                    f"发送命令失败（第 {retry + 1} 次）: seq_id={seq_id}, error={e}"
                )
        
        # 重试全部失败，通知 App
        await self._send_error(conn, "设备无响应，请检查设备状态", code=ErrorCode.TIMEOUT)
        return False
    
    async def _wait_for_esp32_ack(self, esp32_conn, seq_id: str, timeout: float) -> bool:
        """等待 ESP32 的 esp32_ack 响应
        
        Args:
            esp32_conn: ESP32 连接对象
            seq_id: 消息序列 ID
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否收到 esp32_ack（且 code == 0）
        """
        # 创建 Future 对象
        future = asyncio.Future()
        
        # 初始化 _pending_esp32_acks 字典（如果不存在）
        if not hasattr(esp32_conn, "_pending_esp32_acks"):
            esp32_conn._pending_esp32_acks = {}
        
        # 注册 Future
        esp32_conn._pending_esp32_acks[seq_id] = future
        
        try:
            # 等待 esp32_ack（带超时）
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            return False
        finally:
            # 清理 Future
            esp32_conn._pending_esp32_acks.pop(seq_id, None)

    async def _send_error(self, conn, message: str, code: int = ErrorCode.INTERNAL_ERROR):
        """发送错误响应
        
        Args:
            conn: App 连接对象
            message: 错误消息
            code: 统一错误码（0-10）
        """
        try:
            # 添加日志记录
            conn.logger.bind(tag=TAG).warning(
                f"锁控命令错误: device_id={conn.device_id}, app_id={conn.app_id}, "
                f"code={code}, message={message}"
            )
            
            # 返回 ack 格式（符合协议）
            # 注意：需要从原始消息中获取 seq_id
            await conn.websocket.send(json.dumps({
                "type": "ack",
                "code": code,
                "msg": message
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
            await self._send_error(conn, "设备离线", code=ErrorCode.DEVICE_OFFLINE)
            return
        
        # 转发给 ESP32
        await self._forward_to_esp32(conn, esp32_conn, msg_json)

    async def _forward_to_esp32(self, conn, esp32_conn, msg_json: Dict[str, Any]):
        """转发命令到 ESP32（带重试机制）"""
        try:
            # 透传 App 的 seq_id（v5.2 协议）
            seq_id = msg_json.get("seq_id")
            if not seq_id:
                # 如果 App 没有提供 seq_id，生成新的（兼容旧版）
                seq_id = f"{int(time.time() * 1000)}_0"
                msg_json["seq_id"] = seq_id
                conn.logger.bind(tag=TAG).warning(f"App 未提供 seq_id，已生成: {seq_id}")
            
            # 移除 App 协议特有字段（兼容旧版）
            msg_json.pop("msg_id", None)
            
            # 缓存控制命令信息（用于后续构造 status_report）
            target = msg_json.get("target")
            action = msg_json.get("action")
            if target == "light":
                esp32_conn.last_light_control = {
                    "ts": int(time.time() * 1000),
                    "action": action,
                    "seq_id": seq_id
                }
                conn.logger.bind(tag=TAG).debug(
                    f"缓存灯控制命令: action={action}"
                )
            
            # 使用重试机制转发命令
            success = await self._forward_with_retry(conn, esp32_conn, msg_json)
            
            if success:
                conn.logger.bind(tag=TAG).debug(f"设备控制命令已成功转发: seq_id={seq_id}")
            else:
                conn.logger.bind(tag=TAG).warning(f"设备控制命令转发失败（重试耗尽）: seq_id={seq_id}")
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发命令失败: {e}")
            await self._send_error(conn, f"转发失败: {str(e)}", code=ErrorCode.INTERNAL_ERROR)

    async def _forward_with_retry(self, conn, esp32_conn, msg_json: Dict[str, Any]) -> bool:
        """转发命令到 ESP32，带重试机制
        
        Args:
            conn: App 连接对象
            esp32_conn: ESP32 连接对象
            msg_json: 命令消息
            
        Returns:
            bool: 是否成功收到 esp32_ack
        """
        seq_id = msg_json.get("seq_id")
        max_retries = 3
        
        for retry in range(max_retries):
            try:
                # 发送命令到 ESP32
                await esp32_conn.websocket.send(json.dumps(msg_json, ensure_ascii=False))
                conn.logger.bind(tag=TAG).debug(
                    f"设备控制命令已发送（第 {retry + 1} 次）: seq_id={seq_id}"
                )
                
                # 等待 esp32_ack
                ack_received = await self._wait_for_esp32_ack(esp32_conn, seq_id, timeout=2.0)
                
                if ack_received:
                    conn.logger.bind(tag=TAG).info(
                        f"收到 ESP32 确认: seq_id={seq_id}, 重试次数={retry + 1}"
                    )
                    return True
                else:
                    conn.logger.bind(tag=TAG).warning(
                        f"等待 ESP32 确认超时（第 {retry + 1} 次）: seq_id={seq_id}"
                    )
                    
            except Exception as e:
                conn.logger.bind(tag=TAG).warning(
                    f"发送设备控制命令失败（第 {retry + 1} 次）: seq_id={seq_id}, error={e}"
                )
        
        # 重试全部失败，通知 App
        await self._send_error(conn, "设备无响应，请检查设备状态", code=ErrorCode.TIMEOUT)
        return False
    
    async def _wait_for_esp32_ack(self, esp32_conn, seq_id: str, timeout: float) -> bool:
        """等待 ESP32 的 esp32_ack 响应
        
        Args:
            esp32_conn: ESP32 连接对象
            seq_id: 消息序列 ID
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否收到 esp32_ack（且 code == 0）
        """
        # 创建 Future 对象
        future = asyncio.Future()
        
        # 初始化 _pending_esp32_acks 字典（如果不存在）
        if not hasattr(esp32_conn, "_pending_esp32_acks"):
            esp32_conn._pending_esp32_acks = {}
        
        # 注册 Future
        esp32_conn._pending_esp32_acks[seq_id] = future
        
        try:
            # 等待 esp32_ack（带超时）
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            return False
        finally:
            # 清理 Future
            esp32_conn._pending_esp32_acks.pop(seq_id, None)

    async def _send_error(self, conn, message: str, code: int = ErrorCode.INTERNAL_ERROR):
        """发送错误响应
        
        Args:
            conn: App 连接对象
            message: 错误消息
            code: 统一错误码（0-10）
        """
        try:
            # 添加日志记录
            conn.logger.bind(tag=TAG).warning(
                f"设备控制错误: device_id={conn.device_id}, app_id={conn.app_id}, "
                f"code={code}, message={message}"
            )
            
            # 返回 ack 格式（符合协议）
            await conn.websocket.send(json.dumps({
                "type": "ack",
                "code": code,
                "msg": message
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
        
        # 密码查询已改为通过 query 接口，不再转发到 ESP32
        if category == "password" and command == "query":
            await self._send_error(
                conn, 
                "密码查询请使用 query 接口（target=password），不再支持通过 user_mgmt 查询",
                code=ErrorCode.PARAM_ERROR
            )
            return
        
        # 检查 ESP32 是否在线
        manager = ConnectionManager.get_instance()
        esp32_conn = manager.get_esp32_conn(conn.device_id)
        
        if not esp32_conn or not esp32_conn.websocket:
            await self._send_error(conn, "设备离线", code=ErrorCode.DEVICE_OFFLINE)
            return
        
        # 转发给 ESP32
        await self._forward_to_esp32(conn, esp32_conn, msg_json)

    async def _forward_to_esp32(self, conn, esp32_conn, msg_json: Dict[str, Any]):
        """转发命令到 ESP32（带重试机制）"""
        try:
            # 透传 App 的 seq_id（v5.2 协议）
            seq_id = msg_json.get("seq_id")
            if not seq_id:
                # 如果 App 没有提供 seq_id，生成新的（兼容旧版）
                seq_id = f"{int(time.time() * 1000)}_0"
                msg_json["seq_id"] = seq_id
                conn.logger.bind(tag=TAG).warning(f"App 未提供 seq_id，已生成: {seq_id}")
            
            # 移除 App 协议特有字段（兼容旧版）
            msg_json.pop("msg_id", None)
            
            # 缓存用户管理命令信息（用于后续保存到数据库）
            category = msg_json.get("category")
            command = msg_json.get("command")
            if command in ["add", "del", "clear"]:
                esp32_conn.last_user_mgmt_cmd = {
                    "ts": int(time.time() * 1000),
                    "category": category,
                    "command": command,
                    "user_name": msg_json.get("user_name"),  # App 提供的备注名（可选）
                    "payload": msg_json.get("payload"),      # App 提供的额外数据
                    "user_id": msg_json.get("user_id"),      # App 提供的用户 ID
                    "app_id": conn.app_id,                   # 记录操作者
                    "seq_id": seq_id
                }
                conn.logger.bind(tag=TAG).debug(
                    f"缓存用户管理命令: category={category}, command={command}, "
                    f"user_name={msg_json.get('user_name')}, payload={msg_json.get('payload')}"
                )
            
            # 使用重试机制转发命令
            success = await self._forward_with_retry(conn, esp32_conn, msg_json)
            
            if success:
                conn.logger.bind(tag=TAG).debug(f"用户管理命令已成功转发: seq_id={seq_id}")
            else:
                conn.logger.bind(tag=TAG).warning(f"用户管理命令转发失败（重试耗尽）: seq_id={seq_id}")
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发命令失败: {e}")
            await self._send_error(conn, f"转发失败: {str(e)}", code=ErrorCode.INTERNAL_ERROR)

    async def _forward_with_retry(self, conn, esp32_conn, msg_json: Dict[str, Any]) -> bool:
        """转发命令到 ESP32，带重试机制
        
        Args:
            conn: App 连接对象
            esp32_conn: ESP32 连接对象
            msg_json: 命令消息
            
        Returns:
            bool: 是否成功收到 esp32_ack
        """
        seq_id = msg_json.get("seq_id")
        max_retries = 3
        
        for retry in range(max_retries):
            try:
                # 发送命令到 ESP32
                await esp32_conn.websocket.send(json.dumps(msg_json, ensure_ascii=False))
                conn.logger.bind(tag=TAG).debug(
                    f"用户管理命令已发送（第 {retry + 1} 次）: seq_id={seq_id}"
                )
                
                # 等待 esp32_ack
                ack_received = await self._wait_for_esp32_ack(esp32_conn, seq_id, timeout=2.0)
                
                if ack_received:
                    conn.logger.bind(tag=TAG).info(
                        f"收到 ESP32 确认: seq_id={seq_id}, 重试次数={retry + 1}"
                    )
                    return True
                else:
                    conn.logger.bind(tag=TAG).warning(
                        f"等待 ESP32 确认超时（第 {retry + 1} 次）: seq_id={seq_id}"
                    )
                    
            except Exception as e:
                conn.logger.bind(tag=TAG).warning(
                    f"发送用户管理命令失败（第 {retry + 1} 次）: seq_id={seq_id}, error={e}"
                )
        
        # 重试全部失败，通知 App
        await self._send_error(conn, "设备无响应，请检查设备状态", code=ErrorCode.TIMEOUT)
        return False
    
    async def _wait_for_esp32_ack(self, esp32_conn, seq_id: str, timeout: float) -> bool:
        """等待 ESP32 的 esp32_ack 响应
        
        Args:
            esp32_conn: ESP32 连接对象
            seq_id: 消息序列 ID
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否收到 esp32_ack（且 code == 0）
        """
        # 创建 Future 对象
        future = asyncio.Future()
        
        # 初始化 _pending_esp32_acks 字典（如果不存在）
        if not hasattr(esp32_conn, "_pending_esp32_acks"):
            esp32_conn._pending_esp32_acks = {}
        
        # 注册 Future
        esp32_conn._pending_esp32_acks[seq_id] = future
        
        try:
            # 等待 esp32_ack（带超时）
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            return False
        finally:
            # 清理 Future
            esp32_conn._pending_esp32_acks.pop(seq_id, None)

    async def _send_error(self, conn, message: str, code: int = ErrorCode.INTERNAL_ERROR):
        """发送错误响应
        
        Args:
            conn: App 连接对象
            message: 错误消息
            code: 统一错误码（0-10）
        """
        try:
            # 添加日志记录
            conn.logger.bind(tag=TAG).warning(
                f"用户管理错误: device_id={conn.device_id}, app_id={conn.app_id}, "
                f"code={code}, message={message}"
            )
            
            # 返回 user_mgmt_result 格式（符合协议）
            await conn.websocket.send(json.dumps({
                "type": "user_mgmt_result",
                "result": False,
                "val": code,
                "msg": message
            }))
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"发送错误响应失败: {e}")
