@echo off
chcp 65001 >nul
title A1_Nexus 启动菜单

:menu
cls
echo ==================================================
echo               A1_Nexus 系统启动菜单
echo ==================================================
echo.
echo   1. 启动全自动流水线 (执行 MESSAGES 中的任务)
echo   2. 检查下一个待执行任务
echo   3. 清理工作区 (为新项目做准备)
echo   4. 退出
echo.
echo ==================================================
set /p choice="请输入选项 (1-4): "

if "%choice%"=="1" goto auto
if "%choice%"=="2" goto check
if "%choice%"=="3" goto clean
if "%choice%"=="4" goto end

echo 无效选项，请重新输入。
pause
goto menu

:auto
cls
echo 正在启动全自动流水线...
python SYSTEM/auto_setup.py --auto
pause
goto menu

:check
cls
echo 正在检查下一个任务...
python SYSTEM/check_next.py
pause
goto menu

:clean
cls
python SYSTEM/cleanup_workspace.py
pause
goto menu

:end
exit
