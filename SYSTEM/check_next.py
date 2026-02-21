import os
import re
import sys
from pathlib import Path

# 强制设置标准输出编码为 utf-8，解决 Windows 下打印 emoji 报错的问题
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("============================================================")
    print("🔍 极简流 - 任务流转分析器 (Task Flow Analyzer)")
    print("============================================================")

    messages_dir = Path("MESSAGES")
    if not messages_dir.is_dir():
        print("❌ 错误: MESSAGES 目录不存在！请确保你在项目根目录。")
        return

    print("[1] 分析 MESSAGES 目录中的待处理任务...")
    print("------------------------------------------------------------")

    has_tasks = False
    for file_path in messages_dir.glob("*.md"):
        if not file_path.is_file():
            continue

        has_tasks = True
        filename = file_path.name
        
        # 提取状态前缀：例如 [NEW], [READ], [DONE], [FAIL], 等
        status_match = re.match(r'^(\[.*?\])', filename)
        status = status_match.group(1) if status_match else "无状态"
        
        # 提取接收者 (TO_后面的部分直到下划线)
        receiver_match = re.search(r'TO_([^_]+)_', filename)
        receiver = receiver_match.group(1) if receiver_match else "未知接收者"

        print(f"📄 文件名: {filename}")
        print(f"  -> 状态标签: {status}")

        if status == "[NEW]" or status == "无状态" or not status.startswith("["):
            print(f"  => 🔴 [等待接管] 下一步请切换到 【{receiver}】 处理该任务！")
        elif "+1" in status or "[READ]" in status:
            print(f"  => 🟡 [执行中/迭代] 需要 【{receiver}】 继续处理，或原发送者确认。")
        elif "[DONE]" in status:
            print(f"  => 🟢 [已完成] 任务已完成，等待 P1-Nexus 合并，或 P9 归档。")
        elif "+2" in status:
            print(f"  => 🗑️ [等待清理] 二次迭代已完成，等待 P9-行政 进行 GC 垃圾回收。")
        elif "[FAIL]" in status:
            print(f"  => 💥 [熔断警告] 任务多次失败！需要上级重新评估并下发新任务。")
            
        print("------------------------------------------------------------")

    if not has_tasks:
        print("📁 MESSAGES 目录当前为空。")
        print("💡 提示: 项目处于初始状态或全部任务已归档。")
        print("=> 下一步: 董事长(User) 需要向 P1-Nexus 下发新的 [NEW] 指令。")

    print("============================================================")
    print("🎯 看板动态提示 (参考用):")
    
    # 尝试在当前目录和父目录查找项目看板
    dashboard_path = Path("项目看板.md")
    if not dashboard_path.is_file():
        dashboard_path = Path("SYSTEM/DOCS/项目看板.md")
    if dashboard_path.is_file():
        try:
            with open(dashboard_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                found = False
                for i, line in enumerate(lines):
                    if "🎯 当前执行建议" in line:
                        print(f"> {line.strip()}")
                        if i + 1 < len(lines):
                            print(f"> {lines[i+1].strip()}")
                        found = True
                        break
                if not found:
                    print("> (看板中未找到执行建议)")
        except Exception as e:
            print(f"> (读取 项目看板.md 失败: {e})")
    else:
        print("> (未找到 项目看板.md)")
        
    print("============================================================")

if __name__ == "__main__":
    main()
