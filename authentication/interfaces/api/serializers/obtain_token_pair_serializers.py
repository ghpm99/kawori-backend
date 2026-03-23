from rest_framework import serializers


class ObtainTokenPairRequestSerializer(serializers.Serializer):
    username = serializers.JSONField(required=False)
    password = serializers.JSONField(required=False)
