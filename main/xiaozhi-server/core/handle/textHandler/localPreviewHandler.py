"""
本地预览响应处理器

处理 ESP32 返回的 local_preview 响应消息。
当 ESP32 执行本地预览命令后，会返回执行结果，此处理器负责接收并缓存响应。

消息格式：
{
    "type": "local_preview",
    "action": "start" | "stop",
    "status": "success" | "error",
    "error": "错误信息"  // 仅在 status="error" 时存在
}

作者：毕业设计项目组
创建日期：2026-05-04
"""

from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class LocalPreviewHandler(TextMessageHandler):
    """本地预览响应处理器"""
    
    @property
    def message_type(self) -> TextMessageType:
        """返回处理的消息类型"""
        return TextMessageType.LOCAL_PREVIEW
    
    async def handle(self, conn, msg_json: dict):
        """
        处理 local_preview 响应消息
        
        Args:
            conn: 连接对象
            msg_json: 解析后的 JSON 消息
        """
        try:
            action = msg_json.get("action")
            status = msg_json.get("status")
            error = msg_json.get("error")
            
            logger.bind(tag=TAG).info(
                f"收到 ESP32 的 local_preview 响应: "
                f"device_id={conn.device_id}, action={action}, status={status}, error={error}"
            )
            
            # 将响应存储到连接对象的缓存中
            # 插件函数会轮询此缓存来获取响应
            conn._local_preview_response = msg_json
            
            logger.bind(tag=TAG).debug(
                f"local_preview 响应已缓存: device_id={conn.device_id}"
            )
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"处理 local_preview 响应失败: device_id={conn.device_id}, error={e}"
            )
            import traceback
            logger.bind(tag=TAG).error(traceback.format_exc())
