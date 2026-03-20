import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from ai.cache import get_ai_response_cache
from ai.dto import (
    AITaskRequest,
    AITaskType,
    ProviderCompletionRequest,
    ProviderCompletionResponse,
)
from ai.exceptions import AIExecutionError, AIProviderError, AIProviderTimeoutError
from ai.orchestrator import AIOrchestrator
from ai.providers.anthropic import AnthropicMessagesProvider
from ai.providers.base import AIProviderGateway, AIProviderRegistry
from ai.providers.openai import OpenAIChatProvider
from ai.routing import AITaskRouter
from ai.strategies import build_default_task_strategy_registry


class SequenceProvider(AIProviderGateway):
    def __init__(self, provider_key: str, sequence: list[object]):
        self.provider_key = provider_key
        self._sequence = list(sequence)
        self.calls: list[ProviderCompletionRequest] = []

    def generate(
        self, request: ProviderCompletionRequest
    ) -> ProviderCompletionResponse:
        self.calls.append(request)
        if not self._sequence:
            raise AssertionError("SequenceProvider sem respostas configuradas.")

        next_item = self._sequence.pop(0)
        if isinstance(next_item, Exception):
            raise next_item

        if isinstance(next_item, (dict, list)):
            raw_text = json.dumps(next_item, ensure_ascii=False)
        else:
            raw_text = str(next_item)

        return ProviderCompletionResponse(
            provider=request.provider,
            model=request.model,
            raw_text=raw_text,
            raw_payload={"mocked": True},
            finish_reason="stop",
        )


