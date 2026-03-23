from rest_framework import serializers

from kawori.utils import format_date


class ReportPaymentPeriodQuerySerializer(serializers.Serializer):
    date_from = serializers.CharField(required=False, allow_blank=True)
    date_to = serializers.CharField(required=False, allow_blank=True)

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


class RequiredPeriodQuerySerializer(serializers.Serializer):
    date_from = serializers.CharField(required=False, allow_blank=True)
    date_to = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        date_from_raw = attrs.get("date_from")
        date_to_raw = attrs.get("date_to")

        date_from_parsed = format_date(date_from_raw) if date_from_raw else None
        if not date_from_parsed:
            raise serializers.ValidationError("date_from and date_to are required")

        date_to_parsed = format_date(date_to_raw) if date_to_raw else None
        if not date_to_parsed:
            raise serializers.ValidationError("date_from and date_to are required")

        if date_from_parsed > date_to_parsed:
            raise serializers.ValidationError(
                "date_from must be less than or equal to date_to"
            )

        attrs["date_from_parsed"] = date_from_parsed
        attrs["date_to_parsed"] = date_to_parsed
        return attrs


class DateFromRequiredQuerySerializer(serializers.Serializer):
    date_from = serializers.CharField(required=False, allow_blank=True)
    months_ahead = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        date_from_raw = attrs.get("date_from")
        date_from_parsed = format_date(date_from_raw) if date_from_raw else None
        if not date_from_parsed:
            raise serializers.ValidationError("date_from is required")

        attrs["date_from_parsed"] = date_from_parsed
        return attrs


class ReportPaymentSummaryResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload


class ReportCountPaymentResponseSerializer(serializers.Serializer):
    def to_representation(self, payload):
        return payload
