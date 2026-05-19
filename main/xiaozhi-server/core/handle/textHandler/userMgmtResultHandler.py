"""
用户管理结果处理器
"""
import json
from typing import Dict, Any
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.connection_manager import ConnectionManager
from core.handle.textHandler.queryHandler import _get_base_database

TAG = __name__


class UserMgmtResultHandler(TextMessageHandler):
    """处理 ESP32 用户管理结果上报"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.USER_MGMT_RESULT

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理用户管理结果
        
        消息格式:
        {
            "type": "user_mgmt_result",
            "category": "finger",
            "command": "add",
            "result": true,
            "val": 6,
            "msg": "Success"
        }
        
        category: finger/nfc/password
        command: add/del/clear/query/set
        val: 成功时=分配的ID/查询数量，失败时=错误码
        """
        try:
            category = msg_json.get("category")
            command = msg_json.get("command")
            result = msg_json.get("result")
            val = msg_json.get("val")
            msg = msg_json.get("msg", "")
            
            if result:
                conn.logger.bind(tag=TAG).info(
                    f"用户管理成功: {category}/{command}, val={val}"
                )
                
                # 保存到数据库
                await self._save_to_database(conn, msg_json)
            else:
                conn.logger.bind(tag=TAG).warning(
                    f"用户管理失败: {category}/{command}, error={val}, msg={msg}"
                )
            
            # 转发给关联的 App
            await self._forward_to_apps(conn, msg_json)
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理用户管理结果失败: {e}")

    async def _forward_to_apps(self, conn, msg_json: Dict[str, Any]):
        """转发结果到所有关联的 App"""
        try:
            manager = ConnectionManager.get_instance()
            app_conns = manager.get_app_conns(conn.device_id)
            
            if not app_conns:
                return
            
            for app_conn in app_conns:
                if app_conn.websocket:
                    await app_conn.websocket.send(json.dumps(msg_json))
                    
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"转发结果失败: {e}")

    async def _save_to_database(self, conn, msg_json: Dict[str, Any]):
        """保存用户管理结果到数据库
        
        适配实际表结构：doorlock_users(device_id, user_type, user_id, user_name, user_data, status, created_by)
        
        处理场景：
        - finger/add: 插入一条 user_type=finger 的记录
        - nfc/add: 插入一条 user_type=nfc 的记录
        - finger/del: 软删除对应的指纹记录
        - nfc/del: 软删除对应的 NFC 记录
        - finger/clear: 软删除所有指纹记录
        - nfc/clear: 软删除所有 NFC 记录
        """
        try:
            db = _get_base_database(conn)
            if not db:
                conn.logger.bind(tag=TAG).warning("无法获取数据库实例，跳过保存")
                return
            
            category = msg_json.get("category")
            command = msg_json.get("command")
            result = msg_json.get("result")
            val = msg_json.get("val")
            
            if not result:
                return
            
            # 获取缓存的命令信息（从 ESP32 连接对象）
            last_cmd = getattr(conn, "last_user_mgmt_cmd", None)
            # payload 就是 App 端为该用户设置的备注名
            user_name = last_cmd.get("payload") if last_cmd else None
            created_by = last_cmd.get("app_id") if last_cmd else None
            
            # 处理添加（指纹/NFC）
            if command == "add" and category in ("finger", "nfc"):
                # AlreadyExists 表示该指纹/NFC 已存在，val 不是有效 ID，跳过保存
                msg_text = msg_json.get("msg", "")
                if msg_text == "AlreadyExists":
                    conn.logger.bind(tag=TAG).info(
                        f"{category}已存在（AlreadyExists），跳过数据库保存"
                    )
                    return
                
                assigned_id = val  # ESP32 返回的分配 ID
                default_name = f"指纹用户{assigned_id}" if category == "finger" else f"NFC用户{assigned_id}"
                
                db.save_doorlock_user(
                    device_id=conn.device_id,
                    user_id=assigned_id,
                    user_type=category,
                    user_name=user_name or default_name,
                    created_by=created_by
                )
                conn.logger.bind(tag=TAG).info(
                    f"已保存{category}用户到数据库: device_id={conn.device_id}, "
                    f"user_id={assigned_id}, user_name={user_name or default_name}"
                )
            
            # 处理删除（指纹/NFC）
            elif command == "del" and category in ("finger", "nfc"):
                deleted_id = val  # ESP32 返回的被删除 ID
                db.delete_doorlock_user(
                    device_id=conn.device_id,
                    user_type=category,
                    user_id=deleted_id
                )
                conn.logger.bind(tag=TAG).info(
                    f"已删除{category}用户: device_id={conn.device_id}, user_id={deleted_id}"
                )
            
            # 处理清空（指纹/NFC）
            elif command == "clear" and category in ("finger", "nfc"):
                count = db.clear_doorlock_users(
                    device_id=conn.device_id,
                    user_type=category
                )
                conn.logger.bind(tag=TAG).info(
                    f"已清空设备 {conn.device_id} 所有{category}用户，共 {count} 条"
                )
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"保存用户管理结果到数据库失败: {e}")
            # 不抛出异常，避免影响转发给 App
