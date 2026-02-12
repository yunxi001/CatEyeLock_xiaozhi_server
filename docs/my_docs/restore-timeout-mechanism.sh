#!/bin/bash
# 恢复 ESP32 连接超时机制脚本
# 使用方法: bash docs/my_docs/restore-timeout-mechanism.sh

echo "=========================================="
echo "恢复 ESP32 连接超时机制"
echo "=========================================="
echo ""

# 检查是否在正确的目录
if [ ! -f "main/xiaozhi-server/core/connection.py" ]; then
    echo "❌ 错误：请在项目根目录下运行此脚本"
    exit 1
fi

echo "📝 备份当前文件..."
cp main/xiaozhi-server/core/connection.py main/xiaozhi-server/core/connection.py.no-timeout.bak
cp main/xiaozhi-server/core/handle/receiveAudioHandle.py main/xiaozhi-server/core/handle/receiveAudioHandle.py.no-timeout.bak
echo "✅ 备份完成"
echo ""

echo "🔄 恢复 connection.py 中的超时检查任务..."
# 恢复 connection.py
sed -i.tmp 's/# self.timeout_task = asyncio.create_task(self._check_timeout())/self.timeout_task = asyncio.create_task(self._check_timeout())/g' main/xiaozhi-server/core/connection.py
sed -i.tmp 's/self.timeout_task = None/# self.timeout_task = None  # 已恢复超时机制/g' main/xiaozhi-server/core/connection.py
rm -f main/xiaozhi-server/core/connection.py.tmp
echo "✅ connection.py 恢复完成"
echo ""

echo "🔄 恢复 receiveAudioHandle.py 中的超时检查..."
# 这个需要手动恢复，因为涉及多行注释
echo "⚠️  receiveAudioHandle.py 需要手动恢复"
echo "   请编辑 main/xiaozhi-server/core/handle/receiveAudioHandle.py"
echo "   取消第 100-116 行的注释块"
echo ""

echo "=========================================="
echo "✅ 超时机制恢复完成"
echo "=========================================="
echo ""
echo "📋 后续步骤："
echo "1. 手动编辑 receiveAudioHandle.py 取消注释"
echo "2. 重启服务器: python main/xiaozhi-server/app.py"
echo "3. 测试超时功能是否正常"
echo ""
echo "💾 备份文件位置："
echo "   - main/xiaozhi-server/core/connection.py.no-timeout.bak"
echo "   - main/xiaozhi-server/core/handle/receiveAudioHandle.py.no-timeout.bak"
