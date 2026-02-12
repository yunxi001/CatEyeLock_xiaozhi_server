@echo off
REM 恢复 ESP32 连接超时机制脚本 (Windows)
REM 使用方法: docs\my_docs\restore-timeout-mechanism.bat

echo ==========================================
echo 恢复 ESP32 连接超时机制
echo ==========================================
echo.

REM 检查是否在正确的目录
if not exist "main\xiaozhi-server\core\connection.py" (
    echo ❌ 错误：请在项目根目录下运行此脚本
    pause
    exit /b 1
)

echo 📝 备份当前文件...
copy main\xiaozhi-server\core\connection.py main\xiaozhi-server\core\connection.py.no-timeout.bak >nul
copy main\xiaozhi-server\core\handle\receiveAudioHandle.py main\xiaozhi-server\core\handle\receiveAudioHandle.py.no-timeout.bak >nul
echo ✅ 备份完成
echo.

echo ⚠️  需要手动恢复以下文件：
echo.
echo 1. main\xiaozhi-server\core\connection.py
echo    - 找到第 206-208 行
echo    - 取消注释: self.timeout_task = asyncio.create_task(self._check_timeout())
echo    - 注释掉: self.timeout_task = None
echo.
echo 2. main\xiaozhi-server\core\handle\receiveAudioHandle.py
echo    - 找到第 100-116 行
echo    - 取消注释超时检查代码块
echo.

echo ==========================================
echo 📋 后续步骤：
echo ==========================================
echo 1. 使用编辑器手动恢复上述两个文件
echo 2. 重启服务器: python main\xiaozhi-server\app.py
echo 3. 测试超时功能是否正常
echo.
echo 💾 备份文件位置：
echo    - main\xiaozhi-server\core\connection.py.no-timeout.bak
echo    - main\xiaozhi-server\core\handle\receiveAudioHandle.py.no-timeout.bak
echo.

pause
