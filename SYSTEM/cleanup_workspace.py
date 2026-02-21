import os
import shutil
import datetime

def cleanup_workspace():
    print("==================================================")
    print("        A1_Nexus 工作区清理与归档工具")
    print("==================================================")
    print("警告：此操作将清理当前工作区，为新项目做准备。")
    print("请确保您已经将 PROJECT_SPACE 中的重要产出物保存或移走！\n")
    
    confirm = input("您确定要继续清理吗？(y/n): ")
    if confirm.lower() != 'y':
        print("清理已取消。")
        return

    # 1. 归档 ARCHIVE 目录
    archive_dir = "ARCHIVE"
    if os.path.exists(archive_dir) and os.listdir(archive_dir):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_folder = f"ARCHIVE_BACKUP_{timestamp}"
        os.rename(archive_dir, backup_folder)
        os.makedirs(archive_dir)
        print(f"[成功] 旧任务已归档至: {backup_folder}")
    else:
        print("[跳过] ARCHIVE 目录为空，无需归档。")

    # 2. 清空 MESSAGES 目录
    messages_dir = "MESSAGES"
    if os.path.exists(messages_dir):
        for filename in os.listdir(messages_dir):
            file_path = os.path.join(messages_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"[错误] 无法删除 {file_path}. 原因: {e}")
        print(f"[成功] MESSAGES 目录已清空。")

    # 3. 提示清理 PROJECT_SPACE
    project_space = "PROJECT_SPACE"
    if os.path.exists(project_space) and os.listdir(project_space):
        print(f"\n[注意] PROJECT_SPACE 目录中仍有文件。")
        clean_ps = input("是否要一并清空 PROJECT_SPACE 目录？(y/n): ")
        if clean_ps.lower() == 'y':
            # 备份 PROJECT_SPACE
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_folder = f"PROJECT_BACKUP_{timestamp}"
            try:
                shutil.copytree(project_space, backup_folder)
                print(f"[成功] PROJECT_SPACE 已备份至: {backup_folder}")
            except Exception as e:
                print(f"[错误] 备份 PROJECT_SPACE 失败: {e}")
                print("为安全起见，取消清理 PROJECT_SPACE。")
                return

            for filename in os.listdir(project_space):
                file_path = os.path.join(project_space, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"[错误] 无法删除 {file_path}. 原因: {e}")
            print(f"[成功] PROJECT_SPACE 目录已清空。")
        else:
            print("[跳过] PROJECT_SPACE 目录保留。")

    print("\n==================================================")
    print("清理完成！系统已准备好迎接下一个项目。")
    print("==================================================")

if __name__ == "__main__":
    cleanup_workspace()
