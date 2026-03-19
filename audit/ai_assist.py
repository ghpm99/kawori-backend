from __future__ import annotations

import logging
from typing import Any

from ai.assist import safe_execute_ai_task
from ai.prompt_service import build_ai_request_from_prompt

logger = logging.getLogger(__name__)


def _normalize_list(value: Any, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        text = str(item).strip()
        if text and text not in normalized:
            normalized.append(text)
        if len(normalized) >= limit:
            break
    return normalized


def _build_candidates(summary: dict, failures_by_action: list[dict], by_user: list[dict]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    total = int(summary.get("total_events", 0) or 0)
    failures = int(summary.get("failure_events", 0) or 0) + int(summary.get("error_events", 0) or 0)

    if total > 0 and (failures / total) >= 0.25:
        candidates.append(
            {
                "signal": "high_failure_ratio",
                "value": round((failures / total) * 100, 2),
                "detail": "Taxa de falhas/erros acima de 25% no período filtrado.",
            }
        )

    if failures_by_action:
        top_failure = failures_by_action[0]
        if int(top_failure.get("count", 0) or 0) >= 3:
            candidates.append(
                {
                    "signal": "repeated_failure_action",
                    "value": top_failure.get("count"),
                    "detail": f"Ação com falhas repetidas: {top_failure.get('action')}.",
                }
            )

    if by_user:
        top_user = by_user[0]
        if int(top_user.get("count", 0) or 0) >= 20:
            candidates.append(
                {
                    "signal": "high_activity_user",
                    "value": top_user.get("count"),
                    "detail": f"Usuário com volume alto de eventos: {top_user.get('username')}.",
                }
            )

    return candidates


def build_audit_ai_insights(
    *,
    filters: dict[str, Any],
    summary: dict[str, Any],
    interactions_by_day: list[dict[str, Any]],
    by_action: list[dict[str, Any]],
    by_category: list[dict[str, Any]],
    by_user: list[dict[str, Any]],
    failures_by_action: list[dict[str, Any]],
) -> dict[str, Any] | None:
    anomaly_candidates = _build_candidates(summary, failures_by_action, by_user)

    payload = {
        "filters": filters,
        "summary": summary,
        "interactions_by_day": interactions_by_day[:14],
        "by_action": by_action[:10],
        "by_category": by_category[:10],
        "by_user": by_user[:10],
        "failures_by_action": failures_by_action[:10],
        "anomaly_candidates": anomaly_candidates,
    }

    try:
        built_request = build_ai_request_from_prompt(
            prompt_key="audit.insights.v1",
            payload=payload,
            feature_name="audit_insights",
        )
    except Exception:
        logger.exception("Falha ao montar prompt para insights de auditoria.")
        return None

    response = safe_execute_ai_task(
        built_request.task_request,
        feature_name="audit_insights",
    )
    if response is None or not isinstance(response.output, dict):
        return None

    output = response.output
    result = {
        "summary": str(output.get("summary", "")).strip(),
        "incident_clusters": _normalize_list(output.get("incident_clusters"), limit=6),
        "probable_root_causes": _normalize_list(output.get("probable_root_causes"), limit=6),
        "recommended_actions": _normalize_list(output.get("recommended_actions"), limit=8),
        "anomaly_candidates": anomaly_candidates,
        "trace_id": response.trace_id,
        "provider": response.provider,
        "model": response.model,
        "prompt_key": built_request.prompt_resolution.key,
        "prompt_source": built_request.prompt_resolution.source,
        "prompt_version": built_request.prompt_resolution.version,
        "prompt_hash": built_request.prompt_resolution.content_hash,
    }

    if not result["summary"] and not result["incident_clusters"] and not result["recommended_actions"]:
        return None

    return result
