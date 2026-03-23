from rest_framework import serializers


class GetAllUsersResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
