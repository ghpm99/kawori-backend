from financial.ai_features import generate_financial_ai_insights


class ReportAIInsightsUseCase:
    def execute(self, user, payload):
        return generate_financial_ai_insights(user=user, payload=payload)
