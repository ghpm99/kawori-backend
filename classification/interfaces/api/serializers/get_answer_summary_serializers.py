from rest_framework import serializers


class GetAnswerSummaryResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
