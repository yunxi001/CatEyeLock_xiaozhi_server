"""
照片缓存管理器

用于统一看护对话模式中的定时拍照缓存管理。
支持按session_id管理照片缓存，最多保留10张照片。
"""

import base64
from collections import deque
from datetime import datetime
from typing import Dict, Optional, Deque
from loguru import logger


class PhotoCacheManager:
    """照片缓存管理器（单例模式）
    
    功能：
    - 按session_id管理照片缓存
    - 每个session最多保留10张照片
    - 自动清理超过限制的旧照片
    - 支持获取最新照片
    - 支持清理指定session的所有缓存
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super(PhotoCacheManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化照片缓存管理器"""
        # 避免重复初始化
        if PhotoCacheManager._initialized:
            return
            
        # 照片缓存字典：{session_id: deque([{photo, timestamp}, ...])}
        self._cache: Dict[str, Deque[Dict]] = {}
        
        # 最大缓存数量
        self._max_cache_size = 10
        
        PhotoCacheManager._initialized = True
        logger.bind(tag="PhotoCache").info("照片缓存管理器初始化完成")
    
    def add_photo(self, session_id: str, photo_data: bytes) -> None:
        """添加照片到缓存
        
        Args:
            session_id: 会话ID
            photo_data: 照片数据（bytes格式）
        """
        try:
            # 如果session不存在，创建新的deque
            if session_id not in self._cache:
                self._cache[session_id] = deque(maxlen=self._max_cache_size)
            
            # 转换为Base64编码
            photo_base64 = base64.b64encode(photo_data).decode('utf-8')
            
            # 添加照片到缓存（带时间戳）
            photo_entry = {
                'photo': photo_base64,
                'timestamp': datetime.now()
            }
            
            self._cache[session_id].append(photo_entry)
            
            cache_size = len(self._cache[session_id])
            logger.bind(tag="PhotoCache").debug(
                f"添加照片到缓存 - 会话: {session_id}, "
                f"当前缓存数量: {cache_size}/{self._max_cache_size}, "
                f"照片大小: {len(photo_data)} bytes"
            )
            
        except Exception as e:
            logger.bind(tag="PhotoCache").error(
                f"添加照片到缓存失败 - 会话: {session_id}, 错误: {e}"
            )
            raise
    
    def get_latest_photo(self, session_id: str) -> Optional[str]:
        """获取最新的缓存照片
        
        Args:
            session_id: 会话ID
            
        Returns:
            Base64编码的照片，如果缓存为空则返回None
        """
        try:
            # 检查session是否存在
            if session_id not in self._cache:
                logger.bind(tag="PhotoCache").warning(
                    f"获取最新照片失败 - 会话不存在: {session_id}"
                )
                return None
            
            # 检查缓存是否为空
            if not self._cache[session_id]:
                logger.bind(tag="PhotoCache").warning(
                    f"获取最新照片失败 - 缓存为空: {session_id}"
                )
                return None
            
            # 获取最新照片（deque最右边的元素）
            latest_entry = self._cache[session_id][-1]
            photo_base64 = latest_entry['photo']
            timestamp = latest_entry['timestamp']
            
            logger.bind(tag="PhotoCache").debug(
                f"获取最新照片 - 会话: {session_id}, "
                f"时间戳: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            return photo_base64
            
        except Exception as e:
            logger.bind(tag="PhotoCache").error(
                f"获取最新照片异常 - 会话: {session_id}, 错误: {e}"
            )
            return None
    
    def clear_cache(self, session_id: str) -> None:
        """清理指定session_id的所有缓存照片
        
        Args:
            session_id: 会话ID
        """
        try:
            if session_id in self._cache:
                cache_size = len(self._cache[session_id])
                del self._cache[session_id]
                
                logger.bind(tag="PhotoCache").info(
                    f"清理照片缓存 - 会话: {session_id}, 清理数量: {cache_size}"
                )
            else:
                logger.bind(tag="PhotoCache").debug(
                    f"清理照片缓存 - 会话不存在: {session_id}"
                )
                
        except Exception as e:
            logger.bind(tag="PhotoCache").error(
                f"清理照片缓存失败 - 会话: {session_id}, 错误: {e}"
            )
            raise
    
    def get_cache_size(self, session_id: str) -> int:
        """获取指定session的缓存数量
        
        Args:
            session_id: 会话ID
            
        Returns:
            缓存照片数量
        """
        if session_id not in self._cache:
            return 0
        return len(self._cache[session_id])
    
    def get_all_sessions(self) -> list:
        """获取所有活跃的session列表
        
        Returns:
            session_id列表
        """
        return list(self._cache.keys())
