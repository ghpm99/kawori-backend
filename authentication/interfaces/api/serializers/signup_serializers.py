from rest_framework import serializers


class SignupRequestSerializer(serializers.Serializer):
    username = serializers.JSONField(required=False)
    password = serializers.JSONField(required=False)
    email = serializers.JSONField(required=False)
    name = serializers.JSONField(required=False)
    last_name = serializers.JSONField(required=False)
