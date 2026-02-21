import os
import sys
import yaml
import re
import glob
from pathlib import Path
import logging
import argparse

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.tree import Tree
    from rich.progress import Progress, SpinnerColumn, TextColumn
    import questionary
    from openai import OpenAI
except ImportError:
    print("错误: 缺少依赖库。请使用 auto_setup.py 启动。")
    exit(1)

# 初始化 Rich 控制台
# 强制设置标准输出编码为 utf-8，解决 Windows 下打印 emoji 报错的问题
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
console = Console()

class ConfigManager:
    """管理配置文件读取与模型供应选择"""
    def __init__(self, config_file="config.yaml"):
        # 兼容在根目录运行的情况
        if not os.path.exists(config_file):
            config_file = os.path.join("SYSTEM", "config.yaml")
            if not os.path.exists(config_file):
                config_file = os.path.join("A1_Nexus_Improved", "config.yaml")
        with open(config_file, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        
    def get_provider_config(self, role_name):
        """根据角色获取对应的 API 提供商配置和模型"""
        # 1. 检查是否有角色重写
        overrides = self.config.get("role_overrides", {})
        provider_name = self.config["api_providers"]["default"]
        
        # 处理角色名 (例如 "P7-研发" 或 "P8-技术")
        for key, value in overrides.items():
            if key in role_name:
                provider_name = value.get("provider", provider_name)
                break
                
        provider_cfg = self.config["api_providers"]["providers"][provider_name]
        
        # 获取模型
        model_name = provider_cfg["models"]["default"]
        for key, value in overrides.items():
            if key in role_name and "model" in value:
                model_name = value["model"]
                break
                
        return provider_name, provider_cfg, model_name

    def get_all_models(self):
        """获取所有可用的模型列表，用于用户选择"""
        models = []
        for provider_name, provider_cfg in self.config["api_providers"]["providers"].items():
            # 尝试从 API 动态拉取模型列表
            api_key = provider_cfg.get("api_key", "")
            base_url = provider_cfg.get("base_url", "")
            
            if api_key and "YOUR_" not in api_key:
                try:
                    client = OpenAI(api_key=api_key, base_url=base_url)
                    api_models = client.models.list()
                    for model in api_models.data:
                        models.append({
                            "provider": provider_name,
                            "model_id": model.id,
                            "display": f"[{provider_name}] {model.id} (API)"
                        })
                    continue # 如果成功拉取，则跳过本地配置的模型
                except Exception as e:
                    console.print(f"[dim]无法从 {provider_name} 动态拉取模型列表: {e}，将使用本地配置。[/dim]")
            
            # 如果动态拉取失败或未配置 API Key，则使用本地配置的模型
            for model_key, model_id in provider_cfg.get("models", {}).items():
                models.append({
                    "provider": provider_name,
                    "model_id": model_id,
                    "display": f"[{provider_name}] {model_id}"
                })
        return models

class NexusEngine:
    """自动调度核心引擎"""
    def __init__(self, auto_mode=False):
        self.auto_mode = auto_mode
        self.config_mgr = ConfigManager()
        self.messages_dir = Path(self.config_mgr.config["system"]["messages_dir"])
        self.archive_dir = Path(self.config_mgr.config["system"]["archive_dir"])
        self.project_space_dir = Path(self.config_mgr.config["system"].get("project_space_dir", "PROJECT_SPACE"))
        self.personas_dir = Path("PERSONAS")
        self.ensure_directories()
        
    def ensure_directories(self):
        self.messages_dir.mkdir(exist_ok=True)
        self.archive_dir.mkdir(exist_ok=True)
        self.project_space_dir.mkdir(exist_ok=True)
        
    def parse_tasks(self):
        """解析 MESSAGES 目录中的所有任务和依赖关系"""
        tasks = []
        for file_path in self.messages_dir.glob("*.md"):
            filename = file_path.name
            
            # 解析文件名 [NEW]P1_TO_P8-技术_ID001_xxx.md (兼容忘记写状态的情况)
            match = re.match(r'^(?:\[(.*?)\])?(.*?)_TO_(.*?)_(.*)$', filename)
            if not match:
                continue
                
            status, sender, receiver, rest = match.groups()
            if not status:
                status = "NEW"
            
            # 尝试提取 ID
            id_match = re.search(r'(ID\d+)', rest)
            task_id = id_match.group(1) if id_match else rest.split('_')[0]
            
            # 读取文件内容寻找依赖声明: DEPENDS_ON: ID001, ID002
            depends_on = []
            content = ""
            file_encoding = "utf-8"
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, "r", encoding="gbk") as f:
                        content = f.read()
                        file_encoding = "gbk"
                except Exception as e:
                    console.print(f"[red]读取文件 {filename} 失败: {e}[/red]")
                    continue
            except Exception as e:
                console.print(f"[red]读取文件 {filename} 失败: {e}[/red]")
                continue
                
            deps_match = re.search(r'DEPENDS_ON:\s*([^\n]+)', content)
            if deps_match:
                # 分割逗号，去除空格和星号
                depends_on = [d.strip(" *") for d in deps_match.group(1).split(",") if d.strip(" *") and d.strip(" *").upper() != "NONE"]
            
            tasks.append({
                "id": task_id,
                "file": file_path,
                "filename": filename,
                "status": status,
                "sender": sender,
                "receiver": receiver,
                "depends_on": depends_on,
                "content": content,
                "encoding": file_encoding
            })
        return tasks

    def draw_dag(self, tasks):
        """使用 Rich 树状图渲染任务依赖 DAG"""
        tree = Tree("📋 [bold blue]A1 任务执行流 (DAG)[/bold blue]")
        
        # 建立按 ID 索引的字典
        task_dict = {t["id"]: t for t in tasks}
        
        def format_node(t):
            color = "white"
            icon = "⚪"
            if "DONE" in t["status"].upper():
                color = "green"
                icon = "🟢"
            elif "NEW" in t["status"].upper():
                color = "yellow"
                icon = "🟡"
            elif "FAIL" in t["status"].upper():
                color = "red"
                icon = "🔴"
            elif "READ" in t["status"].upper():
                color = "cyan"
                icon = "🔵"
                
            return f"{icon} [{color}][{t['status']}] {t['receiver']} - {t['id']}[/{color}]"

        # 找出顶层任务 (没有依赖，或者依赖的任务不在当前列表中)
        top_tasks = []
        for t in tasks:
            is_top = True
            for dep in t["depends_on"]:
                if dep in task_dict:
                    is_top = False
                    break
            if is_top:
                top_tasks.append(t)
                
        def add_children(node, current_task):
            # 找到所有依赖于 current_task 的任务
            for t in tasks:
                if current_task["id"] in t["depends_on"]:
                    child_node = node.add(format_node(t))
                    add_children(child_node, t)
                    
        for t in top_tasks:
            node = tree.add(format_node(t))
            add_children(node, t)
            
        console.print(Panel(tree, title="调度引擎状态图", border_style="blue"))

    def get_runnable_tasks(self, tasks):
        """获取当前可执行的任务 (状态为NEW且依赖已全部DONE)"""
        runnable = []
        task_status_dict = {t["id"]: t["status"] for t in tasks}
        
        # 获取已归档的任务ID列表
        archived_ids = set()
        for file_path in self.archive_dir.glob("*.md"):
            match = re.match(r'^(?:\[(.*?)\])?(.*?)_TO_(.*?)_(.*)$', file_path.name)
            if match:
                rest = match.group(4)
                id_match = re.search(r'(ID\d+)', rest)
                if id_match:
                    archived_ids.add(id_match.group(1))
                else:
                    archived_ids.add(rest.split('_')[0])
        
        for t in tasks:
            if t["status"] != "NEW":
                continue
                
            can_run = True
            for dep in t["depends_on"]:
                # 如果依赖的任务在归档目录中，说明已经 DONE
                if dep in archived_ids:
                    continue
                # 如果依赖的任务不在列表中，或者状态不是 DONE，则阻塞
                if dep not in task_status_dict or "DONE" not in task_status_dict[dep].upper():
                    can_run = False
                    break
            if can_run:
                runnable.append(t)
                
        return runnable

    def execute_task(self, task):
        """执行具体的任务: 调用大模型并保存结果"""
        console.print(f"\n[bold yellow]>>> 开始执行任务: {task['id']} (由 {task['receiver']} 负责)[/bold yellow]")
        
        # 1. 寻找对应的角色身份卡 (Persona)
        persona_content = ""
        # 匹配角色卡：提取角色级别（如 P7, P8）
        receiver_level = task['receiver'].split('-')[0].upper() if '-' in task['receiver'] else task['receiver'].upper()
        
        # 优先精确匹配全名，其次匹配级别前缀
        best_match_file = None
        exact_name = task['receiver'].replace('-', '_').upper()
        
        # 1. 完全精确匹配 (不含扩展名)
        for p_file in self.personas_dir.glob("*.md"):
            if p_file.stem.upper() == exact_name:
                best_match_file = p_file
                break
                
        # 2. 前缀匹配
        if not best_match_file:
            for p_file in self.personas_dir.glob("*.md"):
                if p_file.stem.upper().startswith(exact_name + "_") or p_file.stem.upper().startswith(exact_name):
                    best_match_file = p_file
                    break
                    
        # 3. 级别通用卡匹配
        if not best_match_file:
            for p_file in self.personas_dir.glob("*.md"):
                if p_file.stem.upper().startswith(receiver_level + "_"):
                    best_match_file = p_file
                    break
                
        if best_match_file:
            with open(best_match_file, "r", encoding="utf-8") as f:
                persona_content = f.read()
        else:
            console.print(f"[yellow]⚠️ 警告: 未找到匹配 {task['receiver']} 的角色身份卡，将使用通用设定。[/yellow]")
            persona_content = f"你是 {task['receiver']}。请根据公司制度总纲执行以下任务。严禁废话。"

        # 2. 读取必要的上下文 (总纲和看板)
        try:
            with open("公司制度总纲.md", "r", encoding="utf-8") as f:
                manifesto = f.read()
            with open("项目看板.md", "r", encoding="utf-8") as f:
                dashboard = f.read()
        except Exception:
            manifesto, dashboard = "", ""

        # 3. 组装 System Prompt
        system_prompt = f"""
{persona_content}

========== 核心协议强制提醒 ==========
{manifesto}

========== 当前看板状态 ==========
{dashboard}

========== 目录结构上下文 ==========
当前 PROJECT_SPACE 目录结构如下：
"""
        # 注入 PROJECT_SPACE 目录结构作为上下文
        project_space_files = list(self.project_space_dir.rglob("*"))
        if project_space_files:
            for p in project_space_files:
                if p.is_file():
                    system_prompt += f"- {p.relative_to(self.project_space_dir)}\n"
        else:
            system_prompt += "(空)\n"
        system_prompt += "\n"
        
        # 4. 获取 API 配置并初始化 Client
        provider_name, provider_cfg, model_name = self.config_mgr.get_provider_config(task['receiver'])
        
        # 4.1 提示用户确认或切换模型
        console.print(f"\n[bold cyan]🤖 默认分配模型:[/bold cyan] [green]{provider_name} -> {model_name}[/green]")
        
        all_models = self.config_mgr.get_all_models()
        model_choices = [m["display"] for m in all_models]
        
        # 找到默认模型在列表中的索引
        # 优先匹配动态拉取的模型，其次匹配本地配置的模型
        default_display_api = f"[{provider_name}] {model_name} (API)"
        default_display_local = f"[{provider_name}] {model_name}"
        
        default_display = default_display_local
        default_index = 0
        
        if default_display_api in model_choices:
            default_display = default_display_api
            default_index = model_choices.index(default_display_api)
        elif default_display_local in model_choices:
            default_display = default_display_local
            default_index = model_choices.index(default_display_local)
        elif len(model_choices) > 0:
            # 如果默认模型不在列表中，默认选择第一个
            default_display = model_choices[0]
            default_index = 0
            
        if self.auto_mode:
            selected_model_display = default_display
            console.print(f"[dim]自动模式: 已自动选择默认模型 {selected_model_display}[/dim]")
        else:
            selected_model_display = questionary.select(
                f"请确认 {task['receiver']} 使用的模型 (可上下选择切换):",
                choices=model_choices,
                default=model_choices[default_index]
            ).ask()
            
            if not selected_model_display:
                console.print("[yellow]已取消任务执行。[/yellow]")
                return False
            
        # 解析用户选择的模型
        selected_model_info = next((m for m in all_models if m["display"] == selected_model_display), None)
        if not selected_model_info:
            console.print(f"[red]❌ 错误: 无法找到选定的模型信息: {selected_model_display}[/red]")
            return False
        provider_name = selected_model_info["provider"]
        model_name = selected_model_info["model_id"]
        provider_cfg = self.config_mgr.config["api_providers"]["providers"][provider_name]

        if "YOUR_" in provider_cfg["api_key"]:
            console.print(f"[red]❌ 错误: 您尚未在 config.yaml 中配置 {provider_name} 的 API Key！[/red]")
            # 如果是自动模式，遇到 API Key 错误应该退出，避免死循环
            if self.auto_mode:
                console.print("[red]自动模式下遇到 API Key 错误，系统退出。[/red]")
                sys.exit(1)
            return False
            
        client = OpenAI(
            api_key=provider_cfg["api_key"],
            base_url=provider_cfg["base_url"]
        )

        console.print(f"📡 正在连接 [cyan]{provider_name}[/cyan] API (模型: [green]{model_name}[/green])...")

        # 5. 发起请求并展示进度动画 (带重试机制)
        response_text = ""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                desc = f"AI [{task['receiver']}] 正在思考与编码中..."
                if retry_count > 0:
                    desc += f" (重试 {retry_count}/{max_retries-1})"
                progress.add_task(description=desc, total=None)
                
                try:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"请处理以下任务文件内容：\n\n{task['content']}"}
                        ],
                        temperature=0.2 # 编程任务偏向确定性
                    )
                    response_text = response.choices[0].message.content
                    
                    # 尝试获取 Token 消耗 (不同提供商返回结构可能略有不同)
                    if hasattr(response, 'usage') and response.usage:
                        tokens = response.usage.total_tokens
                        console.print(f"[dim]💡 消耗 Token 数量: ~{tokens}[/dim]")
                    
                    break # 成功则跳出重试循环
                        
                except Exception as e:
                    retry_count += 1
                    console.print(f"[yellow]请求 API 失败 ({retry_count}/{max_retries}): {e}[/yellow]")
                    if retry_count >= max_retries:
                        console.print(f"[red]❌ 达到最大重试次数，任务执行失败。[/red]")
                        return False
                    import time
                    time.sleep(2) # 失败后等待2秒再试

        # 6. 交互审批
        console.print(Panel(response_text[:500] + "\n...\n(内容已截断)", title=f"{task['receiver']} 的输出预览", border_style="green"))
        
        if self.auto_mode:
            action = "1. 接受并写入文件 (标记为 [DONE])"
            console.print("[dim]自动模式: 已自动接受并写入文件[/dim]")
        else:
            action = questionary.select(
                "审批上述产出：",
                choices=[
                    "1. 接受并写入文件 (标记为 [DONE])",
                    "2. 打回重做 (不保存)",
                    "3. 接受并写入文件，但需人工修改后再标记 [DONE]"
                ]
            ).ask()

        if action and action.startswith("1"):
            # 将新内容追加到文件中，并修改文件名为 [DONE]
            # 使用读取时记录的编码
            file_encoding = task.get('encoding', 'utf-8')
            with open(task['file'], "a", encoding=file_encoding) as f:
                f.write("\n\n---\n## AI 执行结果:\n")
                f.write(response_text)
            
            # 只替换开头的状态标签，如果没有状态标签则添加
            if re.match(r'^\[.*?\]', task['filename']):
                new_filename = re.sub(r'^\[.*?\]', '[DONE]', task['filename'])
            else:
                new_filename = f"[DONE]{task['filename']}"
                
            new_path = self.messages_dir / new_filename
            os.rename(task['file'], new_path)
            console.print(f"✅ 文件已更新并重命名为: {new_filename}")
            
            # 自动模式下，执行完一个任务后返回 True，让主循环继续
            return True
            
        elif action and action.startswith("3"):
            file_encoding = task.get('encoding', 'utf-8')
            with open(task['file'], "a", encoding=file_encoding) as f:
                f.write("\n\n---\n## AI 执行结果 (待人工复核):\n")
                f.write(response_text)
            console.print("⚠️ 内容已追加，但未更改文件状态。请人工修改后重命名文件。")
            return True
        else:
            console.print("❌ 任务被打回，文件保持 [NEW] 状态。")
            return False

    def archive_done_tasks(self):
        """P9 归档逻辑：将所有 [DONE] 状态的任务移动到 ARCHIVE 目录"""
        archived_count = 0
        for file_path in self.messages_dir.glob("*.md"):
            if file_path.name.startswith("[DONE]"):
                dest_path = self.archive_dir / file_path.name
                try:
                    os.rename(file_path, dest_path)
                    archived_count += 1
                except Exception as e:
                    console.print(f"[red]归档文件 {file_path.name} 失败: {e}[/red]")
        
        if archived_count > 0:
            console.print(f"[dim]🧹 P9 审计完成: 已将 {archived_count} 个 [DONE] 任务归档至 {self.archive_dir.name}/ 目录。[/dim]")

    def check_stop_signal(self):
        """检查是否存在停止信号文件"""
        stop_file = Path("SYSTEM/stop_signal.txt")
        if stop_file.exists():
            console.print("\n[bold red]🛑 检测到停止信号 (stop_signal.txt)，系统正在安全退出...[/bold red]")
            try:
                stop_file.unlink() # 退出前删除信号文件
            except Exception:
                pass
            return True
        return False

    def run(self):
        """主循环"""
        console.print("\n[bold magenta]A1_Nexus 全自动调度系统已启动[/bold magenta]")
        console.print("[dim]提示: 在 SYSTEM 目录下创建 stop_signal.txt 文件可安全停止系统[/dim]")
        
        while True:
            # 检查停止信号
            if self.check_stop_signal():
                break

            # 执行 P9 归档逻辑
            self.archive_done_tasks()
            
            tasks = self.parse_tasks()
            
            if not tasks:
                console.print("[dim]当前 MESSAGES 目录为空，暂无任务。[/dim]")
                break
                
            self.draw_dag(tasks)
            
            runnable_tasks = self.get_runnable_tasks(tasks)
            if not runnable_tasks:
                console.print("[yellow]当前没有可以立即执行的任务。可能都在等待前置依赖完成。[/yellow]")
                break
                
            console.print(f"\n找到 [bold green]{len(runnable_tasks)}[/bold green] 个可开工任务。")
            
            if self.auto_mode:
                target_task = runnable_tasks[0]
                console.print(f"[dim]自动模式: 自动选择任务 {target_task['id']} ({target_task['receiver']})[/dim]")
                success = self.execute_task(target_task)
                if not success:
                    console.print("[red]自动模式下任务执行失败，系统退出。[/red]")
                    break
            else:
                task_choices = [f"{t['id']} ({t['receiver']})" for t in runnable_tasks]
                task_choices.append("退回终端 (Exit)")
                
                selected = questionary.select(
                    "请选择要调度执行的任务：",
                    choices=task_choices
                ).ask()
                
                if not selected or selected == "退回终端 (Exit)":
                    break
                    
                # 获取选中的任务
                selected_id = selected.split(" ")[0]
                target_task = next((t for t in runnable_tasks if t['id'] == selected_id), None)
                
                if target_task:
                    self.execute_task(target_task)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A1_Nexus 自动调度系统")
    parser.add_argument("--auto", action="store_true", help="启用全自动模式，无需人工干预")
    args = parser.parse_args()
    
    try:
        engine = NexusEngine(auto_mode=args.auto)
        engine.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]已退出调度控制台。[/yellow]")
