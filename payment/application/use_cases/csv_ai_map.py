from payment.ai_features import suggest_csv_mapping
from payment.models import ImportedPayment


class CSVAIMapUseCase:
    def execute(self, headers, sample_rows=None, import_type=None):
        rows = sample_rows if isinstance(sample_rows, list) else []
        source = str(import_type or ImportedPayment.IMPORT_SOURCE_TRANSACTIONS)
        return suggest_csv_mapping(
            headers=headers,
            sample_rows=rows,
            import_type=source,
        )