class AIOrchestratorTestCase(SimpleTestCase):
    def _build_orchestrator(
        self, providers: dict[str, AIProviderGateway], routes: dict
    ) -> AIOrchestrator:
        return AIOrchestrator(
            provider_registry=AIProviderRegistry(providers),
            task_router=AITaskRouter(
                task_routes=routes, default_timeout_seconds=5, default_max_retries=0
            ),
            strategy_registry=build_default_task_strategy_registry(),
            enable_fallback=True,
        )

    def test_text_generation_success_uses_strategy(self):
        provider = SequenceProvider("openai", sequence=["Texto final"])
        orchestrator = self._build_orchestrator(
            providers={"openai": provider},
            routes={
                "text_generation": {
                    "primary": {"provider": "openai", "model": "gpt-4o-mini"},
                    "fallbacks": [],
                    "timeout_seconds": 7,
                    "max_retries": 0,
                }
            },
        )

        response = orchestrator.execute(
            AITaskRequest(
                task_type=AITaskType.TEXT_GENERATION.value,
                input_text="Gere um texto sobre arquitetura.",
            )
        )

        self.assertEqual(response.output, "Texto final")
        self.assertEqual(response.strategy, "TextGenerationTaskStrategy")
        self.assertEqual(response.provider, "openai")
        self.assertEqual(response.model, "gpt-4o-mini")
        self.assertEqual(response.attempts, 1)
        self.assertFalse(response.used_fallback)
        self.assertEqual(len(provider.calls), 1)

    def test_retry_on_timeout_before_success(self):
        provider = SequenceProvider(
            "openai",
            sequence=[AIProviderTimeoutError("timeout"), "Resposta após retry"],
        )
        orchestrator = self._build_orchestrator(
            providers={"openai": provider},
            routes={
                "summarization": {
                    "primary": {"provider": "openai", "model": "gpt-4o-mini"},
                    "fallbacks": [],
                    "timeout_seconds": 5,
                    "max_retries": 1,
                }
            },
        )

        response = orchestrator.execute(
            AITaskRequest(
                task_type=AITaskType.SUMMARIZATION.value,
                input_text="Conteúdo longo para resumir.",
            )
        )

        self.assertEqual(response.output, "Resposta após retry")
        self.assertEqual(response.attempts, 2)
        self.assertFalse(response.execution_trace[0].success)
        self.assertTrue(response.execution_trace[1].success)

    def test_fallback_to_secondary_provider_when_primary_fails(self):
        primary_provider = SequenceProvider(
            "openai",
            sequence=[AIProviderError("falha no provider primário", transient=True)],
        )
        fallback_provider = SequenceProvider(
            "anthropic", sequence=["Resposta do fallback"]
        )
        orchestrator = self._build_orchestrator(
            providers={"openai": primary_provider, "anthropic": fallback_provider},
            routes={
                "simple_task": {
                    "primary": {"provider": "openai", "model": "gpt-4o-mini"},
                    "fallbacks": [
                        {"provider": "anthropic", "model": "claude-3-5-haiku-latest"}
                    ],
                    "timeout_seconds": 5,
                    "max_retries": 0,
                }
            },
        )

        response = orchestrator.execute(
            AITaskRequest(
                task_type=AITaskType.SIMPLE_TASK.value,
                input_text="Responda de forma curta.",
            )
        )

        self.assertEqual(response.provider, "anthropic")
        self.assertEqual(response.model, "claude-3-5-haiku-latest")
        self.assertTrue(response.used_fallback)
        self.assertEqual(response.attempts, 2)
        self.assertFalse(response.execution_trace[0].success)
        self.assertTrue(response.execution_trace[1].success)

    def test_non_transient_provider_error_does_not_trigger_fallback(self):
        primary_provider = SequenceProvider(
            "openai",
            sequence=[
                AIProviderError("erro de validação", status_code=400, transient=False)
            ],
        )
        fallback_provider = SequenceProvider(
            "anthropic", sequence=["não deveria chamar fallback"]
        )
        orchestrator = self._build_orchestrator(
            providers={"openai": primary_provider, "anthropic": fallback_provider},
            routes={
                "simple_task": {
                    "primary": {"provider": "openai", "model": "gpt-4o-mini"},
                    "fallbacks": [
                        {"provider": "anthropic", "model": "claude-3-5-haiku-latest"}
                    ],
                    "timeout_seconds": 5,
                    "max_retries": 1,
                }
            },
        )

        with self.assertRaises(AIExecutionError):
            orchestrator.execute(
                AITaskRequest(task_type=AITaskType.SIMPLE_TASK.value, input_text="foo")
            )

        self.assertEqual(len(primary_provider.calls), 1)
        self.assertEqual(len(fallback_provider.calls), 0)

    @override_settings(
        AI_CACHE_ENABLED=True,
        AI_CACHE_FEATURE_FLAGS={"audit_insights": True},
        AI_CACHE_TTL_SECONDS={"audit_insights": 30},
        AI_CACHE_DEFAULT_TTL_SECONDS=30,
    )
    def test_cache_hit_avoids_second_external_call(self):
        provider = SequenceProvider("openai", sequence=["primeira resposta"])
        orchestrator = self._build_orchestrator(
            providers={"openai": provider},
            routes={
                "simple_task": {
                    "primary": {"provider": "openai", "model": "gpt-4o-mini"},
                    "fallbacks": [],
                    "timeout_seconds": 5,
                    "max_retries": 0,
                }
            },
        )

        request = AITaskRequest(
            task_type=AITaskType.SIMPLE_TASK.value,
            input_text="mesmo payload",
            metadata={"feature_name": "audit_insights"},
        )
        first = orchestrator.execute(request)
        second = orchestrator.execute(request)

        self.assertEqual(first.output, second.output)
        self.assertEqual(second.cache_status, "hit")
        self.assertEqual(len(provider.calls), 1)

        cache = get_ai_response_cache()
        cache._store.clear()  # nosec - isolamento do teste

    def test_classification_strategy_parses_json_response(self):
        provider = SequenceProvider(
            "openai",
            sequence=[
                {
                    "label": "positive",
                    "confidence": 0.91,
                    "reason": "sentimento favorável",
                }
            ],
        )
        orchestrator = self._build_orchestrator(
            providers={"openai": provider},
            routes={
                "classification": {
                    "primary": {"provider": "openai", "model": "gpt-4o-mini"},
                    "fallbacks": [],
                    "timeout_seconds": 5,
                    "max_retries": 0,
                }
            },
        )

        response = orchestrator.execute(
            AITaskRequest(
                task_type=AITaskType.CLASSIFICATION.value,
                input_text="Gostei muito do produto.",
                metadata={"labels": ["positive", "negative"]},
            )
        )

        self.assertEqual(response.output["label"], "positive")
        self.assertEqual(response.output["confidence"], 0.91)
        self.assertEqual(response.strategy, "ClassificationTaskStrategy")

    def test_structured_extraction_invalid_json_raises_execution_error(self):
        provider = SequenceProvider("openai", sequence=["resposta sem json"])
        orchestrator = self._build_orchestrator(
            providers={"openai": provider},
            routes={
                "structured_extraction": {
                    "primary": {"provider": "openai", "model": "gpt-4o-mini"},
                    "fallbacks": [],
                    "timeout_seconds": 5,
                    "max_retries": 0,
                }
            },
        )

        with self.assertRaises(AIExecutionError) as context:
            orchestrator.execute(
                AITaskRequest(
                    task_type=AITaskType.STRUCTURED_EXTRACTION.value,
                    input_text="Pedido #123 total R$50,00 em 2026-01-01.",
                    metadata={
                        "schema": {
                            "order_id": "string",
                            "amount": "number",
                            "date": "string",
                        }
                    },
                )
            )

        error = context.exception
        self.assertEqual(error.task_type, AITaskType.STRUCTURED_EXTRACTION.value)
        self.assertEqual(len(error.execution_trace), 1)

    def test_default_route_is_used_when_specific_route_is_missing(self):
        provider = SequenceProvider("openai", sequence=["ok"])
        orchestrator = self._build_orchestrator(
            providers={"openai": provider},
            routes={
                "default": {
                    "primary": {"provider": "openai", "model": "gpt-4o-mini"},
                    "fallbacks": [],
                    "timeout_seconds": 3,
                    "max_retries": 0,
                }
            },
        )

        response = orchestrator.execute(
            AITaskRequest(
                task_type=AITaskType.COMPLEX_TASK.value,
                input_text="Analise impacto arquitetural.",
            )
        )

        self.assertEqual(response.model, "gpt-4o-mini")
        self.assertEqual(response.output, "ok")


