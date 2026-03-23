from rest_framework import serializers

from kawori.utils import format_date


class PaymentsMonthQuerySerializer(serializers.Serializer):
    date_from = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    date_to = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)

    def validate(self, attrs):
        date_from_raw = attrs.get("date_from")
        date_to_raw = attrs.get("date_to")

        date_from_parsed = format_date(date_from_raw) if date_from_raw else None
        date_to_parsed = format_date(date_to_raw) if date_to_raw else None

        if date_from_parsed and date_to_parsed and date_from_parsed > date_to_parsed:
            raise serializers.ValidationError(
                "date_from must be less than or equal to date_to"
            )

        attrs["date_from_parsed"] = date_from_parsed
        attrs["date_to_parsed"] = date_to_parsed
        return attrs
