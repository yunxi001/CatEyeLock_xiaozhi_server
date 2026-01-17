"""
seq_id 防重放缓存

用于 App 协议 v2.2 的消息确认机制，防止 TCP 重传导致消息重复执行
"""
from collections import OrderedDict
from typing import Dict


class SeqIdCache:
    """按 app_id 分组的 seq_id 缓存，用于防重放
    
    采用 FIFO 淘汰策略，每个 app_id 最多缓存 max_size 条 seq_id
    """
    
    def __init__(self, max_size: int = 100):
        """初始化缓存
        
        Args:
            max_size: 每个 app_id 的最大缓存条数
        """
        self.max_size = max_size
        self._cache: Dict[str, OrderedDict] = {}
    
    def check_and_add(self, app_id: str, seq_id: str) -> bool:
        """检查 seq_id 是否重复，如果不重复则添加到缓存
        
        Args:
            app_id: App 用户标识
            seq_id: 消息序列号
            
        Returns:
            True 如果是新消息（未重复），False 如果是重复消息
        """
        if not app_id or not seq_id:
            return True  # 没有 seq_id 的消息不做防重放检查
        
        if app_id not in self._cache:
            self._cache[app_id] = OrderedDict()
        
        cache = self._cache[app_id]
        
        if seq_id in cache:
            return False  # 重复消息
        
        # 添加新 seq_id
        cache[seq_id] = True
        
        # FIFO 淘汰
        while len(cache) > self.max_size:
            cache.popitem(last=False)
        
        return True
    
    def clear(self, app_id: str = None):
        """清除缓存
        
        Args:
            app_id: 指定 app_id 则只清除该用户的缓存，否则清除所有
        """
        if app_id:
            if app_id in self._cache:
                del self._cache[app_id]
        else:
            self._cache.clear()
    
    def get_cache_size(self, app_id: str = None) -> int:
        """获取缓存大小
        
        Args:
            app_id: 指定 app_id 则返回该用户的缓存大小，否则返回总大小
            
        Returns:
            缓存条数
        """
        if app_id:
            return len(self._cache.get(app_id, {}))
        return sum(len(cache) for cache in self._cache.values())
