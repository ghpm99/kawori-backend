from rest_framework import serializers


class SocialCallbackQuerySerializer(serializers.Serializer):
    code = serializers.CharField(required=False, allow_blank=True)
    state = serializers.CharField(required=False, allow_blank=True)
    error = serializers.CharField(required=False, allow_blank=True)
