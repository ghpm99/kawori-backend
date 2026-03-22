from payment.ai_features import normalize_csv_transactions


class CSVAINormalizeUseCase:
    def execute(self, transactions):
        return normalize_csv_transactions(transactions)
