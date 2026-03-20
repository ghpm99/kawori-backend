from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from django.db.models import Case, IntegerField, Q, When
from django.utils import timezone

from ai.dto import AITaskRequest, AITaskType, normalize_task_type
from ai.exceptions import AIConfigurationError

logger = logging.getLogger(__name__)


_TEMPLATE_VARIABLE_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_\.]*)\s*}}")
_ALLOWED_TASK_TYPES = {item.value for item in AITaskType}
_DEFAULT_PROMPT_ENVIRONMENT = "all"


class PromptNotFoundError(KeyError):
    pass


class PromptRenderError(ValueError):
    pass


@dataclass(frozen=True)
class PromptDefinition:
    key: str
    version: str
    task_type: str
    schema_json: dict[str, Any]
    temperature: float | None
    max_tokens: int | None
    template_file: str
    content: str
    active: bool


@dataclass(frozen=True)
class PromptResolution:
    key: str
    version: str
    source: str
    task_type: str
    schema_json: dict[str, Any]
    temperature: float | None
    max_tokens: int | None
    content: str
    content_hash: str
    environment: str

    def to_trace_metadata(self) -> dict[str, Any]:
        return {
            "prompt_key": self.key,
            "prompt_source": self.source,
            "prompt_version": self.version,
            "prompt_hash": self.content_hash,
        }


@dataclass(frozen=True)
class BuiltPromptRequest:
    task_request: AITaskRequest
    prompt_resolution: PromptResolution


