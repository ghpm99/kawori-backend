from rest_framework import serializers


class AuditLogsResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
