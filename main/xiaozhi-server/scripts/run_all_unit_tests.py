"""
运行所有单元测试

这个脚本会依次运行所有单元测试文件，并汇总结果
"""

import subprocess
import sys

# 定义所有测试文件
test_files = [
    "test_prompt_composition.py",
    "test_image_passing.py",
    "test_image_token_limit.py",
    "test_dialogue_truncation.py",
    "test_token_usage_monitoring.py",
    "test_photo_cache_manager.py",
]

def run_test(test_file):
    """运行单个测试文件"""
    print(f"\n{'=' * 70}")
    print(f"运行测试: {test_file}")
    print('=' * 70)
    
    try:
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # 打印输出
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        
        # 检查返回码
        if result.returncode == 0:
            print(f"✅ {test_file} - 通过")
            return True
        else:
            print(f"❌ {test_file} - 失败 (返回码: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"❌ {test_file} - 超时")
        return False
    except Exception as e:
        print(f"❌ {test_file} - 异常: {e}")
        return False


def main():
    """主函数"""
    print("=" * 70)
    print("开始运行所有单元测试")
    print("=" * 70)
    
    results = {}
    
    for test_file in test_files:
        results[test_file] = run_test(test_file)
    
    # 汇总结果
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    failed = len(results) - passed
    
    for test_file, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} - {test_file}")
    
    print("\n" + "=" * 70)
    print(f"总计: {len(results)} 个测试文件")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    print("=" * 70)
    
    if failed == 0:
        print("\n🎉 所有单元测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {failed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
