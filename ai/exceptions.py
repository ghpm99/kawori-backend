from __future__ import annotations

from typing import Any


class AIError(Exception):
    """Base para erros da camada de IA."""


class AIConfigurationError(AIError):
    """Erros de configuração (rotas, providers, settings)."""


class AIProviderError(AIError):
    """Erros ao executar chamadas em providers externos."""


class AIProviderTimeoutError(AIProviderError):
    """Timeout na chamada ao provider."""


class AIResponseFormatError(AIError):
    """Resposta inválida para o formato esperado pela estratégia."""


class AIExecutionError(AIError):
    """Erro final após esgotar retries/fallbacks."""

    def __init__(
        self,
        message: str,
        *,
        task_type: str,
        trace_id: str,
        execution_trace: list[dict[str, Any]],
        last_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.task_type = task_type
        self.trace_id = trace_id
        self.execution_trace = execution_trace
        self.last_error = last_error
