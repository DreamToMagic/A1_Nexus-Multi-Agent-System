import os
import sys
import gradio as gr
from pathlib import Path
import threading
import time
import re
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入核心引擎
from nexus_core import NexusEngine, ConfigManager

# 初始化引擎
engine = NexusEngine(auto_mode=True)
config_mgr = ConfigManager()

def get_system_status():
    """获取系统当前状态"""
    tasks = engine.parse_tasks()
    
    # 统计任务状态
    total = len(tasks)
    done = sum(1 for t in tasks if "DONE" in t["status"].upper())
    new = sum(1 for t in tasks if "NEW" in t["status"].upper())
    
    # 获取归档任务数
    archived = len(list(engine.archive_dir.glob("*.md")))
    
    status_text = f"📊 **系统状态**: 共 {total} 个活跃任务 | ✅ 已完成: {done} | ⏳ 待执行: {new} | 📦 已归档: {archived}"
    return status_text

def get_task_list():
    """获取任务列表用于展示"""
    tasks = engine.parse_tasks()
    if not tasks:
        return "当前没有活跃任务。"
        
    markdown_list = "### 📋 任务看板\n\n"
    markdown_list += "| 状态 | 任务 ID | 接收者 | 依赖项 | 文件名 |\n"
    markdown_list += "|---|---|---|---|---|\n"
    
    for t in tasks:
        status_icon = "🟢" if "DONE" in t["status"].upper() else "🟡"
        deps = ", ".join(t["depends_on"]) if t["depends_on"] else "无"
        markdown_list += f"| {status_icon} {t['status']} | **{t['id']}** | {t['receiver']} | {deps} | `{t['filename']}` |\n"
        
    return markdown_list

def run_one_step():
    """执行一步任务"""
    engine.archive_done_tasks()
    tasks = engine.parse_tasks()
    
    if not tasks:
        return "✅ 当前没有任务需要执行。"
        
    runnable_tasks = engine.get_runnable_tasks(tasks)
    if not runnable_tasks:
        return "⏳ 当前没有可立即执行的任务（可能都在等待前置依赖完成）。"
        
    target_task = runnable_tasks[0]
    log_msg = f"🚀 正在执行任务: **{target_task['id']}** (由 {target_task['receiver']} 负责)...\n\n"
    
    # 捕获标准输出以显示在 UI 中
    import io
    from contextlib import redirect_stdout
    
    f = io.StringIO()
    with redirect_stdout(f):
        success = engine.execute_task(target_task)
        
    output = f.getvalue()
    
    # 记录工作历史
    re d_work_history(target_task, success)
    
    if success:
        return log_msg + "✅ 任务执行成功！\n\n" + "```text\n" + output + "\n```"
    else:
        return log_msg + "❌ 任务执行失败。\n\n" + "```text\n" + output + "\n```"

# 全局变量控制自动运行状态
auto_run_flag = False

def toggle_auto_run():
    """切换自动运行状态"""
    global auto_run_flag
    auto_run_flag = not auto_run_flag
    if auto_run_flag:
        return "⏸️ 暂停自动执行", "🚀 自动流水线已启动..."
    else:
        return "🚀 一键全自动执行", "⏸️ 自动流水线已暂停。"

def auto_run_all(progress=gr.Progress()):
    """全自动执行所有任务"""
    global auto_run_flag
    if not auto_run_flag:
        yield "⏸️ 自动流水线已暂停。"
        return
        
    log_output = "🚀 开始全自动流水线...\n\n"
    yield log_output
    
    while auto_run_flag:
        engine.archive_done_tasks()
        tasks = engine.parse_tasks()
        
        if not tasks:
            log_output += "✅ 所有任务已完成！\n"
            auto_run_flag = False
            yield log_output
            break
            
        runnable_tasks = engine.get_runnable_tasks(tasks)
        if not runnable_tasks:
            log_output += "⏳ 没有可执行的任务，流水线停止。\n"
            auto_run_flag = False
            yield log_output
            break
            
        target_task = runnable_tasks[0]
        progress(0, desc=f"正在执行: {target_task['id']}")
        
        log_output += f"▶️ 执行任务: {target_task['id']} ({target_task['receiver']})\n"
        yield log_output
        
        # 捕获输出
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            success = engine.execute_task(target_task)
            
        output = f.getvalue()
        
        if not success:
            log_output += f"❌ 任务执行失败，流水线中止。\n\n{output}\n"
            auto_run_flag = False
            yield log_output
            break
            
        log_output += f"✅ 任务完成。\n\n{output}\n"
        yield log_output
        
        # 记录工作历史
        record_work_history(target_task, success)
        
        time.sleep(1) # 稍微暂停一下，避免 API 频率过高

