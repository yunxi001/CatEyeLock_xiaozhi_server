"""
修复测试文件中的Unicode编码问题
将✓和✗替换为普通文本
"""

import os
import re

test_files = [
    "test_prompt_composition.py",
    "test_image_passing.py",
    "test_image_token_limit.py",
    "test_dialogue_truncation.py",
    "test_token_usage_monitoring.py",
    "test_photo_cache_manager.py",
]

def fix_file(filepath):
    """修复单个文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换Unicode字符
    content = content.replace('✓', '[PASS]')
    content = content.replace('✗', '[FAIL]')
    content = content.replace('❌', '[FAIL]')
    content = content.replace('✅', '[PASS]')
    content = content.replace('⚠️', '[WARN]')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"已修复: {filepath}")

def main():
    for test_file in test_files:
        if os.path.exists(test_file):
            fix_file(test_file)
        else:
            print(f"文件不存在: {test_file}")
    
    print("\n所有文件已修复！")

if __name__ == "__main__":
    main()
