from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger("ai.execution")


def emit_event(event_type: str, payload: dict[str, Any]) -> None:
    event = {
        "event_type": event_type,
        **payload,
    }
    logger.info(
        "ai_event=%s",
        json.dumps(event, ensure_ascii=False, default=str, sort_keys=True),
    )

    if not bool(getattr(settings, "AI_PERSIST_EXECUTION_EVENTS", False)):
        return

    try:
        from ai.models import AIExecutionEvent

        AIExecutionEvent.objects.create(
            trace_id=str(payload.get("trace_id") or ""),
            feature_name=str(payload.get("feature_name") or ""),
            task_type=str(payload.get("task_type") or ""),
            provider=str(payload.get("provider") or ""),
            model=str(payload.get("model") or ""),
            attempts=int(payload.get("attempts") or 0),
            used_fallback=bool(payload.get("used_fallback")),
            latency_ms=int(payload.get("latency_ms") or 0),
            success=bool(payload.get("success")),
            error_message=str(payload.get("error_message") or "")[:1000],
            prompt_tokens=int((payload.get("usage") or {}).get("prompt_tokens") or 0),
            completion_tokens=int(
                (payload.get("usage") or {}).get("completion_tokens") or 0
            ),
            total_tokens=int((payload.get("usage") or {}).get("total_tokens") or 0),
            cost_estimate=payload.get("cost_estimate"),
            cache_status=str(payload.get("cache_status") or ""),
            retry_count=max(int(payload.get("attempts") or 0) - 1, 0),
            metadata={
                "event_type": event_type,
                "fallback_used": payload.get("used_fallback"),
                "execution_trace": payload.get("execution_trace") or [],
            },
            user_id=payload.get("user_id"),
        )
    except Exception:
        logger.exception("Falha ao persistir evento de telemetria de IA")
