#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 httpx 0.28.1 编码问题

httpx 0.28.x 版本在处理中文字符时存在编码 bug，导致：
'ascii' codec can't encode characters in position X-Y: ordinal not in range(128)

解决方案：降级到 httpx 0.27.2
"""

import subprocess
import sys

def fix_httpx_encoding():
    """修复 httpx 编码问题"""
    print("=" * 60)
    print("修复 httpx 编码问题")
    print("=" * 60)
    
    print("\n当前 httpx 版本：")
    subprocess.run([sys.executable, "-m", "pip", "show", "httpx"])
    
    print("\n" + "=" * 60)
    print("开始降级 httpx 到 0.27.2...")
    print("=" * 60)
    
    try:
        # 卸载当前版本
        print("\n1. 卸载 httpx 0.28.1...")
        subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", "httpx"],
            check=True
        )
        
        # 安装 0.27.2 版本
        print("\n2. 安装 httpx 0.27.2...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "httpx==0.27.2"],
            check=True
        )
        
        print("\n" + "=" * 60)
        print("✓ httpx 降级成功！")
        print("=" * 60)
        
        print("\n新版本信息：")
        subprocess.run([sys.executable, "-m", "pip", "show", "httpx"])
        
        print("\n" + "=" * 60)
        print("修复完成！请重新启动服务。")
        print("=" * 60)
        
    except subprocess.CalledProcessError as e:
        print(f"\n✗ 修复失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    fix_httpx_encoding()
