from rest_framework import serializers


class PaymentDetailPathSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)


class PaymentDetailResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
