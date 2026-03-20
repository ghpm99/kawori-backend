from __future__ import annotations

import requests

from ai.dto import ProviderCompletionRequest, ProviderCompletionResponse
from ai.exceptions import AIConfigurationError, AIProviderError, AIProviderTimeoutError, AIResponseFormatError
from ai.providers.base import AIProviderGateway


class CohereChatProvider(AIProviderGateway):
    def __init__(
        self,
        *,
        provider_key: str,
        api_key: str,
        base_url: str = "https://api.cohere.com/v2",
    ) -> None:
        self.provider_key = provider_key
        self.api_key = api_key or ""
        self.base_url = (base_url or "https://api.cohere.com/v2").rstrip("/")

    def generate(self, request: ProviderCompletionRequest) -> ProviderCompletionResponse:
        if not self.api_key:
            raise AIConfigurationError(f"Provider '{self.provider_key}' sem API key configurada.")

        system_messages = [message.content for message in request.messages if message.role == "system"]
        user_and_assistant_messages = [
            {"role": message.role, "content": message.content}
            for message in request.messages
            if message.role in {"user", "assistant"}
        ]
        if not user_and_assistant_messages:
            raise AIResponseFormatError("Mensagem do usuário não foi fornecida para o provider Cohere.")

        payload: dict[str, object] = {
            "model": request.model,
            "messages": user_and_assistant_messages,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if system_messages:
            payload["preamble"] = "\n".join(system_messages)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat"

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=request.timeout_seconds)
        except requests.Timeout as exc:
            raise AIProviderTimeoutError(f"Timeout ao chamar provider '{self.provider_key}'.") from exc
        except requests.RequestException as exc:
            raise AIProviderError(f"Falha de comunicação com provider '{self.provider_key}'.") from exc

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
            raise AIResponseFormatError(f"Provider '{self.provider_key}' retornou JSON inválido.") from exc

        message = response_payload.get("message") or {}
        content_items = message.get("content") or []
        raw_text = "".join(item.get("text", "") for item in content_items if isinstance(item, dict)).strip()
        if not raw_text:
            text_fallback = response_payload.get("text")
            raw_text = str(text_fallback).strip() if text_fallback is not None else ""
        if not raw_text:
            raise AIResponseFormatError(f"Provider '{self.provider_key}' retornou conteúdo vazio.")

        return ProviderCompletionResponse(
            provider=request.provider,
            model=request.model,
            raw_text=raw_text,
            raw_payload=response_payload,
            finish_reason=response_payload.get("finish_reason"),
        )
