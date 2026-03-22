from rest_framework import serializers


class ProcessCSVUploadInputSerializer(serializers.Serializer):
    headers = serializers.JSONField(required=False)
    body = serializers.JSONField(required=False)
    import_type = serializers.JSONField(required=False)
    payment_date = serializers.JSONField(required=False)
    ai_suggestion_limit = serializers.JSONField(required=False)
