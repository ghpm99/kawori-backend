from rest_framework import serializers


class RefreshTokenResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
