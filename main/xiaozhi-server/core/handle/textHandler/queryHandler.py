"""
数据查询消息处理器

协议版本: v2.5
支持查询:
- status: 当前设备状态
- status_history: 历史状态
- events: 事件历史
- unlock_logs: 开锁日志
- media_files: 媒体文件列表
- password: 设备密码
- visitor_intents: 访客意图历史
- package_alerts: 快递警报历史
"""
import json
from typing import Dict, Any, Optional
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.connection_manager import ConnectionManager
from core.handle.textHandler.faceRecognitionHandler import get_face_service

TAG = __name__


def _get_ai_database(conn):
    """获取 AI 功能数据库实例（DoorlockDatabase）
    
    用于访客意图、快递警报等 AI 功能查询
    """
    try:
        face_service = get_face_service(conn.logger)
        # 检查 face_service 是否有 doorlock_db 属性
        if hasattr(face_service, 'doorlock_db'):
            return face_service.doorlock_db
        
        # 如果没有，尝试创建 DoorlockDatabase 实例
        from core.providers.doorlock.doorlock_database import DoorlockDatabase
        from config.config_loader import load_config
        
        config = load_config()
        doorlock_db = DoorlockDatabase(config)
        
        # 缓存到 face_service 中，避免重复创建
        face_service.doorlock_db = doorlock_db
        
        return doorlock_db
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"获取 AI 数据库实例失败: {e}")
        return None


def _get_base_database(conn):
    """获取基础功能数据库实例（Database）
    
    用于设备状态、事件、开锁日志、密码、门锁用户等基础查询
    """
    try:
        face_service = get_face_service(conn.logger)
        # 检查 face_service 是否有 db 属性
        if hasattr(face_service, 'db'):
            return face_service.db
        
        # 如果没有，尝试创建 Database 实例
        from core.providers.doorlock.database import Database
        from config.config_loader import load_config
        
        config = load_config()
        mysql_config = config.get('mysql', {})
        base_db = Database(mysql_config, logger=conn.logger, auto_init=False)
        
        # 缓存到 face_service 中，避免重复创建
        face_service.db = base_db
        
        return base_db
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"获取基础数据库实例失败: {e}")
        return None