@lru_cache(maxsize=4)
def _load_prompt_definitions(
    registry_path: str, prompts_root: str
) -> dict[str, PromptDefinition]:
    registry_file = Path(registry_path)
    templates_root = Path(prompts_root)

    if not registry_file.exists():
        raise AIConfigurationError(
            f"Registry de prompts não encontrado em '{registry_file}'."
        )

    try:
        payload = yaml.safe_load(registry_file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise AIConfigurationError(
            f"Registry de prompts inválido em '{registry_file}'."
        ) from exc

    if isinstance(payload, dict):
        entries = payload.get("prompts") or []
    elif isinstance(payload, list):
        entries = payload
    else:
        raise AIConfigurationError(
            "Registry de prompts deve ser um objeto com 'prompts' ou uma lista de itens."
        )

    definitions: dict[str, PromptDefinition] = {}
    for raw_item in entries:
        if not isinstance(raw_item, dict):
            raise AIConfigurationError(
                "Cada entrada do registry de prompts precisa ser um objeto."
            )

        key = str(raw_item.get("key", "")).strip()
        if not key:
            raise AIConfigurationError("Entrada do registry sem 'key'.")
        if key in definitions:
            raise AIConfigurationError(
                f"Chave de prompt duplicada no registry: '{key}'."
            )

        template_file = str(raw_item.get("template_file", "")).strip()
        if not template_file:
            raise AIConfigurationError(f"Prompt '{key}' sem 'template_file'.")

        task_type = normalize_task_type(str(raw_item.get("task_type", "")).strip())
        if task_type not in _ALLOWED_TASK_TYPES:
            raise AIConfigurationError(
                f"Prompt '{key}' possui task_type inválido: '{task_type}'."
            )

        raw_schema = raw_item.get("schema") or {}
        if not isinstance(raw_schema, dict):
            raise AIConfigurationError(
                f"Prompt '{key}' possui schema inválido; esperado objeto JSON."
            )

        temperature = _to_optional_float(
            raw_item.get("temperature"), key=key, field_name="temperature"
        )
        max_tokens = _to_optional_int(
            raw_item.get("max_tokens"), key=key, field_name="max_tokens"
        )
        active = _to_bool(raw_item.get("active", True), default=True)

        version = str(
            raw_item.get("version", "")
        ).strip() or _infer_prompt_version_from_key(key)
        template_path = templates_root / template_file
        if not template_path.exists():
            raise AIConfigurationError(
                f"Template de prompt '{template_file}' não encontrado para key '{key}'."
            )

        definitions[key] = PromptDefinition(
            key=key,
            version=version,
            task_type=task_type,
            schema_json=raw_schema,
            temperature=temperature,
            max_tokens=max_tokens,
            template_file=template_file,
            content=template_path.read_text(encoding="utf-8").strip(),
            active=active,
        )

    return definitions


class PromptService:
    _override_cache: dict[tuple[str, str], tuple[float, PromptResolution | None]] = {}
    _cache_lock = threading.Lock()
    _stats_lock = threading.Lock()
    _resolution_stats: dict[str, dict[str, int]] = {}

    def __init__(
        self,
        *,
        registry_path: Path | None = None,
        prompts_root: Path | None = None,
        override_cache_ttl_seconds: int | None = None,
    ) -> None:
        self._prompts_root = Path(
            prompts_root or getattr(settings, "AI_PROMPT_TEMPLATES_ROOT")
        )
        self._registry_path = Path(
            registry_path or getattr(settings, "AI_PROMPT_REGISTRY_PATH")
        )
        self._override_cache_ttl_seconds = int(
            override_cache_ttl_seconds
            if override_cache_ttl_seconds is not None
            else getattr(settings, "AI_PROMPT_OVERRIDE_CACHE_TTL_SECONDS", 60)
        )

    def resolve(
        self, prompt_key: str, environment: str | None = None
    ) -> PromptResolution:
        normalized_key = str(prompt_key or "").strip()
        if not normalized_key:
            raise PromptNotFoundError("Prompt key não pode ser vazio.")

        prompt_environment = _normalize_environment(
            environment or self._resolve_default_environment()
        )
        file_definition = self._load_file_prompt(normalized_key)

        if self._is_db_override_enabled():
            try:
                override_resolution = self._resolve_db_override(
                    prompt_key=normalized_key,
                    environment=prompt_environment,
                    fallback_definition=file_definition,
                )
            except Exception:
                logger.exception(
                    "Falha ao buscar override de prompt no banco (key=%s, environment=%s).",
                    normalized_key,
                    prompt_environment,
                )
                self._record_stat(normalized_key, "db_errors")
                override_resolution = None

            if override_resolution is not None:
                self._record_stat(normalized_key, "db_resolutions")
                return override_resolution

        self._record_stat(normalized_key, "file_resolutions")
        return self._definition_to_resolution(
            file_definition, source="file", environment=prompt_environment
        )

    def render(self, template: str, context: dict[str, Any] | None = None) -> str:
        return render_prompt_template(template, context=context, strict=True)

    @classmethod
    def invalidate_override_cache(
        cls, *, prompt_key: str | None = None, environment: str | None = None
    ) -> None:
        with cls._cache_lock:
            if prompt_key is None:
                cls._override_cache.clear()
                return

            normalized_key = str(prompt_key).strip()
            if not normalized_key:
                cls._override_cache.clear()
                return

            if environment is None:
                keys_to_drop = [
                    cache_key
                    for cache_key in cls._override_cache
                    if cache_key[0] == normalized_key
                ]
                for cache_key in keys_to_drop:
                    cls._override_cache.pop(cache_key, None)
                return

            cache_key = (normalized_key, _normalize_environment(environment))
            cls._override_cache.pop(cache_key, None)

    @classmethod
    def get_resolution_stats(cls) -> dict[str, dict[str, int]]:
        with cls._stats_lock:
            return {
                prompt_key: {
                    source_key: source_count
                    for source_key, source_count in source_map.items()
                }
                for prompt_key, source_map in cls._resolution_stats.items()
            }

    @classmethod
    def reset_resolution_stats(cls) -> None:
        with cls._stats_lock:
            cls._resolution_stats.clear()

    def _resolve_db_override(
        self,
        *,
        prompt_key: str,
        environment: str,
        fallback_definition: PromptDefinition,
    ) -> PromptResolution | None:
        cache_key = (prompt_key, environment)
        now_epoch = time.time()

        with self._cache_lock:
            cached_entry = self._override_cache.get(cache_key)
            if cached_entry and cached_entry[0] > now_epoch:
                return cached_entry[1]

        from ai.models import PromptOverride

        now = timezone.now()
        queryset = (
            PromptOverride.objects.filter(key=prompt_key, is_active=True)
            .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=now))
            .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=now))
            .filter(environment__in=[environment, _DEFAULT_PROMPT_ENVIRONMENT])
            .order_by(
                Case(
                    When(environment=environment, then=0),
                    default=1,
                    output_field=IntegerField(),
                ),
                "-updated_at",
            )
        )

        override = queryset.first()
        resolution: PromptResolution | None = None
        if override is not None:
            override_definition = self._build_definition_from_override(
                override, fallback_definition=fallback_definition
            )
            if override_definition is not None:
                resolution = self._definition_to_resolution(
                    override_definition, source="db", environment=environment
                )

        expires_at = now_epoch + max(self._override_cache_ttl_seconds, 1)
        with self._cache_lock:
            self._override_cache[cache_key] = (expires_at, resolution)

        return resolution

    @classmethod
    def _record_stat(cls, prompt_key: str, source: str) -> None:
        with cls._stats_lock:
            key_stats = cls._resolution_stats.setdefault(prompt_key, {})
            key_stats[source] = key_stats.get(source, 0) + 1

    def _build_definition_from_override(
        self,
        override: Any,
        *,
        fallback_definition: PromptDefinition,
    ) -> PromptDefinition | None:
        content = str(override.content or "").strip()
        if not content:
            logger.warning(
                "Override de prompt ignorado por conteúdo vazio (key=%s, id=%s).",
                override.key,
                override.pk,
            )
            return None

        task_type = normalize_task_type(
            override.task_type or fallback_definition.task_type
        )
        if task_type not in _ALLOWED_TASK_TYPES:
            logger.warning(
                "Override de prompt ignorado por task_type inválido (key=%s, id=%s, task_type=%s).",
                override.key,
                override.pk,
                override.task_type,
            )
            return None

        if override.schema_json is None:
            schema_json = fallback_definition.schema_json
        elif not isinstance(override.schema_json, dict):
            logger.warning(
                "Override de prompt ignorado por schema inválido (key=%s, id=%s).",
                override.key,
                override.pk,
            )
            return None
        else:
            schema_json = override.schema_json

        try:
            temperature = _to_optional_float(
                override.temperature, key=override.key, field_name="temperature"
            )
            max_tokens = _to_optional_int(
                override.max_tokens, key=override.key, field_name="max_tokens"
            )
        except AIConfigurationError:
            logger.warning(
                "Override de prompt ignorado por parâmetros inválidos (key=%s, id=%s).",
                override.key,
                override.pk,
            )
            return None

        version = (
            str(override.version or fallback_definition.version).strip()
            or fallback_definition.version
        )

        return PromptDefinition(
            key=fallback_definition.key,
            version=version,
            task_type=task_type,
            schema_json=schema_json,
            temperature=temperature,
            max_tokens=max_tokens,
            template_file=fallback_definition.template_file,
            content=content,
            active=True,
        )

    def _load_file_prompt(self, prompt_key: str) -> PromptDefinition:
        definitions = _load_prompt_definitions(
            registry_path=str(self._registry_path),
            prompts_root=str(self._prompts_root),
        )
        definition = definitions.get(prompt_key)
        if definition is None:
            raise PromptNotFoundError(
                f"Prompt key '{prompt_key}' não encontrado no registry."
            )
        if not definition.active:
            raise PromptNotFoundError(
                f"Prompt key '{prompt_key}' está inativo no registry."
            )
        return definition

    @staticmethod
    def _definition_to_resolution(
        definition: PromptDefinition, *, source: str, environment: str
    ) -> PromptResolution:
        content_hash = hashlib.sha256(definition.content.encode("utf-8")).hexdigest()
        return PromptResolution(
            key=definition.key,
            version=definition.version,
            source=source,
            task_type=definition.task_type,
            schema_json=definition.schema_json,
            temperature=definition.temperature,
            max_tokens=definition.max_tokens,
            content=definition.content,
            content_hash=content_hash,
            environment=environment,
        )

    @staticmethod
    def _is_db_override_enabled() -> bool:
        return _to_bool(
            getattr(settings, "AI_PROMPT_DB_OVERRIDE_ENABLED", False), default=False
        )

    @staticmethod
    def _resolve_default_environment() -> str:
        configured_value = getattr(settings, "AI_PROMPT_ENVIRONMENT", None)
        if configured_value:
            return str(configured_value)

        environment_name = getattr(settings, "ENVIRONMENT_NAME", None)
        if environment_name:
            return str(environment_name)

        return _DEFAULT_PROMPT_ENVIRONMENT


