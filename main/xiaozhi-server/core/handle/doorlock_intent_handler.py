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

TAG = "DoorlockIntentHandler"


class DoorlockIntentHandler:
    """门锁意图识别对话处理器"""
    
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
        notification_service = NotificationService(config, logger_instance)
        doorlock_database = DoorlockDatabase(config)
        
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
            config=doorlock_config
        )


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
        
        logger.bind(tag=TAG).info(
            f"意图识别处理器初始化完成: timeout={self.dialogue_timeout}s, "
            f"max_rounds={self.max_dialogue_rounds}"
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
                    # 有权限：播放欢迎词并开门
                    logger.bind(tag=TAG).info(
                        f"访客有开门权限 - 人员: {person.name} (ID: {person.id})"
                    )
                    
                    await self.greeting_handler.play_welcome_greeting(
                        device_id=device_id,
                        person_id=person.id,
                        person_name=person.name,
                        conn=conn
                    )
                    
                    # TODO: 触发开门操作
                    
                    # 清除会话
                    await self.session_manager.cleanup_session(session_id)
                    
                    return {
                        "success": True,
                        "action": "door_opened",
                        "person_id": person.id,
                        "person_name": person.name
                    }
            
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
        """拍摄访客照片
        
        Args:
            device_id: 设备ID
            conn: 连接对象
            
        Returns:
            JPEG图片数据，失败返回None
        """
        try:
            # TODO: 调用ESP32拍照功能
            # 这里需要通过MCP协议调用ESP32的capture_image工具
            logger.bind(tag=TAG).info(f"拍摄访客照片 - 设备: {device_id}")
            
            # 暂时返回None，表示需要实现
            return None
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"拍摄访客照片失败: {e}")
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
        person_info: Optional[Dict[str, Any]]
    ) -> str:
        """播放主动问候
        
        Args:
            device_id: 设备ID
            person_info: 人员信息
            
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
    
    async def _wait_for_visitor_response(self, device_id: str) -> Optional[str]:
        """等待访客回复
        
        Args:
            device_id: 设备ID
            
        Returns:
            访客回复文本，如果没有回复返回None
        """
        # TODO: 集成ASR服务，等待语音识别结果
        # 这里简化处理，返回None表示没有回复
        await asyncio.sleep(1)
        return None
    
    async def _play_ai_response(self, device_id: str, response: str):
        """播放AI回复
        
        Args:
            device_id: 设备ID
            response: 回复文本
        """
        logger.bind(tag=TAG).debug(f"播放AI回复 - 设备: {device_id}, 内容: {response}")
        
        # TODO: 调用TTS服务播放语音
    
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