class ProviderUsageParsingTestCase(SimpleTestCase):
    @patch("ai.providers.openai.requests.post")
    def test_openai_provider_extracts_usage(self, post_mock):
        fake_response = Mock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        post_mock.return_value = fake_response

        provider = OpenAIChatProvider(provider_key="openai", api_key="test")
        response = provider.generate(
            ProviderCompletionRequest(
                provider="openai",
                model="gpt-4o-mini",
                messages=[type("M", (), {"role": "user", "content": "oi"})()],
                timeout_seconds=5,
            )
        )
        self.assertEqual(response.usage["prompt_tokens"], 10)
        self.assertEqual(response.usage["completion_tokens"], 5)
        self.assertEqual(response.usage["total_tokens"], 15)

    @patch("ai.providers.anthropic.requests.post")
    def test_anthropic_provider_extracts_usage(self, post_mock):
        fake_response = Mock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": 12, "output_tokens": 7},
            "stop_reason": "end_turn",
        }
        post_mock.return_value = fake_response

        provider = AnthropicMessagesProvider(provider_key="anthropic", api_key="test")
        response = provider.generate(
            ProviderCompletionRequest(
                provider="anthropic",
                model="claude-3-5-haiku-latest",
                messages=[type("M", (), {"role": "user", "content": "oi"})()],
                timeout_seconds=5,
            )
        )
        self.assertEqual(response.usage["prompt_tokens"], 12)
        self.assertEqual(response.usage["completion_tokens"], 7)
        self.assertEqual(response.usage["total_tokens"], 19)
