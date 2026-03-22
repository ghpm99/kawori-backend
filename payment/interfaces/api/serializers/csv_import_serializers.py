from rest_framework import serializers


class ProcessCSVUploadInputSerializer(serializers.Serializer):
    headers = serializers.JSONField(required=False)
    body = serializers.JSONField(required=False)
    import_type = serializers.JSONField(required=False)
    payment_date = serializers.JSONField(required=False)
    ai_suggestion_limit = serializers.JSONField(required=False)


class CSVResolveImportsInputSerializer(serializers.Serializer):
    import_data = serializers.JSONField(required=False)
    import_type = serializers.JSONField(required=False)

    def get_import_data(self):
        return self.initial_data.get("import", [])


class CSVImportInputSerializer(serializers.Serializer):
    data = serializers.JSONField(required=False)

    def get_items(self):
        return self.initial_data.get("data")
