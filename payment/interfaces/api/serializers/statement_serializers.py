from datetime import datetime

from rest_framework import serializers


class StatementAnomaliesQuerySerializer(serializers.Serializer):
    date_from = serializers.CharField(required=False)
    date_to = serializers.CharField(required=False)

    def validate(self, attrs):
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")

        if not date_from or not date_to:
            raise serializers.ValidationError("date_from and date_to are required")

        try:
            date_from_parsed = datetime.strptime(date_from, "%Y-%m-%d").date()
            date_to_parsed = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError as exc:
            raise serializers.ValidationError(
                "date_from and date_to must be in YYYY-MM-DD format"
            ) from exc

        if date_from_parsed > date_to_parsed:
            raise serializers.ValidationError(
                "date_from must be less than or equal to date_to"
            )

        attrs["date_from_parsed"] = date_from_parsed
        attrs["date_to_parsed"] = date_to_parsed
        return attrs
