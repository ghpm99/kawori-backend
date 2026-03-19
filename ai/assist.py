from __future__ import annotations

import logging
from functools import lru_cache

from django.conf import settings

from ai.dto import AITaskRequest, AITaskResponse
from ai.exceptions import AIError
from ai.utils import execute_ai_task

logger = logging.getLogger(__name__)


def _to_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def has_configured_provider() -> bool:
    providers = getattr(settings, "AI_PROVIDERS", {}) or {}
    for provider_conf in providers.values():
        if not isinstance(provider_conf, dict):
            continue
        api_key = str(provider_conf.get("api_key", "") or "").strip()
        if api_key:
            return True
    return False


def is_feature_enabled(feature_name: str | None = None) -> bool:
    if not _to_bool(getattr(settings, "AI_ASSIST_ENABLED", True), True):
        return False

    if feature_name is None:
        return True

    configured_flags = getattr(settings, "AI_FEATURE_FLAGS", {}) or {}
    feature_value = configured_flags.get(feature_name, True)
    return _to_bool(feature_value, True)


def safe_execute_ai_task(
    task_request: AITaskRequest,
    *,
    feature_name: str | None = None,
) -> AITaskResponse | None:
    if not is_feature_enabled(feature_name):
        return None

    if not has_configured_provider():
        return None

    try:
        return execute_ai_task(task_request)
    except AIError as exc:
        logger.warning("IA indisponivel para feature '%s': %s", feature_name or "default", exc)
        return None
    except Exception:
        logger.exception("Falha inesperada na execucao de IA para feature '%s'.", feature_name or "default")
        return None
