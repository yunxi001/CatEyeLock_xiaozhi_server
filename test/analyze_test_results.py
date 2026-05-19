"""
测试结果分析工具

用于分析意图识别测试结果，生成测试报告
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path


class TestResultAnalyzer:
    """测试结果分析器"""
    
    def __init__(self, results_dir: str = "test_results"):
        """初始化分析器
        
        Args:
            results_dir: 测试结果目录
        """
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)
        
        self.test_results: List[Dict[str, Any]] = []
    
    def add_result(
        self,
        scenario_name: str,
        expected_intent: str,
        actual_intent: str,
        response_time: float,
        keywords_matched: List[str],
        keywords_missed: List[str],
        success: bool
    ):
        """添加测试结果
        
        Args:
            scenario_name: 场景名称
            expected_intent: 预期意图类型
            actual_intent: 实际意图类型
            response_time: 响应时间（秒）
            keywords_matched: 匹配的关键词
            keywords_missed: 未匹配的关键词
            success: 是否成功
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "scenario_name": scenario_name,
            "expected_intent": expected_intent,
            "actual_intent": actual_intent,
            "response_time": response_time,
            "keywords_matched": keywords_matched,
            "keywords_missed": keywords_missed,
            "success": success,
            "intent_match": expected_intent == actual_intent,
            "keyword_match_rate": len(keywords_matched) / (len(keywords_matched) + len(keywords_missed)) if (keywords_matched or keywords_missed) else 0
        }
        
        self.test_results.append(result)
    
    def save_results(self, filename: str = None):
        """保存测试结果到文件
        
        Args:
            filename: 文件名，默认使用时间戳
        """
        if not filename:
            filename = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = self.results_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)
        
        print(f"测试结果已保存到: {filepath}")
    
    def generate_report(self) -> str:
        """生成测试报告
        
        Returns:
            报告文本
        """
        if not self.test_results:
            return "没有测试结果"
        
        # 统计数据
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r['success'])
        intent_matches = sum(1 for r in self.test_results if r['intent_match'])
        avg_response_time = sum(r['response_time'] for r in self.test_results) / total_tests
        avg_keyword_match_rate = sum(r['keyword_match_rate'] for r in self.test_results) / total_tests
        
        # 生成报告
        report = []
        report.append("="*70)
        report.append("访客意图识别测试报告")
        report.append("="*70)
        report.append(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"测试场景数: {total_tests}")
        report.append("")
        
        # 总体统计
        report.append("【总体统计】")
        report.append(f"  成功率: {successful_tests}/{total_tests} ({successful_tests/total_tests*100:.1f}%)")
        report.append(f"  意图识别准确率: {intent_matches}/{total_tests} ({intent_matches/total_tests*100:.1f}%)")
        report.append(f"  平均响应时间: {avg_response_time:.2f}秒")
        report.append(f"  关键词提取率: {avg_keyword_match_rate*100:.1f}%")
        report.append("")
        
        # 详细结果
        report.append("【详细结果】")
        report.append("")
        
        for i, result in enumerate(self.test_results, 1):
            status = "✓" if result['success'] else "✗"
            intent_status = "✓" if result['intent_match'] else "✗"
            
            report.append(f"{i}. {result['scenario_name']}")
            report.append(f"   状态: {status}")
            report.append(f"   意图识别: {intent_status} (预期: {result['expected_intent']}, 实际: {result['actual_intent']})")
            report.append(f"   响应时间: {result['response_time']:.2f}秒")
            report.append(f"   关键词匹配: {len(result['keywords_matched'])}/{len(result['keywords_matched']) + len(result['keywords_missed'])}")
            
            if result['keywords_matched']:
                report.append(f"     ✓ 已匹配: {', '.join(result['keywords_matched'])}")
            if result['keywords_missed']:
                report.append(f"     ✗ 未匹配: {', '.join(result['keywords_missed'])}")
            
            report.append("")
        
        # 性能分析
        report.append("【性能分析】")
        response_times = [r['response_time'] for r in self.test_results]
        min_time = min(response_times)
        max_time = max(response_times)
        
        report.append(f"  最快响应: {min_time:.2f}秒")
        report.append(f"  最慢响应: {max_time:.2f}秒")
        report.append(f"  平均响应: {avg_response_time:.2f}秒")
        report.append("")
        
        # 意图分类统计
        report.append("【意图分类统计】")
        intent_stats = {}
        for result in self.test_results:
            intent = result['expected_intent']
            if intent not in intent_stats:
                intent_stats[intent] = {'total': 0, 'correct': 0}
            intent_stats[intent]['total'] += 1
            if result['intent_match']:
                intent_stats[intent]['correct'] += 1
        
        for intent, stats in intent_stats.items():
            accuracy = stats['correct'] / stats['total'] * 100
            report.append(f"  {intent}: {stats['correct']}/{stats['total']} ({accuracy:.1f}%)")
        
        report.append("")
        report.append("="*70)
        
        return "\n".join(report)
    
    def save_report(self, filename: str = None):
        """保存测试报告到文件
        
        Args:
            filename: 文件名，默认使用时间戳
        """
        if not filename:
            filename = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        filepath = self.results_dir / filename
        
        report = self.generate_report()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"测试报告已保存到: {filepath}")
        
        return report
    
    def print_report(self):
        """打印测试报告"""
        print(self.generate_report())


def demo():
    """演示用法"""
    analyzer = TestResultAnalyzer()
    
    # 添加示例结果
    analyzer.add_result(
        scenario_name="快递员送货",
        expected_intent="delivery",
        actual_intent="delivery",
        response_time=2.3,
        keywords_matched=["快递", "顺丰", "签收"],
        keywords_missed=[],
        success=True
    )
    
    analyzer.add_result(
        scenario_name="朋友拜访",
        expected_intent="visit",
        actual_intent="visit",
        response_time=2.1,
        keywords_matched=["李明", "同学"],
        keywords_missed=["吃饭"],
        success=True
    )
    
    analyzer.add_result(
        scenario_name="推销人员",
        expected_intent="sales",
        actual_intent="sales",
        response_time=2.5,
        keywords_matched=["保险"],
        keywords_missed=["推销"],
        success=True
    )
    
    # 打印报告
    analyzer.print_report()
    
    # 保存结果和报告
    analyzer.save_results()
    analyzer.save_report()


if __name__ == "__main__":
    demo()
