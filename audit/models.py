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


SCRIPT_STATUS_SUCCESS = "success"
SCRIPT_STATUS_FAILURE = "failure"
SCRIPT_STATUS_SKIPPED = "skipped"

SCRIPT_STATUS_CHOICES = [
    (SCRIPT_STATUS_SUCCESS, "Success"),
    (SCRIPT_STATUS_FAILURE, "Failure"),
    (SCRIPT_STATUS_SKIPPED, "Skipped"),
]


class ReleaseScriptExecution(models.Model):
    release_version = models.CharField(max_length=20)
    script_name = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=SCRIPT_STATUS_CHOICES)
    output = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "release_script_execution"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["release_version", "script_name"]),
            models.Index(fields=["status", "-started_at"]),
        ]

    def __str__(self):
        return f"{self.release_version}:{self.script_name} ({self.status})"
