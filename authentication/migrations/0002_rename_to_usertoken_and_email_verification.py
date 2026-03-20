import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0001_password_reset_token"),
    ]

    operations = [
        # Rename model PasswordResetToken -> UserToken
        migrations.RenameModel(
            old_name="PasswordResetToken",
            new_name="UserToken",
        ),
        # Add token_type field with default for existing rows
        migrations.AddField(
            model_name="usertoken",
            name="token_type",
            field=models.CharField(
                choices=[
                    ("password_reset", "Password Reset"),
                    ("email_verification", "Email Verification"),
                ],
                default="password_reset",
                max_length=30,
            ),
        ),
        # Update related_name from password_reset_tokens to tokens
        migrations.AlterField(
            model_name="usertoken",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tokens",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Rename db_table
        migrations.AlterModelTable(
            name="usertoken",
            table="auth_user_token",
        ),
        # Create EmailVerification model
        migrations.CreateModel(
            name="EmailVerification",
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
                ("is_verified", models.BooleanField(default=False)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="email_verification",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "auth_email_verification",
            },
        ),
    ]
