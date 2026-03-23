class ReportForecastAmountValueUseCase:
    def execute(self, user, date_from, date_to, cursor_factory):
        query_params = {"user_id": user.id}

        query_monthly_avg = """
            SELECT
                AVG(monthly_total) AS avg_monthly,
                COUNT(*) AS total_months
            FROM (
                SELECT
                    date_trunc('month', fp.payment_date) AS month,
                    SUM(fp.value) AS monthly_total
                FROM
                    financial_payment fp
                WHERE 1=1
                    AND fp.user_id = %(user_id)s
                    AND fp.active = true
                GROUP BY
                    date_trunc('month', fp.payment_date)
            ) monthly_totals;
        """

        with cursor_factory() as cursor:
            cursor.execute(query_monthly_avg, query_params)
            result = cursor.fetchone()

        avg_monthly = float(result[0] or 0)
        total_months = int(result[1] or 0)

        if avg_monthly == 0:
            return 0

        if date_from and date_to:
            months_in_period = (
                (date_to.year - date_from.year) * 12
                + date_to.month
                - date_from.month
                + 1
            )
        else:
            months_in_period = total_months

        return round(avg_monthly * months_in_period, 2)
