"""
用户管理命令控制器
"""
import json
import time

TAG = __name__


class UserManager:
    """用户管理控制器，负责下发指纹/NFC/密码管理命令"""
    
    @staticmethod
    async def send_user_mgmt(
        conn,
        category: str,
        command: str,
        user_id: int = 0,
        payload: str = ""
    ) -> str:
        """发送用户管理命令
        
        Args:
            conn: 连接对象
            category: 类别 (finger/nfc/password)
            command: 命令 (add/del/clear/query/set)
            user_id: 用户 ID，0=自动分配
            payload: 附加数据（密码设置时使用）
            
        Returns:
            msg_id: 消息 ID
        """
        msg_id = f"cmd_{int(time.time() * 1000)}"
        
        message = {
            "type": "user_mgmt",
            "msg_id": msg_id,
            "category": category,
            "command": command,
            "user_id": user_id,
            "payload": payload
        }
        
        await conn.websocket.send(json.dumps(message))
        conn.logger.bind(tag=TAG).info(
            f"发送用户管理命令: {category}/{command}, user_id={user_id}"
        )
        
        return msg_id
    
    # ========== 指纹管理 ==========
    
    @staticmethod
    async def add_finger(conn) -> str:
        """添加指纹"""
        return await UserManager.send_user_mgmt(conn, "finger", "add")
    
    @staticmethod
    async def delete_finger(conn, user_id: int) -> str:
        """删除指纹"""
        return await UserManager.send_user_mgmt(conn, "finger", "del", user_id)
    
    @staticmethod
    async def clear_fingers(conn) -> str:
        """清空所有指纹"""
        return await UserManager.send_user_mgmt(conn, "finger", "clear")
    
    @staticmethod
    async def query_fingers(conn) -> str:
        """查询指纹数量"""
        return await UserManager.send_user_mgmt(conn, "finger", "query")
    
    # ========== NFC 管理 ==========
    
    @staticmethod
    async def add_nfc(conn) -> str:
        """添加 NFC 卡"""
        return await UserManager.send_user_mgmt(conn, "nfc", "add")
    
    @staticmethod
    async def delete_nfc(conn, user_id: int) -> str:
        """删除 NFC 卡"""
        return await UserManager.send_user_mgmt(conn, "nfc", "del", user_id)
    
    @staticmethod
    async def clear_nfc(conn) -> str:
        """清空所有 NFC 卡"""
        return await UserManager.send_user_mgmt(conn, "nfc", "clear")
    
    @staticmethod
    async def query_nfc(conn) -> str:
        """查询 NFC 卡数量"""
        return await UserManager.send_user_mgmt(conn, "nfc", "query")
    
    # ========== 密码管理 ==========
    
    @staticmethod
    async def set_password(conn, password: str) -> str:
        """设置密码
        
        Args:
            conn: 连接对象
            password: 6位数字密码
        """
        if len(password) != 6 or not password.isdigit():
            raise ValueError("密码必须是6位数字")
        return await UserManager.send_user_mgmt(conn, "password", "set", payload=password)
    
    @staticmethod
    async def query_password(conn) -> str:
        """查询密码状态"""
        return await UserManager.send_user_mgmt(conn, "password", "query")
