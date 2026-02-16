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
    """门锁AI专用VLLM提供者
    
    复用系统已加载的 VLLM 配置，不独立配置模型参数
    """
    
    def __init__(self, config: dict, logger_instance=None):
        """初始化VLLM提供者
        
        Args:
            config: 系统配置字典（已从 manage-api 或本地加载完成）
            logger_instance: 日志实例（可选）
        """
        self.logger = logger_instance or logger
        
        # 从系统配置获取选中的 VLLM 配置
        selected_vllm = config.get("selected_module", {}).get("VLLM", "")
        if not selected_vllm:
            raise ValueError("系统未配置 VLLM 模块，请在 selected_module.VLLM 中指定")
        
        vllm_configs = config.get("VLLM", {})
        if selected_vllm not in vllm_configs:
            raise ValueError(f"找不到 VLLM 配置: {selected_vllm}")
        
        vllm_config = vllm_configs[selected_vllm]
        
        # 提取 VLLM 配置参数（完全复用系统配置）
        self.model_name = vllm_config.get("model_name")
        self.api_key = vllm_config.get("api_key")
        # 兼容 base_url 和 url 两种写法
        self.base_url = vllm_config.get("base_url") or vllm_config.get("url")
        
        # 参数配置（完全复用系统配置的参数）
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
        
        # 从门锁独立配置加载性能参数和Token限制
        doorlock_config = self._load_doorlock_config()
        performance_config = doorlock_config.get("performance", {})
        
        # Token使用量警告阈值（输出Token）
        self.max_token_usage_ratio = float(
            performance_config.get("max_token_usage_ratio", 0.8)
        )
        
        # VLLM模型Token限制（用于多层次监控）
        vllm_limits = performance_config.get("vllm_limits", {})
        self.model_context_limit = int(vllm_limits.get("model_context_limit", 262144))
        self.max_input_tokens = int(vllm_limits.get("max_input_tokens", 260096))
        self.max_output_tokens = int(vllm_limits.get("max_output_tokens", 32768))
        self.max_image_tokens = int(vllm_limits.get("max_image_tokens", 16384))
        self.tokens_per_image = int(vllm_limits.get("tokens_per_image", 7000))
        self.input_warning_ratio = float(vllm_limits.get("input_warning_ratio", 0.8))
        self.total_warning_ratio = float(vllm_limits.get("total_warning_ratio", 0.8))
        
        # 加载提示词配置
        self.prompts = self._load_prompts()
        
        # 工具函数（延迟初始化）
        self.doorlock_tools = None
        
        # 初始化OpenAI客户端
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        self.logger.bind(tag=TAG).info(
            f"门锁VLLM提供者初始化完成: 复用系统配置 {selected_vllm}, "
            f"model={self.model_name}, max_tokens={self.max_tokens}, "
            f"context_limit={self.model_context_limit}, "
            f"tokens_per_image={self.tokens_per_image}, "
            f"prompts_loaded={len(self.prompts)}"
        )
    
    def _load_doorlock_config(self) -> dict:
        """加载门锁独立配置文件（仅用于业务配置，不影响 VLLM 模型配置）
        
        Returns:
            门锁配置字典，加载失败返回空字典
        """
        try:
            doorlock_config_path = Path(__file__).parent.parent.parent.parent / "config" / "doorlock_config.yaml"
            if not doorlock_config_path.exists():
                self.logger.bind(tag=TAG).debug("门锁配置文件不存在，使用默认配置")
                return {}
            
            from ruamel.yaml import YAML
            yaml = YAML()
            with open(doorlock_config_path, 'r', encoding='utf-8') as f:
                config = yaml.load(f)
            
            self.logger.bind(tag=TAG).debug("门锁配置加载成功")
            return config
        except Exception as e:
            self.logger.bind(tag=TAG).warning(f"加载门锁配置失败: {e}，使用默认配置")
            return {}
    
    def set_doorlock_tools(self, doorlock_tools: DoorlockTools):
        """设置门锁工具函数
        
        Args:
            doorlock_tools: 门锁工具函数实例
        """
        self.doorlock_tools = doorlock_tools
        self.logger.bind(tag=TAG).info("门锁工具函数已设置")
    
    def _estimate_tokens(self, text: str) -> int:
        """估算文本的Token数量（简化方法）
        
        Args:
            text: 文本内容
            
        Returns:
            估算的Token数量
        
        说明：
            - 中文：约 1.5 字符/Token
            - 英文：约 4 字符/Token
            - 这是粗略估算，实际Token数由模型决定
        """
        if not text:
            return 0
        
        # 统计中英文字符
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        
        # 估算Token数
        estimated_tokens = int(chinese_chars / 1.5 + other_chars / 4)
        
        return estimated_tokens
    
    def _estimate_image_tokens(self, image_count: int) -> int:
        """估算图片的Token数量
        
        Args:
            image_count: 图片数量
            
        Returns:
            估算的Token数量
        
        说明：
            - 从配置文件加载 tokens_per_image 参数
            - 默认值：7000 tokens（VGA分辨率）
            - 可根据实际图片分辨率调整配置
        """
        return image_count * self.tokens_per_image
    
    def _truncate_dialogue_history(
        self,
        dialogue_history: List[Dict[str, str]],
        max_tokens: int
    ) -> List[Dict[str, str]]:
        """截断对话历史以满足Token限制
        
        Args:
            dialogue_history: 完整对话历史
            max_tokens: 最大Token数
            
        Returns:
            截断后的对话历史（保留最近的对话）
        """
        if max_tokens <= 0:
            return []
        
        # 从最新的对话开始累加
        truncated = []
        current_tokens = 0
        
        for msg in reversed(dialogue_history):
            content = msg.get("content", "")
            msg_tokens = self._estimate_tokens(content)
            
            if current_tokens + msg_tokens > max_tokens:
                # 超出限制，停止添加
                break
            
            truncated.insert(0, msg)
            current_tokens += msg_tokens
        
        return truncated
    
    def _check_image_token_limit(self, image_count: int) -> bool:
        """检查图片数量是否超过Token限制
        
        Args:
            image_count: 图片数量
            
        Returns:
            是否在限制内
        """
        estimated_tokens = self._estimate_image_tokens(image_count)
        
        if estimated_tokens > self.max_image_tokens:
            self.logger.bind(tag=TAG).error(
                f"❌ 图片Token超出限制: {estimated_tokens} > {self.max_image_tokens}, "
                f"图片数量: {image_count}"
            )
            return False
        
        return True
    
    def _check_token_usage(self, token_usage: dict, response_time: float, tool_calls_count: int):
        """多层次检查Token使用情况，提供详细的监控和警告
        
        Args:
            token_usage: Token使用统计字典
            response_time: 响应时间（秒）
            tool_calls_count: 工具调用次数
        """
        prompt_tokens = token_usage["prompt_tokens"]
        completion_tokens = token_usage["completion_tokens"]
        total_tokens = token_usage["total_tokens"]
        
        # 计算各项使用率
        output_usage_ratio = completion_tokens / self.max_tokens
        input_usage_ratio = prompt_tokens / self.max_input_tokens
        total_usage_ratio = total_tokens / self.model_context_limit
        
        # 1. 检查输出Token使用率（主要警告 - 影响回复完整性）
        if output_usage_ratio > self.max_token_usage_ratio:
            self.logger.bind(tag=TAG).warning(
                f"⚠️ 输出Token接近限制: {completion_tokens}/{self.max_tokens} "
                f"({output_usage_ratio:.1%})，AI回复可能被截断，建议增加 max_tokens"
            )
        
        # 2. 检查输入Token使用率（次要警告 - 影响上下文容量）
        if input_usage_ratio > self.input_warning_ratio:
            self.logger.bind(tag=TAG).warning(
                f"⚠️ 输入Token较高: {prompt_tokens}/{self.max_input_tokens} "
                f"({input_usage_ratio:.1%})，建议优化提示词、减少对话历史或降低图片分辨率"
            )
        
        # 3. 检查总Token使用率（严重警告 - 接近模型上限）
        if total_usage_ratio > self.total_warning_ratio:
            self.logger.bind(tag=TAG).warning(
                f"⚠️ 总Token接近上下文窗口: {total_tokens}/{self.model_context_limit} "
                f"({total_usage_ratio:.1%})，接近模型上限，可能影响性能"
            )
        
        # 4. 记录详细统计（信息级别 - 用于监控和分析）
        self.logger.bind(tag=TAG).info(
            f"VLLM调用统计 | "
            f"输入: {prompt_tokens} ({input_usage_ratio:.1%}) | "
            f"输出: {completion_tokens} ({output_usage_ratio:.1%}) | "
            f"总计: {total_tokens} ({total_usage_ratio:.1%}) | "
            f"响应时间: {response_time:.2f}s | "
            f"工具调用: {tool_calls_count}"
        )
    
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
    
    def _build_unified_prompt(self, has_baseline: bool) -> str:
        """动态组合统一模式提示词
        
        Args:
            has_baseline: 是否有基准图片（看护模式是否激活）
            
        Returns:
            组合后的完整提示词字符串
        """
        # 基础部分（总是包含）
        prompt_parts = [
            self.get_prompt("core_role_and_style"),
            self.get_prompt("dialogue_tasks")
        ]
        
        # 如果看护模式激活，添加看护任务
        if has_baseline:
            prompt_parts.append(self.get_prompt("guard_tasks"))
        
        # 总是添加工具指南
        prompt_parts.append(self.get_prompt("tools_guide"))
        
        # 过滤空提示词并拼接
        prompt_parts = [p for p in prompt_parts if p]
        
        return "\n\n".join(prompt_parts)
    
    async def analyze_unified(
        self,
        visitor_image: str,
        baseline_image: Optional[str],
        dialogue_history: List[Dict[str, str]],
        is_first_round: bool = False
    ) -> Dict[str, Any]:
        """统一模式分析，同时处理对话和监控任务
        
        Args:
            visitor_image: 访客照片（Base64编码）
            baseline_image: 基准图片（Base64编码，可选）
            dialogue_history: 对话历史列表
            is_first_round: 是否第一轮对话
            
        Returns:
            分析结果字典，包含：
            - content: AI回复文本
            - tool_calls: 工具调用列表
            - token_usage: Token统计
            - response_time: 响应时间（秒）
        """
        start_time = time.time()
        
        try:
            # 1. 构建图片列表（第一轮传2张，后续传1张）
            images = []
            if is_first_round and baseline_image:
                # 第一轮：传入访客图片和基准图片
                images = [visitor_image, baseline_image]
                self.logger.bind(tag=TAG).debug(
                    "统一模式第一轮：传入2张图片（访客图片+基准图片）"
                )
            else:
                # 后续轮次：仅传入访客图片
                images = [visitor_image]
                self.logger.bind(tag=TAG).debug(
                    "统一模式后续轮次：传入1张图片（访客图片）"
                )
            
            # 2. 检查图片Token限制
            if not self._check_image_token_limit(len(images)):
                error_msg = (
                    f"图片Token超出限制: {len(images)}张图片估算 "
                    f"{self._estimate_image_tokens(len(images))} tokens > "
                    f"{self.max_image_tokens}"
                )
                self.logger.bind(tag=TAG).error(error_msg)
                raise ValueError(error_msg)
            
            # 3. 动态组合提示词（根据是否有基准图片）
            has_baseline = baseline_image is not None
            system_prompt = self._build_unified_prompt(has_baseline)
            
            if has_baseline:
                self.logger.bind(tag=TAG).debug(
                    "统一模式提示词：包含看护任务（看护模式激活）"
                )
            else:
                self.logger.bind(tag=TAG).debug(
                    "统一模式提示词：仅对话任务（看护模式未激活）"
                )
            
            # 4. 调用VLLM进行分析
            # 构建问题文本
            if dialogue_history:
                # 从对话历史中提取最后一条用户消息
                last_user_msg = None
                for msg in reversed(dialogue_history):
                    if msg.get("role") == "user":
                        last_user_msg = msg.get("content", "")
                        break
                
                question = last_user_msg or "请继续对话。"
            else:
                # 第一轮对话，主动问候
                question = "请根据访客照片，主动问候访客并询问来访目的。"
            
            # 调用analyze_with_tools方法
            result = self.analyze_with_tools(
                question=question,
                images=images,
                dialogue_history=dialogue_history,
                system_prompt=system_prompt
            )
            
            # 5. 返回结果（已包含Token统计和响应时间）
            return result
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"统一模式分析异常: {e}")
            # 返回默认响应
            return {
                "content": "抱歉，我暂时无法理解，请稍后再试。",
                "tool_calls": [],
                "token_usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                },
                "response_time": time.time() - start_time
            }
    
    async def final_package_check(
        self,
        current_image: str,
        baseline_image: str
    ) -> Dict[str, Any]:
        """对话结束后的快递状态最终检查
        
        Args:
            current_image: 当前图片（Base64编码）
            baseline_image: 基准图片（Base64编码）
            
        Returns:
            检查结果字典，包含：
            - threat_level: 威胁等级 ("low"|"medium"|"high")
            - action: 行为类型 ("taking"|"searching"|"damaging"|"normal"|"passing")
            - description: 详细描述
        """
        start_time = time.time()
        
        try:
            # 1. 检查图片Token限制（2张图片）
            if not self._check_image_token_limit(2):
                error_msg = (
                    f"图片Token超出限制: 2张图片估算 "
                    f"{self._estimate_image_tokens(2)} tokens > "
                    f"{self.max_image_tokens}"
                )
                self.logger.bind(tag=TAG).error(error_msg)
                raise ValueError(error_msg)
            
            # 2. 加载专用提示词
            system_prompt = self.get_prompt("final_package_check_prompt")
            
            if not system_prompt:
                self.logger.bind(tag=TAG).warning(
                    "未找到final_package_check_prompt提示词，使用默认提示词"
                )
                system_prompt = """
【任务】
访客已离开，请对比基准图片和当前图片，判断快递的最终状态。

【要求】
- 对比两张图片，判断快递是否被移动、拿走或破坏
- 评估威胁等级
- 以纯JSON格式返回结果

【输出格式】
```json
{
  "threat_level": "low|medium|high",
  "action": "taking|searching|damaging|normal|passing",
  "description": "详细描述你看到的情况"
}
```

【判断标准】
- 快递位置未变化 = low + normal
- 快递被移动但未拿走 = medium + searching
- 快递被拿走 = high + taking（除非是主人）
- 快递被破坏 = high + damaging
"""
            
            # 3. 构建问题文本
            question = """
请对比基准图片和当前图片，判断快递的最终状态。

第一张图片是基准图片（之前的状态）
第二张图片是当前图片（现在的状态）

请以纯JSON格式返回结果，不要包含任何其他文字说明。
"""
            
            # 4. 调用VLLM（不使用工具函数）
            messages = self._build_messages(
                question=question,
                images=[baseline_image, current_image],
                dialogue_history=[],
                system_prompt=system_prompt
            )
            
            # 调用VLLM（不传入tools参数）
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=min(self.max_tokens, self.max_output_tokens),
                stream=False
            )
            
            # 计算响应时间
            response_time = time.time() - start_time
            
            # 提取响应内容
            content = response.choices[0].message.content or ""
            
            # Token统计
            token_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            # Token使用量检查
            self._check_token_usage(token_usage, response_time, 0)
            
            # 5. 解析纯JSON格式结果
            result = self._parse_json_response(content)
            
            # 验证必需字段
            if not all(k in result for k in ["threat_level", "action", "description"]):
                self.logger.bind(tag=TAG).warning(
                    f"快递状态检查结果缺少必需字段，返回默认值"
                )
                return self._get_default_package_check_result()
            
            self.logger.bind(tag=TAG).info(
                f"快递状态检查完成: threat_level={result['threat_level']}, "
                f"action={result['action']}, response_time={response_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"快递状态检查异常: {e}")
            # 6. 异常处理：返回默认低威胁结果
            return self._get_default_package_check_result()
    
    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """解析JSON格式的响应内容
        
        Args:
            content: 响应内容（可能包含markdown代码块）
            
        Returns:
            解析后的字典
        """
        import json
        import re
        
        try:
            # 尝试直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试从markdown代码块中提取JSON
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # 尝试查找第一个完整的JSON对象
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
            
            # 解析失败
            self.logger.bind(tag=TAG).error(f"JSON解析失败，原始内容: {content[:200]}")
            raise ValueError("无法解析JSON响应")
    
    def _get_default_package_check_result(self) -> Dict[str, Any]:
        """获取默认的快递检查结果（低威胁）
        
        Returns:
            默认结果字典
        """
        return {
            "threat_level": "low",
            "action": "normal",
            "description": "无法解析检查结果，默认判定为正常状态"
        }
    
    async def generate_intent_summary(
        self,
        visitor_image: str,
        dialogue_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """生成访客意图总结
        
        Args:
            visitor_image: 访客照片（Base64编码）
            dialogue_history: 完整对话历史
            
        Returns:
            总结结果字典，包含：
            - intent_type: 意图类型 ("delivery"|"visit"|"sales"|"maintenance"|"other")
            - summary: 简洁总结
            - important_notes: 重要信息列表
            - ai_analysis: 详细分析
        """
        start_time = time.time()
        
        try:
            # 1. 检查图片Token限制（1张图片）
            if not self._check_image_token_limit(1):
                error_msg = (
                    f"图片Token超出限制: 1张图片估算 "
                    f"{self._estimate_image_tokens(1)} tokens > "
                    f"{self.max_image_tokens}"
                )
                self.logger.bind(tag=TAG).error(error_msg)
                raise ValueError(error_msg)
            
            # 2. 加载专用提示词
            system_prompt = self.get_prompt("intent_summary_prompt")
            
            if not system_prompt:
                self.logger.bind(tag=TAG).warning(
                    "未找到intent_summary_prompt提示词，使用默认提示词"
                )
                system_prompt = """
【任务】
根据完整的对话历史和访客照片，生成结构化的访客意图总结。

【要求】
- 识别访客意图类型
- 提取重要信息（留言、提醒）
- 生成完整总结
- 提供AI分析

【输出格式】
```json
{
  "intent_type": "delivery|visit|sales|maintenance|other",
  "summary": "简洁的总结（一句话）",
  "important_notes": [
    "【留言】...",
    "【提醒】..."
  ],
  "ai_analysis": "详细的AI分析，包括访客特征、行为观察、建议等"
}
```

【意图类型说明】
- delivery: 送快递/外卖
- visit: 拜访朋友/家人
- sales: 推销产品/服务
- maintenance: 维修/物业工作
- other: 其他情况
"""
            
            # 3. 构建问题文本
            question = """
请根据完整的对话历史和访客照片，生成结构化的访客意图总结。

请以JSON格式返回结果。
"""
            
            # 4. 调用VLLM（不使用工具函数）
            messages = self._build_messages(
                question=question,
                images=[visitor_image],
                dialogue_history=dialogue_history,
                system_prompt=system_prompt
            )
            
            # 调用VLLM（不传入tools参数）
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=min(self.max_tokens, self.max_output_tokens),
                stream=False
            )
            
            # 计算响应时间
            response_time = time.time() - start_time
            
            # 提取响应内容
            content = response.choices[0].message.content or ""
            
            # Token统计
            token_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            # Token使用量检查
            self._check_token_usage(token_usage, response_time, 0)
            
            # 5. 解析混合JSON格式结果
            result = self._parse_json_response(content)
            
            # 验证必需字段
            required_fields = ["intent_type", "summary", "important_notes", "ai_analysis"]
            if not all(k in result for k in required_fields):
                self.logger.bind(tag=TAG).warning(
                    f"意图总结结果缺少必需字段，返回默认值"
                )
                return self._get_default_intent_summary()
            
            # 确保important_notes是列表
            if not isinstance(result.get("important_notes"), list):
                result["important_notes"] = []
            
            self.logger.bind(tag=TAG).info(
                f"意图总结生成完成: intent_type={result['intent_type']}, "
                f"response_time={response_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"意图总结生成异常: {e}")
            # 6. 异常处理：返回默认总结结果
            return self._get_default_intent_summary()
    
    def _get_default_intent_summary(self) -> Dict[str, Any]:
        """获取默认的意图总结结果
        
        Returns:
            默认总结字典
        """
        return {
            "intent_type": "other",
            "summary": "访客到访，无法生成详细总结",
            "important_notes": [],
            "ai_analysis": "由于系统异常，无法生成详细的访客分析"
        }
    
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
            
            # 应用输出Token限制（使用门锁配置的限制，不超过系统配置）
            max_tokens = min(self.max_tokens, self.max_output_tokens)
            
            # 调用VLLM
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools if tools else None,
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=max_tokens,
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
            
            # 多层次Token使用量检查和警告
            self._check_token_usage(token_usage, response_time, len(tool_calls))
            
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
        
        # 检查图片Token限制（1张图片）
        if not self._check_image_token_limit(1):
            error_msg = f"图片Token超出限制: 1张图片估算 {self._estimate_image_tokens(1)} tokens > {self.max_image_tokens}"
            self.logger.bind(tag=TAG).error(error_msg)
            raise ValueError(error_msg)
        
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
        
        # 检查图片Token限制（2张图片）
        if not self._check_image_token_limit(2):
            error_msg = f"图片Token超出限制: 2张图片估算 {self._estimate_image_tokens(2)} tokens > {self.max_image_tokens}"
            self.logger.bind(tag=TAG).error(error_msg)
            raise ValueError(error_msg)
        
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
        """构建消息列表（带Token限制）
        
        Args:
            question: 问题文本
            images: 图片列表（Base64）
            dialogue_history: 对话历史
            system_prompt: 系统提示词
            
        Returns:
            消息列表
        """
        # 估算各部分Token数
        system_tokens = self._estimate_tokens(system_prompt) if system_prompt else 0
        question_tokens = self._estimate_tokens(question)
        image_tokens = self._estimate_image_tokens(len(images))
        
        # 计算固定部分Token数
        fixed_tokens = system_tokens + question_tokens + image_tokens
        
        # 计算对话历史可用Token数（综合考虑输入限制和总限制）
        # 方案1：基于输入限制
        available_by_input = self.max_input_tokens - fixed_tokens - self.max_tokens
        
        # 方案2：基于总限制（模型上下文窗口）
        available_by_total = self.model_context_limit - fixed_tokens - self.max_tokens
        
        # 取两者的最小值，确保不超过任何一个限制
        available_for_history = min(available_by_input, available_by_total)
        
        if available_for_history < 0:
            self.logger.bind(tag=TAG).warning(
                f"⚠️ 固定内容已超出限制: "
                f"system={system_tokens}, question={question_tokens}, "
                f"images={image_tokens}, total_fixed={fixed_tokens}, "
                f"max_input={self.max_input_tokens}, "
                f"context_limit={self.model_context_limit}, "
                f"reserved_output={self.max_tokens}"
            )
            # 如果固定内容已超限，清空对话历史
            dialogue_history = []
            available_for_history = 0
        
        # 截断对话历史
        truncated_history = self._truncate_dialogue_history(
            dialogue_history,
            max_tokens=available_for_history
        )
        
        if len(truncated_history) < len(dialogue_history):
            # 计算实际使用的限制类型
            limit_type = "输入限制" if available_by_input < available_by_total else "总限制"
            self.logger.bind(tag=TAG).info(
                f"对话历史已截断: {len(dialogue_history)} -> {len(truncated_history)} 轮, "
                f"可用Token: {available_for_history} (受限于{limit_type})"
            )
        
        # 构建消息
        messages = []
        
        # 添加系统提示词
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # 添加截断后的对话历史
        for msg in truncated_history:
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
