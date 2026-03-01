import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserToken(models.Model):
    class Meta:
        db_table = "auth_user_token"

    TOKEN_TYPE_PASSWORD_RESET = "password_reset"
    TOKEN_TYPE_EMAIL_VERIFICATION = "email_verification"
    TOKEN_TYPE_CHOICES = [
        (TOKEN_TYPE_PASSWORD_RESET, "Password Reset"),
        (TOKEN_TYPE_EMAIL_VERIFICATION, "Email Verification"),
    ]

    EXPIRY_CONFIG = {
        TOKEN_TYPE_PASSWORD_RESET: 30,
        TOKEN_TYPE_EMAIL_VERIFICATION: 1440,
    }

    MAX_REQUESTS_PER_IP_PER_HOUR = 5
    MAX_REQUESTS_PER_USER_PER_HOUR = 3

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tokens")
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    token_type = models.CharField(max_length=30, choices=TOKEN_TYPE_CHOICES, default=TOKEN_TYPE_PASSWORD_RESET)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    ip_requested = models.GenericIPAddressField(null=True, blank=True)
    ip_used = models.GenericIPAddressField(null=True, blank=True)

    @staticmethod
    def generate_raw_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @classmethod
    def create_for_user(cls, user: User, token_type: str, ip_address: str = None) -> str:
        cls.objects.filter(user=user, token_type=token_type, used=False).update(used=True)

        raw_token = cls.generate_raw_token()
        token_hash = cls.hash_token(raw_token)
        expiry_minutes = cls.EXPIRY_CONFIG.get(token_type, 30)
        expires_at = timezone.now() + timedelta(minutes=expiry_minutes)

        cls.objects.create(
            user=user,
            token_hash=token_hash,
            token_type=token_type,
            expires_at=expires_at,
            ip_requested=ip_address,
        )

        return raw_token

    @classmethod
    def is_rate_limited_by_ip(cls, ip_address: str, token_type: str) -> bool:
        since = timezone.now() - timedelta(hours=1)
        count = cls.objects.filter(
            ip_requested=ip_address, token_type=token_type, created_at__gte=since
        ).count()
        return count >= cls.MAX_REQUESTS_PER_IP_PER_HOUR

    @classmethod
    def is_rate_limited_by_user(cls, user: User, token_type: str) -> bool:
        since = timezone.now() - timedelta(hours=1)
        count = cls.objects.filter(
            user=user, token_type=token_type, created_at__gte=since
        ).count()
        return count >= cls.MAX_REQUESTS_PER_USER_PER_HOUR

    def is_valid(self) -> bool:
        return not self.used and timezone.now() < self.expires_at

    def consume(self, ip_address: str = None) -> None:
        self.used = True
        self.ip_used = ip_address
        self.save(update_fields=["used", "ip_used"])


class EmailVerification(models.Model):
    class Meta:
        db_table = "auth_email_verification"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="email_verification")
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
