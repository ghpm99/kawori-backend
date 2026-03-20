from __future__ import annotations

from typing import Any

from ai.exceptions import AIConfigurationError
from ai.providers import (
    AIProviderRegistry,
    AnthropicMessagesProvider,
    CohereChatProvider,
    GoogleGeminiProvider,
    OpenAIChatProvider,
    OpenAICompatibleChatProvider,
)


def build_provider_registry(provider_settings: dict[str, Any]) -> AIProviderRegistry:
    providers = {}

    for provider_key, provider_conf in (provider_settings or {}).items():
        if not isinstance(provider_conf, dict):
            raise AIConfigurationError(
                f"Provider '{provider_key}' possui configuração inválida."
            )

        engine = (provider_conf.get("engine") or "").strip().lower()
        if engine == "openai":
            providers[provider_key] = OpenAIChatProvider(
                provider_key=provider_key,
                api_key=provider_conf.get("api_key", ""),
                base_url=provider_conf.get("base_url", "https://api.openai.com/v1"),
            )
            continue

        if engine == "anthropic":
            providers[provider_key] = AnthropicMessagesProvider(
                provider_key=provider_key,
                api_key=provider_conf.get("api_key", ""),
                base_url=provider_conf.get("base_url", "https://api.anthropic.com/v1"),
                api_version=provider_conf.get("api_version", "2023-06-01"),
            )
            continue

        if engine == "openai_compatible":
            providers[provider_key] = OpenAICompatibleChatProvider(
                provider_key=provider_key,
                api_key=provider_conf.get("api_key", ""),
                base_url=provider_conf.get("base_url", ""),
                auth_header_name=provider_conf.get("auth_header_name", "Authorization"),
                auth_prefix=provider_conf.get("auth_prefix", "Bearer "),
                completions_path=provider_conf.get(
                    "completions_path", "/chat/completions"
                ),
            )
            continue

        if engine == "google_gemini":
            providers[provider_key] = GoogleGeminiProvider(
                provider_key=provider_key,
                api_key=provider_conf.get("api_key", ""),
                base_url=provider_conf.get(
                    "base_url", "https://generativelanguage.googleapis.com/v1beta"
                ),
            )
            continue

        if engine == "cohere_chat":
            providers[provider_key] = CohereChatProvider(
                provider_key=provider_key,
                api_key=provider_conf.get("api_key", ""),
                base_url=provider_conf.get("base_url", "https://api.cohere.com/v2"),
            )
            continue

        raise AIConfigurationError(
            f"Engine '{engine or 'vazio'}' não suportada no provider '{provider_key}'."
        )

    if not providers:
        raise AIConfigurationError("Nenhum provider de IA foi configurado.")

    return AIProviderRegistry(providers)
