from rest_framework import serializers


class SaveNewPaymentInputSerializer(serializers.Serializer):
    type = serializers.JSONField(required=False)
    name = serializers.JSONField(required=False)
    date = serializers.JSONField(required=False)
    payment_date = serializers.JSONField(required=False)
    installments = serializers.JSONField(required=False)
    fixed = serializers.JSONField(required=False)
    value = serializers.JSONField(required=False)


class SaveNewPaymentResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
