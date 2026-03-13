from django.conf import settings
from django.db import models
from django.utils import timezone


class EmailQueue(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SENDING = "sending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SENDING, "Sending"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    PRIORITY_HIGH = 10
    PRIORITY_NORMAL = 50
    PRIORITY_LOW = 90

    TYPE_PASSWORD_RESET = "password_reset"
    TYPE_EMAIL_VERIFICATION = "email_verification"
    TYPE_PAYMENT_NOTIFICATION = "payment_notification"
    TYPE_GENERIC = "generic"
    TYPE_CHOICES = [
        (TYPE_PASSWORD_RESET, "Password Reset"),
        (TYPE_EMAIL_VERIFICATION, "Email Verification"),
        (TYPE_PAYMENT_NOTIFICATION, "Payment Notification"),
        (TYPE_GENERIC, "Generic"),
    ]

    CATEGORY_TRANSACTIONAL = "transactional"
    CATEGORY_NOTIFICATION = "notification"
    CATEGORY_PROMOTIONAL = "promotional"
    CATEGORY_CHOICES = [
        (CATEGORY_TRANSACTIONAL, "Transactional"),
        (CATEGORY_NOTIFICATION, "Notification"),
        (CATEGORY_PROMOTIONAL, "Promotional"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="email_queue"
    )
    to_email = models.EmailField()
    from_email = models.EmailField(blank=True, default="")
    subject = models.CharField(max_length=255)
    body_html = models.TextField()
    email_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_GENERIC)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_TRANSACTIONAL)
    priority = models.IntegerField(default=PRIORITY_NORMAL)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    skip_reason = models.CharField(max_length=100, blank=True, default="")
    context_data = models.JSONField(default=dict, blank=True)

    scheduled_at = models.DateTimeField(default=timezone.now)
    max_retries = models.IntegerField(default=3)
    retry_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mailer_email_queue"
        ordering = ["priority", "scheduled_at"]
        indexes = [
            models.Index(fields=["status", "scheduled_at"], name="idx_email_status_scheduled"),
            models.Index(fields=["priority", "scheduled_at"], name="idx_email_priority_scheduled"),
        ]

    def __str__(self):
        return f"[{self.status}] {self.email_type} -> {self.to_email}"


class UserEmailPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_preference"
    )
    allow_all_emails = models.BooleanField(default=True)
    allow_notification = models.BooleanField(default=True)
    allow_promotional = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mailer_user_email_preference"

    def __str__(self):
        return f"EmailPreference({self.user.username})"
