from django.contrib import admin

from mailer.models import EmailQueue, UserEmailPreference


@admin.register(EmailQueue)
class EmailQueueAdmin(admin.ModelAdmin):
    list_display = ("email_type", "to_email", "status", "priority", "category", "retry_count", "scheduled_at", "sent_at")
    list_filter = ("status", "email_type", "category", "priority")
    search_fields = ("to_email", "subject", "skip_reason")
    readonly_fields = (
        "user",
        "to_email",
        "from_email",
        "subject",
        "body_html",
        "email_type",
        "category",
        "priority",
        "status",
        "skip_reason",
        "context_data",
        "scheduled_at",
        "max_retries",
        "retry_count",
        "last_error",
        "created_at",
        "updated_at",
        "sent_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserEmailPreference)
class UserEmailPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "allow_all_emails", "allow_notification", "allow_promotional", "updated_at")
    list_filter = ("allow_all_emails", "allow_notification", "allow_promotional")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user", "created_at", "updated_at")