class QueryHandler(TextMessageHandler):
    """处理 App 数据查询请求"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.QUERY

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        # 仅处理 App 发送的查询
        if not hasattr(conn, "client_type") or conn.client_type != "app":
            return
        
        target = msg_json.get("target")
        data = msg_json.get("data", {})
        
        conn.logger.bind(tag=TAG).info(f"收到数据查询请求: target={target}")
        
        handlers = {
            "status": self._query_status,
            "status_history": self._query_status_history,
            "events": self._query_events,
            "unlock_logs": self._query_unlock_logs,
            "media_files": self._query_media_files,
            "password": self._query_password,
            "visitor_intents": self._query_visitor_intents,  # 新增访客意图查询
            "package_alerts": self._query_package_alerts,    # 新增快递警报查询
            "doorlock_users": self._query_doorlock_users,    # 新增门锁用户查询
        }
        
        handler = handlers.get(target)
        if handler:
            await handler(conn, data)
        else:
            await self._send_error(conn, target, f"未知查询目标: {target}")

    async def _query_status(self, conn, data: Dict):
        """查询当前设备状态（从内存缓存读取）"""
        try:
            # 获取 ESP32 连接，读取缓存的状态
            manager = ConnectionManager.get_instance()
            esp32_conn = manager.get_esp32_conn(conn.device_id)
            
            if esp32_conn and hasattr(esp32_conn, "device_status"):
                status = esp32_conn.device_status
                await self._send_response(conn, "status", {
                    "battery": status.get("bat", 0),
                    "lux": status.get("lux", 0),
                    "lock_state": status.get("lock", 0),
                    "light_state": status.get("light", 0),
                    "last_update": status.get("ts", 0)
                })
            else:
                # 尝试从数据库读取最新状态
                db = _get_base_database(conn)
                if db:
                    status = db.get_latest_status(conn.device_id)
                    if status:
                        await self._send_response(conn, "status", status)
                        return
                
                await self._send_error(conn, "status", "暂无设备状态数据")
                
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"查询设备状态失败: {e}")
            await self._send_error(conn, "status", str(e))

    async def _query_status_history(self, conn, data: Dict):
        """查询历史状态"""
        try:
            limit = min(data.get("limit", 100), 500)
            offset = data.get("offset", 0)
            
            db = _get_base_database(conn)
            if not db:
                await self._send_error(conn, "status_history", "数据库不可用")
                return
            
            records, total = db.get_status_history(
                device_id=conn.device_id,
                limit=limit,
                offset=offset
            )
            
            # 检查是否有数据
            if total == 0 and offset == 0:
                conn.logger.bind(tag=TAG).info(f"设备 {conn.device_id} 暂无历史状态数据")
            
            await self._send_response(conn, "status_history", {
                "records": records,
                "total": total,
                "limit": limit,
                "offset": offset
            })
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"查询历史状态失败: {e}")
            await self._send_error(conn, "status_history", str(e))

    async def _query_events(self, conn, data: Dict):
        """查询事件历史"""
        try:
            event_type = data.get("event_type")
            limit = min(data.get("limit", 100), 500)
            offset = data.get("offset", 0)
            
            db = _get_base_database(conn)
            if not db:
                await self._send_error(conn, "events", "数据库不可用")
                return
            
            records, total = db.get_events(
                device_id=conn.device_id,
                event_type=event_type,
                limit=limit,
                offset=offset
            )
            
            # 检查是否有数据
            if total == 0 and offset == 0:
                filter_msg = f"（类型: {event_type}）" if event_type else ""
                conn.logger.bind(tag=TAG).info(f"设备 {conn.device_id} 暂无事件历史数据{filter_msg}")
            
            await self._send_response(conn, "events", {
                "records": records,
                "total": total,
                "limit": limit,
                "offset": offset
            })
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"查询事件历史失败: {e}")
            await self._send_error(conn, "events", str(e))

    async def _query_unlock_logs(self, conn, data: Dict):
        """查询开锁日志"""
        try:
            method = data.get("method")
            result = data.get("result")
            limit = min(data.get("limit", 100), 500)
            offset = data.get("offset", 0)
            
            db = _get_base_database(conn)
            if not db:
                await self._send_error(conn, "unlock_logs", "数据库不可用")
                return
            
            records, total = db.get_unlock_logs(
                device_id=conn.device_id,
                method=method,
                result=result,
                limit=limit,
                offset=offset
            )
            
            # 检查是否有数据
            if total == 0 and offset == 0:
                filter_parts = []
                if method:
                    filter_parts.append(f"方式: {method}")
                if result is not None:
                    filter_parts.append(f"结果: {'成功' if result == 1 else '失败'}")
                filter_msg = f"（{', '.join(filter_parts)}）" if filter_parts else ""
                conn.logger.bind(tag=TAG).info(f"设备 {conn.device_id} 暂无开锁日志数据{filter_msg}")
            
            await self._send_response(conn, "unlock_logs", {
                "records": records,
                "total": total,
                "limit": limit,
                "offset": offset
            })
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"查询开锁日志失败: {e}")
            await self._send_error(conn, "unlock_logs", str(e))

    async def _query_media_files(self, conn, data: Dict):
        """查询媒体文件列表"""
        try:
            file_type = data.get("file_type")
            date_from = data.get("date_from")
            date_to = data.get("date_to")
            limit = min(data.get("limit", 100), 500)
            offset = data.get("offset", 0)
            
            db = _get_base_database(conn)
            if not db:
                await self._send_error(conn, "media_files", "数据库不可用")
                return
            
            records, total = db.get_media_files(
                device_id=conn.device_id,
                file_type=file_type,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                offset=offset
            )
            
            # 检查是否有数据
            if total == 0 and offset == 0:
                filter_parts = []
                if file_type:
                    filter_parts.append(f"类型: {file_type}")
                if date_from:
                    filter_parts.append(f"起始: {date_from}")
                if date_to:
                    filter_parts.append(f"结束: {date_to}")
                filter_msg = f"（{', '.join(filter_parts)}）" if filter_parts else ""
                conn.logger.bind(tag=TAG).info(f"设备 {conn.device_id} 暂无媒体文件数据{filter_msg}")
            
            await self._send_response(conn, "media_files", {
                "records": records,
                "total": total,
                "limit": limit,
                "offset": offset
            })
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"查询媒体文件失败: {e}")
            await self._send_error(conn, "media_files", str(e))

    async def _query_password(self, conn, data: Dict):
        """查询设备密码（从服务器数据库读取）"""
        try:
            db = _get_base_database(conn)
            if not db:
                await self._send_error(conn, "password", "数据库不可用")
                return
            
            # 从数据库获取密码
            password = db.get_device_password(conn.device_id)
            
            if password:
                conn.logger.bind(tag=TAG).info(
                    f"密码查询成功: device_id={conn.device_id}, password_length={len(password)}"
                )
                await self._send_response(conn, "password", {
                    "password": password
                })
            else:
                conn.logger.bind(tag=TAG).warning(f"设备 {conn.device_id} 密码不存在，返回默认密码")
                await self._send_response(conn, "password", {
                    "password": "123456"
                })
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"查询密码失败: {e}")
            await self._send_error(conn, "password", str(e))

    async def _query_visitor_intents(self, conn, data: Dict):
        """查询访客意图历史
        
        请求参数:
        - start_date: 开始日期 (YYYY-MM-DD)，可选
        - end_date: 结束日期 (YYYY-MM-DD)，可选
        - limit: 返回条数，默认20，最大100
        - offset: 偏移量，默认0
        """
        try:
            from datetime import datetime
            
            start_date_str = data.get("start_date")
            end_date_str = data.get("end_date")
            limit = min(data.get("limit", 20), 100)
            offset = data.get("offset", 0)
            
            # 转换日期字符串为 datetime 对象
            start_date = None
            end_date = None
            
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                except ValueError:
                    conn.logger.bind(tag=TAG).warning(f"无效的开始日期格式: {start_date_str}")
            
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                except ValueError:
                    conn.logger.bind(tag=TAG).warning(f"无效的结束日期格式: {end_date_str}")
            
            db = _get_ai_database(conn)
            if not db:
                await self._send_error(conn, "visitor_intents", "数据库不可用")
                return
            
            # 调用数据库方法查询
            records, total = await db.get_visitor_intents(
                device_id=conn.device_id,
                limit=limit,
                offset=offset,
                start_date=start_date,
                end_date=end_date
            )
            
            # 转换记录为字典格式
            records_dict = []
            for record in records:
                # important_notes 和 ai_analysis 嵌套在 intent_summary 字典中
                intent_summary = record.intent_summary or {}
                record_dict = {
                    "id": record.id,
                    "visit_id": record.visit_id,
                    "session_id": record.session_id,
                    "person_id": record.person_id,
                    "intent_type": record.intent_type,
                    "intent_summary": intent_summary,
                    "important_notes": intent_summary.get("important_notes", []),
                    "ai_analysis": intent_summary.get("ai_analysis", ""),
                    "dialogue_history": record.dialogue_history or [],
                    "created_at": record.created_at.isoformat() if record.created_at else None
                }
                records_dict.append(record_dict)
            
            # 检查是否有数据
            if total == 0 and offset == 0:
                filter_parts = []
                if start_date_str:
                    filter_parts.append(f"起始: {start_date_str}")
                if end_date_str:
                    filter_parts.append(f"结束: {end_date_str}")
                filter_msg = f"（{', '.join(filter_parts)}）" if filter_parts else ""
                conn.logger.bind(tag=TAG).info(f"设备 {conn.device_id} 暂无访客意图历史数据{filter_msg}")
            
            conn.logger.bind(tag=TAG).info(
                f"查询访客意图历史成功: device_id={conn.device_id}, count={len(records_dict)}, total={total}"
            )
            
            await self._send_response(conn, "visitor_intents", {
                "records": records_dict,
                "total": total,
                "limit": limit,
                "offset": offset
            })
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"查询访客意图历史失败: device_id={conn.device_id}, error={e}")
            await self._send_error(conn, "visitor_intents", str(e))

    async def _query_package_alerts(self, conn, data: Dict):
        """查询快递警报历史
        
        请求参数:
        - start_date: 开始日期 (YYYY-MM-DD)，可选
        - end_date: 结束日期 (YYYY-MM-DD)，可选
        - limit: 返回条数，默认20，最大100
        - offset: 偏移量，默认0
        """
        try:
            from datetime import datetime
            
            start_date_str = data.get("start_date")
            end_date_str = data.get("end_date")
            limit = min(data.get("limit", 20), 100)
            offset = data.get("offset", 0)
            
            # 转换日期字符串为 datetime 对象
            start_date = None
            end_date = None
            
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                except ValueError:
                    conn.logger.bind(tag=TAG).warning(f"无效的开始日期格式: {start_date_str}")
            
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                except ValueError:
                    conn.logger.bind(tag=TAG).warning(f"无效的结束日期格式: {end_date_str}")
            
            db = _get_ai_database(conn)
            if not db:
                await self._send_error(conn, "package_alerts", "数据库不可用")
                return
            
            # 调用数据库方法查询
            records, total = await db.get_package_alerts(
                device_id=conn.device_id,
                limit=limit,
                offset=offset,
                start_date=start_date,
                end_date=end_date
            )
            
            # 转换记录为字典格式
            records_dict = []
            for record in records:
                record_dict = {
                    "id": record.id,
                    "device_id": record.device_id,
                    "session_id": record.session_id,
                    "threat_level": record.threat_level,
                    "action": record.action,
                    "description": record.description or "",
                    "photo_path": record.photo_path or "",
                    "voice_warning_sent": record.voice_warning_sent,
                    "notified": record.notified,
                    "created_at": record.created_at.isoformat() if record.created_at else None
                }
                records_dict.append(record_dict)
            
            # 检查是否有数据
            if total == 0 and offset == 0:
                filter_parts = []
                if start_date_str:
                    filter_parts.append(f"起始: {start_date_str}")
                if end_date_str:
                    filter_parts.append(f"结束: {end_date_str}")
                filter_msg = f"（{', '.join(filter_parts)}）" if filter_parts else ""
                conn.logger.bind(tag=TAG).info(f"设备 {conn.device_id} 暂无快递警报历史数据{filter_msg}")
            
            conn.logger.bind(tag=TAG).info(
                f"查询快递警报历史成功: device_id={conn.device_id}, count={len(records_dict)}, total={total}"
            )
            
            await self._send_response(conn, "package_alerts", {
                "records": records_dict,
                "total": total,
                "limit": limit,
                "offset": offset
            })
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"查询快递警报历史失败: device_id={conn.device_id}, error={e}")
            await self._send_error(conn, "package_alerts", str(e))

    async def _query_doorlock_users(self, conn, data: Dict):
        """查询门锁用户列表
        
        适配实际表结构：doorlock_users(device_id, user_type, user_id, user_name, user_data, status)
        
        请求参数:
        - user_type: 用户类型过滤（可选）：finger/nfc/password
        - limit: 返回条数，默认100，最大500
        - offset: 偏移量，默认0
        """
        try:
            user_type = data.get("user_type")
            limit = min(data.get("limit", 100), 500)
            offset = data.get("offset", 0)
            
            db = _get_base_database(conn)
            if not db:
                await self._send_error(conn, "doorlock_users", "数据库不可用")
                return
            
            # 直接通过 user_type 参数查询，数据库方法已支持过滤
            all_users = db.get_doorlock_users(conn.device_id, user_type=user_type)
            
            # 分页
            total = len(all_users)
            records = all_users[offset:offset + limit]
            
            # 转换记录格式（适配实际表字段）
            records_dict = []
            for user in records:
                record_dict = {
                    "id": user.get('id'),
                    "device_id": user.get('device_id'),
                    "user_type": user.get('user_type', ''),
                    "user_id": user.get('user_id'),
                    "user_name": user.get('user_name', ''),
                    "user_data": user.get('user_data', ''),
                    "status": user.get('status', 1),
                    "created_at": user.get('created_at').isoformat() if user.get('created_at') else None,
                    "updated_at": user.get('updated_at').isoformat() if user.get('updated_at') else None,
                    "created_by": user.get('created_by', '')
                }
                records_dict.append(record_dict)
            
            # 检查是否有数据
            if total == 0 and offset == 0:
                filter_msg = f"（类型: {user_type}）" if user_type else ""
                conn.logger.bind(tag=TAG).info(f"设备 {conn.device_id} 暂无门锁用户数据{filter_msg}")
            
            conn.logger.bind(tag=TAG).info(
                f"查询门锁用户成功: device_id={conn.device_id}, count={len(records_dict)}, total={total}"
            )
            
            await self._send_response(conn, "doorlock_users", {
                "records": records_dict,
                "total": total,
                "limit": limit,
                "offset": offset
            })
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"查询门锁用户失败: device_id={conn.device_id}, error={e}")
            await self._send_error(conn, "doorlock_users", str(e))

    async def _send_response(self, conn, target: str, data: Any):
        """发送查询响应"""
        try:
            await conn.websocket.send(json.dumps({
                "type": "query_result",
                "target": target,
                "status": "success",
                "data": data
            }))
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"发送查询响应失败: {e}")

    async def _send_error(self, conn, target: str, error: str):
        """发送错误响应"""
        try:
            conn.logger.bind(tag=TAG).error(f"查询失败: target={target}, error={error}")
            await conn.websocket.send(json.dumps({
                "type": "query_result",
                "target": target,
                "status": "error",
                "error": error
            }))
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"发送错误响应失败: {e}")
