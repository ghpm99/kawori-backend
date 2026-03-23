from rest_framework import serializers


class SaveDetailPaymentPathSerializer(serializers.Serializer):
    id = serializers.IntegerField()


class SaveDetailPaymentInputSerializer(serializers.Serializer):
    type = serializers.JSONField(required=False)
    name = serializers.JSONField(required=False)
    payment_date = serializers.JSONField(required=False)
    fixed = serializers.JSONField(required=False)
    active = serializers.JSONField(required=False)
    value = serializers.JSONField(required=False)
