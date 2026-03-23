from rest_framework import serializers


class ContractListQuerySerializer(serializers.Serializer):
    id = serializers.CharField(required=False, allow_blank=True)
    page = serializers.CharField(required=False, allow_blank=True)
    page_size = serializers.CharField(required=False, allow_blank=True)


class ContractInvoicesQuerySerializer(serializers.Serializer):
    page = serializers.CharField(required=False, allow_blank=True)
    page_size = serializers.CharField(required=False, allow_blank=True)
