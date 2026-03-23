from rest_framework import serializers


class BudgetPeriodQuerySerializer(serializers.Serializer):
    period = serializers.CharField(required=False, allow_blank=True)
