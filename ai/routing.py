from __future__ import annotations

from typing import Any

from ai.dto import ModelRoute, TaskRouteConfig, normalize_task_type
from ai.exceptions import AIConfigurationError


class AITaskRouter:
    def __init__(
        self,
        *,
        task_routes: dict[str, Any],
        default_timeout_seconds: int = 20,
        default_max_retries: int = 1,
    ) -> None:
        self._task_routes = task_routes or {}
        self._default_timeout_seconds = default_timeout_seconds
        self._default_max_retries = default_max_retries

    def resolve(self, task_type: str) -> TaskRouteConfig:
        normalized_task_type = normalize_task_type(task_type)
        route_payload = self._task_routes.get(normalized_task_type) or self._task_routes.get("default")
        if route_payload is None:
            raise AIConfigurationError(f"Rota de task '{normalized_task_type}' não foi configurada.")

        primary_model = self._parse_model(route_payload.get("primary"))
        fallback_models = [self._parse_model(model) for model in route_payload.get("fallbacks", [])]

        timeout_seconds = int(route_payload.get("timeout_seconds", self._default_timeout_seconds))
        timeout_seconds = max(timeout_seconds, 1)

        max_retries = int(route_payload.get("max_retries", self._default_max_retries))
        max_retries = max(max_retries, 0)

        return TaskRouteConfig(
            primary_model=primary_model,
            fallback_models=fallback_models,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    @staticmethod
    def _parse_model(payload: Any) -> ModelRoute:
        if not isinstance(payload, dict):
            raise AIConfigurationError("Configuração de modelo inválida.")

        provider = (payload.get("provider") or "").strip()
        model = (payload.get("model") or "").strip()
        if not provider or not model:
            raise AIConfigurationError("Configuração de modelo exige provider e model.")
        return ModelRoute(provider=provider, model=model)
