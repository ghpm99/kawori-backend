from rest_framework import serializers


class GetBDOClassResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
