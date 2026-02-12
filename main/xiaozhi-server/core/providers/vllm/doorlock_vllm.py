"""
门锁AI专用VLLM提供者

扩展标准VLLM提供者，支持：
- 工具函数调用
- 多图片输入（单图片用于意图识别，双图片用于看护监控）
- 提示词动态加载
- Token消耗统计
- 性能监控
"""
import time
import yaml
import openai
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

from .base import VLLMProviderBase
from ..doorlock.doorlock_tools import DoorlockTools

TAG = "DoorlockVLLM"


class DoorlockVLLMProvider(VLLMProviderBase):
    """门锁AI专用VLLM提供者"""
    
    def __init__(self, config: dict, logger_instance=None):
        """初始化VLLM提供者
        
        Args:
            config: 系统配置字典
            logger_instance: 日志实例（可选）
        """
        self.logger = logger_instance or logger
        
        # 从系统配置获取选中的 VLLM 配置
        selected_vllm = config.get("selected_module", {}).get("VLLM", "")
        if not selected_vllm:
            raise ValueError("系统未配置 VLLM 模块，请在 config.yaml 的 selected_module.VLLM 中指定")
        
        vllm_configs = config.get("VLLM", {})
        if selected_vllm not in vllm_configs:
            raise ValueError(f"找不到 VLLM 配置: {selected_vllm}")
        
        vllm_config = vllm_configs[selected_vllm]
        
        # 提取 VLLM 配置参数（与 openai.py 保持一致）
        self.model_name = vllm_config.get("model_name")
        self.api_key = vllm_config.get("api_key")
        # 兼容 base_url 和 url 两种写法
        self.base_url = vllm_config.get("base_url") or vllm_config.get("url")
        
        # 参数配置（与 openai.py 保持一致的处理方式）
        param_defaults = {
            "max_tokens": (500, int),
            "temperature": (0.7, lambda x: round(float(x), 1)),
            "top_p": (1.0, lambda x: round(float(x), 1)),
        }
        
        for param, (default, converter) in param_defaults.items():
            value = vllm_config.get(param)
            try:
                setattr(
                    self,
                    param,
                    converter(value) if value not in (None, "") else default,
                )
            except (ValueError, TypeError):
                setattr(self, param, default)
        
        # Token使用量警告阈值（从门锁独立配置读取）
        doorlock_config_path = Path(__file__).parent.parent.parent.parent / "config" / "doorlock_config.yaml"
        doorlock_config = {}
        if doorlock_config_path.exists():
            try:
                from ruamel.yaml import YAML
                yaml = YAML()
                with open(doorlock_config_path, 'r', encoding='utf-8') as f:
                    doorlock_config = yaml.load(f)
            except Exception as e:
                self.logger.bind(tag=TAG).warning(f"加载门锁配置失败: {e}")
        
        performance_config = doorlock_config.get("performance", {})
        self.max_token_usage_ratio = float(
            performance_config.get("max_token_usage_ratio", 0.8)
        )
        
        # 加载提示词配置
        self.prompts = self._load_prompts()
        
        # 工具函数（延迟初始化）
        self.doorlock_tools = None
        
        # 初始化OpenAI客户端（与 openai.py 保持一致）
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        self.logger.bind(tag=TAG).info(
            f"门锁VLLM提供者初始化完成: 使用系统配置 {selected_vllm}, "
            f"model={self.model_name}, max_tokens={self.max_tokens}, "
            f"prompts_loaded={len(self.prompts)}"
        )
    
    def set_doorlock_tools(self, doorlock_tools: DoorlockTools):
        """设置门锁工具函数
        
        Args:
            doorlock_tools: 门锁工具函数实例
        """
        self.doorlock_tools = doorlock_tools
        self.logger.bind(tag=TAG).info("门锁工具函数已设置")
    
    def _load_prompts(self) -> Dict[str, str]:
        """从配置文件加载提示词
        
        Returns:
            提示词字典
        """
        try:
            prompts_path = Path("config/doorlock_prompts.yaml")
            
            if not prompts_path.exists():
                self.logger.bind(tag=TAG).warning(
                    f"提示词配置文件不存在: {prompts_path}"
                )
                return {}
            
            with open(prompts_path, 'r', encoding='utf-8') as f:
                prompts = yaml.safe_load(f)
            
            self.logger.bind(tag=TAG).info(
                f"提示词配置加载成功: {len(prompts)} 个提示词"
            )
            
            return prompts
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"加载提示词配置失败: {e}")
            return {}
    
    def get_prompt(self, prompt_name: str) -> str:
        """获取指定的提示词
        
        Args:
            prompt_name: 提示词名称
            
        Returns:
            提示词文本
        """
        return self.prompts.get(prompt_name, "")
    
    def response(self, question: str, base64_image: str) -> str:
        """标准VLLM响应（兼容基类接口）
        
        Args:
            question: 问题文本
            base64_image: Base64编码的图片
            
        Returns:
            AI响应文本
        """
        result = self.analyze_with_tools(
            question=question,
            images=[base64_image],
            dialogue_history=[],
            system_prompt=None
        )
        return result.get("content", "")
    
    def analyze_with_tools(
        self,
        question: str,
        images: List[str],
        dialogue_history: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """使用工具函数进行分析
        
        Args:
            question: 问题文本
            images: Base64编码的图片列表（1张用于意图识别，2张用于看护监控）
            dialogue_history: 对话历史
            system_prompt: 系统提示词（可选）
            
        Returns:
            分析结果字典，包含 content, tool_calls, token_usage, response_time
        """
        start_time = time.time()
        
        try:
            # 构建消息
            messages = self._build_messages(
                question=question,
                images=images,
                dialogue_history=dialogue_history,
                system_prompt=system_prompt
            )
            
            # 准备工具Schema
            tools = None
            if self.doorlock_tools:
                tools = DoorlockTools.get_tools_schema()
            
            # 调用VLLM
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools if tools else None,
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=self.max_tokens,
                stream=False
            )
            
            # 计算响应时间
            response_time = time.time() - start_time
            
            # 提取响应内容
            message = response.choices[0].message
            content = message.content or ""
            tool_calls = []
            
            # 解析工具调用
            if hasattr(message, 'tool_calls') and message.tool_calls:
                import json
                for tool_call in message.tool_calls:
                    tool_calls.append({
                        "id": tool_call.id,
                        "name": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments)  # JSON字符串转字典
                    })
            
            # Token统计
            token_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            # Token使用量警告
            usage_ratio = token_usage["total_tokens"] / self.max_tokens
            if usage_ratio > self.max_token_usage_ratio:
                self.logger.bind(tag=TAG).warning(
                    f"Token使用量已达 {token_usage['total_tokens']}/{self.max_tokens} "
                    f"({usage_ratio:.1%})，接近上限"
                )
            
            self.logger.bind(tag=TAG).info(
                f"VLLM调用统计 | 输入Token: {token_usage['prompt_tokens']} | "
                f"输出Token: {token_usage['completion_tokens']} | "
                f"总Token: {token_usage['total_tokens']} | "
                f"响应时间: {response_time:.2f}s | "
                f"工具调用: {len(tool_calls)}"
            )
            
            return {
                "content": content,
                "tool_calls": tool_calls,
                "token_usage": token_usage,
                "response_time": response_time
            }
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"VLLM分析异常: {e}")
            raise
    
    async def analyze_intent(
        self,
        visitor_image: str,
        dialogue_history: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """意图识别分析（单图片+对话历史）
        
        Args:
            visitor_image: 访客照片（Base64）
            dialogue_history: 对话历史
            system_prompt: 意图识别提示词（可选，如果不提供则从配置加载）
            
        Returns:
            分析结果
        """
        self.logger.bind(tag=TAG).debug("执行意图识别分析")
        
        # 如果没有提供提示词，从配置加载
        if not system_prompt:
            system_prompt = self.get_prompt("intent_recognition_prompt")
        
        return self.analyze_with_tools(
            question="请根据对话历史和访客照片，识别访客意图。",
            images=[visitor_image],
            dialogue_history=dialogue_history,
            system_prompt=system_prompt
        )
    
    async def analyze_package_status(
        self,
        current_image: str,
        baseline_image: str,
        dialogue_history: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """看护监控分析（双图片对比+对话历史）
        
        Args:
            current_image: 当前图片（Base64）
            baseline_image: 基准图片（Base64）
            dialogue_history: 对话历史
            system_prompt: 看护模式提示词（可选，如果不提供则从配置加载）
            
        Returns:
            分析结果
        """
        self.logger.bind(tag=TAG).debug("执行看护监控分析")
        
        # 如果没有提供提示词，从配置加载
        if not system_prompt:
            system_prompt = self.get_prompt("package_guard_prompt")
        
        # 构建问题文本，说明两张图片的含义
        question = """
        请对比当前图片和基准图片，判断门口快递的状态变化和威胁等级。
        
        第一张图片是基准图片（之前的状态）
        第二张图片是当前图片（现在的状态）
        
        请调用 report_package_status 工具报告情况。
        """
        
        return self.analyze_with_tools(
            question=question,
            images=[baseline_image, current_image],  # 基准图片在前，当前图片在后
            dialogue_history=dialogue_history,
            system_prompt=system_prompt
        )
    
    async def execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """执行工具调用
        
        Args:
            tool_calls: 工具调用列表
            
        Returns:
            工具执行结果列表
        """
        if not self.doorlock_tools:
            self.logger.bind(tag=TAG).warning("工具函数未初始化，无法执行工具调用")
            return []
        
        results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            arguments = tool_call.get("arguments", {})
            
            try:
                # 调用工具函数
                result = await self.doorlock_tools.call_tool(tool_name, arguments)
                
                results.append({
                    "tool_call_id": tool_call.get("id"),
                    "tool_name": tool_name,
                    "result": result
                })
                
            except Exception as e:
                self.logger.bind(tag=TAG).error(
                    f"工具调用执行异常: tool_name={tool_name}, error={e}"
                )
                results.append({
                    "tool_call_id": tool_call.get("id"),
                    "tool_name": tool_name,
                    "result": {
                        "success": False,
                        "message": f"工具调用异常: {str(e)}"
                    }
                })
        
        return results
    
    def _build_messages(
        self,
        question: str,
        images: List[str],
        dialogue_history: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """构建消息列表
        
        Args:
            question: 问题文本
            images: 图片列表（Base64）
            dialogue_history: 对话历史
            system_prompt: 系统提示词
            
        Returns:
            消息列表
        """
        messages = []
        
        # 添加系统提示词
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # 添加对话历史
        for msg in dialogue_history:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        
        # 添加当前问题和图片
        content = [{"type": "text", "text": question}]
        
        # 添加图片
        for image_base64 in images:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }
            })
        
        messages.append({
            "role": "user",
            "content": content
        })
        
        return messages
