from rest_framework import serializers


class MetricsTimeseriesResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
