from django.contrib.auth.models import User
from django.db import models


CATEGORY_AUTH = "auth"
CATEGORY_FINANCIAL = "financial"
CATEGORY_FACETEXTURE = "facetexture"
CATEGORY_CLASSIFICATION = "classification"
CATEGORY_REMOTE = "remote"
CATEGORY_PUSHER = "pusher"

CATEGORY_CHOICES = [
    (CATEGORY_AUTH, "Auth"),
    (CATEGORY_FINANCIAL, "Financial"),
    (CATEGORY_FACETEXTURE, "Facetexture"),
    (CATEGORY_CLASSIFICATION, "Classification"),
    (CATEGORY_REMOTE, "Remote"),
    (CATEGORY_PUSHER, "Pusher"),
]

RESULT_SUCCESS = "success"
RESULT_FAILURE = "failure"
RESULT_ERROR = "error"

RESULT_CHOICES = [
    (RESULT_SUCCESS, "Success"),
    (RESULT_FAILURE, "Failure"),
    (RESULT_ERROR, "Error"),
]


class AuditLog(models.Model):
    action = models.CharField(max_length=100)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    result = models.CharField(max_length=10, choices=RESULT_CHOICES)

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    username = models.CharField(max_length=150, blank=True, default="")

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    path = models.CharField(max_length=500, blank=True, default="")
    method = models.CharField(max_length=10, blank=True, default="")

    target_model = models.CharField(max_length=100, blank=True, default="")
    target_id = models.CharField(max_length=100, blank=True, default="")

    detail = models.JSONField(default=dict, blank=True)
    response_status = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["action"]),
            models.Index(fields=["category", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.created_at}] {self.action} by {self.username} ({self.result})"
