from rest_framework import serializers


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField(required=True, allow_blank=False)
