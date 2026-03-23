from rest_framework import serializers


class UpdateEmailPreferencesSerializer(serializers.Serializer):
    allow_all_emails = serializers.JSONField(required=False)
    allow_notification = serializers.JSONField(required=False)
    allow_promotional = serializers.JSONField(required=False)

    def validate(self, attrs):
        for field, value in attrs.items():
            if not isinstance(value, bool):
                raise serializers.ValidationError(f"Campo '{field}' deve ser booleano.")
        return attrs
