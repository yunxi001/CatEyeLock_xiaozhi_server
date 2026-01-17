"""
硬件外设控制器
"""
import json
import time

TAG = __name__


class DeviceController:
    """硬件外设控制器"""
    
    @staticmethod
    async def control_beep(
        conn,
        count: int = 1,
        mode: str = "short"
    ) -> str:
        """控制蜂鸣器
        
        Args:
            conn: 连接对象
            count: 响铃次数
            mode: 模式 (short/long/alarm)
            
        Returns:
            msg_id: 消息 ID
        """
        msg_id = f"cmd_{int(time.time() * 1000)}"
        
        message = {
            "type": "dev_control",
            "msg_id": msg_id,
            "target": "beep",
            "count": count,
            "mode": mode
        }
        
        await conn.websocket.send(json.dumps(message))
        conn.logger.bind(tag=TAG).info(f"控制蜂鸣器: mode={mode}, count={count}")
        
        return msg_id
    
    @staticmethod
    async def control_oled(conn, icon: int) -> str:
        """控制 OLED 显示
        
        Args:
            conn: 连接对象
            icon: 图标 ID (0-5)
                0: 清屏/待机
                1: WiFi 已连接
                2: 云端已连接
                3: 识别中
                4: 识别成功
                5: 识别失败
            
        Returns:
            msg_id: 消息 ID
        """
        msg_id = f"cmd_{int(time.time() * 1000)}"
        
        message = {
            "type": "dev_control",
            "msg_id": msg_id,
            "target": "oled",
            "icon": icon
        }
        
        await conn.websocket.send(json.dumps(message))
        conn.logger.bind(tag=TAG).info(f"控制 OLED: icon={icon}")
        
        return msg_id
    
    @staticmethod
    async def control_light(conn, action: str) -> str:
        """控制补光灯
        
        Args:
            conn: 连接对象
            action: 动作 (on/off/auto)
            
        Returns:
            msg_id: 消息 ID
        """
        msg_id = f"cmd_{int(time.time() * 1000)}"
        
        message = {
            "type": "dev_control",
            "msg_id": msg_id,
            "target": "light",
            "action": action
        }
        
        await conn.websocket.send(json.dumps(message))
        conn.logger.bind(tag=TAG).info(f"控制补光灯: action={action}")
        
        return msg_id
    
    @staticmethod
    async def alarm(conn, count: int = 3) -> str:
        """触发警报"""
        return await DeviceController.control_beep(conn, count, "alarm")
    
    @staticmethod
    async def beep_short(conn, count: int = 1) -> str:
        """短滴提示音"""
        return await DeviceController.control_beep(conn, count, "short")
    
    @staticmethod
    async def light_on(conn) -> str:
        """开启补光灯"""
        return await DeviceController.control_light(conn, "on")
    
    @staticmethod
    async def light_off(conn) -> str:
        """关闭补光灯"""
        return await DeviceController.control_light(conn, "off")
    
    @staticmethod
    async def light_auto(conn) -> str:
        """恢复补光灯自动控制"""
        return await DeviceController.control_light(conn, "auto")
