from rest_framework import serializers


class MetricsEventsResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