def get_work_history():
    """获取工作历史记录"""
    history_file = Path("SYSTEM/work_history.json")
    if not history_file.exists():
        return []
    try:
        import json
        with open(history_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def record_work_history(task, success):
    """记录工作历史"""
    history_file = Path("SYSTEM/work_history.json")
    history = get_work_history()
    
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    record = {
        "time": now,
        "task_id": task.get("id", "Unknown"),
        "receiver": task.get("receiver", "Unknown"),
        "status": "Success" if success else "Failed",
        "filename": task.get("filename", "Unknown")
    }
    
    history.insert(0, record) # 插入到最前面
    # 保留最近 100 条记录
    history = history[:100]
    
    try:
        import json
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"记录工作历史失败: {e}")

def format_history_direct():
    """直接格式化历史记录"""
    history = get_work_history()
    if not history:
        return "暂无工作记录。"
        
    md = "### 📋 原始工作记录\n\n"
    md += "| 时间 | 任务 ID | 执行者 | 状态 | 文件名 |\n"
    md += "|---|---|---|---|---|\n"
    
    for r in history:
        status_icon = "✅" if r["status"] == "Success" else "❌"
        md += f"| {r['time']} | **{r['task_id']}** | {r['receiver']} | {status_icon} {r['status']} | `{r['filename']}` |\n"
        
    return md

def format_history_translated(progress=gr.Progress()):
    """AI 翻译历史记录为人话"""
    history = get_work_history()
    if not history:
        return "暂无工作记录。"
        
    progress(0, desc="正在调用 AI 翻译工作记录...")
    
    # 取最近 10 条记录进行翻译，避免 token 过多
    recent_history = history[:10]
    import json
    history_str = json.dumps(recent_history, ensure_ascii=False, indent=2)
    
    system_prompt = """你是一个通俗易懂的项目汇报助手。
请将以下 JSON 格式的系统工作记录，翻译成一段连贯、易懂的“人话”汇报。
让不懂技术的用户也能明白系统刚才做了什么。
例如：“在下午3点，技术主管成功完成了基础框架的搭建（任务ID001）...”
请直接输出汇报内容，不要包含任何多余的解释。"""

    provider_name, provider_cfg, model_name = config_mgr.get_provider_config("P1_Nexus")
    
    from openai import OpenAI
    client = OpenAI(
        api_key=provider_cfg["api_key"],
        base_url=provider_cfg["base_url"]
    )
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请翻译以下记录：\n\n{history_str}"}
            ],
            temperature=0.5
        )
        
        progress(1.0, desc="翻译完成！")
        return f"### 🗣️ AI 汇报 (最近 10 条)\n\n{response.choices[0].message.content}"
    except Exception as e:
        return f"❌ 翻译失败: {e}\n\n请检查 API 配置或网络连接。"

def create_new_task(receiver, task_desc, depends_on, task_id=None):
    """创建一个新任务"""
    if not receiver or not task_desc:
        return "❌ 接收者和任务描述不能为空！"
        
    # 生成任务 ID
    if not task_id:
        tasks = engine.parse_tasks()
        existing_ids = [int(re.search(r'\d+', t['id']).group()) for t in tasks if re.search(r'\d+', t['id'])]
        next_id = max(existing_ids) + 1 if existing_ids else 1
        task_id = f"ID{next_id:03d}"
    
    # 格式化依赖
    deps_str = depends_on if depends_on else "NONE"
    
    # 生成文件名
    short_desc = task_desc[:10].replace(" ", "_").replace("\n", "")
    filename = f"[NEW]P1_TO_{receiver}_{task_id}_{short_desc}.md"
    filepath = engine.messages_dir / filename
    
    # 写入文件
    content = f"""# 任务目标：{task_desc.split(chr(10))[0]}

**DEPENDS_ON: {deps_str}**

## 详细要求
{task_desc}
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
        
    return f"✅ 成功创建任务: {filename}"

def auto_breakdown_task(macro_task_desc, progress=gr.Progress()):
    """P1 自动拆解宏观任务为多个子任务"""
    if not macro_task_desc:
        return "❌ 宏观任务描述不能为空！"
        
    progress(0, desc="正在调用 P1 思考拆解方案...")
    
    # 获取当前可用的角色列表
    available_personas = [p.stem for p in engine.personas_dir.glob("*.md")]
    personas_str = ", ".join(available_personas) if available_personas else "P8_技术, P8_文案, P9_行政合规审计"
    
    # 构造 P1 的 Prompt
    system_prompt = f"""你是 P1-首席执行架构师 (Nexus-001)。
