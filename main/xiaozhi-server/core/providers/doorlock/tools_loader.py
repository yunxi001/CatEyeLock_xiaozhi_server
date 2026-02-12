"""
门锁工具函数加载器

负责：
- 动态加载门锁工具函数
- 初始化工具函数依赖
- 提供工具函数注册接口
"""
from typing import Optional
from loguru import logger

from .doorlock_tools import DoorlockTools
from .package_guard_manager import PackageGuardManager
from .doorlock_database import DoorlockDatabase
from .notification_service import NotificationService

TAG = "ToolsLoader"


class DoorlockToolsLoader:
    """门锁工具函数加载器"""
    
    @staticmethod
    def load_tools(
        db: DoorlockDatabase,
        guard_manager: PackageGuardManager,
        notification_service: NotificationService
    ) -> Optional[DoorlockTools]:
        """加载门锁工具函数
        
        Args:
            db: 数据库服务
            guard_manager: 看护模式管理器
            notification_service: 通知服务
            
        Returns:
            工具函数实例，失败返回None
        """
        try:
            # 创建工具函数实例
            tools = DoorlockTools(
                guard_manager=guard_manager,
                db=db,
                notification_service=notification_service
            )
            
            logger.bind(tag=TAG).info("门锁工具函数加载成功")
            return tools
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"门锁工具函数加载失败: {e}")
            return None
    
    @staticmethod
    def get_tools_schema() -> list:
        """获取工具函数Schema
        
        Returns:
            工具函数Schema列表
        """
        return DoorlockTools.get_tools_schema()
