from pydantic import BaseModel
from typing import Any


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


class AgentDecision(BaseModel):
    mode: str
    thought: str
    tool: str
    input: dict[str, str]


class AgentStep(BaseModel):
    id: str
    thought: str
    tool: str
    input: dict[str, Any]


class AgentPlan(BaseModel):
    version: str = "planner.v1"
    source: str = "rule"
    goal: str
    max_steps: int = 8
    context: dict[str, Any] = {}
    steps: list[AgentStep]


class StepResult(BaseModel):
    step: AgentStep
    status: str
    result: dict[str, Any]


class ExecutionResult(BaseModel):
    plan: AgentPlan
    step_results: list[StepResult]
    events: list[dict[str, Any]] = []
    status: str
