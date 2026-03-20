from __future__ import annotations

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from ai.dto import AITaskType, normalize_task_type

PROMPT_OVERRIDE_ENVIRONMENT_ALL = "all"

PROMPT_HISTORY_ACTION_CREATED = "created"
PROMPT_HISTORY_ACTION_UPDATED = "updated"
PROMPT_HISTORY_ACTION_DELETED = "deleted"

PROMPT_HISTORY_ACTION_CHOICES = [
    (PROMPT_HISTORY_ACTION_CREATED, "Created"),
    (PROMPT_HISTORY_ACTION_UPDATED, "Updated"),
    (PROMPT_HISTORY_ACTION_DELETED, "Deleted"),
]

_ALLOWED_TASK_TYPES = {item.value for item in AITaskType}


class PromptOverride(models.Model):
    key = models.CharField(max_length=128, db_index=True)
    environment = models.CharField(max_length=32, default=PROMPT_OVERRIDE_ENVIRONMENT_ALL, db_index=True)
    content = models.TextField()
    task_type = models.CharField(max_length=64)
    schema_json = models.JSONField(default=dict, blank=True)
    temperature = models.FloatField(null=True, blank=True)
    max_tokens = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=False, db_index=True)
    version = models.CharField(max_length=32, default="v1")
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_prompt_override_updates",
    )
    change_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ai_prompt_override"
        ordering = ["key", "environment", "-updated_at"]
        indexes = [
            models.Index(fields=["key", "environment"]),
            models.Index(fields=["key", "environment", "is_active"]),
            models.Index(fields=["is_active", "updated_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["key", "environment"],
                condition=Q(is_active=True),
                name="uniq_ai_prompt_override_active_key_environment",
            )
        ]

    def clean(self) -> None:
        self.key = str(self.key or "").strip()
        self.environment = str(self.environment or "").strip().lower() or PROMPT_OVERRIDE_ENVIRONMENT_ALL
        self.version = str(self.version or "").strip() or "v1"
        self.task_type = normalize_task_type(self.task_type)

        if not self.key:
            raise ValidationError({"key": "Prompt key é obrigatório."})

        if self.task_type not in _ALLOWED_TASK_TYPES:
            raise ValidationError({"task_type": "task_type inválido."})

        if self.schema_json is not None and not isinstance(self.schema_json, dict):
            raise ValidationError({"schema_json": "schema_json precisa ser um objeto JSON."})

        if self.temperature is not None:
            try:
                self.temperature = float(self.temperature)
            except (TypeError, ValueError) as exc:
                raise ValidationError({"temperature": "temperature inválida."}) from exc

        if self.max_tokens is not None:
            try:
                self.max_tokens = int(self.max_tokens)
            except (TypeError, ValueError) as exc:
                raise ValidationError({"max_tokens": "max_tokens inválido."}) from exc
            if self.max_tokens <= 0:
                raise ValidationError({"max_tokens": "max_tokens deve ser maior que zero."})

        if self.valid_from and self.valid_until and self.valid_from >= self.valid_until:
            raise ValidationError({"valid_until": "valid_until deve ser maior que valid_from."})

        if self.is_active and not str(self.change_reason or "").strip():
            raise ValidationError({"change_reason": "change_reason é obrigatório para override ativo."})

        if self.pk:
            previous = PromptOverride.objects.filter(pk=self.pk).first()
            if previous and previous.is_active:
                protected_fields = [
                    "key",
                    "environment",
                    "content",
                    "task_type",
                    "schema_json",
                    "temperature",
                    "max_tokens",
                    "version",
                    "valid_from",
                    "valid_until",
                ]
                changed_active_payload = any(getattr(previous, field) != getattr(self, field) for field in protected_fields)
                if changed_active_payload:
                    raise ValidationError(
                        "Override ativo não pode ser editado diretamente. "
                        "Crie uma nova versão e ative a nova entrada."
                    )

    def __str__(self) -> str:
        return f"{self.key} ({self.environment}) [{self.version}]"


class PromptOverrideHistory(models.Model):
    prompt_override = models.ForeignKey(
        PromptOverride,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="history_entries",
    )
    action = models.CharField(max_length=32, choices=PROMPT_HISTORY_ACTION_CHOICES)

    key = models.CharField(max_length=128)
    environment = models.CharField(max_length=32)
    content = models.TextField()
    task_type = models.CharField(max_length=64)
    schema_json = models.JSONField(default=dict, blank=True)
    temperature = models.FloatField(null=True, blank=True)
    max_tokens = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    version = models.CharField(max_length=32, default="v1")
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    change_reason = models.TextField(blank=True, default="")

    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_prompt_override_history_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_prompt_override_history"
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["key", "environment", "-changed_at"]),
            models.Index(fields=["action", "-changed_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.key} ({self.environment}) {self.action} @ {self.changed_at.isoformat()}"


class AIExecutionEvent(models.Model):
    trace_id = models.CharField(max_length=64, db_index=True)
    feature_name = models.CharField(max_length=128, db_index=True, blank=True, default="")
    task_type = models.CharField(max_length=64, db_index=True, blank=True, default="")
    provider = models.CharField(max_length=64, blank=True, default="")
    model = models.CharField(max_length=128, blank=True, default="")
    attempts = models.PositiveIntegerField(default=0)
    used_fallback = models.BooleanField(default=False)
    latency_ms = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=False, db_index=True)
    error_message = models.TextField(blank=True, default="")
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    cost_estimate = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    cache_status = models.CharField(max_length=16, blank=True, default="")
    retry_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_execution_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_execution_event"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["feature_name", "created_at"]),
            models.Index(fields=["trace_id", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.feature_name}:{self.task_type} ({self.trace_id})"


class AIBudgetPolicy(models.Model):
    feature_name = models.CharField(max_length=128, unique=True)
    active = models.BooleanField(default=True, db_index=True)
    daily_limit_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    monthly_limit_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    user_daily_limit_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    user_monthly_limit_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ai_budget_policy"
        ordering = ["feature_name"]

    def __str__(self) -> str:
        return f"{self.feature_name} (active={self.active})"
