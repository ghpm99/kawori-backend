from rest_framework import serializers


class PaymentDetailPathSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)
