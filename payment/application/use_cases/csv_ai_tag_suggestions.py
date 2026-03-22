from payment.ai_features import suggest_tag_suggestions


class CSVAITagSuggestionsUseCase:
    def execute(self, user, transactions):
        return suggest_tag_suggestions(user=user, transactions=transactions)
