from __future__ import annotations

from abc import ABC, abstractmethod

from ai.dto import ProviderCompletionRequest, ProviderCompletionResponse
from ai.exceptions import AIConfigurationError


class AIProviderGateway(ABC):
    @abstractmethod
    def generate(
        self, request: ProviderCompletionRequest
    ) -> ProviderCompletionResponse:
        raise NotImplementedError


class AIProviderRegistry:
    def __init__(self, providers: dict[str, AIProviderGateway]) -> None:
        self._providers = providers

    def get(self, provider_key: str) -> AIProviderGateway:
        provider = self._providers.get(provider_key)
        if provider is None:
            raise AIConfigurationError(
                f"Provider '{provider_key}' não foi configurado."
            )
        return provider
