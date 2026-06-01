import json
import os
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from api.planner import normalize_plan
from api.planner_input import PlannerInput, build_planner_input
from api.schemas import AgentPlan

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-4.1"


def build_system_prompt() -> str:
    return (
        "You are the Planner for a local coding-agent runtime. "
        "Return only a planner.v1 AgentPlan JSON object. "
        "Do not execute tools. "
        "Do not write files directly. "
        "Use only tools from the provided tool_manifest. "
        "Never invent tools. "
        "Every step must have id, thought, tool, and input. "
        "Prefer precise file tools over shell commands when editing files."
    )


def agent_plan_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "source": {"type": "string"},
            "goal": {"type": "string"},
            "max_steps": {"type": "integer"},
            "context": {"type": "object"},
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "thought": {"type": "string"},
                        "tool": {"type": "string"},
                        "input": {"type": "object"},
                    },
                    "required": ["id", "thought", "tool", "input"],
                },
            },
        },
        "required": ["goal", "steps"],
    }


def build_openai_payload(planner_input: PlannerInput, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": build_system_prompt(),
            },
            {
                "role": "user",
                "content": planner_input.model_dump_json(),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "agent_plan",
                "description": "A planner.v1 AgentPlan for the local coding-agent runtime.",
                "schema": agent_plan_json_schema(),
                "strict": False,
            }
        },
    }


def call_openai_responses(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    request = Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API request failed: {error.code} {body}") from error


def extract_response_text(response_payload: dict[str, Any]) -> str:
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    for item in response_payload.get("output", []):
        if item.get("type") != "message":
            continue

        for content in item.get("content", []):
            if content.get("type") not in {"output_text", "text"}:
                continue

            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text

    raise ValueError("OpenAI response did not contain output text")


def build_llm_plan(message: str, *, model: str | None = None) -> AgentPlan:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for LLM planner")

    selected_model = model or os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    planner_input = build_planner_input(message)
    payload = build_openai_payload(planner_input, selected_model)
    response_payload = call_openai_responses(payload, api_key)
    response_text = extract_response_text(response_payload)

    plan_data = json.loads(response_text)
    plan = normalize_plan(plan_data)
    plan.source = "llm"
    return plan