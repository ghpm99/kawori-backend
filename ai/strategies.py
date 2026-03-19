from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from ai.dto import AIMessage, AITaskRequest, AITaskType, normalize_task_type
from ai.exceptions import AIConfigurationError, AIResponseFormatError


class AITaskStrategy(ABC):
    task_type: str
    response_format: str = "text"

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def build_messages(self, request: AITaskRequest) -> list[AIMessage]:
        raise NotImplementedError

    def normalize_output(self, raw_text: str, request: AITaskRequest) -> Any:
        return raw_text.strip()

    @staticmethod
    def _context_to_text(context: dict[str, Any]) -> str:
        if not context:
            return ""
        return json.dumps(context, ensure_ascii=False)


class TextGenerationTaskStrategy(AITaskStrategy):
    task_type = AITaskType.TEXT_GENERATION.value

    def build_messages(self, request: AITaskRequest) -> list[AIMessage]:
        system_instruction = request.instructions or "Gere uma resposta útil, objetiva e em português."
        context_text = self._context_to_text(request.context)
        user_text = request.input_text
        if context_text:
            user_text = f"{request.input_text}\n\nContexto adicional:\n{context_text}"

        return [AIMessage(role="system", content=system_instruction), AIMessage(role="user", content=user_text)]


class SummarizationTaskStrategy(AITaskStrategy):
    task_type = AITaskType.SUMMARIZATION.value

    def build_messages(self, request: AITaskRequest) -> list[AIMessage]:
        max_sentences = int(request.metadata.get("max_sentences", 5))
        system_instruction = request.instructions or "Você cria resumos claros e fiéis ao conteúdo original."
        user_text = (
            "Resuma o conteúdo abaixo em até "
            f"{max_sentences} frases, destacando apenas os pontos essenciais.\n\n{request.input_text}"
        )
        return [AIMessage(role="system", content=system_instruction), AIMessage(role="user", content=user_text)]


class ClassificationTaskStrategy(AITaskStrategy):
    task_type = AITaskType.CLASSIFICATION.value
    response_format = "json"

    def build_messages(self, request: AITaskRequest) -> list[AIMessage]:
        labels = request.metadata.get("labels") or []
        labels_text = ", ".join(labels) if labels else "não informado"
        criteria = request.metadata.get("criteria", "")
        criteria_text = f"\nCritérios adicionais: {criteria}" if criteria else ""
        system_instruction = request.instructions or "Classifique textos retornando JSON com label e confidence."
        user_text = (
            f"Classifique o texto abaixo entre as labels: {labels_text}.{criteria_text}\n"
            "Retorne JSON: {\"label\": \"...\", \"confidence\": 0.0, \"reason\": \"...\"}.\n\n"
            f"Texto: {request.input_text}"
        )
        return [AIMessage(role="system", content=system_instruction), AIMessage(role="user", content=user_text)]

    def normalize_output(self, raw_text: str, request: AITaskRequest) -> dict[str, Any]:
        labels = request.metadata.get("labels") or []
        stripped_text = raw_text.strip()
        try:
            payload = json.loads(stripped_text)
        except json.JSONDecodeError:
            if labels and stripped_text not in labels:
                raise AIResponseFormatError("Resposta de classificação fora das labels esperadas.")
            return {"label": stripped_text, "confidence": None, "reason": ""}

        if not isinstance(payload, dict):
            raise AIResponseFormatError("Resposta de classificação precisa ser um objeto JSON.")

        label = str(payload.get("label", "")).strip()
        if not label:
            raise AIResponseFormatError("Campo 'label' ausente na resposta de classificação.")
        if labels and label not in labels:
            raise AIResponseFormatError("Label retornada não pertence ao conjunto configurado.")

        confidence = payload.get("confidence")
        try:
            confidence_value = float(confidence) if confidence is not None else None
        except (TypeError, ValueError) as exc:
            raise AIResponseFormatError("Campo 'confidence' inválido na resposta de classificação.") from exc

        return {
            "label": label,
            "confidence": confidence_value,
            "reason": str(payload.get("reason", "")).strip(),
        }


class StructuredExtractionTaskStrategy(AITaskStrategy):
    task_type = AITaskType.STRUCTURED_EXTRACTION.value
    response_format = "json"

    def build_messages(self, request: AITaskRequest) -> list[AIMessage]:
        schema_definition = request.metadata.get("schema")
        schema_text = json.dumps(schema_definition, ensure_ascii=False) if schema_definition else "{}"
        system_instruction = request.instructions or "Extraia dados estruturados e retorne apenas JSON válido."
        user_text = (
            "Extraia os dados do texto abaixo seguindo o schema informado e retorne JSON válido sem markdown.\n"
            f"Schema esperado: {schema_text}\n\nTexto:\n{request.input_text}"
        )
        return [AIMessage(role="system", content=system_instruction), AIMessage(role="user", content=user_text)]

    def normalize_output(self, raw_text: str, request: AITaskRequest) -> dict[str, Any]:
        try:
            payload = json.loads(raw_text.strip())
        except json.JSONDecodeError as exc:
            raise AIResponseFormatError("Resposta da extração estruturada não é JSON válido.") from exc

        if not isinstance(payload, dict):
            raise AIResponseFormatError("Resposta da extração estruturada precisa ser um objeto JSON.")
        return payload


class SimpleTaskStrategy(AITaskStrategy):
    task_type = AITaskType.SIMPLE_TASK.value

    def build_messages(self, request: AITaskRequest) -> list[AIMessage]:
        system_instruction = request.instructions or "Resolva a tarefa de forma direta e econômica."
        return [AIMessage(role="system", content=system_instruction), AIMessage(role="user", content=request.input_text)]


class ComplexTaskStrategy(AITaskStrategy):
    task_type = AITaskType.COMPLEX_TASK.value

    def build_messages(self, request: AITaskRequest) -> list[AIMessage]:
        system_instruction = request.instructions or "Resolva a tarefa com profundidade, validando premissas e trade-offs."
        context_text = self._context_to_text(request.context)
        user_text = request.input_text
        if context_text:
            user_text = f"{request.input_text}\n\nContexto:\n{context_text}"
        return [AIMessage(role="system", content=system_instruction), AIMessage(role="user", content=user_text)]


class TaskStrategyRegistry:
    def __init__(self, strategies: list[AITaskStrategy]) -> None:
        self._strategies = {strategy.task_type: strategy for strategy in strategies}

    def get(self, task_type: str) -> AITaskStrategy:
        normalized_task_type = normalize_task_type(task_type)
        strategy = self._strategies.get(normalized_task_type)
        if strategy is None:
            raise AIConfigurationError(f"Estratégia para task_type '{normalized_task_type}' não foi configurada.")
        return strategy


def build_default_task_strategy_registry() -> TaskStrategyRegistry:
    return TaskStrategyRegistry(
        strategies=[
            TextGenerationTaskStrategy(),
            SummarizationTaskStrategy(),
            ClassificationTaskStrategy(),
            StructuredExtractionTaskStrategy(),
            SimpleTaskStrategy(),
            ComplexTaskStrategy(),
        ]
    )
