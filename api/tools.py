from collections.abc import Awaitable, Callable
import base64
import json
import shlex
from typing import Any

from api.sandbox import run_shell

ToolInput = dict[str, Any]
ToolResult = dict[str, Any]
ToolHandler = Callable[[ToolInput], Awaitable[ToolResult]]


async def run_shell_tool(tool_input: ToolInput) -> ToolResult:
    command = str(tool_input.get("command", "")).strip()
    if not command:
        return {"exit_code": 2, "stdout": "", "stderr": "Missing command"}

    return await run_shell(command)


async def list_files_tool(tool_input: ToolInput) -> ToolResult:
    path = str(tool_input.get("path", ".")).strip() or "."
    script = r"""
import json
import pathlib
import sys

path = sys.argv[1]
target = pathlib.Path(path)

if not target.exists():
    print(json.dumps({"path": path, "entries": [], "error": "Path does not exist"}, ensure_ascii=False))
    raise SystemExit(1)

if not target.is_dir():
    print(json.dumps({"path": path, "entries": [], "error": "Path is not a directory"}, ensure_ascii=False))
    raise SystemExit(1)

entries = []
for entry in sorted(target.iterdir(), key=lambda item: item.name.lower()):
    if entry.is_dir():
        entry_type = "directory"
    elif entry.is_file():
        entry_type = "file"
    elif entry.is_symlink():
        entry_type = "symlink"
    else:
        entry_type = "other"

    entries.append({"name": entry.name, "type": entry_type})

print(json.dumps({"path": path, "entries": entries}, ensure_ascii=False))
"""
    return await run_structured_python(script, path)


async def read_file_tool(tool_input: ToolInput) -> ToolResult:
    path = str(tool_input.get("path", "")).strip()
    if not path:
        return {"path": "", "content": "", "truncated": False, "error": "Missing path"}

    script = r"""
import json
import pathlib
import sys

path = sys.argv[1]
target = pathlib.Path(path)
max_lines = 200

if not target.exists():
    print(json.dumps({"path": path, "content": "", "truncated": False, "error": "File does not exist"}, ensure_ascii=False))
    raise SystemExit(1)

if not target.is_file():
    print(json.dumps({"path": path, "content": "", "truncated": False, "error": "Path is not a file"}, ensure_ascii=False))
    raise SystemExit(1)

content_lines = []
truncated = False

with target.open("r", encoding="utf-8", errors="replace") as file:
    for index, line in enumerate(file):
        if index >= max_lines:
            truncated = True
            break
        content_lines.append(line)

print(json.dumps(
    {
        "path": path,
        "content": "".join(content_lines),
        "truncated": truncated,
        "line_count": len(content_lines),
    },
    ensure_ascii=False,
))
"""
    return await run_structured_python(script, path)


async def write_file_tool(tool_input: ToolInput) -> ToolResult:
    path = str(tool_input.get("path", "")).strip()
    content = str(tool_input.get("content", ""))
    if not path:
        return {"path": "", "bytes_written": 0, "error": "Missing path"}

    encoded_content = base64.b64encode(content.encode("utf-8")).decode("ascii")
    script = r"""
import base64
import json
import pathlib
import sys

path = sys.argv[1]
encoded_content = sys.argv[2]
target = pathlib.Path(path)

if target.exists() and target.is_dir():
    print(json.dumps({"path": path, "bytes_written": 0, "error": "Path is a directory"}, ensure_ascii=False))
    raise SystemExit(1)

target.parent.mkdir(parents=True, exist_ok=True)
content = base64.b64decode(encoded_content.encode("ascii")).decode("utf-8")
target.write_text(content, encoding="utf-8")

print(json.dumps(
    {
        "path": path,
        "bytes_written": len(content.encode("utf-8")),
        "created": True,
    },
    ensure_ascii=False,
))
"""
    return await run_structured_python(script, path, encoded_content)


async def replace_text_tool(tool_input: ToolInput) -> ToolResult:
    path = str(tool_input.get("path", "")).strip()
    old_text = str(tool_input.get("old_text", ""))
    new_text = str(tool_input.get("new_text", ""))
    if not path:
        return {"path": "", "replacements": 0, "bytes_written": 0, "error": "Missing path"}
    if old_text == "":
        return {"path": path, "replacements": 0, "bytes_written": 0, "error": "Missing old_text"}

    encoded_old_text = base64.b64encode(old_text.encode("utf-8")).decode("ascii")
    encoded_new_text = base64.b64encode(new_text.encode("utf-8")).decode("ascii")
    script = r"""
import base64
import json
import pathlib
import sys

path = sys.argv[1]
encoded_old_text = sys.argv[2]
encoded_new_text = sys.argv[3]
target = pathlib.Path(path)

if not target.exists():
    print(json.dumps({"path": path, "replacements": 0, "bytes_written": 0, "error": "File does not exist"}, ensure_ascii=False))
    raise SystemExit(1)

if not target.is_file():
    print(json.dumps({"path": path, "replacements": 0, "bytes_written": 0, "error": "Path is not a file"}, ensure_ascii=False))
    raise SystemExit(1)

old_text = base64.b64decode(encoded_old_text.encode("ascii")).decode("utf-8")
new_text = base64.b64decode(encoded_new_text.encode("ascii")).decode("utf-8")
content = target.read_text(encoding="utf-8", errors="replace")
match_count = content.count(old_text)

if match_count == 0:
    print(json.dumps({"path": path, "replacements": 0, "bytes_written": 0, "error": "old_text not found"}, ensure_ascii=False))
    raise SystemExit(1)

if match_count > 1:
    print(json.dumps({"path": path, "replacements": 0, "bytes_written": 0, "error": "old_text is not unique", "matches": match_count}, ensure_ascii=False))
    raise SystemExit(1)

updated = content.replace(old_text, new_text, 1)
target.write_text(updated, encoding="utf-8")

print(json.dumps(
    {
        "path": path,
        "replacements": 1,
        "bytes_written": len(updated.encode("utf-8")),
    },
    ensure_ascii=False,
))
"""
    return await run_structured_python(script, path, encoded_old_text, encoded_new_text)


