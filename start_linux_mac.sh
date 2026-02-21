#!/bin/bash

# 设置终端支持 UTF-8
export LANG=en_US.UTF-8

# 检查是否安装了 python3 和 python3-venv (Debian/Ubuntu 常见问题)
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3。请先安装 Python 3。"
    echo "在 Debian/Ubuntu 上，您可以运行: sudo apt update && sudo apt install python3"
    exit 1
fi

# 尝试运行一个简单的 python 命令来检查 venv 模块是否存在
if ! python3 -c "import venv" &> /dev/null; then
    echo "错误: 未找到 python3-venv 模块。"
    echo "在 Debian/Ubuntu 上，默认的 python3 安装可能不包含 venv。"
    echo "请运行以下命令安装: sudo apt update && sudo apt install python3-venv"
    exit 1
fi

while true; do
    clear
    echo "=================================================="
    echo "              A1_Nexus 系统启动菜单"
    echo "=================================================="
    echo ""
    echo "  1. 启动全自动流水线 (执行 MESSAGES 中的任务)"
    echo "  2. 检查下一个待执行任务"
    echo "  3. 清理工作区 (为新项目做准备)"
    echo "  4. 退出"
    echo ""
    echo "=================================================="
    read -p "请输入选项 (1-4): " choice

    case $choice in
        1)
            clear
            echo "正在启动全自动流水线..."
            python3 SYSTEM/auto_setup.py --auto
            read -p "按回车键继续..."
            ;;
        2)
            clear
            echo "正在检查下一个任务..."
            python3 SYSTEM/check_next.py
            read -p "按回车键继续..."
            ;;
        3)
            clear
            python3 SYSTEM/cleanup_workspace.py
            read -p "按回车键继续..."
            ;;
        4)
            echo "退出系统。"
            exit 0
            ;;
        *)
            echo "无效选项，请重新输入。"
            read -p "按回车键继续..."
            ;;
    esac
done
