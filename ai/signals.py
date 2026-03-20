from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from ai.models import (
    PROMPT_HISTORY_ACTION_CREATED,
    PROMPT_HISTORY_ACTION_DELETED,
    PROMPT_HISTORY_ACTION_UPDATED,
    PromptOverride,
    PromptOverrideHistory,
)
from ai.prompt_service import invalidate_prompt_override_cache


@receiver(post_save, sender=PromptOverride)
def prompt_override_post_save(
    sender, instance: PromptOverride, created: bool, **kwargs
) -> None:
    PromptOverrideHistory.objects.create(
        prompt_override=instance,
        action=(
            PROMPT_HISTORY_ACTION_CREATED if created else PROMPT_HISTORY_ACTION_UPDATED
        ),
        key=instance.key,
        environment=instance.environment,
        content=instance.content,
        task_type=instance.task_type,
        schema_json=instance.schema_json,
        temperature=instance.temperature,
        max_tokens=instance.max_tokens,
        is_active=instance.is_active,
        version=instance.version,
        valid_from=instance.valid_from,
        valid_until=instance.valid_until,
        change_reason=instance.change_reason,
        changed_by=instance.updated_by,
    )
    invalidate_prompt_override_cache(
        prompt_key=instance.key, environment=instance.environment
    )


@receiver(post_delete, sender=PromptOverride)
def prompt_override_post_delete(sender, instance: PromptOverride, **kwargs) -> None:
    PromptOverrideHistory.objects.create(
        prompt_override=None,
        action=PROMPT_HISTORY_ACTION_DELETED,
        key=instance.key,
        environment=instance.environment,
        content=instance.content,
        task_type=instance.task_type,
        schema_json=instance.schema_json,
        temperature=instance.temperature,
        max_tokens=instance.max_tokens,
        is_active=instance.is_active,
        version=instance.version,
        valid_from=instance.valid_from,
        valid_until=instance.valid_until,
        change_reason=instance.change_reason,
        changed_by=instance.updated_by,
    )
    invalidate_prompt_override_cache(
        prompt_key=instance.key, environment=instance.environment
    )
