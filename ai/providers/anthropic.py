from __future__ import annotations

import requests

from ai.dto import ProviderCompletionRequest, ProviderCompletionResponse
from ai.exceptions import AIConfigurationError, AIProviderError, AIProviderTimeoutError, AIResponseFormatError
from ai.providers.base import AIProviderGateway


class AnthropicMessagesProvider(AIProviderGateway):
    def __init__(
        self,
        *,
        provider_key: str,
        api_key: str,
        base_url: str = "https://api.anthropic.com/v1",
        api_version: str = "2023-06-01",
    ) -> None:
        self.provider_key = provider_key
        self.api_key = api_key or ""
        self.base_url = (base_url or "https://api.anthropic.com/v1").rstrip("/")
        self.api_version = api_version

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
            raise AIResponseFormatError("Mensagem do usuário não foi fornecida para o provider Anthropic.")

        payload: dict[str, object] = {
            "model": request.model,
            "messages": user_and_assistant_messages,
            "max_tokens": request.max_tokens or 512,
        }
        if system_messages:
            payload["system"] = "\n".join(system_messages)
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "content-type": "application/json",
        }
        url = f"{self.base_url}/messages"

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=request.timeout_seconds)
        except requests.Timeout as exc:
            raise AIProviderTimeoutError(f"Timeout ao chamar provider '{self.provider_key}'.") from exc
        except requests.RequestException as exc:
            raise AIProviderError(f"Falha de comunicação com provider '{self.provider_key}'.") from exc

        if response.status_code >= 400:
            body = response.text[:500]
            raise AIProviderError(f"Provider '{self.provider_key}' retornou erro {response.status_code}: {body}")

        try:
            response_payload = response.json()
        except ValueError as exc:
            raise AIResponseFormatError(f"Provider '{self.provider_key}' retornou JSON inválido.") from exc

        content_blocks = response_payload.get("content") or []
        text_chunks = [
            block.get("text", "")
            for block in content_blocks
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        raw_text = "".join(text_chunks).strip()
        if not raw_text:
            raise AIResponseFormatError(f"Provider '{self.provider_key}' retornou conteúdo vazio.")

        return ProviderCompletionResponse(
            provider=request.provider,
            model=request.model,
            raw_text=raw_text,
            raw_payload=response_payload,
            finish_reason=response_payload.get("stop_reason"),
        )
