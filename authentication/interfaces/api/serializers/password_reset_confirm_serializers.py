from rest_framework import serializers


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True, allow_blank=False)
    new_password = serializers.CharField(required=True, allow_blank=False)
