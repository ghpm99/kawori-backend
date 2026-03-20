from __future__ import annotations

from typing import Any

from django.conf import settings

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

    def resolve(
        self,
        task_type: str,
        *,
        feature_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskRouteConfig:
        normalized_task_type = normalize_task_type(task_type)
        route_payload = self._task_routes.get(normalized_task_type) or self._task_routes.get("default")
        if route_payload is None:
            raise AIConfigurationError(f"Rota de task '{normalized_task_type}' não foi configurada.")

        primary_model = self._parse_model(route_payload.get("primary"))
        fallback_models = [self._parse_model(model) for model in route_payload.get("fallbacks", [])]
        primary_model = self._resolve_cost_tier_route(
            primary_model=primary_model,
            feature_name=feature_name,
            metadata=metadata,
        )

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
    def _resolve_cost_tier_route(
        *,
        primary_model: ModelRoute,
        feature_name: str | None,
        metadata: dict[str, Any] | None,
    ) -> ModelRoute:
        if not feature_name:
            return primary_model

        feature_tiers = getattr(settings, "AI_FEATURE_MODEL_TIERS", {}) or {}
        feature_conf = feature_tiers.get(feature_name) or {}
        if not isinstance(feature_conf, dict):
            return primary_model

        low_cost = feature_conf.get("low_cost")
        high_quality = feature_conf.get("high_quality")
        default_tier = str(feature_conf.get("default_tier", "low_cost")).strip().lower()
        escalation_threshold = feature_conf.get("escalation_confidence_below")

        selected = low_cost if default_tier == "low_cost" else high_quality
        if selected is None:
            selected = high_quality or low_cost
        if selected is None:
            return primary_model

        if escalation_threshold is not None:
            confidence = _extract_confidence(metadata)
            if confidence is not None and confidence < float(escalation_threshold) and high_quality:
                selected = high_quality

        try:
            return AITaskRouter._parse_model(selected)
        except AIConfigurationError:
            return primary_model

    @staticmethod
    def _parse_model(payload: Any) -> ModelRoute:
        if not isinstance(payload, dict):
            raise AIConfigurationError("Configuração de modelo inválida.")

        provider = (payload.get("provider") or "").strip()
        model = (payload.get("model") or "").strip()
        if not provider or not model:
            raise AIConfigurationError("Configuração de modelo exige provider e model.")
        return ModelRoute(provider=provider, model=model)


def _extract_confidence(metadata: dict[str, Any] | None) -> float | None:
    if not isinstance(metadata, dict):
        return None
    for key in ("heuristic_confidence", "confidence", "score"):
        value = metadata.get(key)
        if value is None:
            continue
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            continue
        return max(0.0, min(1.0, confidence))
    return None
