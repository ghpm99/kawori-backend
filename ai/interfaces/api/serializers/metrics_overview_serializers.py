from rest_framework import serializers


class MetricsOverviewResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
