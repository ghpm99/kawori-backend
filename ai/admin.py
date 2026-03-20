from __future__ import annotations

import re

from django.contrib import admin, messages
from django.db import transaction

from ai.models import PromptOverride, PromptOverrideHistory

AI_PROMPT_EDITOR_GROUP = "AI_PROMPT_EDITOR"


@admin.register(PromptOverride)
class PromptOverrideAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "environment",
        "version",
        "is_active",
        "valid_from",
        "valid_until",
        "updated_by",
        "updated_at",
    )
    list_filter = ("key", "environment", "is_active")
    search_fields = ("key", "version", "change_reason")
    ordering = ("key", "environment", "-updated_at")
    readonly_fields = ("created_at", "updated_at", "updated_by")
    actions = ("activate_new_version", "deactivate_override", "clone_version")
    fieldsets = (
        (
            "Prompt",
            {
                "fields": (
                    "key",
                    "environment",
                    "version",
                    "is_active",
                    "task_type",
                    "schema_json",
                    "content",
                )
            },
        ),
        (
            "Runtime",
            {
                "fields": (
                    "temperature",
                    "max_tokens",
                    "valid_from",
                    "valid_until",
                )
            },
        ),
        (
            "Auditoria",
            {
                "fields": (
                    "change_reason",
                    "updated_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.action(description="Ativar nova versão")
    def activate_new_version(self, request, queryset):
        activated = 0
        for override in queryset:
            with transaction.atomic():
                if not str(override.change_reason or "").strip():
                    override.change_reason = (
                        f"Ativado via admin por {request.user.username}."
                    )

                active_items = PromptOverride.objects.filter(
                    key=override.key,
                    environment=override.environment,
                    is_active=True,
                ).exclude(pk=override.pk)

                for active_item in active_items:
                    active_item.is_active = False
                    if not str(active_item.change_reason or "").strip():
                        active_item.change_reason = (
                            f"Desativado por ativação de {override.version}."
                        )
                    active_item.updated_by = request.user
                    active_item.full_clean()
                    active_item.save()

                if not override.is_active:
                    override.is_active = True
                    override.updated_by = request.user
                    override.full_clean()
                    override.save()
                    activated += 1

        self.message_user(
            request, f"{activated} override(s) ativado(s).", level=messages.SUCCESS
        )

    @admin.action(description="Desativar override")
    def deactivate_override(self, request, queryset):
        deactivated = 0
        for override in queryset.filter(is_active=True):
            override.is_active = False
            if not str(override.change_reason or "").strip():
                override.change_reason = (
                    f"Desativado via admin por {request.user.username}."
                )
            override.updated_by = request.user
            override.full_clean()
            override.save()
            deactivated += 1

        self.message_user(
            request, f"{deactivated} override(s) desativado(s).", level=messages.SUCCESS
        )

    @admin.action(description="Clonar versão")
    def clone_version(self, request, queryset):
        cloned = 0
        for override in queryset:
            clone = PromptOverride(
                key=override.key,
                environment=override.environment,
                content=override.content,
                task_type=override.task_type,
                schema_json=override.schema_json,
                temperature=override.temperature,
                max_tokens=override.max_tokens,
                is_active=False,
                version=_next_version(override.version),
                valid_from=override.valid_from,
                valid_until=override.valid_until,
                updated_by=request.user,
                change_reason=f"Clonado de {override.version} por {request.user.username}.",
            )
            clone.full_clean()
            clone.save()
            cloned += 1

        self.message_user(
            request, f"{cloned} override(s) clonado(s).", level=messages.SUCCESS
        )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.is_active:
            readonly_fields.extend(
                [
                    "key",
                    "environment",
                    "version",
                    "is_active",
                    "task_type",
                    "schema_json",
                    "content",
                    "temperature",
                    "max_tokens",
                    "valid_from",
                    "valid_until",
                ]
            )
        return tuple(dict.fromkeys(readonly_fields))

    def has_module_permission(self, request):
        return self._is_prompt_editor(request)

    def has_view_permission(self, request, obj=None):
        return self._is_prompt_editor(request)

    def has_add_permission(self, request):
        return self._is_prompt_editor(request)

    def has_change_permission(self, request, obj=None):
        return self._is_prompt_editor(request)

    def has_delete_permission(self, request, obj=None):
        return self._is_prompt_editor(request)

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @staticmethod
    def _is_prompt_editor(request) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name=AI_PROMPT_EDITOR_GROUP).exists()


@admin.register(PromptOverrideHistory)
class PromptOverrideHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "environment",
        "version",
        "action",
        "is_active",
        "changed_by",
        "changed_at",
    )
    list_filter = ("key", "environment", "action", "is_active")
    search_fields = ("key", "version", "change_reason")
    ordering = ("-changed_at",)
    readonly_fields = (
        "prompt_override",
        "action",
        "key",
        "environment",
        "content",
        "task_type",
        "schema_json",
        "temperature",
        "max_tokens",
        "is_active",
        "version",
        "valid_from",
        "valid_until",
        "change_reason",
        "changed_by",
        "changed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_module_permission(self, request):
        return PromptOverrideAdmin._is_prompt_editor(request)

    def has_view_permission(self, request, obj=None):
        return PromptOverrideAdmin._is_prompt_editor(request)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def _next_version(version: str) -> str:
    match = re.search(r"(\d+)$", str(version or ""))
    if not match:
        return f"{version}-copy" if version else "v1"

    prefix = version[: match.start(1)]
    current_number = int(match.group(1))
    return f"{prefix}{current_number + 1}"
