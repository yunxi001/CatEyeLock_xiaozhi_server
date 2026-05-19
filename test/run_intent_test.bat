@echo off
chcp 65001 >nul
echo ============================================================
echo 访客意图识别测试工具
echo ============================================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.7+
    pause
    exit /b 1
)

echo [提示] 请确保服务器已启动 (python app.py)
echo.

:menu
echo 请选择测试模式:
echo 1. 快速测试 (单个场景)
echo 2. 完整测试 (所有场景)
echo 3. 自定义场景测试
echo 4. 退出
echo.
set /p choice="请输入选项 (1-4): "

if "%choice%"=="1" goto quick_test
if "%choice%"=="2" goto full_test
if "%choice%"=="3" goto custom_test
if "%choice%"=="4" goto end
echo [错误] 无效选项，请重新选择
echo.
goto menu

:quick_test
echo.
echo ============================================================
echo 运行快速测试...
echo ============================================================
python quick_test_intent.py
echo.
echo 测试完成！
pause
goto menu

:full_test
echo.
echo ============================================================
echo 运行完整测试套件...
echo ============================================================
python test_visitor_intent_recognition.py
echo.
echo 测试完成！
pause
goto menu

:custom_test
echo.
echo 可用场景:
echo 1. 快递员送货
echo 2. 朋友拜访
echo 3. 推销人员
echo 4. 物业维修
echo 5. 紧急求助
echo.
set /p scenario_choice="请选择场景 (1-5): "

if "%scenario_choice%"=="1" set scenario_name=快递员送货
if "%scenario_choice%"=="2" set scenario_name=朋友拜访
if "%scenario_choice%"=="3" set scenario_name=推销人员
if "%scenario_choice%"=="4" set scenario_name=物业维修
if "%scenario_choice%"=="5" set scenario_name=紧急求助

if not defined scenario_name (
    echo [错误] 无效选项
    pause
    goto menu
)

echo.
echo ============================================================
echo 运行场景: %scenario_name%
echo ============================================================
python test_visitor_intent_recognition.py --scenario "%scenario_name%"
echo.
echo 测试完成！
pause
goto menu

:end
echo.
echo 感谢使用！
exit /b 0
