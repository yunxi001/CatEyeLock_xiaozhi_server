from enum import Enum


class TextMessageType(Enum):
    """消息类型枚举"""
    HELLO = "hello"
    ABORT = "abort"
    LISTEN = "listen"
    IOT = "iot"
    MCP = "mcp"
    SERVER = "server"
    SYSTEM = "system"
    FACE_RECOGNITION = "face_recognition"
    FACE_MANAGEMENT = "face_management"
    
    # ESP32 智能门锁上报类型
    STATUS_REPORT = "status_report"        # 传感器状态上报
    EVENT_REPORT = "event_report"          # 关键事件上报
    LOG_REPORT = "log_report"              # 开锁日志上报
    ACK = "ack"                            # ACK 响应（ESP32）
    USER_MGMT_RESULT = "user_mgmt_result"  # 用户管理结果
    HEARTBEAT = "heartbeat"                # 心跳请求（预留）
    
    # v5.2 协议新增消息类型
    ESP32_ACK = "esp32_ack"                # ESP32 第一级确认（命令已收到）
    DOOR_OPENED_REPORT = "door_opened_report"  # 开门日志上报
    PASSWORD_REPORT = "password_report"    # 密码查询结果上报
    
    # App 协议 v2.2 新增 - 数据查询与媒体下载
    QUERY = "query"                        # 数据查询
    MEDIA_DOWNLOAD = "media_download"      # 媒体文件下载
    MEDIA_DOWNLOAD_CHUNK = "media_download_chunk"  # 大文件分片下载
    
    # App 协议 v2.2 新增 - 命令代理（App 发送，转发给 ESP32）
    LOCK_CONTROL = "lock_control"          # 锁控命令
    DEV_CONTROL = "dev_control"            # 设备控制命令
    USER_MGMT = "user_mgmt"                # 用户管理命令
    
    # 本地预览功能（v5.2 协议扩展）
    LOCAL_PREVIEW = "local_preview"        # 本地预览控制响应
