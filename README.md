# A1_Nexus 多智能体协作系统

A1_Nexus 是一个基于 DAG（有向无环图）的多智能体（Multi-Agent）协作系统。它允许你将宏大的目标拆解为多个子任务，下发给不同的“虚拟员工”（如技术主管、文案主管、UI设计师等），然后系统会自动调度大模型完成这些任务，并处理它们之间的依赖关系。

## 🌟 核心特性

- **多角色协作**：预设多种虚拟员工角色（Persona），各司其职。
- **DAG 任务调度**：支持复杂的任务依赖关系，自动按顺序执行。
- **跨平台支持**：完美兼容 Windows、Mac 和 Linux。
- **多模型支持**：内置支持 OpenAI、DeepSeek、Gemini、Anthropic、SiliconFlow 等多种大模型 API。
- **可视化 Web UI**：提供直观的 Gradio 界面，方便管理任务、查看进度和与 AI 闲聊。
- **一键启动**：自带环境自检与依赖安装脚本，无需繁琐配置。

## 🚀 快速开始

### 1. 准备工作

确保你的电脑上已安装 **Python 3.8** 或更高版本。

### 2. 配置 API Key

打开 `SYSTEM/config.yaml` 文件，找到你想要使用的模型提供商（如 `deepseek`, `gemini`, `openai` 等），填入你的 API Key。

```yaml
api_providers:
  default: gemini # 设置默认使用的模型
  providers:
    gemini:
      base_url: "https://generativelanguage.googleapis.com/v1beta/openai/"
      api_key: "YOUR_GEMINI_API_KEY_HERE" # 填入你的 API Key
      models:
        default: "gemini-2.5-flash"
```

### 3. 启动系统

根据你的操作系统，双击或运行对应的启动脚本：

- **Windows**: 双击 `start_web_ui.bat`
- **Mac / Linux**: 在终端中运行 `./start_web_ui.sh` (首次运行可能需要 `chmod +x start_web_ui.sh`)

系统会自动创建虚拟环境、安装依赖，并在浏览器中打开 Web UI 界面（默认地址：`http://localhost:8080`）。

## 📖 使用指南

### 任务下发流程

1. **拆解任务**：将你的大目标拆解为多个具体的子任务。
2. **创建任务文件**：在 `MESSAGES/` 目录下为每个子任务创建一个 Markdown 文件。
   - 文件名规范：`[NEW]P1_TO_{接收者角色名}_ID{三位数字}_{简短描述}.md`
   - 示例：`[NEW]P1_TO_P8_技术主管_ID001_搭建基础框架.md`
3. **编写任务内容**：在文件中详细描述任务要求，并声明依赖关系。
   ```markdown
   # 任务目标：搭建基础框架
   
   **DEPENDS_ON: NONE**
   
   ## 详细要求
   请使用 Python 搭建一个基础的 Web 框架...
   ```
4. **执行任务**：在 Web UI 中点击“启动/刷新系统”，系统会自动读取并执行任务。
5. **查看结果**：执行完成的任务会被移动到 `ARCHIVE/` 目录下，文件名前缀变为 `[DONE]`。你可以在文件中查看 AI 的执行结果。

### 目录结构说明

- `MESSAGES/`: 存放待执行的任务文件。
- `ARCHIVE/`: 存放已完成的任务文件。
- `PERSONAS/`: 存放虚拟员工的角色设定文件。
- `PROJECT_SPACE/`: 存放 AI 生成的最终项目代码和文件。
- `SYSTEM/`: 存放系统的核心代码和配置文件。

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request 来帮助改进 A1_Nexus！

## 📄 许可证

本项目采用 MIT 许可证。详情请参阅 [LICENSE](LICENSE) 文件。
