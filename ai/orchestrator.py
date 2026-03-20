from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from django.conf import settings

from ai.cache import get_ai_response_cache
from ai.dto import AITaskRequest, AITaskResponse, ExecutionTraceEntry, ProviderCompletionRequest
from ai.exceptions import AIConfigurationError, AIExecutionError, AIProviderError, AIProviderTimeoutError, AIResponseFormatError
from ai.providers.base import AIProviderRegistry
from ai.routing import AITaskRouter
from ai.strategies import TaskStrategyRegistry
from ai.telemetry import emit_event


class AIOrchestrator:
    def __init__(
        self,
        *,
        provider_registry: AIProviderRegistry,
        task_router: AITaskRouter,
        strategy_registry: TaskStrategyRegistry,
        enable_fallback: bool = True,
    ) -> None:
        self._provider_registry = provider_registry
        self._task_router = task_router
        self._strategy_registry = strategy_registry
        self._enable_fallback = enable_fallback

    def execute(self, request: AITaskRequest) -> AITaskResponse:
        started_at = time.monotonic()
        task_type = request.resolved_task_type()
        trace_id = request.resolved_trace_id()
        feature_name = str((request.metadata or {}).get("feature_name") or "")
        user_id = (request.metadata or {}).get("user_id")

        strategy = self._strategy_registry.get(task_type)
        route_config = self._task_router.resolve(task_type, feature_name=feature_name, metadata=request.metadata)
        messages = strategy.build_messages(request)

        max_fallback_routes = max(int(getattr(settings, "AI_MAX_FALLBACK_ROUTES", 1)), 0)
        model_candidates = [route_config.primary_model]
        if self._enable_fallback and max_fallback_routes > 0:
            model_candidates.extend(route_config.fallback_models[:max_fallback_routes])

        cache_status = "bypass"
        cached_response = self._try_get_cached_response(
            request=request,
            trace_id=trace_id,
            task_type=task_type,
            feature_name=feature_name,
            primary_provider=route_config.primary_model.provider,
            primary_model=route_config.primary_model.model,
        )
        if cached_response is not None:
            return cached_response
        if self._is_cache_enabled(feature_name):
            cache_status = "miss"

        execution_trace: list[ExecutionTraceEntry] = []
        last_error: Exception | None = None
        should_allow_fallback = True

        for route_index, model_route in enumerate(model_candidates):
            if route_index > 0 and not should_allow_fallback:
                break

            provider = self._provider_registry.get(model_route.provider)
            max_attempts = route_config.max_retries + 1

            for attempt in range(1, max_attempts + 1):
                effective_max_tokens = self._resolve_max_tokens(
                    requested_max_tokens=request.max_tokens,
                    feature_name=feature_name,
                    task_type=task_type,
                )
                provider_request = ProviderCompletionRequest(
                    provider=model_route.provider,
                    model=model_route.model,
                    messages=messages,
                    timeout_seconds=request.timeout_seconds or route_config.timeout_seconds,
                    temperature=request.temperature,
                    max_tokens=effective_max_tokens,
                    response_format=strategy.response_format,
                    metadata={
                        **request.metadata,
                        "trace_id": trace_id,
                        "task_type": task_type,
                    },
                )

                try:
                    provider_response = provider.generate(provider_request)
                    normalized_output = strategy.normalize_output(provider_response.raw_text, request)
                except (AIProviderError, AIResponseFormatError, AIConfigurationError) as exc:
                    last_error = exc
                    execution_trace.append(
                        ExecutionTraceEntry(
                            provider=model_route.provider,
                            model=model_route.model,
                            attempt=attempt,
                            success=False,
                            error_message=str(exc),
                        )
                    )

                    is_retryable = _is_retryable_error(exc)
                    should_allow_fallback = _should_fallback_for_error(exc)

                    if attempt < max_attempts and is_retryable:
                        self._sleep_for_retry(attempt)
                        continue
                    break

                execution_trace.append(
                    ExecutionTraceEntry(
                        provider=model_route.provider,
                        model=model_route.model,
                        attempt=attempt,
                        success=True,
                    )
                )

                response = AITaskResponse(
                    task_type=task_type,
                    output=normalized_output,
                    raw_output=provider_response.raw_text,
                    provider=model_route.provider,
                    model=model_route.model,
                    strategy=strategy.name,
                    trace_id=trace_id,
                    used_fallback=route_index > 0,
                    attempts=len(execution_trace),
                    execution_trace=execution_trace,
                    usage=provider_response.usage,
                    cost_estimate=provider_response.cost_estimate,
                    cache_status=cache_status,
                )

                self._store_cache(
                    request=request,
                    response=response,
                    provider=model_route.provider,
                    model=model_route.model,
                    feature_name=feature_name,
                )

                emit_event(
                    "ai_execution_success",
                    {
                        "trace_id": trace_id,
                        "feature_name": feature_name,
                        "task_type": task_type,
                        "provider": model_route.provider,
                        "model": model_route.model,
                        "attempts": len(execution_trace),
                        "used_fallback": route_index > 0,
                        "latency_ms": int((time.monotonic() - started_at) * 1000),
                        "usage": provider_response.usage,
                        "cost_estimate": provider_response.cost_estimate,
                        "cache_status": cache_status,
                        "success": True,
                        "error_message": "",
                        "execution_trace": [item.to_dict() for item in execution_trace],
                        "user_id": user_id,
                    },
                )
                return response

        emit_event(
            "ai_execution_error",
            {
                "trace_id": trace_id,
                "feature_name": feature_name,
                "task_type": task_type,
                "provider": model_candidates[0].provider if model_candidates else "",
                "model": model_candidates[0].model if model_candidates else "",
                "attempts": len(execution_trace),
                "used_fallback": any(item.success for item in execution_trace[1:]),
                "latency_ms": int((time.monotonic() - started_at) * 1000),
                "usage": None,
                "cost_estimate": None,
                "cache_status": cache_status,
                "success": False,
                "error_message": str(last_error or "unknown_error"),
                "execution_trace": [item.to_dict() for item in execution_trace],
                "user_id": user_id,
            },
        )

        raise AIExecutionError(
            "Não foi possível executar a tarefa de IA com sucesso.",
            task_type=task_type,
            trace_id=trace_id,
            execution_trace=[item.to_dict() for item in execution_trace],
            last_error=last_error,
        )

    def _try_get_cached_response(
        self,
        *,
        request: AITaskRequest,
        trace_id: str,
        task_type: str,
        feature_name: str,
        primary_provider: str,
        primary_model: str,
    ) -> AITaskResponse | None:
        if not self._is_cache_enabled(feature_name):
            emit_event(
                "ai_cache_bypass",
                {
                    "trace_id": trace_id,
                    "feature_name": feature_name,
                    "task_type": task_type,
                    "provider": primary_provider,
                    "model": primary_model,
                    "attempts": 0,
                    "used_fallback": False,
                    "latency_ms": 0,
                    "usage": None,
                    "cost_estimate": None,
                    "cache_status": "bypass",
                    "success": True,
                    "error_message": "",
                    "user_id": (request.metadata or {}).get("user_id"),
                },
            )
            return None

        cache = get_ai_response_cache()
        cache_key = cache.build_cache_key(request, provider=primary_provider, model=primary_model)
        cached = cache.get(cache_key)
        if cached is None:
            emit_event(
                "ai_cache_miss",
                {
                    "trace_id": trace_id,
                    "feature_name": feature_name,
                    "task_type": task_type,
                    "provider": primary_provider,
                    "model": primary_model,
                    "attempts": 0,
                    "used_fallback": False,
                    "latency_ms": 0,
                    "usage": None,
                    "cost_estimate": None,
                    "cache_status": "miss",
                    "success": True,
                    "error_message": "",
                    "user_id": (request.metadata or {}).get("user_id"),
                },
            )
            return None

        response = replace(cached, trace_id=trace_id, cache_status="hit")
        emit_event(
            "ai_cache_hit",
            {
                "trace_id": trace_id,
                "feature_name": feature_name,
                "task_type": task_type,
                "provider": response.provider,
                "model": response.model,
                "attempts": response.attempts,
                "used_fallback": response.used_fallback,
                "latency_ms": 0,
                "usage": response.usage,
                "cost_estimate": response.cost_estimate,
                "cache_status": "hit",
                "success": True,
                "error_message": "",
                "user_id": (request.metadata or {}).get("user_id"),
            },
        )
        return response

    def _store_cache(
        self,
        *,
        request: AITaskRequest,
        response: AITaskResponse,
        provider: str,
        model: str,
        feature_name: str,
    ) -> None:
        if not self._is_cache_enabled(feature_name):
            return

        ttl = self._resolve_cache_ttl(feature_name)
        if ttl <= 0:
            return

        cache = get_ai_response_cache()
        cache_key = cache.build_cache_key(request, provider=provider, model=model)
        cache.set(cache_key, response, ttl_seconds=ttl)

    @staticmethod
    def _sleep_for_retry(attempt: int) -> None:
        base = float(getattr(settings, "AI_RETRY_BACKOFF_SECONDS", 0.3))
        if base <= 0:
            return
        time.sleep(base * (2 ** max(attempt - 1, 0)))

    @staticmethod
    def _resolve_cache_ttl(feature_name: str) -> int:
        per_feature = getattr(settings, "AI_CACHE_TTL_SECONDS", {}) or {}
        default_ttl = int(getattr(settings, "AI_CACHE_DEFAULT_TTL_SECONDS", 0))
        return max(int(per_feature.get(feature_name, default_ttl)), 0)

    @staticmethod
    def _is_cache_enabled(feature_name: str) -> bool:
        global_enabled = bool(getattr(settings, "AI_CACHE_ENABLED", True))
        if not global_enabled:
            return False

        per_feature = getattr(settings, "AI_CACHE_FEATURE_FLAGS", {}) or {}
        return _to_bool(per_feature.get(feature_name, True), default=True)

    @staticmethod
    def _resolve_max_tokens(*, requested_max_tokens: int | None, feature_name: str, task_type: str) -> int | None:
        feature_caps = getattr(settings, "AI_MAX_TOKENS_BY_FEATURE", {}) or {}
        task_caps = getattr(settings, "AI_MAX_TOKENS_BY_TASK", {}) or {}

        caps = [requested_max_tokens]
        if feature_name in feature_caps:
            caps.append(int(feature_caps[feature_name]))
        if task_type in task_caps:
            caps.append(int(task_caps[task_type]))

        filtered = [int(value) for value in caps if value is not None and int(value) > 0]
        if not filtered:
            return None
        return min(filtered)


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, AIProviderTimeoutError):
        return True

    if isinstance(exc, AIProviderError):
        if exc.transient is not None:
            return bool(exc.transient)
        if exc.status_code is not None:
            return exc.status_code == 429 or exc.status_code >= 500

    return False


def _should_fallback_for_error(exc: Exception) -> bool:
    if isinstance(exc, (AIResponseFormatError, AIConfigurationError)):
        return False
    return _is_retryable_error(exc)


def _to_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
