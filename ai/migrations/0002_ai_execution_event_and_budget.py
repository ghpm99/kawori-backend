# Generated manually for AI telemetry and budget governance

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ai", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIBudgetPolicy",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("feature_name", models.CharField(max_length=128, unique=True)),
                ("active", models.BooleanField(db_index=True, default=True)),
                (
                    "daily_limit_usd",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=12, null=True
                    ),
                ),
                (
                    "monthly_limit_usd",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=12, null=True
                    ),
                ),
                (
                    "user_daily_limit_usd",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=12, null=True
                    ),
                ),
                (
                    "user_monthly_limit_usd",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=12, null=True
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "ai_budget_policy",
                "ordering": ["feature_name"],
            },
        ),
        migrations.CreateModel(
            name="AIExecutionEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("trace_id", models.CharField(db_index=True, max_length=64)),
                (
                    "feature_name",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=128
                    ),
                ),
                (
                    "task_type",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=64
                    ),
                ),
                ("provider", models.CharField(blank=True, default="", max_length=64)),
                ("model", models.CharField(blank=True, default="", max_length=128)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("used_fallback", models.BooleanField(default=False)),
                ("latency_ms", models.PositiveIntegerField(default=0)),
                ("success", models.BooleanField(db_index=True, default=False)),
                ("error_message", models.TextField(blank=True, default="")),
                ("prompt_tokens", models.PositiveIntegerField(default=0)),
                ("completion_tokens", models.PositiveIntegerField(default=0)),
                ("total_tokens", models.PositiveIntegerField(default=0)),
                (
                    "cost_estimate",
                    models.DecimalField(
                        blank=True, decimal_places=6, max_digits=12, null=True
                    ),
                ),
                (
                    "cache_status",
                    models.CharField(blank=True, default="", max_length=16),
                ),
                ("retry_count", models.PositiveIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ai_execution_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "ai_execution_event",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="aiexecutionevent",
            index=models.Index(fields=["created_at"], name="ai_exec_event_created_idx"),
        ),
        migrations.AddIndex(
            model_name="aiexecutionevent",
            index=models.Index(
                fields=["feature_name", "created_at"],
                name="ai_exec_event_feature_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="aiexecutionevent",
            index=models.Index(
                fields=["trace_id", "created_at"],
                name="ai_exec_event_trace_created_idx",
            ),
        ),
    ]