@lru_cache(maxsize=1)
def get_prompt_service() -> PromptService:
    return PromptService()


def reset_prompt_service_cache() -> None:
    get_prompt_service.cache_clear()
    _load_prompt_definitions.cache_clear()
    PromptService.invalidate_override_cache()
    PromptService.reset_resolution_stats()


def invalidate_prompt_override_cache(
    *, prompt_key: str | None = None, environment: str | None = None
) -> None:
    PromptService.invalidate_override_cache(
        prompt_key=prompt_key, environment=environment
    )


def get_prompt_resolution_stats() -> dict[str, dict[str, int]]:
    return PromptService.get_resolution_stats()


def build_ai_request_from_prompt(
    *,
    prompt_key: str,
    payload: Any,
    context: dict[str, Any] | None = None,
    feature_name: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
    environment: str | None = None,
) -> BuiltPromptRequest:
    prompt_service = get_prompt_service()
    resolution = prompt_service.resolve(prompt_key, environment=environment)
    instructions = prompt_service.render(resolution.content, context=context or {})

    metadata = dict(extra_metadata or {})
    if resolution.schema_json and "schema" not in metadata:
        metadata["schema"] = resolution.schema_json
    metadata.update(resolution.to_trace_metadata())
    if feature_name:
        metadata["feature_name"] = feature_name

    request = AITaskRequest(
        task_type=resolution.task_type,
        input_text=_serialize_payload(payload),
        instructions=instructions,
        metadata=metadata,
        temperature=resolution.temperature,
        max_tokens=resolution.max_tokens,
    )

    return BuiltPromptRequest(task_request=request, prompt_resolution=resolution)


