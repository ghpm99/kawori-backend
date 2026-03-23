from rest_framework import serializers


class SocialProvidersResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
