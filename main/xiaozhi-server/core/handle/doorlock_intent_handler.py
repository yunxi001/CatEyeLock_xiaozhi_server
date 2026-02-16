"""
智能门锁意图识别对话处理器

处理访客到访的完整流程：
- 人脸识别（支持重试）
- 欢迎词播放（有权限用户）
- 意图识别对话（无权限访客）
- 生成意图总结
- 发送App通知
"""
import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from core.providers.doorlock.face_recognition_handler import FaceRecognitionHandler
from core.providers.doorlock.greeting_handler import GreetingHandler
from core.providers.doorlock.session_manager import SessionManager
from core.providers.doorlock.notification_service import NotificationService
from core.providers.doorlock.doorlock_database import DoorlockDatabase
from core.providers.vllm.doorlock_vllm import DoorlockVLLMProvider
from core.providers.doorlock.photo_cache_manager import PhotoCacheManager

TAG = "DoorlockIntentHandler"


class DoorlockIntentHandler:
    """门锁意图识别对话处理器"""
    
    def __init__(
        self,
        face_recognition_handler: FaceRecognitionHandler,
        greeting_handler: GreetingHandler,
        session_manager: SessionManager,
        notification_service: NotificationService,
        doorlock_database: DoorlockDatabase,
        vllm_provider: DoorlockVLLMProvider,
        config: dict
    ):
        """初始化意图识别处理器
        
        Args:
            face_recognition_handler: 人脸识别处理器
            greeting_handler: 欢迎词处理器
            session_manager: 会话管理器
            notification_service: 通知服务
            doorlock_database: 门锁数据库服务
            vllm_provider: VLLM提供者
            config: 配置字典
        """
        self.face_handler = face_recognition_handler
        self.greeting_handler = greeting_handler
        self.session_manager = session_manager
        self.notification_service = notification_service
        self.db = doorlock_database
        self.vllm = vllm_provider
        
        # 配置参数
        self.dialogue_timeout = config.get('dialogue_timeout', 30)
        self.max_dialogue_rounds = config.get('max_dialogue_rounds', 10)
        self.max_token_usage_ratio = config.get('max_token_usage_ratio', 0.8)
        
        # 提示词（从配置加载）
        self.intent_recognition_prompt = config.get('intent_recognition_prompt', '')
        
        # 照片缓存管理器
        self.photo_cache = PhotoCacheManager()
        
        # 定时拍照任务字典：{session_id: asyncio.Task}
        self._photo_capture_tasks: Dict[str, asyncio.Task] = {}
        
        logger.bind(tag=TAG).info(
            f"意图识别处理器初始化完成: timeout={self.dialogue_timeout}s, "
            f"max_rounds={self.max_dialogue_rounds}"
        )
    
    @classmethod
    async def create_from_config(cls, config: dict, logger_instance):
        """从配置创建处理器实例（工厂方法）
        
        Args:
            config: 配置字典
            logger_instance: 日志实例
            
        Returns:
            DoorlockIntentHandler实例
        """
        # 加载门锁配置
        doorlock_config = config.get('doorlock', {})
        
        # 初始化各个组件
        face_handler = FaceRecognitionHandler(config, logger_instance)
        greeting_handler = GreetingHandler(config, logger_instance)
        session_manager = SessionManager(logger_instance)
        notification_service = NotificationService()
        doorlock_database = DoorlockDatabase(logger_instance)
        
        # 初始化VLLM提供者
        vllm_provider = None
        if 'VLLM' in config and config.get('selected_module', {}).get('VLLM'):
            try:
                vllm_provider = DoorlockVLLMProvider(config, logger_instance)
            except Exception as e:
                logger_instance.bind(tag=TAG).warning(f"VLLM提供者初始化失败: {e}")
        
        return cls(
            face_recognition_handler=face_handler,
            greeting_handler=greeting_handler,
            session_manager=session_manager,
            notification_service=notification_service,
            doorlock_database=doorlock_database,
            vllm_provider=vllm_provider,
            config=doorlock_config.get('intent_recognition', {})
        )
    
    async def handle_visitor(
        self,
        device_id: str,
        conn=None,
        guard_active: bool = False,
        session_id: Optional[str] = None,
        jpeg_data: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """处理访客到访主流程（支持从PIR事件调用）
        
        Args:
            device_id: 设备ID
            conn: 连接对象（可选，用于获取TTS/ASR服务）
            guard_active: 看护模式是否激活
            session_id: 会话ID（可选，如果不提供则自动生成）
            jpeg_data: 访客照片（可选，如果不提供则自动拍照）
            
        Returns:
            处理结果字典
        """
        # 生成会话ID
        if not session_id:
            session = self.session_manager.create_session(device_id)
            session_id = session.session_id
        
        logger.bind(tag=TAG).info(
            f"开始处理访客到访 - 设备: {device_id}, 会话: {session_id}, "
            f"看护模式: {'激活' if guard_active else '未激活'}"
        )
        
        try:
            # 如果看护模式激活，同时启动监控和对话
            if guard_active:
                logger.bind(tag=TAG).info(f"看护模式已激活，将同时启动监控和对话")
                # TODO: 启动看护监控任务
                # asyncio.create_task(self._start_package_monitoring(device_id, session_id))
            
            # 步骤1: 拍照（如果没有提供照片）
            if not jpeg_data:
                jpeg_data = await self._capture_visitor_photo(device_id, conn)
                if not jpeg_data:
                    logger.bind(tag=TAG).error(f"拍照失败 - 设备: {device_id}")
                    return {"success": False, "error": "拍照失败"}
            
            # 步骤2: 人脸识别（支持重试）
            recognition_result = await self.face_handler.recognize_with_retry(
                device_id=device_id,
                jpeg_data=jpeg_data,
                conn=conn
            )
            
            # 步骤3: 判断是否有开门权限
            if recognition_result["success"] and recognition_result["person"]:
                person = recognition_result["person"]
                
                # 检查权限
                has_permission = await self._check_access_permission(
                    person_id=person.id
                )
                
                if has_permission:
                    # 有权限：下发face_result消息并播放欢迎词
                    logger.bind(tag=TAG).info(
                        f"访客有开门权限 - 人员: {person.name} (ID: {person.id})"
                    )
                    
                    # 下发face_result消息（ESP32会根据granted字段自动开锁）
                    await self._send_face_result(
                        conn=conn,
                        result="known",
                        user_id=person.id,
                        access_granted=True,
                        reason="authorized_user"
                    )
                    
                    # 播放欢迎词
                    await self.greeting_handler.play_welcome_greeting(
                        device_id=device_id,
                        person_id=person.id,
                        person_name=person.name,
                        conn=conn
                    )
                    
                    # 清除会话
                    await self.session_manager.cleanup_session(session_id)
                    
                    return {
                        "success": True,
                        "action": "door_opened",
                        "person_id": person.id,
                        "person_name": person.name
                    }
                else:
                    # 无权限：下发face_result消息（拒绝开锁）
                    logger.bind(tag=TAG).info(
                        f"访客无开门权限 - 人员: {person.name} (ID: {person.id})"
                    )
                    
                    await self._send_face_result(
                        conn=conn,
                        result="known",
                        user_id=person.id,
                        access_granted=False,
                        reason="unauthorized_user"
                    )
            else:
                # 识别失败：下发face_result消息
                result = recognition_result.get("result", "error")
                logger.bind(tag=TAG).info(
                    f"人脸识别失败 - 结果: {result}"
                )
                
                await self._send_face_result(
                    conn=conn,
                    result=result,
                    user_id=None,
                    access_granted=False,
                    reason="unauthorized_user"
                )
            
            # 步骤4: 无权限或识别失败，启动意图识别对话
            person_info = None
            if recognition_result["success"] and recognition_result["person"]:
                person = recognition_result["person"]
                person_info = {
                    "person_id": person.id,
                    "name": person.name,
                    "relation_type": person.relation_type,
                    "has_permission": False
                }
            
            intent_result = await self.start_intent_dialogue(
                device_id=device_id,
                session_id=session_id,
                person_info=person_info,
                visitor_image=jpeg_data,
                conn=conn
            )
            
            # 清除会话
            await self.session_manager.cleanup_session(session_id)
            
            return intent_result
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"处理访客到访异常 - 设备: {device_id}, 会话: {session_id}, 错误: {e}"
            )
            import traceback
            logger.bind(tag=TAG).error(traceback.format_exc())
            
            # 清除会话
            try:
                await self.session_manager.cleanup_session(session_id)
            except:
                pass
            
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _capture_visitor_photo(
        self,
        device_id: str,
        conn=None
    ) -> Optional[bytes]:
        """拍摄访客照片（通过MCP协议）
        
        Args:
            device_id: 设备ID
            conn: 连接对象（必须有mcp_client）
            
        Returns:
            JPEG图片数据，失败返回None
        """
        try:
            from core.providers.doorlock.esp32_camera import ESP32CameraService
            
            logger.bind(tag=TAG).info(f"拍摄访客照片 - 设备: {device_id}")
            
            # 检查连接对象
            if not conn:
                logger.bind(tag=TAG).error(
                    f"拍照失败：未提供连接对象 - 设备: {device_id}"
                )
                return None
            
            # 创建摄像头服务
            # 注意：这里需要传入完整的config，从self获取或使用空字典
            camera_config = {}
            if hasattr(self, 'config'):
                # 如果有config属性，使用它
                camera_config = self.config
            else:
                # 否则尝试从其他组件获取
                logger.bind(tag=TAG).warning(
                    "DoorlockIntentHandler未找到config属性，使用默认配置"
                )
            
            camera_service = ESP32CameraService(
                config=camera_config,
                logger_instance=logger
            )
            
            # 调用拍照（通过MCP协议）
            jpeg_data = await camera_service.capture_image(
                device_id=device_id,
                conn=conn,
                question="访客到访拍照",
                timeout=10
            )
            
            if jpeg_data:
                logger.bind(tag=TAG).info(
                    f"拍照成功 - 设备: {device_id}, "
                    f"大小: {len(jpeg_data)} bytes"
                )
                return jpeg_data
            else:
                logger.bind(tag=TAG).error(
                    f"拍照失败 - 设备: {device_id}"
                )
                return None
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"拍摄访客照片异常 - 设备: {device_id}, 错误: {e}"
            )
            import traceback
            logger.bind(tag=TAG).error(traceback.format_exc())
            return None
    
    async def start_intent_dialogue(
        self,
        device_id: str,
        session_id: str,
        person_info: Optional[Dict[str, Any]],
        visitor_image: bytes,
        conn=None
    ) -> Dict[str, Any]:
        """启动意图识别对话
        
        Args:
            device_id: 设备ID
            session_id: 会话ID
            person_info: 人员信息（可选，陌生人为None）
            visitor_image: 访客照片
            conn: 连接对象（用于TTS/ASR服务）
            
        Returns:
            对话结果字典
        """
        logger.bind(tag=TAG).info(
            f"启动意图识别对话 - 设备: {device_id}, 会话: {session_id}, "
            f"访客: {person_info.get('name') if person_info else '陌生人'}"
        )
        
        try:
            # 步骤1: 播放主动问候
            greeting = await self._play_initial_greeting(device_id, person_info)
            
            # 添加问候到对话历史
            self.session_manager.add_dialogue(
                session_id=session_id,
                role="assistant",
                content=greeting
            )
            
            # 步骤2: 对话循环（持续到沉默30秒或PIR无人体）
            dialogue_count = 0
            max_rounds = self.max_dialogue_rounds
            
            while dialogue_count < max_rounds:
                # 检查对话是否应该结束
                should_end = await self.session_manager.check_dialogue_end(
                    session_id=session_id,
                    pir_detected=await self._check_pir_status(device_id)
                )
                
                if should_end:
                    logger.bind(tag=TAG).info(
                        f"对话结束 - 会话: {session_id}, 轮次: {dialogue_count}"
                    )
                    break
                
                # 等待访客回复（这里需要集成ASR服务）
                # TODO: 集成ASR服务获取访客语音
                visitor_response = await self._wait_for_visitor_response(device_id)
                
                if not visitor_response:
                    # 访客沉默，继续检查
                    await asyncio.sleep(1)
                    continue
                
                # 添加访客回复到对话历史
                self.session_manager.add_dialogue(
                    session_id=session_id,
                    role="user",
                    content=visitor_response
                )
                
                # 调用VLLM进行意图识别
                dialogue_history = self.session_manager.get_dialogue_history(session_id)
                
                # 转换图片为Base64
                import base64
                visitor_image_base64 = base64.b64encode(visitor_image).decode('utf-8')
                
                vllm_result = await self.vllm.analyze_intent(
                    visitor_image=visitor_image_base64,
                    dialogue_history=dialogue_history,
                    system_prompt=self.intent_recognition_prompt
                )
                
                # 检查Token使用量
                self._check_token_usage(vllm_result.get("token_usage", {}))
                
                # 处理AI回复
                ai_response = vllm_result.get("content", "")
                if ai_response:
                    # 添加AI回复到对话历史
                    self.session_manager.add_dialogue(
                        session_id=session_id,
                        role="assistant",
                        content=ai_response
                    )
                    
                    # 播放AI回复
                    await self._play_ai_response(device_id, ai_response)
                
                # 处理工具调用
                tool_calls = vllm_result.get("tool_calls", [])
                if tool_calls:
                    await self.vllm.execute_tool_calls(tool_calls)
                
                dialogue_count += 1
            
            # 步骤3: 生成意图总结
            dialogue_history = self.session_manager.get_dialogue_history(session_id)
            intent_summary = await self.generate_intent_summary(dialogue_history)
            
            # 步骤4: 保存到数据库
            visit_id = await self._save_visit_record(
                session_id=session_id,
                person_info=person_info,
                intent_summary=intent_summary,
                dialogue_history=dialogue_history,
                visitor_image=visitor_image
            )
            
            # 步骤5: 发送App通知
            await self.notification_service.notify_visitor_intent(
                visit_id=visit_id,
                session_id=session_id,
                person_info=person_info or {"person_id": None, "name": "陌生人", "relation_type": "unknown"},
                intent_summary=intent_summary,
                dialogue_text=dialogue_history
            )
            
            logger.bind(tag=TAG).info(
                f"意图识别对话完成 - 会话: {session_id}, visit_id: {visit_id}, "
                f"意图类型: {intent_summary.get('intent_type')}"
            )
            
            return {
                "success": True,
                "action": "intent_recognized",
                "visit_id": visit_id,
                "intent_summary": intent_summary,
                "dialogue_count": dialogue_count
            }
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"意图识别对话异常 - 会话: {session_id}, 错误: {e}"
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_intent_summary(
        self,
        dialogue_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """生成意图总结（JSON格式）
        
        Args:
            dialogue_history: 对话历史
            
        Returns:
            意图总结字典:
            {
                "important_notes": ["【留言】...", "【提醒】..."],
                "intent_type": "delivery/visit/sales/maintenance/other",
                "purpose": "来访目的",
                "full_summary": "完整摘要"
            }
        """
        logger.bind(tag=TAG).debug("生成意图总结")
        
        try:
            # 构建总结提示词
            summary_prompt = """
            请根据以下对话历史，生成结构化的访客意图总结。
            
            要求：
            1. 提取重要信息（留言、提醒），每条以【留言】或【提醒】开头
            2. 判断意图类型：delivery（送快递/外卖）、visit（拜访）、sales（推销）、maintenance（维修/物业）、other（其他）
            3. 概括来访目的
            4. 生成完整摘要
            
            请以JSON格式返回，包含以下字段：
            - important_notes: 重要信息列表
            - intent_type: 意图类型
            - purpose: 来访目的
            - full_summary: 完整摘要
            """
            
            # 调用VLLM生成总结
            # 这里简化处理，实际应该调用VLLM
            # 暂时使用规则提取
            intent_summary = self._extract_intent_from_dialogue(dialogue_history)
            
            logger.bind(tag=TAG).info(
                f"意图总结生成完成: intent_type={intent_summary.get('intent_type')}"
            )
            
            return intent_summary
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"生成意图总结异常: {e}")
            return {
                "important_notes": [],
                "intent_type": "other",
                "purpose": "无法识别",
                "full_summary": "对话记录不完整或无法识别意图"
            }
    
    def _extract_intent_from_dialogue(
        self,
        dialogue_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """从对话历史中提取意图（规则方法）
        
        Args:
            dialogue_history: 对话历史
            
        Returns:
            意图总结字典
        """
        # 简化实现：基于关键词判断
        full_text = " ".join([msg.get("content", "") for msg in dialogue_history])
        
        # 判断意图类型
        intent_type = "other"
        if any(kw in full_text for kw in ["快递", "外卖", "送货", "包裹"]):
            intent_type = "delivery"
        elif any(kw in full_text for kw in ["拜访", "找", "见面", "朋友"]):
            intent_type = "visit"
        elif any(kw in full_text for kw in ["推销", "产品", "服务", "办理"]):
            intent_type = "sales"
        elif any(kw in full_text for kw in ["维修", "物业", "检查", "抄表"]):
            intent_type = "maintenance"
        
        # 提取重要信息（简化）
        important_notes = []
        for msg in dialogue_history:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if any(kw in content for kw in ["留言", "告诉", "转达"]):
                    important_notes.append(f"【留言】{content}")
                elif any(kw in content for kw in ["提醒", "记得", "别忘"]):
                    important_notes.append(f"【提醒】{content}")
        
        # 生成摘要
        purpose = f"{intent_type}相关事宜"
        full_summary = f"访客进行了{len(dialogue_history)}轮对话，意图类型为{intent_type}。"
        
        return {
            "important_notes": important_notes,
            "intent_type": intent_type,
            "purpose": purpose,
            "full_summary": full_summary
        }
    
    async def _check_access_permission(self, person_id: int) -> bool:
        """检查开门权限
        
        Args:
            person_id: 人员ID
            
        Returns:
            是否有权限
        """
        # TODO: 调用人脸识别服务的权限检查
        # 这里简化处理，假设所有已识别的人都有权限
        return True
    
    async def _play_initial_greeting(
        self,
        device_id: str,
        person_info: Optional[Dict[str, Any]],
        conn=None
    ) -> str:
        """播放主动问候
        
        Args:
            device_id: 设备ID
            person_info: 人员信息
            conn: 连接对象（用于TTS服务）
            
        Returns:
            问候文本
        """
        if person_info:
            # 已识别但无权限的人
            greeting = f"您好，{person_info.get('name')}，请问有什么可以帮您？"
        else:
            # 陌生人
            greeting = "您好，请问您找谁？"
        
        logger.bind(tag=TAG).info(f"播放主动问候 - 设备: {device_id}, 内容: {greeting}")
        
        # TODO: 调用TTS服务播放语音
        # if conn and hasattr(conn, 'tts_service'):
        #     await conn.tts_service.play(greeting)
        
        return greeting
    
    async def _check_pir_status(self, device_id: str) -> bool:
        """检查PIR传感器状态
        
        Args:
            device_id: 设备ID
            
        Returns:
            是否检测到人体
        """
        # TODO: 查询设备的PIR状态
        # 这里简化处理，假设一直有人
        return True
    
    async def _wait_for_visitor_response(self, device_id: str, conn=None) -> Optional[str]:
        """等待访客回复
        
        Args:
            device_id: 设备ID
            conn: 连接对象（用于ASR服务）
            
        Returns:
            访客回复文本，如果没有回复返回None
        """
        # TODO: 集成ASR服务，等待语音识别结果
        # if conn and hasattr(conn, 'asr_service'):
        #     return await conn.asr_service.recognize()
        
        # 这里简化处理，返回None表示没有回复
        await asyncio.sleep(1)
        return None
    
    async def _play_ai_response(self, device_id: str, response: str, conn=None):
        """播放AI回复
        
        Args:
            device_id: 设备ID
            response: 回复文本
            conn: 连接对象（用于TTS服务）
        """
        logger.bind(tag=TAG).debug(f"播放AI回复 - 设备: {device_id}, 内容: {response}")
        
        # TODO: 调用TTS服务播放语音
        # if conn and hasattr(conn, 'tts_service'):
        #     await conn.tts_service.play(response)
    
    def _check_token_usage(self, token_usage: Dict[str, int]):
        """检查Token使用量
        
        Args:
            token_usage: Token使用统计
        """
        total_tokens = token_usage.get("total_tokens", 0)
        max_tokens = self.vllm.max_tokens
        
        usage_ratio = total_tokens / max_tokens if max_tokens > 0 else 0
        
        if usage_ratio > self.max_token_usage_ratio:
            logger.bind(tag=TAG).warning(
                f"Token使用量已达 {total_tokens}/{max_tokens} ({usage_ratio:.1%})，接近上限"
            )
    
    async def _save_visit_record(
        self,
        session_id: str,
        person_info: Optional[Dict[str, Any]],
        intent_summary: Dict[str, Any],
        dialogue_history: List[Dict[str, str]],
        visitor_image: bytes
    ) -> int:
        """保存访问记录到数据库
        
        Args:
            session_id: 会话ID
            person_info: 人员信息
            intent_summary: 意图总结
            dialogue_history: 对话历史
            visitor_image: 访客照片
            
        Returns:
            visit_id
        """
        try:
            # 保存访客意图记录
            from core.providers.doorlock.models import VisitorIntent
            
            intent = VisitorIntent(
                visit_id=None,  # TODO: 关联visit_records表
                session_id=session_id,
                person_id=person_info.get("person_id") if person_info else None,
                intent_type=intent_summary.get("intent_type", "other"),
                intent_summary=intent_summary,
                dialogue_history=dialogue_history
            )
            
            visit_id = await self.db.save_visitor_intent(intent)
            
            logger.bind(tag=TAG).info(
                f"访问记录已保存 - visit_id: {visit_id}, session_id: {session_id}"
            )
            
            return visit_id
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"保存访问记录异常: {e}")
            return 0

    async def _send_face_result(
        self,
        conn,
        result: str,
        user_id: Optional[int],
        access_granted: bool,
        reason: str
    ):
        """下发人脸识别结果消息
        
        根据v5.2协议规范，face_result是服务器主动推送的识别结果：
        - 不需要seq_id字段
        - 不需要esp32_ack和ack两级确认
        - ESP32根据access.granted字段决定是否开锁
        - 开锁结果通过log_report上报
        
        Args:
            conn: 连接对象
            result: 识别结果 (known/unknown/no_face/error)
            user_id: 用户ID（识别成功时有效）
            access_granted: 是否授权开锁
            reason: 授权/拒绝原因
        """
        try:
            if not conn:
                logger.bind(tag=TAG).warning("连接对象为空，无法发送face_result")
                return
            
            # 构建face_result消息（符合v5.2协议）
            face_result_msg = {
                "type": "face_result",
                "result": result,
                "user_id": user_id,
                "access": {
                    "granted": access_granted,
                    "reason": reason
                }
            }
            
            # 缓存识别结果（供开锁日志使用，30秒有效期）
            import time
            conn.last_face_result = {
                "ts": int(time.time() * 1000),
                "result": result,
                "user_id": user_id,
                "access_granted": access_granted,
                "reason": reason
            }
            
            # 发送消息
            await conn.send_json(face_result_msg)
            
            logger.bind(tag=TAG).info(
                f"已发送face_result - 设备: {conn.device_id}, "
                f"result={result}, user_id={user_id}, "
                f"granted={access_granted}, reason={reason}"
            )
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"发送face_result失败 - 设备: {conn.device_id if conn else 'unknown'}, "
                f"错误: {e}"
            )
            import traceback
            logger.bind(tag=TAG).error(traceback.format_exc())
    
    async def start_photo_capture_task(
        self,
        device_id: str,
        session_id: str,
        conn,
        interval_seconds: int = 5
    ) -> None:
        """启动定时拍照任务
        
        在统一看护对话模式中，每隔指定时间拍照一次并缓存。
        
        Args:
            device_id: 设备ID
            session_id: 会话ID
            conn: 连接对象（用于调用拍照接口）
            interval_seconds: 拍照间隔（秒），默认5秒
        """
        logger.bind(tag=TAG).info(
            f"启动定时拍照任务 - 设备: {device_id}, 会话: {session_id}, "
            f"间隔: {interval_seconds}秒"
        )
        
        async def photo_capture_loop():
            """定时拍照循环"""
            capture_count = 0
            
            try:
                while True:
                    try:
                        # 拍照
                        jpeg_data = await self._capture_visitor_photo(
                            device_id=device_id,
                            conn=conn
                        )
                        
                        if jpeg_data:
                            # 添加到缓存
                            self.photo_cache.add_photo(
                                session_id=session_id,
                                photo_data=jpeg_data
                            )
                            
                            capture_count += 1
                            cache_size = self.photo_cache.get_cache_size(session_id)
                            
                            logger.bind(tag=TAG).debug(
                                f"定时拍照成功 - 设备: {device_id}, 会话: {session_id}, "
                                f"第{capture_count}次, 缓存数量: {cache_size}"
                            )
                        else:
                            logger.bind(tag=TAG).warning(
                                f"定时拍照失败 - 设备: {device_id}, 会话: {session_id}"
                            )
                        
                    except Exception as e:
                        logger.bind(tag=TAG).error(
                            f"定时拍照异常 - 设备: {device_id}, 会话: {session_id}, "
                            f"错误: {e}"
                        )
                        # 继续运行，不中断任务
                    
                    # 等待下一次拍照
                    await asyncio.sleep(interval_seconds)
                    
            except asyncio.CancelledError:
                logger.bind(tag=TAG).info(
                    f"定时拍照任务已取消 - 设备: {device_id}, 会话: {session_id}, "
                    f"总拍照次数: {capture_count}"
                )
                raise
        
        # 创建并启动异步任务
        task = asyncio.create_task(photo_capture_loop())
        self._photo_capture_tasks[session_id] = task
        
        logger.bind(tag=TAG).info(
            f"定时拍照任务已启动 - 设备: {device_id}, 会话: {session_id}"
        )
    
    async def stop_photo_capture_task(
        self,
        session_id: str
    ) -> None:
        """停止定时拍照任务
        
        Args:
            session_id: 会话ID
        """
        logger.bind(tag=TAG).info(
            f"停止定时拍照任务 - 会话: {session_id}"
        )
        
        try:
            # 检查任务是否存在
            if session_id not in self._photo_capture_tasks:
                logger.bind(tag=TAG).debug(
                    f"定时拍照任务不存在 - 会话: {session_id}"
                )
                return
            
            # 获取任务
            task = self._photo_capture_tasks[session_id]
            
            # 取消任务
            if not task.done():
                task.cancel()
                
                try:
                    # 等待任务完成取消
                    await task
                except asyncio.CancelledError:
                    # 预期的取消异常
                    pass
            
            # 清理任务引用
            del self._photo_capture_tasks[session_id]
            
            logger.bind(tag=TAG).info(
                f"定时拍照任务已停止 - 会话: {session_id}"
            )
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"停止定时拍照任务异常 - 会话: {session_id}, 错误: {e}"
            )
            # 确保清理任务引用
            self._photo_capture_tasks.pop(session_id, None)
    
    async def start_unified_dialogue(
        self,
        device_id: str,
        session_id: str,
        person_info: Optional[Dict[str, Any]],
        visitor_image: bytes,
        baseline_image: Optional[bytes],
        conn=None
    ) -> Dict[str, Any]:
        """启动统一模式对话（支持看护）
        
        统一模式同时处理对话和看护监控任务。
        如果看护模式激活（baseline_image不为None），则启动定时拍照任务。
        
        Args:
            device_id: 设备ID
            session_id: 会话ID
            person_info: 人员信息（可选，陌生人为None）
            visitor_image: 访客照片（初次拍照）
            baseline_image: 基准图片（看护模式激活时提供）
            conn: 连接对象（用于TTS/ASR/拍照服务）
            
        Returns:
            对话结果字典
        """
        logger.bind(tag=TAG).info(
            f"启动统一模式对话 - 设备: {device_id}, 会话: {session_id}, "
            f"访客: {person_info.get('name') if person_info else '陌生人'}, "
            f"看护模式: {'激活' if baseline_image else '未激活'}"
        )
        
        # 保存初次访客照片（用于后续意图总结）
        initial_visitor_image = visitor_image
        
        try:
            # 步骤1: 如果看护模式激活，启动定时拍照任务
            if baseline_image:
                logger.bind(tag=TAG).info(
                    f"看护模式已激活，启动定时拍照任务 - 会话: {session_id}"
                )
                await self.start_photo_capture_task(
                    device_id=device_id,
                    session_id=session_id,
                    conn=conn,
                    interval_seconds=5  # 每5秒拍照一次
                )
            
            # 步骤2: 播放主动问候
            greeting = await self._play_initial_greeting(device_id, person_info, conn)
            
            # 添加问候到对话历史
            self.session_manager.add_dialogue(
                session_id=session_id,
                role="assistant",
                content=greeting
            )
            
            # 步骤3: 对话循环（持续到沉默30秒或PIR无人体）
            dialogue_count = 0
            max_rounds = self.max_dialogue_rounds
            is_first_round = True
            
            while dialogue_count < max_rounds:
                # 检查对话是否应该结束
                should_end = await self.session_manager.check_dialogue_end(
                    session_id=session_id,
                    pir_detected=await self._check_pir_status(device_id)
                )
                
                if should_end:
                    logger.bind(tag=TAG).info(
                        f"对话结束 - 会话: {session_id}, 轮次: {dialogue_count}"
                    )
                    break
                
                # 等待访客回复（ASR识别）
                visitor_response = await self._wait_for_visitor_response(device_id, conn)
                
                if not visitor_response:
                    # 访客沉默，继续检查
                    await asyncio.sleep(1)
                    continue
                
                # 添加访客回复到对话历史
                self.session_manager.add_dialogue(
                    session_id=session_id,
                    role="user",
                    content=visitor_response
                )
                
                # 从PhotoCacheManager获取最新缓存照片
                latest_photo = None
                if baseline_image:
                    latest_photo = self.photo_cache.get_latest_photo(session_id)
                    if not latest_photo:
                        logger.bind(tag=TAG).warning(
                            f"未找到缓存照片，使用初次访客照片 - 会话: {session_id}"
                        )
                        latest_photo = visitor_image
                else:
                    # 看护未激活，使用初次访客照片
                    latest_photo = visitor_image
                
                # 调用VLLM统一分析（传入语音文本+照片）
                dialogue_history = self.session_manager.get_dialogue_history(session_id)
                
                # 转换图片为Base64
                import base64
                latest_photo_base64 = base64.b64encode(latest_photo).decode('utf-8')
                baseline_image_base64 = None
                if baseline_image:
                    baseline_image_base64 = base64.b64encode(baseline_image).decode('utf-8')
                
                vllm_result = await self.vllm.analyze_unified(
                    visitor_image=latest_photo_base64,
                    baseline_image=baseline_image_base64,
                    dialogue_history=dialogue_history,
                    is_first_round=is_first_round
                )
                
                # 播放AI回复（TTS）
                ai_response = vllm_result.get("content", "")
                if ai_response:
                    # 添加AI回复到对话历史
                    self.session_manager.add_dialogue(
                        session_id=session_id,
                        role="assistant",
                        content=ai_response
                    )
                    
                    # 播放AI回复
                    await self._play_ai_response(device_id, ai_response, conn)
                
                # 处理工具调用
                tool_calls = vllm_result.get("tool_calls", [])
                if tool_calls:
                    await self._handle_tool_calls(
                        device_id=device_id,
                        session_id=session_id,
                        tool_calls=tool_calls,
                        conn=conn
                    )
                
                # 检查对话结束条件
                # （已在循环开始时检查）
                
                dialogue_count += 1
                is_first_round = False
            
            # 步骤4: 对话结束后停止定时拍照任务
            if baseline_image:
                logger.bind(tag=TAG).info(
                    f"对话结束，停止定时拍照任务 - 会话: {session_id}"
                )
                await self.stop_photo_capture_task(session_id)
            
            # 步骤5: 对话结束后处理
            dialogue_history = self.session_manager.get_dialogue_history(session_id)
            post_result = await self._post_dialogue_processing(
                device_id=device_id,
                session_id=session_id,
                visitor_image=initial_visitor_image,
                baseline_image=baseline_image,
                dialogue_history=dialogue_history,
                conn=conn
            )
            
            # 步骤6: 清理照片缓存
            if baseline_image:
                logger.bind(tag=TAG).info(
                    f"清理照片缓存 - 会话: {session_id}"
                )
                self.photo_cache.clear_cache(session_id)
            
            logger.bind(tag=TAG).info(
                f"统一模式对话完成 - 会话: {session_id}, 轮次: {dialogue_count}"
            )
            
            return {
                "success": True,
                "action": "intent_recognized",
                "visit_id": post_result.get("visit_id"),
                "intent_summary": post_result.get("intent_summary"),
                "dialogue_count": dialogue_count
            }
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"统一模式对话异常 - 会话: {session_id}, 错误: {e}"
            )
            import traceback
            logger.bind(tag=TAG).error(traceback.format_exc())
            
            # 异常情况下确保停止定时拍照任务
            if baseline_image:
                try:
                    await self.stop_photo_capture_task(session_id)
                except Exception as stop_error:
                    logger.bind(tag=TAG).error(
                        f"停止定时拍照任务失败 - 会话: {session_id}, 错误: {stop_error}"
                    )
            
            # 异常情况下确保清理照片缓存
            if baseline_image:
                try:
                    self.photo_cache.clear_cache(session_id)
                except Exception as clear_error:
                    logger.bind(tag=TAG).error(
                        f"清理照片缓存失败 - 会话: {session_id}, 错误: {clear_error}"
                    )
            
            return {
                "success": False,
                "error": str(e)
            }

    async def _post_dialogue_processing(
        self,
        device_id: str,
        session_id: str,
        visitor_image: bytes,
        baseline_image: Optional[bytes],
        dialogue_history: List[Dict[str, str]],
        conn=None
    ) -> Dict[str, Any]:
        """对话结束后的处理流程
        
        步骤：
        1. 检查快递状态（如果看护激活）
        2. 生成访客意图总结
        3. 保存访问记录
        4. 发送App通知
        5. 清理会话
        
        Args:
            device_id: 设备ID
            session_id: 会话ID
            visitor_image: 访客照片（初次拍照）
            baseline_image: 基准图片（看护模式激活时提供）
            dialogue_history: 完整对话历史
            conn: 连接对象
            
        Returns:
            处理结果字典
        """
        logger.bind(tag=TAG).info(
            f"开始对话结束后处理 - 设备: {device_id}, 会话: {session_id}"
        )
        
        try:
            package_check_result = None
            
            # 步骤1: 检查快递状态（如果看护激活）
            if baseline_image:
                logger.bind(tag=TAG).info(
                    f"看护模式已激活，执行快递状态检查 - 会话: {session_id}"
                )
                
                # 获取最后一张缓存照片
                last_photo = self.photo_cache.get_latest_photo(session_id)
                if not last_photo:
                    logger.bind(tag=TAG).warning(
                        f"未找到缓存照片，重新拍照 - 会话: {session_id}"
                    )
                    last_photo = await self._capture_visitor_photo(device_id, conn)
                
                if last_photo:
                    # 转换图片为Base64
                    import base64
                    current_image_base64 = base64.b64encode(last_photo).decode('utf-8')
                    baseline_image_base64 = base64.b64encode(baseline_image).decode('utf-8')
                    
                    # 调用VLLM检查快递状态
                    package_check_result = await self.vllm.final_package_check(
                        current_image=current_image_base64,
                        baseline_image=baseline_image_base64
                    )
                    
                    logger.bind(tag=TAG).info(
                        f"快递状态检查完成 - 会话: {session_id}, "
                        f"威胁等级: {package_check_result.get('threat_level')}, "
                        f"行为: {package_check_result.get('action')}"
                    )
                    
                    # 如果检测到威胁，保存警报
                    threat_level = package_check_result.get('threat_level', 'low')
                    if threat_level in ['medium', 'high']:
                        logger.bind(tag=TAG).warning(
                            f"检测到快递威胁 - 会话: {session_id}, "
                            f"威胁等级: {threat_level}"
                        )
                        # TODO: 保存警报到数据库
                else:
                    logger.bind(tag=TAG).error(
                        f"无法获取照片进行快递状态检查 - 会话: {session_id}"
                    )
            
            # 步骤2: 生成访客意图总结
            logger.bind(tag=TAG).info(
                f"生成访客意图总结 - 会话: {session_id}"
            )
            
            # 转换访客图片为Base64
            import base64
            visitor_image_base64 = base64.b64encode(visitor_image).decode('utf-8')
            
            intent_summary = await self.vllm.generate_intent_summary(
                visitor_image=visitor_image_base64,
                dialogue_history=dialogue_history
            )
            
            logger.bind(tag=TAG).info(
                f"意图总结生成完成 - 会话: {session_id}, "
                f"意图类型: {intent_summary.get('intent_type')}"
            )
            
            # 步骤3: 保存访问记录
            logger.bind(tag=TAG).info(
                f"保存访问记录 - 会话: {session_id}"
            )
            
            visit_id = await self._save_visit_record(
                session_id=session_id,
                person_info=None,  # TODO: 从会话中获取person_info
                intent_summary=intent_summary,
                dialogue_history=dialogue_history,
                visitor_image=visitor_image,
                package_check_result=package_check_result
            )
            
            # 步骤4: 发送App通知
            logger.bind(tag=TAG).info(
                f"发送App通知 - 会话: {session_id}, visit_id: {visit_id}"
            )
            
            await self.notification_service.notify_visitor_intent(
                visit_id=visit_id,
                session_id=session_id,
                person_info={"person_id": None, "name": "陌生人", "relation_type": "unknown"},
                intent_summary=intent_summary,
                dialogue_text=dialogue_history
            )
            
            # 步骤5: 清理会话
            logger.bind(tag=TAG).info(
                f"清理会话 - 会话: {session_id}"
            )
            # 注意：会话清理由调用方负责
            
            logger.bind(tag=TAG).info(
                f"对话结束后处理完成 - 会话: {session_id}, visit_id: {visit_id}"
            )
            
            return {
                "success": True,
                "visit_id": visit_id,
                "intent_summary": intent_summary,
                "package_check_result": package_check_result
            }
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"对话结束后处理异常 - 会话: {session_id}, 错误: {e}"
            )
            import traceback
            logger.bind(tag=TAG).error(traceback.format_exc())
            
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_tool_calls(
        self,
        device_id: str,
        session_id: str,
        tool_calls: List[Dict[str, Any]],
        conn=None
    ) -> None:
        """处理工具调用
        
        遍历工具调用列表，补充必要参数并执行。
        高威胁时立即播放警告语音。
        
        Args:
            device_id: 设备ID
            session_id: 会话ID
            tool_calls: 工具调用列表
            conn: 连接对象
        """
        logger.bind(tag=TAG).info(
            f"处理工具调用 - 设备: {device_id}, 会话: {session_id}, "
            f"工具数量: {len(tool_calls)}"
        )
        
        for tool_call in tool_calls:
            try:
                tool_name = tool_call.get("name")
                arguments = tool_call.get("arguments", {})
                
                logger.bind(tag=TAG).info(
                    f"执行工具调用 - 工具: {tool_name}, 参数: {arguments}"
                )
                
                # 补充必要参数
                if "device_id" not in arguments:
                    arguments["device_id"] = device_id
                if "session_id" not in arguments:
                    arguments["session_id"] = session_id
                
                # 执行工具调用
                if hasattr(self.vllm, 'doorlock_tools'):
                    result = await self.vllm.doorlock_tools.call_tool(
                        tool_name=tool_name,
                        arguments=arguments
                    )
                    
                    logger.bind(tag=TAG).info(
                        f"工具调用完成 - 工具: {tool_name}, 结果: {result}"
                    )
                    
                    # 高威胁特殊处理：立即播放警告
                    if tool_name == "report_package_status":
                        threat_level = arguments.get("threat_level", "low")
                        if threat_level == "high":
                            logger.bind(tag=TAG).warning(
                                f"检测到高威胁，播放警告语音 - 会话: {session_id}"
                            )
                            
                            warning_message = "警告！检测到可疑行为，请立即停止！"
                            await self._play_ai_response(
                                device_id=device_id,
                                response=warning_message,
                                conn=conn
                            )
                else:
                    logger.bind(tag=TAG).warning(
                        f"VLLM提供者未配置doorlock_tools，跳过工具调用 - 工具: {tool_name}"
                    )
                
            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"工具调用执行异常 - 工具: {tool_call.get('name')}, 错误: {e}"
                )
                import traceback
                logger.bind(tag=TAG).error(traceback.format_exc())
                # 继续处理下一个工具调用
    
    async def _save_visit_record(
        self,
        session_id: str,
        person_info: Optional[Dict[str, Any]],
        intent_summary: Dict[str, Any],
        dialogue_history: List[Dict[str, str]],
        visitor_image: bytes,
        package_check_result: Optional[Dict[str, Any]] = None
    ) -> int:
        """保存访问记录到数据库
        
        Args:
            session_id: 会话ID
            person_info: 人员信息
            intent_summary: 意图总结
            dialogue_history: 对话历史
            visitor_image: 访客照片
            package_check_result: 快递检查结果（可选）
            
        Returns:
            visit_id
        """
        try:
            # 保存访客意图记录
            from core.providers.doorlock.models import VisitorIntent
            
            # 合并意图总结和快递检查结果
            full_summary = intent_summary.copy()
            if package_check_result:
                full_summary["package_check"] = package_check_result
            
            intent = VisitorIntent(
                visit_id=None,  # TODO: 关联visit_records表
                session_id=session_id,
                person_id=person_info.get("person_id") if person_info else None,
                intent_type=intent_summary.get("intent_type", "other"),
                intent_summary=full_summary,
                dialogue_history=dialogue_history
            )
            
            visit_id = await self.db.save_visitor_intent(intent)
            
            logger.bind(tag=TAG).info(
                f"访问记录已保存 - visit_id: {visit_id}, session_id: {session_id}"
            )
            
            return visit_id
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"保存访问记录异常: {e}")
            return 0
