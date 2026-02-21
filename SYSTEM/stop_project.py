import os
from pathlib import Path

def stop_project():
    """创建一个停止信号文件，让正在运行的 Nexus 系统安全退出"""
    stop_file = Path("SYSTEM/stop_signal.txt")
    
    try:
        # 确保 SYSTEM 目录存在
        stop_file.parent.mkdir(exist_ok=True)
        
        # 创建信号文件
        with open(stop_file, "w", encoding="utf-8") as f:
            f.write("STOP")
            
        print("✅ 已发送停止信号！")
        print("正在运行的 Nexus 系统（包括全自动模式）将在完成当前任务后安全退出。")
        
    except Exception as e:
        print(f"❌ 发送停止信号失败: {e}")

if __name__ == "__main__":
    stop_project()
