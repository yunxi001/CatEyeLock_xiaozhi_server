import asyncio
import json
import time
from enum import Enum
from typing import Dict, Any, Optional, Callable
from config.logger import setup_logging

TAG = __name__


class ModeType(Enum):
    """模式类型枚举"""
    CONTROL = "control"  # 控制模式：AI对话、控制命令
    MEDIA = "media"      # 音视频模式：仅处理音视频流


class ModeState:
    """模式状态类，用于保存和恢复模式状态"""
    def __init__(self):
        self.mode: ModeType = ModeType.CONTROL
        self.last_switch_time: float = time.time()
        self.session_data: Dict[str, Any] = {}
        self.ai_context: Dict[str, Any] = {}
        self.media_params: Dict[str, Any] = {}
        self.device_status: Dict[str, Any] = {}


class ModeSwitcher:
    """模式切换管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = setup_logging()
        self._current_mode = ModeType.CONTROL
        self._last_switch_time = time.time()
        self._mode_state = ModeState()
        self._mode_state.mode = self._current_mode
        self._connection_handler = None
        
        # 延迟初始化的组件，用于状态保存和恢复
        self._component_backup = {}
        
        # 验证和配置相关参数
        self._enabled = config.get("audio_video_stream", {}).get("enabled", False)
        self._max_switch_frequency = config.get("audio_video_stream", {}).get("max_switch_frequency", 5)  # 每分钟最大切换次数
        self._switch_log = []  # 记录切换日志，用于频率控制
        
    def set_connection_handler(self, conn_handler):
        """设置连接处理器引用"""
        self._connection_handler = conn_handler
        self._mode_state.session_data = {
            'device_id': getattr(conn_handler, 'device_id', None),
            'client_ip': getattr(conn_handler, 'client_ip', None),
            'session_id': getattr(conn_handler, 'session_id', None)
        }

    def get_current_mode(self) -> ModeType:
        """获取当前模式"""
        return self._current_mode

    def is_media_mode(self) -> bool:
        """检查是否为音视频模式"""
        return self._current_mode == ModeType.MEDIA

    def is_control_mode(self) -> bool:
        """检查是否为控制模式"""
        return self._current_mode == ModeType.CONTROL

    async def request_mode_switch(self, target_mode: str, device_id: str = None, 
                                 auth_token: str = None) -> Dict[str, Any]:
        """请求切换模式"""
        try:
            # 验证目标模式
            if target_mode not in [ModeType.CONTROL.value, ModeType.MEDIA.value]:
                return {
                    "success": False,
                    "error": f"无效的模式: {target_mode}",
                    "request_id": "unknown"
                }
            
            target_mode_enum = ModeType(target_mode)
            
            # 权限验证
            if not await self._verify_permissions(device_id, auth_token, target_mode_enum):
                return {
                    "success": False,
                    "error": "权限验证失败",
                    "request_id": "unknown"
                }
            
            # 频率控制验证
            if not self._check_switch_frequency():
                return {
                    "success": False,
                    "error": "模式切换过于频繁",
                    "request_id": "unknown"
                }
            
            # 执行模式切换
            success = await self._perform_mode_switch(target_mode_enum)
            
            if success:
                return {
                    "success": True,
                    "message": f"成功切换到{target_mode}模式",
                    "current_mode": self._current_mode.value
                }
            else:
                return {
                    "success": False,
                    "error": "模式切换失败",
                    "current_mode": self._current_mode.value
                }
                
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"模式切换请求处理失败: {str(e)}")
            return {
                "success": False,
                "error": f"模式切换请求处理失败: {str(e)}",
                "current_mode": self._current_mode.value
            }

    async def _verify_permissions(self, device_id: str, auth_token: str, target_mode: ModeType) -> bool:
        """验证切换权限"""
        try:
            # 如果没有连接处理器，无法验证
            if not self._connection_handler:
                return False
            
            # 基本验证：确保请求来自同一设备
            if device_id and self._connection_handler.device_id != device_id:
                self.logger.bind(tag=TAG).warning(f"设备ID不匹配: {device_id} vs {self._connection_handler.device_id}")
                return False
            
            # 可以在这里添加更多的权限验证逻辑
            # 例如检查JWT令牌、设备白名单等
            if self._connection_handler.server and self._connection_handler.server.auth_enable:
                # 验证认证令牌
                headers = getattr(self._connection_handler, 'headers', {})
                current_token = headers.get('authorization', '').replace('Bearer ', '')
                
                if auth_token and auth_token != current_token:
                    self.logger.bind(tag=TAG).warning("认证令牌验证失败")
                    return False
            
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"权限验证异常: {str(e)}")
            return False

    def _check_switch_frequency(self) -> bool:
        """检查模式切换频率，防止过于频繁的切换"""
        current_time = time.time()
        
        # 清理超过1分钟的日志
        self._switch_log = [timestamp for timestamp in self._switch_log 
                           if current_time - timestamp <= 60]
        
        # 检查是否超过频率限制
        if len(self._switch_log) >= self._max_switch_frequency:
            self.logger.bind(tag=TAG).warning(f"模式切换过于频繁，超过限制: {self._max_switch_frequency}/分钟")
            return False
        
        # 记录当前切换时间
        self._switch_log.append(current_time)
        return True

    async def _perform_mode_switch(self, target_mode: ModeType) -> bool:
        """执行模式切换"""
        try:
            if self._current_mode == target_mode:
                self.logger.bind(tag=TAG).info(f"已经在{target_mode.value}模式，无需切换")
                return True
            
            self.logger.bind(tag=TAG).info(f"开始切换模式: {self._current_mode.value} -> {target_mode.value}")
            
            # 保存当前状态
            if self._current_mode == ModeType.CONTROL:
                await self._save_control_mode_state()
            elif self._current_mode == ModeType.MEDIA:
                await self._save_media_mode_state()
            
            # 执行模式切换前的操作
            if target_mode == ModeType.MEDIA:
                success = await self._prepare_for_media_mode()
            else:  # CONTROL mode
                success = await self._prepare_for_control_mode()
            
            if not success:
                self.logger.bind(tag=TAG).error(f"准备{target_mode.value}模式失败")
                return False
            
            # 更新模式状态
            self._current_mode = target_mode
            self._last_switch_time = time.time()
            self._mode_state.mode = target_mode
            self._mode_state.last_switch_time = self._last_switch_time
            
            # 执行模式切换后的操作
            if target_mode == ModeType.MEDIA:
                await self._on_enter_media_mode()
            else:  # CONTROL mode
                await self._on_enter_control_mode()
            
            self.logger.bind(tag=TAG).info(f"成功切换到{target_mode.value}模式")
            return True
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"模式切换执行失败: {str(e)}")
            # 尝试恢复到原来的模式
            try:
                revert_success = await self._perform_mode_switch(self._current_mode)
                if not revert_success:
                    self.logger.bind(tag=TAG).error("模式切换失败后恢复原模式也失败")
            except Exception:
                self.logger.bind(tag=TAG).error("模式切换失败后无法恢复")
            return False

    async def _save_control_mode_state(self):
        """保存控制模式状态"""
        try:
            if not self._connection_handler:
                return
                
            # 保存AI对话上下文
            self._mode_state.ai_context = {
                'dialogue': getattr(self._connection_handler, 'dialogue', None),
                'llm_finish_task': getattr(self._connection_handler, 'llm_finish_task', True),
                'sentence_id': getattr(self._connection_handler, 'sentence_id', None),
                'tts_MessageText': getattr(self._connection_handler, 'tts_MessageText', ""),
            }
            
            # 保存设备状态
            self._mode_state.device_status = {
                'client_abort': getattr(self._connection_handler, 'client_abort', False),
                'client_is_speaking': getattr(self._connection_handler, 'client_is_speaking', False),
                'client_listen_mode': getattr(self._connection_handler, 'client_listen_mode', 'auto'),
            }
            
            self.logger.bind(tag=TAG).debug("已保存控制模式状态")
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"保存控制模式状态失败: {str(e)}")

    async def _save_media_mode_state(self):
        """保存音视频模式状态"""
        try:
            if not self._connection_handler:
                return
                
            # 保存音视频参数
            self._mode_state.media_params = {
                # 保存音视频流的相关参数
            }
            
            self.logger.bind(tag=TAG).debug("已保存音视频模式状态")
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"保存音视频模式状态失败: {str(e)}")

    async def _prepare_for_media_mode(self) -> bool:
        """准备进入音视频模式"""
        try:
            if not self._connection_handler:
                return False
            
            # 暂停AI相关组件
            await self._pause_ai_components()
            
            # 清理相关队列
            self._clear_ai_queues()
            
            # 重置相关状态
            self._reset_ai_states()
            
            self.logger.bind(tag=TAG).info("已准备好进入音视频模式")
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"准备音视频模式失败: {str(e)}")
            return False

    async def _prepare_for_control_mode(self) -> bool:
        """准备进入控制模式"""
        try:
            if not self._connection_handler:
                return False
            
            # 恢复AI相关组件
            await self._resume_ai_components()
            
            self.logger.bind(tag=TAG).info("已准备好进入控制模式")
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"准备控制模式失败: {str(e)}")
            return False

    async def _pause_ai_components(self):
        """暂停AI组件"""
        if not self._connection_handler:
            return
        
        try:
            # 暂停ASR（语音识别）
            if hasattr(self._connection_handler, 'asr') and self._connection_handler.asr:
                try:
                    await self._connection_handler.asr.close_audio_channels(self._connection_handler)
                except Exception as e:
                    self.logger.bind(tag=TAG).warning(f"关闭ASR通道失败: {str(e)}")
            
            # 暂停TTS（语音合成）
            if hasattr(self._connection_handler, 'tts') and self._connection_handler.tts:
                try:
                    await self._connection_handler.tts.close_audio_channels(self._connection_handler)
                except Exception as e:
                    self.logger.bind(tag=TAG).warning(f"关闭TTS通道失败: {str(e)}")
            
            # 暂停VAD（语音活动检测）
            if hasattr(self._connection_handler, 'vad') and self._connection_handler.vad:
                # VAD通常不需要特殊处理，但可添加必要的逻辑
                pass
            
            # 暂停LLM任务
            if hasattr(self._connection_handler, 'llm_finish_task'):
                self._connection_handler.llm_finish_task = True  # 停止当前LLM任务
            
            # 备份组件引用，以便后续恢复
            self._component_backup['asr'] = self._connection_handler.asr
            self._component_backup['tts'] = self._connection_handler.tts
            self._component_backup['vad'] = self._connection_handler.vad
            
            # 临时清空组件引用，防止在音视频模式下被使用
            self._connection_handler.asr = None
            self._connection_handler.tts = None
            self._connection_handler.vad = None
            
            self.logger.bind(tag=TAG).info("已暂停AI组件")
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"暂停AI组件时出错: {str(e)}")

    async def _resume_ai_components(self):
        """恢复AI组件"""
        if not self._connection_handler:
            return
        
        try:
            # 恢复组件引用
            if 'asr' in self._component_backup:
                self._connection_handler.asr = self._component_backup['asr']
            if 'tts' in self._component_backup:
                self._connection_handler.tts = self._component_backup['tts']
            if 'vad' in self._component_backup:
                self._connection_handler.vad = self._component_backup['vad']
            
            # 重新初始化组件
            if self._connection_handler.asr:
                await self._connection_handler.asr.open_audio_channels(self._connection_handler)
            if self._connection_handler.tts:
                await self._connection_handler.tts.open_audio_channels(self._connection_handler)
            
            # 恢复之前保存的状态
            if hasattr(self._connection_handler, 'dialogue') and self._mode_state.ai_context.get('dialogue'):
                self._connection_handler.dialogue = self._mode_state.ai_context['dialogue']
            
            self._connection_handler.llm_finish_task = self._mode_state.ai_context.get('llm_finish_task', True)
            self._connection_handler.sentence_id = self._mode_state.ai_context.get('sentence_id')
            self._connection_handler.tts_MessageText = self._mode_state.ai_context.get('tts_MessageText', "")
            
            # 恢复设备状态
            self._connection_handler.client_abort = self._mode_state.device_status.get('client_abort', False)
            self._connection_handler.client_is_speaking = self._mode_state.device_status.get('client_is_speaking', False)
            self._connection_handler.client_listen_mode = self._mode_state.device_status.get('client_listen_mode', 'auto')
            
            self.logger.bind(tag=TAG).info("已恢复AI组件")
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"恢复AI组件时出错: {str(e)}")

    def _clear_ai_queues(self):
        """清理AI相关队列"""
        if not self._connection_handler or not self._connection_handler.tts:
            return
        
        try:
            # 清空TTS文本队列
            import queue
            tts_text_queue = getattr(self._connection_handler.tts, 'tts_text_queue', None)
            if tts_text_queue:
                while not tts_text_queue.empty():
                    try:
                        tts_text_queue.get_nowait()
                    except queue.Empty:
                        break
            
            # 清空TTS音频队列
            tts_audio_queue = getattr(self._connection_handler.tts, 'tts_audio_queue', None)
            if tts_audio_queue:
                while not tts_audio_queue.empty():
                    try:
                        tts_audio_queue.get_nowait()
                    except queue.Empty:
                        break
                        
            # 清空ASR音频队列
            asr_audio_queue = getattr(self._connection_handler, 'asr_audio_queue', None)
            if asr_audio_queue:
                while not asr_audio_queue.empty():
                    try:
                        asr_audio_queue.get_nowait()
                    except queue.Empty:
                        break
                        
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"清理AI队列时出错: {str(e)}")

    def _reset_ai_states(self):
        """重置AI相关状态"""
        if not self._connection_handler:
            return
        
        try:
            # 重置对话相关状态
            self._connection_handler.llm_finish_task = True
            self._connection_handler.sentence_id = None
            self._connection_handler.tts_MessageText = ""
            
            # 重置客户端状态
            self._connection_handler.client_abort = False
            self._connection_handler.client_is_speaking = False
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"重置AI状态时出错: {str(e)}")

    async def _on_enter_media_mode(self):
        """进入音视频模式后的操作"""
        # 可以在这里添加特定于音视频模式的初始化逻辑
        pass

    async def _on_enter_control_mode(self):
        """进入控制模式后的操作"""
        # 可以在这里添加特定于控制模式的初始化逻辑
        pass

    def get_mode_status(self) -> Dict[str, Any]:
        """获取模式状态信息"""
        return {
            "current_mode": self._current_mode.value,
            "last_switch_time": self._last_switch_time,
            "enabled": self._enabled,
            "session_data": self._mode_state.session_data,
            "is_media_mode": self.is_media_mode(),
            "is_control_mode": self.is_control_mode(),
            "switch_frequency_count": len([t for t in self._switch_log if time.time() - t <= 60])
        }