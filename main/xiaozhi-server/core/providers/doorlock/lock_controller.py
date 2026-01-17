"""
锁控命令控制器
"""
import json
import time

TAG = __name__


class LockController:
    """门锁控制器，负责下发锁控命令"""
    
    @staticmethod
    async def send_lock_control(
        conn,
        command: str,
        duration: int = 0
    ) -> str:
        """发送锁控命令
        
        Args:
            conn: 连接对象
            command: 命令类型 (unlock/lock)
            duration: 开锁保持时间(秒)，0=默认3分钟
            
        Returns:
            msg_id: 消息 ID
        """
        msg_id = f"cmd_{int(time.time() * 1000)}"
        
        message = {
            "type": "lock_control",
            "msg_id": msg_id,
            "command": command,
            "duration": duration
        }
        
        await conn.websocket.send(json.dumps(message))
        conn.logger.bind(tag=TAG).info(f"发送锁控命令: {command}, msg_id={msg_id}")
        
        return msg_id
    
    @staticmethod
    async def send_temp_code(
        conn,
        code: str,
        expires: int = 3600
    ) -> str:
        """发送临时密码
        
        Args:
            conn: 连接对象
            code: 6位临时密码
            expires: 有效期(秒)
            
        Returns:
            msg_id: 消息 ID
        """
        msg_id = f"cmd_{int(time.time() * 1000)}"
        
        message = {
            "type": "lock_control",
            "msg_id": msg_id,
            "command": "temp_code",
            "code": code,
            "expires": expires
        }
        
        await conn.websocket.send(json.dumps(message))
        conn.logger.bind(tag=TAG).info(f"发送临时密码, msg_id={msg_id}")
        
        return msg_id
    
    @staticmethod
    async def unlock(conn, duration: int = 0) -> str:
        """远程开锁"""
        return await LockController.send_lock_control(conn, "unlock", duration)
    
    @staticmethod
    async def lock(conn) -> str:
        """远程关锁"""
        return await LockController.send_lock_control(conn, "lock", 0)
