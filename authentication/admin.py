from django.contrib import admin

from authentication.models import SocialAccount, SocialAuthState


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "provider",
        "provider_user_id",
        "email",
        "is_email_verified",
        "last_login_at",
    )
    search_fields = (
        "user__username",
        "user__email",
        "provider",
        "provider_user_id",
        "email",
    )
    list_filter = ("provider", "is_email_verified")


@admin.register(SocialAuthState)
class SocialAuthStateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "provider",
        "mode",
        "user",
        "expires_at",
        "used",
        "created_at",
    )
    search_fields = ("provider", "user__username", "user__email")
    list_filter = ("provider", "mode", "used")
