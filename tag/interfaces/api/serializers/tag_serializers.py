from rest_framework import serializers


class TagListQuerySerializer(serializers.Serializer):
    name__icontains = serializers.CharField(required=False, allow_blank=True)
