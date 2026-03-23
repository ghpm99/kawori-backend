from rest_framework import serializers


class AuditReportResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
