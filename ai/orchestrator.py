from __future__ import annotations

from ai.dto import AITaskRequest, AITaskResponse, ExecutionTraceEntry, ProviderCompletionRequest
from ai.exceptions import AIConfigurationError, AIExecutionError, AIProviderError, AIResponseFormatError
from ai.providers.base import AIProviderRegistry
from ai.routing import AITaskRouter
from ai.strategies import TaskStrategyRegistry


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
        task_type = request.resolved_task_type()
        trace_id = request.resolved_trace_id()

        strategy = self._strategy_registry.get(task_type)
        route_config = self._task_router.resolve(task_type)
        messages = strategy.build_messages(request)

        model_candidates = [route_config.primary_model]
        if self._enable_fallback:
            model_candidates.extend(route_config.fallback_models)

        execution_trace: list[ExecutionTraceEntry] = []
        last_error: Exception | None = None

        for route_index, model_route in enumerate(model_candidates):
            provider = self._provider_registry.get(model_route.provider)
            max_attempts = route_config.max_retries + 1

            for attempt in range(1, max_attempts + 1):
                provider_request = ProviderCompletionRequest(
                    provider=model_route.provider,
                    model=model_route.model,
                    messages=messages,
                    timeout_seconds=request.timeout_seconds or route_config.timeout_seconds,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
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
                    if attempt < max_attempts:
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
                return AITaskResponse(
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
                )

        raise AIExecutionError(
            "Não foi possível executar a tarefa de IA com sucesso.",
            task_type=task_type,
            trace_id=trace_id,
            execution_trace=[item.to_dict() for item in execution_trace],
            last_error=last_error,
        )
