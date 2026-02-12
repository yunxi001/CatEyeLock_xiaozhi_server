"""
智能门锁AI会话管理器

管理访客对话会话的生命周期，包括：
- 会话创建和销毁
- 对话历史管理
- 会话状态更新
- 对话结束判定
"""
import asyncio
import time
from datetime import datetime
from typing import Optional, Dict, Any
from threading import Lock
from loguru import logger

from .models import DoorlockSession

TAG = "SessionManager"


class SessionManager:
    """门锁AI会话管理器（线程安全）"""
    
    def __init__(self, dialogue_timeout: int = 30, max_dialogue_rounds: int = 10):
        """初始化会话管理器
        
        Args:
            dialogue_timeout: 对话超时时间（秒），默认30秒
            max_dialogue_rounds: 最大对话轮次，默认10轮
        """
        self.dialogue_timeout = dialogue_timeout
        self.max_dialogue_rounds = max_dialogue_rounds
        
        # 会话存储（内存字典）
        self._sessions: Dict[str, DoorlockSession] = {}
        
        # 并发访问锁
        self._lock = Lock()
        
        logger.bind(tag=TAG).info(
            f"会话管理器初始化完成: timeout={dialogue_timeout}s, max_rounds={max_dialogue_rounds}"
        )
    
    def create_session(self, device_id: str) -> DoorlockSession:
        """创建新会话
        
        Args:
            device_id: 设备ID
            
        Returns:
            新创建的会话对象
        """
        with self._lock:
            # 生成会话ID（格式：device_id_timestamp）
            timestamp = int(time.time() * 1000)
            session_id = f"{device_id}_{timestamp}"
            
            # 创建会话对象
            session = DoorlockSession(
                session_id=session_id,
                device_id=device_id,
                dialogue_history=[],
                photo_records=[],
                last_activity=datetime.now(),
                created_at=datetime.now()
            )
            
            # 存储会话
            self._sessions[session_id] = session
            
            logger.bind(tag=TAG).info(f"创建会话成功: session_id={session_id}, device_id={device_id}")
            return session
    
    def get_session(self, session_id: str) -> Optional[DoorlockSession]:
        """获取会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话对象，如果不存在返回None
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                logger.bind(tag=TAG).debug(f"获取会话成功: session_id={session_id}")
            else:
                logger.bind(tag=TAG).warning(f"会话不存在: session_id={session_id}")
            return session
    
    def update_session(self, session_id: str, **kwargs) -> bool:
        """更新会话状态
        
        Args:
            session_id: 会话ID
            **kwargs: 要更新的字段（dialogue_history, photo_records, last_activity等）
            
        Returns:
            是否更新成功
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                logger.bind(tag=TAG).warning(f"更新会话失败，会话不存在: session_id={session_id}")
                return False
            
            # 更新字段
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)
                else:
                    logger.bind(tag=TAG).warning(f"会话字段不存在: {key}")
            
            # 自动更新最后活动时间
            if 'last_activity' not in kwargs:
                session.last_activity = datetime.now()
            
            logger.bind(tag=TAG).debug(f"更新会话成功: session_id={session_id}, fields={list(kwargs.keys())}")
            return True
    
    def add_dialogue(self, session_id: str, role: str, content: str) -> bool:
        """添加对话记录到会话
        
        Args:
            session_id: 会话ID
            role: 角色（user/assistant）
            content: 对话内容
            
        Returns:
            是否添加成功
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                logger.bind(tag=TAG).warning(f"添加对话失败，会话不存在: session_id={session_id}")
                return False
            
            # 添加对话记录
            session.dialogue_history.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
            
            # 保留最近10轮对话（20条消息）
            if len(session.dialogue_history) > self.max_dialogue_rounds * 2:
                removed_count = len(session.dialogue_history) - self.max_dialogue_rounds * 2
                session.dialogue_history = session.dialogue_history[removed_count:]
                logger.bind(tag=TAG).debug(
                    f"对话历史超过限制，清理了 {removed_count} 条旧记录: session_id={session_id}"
                )
            
            # 更新最后活动时间
            session.last_activity = datetime.now()
            
            logger.bind(tag=TAG).debug(
                f"添加对话记录成功: session_id={session_id}, role={role}, "
                f"history_count={len(session.dialogue_history)}"
            )
            return True
    
    def add_photo_record(self, session_id: str, photo_path: str, photo_type: str = "monitoring") -> bool:
        """添加照片记录到会话
        
        Args:
            session_id: 会话ID
            photo_path: 照片路径
            photo_type: 照片类型（monitoring/baseline/alert）
            
        Returns:
            是否添加成功
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                logger.bind(tag=TAG).warning(f"添加照片记录失败，会话不存在: session_id={session_id}")
                return False
            
            # 添加照片记录
            session.photo_records.append({
                "path": photo_path,
                "type": photo_type,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.bind(tag=TAG).debug(
                f"添加照片记录成功: session_id={session_id}, type={photo_type}, "
                f"photo_count={len(session.photo_records)}"
            )
            return True
    
    async def cleanup_session(self, session_id: str):
        """清除会话
        
        Args:
            session_id: 会话ID
        """
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                del self._sessions[session_id]
                logger.bind(tag=TAG).info(
                    f"清除会话成功: session_id={session_id}, device_id={session.device_id}, "
                    f"dialogue_count={len(session.dialogue_history)}, "
                    f"photo_count={len(session.photo_records)}"
                )
            else:
                logger.bind(tag=TAG).warning(f"清除会话失败，会话不存在: session_id={session_id}")
    
    async def check_dialogue_end(self, session_id: str, pir_detected: bool = True) -> bool:
        """检查对话是否结束
        
        对话结束条件：
        1. 访客沉默超过30秒（从最后活动时间计算）
        2. PIR检测不到人体
        
        Args:
            session_id: 会话ID
            pir_detected: PIR是否检测到人体
            
        Returns:
            是否应该结束对话
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                logger.bind(tag=TAG).warning(f"检查对话结束失败，会话不存在: session_id={session_id}")
                return True  # 会话不存在，认为已结束
            
            # 条件1：PIR检测不到人体
            if not pir_detected:
                logger.bind(tag=TAG).info(f"对话结束（PIR无人体）: session_id={session_id}")
                return True
            
            # 条件2：访客沉默超过30秒
            silence_duration = (datetime.now() - session.last_activity).total_seconds()
            if silence_duration > self.dialogue_timeout:
                logger.bind(tag=TAG).info(
                    f"对话结束（沉默超时）: session_id={session_id}, "
                    f"silence_duration={silence_duration:.1f}s"
                )
                return True
            
            logger.bind(tag=TAG).debug(
                f"对话继续中: session_id={session_id}, silence_duration={silence_duration:.1f}s"
            )
            return False
    
    def get_dialogue_history(self, session_id: str) -> list:
        """获取对话历史
        
        Args:
            session_id: 会话ID
            
        Returns:
            对话历史列表
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                logger.bind(tag=TAG).warning(f"获取对话历史失败，会话不存在: session_id={session_id}")
                return []
            
            return session.dialogue_history.copy()
    
    def get_photo_records(self, session_id: str) -> list:
        """获取照片记录
        
        Args:
            session_id: 会话ID
            
        Returns:
            照片记录列表
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                logger.bind(tag=TAG).warning(f"获取照片记录失败，会话不存在: session_id={session_id}")
                return []
            
            return session.photo_records.copy()
    
    def get_session_count(self) -> int:
        """获取当前会话数量
        
        Returns:
            会话数量
        """
        with self._lock:
            return len(self._sessions)
    
    def get_all_session_ids(self) -> list:
        """获取所有会话ID
        
        Returns:
            会话ID列表
        """
        with self._lock:
            return list(self._sessions.keys())
    
    async def cleanup_expired_sessions(self, max_age_seconds: int = 3600):
        """清理过期会话
        
        Args:
            max_age_seconds: 会话最大存活时间（秒），默认1小时
        """
        with self._lock:
            now = datetime.now()
            expired_sessions = []
            
            for session_id, session in self._sessions.items():
                age = (now - session.created_at).total_seconds()
                if age > max_age_seconds:
                    expired_sessions.append(session_id)
            
            # 删除过期会话
            for session_id in expired_sessions:
                del self._sessions[session_id]
            
            if expired_sessions:
                logger.bind(tag=TAG).info(
                    f"清理过期会话: count={len(expired_sessions)}, "
                    f"max_age={max_age_seconds}s"
                )
