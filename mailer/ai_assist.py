from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, timedelta
from typing import Any

from django.utils import timezone

from ai.assist import safe_execute_ai_task
from ai.prompt_service import build_ai_request_from_prompt
from mailer.models import EmailQueue

logger = logging.getLogger(__name__)


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


def suggest_payment_notification_copy(
    user, payments: list[dict], final_date: date, channel: str
) -> dict[str, Any] | None:
    user_id = getattr(user, "id", None)
    dedupe_key = _build_notification_dedupe_key(user, payments, final_date, channel)
    recent_email = None
    if user_id is not None:
        cutoff = timezone.now() - timedelta(hours=24)
        recent_email = (
            EmailQueue.objects.filter(
                user_id=user_id,
                email_type=EmailQueue.TYPE_PAYMENT_NOTIFICATION,
                created_at__gte=cutoff,
                context_data__ai_dedupe_key=dedupe_key,
            )
            .exclude(context_data={})
            .order_by("-created_at")
            .first()
        )
    if recent_email:
        cached_copy = (recent_email.context_data or {}).get("ai_copy") or {}
        if isinstance(cached_copy, dict) and cached_copy.get("subject_prefix"):
            return {
                "subject_prefix": str(cached_copy.get("subject_prefix", "")).strip(),
                "intro": str(cached_copy.get("intro", "")).strip(),
                "highlights": _normalize_lines(cached_copy.get("highlights"), limit=5),
                "source": "reused",
                "dedupe_key": dedupe_key,
            }

    payload = {
        "channel": channel,
        "username": getattr(user, "username", ""),
        "total_payments": len(payments),
        "total_value": round(
            sum(float(item.get("value", 0) or 0) for item in payments), 2
        ),
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

    try:
        built_request = build_ai_request_from_prompt(
            prompt_key="mailer.communication_notifications.v1",
            payload=payload,
            feature_name="communication_notifications",
            extra_metadata={"user_id": user_id},
        )
    except Exception:
        logger.exception("Falha ao montar prompt para notificação financeira.")
        return None

    response = safe_execute_ai_task(
        built_request.task_request,
        feature_name="communication_notifications",
        user_id=user_id,
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
        "source": "ai",
        "dedupe_key": dedupe_key,
        "trace_id": response.trace_id,
        "provider": response.provider,
        "model": response.model,
        "prompt_key": built_request.prompt_resolution.key,
        "prompt_source": built_request.prompt_resolution.source,
        "prompt_version": built_request.prompt_resolution.version,
        "prompt_hash": built_request.prompt_resolution.content_hash,
    }


def _build_notification_dedupe_key(
    user, payments: list[dict], final_date: date, channel: str
) -> str:
    payload = {
        "user_id": getattr(user, "id", None),
        "channel": channel,
        "final_date": final_date.isoformat(),
        "total_payments": len(payments),
        "total_value": round(
            sum(float(item.get("value", 0) or 0) for item in payments), 2
        ),
        "payments": [
            {
                "name": item.get("name"),
                "value": float(item.get("value", 0) or 0),
                "payment_date": item.get("payment_date"),
            }
            for item in sorted(payments, key=lambda p: str(p.get("name", "")))[:12]
        ],
    }
    payload_raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload_raw.encode("utf-8")).hexdigest()
