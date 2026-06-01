from api.schemas import AgentDecision


def extract_write_request(text: str) -> tuple[str, str]:
    if text.lower().startswith("/write "):
        payload = text[7:].strip()
        path, separator, content = payload.partition("\n")
        if not separator:
            path, _, content = payload.partition(" ")
        return (path.strip() or "output.txt", content)

    for marker in ["内容", "content"]:
        if marker in text:
            before, content = text.split(marker, 1)
            path = extract_path(before)
            return (path, content.strip())

    return ("output.txt", text)


def extract_path(text: str) -> str:
    for marker in ["读取", "打开", "read", "写入", "创建", "保存", "生成", "write", "create", "save"]:
        if marker in text:
            path = text.split(marker, 1)[1].strip()
            return path or "README.md"

    return "README.md"


def plan_next_action(user_message: str) -> AgentDecision:
    text = user_message.strip()
    lower_text = text.lower()

    if lower_text.startswith("/run "):
        command = text[5:].strip() or "pwd"
        return AgentDecision(
            mode="direct_command",
            thought="用户明确要求直接在 Docker 沙箱中执行 shell 命令。",
            tool="run_shell",
            input={"command": command},
        )

    if lower_text.startswith("/write ") or any(
        keyword in lower_text for keyword in ["write", "create", "save", "写入", "创建", "保存", "生成"]
    ):
        path, content = extract_write_request(text)
        return AgentDecision(
            mode="natural_task",
            thought=f"用户想在 Docker 沙箱中写入文件：{path}。",
            tool="write_file",
            input={"path": path, "content": content},
        )

    if any(keyword in lower_text for keyword in ["environment", "version", "runtime", "环境", "版本", "运行环境"]):
        return AgentDecision(
            mode="natural_task",
            thought="用户想检查 Docker 沙箱的运行环境和基础工具版本。",
            tool="run_shell",
            input={"command": "pwd && python --version && node --version && npm --version"},
        )

    if any(keyword in lower_text for keyword in ["read", "读取", "打开"]):
        path = extract_path(text)
        return AgentDecision(
            mode="natural_task",
            thought=f"用户想读取 Docker 沙箱中的文件：{path}。",
            tool="read_file",
            input={"path": path},
        )

    if any(keyword in lower_text for keyword in ["file", "directory", "list", "文件", "目录", "看看", "有什么"]):
        return AgentDecision(
            mode="natural_task",
            thought="用户想查看 Docker 沙箱当前工作目录中的文件列表。",
            tool="list_files",
            input={"path": "."},
        )

    return AgentDecision(
        mode="natural_task",
        thought="当前规则版 Agent 还不能完整规划这个任务，先返回一个安全的沙箱提示。",
        tool="run_shell",
        input={
            "command": 'echo "I can run sandbox commands now. Try /run pwd or ask me to inspect the environment."'
        },
    )
