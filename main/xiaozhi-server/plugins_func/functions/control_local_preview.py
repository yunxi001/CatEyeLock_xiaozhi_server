"""
本地预览功能控制插件

通过语音命令控制 ESP32 的本地预览功能（Local Preview Mode）。
本地预览功能允许用户在 ESP32 的 LCD 屏幕上实时查看摄像头画面，视频数据不发送到服务器。

功能特点：
- 支持语音命令启动/停止本地预览
- 自动识别多种触发词变体
- 提供友好的语音反馈
- 完整的错误处理

作者：毕业设计项目组
创建日期：2026-05-04
"""

import json
import asyncio
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Function Schema 定义（供 LLM 意图识别使用）
CONTROL_LOCAL_PREVIEW_DESC = {
    "type": "function",
    "function": {
        "name": "control_local_preview",
        "description": (
            "控制本地预览功能的开启或关闭。本地预览功能允许在 ESP32 的 LCD 屏幕上实时查看摄像头画面。"
            "当用户想要在设备屏幕上实时显示摄像头画面时调用此函数。"
            "启动本地预览的触发词：'显示监控画面'、'打开监控画面'、'打开监控模式'、'让我看看门口'、'打开本地预览'、'屏幕显示摄像头'、'打开屏幕'、'显示摄像头'、'开启实时预览'、'屏幕显示画面'；"
            "停止本地预览的触发词：'关闭监控画面'、'隐藏监控画面'、'关闭监控模式'、'关闭本地预览'、'关闭屏幕显示'、'关闭屏幕'、'隐藏摄像头'、'停止实时预览'。"
            "注意：这是在设备屏幕上显示实时画面，不是拍照或录像。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "stop"],
                    "description": "操作类型：start 表示启动本地预览，stop 表示停止本地预览"
                }
            },
            "required": ["action"]
        }
    }
}

# 错误码映射表
ERROR_MESSAGES = {
    "Camera not available": "摄像头暂时不可用",
    "Monitor mode active": "监控模式正在运行，无法启动本地预览",
    "Face recognition active": "人脸识别正在进行，请稍后再试",
    "System error": "系统错误，请稍后再试",
    "timeout": "操作超时，请稍后再试",
    "unknown": "未知错误，请稍后再试"
}

# 成功反馈消息
SUCCESS_MESSAGES = {
    "start": "已打开本地预览",
    "stop": "已关闭本地预览"
}


@register_function("control_local_preview", CONTROL_LOCAL_PREVIEW_DESC, ToolType.SYSTEM_CTL)
async def control_local_preview(conn, action: str):
    """
    控制本地预览功能
    
    Args:
        conn: 连接对象（包含 websocket、device_id 等信息）
        action: 操作类型，"start" 或 "stop"
        
    Returns:
        ActionResponse: 包含操作结果和语音反馈文本
    """
    try:
        logger.bind(tag=TAG).info(
            f"本地预览控制插件被调用: action={action}, device_id={conn.device_id}"
        )
        
        # 参数验证
        if action not in ["start", "stop"]:
            error_msg = f"无效的操作类型: {action}"
            logger.bind(tag=TAG).error(error_msg)
            return ActionResponse(
                action=Action.RESPONSE,
                result="参数错误",
                response="操作失败，参数错误"
            )
        
        # 检查 WebSocket 连接
        if not conn.websocket:
            error_msg = "WebSocket 连接不可用"
            logger.bind(tag=TAG).error(error_msg)
            return ActionResponse(
                action=Action.RESPONSE,
                result="连接错误",
                response="设备连接已断开，无法执行操作"
            )
        
        # 构建 WebSocket 命令
        command = {
            "type": "local_preview",
            "action": action
        }
        
        logger.bind(tag=TAG).debug(f"发送本地预览命令到 ESP32: {command}")
        
        # 发送命令到 ESP32
        await conn.websocket.send(json.dumps(command))
        
        # 等待 ESP32 响应（超时时间：10 秒）
        try:
            response = await _wait_for_response(conn, timeout=10.0)
            
            if response is None:
                # 超时
                logger.bind(tag=TAG).warning(
                    f"等待 ESP32 响应超时: device_id={conn.device_id}, action={action}"
                )
                return ActionResponse(
                    action=Action.RESPONSE,
                    result="超时",
                    response=ERROR_MESSAGES["timeout"]
                )
            
            # 解析响应
            result_text, success = _parse_response(response, action)
            
            if success:
                logger.bind(tag=TAG).info(
                    f"本地预览控制成功: action={action}, device_id={conn.device_id}"
                )
            else:
                logger.bind(tag=TAG).warning(
                    f"本地预览控制失败: action={action}, device_id={conn.device_id}, error={response.get('error')}"
                )
            
            return ActionResponse(
                action=Action.RESPONSE,
                result="成功" if success else "失败",
                response=result_text
            )
            
        except asyncio.TimeoutError:
            logger.bind(tag=TAG).warning(
                f"等待 ESP32 响应超时: device_id={conn.device_id}, action={action}"
            )
            return ActionResponse(
                action=Action.RESPONSE,
                result="超时",
                response=ERROR_MESSAGES["timeout"]
            )
        
    except Exception as e:
        logger.bind(tag=TAG).error(
            f"本地预览控制异常: action={action}, device_id={conn.device_id}, error={e}"
        )
        import traceback
        logger.bind(tag=TAG).error(traceback.format_exc())
        
        return ActionResponse(
            action=Action.RESPONSE,
            result="异常",
            response=ERROR_MESSAGES["unknown"]
        )


