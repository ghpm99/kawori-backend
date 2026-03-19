from django.apps import AppConfig


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai"

    def ready(self) -> None:
        from ai import signals  # noqa: F401