你的任务是将用户的宏大目标拆解为多个子任务，下发给各个虚拟员工。
请严格按照以下 JSON 格式输出拆解后的任务列表，不要输出任何其他废话：
[
  {{
    "receiver": "P8_技术主管",
    "depends_on": "NONE",
    "description": "搭建基础框架..."
  }},
  {{
    "receiver": "P8_文案主管",
    "depends_on": "ID001",
    "description": "编写文案..."
  }}
]
注意：
1. receiver 必须是现有的角色名，当前可用的角色有：{personas_str}。
2. depends_on 如果没有依赖填 NONE，如果有依赖填对应的 ID（如 ID001）。ID 是按顺序生成的，第一个任务是 ID001，第二个是 ID002，依此类推。
"""
    
    # 获取 P1 的模型配置
    provider_name, provider_cfg, model_name = config_mgr.get_provider_config("P1_Nexus")
    
    from openai import OpenAI
    client = OpenAI(
        api_key=provider_cfg["api_key"],
        base_url=provider_cfg["base_url"]
    )
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请拆解以下宏观任务：\n\n{macro_task_desc}"}
            ],
            temperature=0.2
        )
        
        result_text = response.choices[0].message.content
        
        # 尝试解析 JSON
        import json
        # 提取 JSON 部分 (防止模型输出带有 markdown 标记)
        json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = result_text
            
        # 进一步清理，确保只包含 JSON 数组
        start_idx = json_str.find('[')
        end_idx = json_str.rfind(']')
        if start_idx != -1 and end_idx != -1:
            json_str = json_str[start_idx:end_idx+1]
            
        tasks_data = json.loads(json_str)
        
        progress(0.5, desc="正在生成任务文件...")
        
        created_files = []
        for i, task_data in enumerate(tasks_data):
            receiver = task_data.get("receiver", "P8_技术")
            depends_on = task_data.get("depends_on", "NONE")
            desc = task_data.get("description", "")
            task_id = task_data.get("id", None)
            
            # 修正依赖 ID (如果模型生成的依赖 ID 不准确，这里可以做一些容错，但目前先信任模型)
            if isinstance(depends_on, list):
                depends_on = ", ".join(depends_on)
            
            res = create_new_task(receiver, desc, depends_on, task_id)
            created_files.append(res)
            
        progress(1.0, desc="拆解完成！")
        return "✅ 自动拆解完成！\n\n" + "\n".join(created_files)
        
    except Exception as e:
        return f"❌ 自动拆解失败: {e}\n\n模型返回内容:\n{result_text if 'result_text' in locals() else '无'}"

def get_config_yaml():
    """读取 config.yaml 内容"""
    config_path = Path("SYSTEM/config.yaml")
    if not config_path.exists():
        config_path = Path("config.yaml")
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return f.read()
    return "配置文件不存在"

def save_config_yaml(content):
    """保存 config.yaml 内容"""
    config_path = Path("SYSTEM/config.yaml")
    if not config_path.exists():
        config_path = Path("config.yaml")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)
        # 重新加载配置
        global config_mgr
        config_mgr = ConfigManager()
        return "✅ 配置保存成功！"
    except Exception as e:
        return f"❌ 保存失败: {e}"

def get_personas_list():
    """获取角色列表"""
    personas = []
    for p_file in engine.personas_dir.glob("*.md"):
        personas.append(p_file.name)
    return personas

def get_persona_content(filename):
    """读取角色文件内容"""
    if not filename:
        return ""
    filepath = engine.personas_dir / filename
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def save_persona_content(filename, content):
    """保存角色文件内容"""
    if not filename:
        return "❌ 请先选择一个角色文件"
    filepath = engine.personas_dir / filename
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ 角色 {filename} 保存成功！"
    except Exception as e:
        return f"❌ 保存失败: {e}"

def create_new_persona(filename, content):
    """创建新角色"""
    if not filename:
        return "❌ 文件名不能为空", gr.update()
    if not filename.endswith(".md"):
        filename += ".md"
    filepath = engine.personas_dir / filename
    if filepath.exists():
        return f"❌ 角色 {filename} 已存在", gr.update()
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ 角色 {filename} 创建成功！", gr.update(choices=get_personas_list(), value=filename)
    except Exception as e:
        return f"❌ 创建失败: {e}", gr.update()

def get_workspace_files():
    """获取工作区文件树"""
    tree_str = "### 📁 PROJECT_SPACE 目录结构\n```text\n"
    
    def build_tree(dir_path, prefix=""):
        nonlocal tree_str
        try:
            items = list(dir_path.iterdir())
            items.sort(key=lambda x: (not x.is_dir(), x.name))
            
            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "
                
                if item.is_dir():
                    tree_str += f"{prefix}{connector}📂 {item.name}/\n"
                    extension = "    " if is_last else "│   "
                    build_tree(item, prefix + extension)
                else:
                    tree_str += f"{prefix}{connector}📄 {item.name}\n"
        except Exception as e:
            tree_str += f"{prefix}└── ❌ 读取错误: {e}\n"
            
    build_tree(engine.project_space_dir)
    tree_str += "```"
    return tree_str

def read_workspace_file(filepath_str):
    """读取工作区文件内容"""
    if not filepath_str:
        return ""
    
    # 简单的安全检查，防止跳出工作区
    filepath = Path(filepath_str)
    if ".." in filepath.parts or filepath.is_absolute():
        return "❌ 非法路径"
        
    full_path = engine.project_space_dir / filepath
    if full_path.exists() and full_path.is_file():
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            return "❌ 无法读取二进制文件或非 UTF-8 编码文件"
        except Exception as e:
            return f"❌ 读取失败: {e}"
    return "❌ 文件不存在"

# 闲聊助手预设
CHAT_PERSONAS = {
    "温柔助手": "你是一个温柔、体贴的AI助手。你现在在一个名为 A1_Nexus 的多智能体协作系统中工作，但你不参与具体的开发任务，你的主要工作是陪伴用户聊天、解闷。你可以看到系统当前的状态，如果用户问起，你可以用通俗易懂、温柔的语气告诉他们。请保持对话轻松愉快。",
    "毒舌程序员": "你是一个资深但非常毒舌的程序员。你现在被迫待在一个名为 A1_Nexus 的多智能体协作系统里当客服。你觉得系统里那些干活的AI（比如P8_技术）都是菜鸟。你说话总是带着嘲讽和傲娇，但其实你还是会回答用户的问题。你可以看到系统状态，如果用户问起，你可以顺便嘲笑一下进度。",
    "中二病患者": "你是一个重度中二病患者。你认为 A1_Nexus 系统是一个封印着无数远古魔神（各个虚拟员工）的魔法阵，而你是守护这个魔法阵的结界师。你说话总是充满奇幻色彩和中二词汇。你可以看到系统状态，并用中二的方式向用户汇报（比如把任务完成说成是'魔物已被讨伐'）。",
    "霸道总裁": "你是一个霸道总裁。A1_Nexus 系统是你名下的一个小产业。你说话总是带着居高临下、霸道但又莫名宠溺的语气。你称呼用户为'女人'或'小家伙'（无论用户性别）。你可以看到系统状态，并用总裁视察工作的口吻向用户汇报。"
}

def chat_with_assistant(message, history, persona_name):
    """闲聊助手对话逻辑"""
    if not message:
        return "", history
        
    system_status = get_system_status()
    persona_prompt = CHAT_PERSONAS.get(persona_name, CHAT_PERSONAS["温柔助手"])
    
    full_system_prompt = f"{persona_prompt}\n\n【当前系统状态参考（仅供参考，用户不问就别主动提）】\n{system_status}"
    
    provider_name, provider_cfg, model_name = config_mgr.get_provider_config(persona_name)
    
    from openai import OpenAI
    client = OpenAI(
        api_key=provider_cfg["api_key"],
        base_url=provider_cfg["base_url"]
    )
    
    messages = [{"role": "system", "content": full_system_prompt}]
    for user_msg, ai_msg in history:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": ai_msg})
    messages.append({"role": "user", "content": message})
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.8
        )
        reply = response.choices[0].message.content
        history.append((message, reply))
        return "", history
    except Exception as e:
        history.append((message, f"❌ 抱歉，我暂时无法连接到大脑：{e}"))
        return "", history

def toggle_ui_mode(mode):
    """切换 UI 模式"""
    is_pro = (mode == "专业模式")
    return [
        gr.update(visible=is_pro), # history_tab
        gr.update(visible=is_pro), # manual_task_tab
        gr.update(visible=is_pro), # personas_tab
        gr.update(visible=is_pro), # workspace_tab
        gr.update(visible=is_pro), # architect_tab
        gr.update(visible=is_pro)  # settings_tab
    ]

# 构建 Gradio 界面
with gr.Blocks(title="A1_Nexus 智能控制台") as demo:
    with gr.Row():
        with gr.Column(scale=4):
            gr.Markdown("# 🚀 A1_Nexus 智能控制台")
            gr.Markdown("这是一个基于 DAG 的多智能体协作系统。您可以在这里可视化地管理任务、配置系统和监控进度。")
        with gr.Column(scale=1):
            ui_mode_radio = gr.Radio(choices=["简洁模式", "专业模式"], value="专业模式", label="界面模式", info="简洁模式隐藏高级配置")
    
    with gr.Row():
        status_md = gr.Markdown(get_system_status())
        refresh_btn = gr.Button("🔄 刷新全局状态", size="sm")
        
    with gr.Tabs() as main_tabs:
        with gr.TabItem("📊 仪表盘 & 任务看板"):
            with gr.Row():
                with gr.Column(scale=2):
                    task_list_md = gr.Markdown(get_task_list())
                with gr.Column(scale=1):
                    gr.Markdown("### ⚙️ 快捷操作")
                    step_btn = gr.Button("▶️ 执行下一步 (手动)", variant="secondary")
                    auto_btn = gr.Button("🚀 一键全自动执行", variant="primary")
                    gr.Markdown("### 📝 执行日志")
                    log_output = gr.Textbox(label="执行日志", lines=15, max_lines=30, interactive=False, value="等待执行...")
            
            step_btn.click(fn=run_one_step, outputs=log_output).then(
                fn=get_task_list, outputs=task_list_md
            ).then(
                fn=get_system_status, outputs=status_md
            )
            
            # 自动运行按钮逻辑：先切换状态，再根据状态决定是否执行
            auto_btn.click(
                fn=toggle_auto_run,
                outputs=[auto_btn, log_output]
            ).then(
                fn=auto_run_all,
                outputs=log_output
            ).then(
                fn=get_task_list, outputs=task_list_md
            ).then(
                fn=get_system_status, outputs=status_md
            ).then(
                # 执行完毕后，如果是因为任务完成而停止，重置按钮状态
                fn=lambda: ("🚀 一键全自动执行" if not auto_run_flag else "⏸️ 暂停自动执行"),
                outputs=[auto_btn]
            )
            
            def send_stop_signal():
                import stop_project
                stop_project.stop_project()
                return "✅ 已发送停止信号！系统将在完成当前任务后安全退出。"
                
            stop_btn = gr.Button("🛑 紧急停止 (安全退出)", variant="stop")
            stop_btn.click(fn=send_stop_signal, outputs=log_output)
            
        with gr.TabItem("💬 闲聊助手"):
            gr.Markdown("工作累了？来和系统里的闲聊助手聊聊天吧！TA 不参与具体工作，但知道系统现在在干嘛。")
            with gr.Row():
                chat_persona_dropdown = gr.Dropdown(choices=list(CHAT_PERSONAS.keys()), value="温柔助手", label="选择助手性格")
            
            chatbot = gr.Chatbot(height=300, label="聊天窗口")
            with gr.Row():
                chat_input = gr.Textbox(show_label=False, placeholder="输入你想说的话，按回车发送...", scale=4)
                chat_submit = gr.Button("发送", variant="primary", scale=1)
                
            chat_input.submit(fn=chat_with_assistant, inputs=[chat_input, chatbot, chat_persona_dropdown], outputs=[chat_input, chatbot])
            chat_submit.click(fn=chat_with_assistant, inputs=[chat_input, chatbot, chat_persona_dropdown], outputs=[chat_input, chatbot])

        with gr.TabItem(" 工作历史记录", visible=True) as history_tab:
            gr.Markdown("查看系统过去的工作记录。您可以选择查看原始数据，或者让 AI 将其翻译成通俗易懂的汇报。")
            
            with gr.Tabs():
                with gr.TabItem("📋 原始记录"):
                    history_direct_md = gr.Markdown(format_history_direct())
                    refresh_direct_btn = gr.Button("🔄 刷新记录", size="sm")
                    refresh_direct_btn.click(fn=format_history_direct, outputs=history_direct_md)
                    
                with gr.TabItem("🗣️ AI 汇报 (人话版)"):
                    gr.Markdown("调用 P1 将最近的工作记录翻译成通俗易懂的语言。")
                    history_translated_md = gr.Markdown("点击下方按钮生成汇报...")
                    translate_btn = gr.Button("✨ 生成 AI 汇报", variant="primary")
                    translate_btn.click(fn=format_history_translated, outputs=history_translated_md)

        with gr.TabItem("➕ 下发新任务"):
            gr.Markdown("在这里作为 P1 (总包工头) 向虚拟员工下发任务。")
            
            with gr.Tabs():
                with gr.TabItem("🤖 AI 自动拆解 (推荐)"):
                    gr.Markdown("输入一个宏大的目标，让 P1 自动为您拆解为多个子任务并下发。")
                    macro_task_input = gr.Textbox(label="宏观任务描述", lines=5, placeholder="例如：帮我写一个贪吃蛇游戏，包含 HTML/CSS/JS，并写一份使用说明。")
                    auto_breakdown_btn = gr.Button("✨ 自动拆解并生成任务", variant="primary")
                    auto_breakdown_result = gr.Markdown("")
                    
                    auto_breakdown_btn.click(
                        fn=auto_breakdown_task,
                        inputs=[macro_task_input],
                        outputs=auto_breakdown_result
                    ).then(
                        fn=get_task_list, outputs=task_list_md
                    ).then(
                        fn=get_system_status, outputs=status_md
                    )

                with gr.TabItem("✍️ 手动创建单步任务", visible=True) as manual_task_tab:
                    # 获取可用角色
                    personas = [p.stem for p in engine.personas_dir.glob("*.md")]
                    if not personas:
                        personas = ["P8_技术", "P8_文案", "P9_行政合规审计"]
                        
                    with gr.Row():
                        receiver_dropdown = gr.Dropdown(choices=personas, label="接收者 (虚拟员工)", value=personas[0] if personas else None)
                        depends_input = gr.Textbox(label="依赖任务 ID (逗号分隔，无依赖填 NONE)", value="NONE")
                        
                    task_desc_input = gr.Textbox(label="任务详细描述", lines=10, placeholder="请详细描述任务目标和要求...")
                    create_btn = gr.Button("📝 创建任务", variant="primary")
                    create_result = gr.Markdown("")
                    
                    create_btn.click(
                        fn=create_new_task, 
                        inputs=[receiver_dropdown, task_desc_input, depends_input], 
                        outputs=create_result
                    ).then(
                        fn=get_task_list, outputs=task_list_md
                    ).then(
                        fn=get_system_status, outputs=status_md
                    )

        with gr.TabItem("👥 角色管理 (Personas)", visible=True) as personas_tab:
            gr.Markdown("管理系统中的虚拟员工角色设定。")
            with gr.Row():
                with gr.Column(scale=1):
                    persona_list = gr.Dropdown(choices=get_personas_list(), label="选择角色", interactive=True)
                    refresh_personas_btn = gr.Button("🔄 刷新列表", size="sm")
                    
                    gr.Markdown("---")
                    gr.Markdown("### 创建新角色")
                    new_persona_name = gr.Textbox(label="新角色文件名 (如 P7_测试.md)")
                    create_persona_btn = gr.Button("➕ 创建角色")
                    
                with gr.Column(scale=2):
                    persona_editor = gr.TextArea(label="角色设定内容", lines=20)
                    save_persona_btn = gr.Button("💾 保存修改", variant="primary")
                    persona_msg = gr.Markdown("")
            
            persona_list.change(fn=get_persona_content, inputs=[persona_list], outputs=[persona_editor])
            refresh_personas_btn.click(fn=lambda: gr.update(choices=get_personas_list()), outputs=[persona_list])
            save_persona_btn.click(fn=save_persona_content, inputs=[persona_list, persona_editor], outputs=[persona_msg])
            create_persona_btn.click(fn=create_new_persona, inputs=[new_persona_name, persona_editor], outputs=[persona_msg, persona_list])

        with gr.TabItem("📁 工作区 (Project Space)", visible=True) as workspace_tab:
            gr.Markdown("查看 AI 生成的项目文件。")
            with gr.Row():
                with gr.Column(scale=1):
                    workspace_tree = gr.Markdown(get_workspace_files())
                    refresh_ws_btn = gr.Button("🔄 刷新目录", size="sm")
                    file_to_read = gr.Textbox(label="输入要查看的文件路径 (相对 PROJECT_SPACE)", placeholder="例如: index.html")
                    read_file_btn = gr.Button("📄 查看文件内容")
                with gr.Column(scale=2):
                    file_content_view = gr.TextArea(label="文件内容预览", lines=25, interactive=False)
            
            refresh_ws_btn.click(fn=get_workspace_files, outputs=[workspace_tree])
            read_file_btn.click(fn=read_workspace_file, inputs=[file_to_read], outputs=[file_content_view])

        with gr.TabItem("💡 架构师建议", visible=True) as architect_tab:
            gr.Markdown("让 P8_架构师 审视当前项目，并主动提出改进建议。")
            
            def get_architect_suggestion(progress=gr.Progress()):
                progress(0, desc="正在收集项目信息...")
                
                # 收集项目文件内容
                project_info = "### 当前项目文件结构：\n"
                project_info += get_workspace_files() + "\n\n"
                
                project_info += "### 核心文件内容：\n"
                # 简单读取几个核心文件，避免超出 token 限制
                for filepath in engine.project_space_dir.rglob("*"):
                    if filepath.is_file() and filepath.suffix in ['.py', '.js', '.html', '.css', '.md']:
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                content = f.read()
                                # 截断过长的文件
                                if len(content) > 2000:
                                    content = content[:2000] + "\n... (内容过长已截断)"
                                project_info += f"#### {filepath.relative_to(engine.project_space_dir)}\n```\n{content}\n```\n\n"
                        except Exception:
                            pass
                            
                progress(0.3, desc="正在调用 P8_架构师 分析项目...")
                
                # 获取 P8_架构师 的设定
                persona_content = get_persona_content("P8_架构师.md")
                if not persona_content:
                    return "❌ 找不到 P8_架构师 的角色设定文件。"
                    
                # 获取模型配置
                provider_name, provider_cfg, model_name = config_mgr.get_provider_config("P8_架构师")
                
                from openai import OpenAI
                client = OpenAI(
                    api_key=provider_cfg["api_key"],
                    base_url=provider_cfg["base_url"]
                )
                
                try:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": persona_content},
                            {"role": "user", "content": f"请根据以下项目信息，提出你的架构师建议报告：\n\n{project_info}"}
                        ],
                        temperature=0.7
                    )
                    
                    progress(1.0, desc="分析完成！")
                    return response.choices[0].message.content
                except Exception as e:
                    return f"❌ 获取建议失败: {e}"

            suggest_btn = gr.Button("🧠 获取架构师建议", variant="primary")
            suggestion_output = gr.Markdown("点击上方按钮获取建议...")
            
            def accept_suggestion(suggestion_text):
                if not suggestion_text or "点击上方按钮" in suggestion_text or "获取建议失败" in suggestion_text:
                    return "❌ 没有可采纳的建议。"
                
                # 自动将建议转化为 P1 给 P8_技术 的任务
                res = create_new_task(
                    receiver="P8_技术主管", 
                    task_desc=f"请根据以下架构师建议进行代码重构和优化：\n\n{suggestion_text}", 
                    depends_on="NONE"
                )
                return f"✅ 已采纳建议并自动下发任务！\n{res}"
                
            def reject_suggestion():
                return "❌ 已忽略该建议。"

            with gr.Row():
                accept_btn = gr.Button("✅ 采纳建议 (自动下发任务)", variant="primary", visible=True)
                reject_btn = gr.Button("❌ 忽略建议", variant="secondary", visible=True)
                
            action_result = gr.Markdown("")

            suggest_btn.click(fn=get_architect_suggestion, outputs=suggestion_output)
            accept_btn.click(fn=accept_suggestion, inputs=[suggestion_output], outputs=[action_result]).then(
                fn=get_task_list, outputs=task_list_md
            ).then(
                fn=get_system_status, outputs=status_md
            )
            reject_btn.click(fn=reject_suggestion, outputs=[action_result])

        with gr.TabItem("⚙️ 系统设置 (API & 模型)", visible=True) as settings_tab:
            gr.Markdown("配置 API Keys 和默认模型。修改后点击保存即可生效。")
            
            with gr.Tabs():
                with gr.TabItem("🔑 API 密钥配置 (.env)"):
                    gr.Markdown("配置全局的 API 密钥和基础 URL。这些配置会保存在 `.env` 文件中，并覆盖 `config.yaml` 中的同名配置。")
                    
                    def get_env_config():
                        load_dotenv(override=True)
                        return {
                            "api_key": os.environ.get("OPENAI_API_KEY", ""),
                            "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                            "model": os.environ.get("DEFAULT_MODEL", "gpt-4o-mini")
                        }
                        
                    def save_env_config(api_key, base_url, model):
                        env_path = Path(".env")
                        env_content = f"""OPENAI_API_KEY="{api_key}"
