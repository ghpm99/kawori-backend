from __future__ import annotations

import requests

from ai.dto import ProviderCompletionRequest, ProviderCompletionResponse
from ai.exceptions import (
    AIConfigurationError,
    AIProviderError,
    AIProviderTimeoutError,
    AIResponseFormatError,
)
from ai.providers.base import AIProviderGateway


class GoogleGeminiProvider(AIProviderGateway):
    def __init__(
        self,
        *,
        provider_key: str,
        api_key: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
    ) -> None:
        self.provider_key = provider_key
        self.api_key = api_key or ""
        self.base_url = (
            base_url or "https://generativelanguage.googleapis.com/v1beta"
        ).rstrip("/")

    def generate(
        self, request: ProviderCompletionRequest
    ) -> ProviderCompletionResponse:
        if not self.api_key:
            raise AIConfigurationError(
                f"Provider '{self.provider_key}' sem API key configurada."
            )

        user_parts: list[dict[str, str]] = []
        system_parts: list[dict[str, str]] = []
        for message in request.messages:
            if message.role == "system":
                system_parts.append({"text": message.content})
            else:
                user_parts.append({"text": message.content})

        if not user_parts:
            raise AIResponseFormatError(
                "Mensagem do usuário não foi fornecida para o provider Google Gemini."
            )

        payload: dict[str, object] = {
            "contents": [
                {
                    "role": "user",
                    "parts": user_parts,
                }
            ]
        }
        generation_config: dict[str, object] = {}
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.max_tokens is not None:
            generation_config["maxOutputTokens"] = request.max_tokens
        if generation_config:
            payload["generationConfig"] = generation_config
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}

        url = f"{self.base_url}/models/{request.model}:generateContent"
        params = {"key": self.api_key}
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(
                url,
                headers=headers,
                params=params,
                json=payload,
                timeout=request.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise AIProviderTimeoutError(
                f"Timeout ao chamar provider '{self.provider_key}'."
            ) from exc
        except requests.RequestException as exc:
            raise AIProviderError(
                f"Falha de comunicação com provider '{self.provider_key}'."
            ) from exc

        if response.status_code >= 400:
            body = response.text[:500]
            raise AIProviderError(
                f"Provider '{self.provider_key}' retornou erro {response.status_code}: {body}",
                status_code=response.status_code,
                transient=response.status_code == 429 or response.status_code >= 500,
            )

        try:
            response_payload = response.json()
        except ValueError as exc:
            raise AIResponseFormatError(
                f"Provider '{self.provider_key}' retornou JSON inválido."
            ) from exc

        candidates = response_payload.get("candidates") or []
        if not candidates:
            raise AIResponseFormatError(
                f"Provider '{self.provider_key}' retornou resposta sem candidates."
            )
        first_candidate = candidates[0] or {}
        content = first_candidate.get("content") or {}
        parts = content.get("parts") or []
        raw_text = "".join(
            part.get("text", "") for part in parts if isinstance(part, dict)
        ).strip()
        if not raw_text:
            raise AIResponseFormatError(
                f"Provider '{self.provider_key}' retornou conteúdo vazio."
            )

        return ProviderCompletionResponse(
            provider=request.provider,
            model=request.model,
            raw_text=raw_text,
            raw_payload=response_payload,
            finish_reason=first_candidate.get("finishReason"),
        )
