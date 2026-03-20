# Generated manually for AI cost-reduction features

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payment", "0007_importedpayment_updated_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="importedpayment",
            name="ai_idempotency_key",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=64
            ),
        ),
        migrations.AddField(
            model_name="importedpayment",
            name="ai_suggestion_data",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="importedpayment",
            name="normalization_signature",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=64
            ),
        ),
        migrations.AddField(
            model_name="importedpayment",
            name="normalization_data",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
