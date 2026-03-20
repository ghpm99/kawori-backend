from __future__ import annotations

import requests

from ai.dto import ProviderCompletionRequest, ProviderCompletionResponse
from ai.exceptions import (
    AIConfigurationError,
    AIProviderError,
    AIProviderTimeoutError,
    AIResponseFormatError,
)
from ai.pricing import estimate_cost
from ai.providers.base import AIProviderGateway


class OpenAICompatibleChatProvider(AIProviderGateway):
    def __init__(
        self,
        *,
        provider_key: str,
        api_key: str,
        base_url: str,
        auth_header_name: str = "Authorization",
        auth_prefix: str = "Bearer ",
        completions_path: str = "/chat/completions",
    ) -> None:
        self.provider_key = provider_key
        self.api_key = api_key or ""
        self.base_url = str(base_url or "").rstrip("/")
        self.auth_header_name = auth_header_name or "Authorization"
        self.auth_prefix = auth_prefix or ""
        self.completions_path = completions_path or "/chat/completions"

    def generate(
        self, request: ProviderCompletionRequest
    ) -> ProviderCompletionResponse:
        if not self.api_key:
            raise AIConfigurationError(
                f"Provider '{self.provider_key}' sem API key configurada."
            )
        if not self.base_url:
            raise AIConfigurationError(
                f"Provider '{self.provider_key}' sem base_url configurada."
            )

        payload: dict[str, object] = {
            "model": request.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        headers = {
            self.auth_header_name: f"{self.auth_prefix}{self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}{self.completions_path}"

        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=request.timeout_seconds
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

        choices = response_payload.get("choices") or []
        if not choices:
            raise AIResponseFormatError(
                f"Provider '{self.provider_key}' retornou resposta sem choices."
            )

        first_choice = choices[0] or {}
        message = first_choice.get("message") or {}
        raw_content = message.get("content")
        if isinstance(raw_content, str):
            raw_text = raw_content
        elif isinstance(raw_content, list):
            text_chunks = [
                chunk.get("text", "")
                for chunk in raw_content
                if isinstance(chunk, dict)
            ]
            raw_text = "".join(text_chunks).strip()
        else:
            raw_text = ""

        if not raw_text:
            raise AIResponseFormatError(
                f"Provider '{self.provider_key}' retornou conteúdo vazio."
            )

        usage = _extract_openai_compatible_usage(response_payload)
        return ProviderCompletionResponse(
            provider=request.provider,
            model=request.model,
            raw_text=raw_text,
            raw_payload=response_payload,
            finish_reason=first_choice.get("finish_reason"),
            usage=usage,
            cost_estimate=estimate_cost(request.model, usage),
        )


def _extract_openai_compatible_usage(payload: dict) -> dict[str, int] | None:
    usage = payload.get("usage") or {}
    if not isinstance(usage, dict):
        return None
    try:
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(
            usage.get("total_tokens") or (prompt_tokens + completion_tokens)
        )
    except (TypeError, ValueError):
        return None
    if prompt_tokens == 0 and completion_tokens == 0 and total_tokens == 0:
        return None
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