def render_prompt_template(
    template: str, context: dict[str, Any] | None = None, *, strict: bool = True
) -> str:
    context_data = context or {}
    missing_variables: list[str] = []

    def replace(match: re.Match[str]) -> str:
        variable_name = match.group(1)
        value, found = _lookup_context_value(context_data, variable_name)
        if not found:
            missing_variables.append(variable_name)
            return match.group(0)
        return str(value)

    rendered = _TEMPLATE_VARIABLE_RE.sub(replace, template)
    if strict and missing_variables:
        raise PromptRenderError(
            "Template de prompt possui variáveis sem valor: "
            + ", ".join(sorted(set(missing_variables)))
        )

    return rendered


def _lookup_context_value(
    context: dict[str, Any], variable_name: str
) -> tuple[Any, bool]:
    current: Any = context
    for key in variable_name.split("."):
        if not isinstance(current, dict) or key not in current:
            return None, False
        current = current[key]
    return current, True


def _serialize_payload(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, default=str)


def _to_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _to_optional_float(value: Any, *, key: str, field_name: str) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise AIConfigurationError(
            f"Prompt '{key}' possui {field_name} inválido: '{value}'."
        ) from exc


def _to_optional_int(value: Any, *, key: str, field_name: str) -> int | None:
    if value is None:
        return None

    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AIConfigurationError(
            f"Prompt '{key}' possui {field_name} inválido: '{value}'."
        ) from exc

    if parsed <= 0:
        raise AIConfigurationError(
            f"Prompt '{key}' possui {field_name} inválido: '{value}'."
        )

    return parsed


def _infer_prompt_version_from_key(key: str) -> str:
    parts = key.rsplit(".", maxsplit=1)
    if len(parts) == 2 and parts[1].startswith("v"):
        return parts[1]
    return "v1"


def _normalize_environment(environment: str) -> str:
    normalized = str(environment or "").strip().lower()
    return normalized or _DEFAULT_PROMPT_ENVIRONMENT
