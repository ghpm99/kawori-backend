from rest_framework import serializers


class ReportAIInsightsPayloadSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("JSON inválido")
        return data


class ReportAIInsightsResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
