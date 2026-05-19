"""
PIR传感器状态管理工具函数

用于访客管理和包裹看守优化，提供PIR状态检查和更新功能。
"""
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler


def is_pir_timeout(conn: "ConnectionHandler", timeout: float = 2.0) -> bool:
    """判断PIR是否已超时（人体是否已离开）
    
    Args:
        conn: 连接对象
        timeout: 超时阈值（秒），默认2.0秒
        
    Returns:
        True: PIR已超时，人体已离开
        False: PIR正常，人体仍在
        
    说明:
        ESP32 PIR传感器每秒上报一次，如果超过timeout秒未收到新上报，
        则认为人体已离开。使用服务器系统时间作为统一基准。
    """
    if not hasattr(conn, 'pir_detected') or not conn.pir_detected:
        return True
    
    if not hasattr(conn, 'last_pir_time') or conn.last_pir_time == 0:
        return True
    
    # 计算距离上次PIR上报的时间（秒）
    # 注意：last_pir_time 使用服务器系统时间（秒），不是 ESP32 设备时间
    current_time = time.time()
    elapsed_sec = current_time - conn.last_pir_time
    
    return elapsed_sec > timeout


def update_pir_state(conn: "ConnectionHandler", param: int, ts: int = None) -> None:
    """更新PIR状态
    
    Args:
        conn: 连接对象
        param: PIR持续时间参数（秒）
        ts: ESP32设备时间戳（毫秒），仅作记录，不用于超时判断
        
    说明:
        每次收到PIR事件上报时调用此函数更新状态。
        使用服务器系统时间记录上报时刻，确保与 is_pir_timeout 时间基准一致。
    """
    conn.pir_detected = True
    conn.last_pir_time = time.time()  # 使用服务器系统时间（秒）
    conn.pir_duration = param


def check_pir_status(conn: "ConnectionHandler", timeout: float = 2.0) -> bool:
    """检查PIR状态（is_pir_timeout的反向版本）
    
    Args:
        conn: 连接对象
        timeout: 超时阈值（秒），默认2.0秒
        
    Returns:
        True: PIR正常，人体仍在
        False: PIR超时，人体已离开
    """
    return not is_pir_timeout(conn, timeout)
