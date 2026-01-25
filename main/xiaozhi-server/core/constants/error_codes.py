"""统一错误码定义（v5.2）

注意：ESP32 端已经将 STM32 的十六进制错误码映射为统一错误码
服务器端接收到的 code 字段已经是 0-10 的十进制错误码
服务器端不需要进行错误码映射，只需定义常量方便使用
"""


class ErrorCode:
    """统一错误码常量定义（0-10）"""
    
    SUCCESS = 0              # 成功
    DEVICE_OFFLINE = 1       # 设备离线
    DEVICE_BUSY = 2          # 设备忙碌
    PARAM_ERROR = 3          # 参数错误
    NOT_SUPPORTED = 4        # 不支持
    TIMEOUT = 5              # 超时
    HARDWARE_FAULT = 6       # 硬件故障
    RESOURCE_FULL = 7        # 资源已满
    UNAUTHORIZED = 8         # 未认证
    DUPLICATE_MESSAGE = 9    # 重复消息
    INTERNAL_ERROR = 10      # 内部错误


ERROR_MESSAGES = {
    ErrorCode.SUCCESS: "成功",
    ErrorCode.DEVICE_OFFLINE: "设备离线",
    ErrorCode.DEVICE_BUSY: "设备忙碌",
    ErrorCode.PARAM_ERROR: "参数错误",
    ErrorCode.NOT_SUPPORTED: "不支持",
    ErrorCode.TIMEOUT: "超时",
    ErrorCode.HARDWARE_FAULT: "硬件故障",
    ErrorCode.RESOURCE_FULL: "资源已满",
    ErrorCode.UNAUTHORIZED: "未认证",
    ErrorCode.DUPLICATE_MESSAGE: "重复消息",
    ErrorCode.INTERNAL_ERROR: "内部错误",
}


def is_valid_error_code(code: int) -> bool:
    """验证错误码是否在有效范围内
    
    Args:
        code: 错误码
        
    Returns:
        bool: 如果错误码在 0-10 范围内返回 True，否则返回 False
    """
    return 0 <= code <= 10


def get_error_message(code: int) -> str:
    """获取错误码对应的错误消息
    
    Args:
        code: 错误码
        
    Returns:
        str: 错误消息，如果错误码不存在则返回"未知错误"
    """
    return ERROR_MESSAGES.get(code, "未知错误")
