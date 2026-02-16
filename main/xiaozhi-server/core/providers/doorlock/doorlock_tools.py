"""
智能门锁AI工具函数

提供AI可调用的工具函数，包括：
- 启用/关闭快递看护模式
- 更新看护基准图片
- 报告快递状态

每个工具函数都定义了完整的JSON Schema供VLLM调用
"""
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger

from .models import PackageAlert, VisitorIntent
from .package_guard_manager import PackageGuardManager
from .doorlock_database import DoorlockDatabase
from .notification_service import NotificationService

TAG = "DoorlockTools"


class DoorlockTools:
    """门锁AI工具函数类"""
    
    # 工具函数JSON Schema定义
    TOOLS_SCHEMA = [
        {
            "name": "enable_package_guard",
            "description": "启用快递看护模式。当访客提到'快递放门口了'、'外卖在这'等信息时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "设备ID"
                    },
                    "reason": {
                        "type": "string",
                        "description": "启用看护的原因，例如：'有新快递需要看护'"
                    }
                },
                "required": ["device_id", "reason"]
            }
        },
        {
            "name": "disable_package_guard",
            "description": "关闭快递看护模式。当判断快递已被主人（is_owner=true）取走时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "设备ID"
                    },
                    "reason": {
                        "type": "string",
                        "description": "关闭看护的原因，例如：'主人已取走快递'"
                    }
                },
                "required": ["device_id", "reason"]
            }
        },
        {
            "name": "update_package_baseline",
            "description": "更新看护基准图片。当发现门口有新快递送达时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "设备ID"
                    }
                },
                "required": ["device_id"]
            }
        },
        {
            "name": "report_package_status",
            "description": "报告快递状态和威胁等级。在看护模式下，每次拍照分析后调用此函数报告情况。",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "设备ID"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "会话ID"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["taking", "searching", "damaging", "normal", "passing"],
                        "description": "行为类型：taking(拿走)、searching(翻找)、damaging(破坏)、normal(正常)、passing(路过)"
                    },
                    "threat_level": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "威胁等级：low(低威胁)、medium(中威胁)、high(高威胁)"
                    },
                    "description": {
                        "type": "string",
                        "description": "详细描述你看到的情况，包括人物行为、快递状态等"
                    }
                },
                "required": ["device_id", "session_id", "action", "threat_level", "description"]
            }
        }
    ]
    
    def __init__(
        self,
        guard_manager: PackageGuardManager,
        db: DoorlockDatabase,
        notification_service: NotificationService
    ):
        """初始化工具函数类
        
        Args:
            guard_manager: 看护模式管理器
            db: 数据库服务
            notification_service: 通知服务
        """
        self.guard_manager = guard_manager
        self.db = db
        self.notification_service = notification_service
        
        logger.bind(tag=TAG).info("门锁工具函数初始化完成")
    
    @classmethod
    def get_tools_schema(cls) -> list:
        """获取所有工具函数的JSON Schema
        
        Returns:
            工具函数Schema列表
        """
        return cls.TOOLS_SCHEMA
    
    async def enable_package_guard(self, device_id: str, reason: str) -> Dict[str, Any]:
        """启用快递看护模式
        
        Args:
            device_id: 设备ID
            reason: 启用原因
            
        Returns:
            执行结果字典
        """
        try:
            # 参数验证
            if not device_id:
                logger.bind(tag=TAG).error("启用看护模式失败: device_id为空")
                return {
                    "success": False,
                    "message": "设备ID不能为空"
                }
            
            if not reason:
                reason = "AI判断需要启用看护"
            
            # 调用看护模式管理器
            success = await self.guard_manager.enable_guard(device_id, reason)
            
            if success:
                logger.bind(tag=TAG).info(
                    f"工具调用成功 - enable_package_guard: device_id={device_id}, reason={reason}"
                )
                return {
                    "success": True,
                    "message": f"看护模式已启用: {reason}"
                }
            else:
                logger.bind(tag=TAG).warning(
                    f"工具调用失败 - enable_package_guard: device_id={device_id}"
                )
                return {
                    "success": False,
                    "message": "看护模式启用失败，可能是看护功能未开启"
                }
                
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"工具调用异常 - enable_package_guard: device_id={device_id}, error={e}"
            )
            return {
                "success": False,
                "message": f"启用看护模式异常: {str(e)}"
            }
    
    async def disable_package_guard(self, device_id: str, reason: str) -> Dict[str, Any]:
        """关闭快递看护模式
        
        Args:
            device_id: 设备ID
            reason: 关闭原因
            
        Returns:
            执行结果字典
        """
        try:
            # 参数验证
            if not device_id:
                logger.bind(tag=TAG).error("关闭看护模式失败: device_id为空")
                return {
                    "success": False,
                    "message": "设备ID不能为空"
                }
            
            if not reason:
                reason = "AI判断可以关闭看护"
            
            # 调用看护模式管理器
            success = await self.guard_manager.disable_guard(device_id, reason)
            
            if success:
                logger.bind(tag=TAG).info(
                    f"工具调用成功 - disable_package_guard: device_id={device_id}, reason={reason}"
                )
                return {
                    "success": True,
                    "message": f"看护模式已关闭: {reason}"
                }
            else:
                logger.bind(tag=TAG).warning(
                    f"工具调用失败 - disable_package_guard: device_id={device_id}"
                )
                return {
                    "success": False,
                    "message": "看护模式关闭失败"
                }
                
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"工具调用异常 - disable_package_guard: device_id={device_id}, error={e}"
            )
            return {
                "success": False,
                "message": f"关闭看护模式异常: {str(e)}"
            }
    
    async def update_package_baseline(self, device_id: str) -> Dict[str, Any]:
        """更新看护基准图片
        
        Args:
            device_id: 设备ID
            
        Returns:
            执行结果字典
        """
        try:
            # 参数验证
            if not device_id:
                logger.bind(tag=TAG).error("更新基准图片失败: device_id为空")
                return {
                    "success": False,
                    "message": "设备ID不能为空"
                }
            
            # 调用看护模式管理器（需要拍照获取图片数据）
            # TODO: 集成拍照功能
            baseline_path = await self.guard_manager.update_baseline(device_id, image_data=None)
            
            if baseline_path:
                logger.bind(tag=TAG).info(
                    f"工具调用成功 - update_package_baseline: device_id={device_id}, path={baseline_path}"
                )
                return {
                    "success": True,
                    "message": f"基准图片已更新: {baseline_path}"
                }
            else:
                logger.bind(tag=TAG).warning(
                    f"工具调用失败 - update_package_baseline: device_id={device_id}"
                )
                return {
                    "success": False,
                    "message": "基准图片更新失败，需要提供图片数据"
                }
                
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"工具调用异常 - update_package_baseline: device_id={device_id}, error={e}"
            )
            return {
                "success": False,
                "message": f"更新基准图片异常: {str(e)}"
            }
    
    async def report_package_status(
        self,
        device_id: str,
        session_id: str,
        action: str,
        threat_level: str,
        description: str
    ) -> Dict[str, Any]:
        """报告快递状态
        
        Args:
            device_id: 设备ID
            session_id: 会话ID
            action: 行为类型
            threat_level: 威胁等级
            description: 详细描述
            
        Returns:
            执行结果字典
        """
        try:
            # 参数验证
            if not device_id or not session_id:
                logger.bind(tag=TAG).error("报告快递状态失败: device_id或session_id为空")
                return {
                    "success": False,
                    "message": "设备ID和会话ID不能为空"
                }
            
            # 验证action枚举值
            valid_actions = ["taking", "searching", "damaging", "normal", "passing"]
            if action not in valid_actions:
                logger.bind(tag=TAG).warning(
                    f"报告快递状态: action值无效 ({action})，使用默认值 'normal'"
                )
                action = "normal"
            
            # 验证threat_level枚举值
            valid_threat_levels = ["low", "medium", "high"]
            if threat_level not in valid_threat_levels:
                logger.bind(tag=TAG).warning(
                    f"报告快递状态: threat_level值无效 ({threat_level})，使用默认值 'low'"
                )
                threat_level = "low"
            
            # 创建警报记录
            alert = PackageAlert(
                device_id=device_id,
                session_id=session_id,
                threat_level=threat_level,
                action=action,
                description=description,
                photo_path="",  # TODO: 保存当前照片路径
                voice_warning_sent=False,
                notified=False
            )
            
            # 保存到数据库
            alert_id = await self.db.save_package_alert(alert)
            
            if alert_id > 0:
                # 根据威胁等级决定是否发送通知
                if threat_level in ["medium", "high"]:
                    voice_text = "请问有什么可以帮您？" if threat_level == "medium" else "您的行为已被记录，请立即停止"
                    
                    await self.notification_service.notify_package_alert(
                        alert_id=alert_id,
                        session_id=session_id,
                        threat_level=threat_level,
                        action=action,
                        description=description,
                        photo_path=alert.photo_path,
                        voice_warning_text=voice_text
                    )
                
                logger.bind(tag=TAG).info(
                    f"工具调用成功 - report_package_status: alert_id={alert_id}, "
                    f"device_id={device_id}, threat_level={threat_level}, action={action}"
                )
                return {
                    "success": True,
                    "message": f"快递状态已记录: {description}",
                    "alert_id": alert_id,
                    "threat_level": threat_level
                }
            else:
                logger.bind(tag=TAG).error(
                    f"工具调用失败 - report_package_status: 保存警报记录失败"
                )
                return {
                    "success": False,
                    "message": "保存快递状态失败"
                }
                
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"工具调用异常 - report_package_status: device_id={device_id}, "
                f"session_id={session_id}, error={e}"
            )
            return {
                "success": False,
                "message": f"报告快递状态异常: {str(e)}"
            }
    
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """工具调用路由
        
        根据工具名称分发到对应的函数
        
        Args:
            tool_name: 工具函数名称
            arguments: 工具函数参数
            
        Returns:
            工具执行结果
        """
        try:
            logger.bind(tag=TAG).info(f"工具调用: tool_name={tool_name}, arguments={arguments}")
            
            # 路由到对应的工具函数
            if tool_name == "enable_package_guard":
                return await self.enable_package_guard(
                    device_id=arguments.get("device_id", ""),
                    reason=arguments.get("reason", "")
                )
            
            elif tool_name == "disable_package_guard":
                return await self.disable_package_guard(
                    device_id=arguments.get("device_id", ""),
                    reason=arguments.get("reason", "")
                )
            
            elif tool_name == "update_package_baseline":
                return await self.update_package_baseline(
                    device_id=arguments.get("device_id", "")
                )
            
            elif tool_name == "report_package_status":
                return await self.report_package_status(
                    device_id=arguments.get("device_id", ""),
                    session_id=arguments.get("session_id", ""),
                    action=arguments.get("action", "normal"),
                    threat_level=arguments.get("threat_level", "low"),
                    description=arguments.get("description", "")
                )
            
            else:
                logger.bind(tag=TAG).error(f"未知的工具函数: {tool_name}")
                return {
                    "success": False,
                    "message": f"未知的工具函数: {tool_name}"
                }
                
        except Exception as e:
            logger.bind(tag=TAG).error(f"工具调用路由异常: tool_name={tool_name}, error={e}")
            return {
                "success": False,
                "message": f"工具调用异常: {str(e)}"
            }
