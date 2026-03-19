from __future__ import annotations

from functools import lru_cache

from django.conf import settings

from ai.dto import AITaskRequest, AITaskResponse
from ai.factory import build_provider_registry
from ai.orchestrator import AIOrchestrator
from ai.routing import AITaskRouter
from ai.strategies import build_default_task_strategy_registry


@lru_cache(maxsize=1)
def get_ai_orchestrator() -> AIOrchestrator:
    provider_registry = build_provider_registry(getattr(settings, "AI_PROVIDERS", {}))
    task_router = AITaskRouter(
        task_routes=getattr(settings, "AI_TASK_ROUTES", {}),
        default_timeout_seconds=int(getattr(settings, "AI_DEFAULT_TIMEOUT_SECONDS", 20)),
        default_max_retries=int(getattr(settings, "AI_DEFAULT_MAX_RETRIES", 1)),
    )
    strategy_registry = build_default_task_strategy_registry()

    return AIOrchestrator(
        provider_registry=provider_registry,
        task_router=task_router,
        strategy_registry=strategy_registry,
        enable_fallback=bool(getattr(settings, "AI_ENABLE_FALLBACK", True)),
    )


def reset_ai_orchestrator_cache() -> None:
    get_ai_orchestrator.cache_clear()


def execute_ai_task(task_request: AITaskRequest) -> AITaskResponse:
    return get_ai_orchestrator().execute(task_request)