async def _wait_for_response(conn, timeout: float = 10.0):
    """
    等待 ESP32 的响应消息
    
    实现方式：轮询检查连接对象的响应缓存
    
    Args:
        conn: 连接对象
        timeout: 超时时间（秒）
        
    Returns:
        dict: ESP32 的响应消息，超时返回 None
    """
    start_time = asyncio.get_event_loop().time()
    
    # 初始化响应缓存（如果不存在）
    if not hasattr(conn, '_local_preview_response'):
        conn._local_preview_response = None
    
    # 轮询等待响应
    while True:
        # 检查是否有响应
        if conn._local_preview_response is not None:
            response = conn._local_preview_response
            conn._local_preview_response = None  # 清除缓存
            return response
        
        # 检查超时
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= timeout:
            return None
        
        # 短暂休眠，避免 CPU 占用过高
        await asyncio.sleep(0.1)


def _parse_response(response: dict, action: str) -> tuple:
    """
    解析 ESP32 的响应消息
    
    Args:
        response: ESP32 的响应消息
        action: 操作类型（start/stop）
        
    Returns:
        tuple: (反馈文本, 是否成功)
    """
    try:
        status = response.get("status")
        
        if status == "success":
            # 成功
            feedback_text = SUCCESS_MESSAGES.get(action, "操作成功")
            return feedback_text, True
        
        elif status == "error":
            # 失败
            error_code = response.get("error", "unknown")
            feedback_text = ERROR_MESSAGES.get(error_code, ERROR_MESSAGES["unknown"])
            return feedback_text, False
        
        else:
            # 未知状态
            logger.bind(tag=TAG).warning(f"未知的响应状态: {status}")
            return ERROR_MESSAGES["unknown"], False
            
    except Exception as e:
        logger.bind(tag=TAG).error(f"解析响应失败: {e}")
        return ERROR_MESSAGES["unknown"], False


# 响应处理辅助函数（需要在消息路由中调用）
def handle_local_preview_response(conn, msg_json: dict):
    """
    处理 ESP32 返回的 local_preview 响应
    
    此函数应该在 textMessageHandler 中被调用，用于接收 ESP32 的响应。
    
    Args:
        conn: 连接对象
        msg_json: 解析后的 JSON 消息
    """
    try:
        if msg_json.get("type") == "local_preview":
            logger.bind(tag=TAG).debug(f"收到 ESP32 的 local_preview 响应: {msg_json}")
            
            # 将响应存储到连接对象的缓存中
            conn._local_preview_response = msg_json
            
    except Exception as e:
        logger.bind(tag=TAG).error(f"处理 local_preview 响应失败: {e}")
