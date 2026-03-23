class ReportCountPaymentUseCase:
    def execute(self, user, date_from, date_to, cursor_factory):
        query_params = {"user_id": user.id}
        if date_from and date_to:
            query_params.update({"begin": date_from, "end": date_to})
            count_payment = """
                SELECT
                    COALESCE(COUNT(id), 0) as payment_total
                FROM
                    financial_payment fp
                WHERE
                    user_id=%(user_id)s
                    AND active=true
                    AND fp."payment_date" BETWEEN %(begin)s AND %(end)s;
            """
        else:
            count_payment = """
                SELECT
                    COALESCE(COUNT(id), 0) as payment_total
                FROM
                    financial_payment fp
                WHERE
                    user_id=%(user_id)s
                    AND active=true;
            """

        with cursor_factory() as cursor:
            cursor.execute(count_payment, query_params)
            payment_total = cursor.fetchone()

        return int(payment_total[0])
