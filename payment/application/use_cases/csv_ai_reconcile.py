from payment.ai_features import suggest_reconciliation_matches
from payment.models import ImportedPayment


class CSVAIReconcileUseCase:
    def execute(self, user, transactions, import_type=None):
        source = str(import_type or ImportedPayment.IMPORT_SOURCE_TRANSACTIONS)
        return suggest_reconciliation_matches(
            user=user,
            transactions=transactions,
            import_type=source,
        )
