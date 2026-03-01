from django.contrib import admin

from audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "category", "result", "username", "ip_address", "path", "response_status", "created_at")
    list_filter = ("category", "result", "action")
    search_fields = ("username", "ip_address", "path", "action")
    readonly_fields = (
        "action",
        "category",
        "result",
        "user",
        "username",
        "ip_address",
        "user_agent",
        "path",
        "method",
        "target_model",
        "target_id",
        "detail",
        "response_status",
        "created_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
