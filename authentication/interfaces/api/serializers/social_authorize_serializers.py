from rest_framework import serializers


class SocialAuthorizeResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
