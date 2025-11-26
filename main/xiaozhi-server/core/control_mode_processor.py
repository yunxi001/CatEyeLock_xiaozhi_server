import asyncio
import json
import time
import queue
from typing import Dict, Any, Optional, Callable
from config.logger import setup_logging
from core.handle.textHandle import handleTextMessage
from core.utils.dialogue import Message, Dialogue
from core.providers.tts.dto.dto import TTSMessageDTO, ContentType, SentenceType
from core.providers.tools.unified_tool_handler import UnifiedToolHandler
from core.utils.prompt_manager import PromptManager
from core.utils.voiceprint_provider import VoiceprintProvider

TAG = __name__


class ControlModeProcessor:
    """控制模式处理器 - 封装AI对话功能，支持暂停和恢复"""
    
    def __init__(self, connection_handler, config: Dict[str, Any]):
        self.conn_handler = connection_handler  # ConnectionHandler实例的引用
        self.config = config
        self.logger = setup_logging()
        
        # AI组件引用
        self.vad = None
        self.asr = None
        self.tts = None
        self.llm = None
        self.memory = None
        self.intent = None
        
        # 初始化状态
        self._is_active = False  # 当前是否活跃
        self._is_paused = False  # 是否暂停
        
        # 保存原始组件引用
        self._original_components = {}
        
        # 对话和状态相关
        self.dialogue = None
        self.llm_finish_task = True
        self.sentence_id = None
        self.tts_MessageText = ""
        
        # 原始状态备份
        self._original_states = {}
        
        # 初始化时备份原始组件
        self._backup_original_components()
        
    def _backup_original_components(self):
        """备份原始组件引用"""
        if self.conn_handler:
            self._original_components = {
                'vad': self.conn_handler.vad,
                'asr': self.conn_handler.asr,
                'tts': self.conn_handler.tts,
                'llm': self.conn_handler.llm,
                'memory': self.conn_handler.memory,
                'intent': self.conn_handler.intent,
            }
            
            self._original_states = {
                'dialogue': self.conn_handler.dialogue,
                'llm_finish_task': self.conn_handler.llm_finish_task,
                'sentence_id': self.conn_handler.sentence_id,
                'tts_MessageText': self.conn_handler.tts_MessageText,
                'func_handler': getattr(self.conn_handler, 'func_handler', None)
            }
    
    def activate(self):
        """激活控制模式 - 恢复AI组件"""
        if self._is_active:
            return True
            
        try:
            # 恢复原始组件引用
            self._restore_components()
            
            # 恢复原始状态
            self._restore_states()
            
            # 重新初始化需要的资源
            self._reinitialize_resources()
            
            self._is_active = True
            self._is_paused = False
            
            self.logger.bind(tag=TAG).info("控制模式已激活")
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"激活控制模式失败: {str(e)}")
            return False
    
    def deactivate(self):
        """停用控制模式 - 暂停AI组件"""
        if not self._is_active:
            return True
            
        try:
            # 保存当前状态
            self._save_current_states()
            
            # 暂停AI组件
            self._pause_components()
            
            self._is_active = False
            self._is_paused = True
            
            self.logger.bind(tag=TAG).info("控制模式已停用")
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"停用控制模式失败: {str(e)}")
            return False
    
    def pause(self):
        """暂停控制模式功能"""
        if not self._is_active or self._is_paused:
            return True
            
        try:
            # 保存当前状态
            self._save_current_states()
            
            # 暂停AI组件
            self._pause_components()
            
            self._is_paused = True
            
            self.logger.bind(tag=TAG).info("控制模式已暂停")
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"暂停控制模式失败: {str(e)}")
            return False
    
    def resume(self):
        """恢复控制模式功能"""
        if not self._is_active or not self._is_paused:
            return True
            
        try:
            # 恢复组件
            self._restore_components()
            
            # 恢复状态
            self._restore_states()
            
            # 重新初始化资源
            self._reinitialize_resources()
            
            self._is_paused = False
            
            self.logger.bind(tag=TAG).info("控制模式已恢复")
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"恢复控制模式失败: {str(e)}")
            return False
    
    def _save_current_states(self):
        """保存当前状态"""
        try:
            if self.conn_handler:
                self._original_states = {
                    'dialogue': self.conn_handler.dialogue,
                    'llm_finish_task': self.conn_handler.llm_finish_task,
                    'sentence_id': self.conn_handler.sentence_id,
                    'tts_MessageText': getattr(self.conn_handler, 'tts_MessageText', ""),
                    'func_handler': getattr(self.conn_handler, 'func_handler', None),
                    'client_abort': getattr(self.conn_handler, 'client_abort', False),
                    'client_is_speaking': getattr(self.conn_handler, 'client_is_speaking', False),
                    'client_listen_mode': getattr(self.conn_handler, 'client_listen_mode', 'auto'),
                }
            self.logger.bind(tag=TAG).debug("已保存当前状态")
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"保存当前状态失败: {str(e)}")
    
    def _restore_states(self):
        """恢复之前保存的状态"""
        try:
            if self.conn_handler and self._original_states:
                # 恢复对话状态
                if 'dialogue' in self._original_states and self._original_states['dialogue']:
                    self.conn_handler.dialogue = self._original_states['dialogue']
                
                # 恢复LLM状态
                if 'llm_finish_task' in self._original_states:
                    self.conn_handler.llm_finish_task = self._original_states['llm_finish_task']
                
                # 恢复句子ID
                if 'sentence_id' in self._original_states:
                    self.conn_handler.sentence_id = self._original_states['sentence_id']
                
                # 恢复TTS文本
                if 'tts_MessageText' in self._original_states:
                    self.conn_handler.tts_MessageText = self._original_states['tts_MessageText']
                
                # 恢复客户端状态
                if 'client_abort' in self._original_states:
                    self.conn_handler.client_abort = self._original_states['client_abort']
                if 'client_is_speaking' in self._original_states:
                    self.conn_handler.client_is_speaking = self._original_states['client_is_speaking']
                if 'client_listen_mode' in self._original_states:
                    self.conn_handler.client_listen_mode = self._original_states['client_listen_mode']
                
                # 恢复工具处理器
                if 'func_handler' in self._original_states:
                    self.conn_handler.func_handler = self._original_states['func_handler']
            
            self.logger.bind(tag=TAG).debug("已恢复之前保存的状态")
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"恢复状态失败: {str(e)}")
    
    def _pause_components(self):
        """暂停AI组件"""
        try:
            # 暂停ASR（语音识别）
            if self.conn_handler and self.conn_handler.asr:
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.conn_handler.asr.close_audio_channels(self.conn_handler), 
                        self.conn_handler.loop
                    ).result(timeout=2)  # 2秒超时
                except Exception as e:
                    self.logger.bind(tag=TAG).warning(f"关闭ASR通道失败: {str(e)}")
            
            # 暂停TTS（语音合成）  
            if self.conn_handler and self.conn_handler.tts:
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.conn_handler.tts.close_audio_channels(self.conn_handler), 
                        self.conn_handler.loop
                    ).result(timeout=2)  # 2秒超时
                except Exception as e:
                    self.logger.bind(tag=TAG).warning(f"关闭TTS通道失败: {str(e)}")
            
            # 暂停LLM任务
            if self.conn_handler:
                self.conn_handler.llm_finish_task = True  # 停止当前LLM任务
            
            # 备份当前组件引用
            self._original_components = {
                'vad': self.conn_handler.vad if self.conn_handler else None,
                'asr': self.conn_handler.asr if self.conn_handler else None,
                'tts': self.conn_handler.tts if self.conn_handler else None,
                'llm': self.conn_handler.llm if self.conn_handler else None,
                'memory': self.conn_handler.memory if self.conn_handler else None,
                'intent': self.conn_handler.intent if self.conn_handler else None,
            }
            
            # 临时清空组件引用，防止被使用
            if self.conn_handler:
                self.conn_handler.asr = None
                self.conn_handler.tts = None
                self.conn_handler.vad = None
            
            self.logger.bind(tag=TAG).info("AI组件已暂停")
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"暂停组件失败: {str(e)}")
    
    def _restore_components(self):
        """恢复AI组件"""
        try:
            if not self.conn_handler:
                return
            
            # 恢复组件引用
            if 'vad' in self._original_components:
                self.conn_handler.vad = self._original_components['vad']
            if 'asr' in self._original_components:
                self.conn_handler.asr = self._original_components['asr']
            if 'tts' in self._original_components:
                self.conn_handler.tts = self._original_components['tts']
            if 'llm' in self._original_components:
                self.conn_handler.llm = self._original_components['llm']
            if 'memory' in self._original_components:
                self.conn_handler.memory = self._original_components['memory']
            if 'intent' in self._original_components:
                self.conn_handler.intent = self._original_components['intent']
            
            # 重新打开音频通道
            if self.conn_handler.asr:
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.conn_handler.asr.open_audio_channels(self.conn_handler), 
                        self.conn_handler.loop
                    )
                except Exception as e:
                    self.logger.bind(tag=TAG).error(f"打开ASR通道失败: {str(e)}")
            
            if self.conn_handler.tts:
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.conn_handler.tts.open_audio_channels(self.conn_handler), 
                        self.conn_handler.loop
                    )
                except Exception as e:
                    self.logger.bind(tag=TAG).error(f"打开TTS通道失败: {str(e)}")
            
            self.logger.bind(tag=TAG).info("AI组件已恢复")
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"恢复组件失败: {str(e)}")
    
    def _reinitialize_resources(self):
        """重新初始化需要的资源"""
        try:
            if not self.conn_handler:
                return
            
            # 重新初始化工具处理器
            if self.conn_handler.intent:
                self.conn_handler.func_handler = UnifiedToolHandler(self.conn_handler)
                
                # 异步初始化工具处理器
                if hasattr(self.conn_handler, "loop") and self.conn_handler.loop:
                    asyncio.run_coroutine_threadsafe(
                        self.conn_handler.func_handler._initialize(), 
                        self.conn_handler.loop
                    )
            
            # 重新初始化提示词管理器（如果不存在）
            if not hasattr(self.conn_handler, 'prompt_manager') or self.conn_handler.prompt_manager is None:
                self.conn_handler.prompt_manager = PromptManager(self.conn_handler.config, self.logger)
            
            self.logger.bind(tag=TAG).debug("资源已重新初始化")
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"重新初始化资源失败: {str(e)}")
    
    async def handle_text_message(self, message: str):
        """处理文本消息"""
        if not self._is_active or self._is_paused:
            self.logger.bind(tag=TAG).warning("控制模式未激活或已暂停，无法处理文本消息")
            return False
            
        try:
            # 调用原始的文本消息处理函数
            await handleTextMessage(self.conn_handler, message)
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"处理文本消息失败: {str(e)}")
            return False
    
    async def handle_audio_data(self, audio_data: bytes):
        """处理音频数据"""
        if not self._is_active or self._is_paused:
            self.logger.bind(tag=TAG).warning("控制模式未激活或已暂停，无法处理音频数据")
            return False
            
        try:
            # 如果ASR组件存在，将音频数据放入ASR队列
            if self.conn_handler.asr:
                self.conn_handler.asr_audio_queue.put(audio_data)
                return True
            else:
                self.logger.bind(tag=TAG).warning("ASR组件不可用，无法处理音频数据")
                return False
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"处理音频数据失败: {str(e)}")
            return False
    
    def is_active(self) -> bool:
        """检查是否激活"""
        return self._is_active
    
    def is_paused(self) -> bool:
        """检查是否暂停"""
        return self._is_paused
    
    def get_status(self) -> Dict[str, Any]:
        """获取处理器状态"""
        return {
            "is_active": self._is_active,
            "is_paused": self._is_paused,
            "has_original_components": bool(self._original_components),
            "has_saved_states": bool(self._original_states),
        }
    
    def chat(self, query: str, depth: int = 0):
        """执行对话功能（封装原始chat方法）"""
        if not self._is_active or self._is_paused:
            self.logger.bind(tag=TAG).warning("控制模式未激活或已暂停，无法执行对话")
            return None
            
        try:
            # 调用ConnectionHandler的原始chat方法
            return self.conn_handler.chat(query, depth)
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"对话处理失败: {str(e)}")
            return None