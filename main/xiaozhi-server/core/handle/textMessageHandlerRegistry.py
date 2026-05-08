from typing import Dict, Optional

from core.handle.textHandler.abortMessageHandler import AbortTextMessageHandler
from core.handle.textHandler.helloMessageHandler import HelloTextMessageHandler
from core.handle.textHandler.iotMessageHandler import IotTextMessageHandler
from core.handle.textHandler.listenMessageHandler import ListenTextMessageHandler
from core.handle.textHandler.mcpMessageHandler import McpTextMessageHandler
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textHandler.serverMessageHandler import ServerTextMessageHandler
from core.handle.textHandler.systemMessageHandler import SystemTextMessageHandler
from core.handle.textHandler.faceRecognitionHandler import FaceRecognitionHandler
# 智能门锁协议 v5.0 新增处理器
from core.handle.textHandler.statusReportHandler import StatusReportHandler
from core.handle.textHandler.eventReportHandler import EventReportHandler
from core.handle.textHandler.logReportHandler import LogReportHandler
from core.handle.textHandler.ackHandler import AckHandler
from core.handle.textHandler.userMgmtResultHandler import UserMgmtResultHandler
# 智能门锁协议 v5.2 新增处理器
from core.handle.textHandler.doorOpenedReportHandler import DoorOpenedReportHandler
from core.handle.textHandler.passwordReportHandler import PasswordReportHandler
# App 协议 v6.0 命令代理处理器
from core.handle.textHandler.commandProxyHandler import (
    LockControlProxyHandler,
    DevControlProxyHandler,
    UserMgmtProxyHandler
)
# 本地预览功能处理器
from core.handle.textHandler.localPreviewHandler import LocalPreviewHandler

TAG = __name__


class TextMessageHandlerRegistry:
    """消息处理器注册表"""

    def __init__(self):
        self._handlers: Dict[str, TextMessageHandler] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """注册默认的消息处理器"""
        handlers = [
            HelloTextMessageHandler(),
            AbortTextMessageHandler(),
            ListenTextMessageHandler(),
            IotTextMessageHandler(),
            McpTextMessageHandler(),
            ServerTextMessageHandler(),
            SystemTextMessageHandler(),
            FaceRecognitionHandler(),
            # 智能门锁协议 v5.0 新增
            StatusReportHandler(),
            EventReportHandler(),
            LogReportHandler(),
            AckHandler(),
            UserMgmtResultHandler(),
            # 智能门锁协议 v5.2 新增
            DoorOpenedReportHandler(),
            PasswordReportHandler(),
            # App 协议 v6.0 命令代理
            LockControlProxyHandler(),
            DevControlProxyHandler(),
            UserMgmtProxyHandler(),
            # 本地预览功能
            LocalPreviewHandler(),
        ]

        for handler in handlers:
            self.register_handler(handler)

    def register_handler(self, handler: TextMessageHandler) -> None:
        """注册消息处理器"""
        self._handlers[handler.message_type.value] = handler

    def get_handler(self, message_type: str) -> Optional[TextMessageHandler]:
        """获取消息处理器"""
        return self._handlers.get(message_type)

    def get_supported_types(self) -> list:
        """获取支持的消息类型"""
        return list(self._handlers.keys())
