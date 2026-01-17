"""
全局连接管理器，用于管理 ESP32 和 App 的 WebSocket 连接
"""
import json
import time
import asyncio
from typing import Dict, List, Optional
from config.logger import setup_logging

TAG = __name__


class ConnectionManager:
    """全局连接管理器，单例模式"""
    
    _instance = None
    
    def __init__(self):
        if ConnectionManager._instance is not None:
            raise Exception("ConnectionManager 是单例类，请使用 get_instance() 方法")
        
        self.esp32_connections: Dict[str, 'ConnectionHandler'] = {}
        self.app_connections: Dict[str, List['AppConnectionHandler']] = {}
        self.logger = setup_logging()
        
        ConnectionManager._instance = self
    
    @classmethod
    def get_instance(cls) -> 'ConnectionManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = ConnectionManager()
        return cls._instance
    
    async def notify_apps_device_status(self, device_id: str, status: str, reason: str = None):
        """通知所有关联的 App 设备状态变化
        
        Args:
            device_id: 设备 ID
            status: "online" 或 "offline"
            reason: 下线原因（仅 offline 时有效）
        """
        app_conns = self.get_app_conns(device_id)
        if not app_conns:
            return
        
        notification = {
            "type": "device_status",
            "status": status,
            "device_id": device_id,
            "ts": int(time.time() * 1000)
        }
        
        if status == "offline" and reason:
            notification["reason"] = reason
        
        msg = json.dumps(notification)
        
        for app_conn in app_conns:
            try:
                if app_conn.websocket:
                    await app_conn.websocket.send(msg)
                    self.logger.bind(tag=TAG).debug(f"已通知 App 设备{status}: {device_id}")
            except Exception as e:
                self.logger.bind(tag=TAG).warning(f"通知 App 设备状态失败: {e}")
    
    def register_esp32(self, device_id: str, conn) -> None:
        """注册 ESP32 连接
        
        Args:
            device_id: 设备唯一标识符
            conn: ConnectionHandler 实例
        """
        self.esp32_connections[device_id] = conn
        self.logger.bind(tag=TAG).info(f"ESP32 连接已注册: {device_id}")
        
        # 通知关联的 App 设备上线
        asyncio.create_task(self.notify_apps_device_status(device_id, "online"))
    
    def register_app(self, device_id: str, conn) -> None:
        """注册 App 连接
        
        Args:
            device_id: 设备唯一标识符
            conn: AppConnectionHandler 实例
        """
        if device_id not in self.app_connections:
            self.app_connections[device_id] = []
        self.app_connections[device_id].append(conn)
        self.logger.bind(tag=TAG).info(
            f"App 连接已注册: {device_id}, 当前连接数: {len(self.app_connections[device_id])}"
        )
    
    def unregister_esp32(self, device_id: str, reason: str = "connection_lost") -> None:
        """注销 ESP32 连接
        
        Args:
            device_id: 设备唯一标识符
            reason: 断开原因（connection_lost/device_disconnect/server_kick/timeout）
        """
        if device_id in self.esp32_connections:
            del self.esp32_connections[device_id]
            self.logger.bind(tag=TAG).info(f"ESP32 连接已注销: {device_id}, 原因: {reason}")
            
            # 通知关联的 App 设备下线
            asyncio.create_task(self.notify_apps_device_status(device_id, "offline", reason))
    
    def unregister_app(self, device_id: str, conn) -> None:
        """注销 App 连接
        
        Args:
            device_id: 设备唯一标识符
            conn: AppConnectionHandler 实例
        """
        if device_id in self.app_connections:
            if conn in self.app_connections[device_id]:
                self.app_connections[device_id].remove(conn)
                self.logger.bind(tag=TAG).info(
                    f"App 连接已注销: {device_id}, 剩余连接数: {len(self.app_connections[device_id])}"
                )
            
            # 如果该设备没有 App 连接了，删除该 key
            if not self.app_connections[device_id]:
                del self.app_connections[device_id]
    
    def get_esp32_conn(self, device_id: str) -> Optional['ConnectionHandler']:
        """获取 ESP32 连接
        
        Args:
            device_id: 设备唯一标识符
            
        Returns:
            ConnectionHandler 实例，如果不存在则返回 None
        """
        return self.esp32_connections.get(device_id)
    
    def get_app_conns(self, device_id: str) -> List['AppConnectionHandler']:
        """获取所有关联的 App 连接
        
        Args:
            device_id: 设备唯一标识符
            
        Returns:
            AppConnectionHandler 实例列表
        """
        return self.app_connections.get(device_id, [])
    
    def is_esp32_online(self, device_id: str) -> bool:
        """检查 ESP32 是否在线
        
        Args:
            device_id: 设备唯一标识符
            
        Returns:
            True 如果在线，否则 False
        """
        return device_id in self.esp32_connections
