from __future__ import annotations

import requests

from ai.dto import ProviderCompletionRequest, ProviderCompletionResponse
from ai.exceptions import AIConfigurationError, AIProviderError, AIProviderTimeoutError, AIResponseFormatError
from ai.providers.base import AIProviderGateway


class OpenAIChatProvider(AIProviderGateway):
    def __init__(
        self,
        *,
        provider_key: str,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self.provider_key = provider_key
        self.api_key = api_key or ""
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")

    def generate(self, request: ProviderCompletionRequest) -> ProviderCompletionResponse:
        if not self.api_key:
            raise AIConfigurationError(f"Provider '{self.provider_key}' sem API key configurada.")

        payload: dict[str, object] = {
            "model": request.model,
            "messages": [{"role": message.role, "content": message.content} for message in request.messages],
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

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

        choices = response_payload.get("choices") or []
        if not choices:
            raise AIResponseFormatError(f"Provider '{self.provider_key}' retornou resposta sem choices.")

        first_choice = choices[0] or {}
        message = first_choice.get("message") or {}
        raw_content = message.get("content")
        if isinstance(raw_content, str):
            raw_text = raw_content
        elif isinstance(raw_content, list):
            text_chunks = [chunk.get("text", "") for chunk in raw_content if isinstance(chunk, dict)]
            raw_text = "".join(text_chunks).strip()
        else:
            raw_text = ""

        if not raw_text:
            raise AIResponseFormatError(f"Provider '{self.provider_key}' retornou conteúdo vazio.")

        return ProviderCompletionResponse(
            provider=request.provider,
            model=request.model,
            raw_text=raw_text,
            raw_payload=response_payload,
            finish_reason=first_choice.get("finish_reason"),
        )
