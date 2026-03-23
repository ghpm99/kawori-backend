from rest_framework import serializers


class SendCommandPayloadSerializer(serializers.Serializer):
    cmd = serializers.JSONField(required=False)
