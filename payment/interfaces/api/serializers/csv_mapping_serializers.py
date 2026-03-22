from rest_framework import serializers


class CSVMappingInputSerializer(serializers.Serializer):
    headers = serializers.ListField(
        child=serializers.CharField(allow_blank=True, trim_whitespace=False),
        allow_empty=False,
    )
