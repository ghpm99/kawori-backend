from rest_framework import serializers


class TotalVotesResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
