from dataclasses import dataclass
import json
from typing import Any


@dataclass(frozen=True)
class ToolInputField:
    name: str
    type_name: str
    required: bool
    description: str


@dataclass(frozen=True)
class ToolManifest:
    name: str
    description: str
    risk: str
    input_fields: tuple[ToolInputField, ...]
    examples: tuple[dict[str, Any], ...]


TOOL_MANIFESTS: dict[str, ToolManifest] = {
    "run_shell": ToolManifest(
        name="run_shell",
        description="Run a shell command inside the Docker sandbox workspace.",
        risk="command",
        input_fields=(
            ToolInputField(
                name="command",
                type_name="str",
                required=True,
                description="Shell command to execute in the sandbox.",
            ),
        ),
        examples=({"command": "python hello.py"}, {"command": "pwd && python --version"}),
    ),
    "list_files": ToolManifest(
        name="list_files",
        description="List entries in a directory inside the Docker sandbox workspace.",
        risk="safe",
        input_fields=(
            ToolInputField(
                name="path",
                type_name="str",
                required=False,
                description="Directory path to list. Defaults to the sandbox workspace root.",
            ),
        ),
        examples=({"path": "."}, {"path": "src"}),
    ),
    "read_file": ToolManifest(
        name="read_file",
        description="Read a UTF-8 text file from the Docker sandbox workspace.",
        risk="safe",
        input_fields=(
            ToolInputField(
                name="path",
                type_name="str",
                required=True,
                description="File path to read.",
            ),
        ),
        examples=({"path": "README.md"}, {"path": "notes/todo.txt"}),
    ),
    "write_file": ToolManifest(
        name="write_file",
        description="Create or overwrite a UTF-8 text file in the Docker sandbox workspace.",
        risk="write",
        input_fields=(
            ToolInputField(
                name="path",
                type_name="str",
                required=True,
                description="File path to write.",
            ),
            ToolInputField(
                name="content",
                type_name="str",
                required=True,
                description="Complete file content to write.",
            ),
        ),
        examples=({"path": "hello.py", "content": "print('hi')"},),
    ),
    "replace_text": ToolManifest(
        name="replace_text",
        description="Replace one exact text block in an existing UTF-8 file inside the Docker sandbox workspace.",
        risk="write",
        input_fields=(
            ToolInputField(
                name="path",
                type_name="str",
                required=True,
                description="Existing file path to edit.",
            ),
            ToolInputField(
                name="old_text",
                type_name="str",
                required=True,
                description="Exact text to replace. It must appear exactly once.",
            ),
            ToolInputField(
                name="new_text",
                type_name="str",
                required=True,
                description="Replacement text. Use an empty string to delete the old text.",
            ),
        ),
        examples=(
            {
                "path": "hello.py",
                "old_text": "print('hi')",
                "new_text": "print('hello')",
            },
        ),
    ),
    "patch_file": ToolManifest(
        name="patch_file",
        description="Apply multiple exact text replacements to one existing UTF-8 file atomically.",
        risk="write",
        input_fields=(
            ToolInputField(
                name="path",
                type_name="str",
                required=True,
                description="Existing file path to edit.",
            ),
            ToolInputField(
                name="edits",
                type_name="list",
                required=True,
                description="Ordered edits. Each edit has old_text and new_text strings.",
            ),
        ),
        examples=(
            {
                "path": "settings.py",
                "edits": [
                    {"old_text": "timeout = 20", "new_text": "timeout = 30"},
                    {"old_text": "retries = 1", "new_text": "retries = 3"},
                ],
            },
        ),
    ),
}


TYPE_NAME_TO_TYPE: dict[str, type] = {
    "str": str,
    "list": list,
}


def get_tool_manifest(tool_name: str) -> ToolManifest | None:
    return TOOL_MANIFESTS.get(tool_name)


def list_tool_manifests() -> list[ToolManifest]:
    return [TOOL_MANIFESTS[name] for name in sorted(TOOL_MANIFESTS)]


def required_input_fields(manifest: ToolManifest) -> dict[str, type]:
    return {
        field.name: field_type(field)
        for field in manifest.input_fields
        if field.required
    }


def optional_input_fields(manifest: ToolManifest) -> dict[str, type]:
    return {
        field.name: field_type(field)
        for field in manifest.input_fields
        if not field.required
    }


def field_type(field: ToolInputField) -> type:
    try:
        return TYPE_NAME_TO_TYPE[field.type_name]
    except KeyError as error:
        raise ValueError(f"Unsupported tool input type: {field.type_name}") from error


def manifest_to_dict(manifest: ToolManifest) -> dict[str, Any]:
    return {
        "name": manifest.name,
        "description": manifest.description,
        "risk": manifest.risk,
        "input_schema": {
            field.name: {
                "type": field.type_name,
                "required": field.required,
                "description": field.description,
            }
            for field in manifest.input_fields
        },
        "examples": list(manifest.examples),
    }


def tool_manifest_payload() -> dict[str, Any]:
    manifests = list_tool_manifests()
    return {
        "version": "tool_manifest.v1",
        "tools": [manifest_to_dict(manifest) for manifest in manifests],
    }


def tool_manifest_json() -> str:
    return json.dumps(tool_manifest_payload(), ensure_ascii=False, indent=2)
