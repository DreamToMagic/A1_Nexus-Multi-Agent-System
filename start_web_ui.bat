@echo off
chcp 65001 >nul
echo =========================================
echo     🚀 启动 A1_Nexus Web UI 控制台
echo =========================================

:: 检查虚拟环境
if not exist ".venv\Scripts\python.exe" (
    echo [提示] 首次运行，正在初始化环境...
    python SYSTEM\auto_setup.py
)

:: 启动 Web UI
echo [提示] 正在启动 Web 服务，请稍候...
.venv\Scripts\python.exe SYSTEM\web_ui.py

pause
