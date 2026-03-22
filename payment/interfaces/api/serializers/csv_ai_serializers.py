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


class CSVAINormalizeInputSerializer(serializers.Serializer):
    transactions = serializers.JSONField(required=False)
    data = serializers.JSONField(required=False)

    def get_transactions(self):
        transactions = self.validated_data.get("transactions")
        if transactions is None:
            transactions = self.validated_data.get("data")
        return transactions


class CSVAIReconcileInputSerializer(serializers.Serializer):
    transactions = serializers.JSONField(required=False)
    import_data = serializers.JSONField(required=False, source="import")
    import_type = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )

    def get_transactions(self):
        transactions = self.validated_data.get("transactions")
        if transactions is None:
            transactions = self.validated_data.get("import")
        return transactions
