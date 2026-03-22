from rest_framework import serializers


class CSVAIMapInputSerializer(serializers.Serializer):
    headers = serializers.ListField(
        child=serializers.CharField(allow_blank=True, trim_whitespace=False),
        allow_empty=False,
    )
    sample_rows = serializers.JSONField(required=False)
    import_type = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )
