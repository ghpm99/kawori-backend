from payment.ai_features import detect_statement_anomalies


class StatementAnomaliesUseCase:
    def execute(self, user, date_from, date_to):
        anomalies = detect_statement_anomalies(user, date_from, date_to)
        return {
            "data": {
                "anomalies": anomalies,
                "total_anomalies": len(anomalies),
            }
        }
