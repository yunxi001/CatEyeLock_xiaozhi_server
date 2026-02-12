"""
人脸识别重试处理器
"""
import asyncio
from typing import Optional, Dict, Any
from loguru import logger

TAG = __name__


class FaceRecognitionHandler:
    """人脸识别重试处理器"""
    
    def __init__(self, face_service, tts_provider, config: dict):
        """初始化人脸识别处理器
        
        Args:
            face_service: 人脸识别服务实例
            tts_provider: TTS 服务提供者实例
            config: 配置字典，包含 max_retries 和 retry_interval
        """
        self.face_service = face_service
        self.tts_provider = tts_provider
        self.max_retries = config.get('max_retries', 3)
        self.retry_interval = config.get('retry_interval', 1)
        
        logger.bind(tag=TAG).info(
            f"人脸识别处理器初始化完成 - 最大重试次数: {self.max_retries}, "
            f"重试间隔: {self.retry_interval}秒"
        )
    
    async def recognize_with_retry(
        self, 
        device_id: str, 
        jpeg_data: bytes,
        max_retries: Optional[int] = None
    ) -> Dict[str, Any]:
        """人脸识别（支持重试）
        
        Args:
            device_id: 设备ID
            jpeg_data: JPEG 图像数据
            max_retries: 最大重试次数，默认使用配置值
            
        Returns:
            识别结果字典:
            {
                "success": bool,  # 是否识别成功
                "person_id": int or None,  # 人员ID
                "person": Person or None,  # 人员对象
                "result": str,  # 识别结果: "known", "unknown", "no_face"
                "confidence": float,  # 置信度
                "attempts": int  # 尝试次数
            }
        """
        if max_retries is None:
            max_retries = self.max_retries
        
        logger.bind(tag=TAG).info(
            f"开始人脸识别 - 设备: {device_id}, 最大重试: {max_retries}次"
        )
        
        for attempt in range(1, max_retries + 1):
            logger.bind(tag=TAG).debug(
                f"人脸识别尝试 {attempt}/{max_retries} - 设备: {device_id}"
            )
            
            # 调用人脸识别服务
            result = self.face_service.recognize(jpeg_data)
            
            # 识别成功
            if result.result == 'known' and result.person:
                logger.bind(tag=TAG).info(
                    f"人脸识别成功 - 设备: {device_id}, "
                    f"人员: {result.person.name} (ID: {result.person.id}), "
                    f"置信度: {result.confidence:.3f}, "
                    f"尝试次数: {attempt}"
                )
                return {
                    "success": True,
                    "person_id": result.person.id,
                    "person": result.person,
                    "result": result.result,
                    "confidence": result.confidence,
                    "attempts": attempt
                }
            
            # 识别失败，处理语音提示
            logger.bind(tag=TAG).warning(
                f"人脸识别失败 - 设备: {device_id}, "
                f"结果: {result.result}, "
                f"尝试: {attempt}/{max_retries}"
            )
            
            # 第一次失败时播放语音提示
            if attempt == 1:
                await self._play_retry_prompt(device_id)
            
            # 如果还有重试机会，等待后继续
            if attempt < max_retries:
                logger.bind(tag=TAG).debug(
                    f"等待 {self.retry_interval}秒 后重试 - 设备: {device_id}"
                )
                await asyncio.sleep(self.retry_interval)
            else:
                # 三次都失败，播放最终失败提示
                await self._play_final_failure_prompt(device_id)
        
        # 所有尝试都失败
        logger.bind(tag=TAG).error(
            f"人脸识别最终失败 - 设备: {device_id}, "
            f"尝试次数: {max_retries}"
        )
        
        return {
            "success": False,
            "person_id": None,
            "person": None,
            "result": result.result if 'result' in locals() else "no_face",
            "confidence": 0.0,
            "attempts": max_retries
        }
    
    async def _play_retry_prompt(self, device_id: str):
        """播放重试提示语音
        
        Args:
            device_id: 设备ID
        """
        prompt_text = "人脸识别失败，请正视摄像头重试"
        logger.bind(tag=TAG).info(
            f"播放重试提示 - 设备: {device_id}, 内容: {prompt_text}"
        )
        
        try:
            # 调用 TTS 服务生成语音
            audio_data = await self._generate_tts(prompt_text)
            if audio_data:
                # TODO: 发送音频到设备
                # 这里需要集成实际的音频发送逻辑
                logger.bind(tag=TAG).debug(
                    f"重试提示语音已生成 - 设备: {device_id}"
                )
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"播放重试提示失败 - 设备: {device_id}, 错误: {e}"
            )
    
    async def _play_final_failure_prompt(self, device_id: str):
        """播放最终失败提示语音
        
        Args:
            device_id: 设备ID
        """
        prompt_text = "人脸识别失败，请使用其他方式解锁"
        logger.bind(tag=TAG).info(
            f"播放最终失败提示 - 设备: {device_id}, 内容: {prompt_text}"
        )
        
        try:
            # 调用 TTS 服务生成语音
            audio_data = await self._generate_tts(prompt_text)
            if audio_data:
                # TODO: 发送音频到设备
                # 这里需要集成实际的音频发送逻辑
                logger.bind(tag=TAG).debug(
                    f"最终失败提示语音已生成 - 设备: {device_id}"
                )
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"播放最终失败提示失败 - 设备: {device_id}, 错误: {e}"
            )
    
    async def _generate_tts(self, text: str) -> Optional[bytes]:
        """生成 TTS 语音
        
        Args:
            text: 要转换的文本
            
        Returns:
            音频数据（bytes）或 None
        """
        try:
            # 使用 TTS 提供者生成语音
            # 根据 TTS 提供者的实现，可能返回文件路径或音频数据
            result = await self.tts_provider.text_to_speak(text, None)
            return result
        except Exception as e:
            logger.bind(tag=TAG).error(f"TTS 生成失败: {e}")
            return None
