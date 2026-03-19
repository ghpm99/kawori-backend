from __future__ import annotations

import json
from datetime import date
from typing import Any

from ai.assist import safe_execute_ai_task
from ai.dto import AITaskRequest, AITaskType


def _normalize_lines(value: Any, limit: int = 4) -> list[str]:
    if not isinstance(value, list):
        return []
    lines = []
    for item in value:
        text = str(item).strip()
        if text and text not in lines:
            lines.append(text)
        if len(lines) >= limit:
            break
    return lines


def suggest_payment_notification_copy(user, payments: list[dict], final_date: date, channel: str) -> dict[str, Any] | None:
    payload = {
        "channel": channel,
        "username": getattr(user, "username", ""),
        "total_payments": len(payments),
        "total_value": round(sum(float(item.get("value", 0) or 0) for item in payments), 2),
        "deadline": final_date.strftime("%d/%m/%Y"),
        "top_payments": [
            {
                "name": item.get("name"),
                "date": item.get("payment_date"),
                "value": item.get("value"),
                "type": item.get("type"),
            }
            for item in payments[:8]
        ],
    }

    response = safe_execute_ai_task(
        AITaskRequest(
            task_type=AITaskType.STRUCTURED_EXTRACTION.value,
            input_text=json.dumps(payload, ensure_ascii=False),
            instructions=(
                "Crie uma comunicação objetiva para notificação financeira. Linguagem clara, sem promessas, "
                "tom operacional e respeitoso."
            ),
            metadata={
                "schema": {
                    "subject_prefix": "string",
                    "intro": "string",
                    "highlights": ["string"],
                }
            },
            temperature=0.2,
            max_tokens=180,
        ),
        feature_name="communication_notifications",
    )
    if response is None or not isinstance(response.output, dict):
        return None

    output = response.output
    subject_prefix = str(output.get("subject_prefix", "")).strip()
    intro = str(output.get("intro", "")).strip()
    if len(subject_prefix) > 90:
        subject_prefix = subject_prefix[:90]
    if len(intro) > 240:
        intro = intro[:240]

    return {
        "subject_prefix": subject_prefix,
        "intro": intro,
        "highlights": _normalize_lines(output.get("highlights"), limit=5),
        "trace_id": response.trace_id,
        "provider": response.provider,
        "model": response.model,
    }
