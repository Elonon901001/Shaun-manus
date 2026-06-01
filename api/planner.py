import re
import json
from typing import Any

from api.agent import extract_path, extract_write_request, plan_next_action
from api.schemas import AgentPlan, AgentStep

PLAN_VERSION = "planner.v1"


def build_plan(user_message: str) -> AgentPlan:
    text = user_message.strip()
    lower_text = text.lower()

    write_run_plan = plan_write_then_run(text)
    if write_run_plan is not None:
        return write_run_plan

    run_read_plan = plan_run_then_read(text)
    if run_read_plan is not None:
        return run_read_plan

    list_read_plan = plan_list_then_read(text)
    if list_read_plan is not None:
        return list_read_plan

    decision = plan_next_action(text)
    return AgentPlan(
        version=PLAN_VERSION,
        source="rule",
        goal=text,
        steps=[
            AgentStep(
                id="step_1",
                thought=decision.thought,
                tool=decision.tool,
                input=decision.input,
            )
        ],
    )


def plan_write_then_run(text: str) -> AgentPlan | None:
    lower_text = text.lower()
    if not any(keyword in lower_text for keyword in ["然后运行", "并运行", "然后执行", "并执行", "then run", "and run"]):
        return None

    if not any(keyword in lower_text for keyword in ["write", "create", "save", "写入", "创建", "保存", "生成"]):
        return None

    path, content = extract_write_request(text)
    content = strip_followup_instruction(content)
    command = infer_run_command(path)
    return AgentPlan(
        version=PLAN_VERSION,
        source="rule",
        goal=text,
        steps=[
            AgentStep(
                id="step_1",
                thought=f"先在 Docker 沙箱中写入文件：{path}。",
                tool="write_file",
                input={"path": path, "content": content},
            ),
            AgentStep(
                id="step_2",
                thought=f"然后运行刚写入的文件：{path}。",
                tool="run_shell",
                input={"command": command},
            ),
        ],
    )


def plan_run_then_read(text: str) -> AgentPlan | None:
    lower_text = text.lower()
    if not any(keyword in lower_text for keyword in ["然后读取", "并读取", "then read", "and read"]):
        return None

    command = extract_run_command(text)
    if not command:
        return None

    path = extract_path_after_read(text)
    return AgentPlan(
        version=PLAN_VERSION,
        source="rule",
        goal=text,
        steps=[
            AgentStep(
                id="step_1",
                thought="先在 Docker 沙箱中运行命令。",
                tool="run_shell",
                input={"command": command},
            ),
            AgentStep(
                id="step_2",
                thought=f"再读取命令完成后的文件：{path}。",
                tool="read_file",
                input={"path": path},
            ),
        ],
    )


def plan_list_then_read(text: str) -> AgentPlan | None:
    lower_text = text.lower()
    if not any(keyword in lower_text for keyword in ["然后读取", "并读取", "then read", "and read"]):
        return None
    if not any(keyword in lower_text for keyword in ["看看", "列出", "list", "目录", "文件"]):
        return None

    path = extract_path_after_read(text)
    return AgentPlan(
        version=PLAN_VERSION,
        source="rule",
        goal=text,
        steps=[
            AgentStep(
                id="step_1",
                thought="先查看 Docker 沙箱当前工作目录。",
                tool="list_files",
                input={"path": "."},
            ),
            AgentStep(
                id="step_2",
                thought=f"再读取用户指定的文件：{path}。",
                tool="read_file",
                input={"path": path},
            ),
        ],
    )


def infer_run_command(path: str) -> str:
    if path.endswith(".py"):
        return f"python {path}"
    if path.endswith(".js"):
        return f"node {path}"
    if path.endswith(".sh"):
        return f"sh {path}"
    return f"cat {path}"


def extract_run_command(text: str) -> str:
    if text.lower().startswith("/run "):
        command_part = text[5:]
    else:
        match = re.search(r"(?:运行|执行|run)\s+(.+)", text, flags=re.IGNORECASE)
        if match is None:
            return ""
        command_part = match.group(1)

    for marker in ["然后读取", "并读取", "then read", "and read"]:
        if marker in command_part:
            command_part = command_part.split(marker, 1)[0]

    return command_part.strip()


def extract_path_after_read(text: str) -> str:
    lower_text = text.lower()
    for marker in ["然后读取", "并读取", "then read", "and read"]:
        index = lower_text.find(marker)
        if index != -1:
            path_text = text[index + len(marker) :].strip()
            return extract_path(path_text) if has_read_marker(path_text) else path_text or "README.md"
    return extract_path(text)


def strip_followup_instruction(content: str) -> str:
    for marker in ["然后运行", "并运行", "然后执行", "并执行", "then run", "and run"]:
        if marker in content:
            return content.split(marker, 1)[0].strip()
    return content


def has_read_marker(text: str) -> bool:
    lower_text = text.lower()
    return any(marker in lower_text for marker in ["读取", "打开", "read"])


def plan_to_json(plan: AgentPlan) -> str:
    return plan.model_dump_json()


def plan_from_json(plan_json: str) -> AgentPlan:
    data = json.loads(plan_json)
    return normalize_plan(data)


def normalize_plan(data: dict[str, Any]) -> AgentPlan:
    if "goal" not in data:
        raise ValueError("Plan is missing goal")
    if "steps" not in data or not isinstance(data["steps"], list):
        raise ValueError("Plan is missing steps")

    normalized = {
        "version": data.get("version", PLAN_VERSION),
        "source": data.get("source", "external"),
        "goal": data["goal"],
        "max_steps": data.get("max_steps", 8),
        "context": data.get("context", {}),
        "steps": data["steps"],
    }
    return AgentPlan.model_validate(normalized)
