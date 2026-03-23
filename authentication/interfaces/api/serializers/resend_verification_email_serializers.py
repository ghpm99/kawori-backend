from rest_framework import serializers


class ResendVerificationEmailResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
