from rest_framework import serializers


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.CharField(required=True, allow_blank=False)

    def validate_email(self, value):
        normalized = value.strip().lower()
        if not normalized:
            raise serializers.ValidationError("E-mail é obrigatório.")
        return normalized
