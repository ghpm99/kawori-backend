from rest_framework import serializers


class ScheduledPaymentsQuerySerializer(serializers.Serializer):
    status = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False
    )
    type = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False
    )
    name__icontains = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )
    date__gte = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False
    )
    date__lte = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False
    )
    installments = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )
    payment_date__gte = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )
    payment_date__lte = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )
    fixed = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False
    )
    active = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False
    )
    page = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False
    )
    page_size = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )
