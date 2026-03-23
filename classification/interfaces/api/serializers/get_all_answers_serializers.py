from rest_framework import serializers


class GetAllAnswersResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
