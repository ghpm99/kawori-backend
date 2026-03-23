from rest_framework import serializers


class GetAllGuildsResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
