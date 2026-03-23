from rest_framework import serializers


class VerifyTokenResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
