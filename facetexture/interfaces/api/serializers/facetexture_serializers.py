from rest_framework import serializers


class GetBDOClassQuerySerializer(serializers.Serializer):
    id = serializers.CharField(required=False, allow_blank=True)


class GetBDOClassResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
