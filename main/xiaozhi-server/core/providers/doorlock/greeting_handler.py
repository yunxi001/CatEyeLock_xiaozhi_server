"""
欢迎词播放处理器
"""
import json
from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger

TAG = __name__


class GreetingHandler:
    """欢迎词播放处理器"""
    
    def __init__(self, doorlock_database, tts_provider):
        """初始化欢迎词处理器
        
        Args:
            doorlock_database: 门锁数据库服务实例
            tts_provider: TTS 服务提供者实例
        """
        self.db = doorlock_database
        self.tts_provider = tts_provider
        
        logger.bind(tag=TAG).info("欢迎词处理器初始化完成")
    
    def select_greeting(
        self, 
        custom_greeting: Optional[Dict[str, str]], 
        current_time: Optional[datetime] = None
    ) -> str:
        """根据时段选择欢迎词
        
        Args:
            custom_greeting: 自定义欢迎词配置字典
                {
                    "morning": "早上好",
                    "afternoon": "下午好",
                    "evening": "晚上好",
                    "night": "夜深了",
                    "default": "欢迎回家"
                }
            current_time: 当前时间，默认使用系统当前时间
            
        Returns:
            选择的欢迎词文本
        """
        if current_time is None:
            current_time = datetime.now()
        
        hour = current_time.hour
        
        # 判断时段
        if 6 <= hour < 12:
            time_slot = "morning"
            time_slot_name = "早晨"
        elif 12 <= hour < 18:
            time_slot = "afternoon"
            time_slot_name = "下午"
        elif 18 <= hour < 22:
            time_slot = "evening"
            time_slot_name = "晚上"
        else:
            time_slot = "night"
            time_slot_name = "夜间"
        
        # 如果没有自定义欢迎词，使用默认
        if not custom_greeting:
            logger.bind(tag=TAG).debug(
                f"未配置自定义欢迎词，使用默认欢迎词 - 时段: {time_slot_name}"
            )
            return "欢迎回家"
        
        # 尝试获取时段对应的欢迎词
        greeting = custom_greeting.get(time_slot)
        if greeting:
            logger.bind(tag=TAG).debug(
                f"使用时段欢迎词 - 时段: {time_slot_name}, 内容: {greeting}"
            )
            return greeting
        
        # 回退到 default
        greeting = custom_greeting.get("default")
        if greeting:
            logger.bind(tag=TAG).debug(
                f"使用默认欢迎词 - 内容: {greeting}"
            )
            return greeting
        
        # 最终回退
        logger.bind(tag=TAG).debug("使用系统默认欢迎词")
        return "欢迎回家"
    
    async def play_welcome_greeting(
        self, 
        device_id: str, 
        person_id: int,
        person_name: Optional[str] = None,
        conn=None
    ) -> bool:
        """播放欢迎词
        
        Args:
            device_id: 设备ID
            person_id: 人员ID
            person_name: 人员姓名（可选，用于日志）
            conn: 连接对象（用于 TTS 播放）
            
        Returns:
            是否成功播放
        """
        try:
            # 从数据库获取用户的欢迎词配置
            greeting_config = await self.db.get_person_greeting(person_id)
            
            # 解析 JSON 格式的欢迎词配置
            custom_greeting = None
            if greeting_config:
                try:
                    custom_greeting = json.loads(greeting_config)
                except json.JSONDecodeError as e:
                    logger.bind(tag=TAG).warning(
                        f"欢迎词配置解析失败 - 人员ID: {person_id}, 错误: {e}"
                    )
            
            # 选择欢迎词
            greeting_text = self.select_greeting(custom_greeting)
            
            # 替换姓名占位符（如果有）
            if person_name and "{name}" in greeting_text:
                greeting_text = greeting_text.replace("{name}", person_name)
            
            logger.bind(tag=TAG).info(
                f"播放欢迎词 - 设备: {device_id}, "
                f"人员: {person_name or person_id}, "
                f"内容: {greeting_text}"
            )
            
            # 通过设备连接播放 TTS（遵循正常对话流程：FIRST → MIDDLE → LAST）
            if conn and hasattr(conn, 'tts') and conn.tts:
                from core.providers.tts.dto.dto import ContentType, SentenceType, TTSMessageDTO
                import uuid
                
                sentence_id = str(uuid.uuid4().hex)
                conn.sentence_id = sentence_id
                
                conn.tts.tts_text_queue.put(TTSMessageDTO(
                    sentence_id=sentence_id,
                    sentence_type=SentenceType.FIRST,
                    content_type=ContentType.ACTION,
                ))
                conn.tts.tts_text_queue.put(TTSMessageDTO(
                    sentence_id=sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=ContentType.TEXT,
                    content_detail=greeting_text,
                ))
                conn.tts.tts_text_queue.put(TTSMessageDTO(
                    sentence_id=sentence_id,
                    sentence_type=SentenceType.LAST,
                    content_type=ContentType.ACTION,
                ))
                return True
            else:
                logger.bind(tag=TAG).warning(
                    f"无法播放欢迎词：连接对象无 TTS 实例 - 设备: {device_id}"
                )
                return False
                
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"播放欢迎词失败 - 设备: {device_id}, "
                f"人员ID: {person_id}, 错误: {e}"
            )
            return False
    
    async def _generate_tts(self, text: str) -> Optional[bytes]:
        """生成 TTS 语音
        
        Args:
            text: 要转换的文本
            
        Returns:
            音频数据（bytes）或 None
        """
        try:
            # 使用 TTS 提供者生成语音
            result = await self.tts_provider.text_to_speak(text, None)
            return result
        except Exception as e:
            logger.bind(tag=TAG).error(f"TTS 生成失败: {e}")
            return None
