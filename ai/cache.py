from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import asdict
from typing import Any

from ai.dto import AITaskRequest, AITaskResponse


class AIResponseCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, dict[str, Any]]] = {}

    def build_cache_key(
        self, request: AITaskRequest, *, provider: str, model: str
    ) -> str:
        relevant_metadata = {
            key: value
            for key, value in (request.metadata or {}).items()
            if key
            not in {
                "trace_id",
                "timestamp",
                "request_id",
            }
        }
        payload = {
            "task_type": request.resolved_task_type(),
            "provider": provider,
            "model": model,
            "instructions": request.instructions,
            "input_text": request.input_text,
            "context": request.context,
            "metadata": relevant_metadata,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        payload_str = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, default=str
        )
        return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    def get(self, key: str) -> AITaskResponse | None:
        now = time.time()
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, response_payload = item
            if expires_at <= now:
                self._store.pop(key, None)
                return None
        return _deserialize_task_response(response_payload)

    def set(self, key: str, value: AITaskResponse, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        with self._lock:
            self._store[key] = (
                time.time() + ttl_seconds,
                _serialize_task_response(value),
            )


_CACHE = AIResponseCache()


def get_ai_response_cache() -> AIResponseCache:
    return _CACHE


def _serialize_task_response(response: AITaskResponse) -> dict[str, Any]:
    payload = asdict(response)
    payload["execution_trace"] = [entry.to_dict() for entry in response.execution_trace]
    return payload


def _deserialize_task_response(payload: dict[str, Any]) -> AITaskResponse:
    from ai.dto import ExecutionTraceEntry

    trace_entries = [
        ExecutionTraceEntry(**item) for item in payload.get("execution_trace", [])
    ]
    data = dict(payload)
    data["execution_trace"] = trace_entries
    return AITaskResponse(**data)
