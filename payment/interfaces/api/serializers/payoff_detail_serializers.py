from rest_framework import serializers


class PayoffDetailPaymentPathSerializer(serializers.Serializer):
    id = serializers.IntegerField()


class PayoffDetailPaymentResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