async def patch_file_tool(tool_input: ToolInput) -> ToolResult:
    path = str(tool_input.get("path", "")).strip()
    edits = tool_input.get("edits", [])
    if not path:
        return {"path": "", "applied_edits": 0, "bytes_written": 0, "error": "Missing path"}
    if not isinstance(edits, list) or not edits:
        return {"path": path, "applied_edits": 0, "bytes_written": 0, "error": "Missing edits"}

    encoded_edits = base64.b64encode(json.dumps(edits, ensure_ascii=False).encode("utf-8")).decode("ascii")
    script = r"""
import base64
import json
import pathlib
import sys

path = sys.argv[1]
encoded_edits = sys.argv[2]
target = pathlib.Path(path)

if not target.exists():
    print(json.dumps({"path": path, "applied_edits": 0, "bytes_written": 0, "error": "File does not exist"}, ensure_ascii=False))
    raise SystemExit(1)

if not target.is_file():
    print(json.dumps({"path": path, "applied_edits": 0, "bytes_written": 0, "error": "Path is not a file"}, ensure_ascii=False))
    raise SystemExit(1)

try:
    edits = json.loads(base64.b64decode(encoded_edits.encode("ascii")).decode("utf-8"))
except (ValueError, TypeError) as error:
    print(json.dumps({"path": path, "applied_edits": 0, "bytes_written": 0, "error": "Invalid edits JSON", "message": str(error)}, ensure_ascii=False))
    raise SystemExit(1)

if not isinstance(edits, list) or not edits:
    print(json.dumps({"path": path, "applied_edits": 0, "bytes_written": 0, "error": "Missing edits"}, ensure_ascii=False))
    raise SystemExit(1)

content = target.read_text(encoding="utf-8", errors="replace")
seen_old_texts = set()

for index, edit in enumerate(edits):
    if not isinstance(edit, dict):
        print(json.dumps({"path": path, "applied_edits": 0, "bytes_written": 0, "error": "Invalid edit", "edit_index": index, "message": "edit must be an object"}, ensure_ascii=False))
        raise SystemExit(1)

    old_text = edit.get("old_text")
    new_text = edit.get("new_text")
    if not isinstance(old_text, str) or old_text == "":
        print(json.dumps({"path": path, "applied_edits": 0, "bytes_written": 0, "error": "Invalid edit", "edit_index": index, "message": "old_text must be a non-empty string"}, ensure_ascii=False))
        raise SystemExit(1)
    if not isinstance(new_text, str):
        print(json.dumps({"path": path, "applied_edits": 0, "bytes_written": 0, "error": "Invalid edit", "edit_index": index, "message": "new_text must be a string"}, ensure_ascii=False))
        raise SystemExit(1)
    if old_text in seen_old_texts:
        print(json.dumps({"path": path, "applied_edits": 0, "bytes_written": 0, "error": "Duplicate old_text", "edit_index": index}, ensure_ascii=False))
        raise SystemExit(1)
    seen_old_texts.add(old_text)

    match_count = content.count(old_text)
    if match_count == 0:
        print(json.dumps({"path": path, "applied_edits": 0, "bytes_written": 0, "error": "old_text not found", "edit_index": index}, ensure_ascii=False))
        raise SystemExit(1)
    if match_count > 1:
        print(json.dumps({"path": path, "applied_edits": 0, "bytes_written": 0, "error": "old_text is not unique", "edit_index": index, "matches": match_count}, ensure_ascii=False))
        raise SystemExit(1)

updated = content
for index, edit in enumerate(edits):
    old_text = edit["old_text"]
    if old_text not in updated:
        print(json.dumps({"path": path, "applied_edits": 0, "bytes_written": 0, "error": "old_text not found after prior edits", "edit_index": index}, ensure_ascii=False))
        raise SystemExit(1)
    updated = updated.replace(old_text, edit["new_text"], 1)

target.write_text(updated, encoding="utf-8")

print(json.dumps(
    {
        "path": path,
        "applied_edits": len(edits),
        "bytes_written": len(updated.encode("utf-8")),
    },
    ensure_ascii=False,
))
"""
    return await run_structured_python(script, path, encoded_edits)


async def run_structured_python(script: str, *arguments: str) -> ToolResult:
    command_parts = ["python", "-c", shlex.quote(script)]
    command_parts.extend(shlex.quote(argument) for argument in arguments)
    command = " ".join(command_parts)
    result = await run_shell(command)

    stdout = str(result.get("stdout", "")).strip()
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {"error": "Tool returned invalid JSON", "raw_stdout": stdout}
    else:
        payload = {"error": "Tool returned no JSON"}
        stderr = str(result.get("stderr", "")).strip()
        if stderr:
            payload["stderr"] = stderr

    if result.get("exit_code", 0) != 0 and "error" not in payload:
        payload["error"] = str(result.get("stderr", "")).strip() or "Tool command failed"

    return payload


TOOLS: dict[str, ToolHandler] = {
    "run_shell": run_shell_tool,
    "list_files": list_files_tool,
    "read_file": read_file_tool,
    "write_file": write_file_tool,
    "replace_text": replace_text_tool,
    "patch_file": patch_file_tool,
}


async def execute_tool(name: str, tool_input: ToolInput) -> ToolResult:
    tool = TOOLS.get(name)
    if tool is None:
        return {"exit_code": 127, "stdout": "", "stderr": f"Unknown tool: {name}"}

    return await tool(tool_input)
