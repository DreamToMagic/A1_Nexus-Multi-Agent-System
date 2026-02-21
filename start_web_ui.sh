#!/bin/bash

echo "========================================="
echo "    🚀 启动 A1_Nexus Web UI 控制台"
echo "========================================="

# 检查虚拟环境
if [ ! -f ".venv/bin/python" ]; then
    echo "[提示] 首次运行，正在初始化环境..."
    python3 SYSTEM/auto_setup.py
fi

# 启动 Web UI
echo "[提示] 正在启动 Web 服务，请稍候..."
.venv/bin/python SYSTEM/web_ui.py
