"""
VLLM工具调用处理器

负责：
- 工具调用结果处理和格式化
- 工具调用错误处理和降级策略
- 工具调用性能监控
"""
import time
from typing import Dict, Any, List, Optional
from loguru import logger

TAG = "VLLMToolHandler"


class VLLMToolHandler:
    """VLLM工具调用处理器"""
    
    def __init__(self, max_retries: int = 2, retry_delay: float = 1.0):
        """初始化工具调用处理器
        
        Args:
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # 性能统计
        self.tool_call_stats = {
            "total_calls": 0,
            "success_calls": 0,
            "failed_calls": 0,
            "total_time": 0.0
        }
        
        logger.bind(tag=TAG).info(
            f"工具调用处理器初始化完成: max_retries={max_retries}, "
            f"retry_delay={retry_delay}s"
        )
    
    async def handle_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        tools_instance: Any
    ) -> List[Dict[str, Any]]:
        """处理工具调用列表
        
        Args:
            tool_calls: 工具调用列表
            tools_instance: 工具函数实例
            
        Returns:
            处理结果列表
        """
        if not tool_calls:
            return []
        
        results = []
        
        for tool_call in tool_calls:
            result = await self._handle_single_tool_call(tool_call, tools_instance)
            results.append(result)
        
        return results
    
    async def _handle_single_tool_call(
        self,
        tool_call: Dict[str, Any],
        tools_instance: Any
    ) -> Dict[str, Any]:
        """处理单个工具调用（带重试和错误处理）
        
        Args:
            tool_call: 工具调用信息
            tools_instance: 工具函数实例
            
        Returns:
            处理结果
        """
        tool_name = tool_call.get("name", "unknown")
        tool_id = tool_call.get("id", "")
        arguments = tool_call.get("arguments", {})
        
        start_time = time.time()
        self.tool_call_stats["total_calls"] += 1
        
        # 重试逻辑
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                # 调用工具函数
                result = await tools_instance.call_tool(tool_name, arguments)
                
                # 记录成功
                elapsed_time = time.time() - start_time
                self.tool_call_stats["success_calls"] += 1
                self.tool_call_stats["total_time"] += elapsed_time
                
                logger.bind(tag=TAG).info(
                    f"工具调用成功: tool={tool_name}, attempt={attempt + 1}, "
                    f"time={elapsed_time:.2f}s"
                )
                
                return self._format_success_result(tool_id, tool_name, result, elapsed_time)
                
            except Exception as e:
                last_error = e
                logger.bind(tag=TAG).warning(
                    f"工具调用失败: tool={tool_name}, attempt={attempt + 1}/{self.max_retries + 1}, "
                    f"error={e}"
                )
                
                # 如果还有重试机会，等待后重试
                if attempt < self.max_retries:
                    import asyncio
                    await asyncio.sleep(self.retry_delay)
                    continue
        
        # 所有重试都失败，执行降级策略
        elapsed_time = time.time() - start_time
        self.tool_call_stats["failed_calls"] += 1
        self.tool_call_stats["total_time"] += elapsed_time
        
        return self._handle_tool_call_failure(
            tool_id,
            tool_name,
            arguments,
            last_error,
            elapsed_time
        )
    
    def _format_success_result(
        self,
        tool_id: str,
        tool_name: str,
        result: Dict[str, Any],
        elapsed_time: float
    ) -> Dict[str, Any]:
        """格式化成功结果
        
        Args:
            tool_id: 工具调用ID
            tool_name: 工具名称
            result: 工具执行结果
            elapsed_time: 执行耗时
            
        Returns:
            格式化后的结果
        """
        return {
            "tool_call_id": tool_id,
            "tool_name": tool_name,
            "status": "success",
            "result": result,
            "elapsed_time": elapsed_time
        }
    
    def _handle_tool_call_failure(
        self,
        tool_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        error: Exception,
        elapsed_time: float
    ) -> Dict[str, Any]:
        """处理工具调用失败（降级策略）
        
        Args:
            tool_id: 工具调用ID
            tool_name: 工具名称
            arguments: 工具参数
            error: 错误信息
            elapsed_time: 执行耗时
            
        Returns:
            降级结果
        """
        logger.bind(tag=TAG).error(
            f"工具调用最终失败，执行降级策略: tool={tool_name}, "
            f"arguments={arguments}, error={error}"
        )
        
        # 降级策略：返回错误信息，但不中断流程
        degraded_result = {
            "success": False,
            "message": f"工具调用失败: {str(error)}",
            "degraded": True
        }
        
        return {
            "tool_call_id": tool_id,
            "tool_name": tool_name,
            "status": "failed",
            "result": degraded_result,
            "error": str(error),
            "elapsed_time": elapsed_time
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取性能统计
        
        Returns:
            统计信息字典
        """
        total_calls = self.tool_call_stats["total_calls"]
        
        if total_calls == 0:
            return {
                "total_calls": 0,
                "success_rate": 0.0,
                "average_time": 0.0
            }
        
        return {
            "total_calls": total_calls,
            "success_calls": self.tool_call_stats["success_calls"],
            "failed_calls": self.tool_call_stats["failed_calls"],
            "success_rate": self.tool_call_stats["success_calls"] / total_calls,
            "average_time": self.tool_call_stats["total_time"] / total_calls
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        self.tool_call_stats = {
            "total_calls": 0,
            "success_calls": 0,
            "failed_calls": 0,
            "total_time": 0.0
        }
        logger.bind(tag=TAG).info("工具调用统计已重置")
