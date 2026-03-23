from rest_framework import serializers


class AnswerByClassResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
