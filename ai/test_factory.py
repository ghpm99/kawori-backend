from django.test import SimpleTestCase

from ai.factory import build_provider_registry
from ai.providers import (
    AnthropicMessagesProvider,
    CohereChatProvider,
    GoogleGeminiProvider,
    OpenAICompatibleChatProvider,
)


class ProviderFactoryTestCase(SimpleTestCase):
    def test_build_registry_supports_famous_provider_engines(self):
        registry = build_provider_registry(
            {
                "anthropic": {
                    "engine": "anthropic",
                    "api_key": "a-key",
                    "base_url": "https://api.anthropic.com/v1",
                },
                "gemini": {
                    "engine": "google_gemini",
                    "api_key": "g-key",
                    "base_url": "https://generativelanguage.googleapis.com/v1beta",
                },
                "cohere": {
                    "engine": "cohere_chat",
                    "api_key": "c-key",
                    "base_url": "https://api.cohere.com/v2",
                },
                "groq": {
                    "engine": "openai_compatible",
                    "api_key": "gr-key",
                    "base_url": "https://api.groq.com/openai/v1",
                },
            }
        )

        self.assertIsInstance(registry.get("anthropic"), AnthropicMessagesProvider)
        self.assertIsInstance(registry.get("gemini"), GoogleGeminiProvider)
        self.assertIsInstance(registry.get("cohere"), CohereChatProvider)
        self.assertIsInstance(registry.get("groq"), OpenAICompatibleChatProvider)