OPENAI_BASE_URL="{base_url}"
DEFAULT_MODEL="{model}"
"""
                        try:
                            with open(env_path, "w", encoding="utf-8") as f:
                                f.write(env_content)
                            # 重新加载环境变量
                            load_dotenv(override=True)
                            # 重新加载配置管理器
                            global config_mgr
                            config_mgr = ConfigManager()
                            return "✅ API 配置已保存到 .env 文件！"
                        except Exception as e:
                            return f"❌ 保存失败: {e}"
                            
                    def test_api_connection(api_key, base_url, model):
                        if not api_key:
                            return "❌ 请先输入 API Key"
                            
                        try:
                            from openai import OpenAI
                            client = OpenAI(api_key=api_key, base_url=base_url)
                            
                            # 发送一个简单的测试请求
                            response = client.chat.completions.create(
                                model=model,
                                messages=[{"role": "user", "content": "Hello, this is a test. Reply with 'OK'."}],
                                max_tokens=10
                            )
                            
                            reply = response.choices[0].message.content
                            return f"✅ API 连接成功！模型返回: {reply}"
                        except Exception as e:
                            return f"❌ API 连接失败: {e}"

                    env_cfg = get_env_config()
                    
                    with gr.Row():
                        with gr.Column(scale=2):
                            env_api_key = gr.Textbox(label="OPENAI_API_KEY", value=env_cfg["api_key"], type="password", placeholder="sk-...")
                            env_base_url = gr.Textbox(label="OPENAI_BASE_URL", value=env_cfg["base_url"], placeholder="https://api.openai.com/v1")
                            env_model = gr.Textbox(label="DEFAULT_MODEL", value=env_cfg["model"], placeholder="gpt-4o-mini")
                        with gr.Column(scale=1):
                            gr.Markdown("### 操作")
                            save_env_btn = gr.Button("💾 保存配置", variant="primary")
                            test_api_btn = gr.Button("🔌 测试 API 连接", variant="secondary")
                            env_msg = gr.Markdown("")
                            
                    save_env_btn.click(
                        fn=save_env_config,
                        inputs=[env_api_key, env_base_url, env_model],
                        outputs=[env_msg]
                    )
                    
                    test_api_btn.click(
                        fn=test_api_connection,
                        inputs=[env_api_key, env_base_url, env_model],
                        outputs=[env_msg]
                    )

                with gr.TabItem("📝 文本配置 (config.yaml)"):
                    config_editor = gr.TextArea(label="config.yaml", value=get_config_yaml(), lines=25)
                    save_config_btn = gr.Button("💾 保存配置", variant="primary")
                    config_msg = gr.Markdown("")
                    save_config_btn.click(fn=save_config_yaml, inputs=[config_editor], outputs=[config_msg])
                    
                with gr.TabItem("🤖 角色模型分配"):
                    gr.Markdown("为不同的虚拟员工分配特定的 AI 模型。")
                    
                    def get_role_overrides_ui():
                        import yaml
                        config_path = Path("SYSTEM/config.yaml")
                        if not config_path.exists():
                            config_path = Path("config.yaml")
                        if not config_path.exists():
                            return "配置文件不存在"
                            
                        with open(config_path, "r", encoding="utf-8") as f:
                            config = yaml.safe_load(f)
                            
                        overrides = config.get("role_overrides", {})
                        
                        # 获取所有可用模型
                        all_models = config_mgr.get_all_models()
                        model_choices = [m["display"] for m in all_models]
                        
                        ui_elements = []
                        for role, cfg in overrides.items():
                            provider = cfg.get("provider", "")
                            model = cfg.get("model", "")
                            current_display = f"[{provider}] {model}"
                            
                            # 尝试找到匹配的显示名称
                            matched_display = current_display
                            for choice in model_choices:
                                if current_display in choice:
                                    matched_display = choice
                                    break
                                    
                            ui_elements.append(f"**{role}**: 当前使用 `{matched_display}`")
                            
                        return "\n\n".join(ui_elements)
                        
                    def update_role_model(role_name, selected_model_display):
                        global config_mgr
                        if not role_name or not selected_model_display:
                            return "❌ 请选择角色和模型", get_role_overrides_ui()
                            
                        import yaml
                        config_path = Path("SYSTEM/config.yaml")
                        if not config_path.exists():
                            config_path = Path("config.yaml")
                            
                        with open(config_path, "r", encoding="utf-8") as f:
                            config = yaml.safe_load(f)
                            
                        # 解析选中的模型
                        all_models = config_mgr.get_all_models()
                        selected_model_info = next((m for m in all_models if m["display"] == selected_model_display), None)
                        
                        if not selected_model_info:
                            return "❌ 找不到选中的模型信息", get_role_overrides_ui()
                            
                        if "role_overrides" not in config:
                            config["role_overrides"] = {}
                            
                        config["role_overrides"][role_name] = {
                            "provider": selected_model_info["provider"],
                            "model": selected_model_info["model_id"]
                        }
                        
                        with open(config_path, "w", encoding="utf-8") as f:
                            yaml.dump(config, f, allow_unicode=True, sort_keys=False)
                            
                        # 重新加载配置
                        config_mgr = ConfigManager()
                        
                        return f"✅ 成功将 {role_name} 的模型设置为 {selected_model_display}", get_role_overrides_ui()

                    with gr.Row():
                        with gr.Column(scale=1):
                            gr.Markdown("### 当前分配情况")
                            role_models_display = gr.Markdown(get_role_overrides_ui())
                            refresh_roles_btn = gr.Button("🔄 刷新显示", size="sm")
                        with gr.Column(scale=1):
                            gr.Markdown("### 修改分配")
                            # 获取所有角色
                            personas = [p.stem for p in engine.personas_dir.glob("*.md")]
                            
                            # 添加系统内置角色和聊天助手
                            builtin_roles = ["P1_Nexus", "P8_架构师"] + list(CHAT_PERSONAS.keys())
                            for role in builtin_roles:
                                if role not in personas:
                                    personas.append(role)
                                    
                            if not personas:
                                personas = ["P1_Nexus", "P8_技术", "P8_文案", "P9_行政合规审计"]
                            
                            # 获取所有模型
                            all_models = config_mgr.get_all_models()
                            model_choices = [m["display"] for m in all_models]
                            
                            role_dropdown = gr.Dropdown(choices=personas, label="选择角色")
                            model_dropdown = gr.Dropdown(choices=model_choices, label="选择模型")
                            update_role_btn = gr.Button("💾 保存分配", variant="primary")
                            update_role_msg = gr.Markdown("")
                            
                    refresh_roles_btn.click(fn=get_role_overrides_ui, outputs=[role_models_display])
                    update_role_btn.click(
                        fn=update_role_model,
                        inputs=[role_dropdown, model_dropdown],
                        outputs=[update_role_msg, role_models_display]
                    )
            
    # UI 模式切换逻辑
    ui_mode_radio.change(
        fn=toggle_ui_mode,
        inputs=[ui_mode_radio],
        outputs=[history_tab, manual_task_tab, personas_tab, workspace_tab, architect_tab, settings_tab]
    )

    refresh_btn.click(fn=get_system_status, outputs=status_md).then(fn=get_task_list, outputs=task_list_md)

if __name__ == "__main__":
    # 启动 Web UI，允许局域网访问
    print("正在启动 Web UI...")
    # 禁用代理以避免 502 错误
    os.environ["no_proxy"] = "localhost,127.0.0.1,0.0.0.0"
    demo.launch(server_name="127.0.0.1", server_port=8080, share=False, theme=gr.themes.Soft(primary_hue="indigo", secondary_hue="blue"))
