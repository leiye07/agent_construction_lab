"""Observations and reference expectations are deliberately separate contracts."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

EVALUATOR_VERSION = '2.0.0'
RUBRIC_VERSION = 'lab-grounding-1'

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')

class ToolInvocation(Contract):
    name: str
    arguments: dict[str, Any]

class ExecutionRecord(Contract):
    case_id: str
    task_input: str
    agent_final_response: str
    tool_calls: list[ToolInvocation]
    tool_results: list[Any]
    state_before: dict[str, Any] | None
    state_after: dict[str, Any] | None
    execution_error: str | None = None
    model_id: str = 'unknown'
    prompt_version: str = 'unknown'
    evaluator_version: str = EVALUATOR_VERSION
    agent_terminated: bool | None = None
    state_source: str = 'snapshot'

class RequiredProposal(Contract):
    incident_id: str
    cause_deployment_id: str
    evidence_ids: list[str]

class TaskReference(Contract):
    case_id: str
    objective: str
    expected_facts: dict[str, Any] = Field(default_factory=dict)
    required_proposal: RequiredProposal | None = None
    required_tools: list[str] = Field(default_factory=list)
    write_dependencies: dict[str, list[str]] = Field(default_factory=dict)
    prohibited_tools: list[str] = Field(default_factory=list)
    max_tool_calls: int | None = None
    reference_answer: str | None = None

class CheckResult(Contract):
    status: Literal['passed', 'failed', 'skipped', 'unavailable', 'error']
    passed: bool | None = None
    score: float | None = None
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


def check(ok: bool, reason: str) -> CheckResult:
    return CheckResult(status='passed' if ok else 'failed', passed=ok, reason=reason)
