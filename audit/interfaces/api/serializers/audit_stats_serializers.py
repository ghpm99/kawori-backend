from rest_framework import serializers


class AuditStatsResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
