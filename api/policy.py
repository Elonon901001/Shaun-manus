from api.tool_manifest import get_tool_manifest

RISK_MESSAGES: dict[str, str] = {
    "safe": "只读操作，会在 Docker 沙箱中读取信息。",
    "write": "写入操作，会修改 Docker 沙箱中的文件。",
    "command": "命令操作，会在 Docker 沙箱中执行 shell 命令。",
    "unknown": "未知工具，执行前需要人工确认。",
}


def get_tool_risk(tool_name: str) -> str:
    manifest = get_tool_manifest(tool_name)
    return manifest.risk if manifest is not None else "unknown"


def get_risk_message(tool_name: str) -> str:
    return RISK_MESSAGES[get_tool_risk(tool_name)]


def requires_confirmation(tool_name: str) -> bool:
    return get_tool_risk(tool_name) != "safe"
