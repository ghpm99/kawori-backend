from rest_framework import serializers


class PayoffDetailPaymentPathSerializer(serializers.Serializer):
    id = serializers.IntegerField()
