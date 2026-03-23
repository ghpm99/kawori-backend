from rest_framework import serializers


class PasswordResetValidateSerializer(serializers.Serializer):
    token = serializers.CharField(required=True, allow_blank=False)
