from rest_framework import serializers


class GetAllQuestionsResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
