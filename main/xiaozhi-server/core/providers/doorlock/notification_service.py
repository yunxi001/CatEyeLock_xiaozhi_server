"""
智能门锁AI通知服务

负责向App推送各类通知，包括：
- 访客意图识别结果通知
- 快递警报通知
- 看护状态变化通知
"""
import json
import time
from typing import Optional, List
from datetime import datetime
from loguru import logger

from core.connection_manager import ConnectionManager
from .constants import MessageType, IntentType, ThreatLevel, ActionType

TAG = "NotificationService"


class NotificationService:
    """门锁AI通知服务"""
    
    def __init__(self):
        """初始化通知服务"""
        self.connection_manager = ConnectionManager.get_instance()
        
        # 通知历史记录（用于失败重试）
        self._notification_history = []
        
        logger.bind(tag=TAG).info("通知服务初始化完成")
    
    async def notify_visitor_intent(
        self,
        visit_id: int,
        session_id: str,
        person_info: dict,
        intent_summary: dict,
        dialogue_text: list
    ) -> bool:
        """发送访客意图识别结果通知
        
        Args:
            visit_id: 访问记录ID
            session_id: 会话ID
            person_info: 人员信息（person_id, name, relation_type, photo_path）
            intent_summary: 意图总结（important_notes, intent_type, purpose, full_summary）
            dialogue_text: 对话文本列表
            
        Returns:
            是否发送成功
        """
        try:
            # 从session_id提取device_id
            device_id = session_id.split('_')[0] if '_' in session_id else session_id
            
            # 构建通知消息
            notification = {
                "type": MessageType.VISITOR_INTENT,
                "data": {
                    "visit_id": visit_id,
                    "session_id": session_id,
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "person_info": {
                        "person_id": person_info.get('person_id'),
                        "name": person_info.get('name'),
                        "relation_type": person_info.get('relation_type'),
                        "photo_path": person_info.get('photo_path')
                    },
                    "intent_summary": {
                        "important_notes": intent_summary.get('important_notes', []),
                        "intent_type": intent_summary.get('intent_type', IntentType.OTHER),
                        "purpose": intent_summary.get('purpose', ''),
                        "full_summary": intent_summary.get('full_summary', '')
                    },
                    "dialogue_text": dialogue_text
                }
            }
            
            # 发送通知
            success = await self._send_notification(device_id, notification)
            
            if success:
                logger.bind(tag=TAG).info(
                    f"发送访客意图通知成功: visit_id={visit_id}, session_id={session_id}, "
                    f"intent_type={intent_summary.get('intent_type')}"
                )
            else:
                logger.bind(tag=TAG).warning(
                    f"发送访客意图通知失败: visit_id={visit_id}, session_id={session_id}"
                )
            
            return success
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"发送访客意图通知异常: visit_id={visit_id}, session_id={session_id}, error={e}"
            )
            return False
    
    async def notify_package_alert(
        self,
        alert_id: int,
        session_id: str,
        threat_level: str,
        action: str,
        description: str,
        photo_path: str,
        voice_warning_text: str = None
    ) -> bool:
        """发送快递警报通知
        
        Args:
            alert_id: 警报记录ID
            session_id: 会话ID
            threat_level: 威胁等级（low/medium/high）
            action: 行为类型（taking/searching/damaging/normal/passing）
            description: 描述
            photo_path: 证据照片路径
            voice_warning_text: 语音警告文本（可选）
            
        Returns:
            是否发送成功
        """
        try:
            # 从session_id提取device_id
            device_id = session_id.split('_')[0] if '_' in session_id else session_id
            
            # 构建通知消息
            notification = {
                "type": MessageType.PACKAGE_ALERT,
                "data": {
                    "alert_id": alert_id,
                    "session_id": session_id,
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "threat_level": threat_level,
                    "action": action,
                    "description": description,
                    "photo_path": photo_path,
                    "voice_warning_sent": voice_warning_text is not None,
                    "voice_warning_text": voice_warning_text
                }
            }
            
            # 发送通知
            success = await self._send_notification(device_id, notification)
            
            if success:
                logger.bind(tag=TAG).info(
                    f"发送快递警报通知成功: alert_id={alert_id}, session_id={session_id}, "
                    f"threat_level={threat_level}, action={action}"
                )
            else:
                logger.bind(tag=TAG).warning(
                    f"发送快递警报通知失败: alert_id={alert_id}, session_id={session_id}"
                )
            
            return success
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"发送快递警报通知异常: alert_id={alert_id}, session_id={session_id}, error={e}"
            )
            return False
    
    async def notify_guard_status_change(
        self,
        device_id: str,
        active: bool,
        reason: str,
        baseline_image: Optional[str] = None,
        start_time: Optional[datetime] = None
    ) -> bool:
        """发送看护状态变化通知
        
        Args:
            device_id: 设备ID
            active: 是否激活
            reason: 变化原因
            baseline_image: 基准图片路径（可选）
            start_time: 启动时间（可选）
            
        Returns:
            是否发送成功
        """
        try:
            # 构建通知消息
            notification = {
                "type": MessageType.PACKAGE_GUARD_STATUS,
                "data": {
                    "device_id": device_id,
                    "active": active,
                    "reason": reason,
                    "baseline_image": baseline_image,
                    "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S') if start_time else None
                }
            }
            
            # 发送通知
            success = await self._send_notification(device_id, notification)
            
            if success:
                logger.bind(tag=TAG).info(
                    f"发送看护状态通知成功: device_id={device_id}, active={active}, reason={reason}"
                )
            else:
                logger.bind(tag=TAG).warning(
                    f"发送看护状态通知失败: device_id={device_id}, active={active}"
                )
            
            return success
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"发送看护状态通知异常: device_id={device_id}, active={active}, error={e}"
            )
            return False
    
    async def _send_notification(self, device_id: str, notification: dict) -> bool:
        """发送通知到App（内部方法）
        
        Args:
            device_id: 设备ID
            notification: 通知消息字典
            
        Returns:
            是否发送成功
        """
        try:
            # 获取关联的App连接
            app_conns = self.connection_manager.get_app_conns(device_id)
            
            if not app_conns:
                logger.bind(tag=TAG).warning(
                    f"无关联的App连接: device_id={device_id}, type={notification.get('type')}"
                )
                # 记录到历史，等待重试
                self._add_to_history(device_id, notification)
                return False
            
            # 添加时间戳
            notification['ts'] = int(time.time() * 1000)
            
            # 转换为JSON
            message = json.dumps(notification, ensure_ascii=False)
            
            # 发送到所有关联的App
            success_count = 0
            fail_count = 0
            
            for app_conn in app_conns:
                try:
                    if app_conn.websocket:
                        await app_conn.websocket.send(message)
                        success_count += 1
                        logger.bind(tag=TAG).debug(
                            f"通知已发送: device_id={device_id}, "
                            f"app_id={getattr(app_conn, 'app_id', 'unknown')}, "
                            f"type={notification.get('type')}"
                        )
                except Exception as e:
                    fail_count += 1
                    logger.bind(tag=TAG).warning(
                        f"发送通知失败: device_id={device_id}, "
                        f"app_id={getattr(app_conn, 'app_id', 'unknown')}, "
                        f"type={notification.get('type')}, error={e}"
                    )
            
            # 如果至少有一个App收到通知，认为成功
            if success_count > 0:
                logger.bind(tag=TAG).info(
                    f"通知发送完成: device_id={device_id}, type={notification.get('type')}, "
                    f"成功={success_count}, 失败={fail_count}"
                )
                return True
            else:
                # 全部失败，记录到历史
                self._add_to_history(device_id, notification)
                return False
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"发送通知异常: device_id={device_id}, type={notification.get('type')}, error={e}"
            )
            return False
    
    def _add_to_history(self, device_id: str, notification: dict):
        """添加通知到历史记录（用于失败重试）
        
        Args:
            device_id: 设备ID
            notification: 通知消息
        """
        self._notification_history.append({
            "device_id": device_id,
            "notification": notification,
            "timestamp": datetime.now(),
            "retry_count": 0
        })
        
        # 限制历史记录数量（最多保留100条）
        if len(self._notification_history) > 100:
            self._notification_history = self._notification_history[-100:]
        
        logger.bind(tag=TAG).debug(
            f"通知已添加到历史记录: device_id={device_id}, "
            f"type={notification.get('type')}, history_count={len(self._notification_history)}"
        )
    
    async def retry_failed_notifications(self, max_retry: int = 3):
        """重试失败的通知
        
        Args:
            max_retry: 最大重试次数
        """
        if not self._notification_history:
            return
        
        logger.bind(tag=TAG).info(
            f"开始重试失败的通知: count={len(self._notification_history)}"
        )
        
        # 复制历史记录，避免在迭代时修改
        history_copy = self._notification_history.copy()
        self._notification_history.clear()
        
        for record in history_copy:
            device_id = record['device_id']
            notification = record['notification']
            retry_count = record['retry_count']
            
            # 检查是否超过最大重试次数
            if retry_count >= max_retry:
                logger.bind(tag=TAG).warning(
                    f"通知重试次数已达上限，放弃: device_id={device_id}, "
                    f"type={notification.get('type')}, retry_count={retry_count}"
                )
                continue
            
            # 尝试重新发送
            success = await self._send_notification(device_id, notification)
            
            if not success:
                # 重试失败，增加重试计数并重新加入历史
                record['retry_count'] += 1
                self._notification_history.append(record)
                logger.bind(tag=TAG).debug(
                    f"通知重试失败: device_id={device_id}, "
                    f"type={notification.get('type')}, retry_count={record['retry_count']}"
                )
            else:
                logger.bind(tag=TAG).info(
                    f"通知重试成功: device_id={device_id}, "
                    f"type={notification.get('type')}, retry_count={retry_count + 1}"
                )
        
        logger.bind(tag=TAG).info(
            f"通知重试完成: 剩余失败={len(self._notification_history)}"
        )
    
    def get_failed_notification_count(self) -> int:
        """获取失败通知数量
        
        Returns:
            失败通知数量
        """
        return len(self._notification_history)
