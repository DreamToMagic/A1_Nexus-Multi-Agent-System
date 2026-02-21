import os
import sys
import subprocess
import venv
from pathlib import Path

# 强制设置标准输出编码为 utf-8，解决 Windows 下打印 emoji 报错的问题
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 虚拟环境目录名称
VENV_DIR = ".venv"
REQUIREMENTS = ["rich", "questionary", "openai", "pyyaml", "gradio"]

def is_in_venv():
    """判断当前是否已在虚拟环境中"""
    return hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)

def get_venv_python():
    """获取虚拟环境中的 python 可执行文件路径"""
    if os.name == 'nt':
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:
        return os.path.join(VENV_DIR, "bin", "python")

def setup():
    print("=========================================")
    print("    🚀 A1_Nexus 环境自检与初始化模块")
    print("=========================================")

    # 1. 检查并创建虚拟环境
    if not os.path.exists(VENV_DIR):
        print(">> 未检测到虚拟环境，正在为您创建独立隔离环境 (.venv)...")
        try:
            venv.create(VENV_DIR, with_pip=True)
            print("   ✅ 虚拟环境创建成功！")
        except Exception as e:
            print(f"   ❌ 创建虚拟环境失败: {e}")
            sys.exit(1)
    else:
        print(">> 虚拟环境已存在。")

    venv_python = get_venv_python()
    if not os.path.exists(venv_python):
        print(f"❌ 虚拟环境损坏，找不到可执行文件: {venv_python}")
        print("建议删除 .venv 文件夹后重新运行本脚本。")
        sys.exit(1)

    # 2. 自动安装依赖
    print(">> 正在检测并安装必须的依赖库 (rich, questionary, openai, pyyaml)...")
    try:
        # 使用虚拟环境的 python -m pip，避免 pip.exe 路径硬编码导致的 Fatal error in launcher
        pip_cmd = [venv_python, "-m", "pip"]
        
        # 检查是否已经安装了依赖，避免每次都运行 pip install
        try:
            import rich
            import questionary
            import openai
            import yaml
            import gradio
            print("   ✅ 依赖包已安装！")
        except ImportError:
            subprocess.check_call(pip_cmd + ["install", "--quiet"] + REQUIREMENTS)
            print("   ✅ 依赖包安装完成！")
    except subprocess.CalledProcessError as e:
        print(f"   ❌ 依赖安装失败，错误码: {e.returncode}")
        sys.exit(1)

    print("=========================================")
    print("环境准备就绪！")
    print("正在为您启动 A1_Nexus 控制台...\n")

    # 3. 启动主程序
    # 兼容在根目录运行的情况
    main_script = "SYSTEM/nexus_core.py"
    if not os.path.exists(main_script):
        print(f"❌ 找不到核心引擎脚本: {main_script}")
        sys.exit(1)

    try:
        # 使用虚拟环境的 python 启动核心脚本
        # 传递所有参数，包括 --auto
        subprocess.call([venv_python, main_script] + sys.argv[1:])
    except KeyboardInterrupt:
        print("\n>> 您已手动终止调度系统。")

if __name__ == "__main__":
    setup()
