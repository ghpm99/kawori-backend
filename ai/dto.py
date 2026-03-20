from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AITaskType(str, Enum):
    TEXT_GENERATION = "text_generation"
    SUMMARIZATION = "summarization"
    CLASSIFICATION = "classification"
    STRUCTURED_EXTRACTION = "structured_extraction"
    SIMPLE_TASK = "simple_task"
    COMPLEX_TASK = "complex_task"


def normalize_task_type(task_type: str | AITaskType) -> str:
    if isinstance(task_type, AITaskType):
        return task_type.value
    return (task_type or "").strip().lower()


@dataclass(frozen=True)
class AIMessage:
    role: str
    content: str


@dataclass(frozen=True)
class AITaskRequest:
    task_type: str
    input_text: str
    instructions: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_seconds: int | None = None
    trace_id: str | None = None

    def resolved_task_type(self) -> str:
        return normalize_task_type(self.task_type)

    def resolved_trace_id(self) -> str:
        return self.trace_id or uuid.uuid4().hex


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str


@dataclass(frozen=True)
class TaskRouteConfig:
    primary_model: ModelRoute
    fallback_models: list[ModelRoute]
    timeout_seconds: int
    max_retries: int


@dataclass(frozen=True)
class ProviderCompletionRequest:
    provider: str
    model: str
    messages: list[AIMessage]
    timeout_seconds: int
    temperature: float | None = None
    max_tokens: int | None = None
    response_format: str = "text"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderCompletionResponse:
    provider: str
    model: str
    raw_text: str
    raw_payload: dict[str, Any]
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
    cost_estimate: float | None = None


@dataclass(frozen=True)
class ExecutionTraceEntry:
    provider: str
    model: str
    attempt: int
    success: bool
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "attempt": self.attempt,
            "success": self.success,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class AITaskResponse:
    task_type: str
    output: Any
    raw_output: str
    provider: str
    model: str
    strategy: str
    trace_id: str
    used_fallback: bool
    attempts: int
    execution_trace: list[ExecutionTraceEntry]
    usage: dict[str, int] | None = None
    cost_estimate: float | None = None
    cache_status: str = "miss"
