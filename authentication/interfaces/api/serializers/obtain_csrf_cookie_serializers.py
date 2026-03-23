from rest_framework import serializers


class ObtainCsrfCookieResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
