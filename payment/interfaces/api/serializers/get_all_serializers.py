from datetime import datetime, timedelta

from rest_framework import serializers

from kawori.utils import format_date


class PaymentGetAllQuerySerializer(serializers.Serializer):
    status = serializers.CharField(required=False, allow_blank=True)
    type = serializers.CharField(required=False, allow_blank=True)
    name__icontains = serializers.CharField(required=False, allow_blank=True)
    date__gte = serializers.CharField(required=False, allow_blank=True)
    date__lte = serializers.CharField(required=False, allow_blank=True)
    installments = serializers.CharField(required=False, allow_blank=True)
    payment_date__gte = serializers.CharField(required=False, allow_blank=True)
    payment_date__lte = serializers.CharField(required=False, allow_blank=True)
    fixed = serializers.CharField(required=False, allow_blank=True)
    active = serializers.CharField(required=False, allow_blank=True)
    invoice_id = serializers.CharField(required=False, allow_blank=True)
    invoice = serializers.CharField(required=False, allow_blank=True)
    page = serializers.CharField(required=False, allow_blank=True)
    page_size = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        date_gte = attrs.get("date__gte")
        if date_gte:
            attrs["date__gte_parsed"] = format_date(date_gte) or datetime(2018, 1, 1)

        date_lte = attrs.get("date__lte")
        if date_lte:
            attrs["date__lte_parsed"] = format_date(date_lte) or datetime.now() + timedelta(days=1)

        payment_date_gte = attrs.get("payment_date__gte")
        if payment_date_gte:
            attrs["payment_date__gte_parsed"] = format_date(payment_date_gte) or datetime(2018, 1, 1)

        payment_date_lte = attrs.get("payment_date__lte")
        if payment_date_lte:
            attrs["payment_date__lte_parsed"] = format_date(payment_date_lte) or datetime.now() + timedelta(days=1)

        return attrs
