from __future__ import annotations

from typing import Any

from django.conf import settings


_DEFAULT_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input_per_1k": 0.00015, "output_per_1k": 0.0006},
    "gpt-4o": {"input_per_1k": 0.0025, "output_per_1k": 0.01},
    "claude-3-5-haiku-latest": {"input_per_1k": 0.0008, "output_per_1k": 0.004},
    "claude-3-7-sonnet-latest": {"input_per_1k": 0.003, "output_per_1k": 0.015},
}


def _get_price_table() -> dict[str, dict[str, float]]:
    configured = getattr(settings, "AI_MODEL_PRICING", None)
    if isinstance(configured, dict):
        return configured
    return _DEFAULT_PRICING


def estimate_cost(model: str, usage: dict[str, Any] | None) -> float | None:
    if not usage:
        return None

    price_table = _get_price_table()
    model_price = price_table.get(str(model or "").strip())
    if not isinstance(model_price, dict):
        return None

    try:
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        input_per_1k = float(model_price.get("input_per_1k") or 0)
        output_per_1k = float(model_price.get("output_per_1k") or 0)
    except (TypeError, ValueError, AttributeError):
        return None

    if input_per_1k < 0 or output_per_1k < 0:
        return None

    estimated = ((prompt_tokens / 1000.0) * input_per_1k) + ((completion_tokens / 1000.0) * output_per_1k)
    return round(estimated, 8)
