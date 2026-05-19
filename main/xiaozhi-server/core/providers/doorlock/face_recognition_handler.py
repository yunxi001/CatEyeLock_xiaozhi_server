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
        conn=None,  # 新增参数：连接对象，用于检查PIR状态
        max_retries: Optional[int] = None
    ) -> Dict[str, Any]:
        """人脸识别（支持重试）
        
        Args:
            device_id: 设备ID
            jpeg_data: JPEG 图像数据
            conn: 连接对象（可选），用于检查PIR状态
            max_retries: 最大重试次数，默认使用配置值
            
        Returns:
            识别结果字典:
            {
                "success": bool,  # 是否识别成功
                "person_id": int or None,  # 人员ID
                "person": Person or None,  # 人员对象
                "result": str,  # 识别结果: "known", "unknown", "no_face", "pir_interrupted"
                "confidence": float,  # 置信度
                "attempts": int  # 尝试次数
            }
        """
        from core.utils.pir_utils import is_pir_timeout
        
        if max_retries is None:
            max_retries = self.max_retries
        
        logger.bind(tag=TAG).info(
            f"开始人脸识别 - 设备: {device_id}, 最大重试: {max_retries}次"
        )
        
        for attempt in range(1, max_retries + 1):
            # 每次重试前检查PIR状态（优化：人离开时及时中止）
            if conn and hasattr(conn, 'last_pir_time'):
                if is_pir_timeout(conn, timeout=2.0):
                    logger.bind(tag=TAG).info(
                        f"PIR超时，人体已离开，中止识别 - "
                        f"设备: {device_id}, 尝试次数: {attempt-1}/{max_retries}"
                    )
                    return {
                        "success": False,
                        "person_id": None,
                        "person": None,
                        "result": "pir_interrupted",
                        "confidence": 0.0,
                        "attempts": attempt - 1
                    }
            
            # 重试时重新拍照（第一次使用传入的照片）
            current_jpeg = jpeg_data
            if attempt > 1 and conn:
                logger.bind(tag=TAG).info(
                    f"重试拍照 - 设备: {device_id}, 尝试: {attempt}/{max_retries}"
                )
                try:
                    from core.providers.doorlock.esp32_camera import ESP32CameraService
                    camera_service = ESP32CameraService(config={}, logger_instance=logger)
                    new_photo = await camera_service.capture_image(
                        device_id=device_id,
                        conn=conn,
                        question="人脸识别重试拍照",
                        timeout=10
                    )
                    if new_photo:
                        current_jpeg = new_photo
                        logger.bind(tag=TAG).info(
                            f"重试拍照成功 - 设备: {device_id}, "
                            f"大小: {len(new_photo)} bytes"
                        )
                    else:
                        logger.bind(tag=TAG).warning(
                            f"重试拍照失败，使用上一张照片 - 设备: {device_id}"
                        )
                except Exception as e:
                    logger.bind(tag=TAG).warning(
                        f"重试拍照异常，使用上一张照片 - 设备: {device_id}, 错误: {e}"
                    )
            
            logger.bind(tag=TAG).info(
                f"人脸识别尝试 {attempt}/{max_retries} - 设备: {device_id}, "
                f"照片大小: {len(current_jpeg)} bytes"
            )
            
            # 保存照片到磁盘（用于调试和回溯）
            try:
                from pathlib import Path
                from datetime import datetime
                save_dir = Path("data/face_recognition/visits") / datetime.now().strftime("%Y-%m")
                save_dir.mkdir(parents=True, exist_ok=True)
                ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"pir_{device_id.replace(':', '')}_{ts_str}_attempt{attempt}.jpg"
                filepath = save_dir / filename
                with open(filepath, 'wb') as f:
                    f.write(current_jpeg)
                logger.bind(tag=TAG).info(f"照片已保存: {filepath}")
            except Exception as e:
                logger.bind(tag=TAG).warning(f"保存照片失败: {e}")
            
            # 调用人脸识别服务
            result = self.face_service.recognize(current_jpeg)
            
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
            
            # 第一次失败时记录日志（ESP32 尚未唤醒，不播放语音）
            if attempt == 1:
                logger.bind(tag=TAG).info(
                    f"人脸识别第一次失败，继续重试 - 设备: {device_id}"
                )
            
            # 如果还有重试机会，等待后继续
            if attempt < max_retries:
                logger.bind(tag=TAG).debug(
                    f"等待 {self.retry_interval}秒 后重试 - 设备: {device_id}"
                )
                await asyncio.sleep(self.retry_interval)
            else:
                # 三次都失败，记录日志（语音提示在 start_listening 之后由对话流程处理）
                logger.bind(tag=TAG).info(
                    f"人脸识别最终失败，将进入意图对话 - 设备: {device_id}"
                )
        
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
    
    async def _play_tts(self, conn, text: str):
        """通过设备连接播放 TTS 语音（遵循正常对话流程）
        
        Args:
            conn: 连接对象（持有 tts 实例）
            text: 要播放的文本
        """
        try:
            if not conn or not hasattr(conn, 'tts') or not conn.tts:
                logger.bind(tag=TAG).warning(
                    f"无法播放语音：连接对象无 TTS 实例"
                )
                return
            
            from core.providers.tts.dto.dto import ContentType, SentenceType, TTSMessageDTO
            import uuid
            
            sentence_id = str(uuid.uuid4().hex)
            conn.sentence_id = sentence_id
            
            # FIRST → MIDDLE → LAST（正常对话流程）
            conn.tts.tts_text_queue.put(TTSMessageDTO(
                sentence_id=sentence_id,
                sentence_type=SentenceType.FIRST,
                content_type=ContentType.ACTION,
            ))
            conn.tts.tts_text_queue.put(TTSMessageDTO(
                sentence_id=sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.TEXT,
                content_detail=text,
            ))
            conn.tts.tts_text_queue.put(TTSMessageDTO(
                sentence_id=sentence_id,
                sentence_type=SentenceType.LAST,
                content_type=ContentType.ACTION,
            ))
            logger.bind(tag=TAG).info(f"已发送 TTS: {text}")
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"播放语音失败: {e}")
