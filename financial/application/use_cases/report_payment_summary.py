class ReportPaymentSummaryUseCase:
    def execute(self, user, date_from, date_to, cursor_factory):
        if date_from and date_to:
            query_payments = """
                SELECT
                    fp.payments_date AS payments_date,
                    fp.debit AS debit_total,
                    fp.credit AS credit_total,
                    fp.total AS total,
                    fp.dif AS dif,
                    fp.accumulated AS accumulated
                FROM
                    financial_paymentsummary fp
                WHERE
                    fp.user_id = %(user_id)s
                    AND fp.payments_date BETWEEN %(begin)s
                    AND %(end)s
                ORDER BY
                    fp.payments_date
            """
        else:
            query_payments = """
                SELECT
                    fp.payments_date AS payments_date,
                    fp.debit AS debit_total,
                    fp.credit AS credit_total,
                    fp.total AS total,
                    fp.dif AS dif,
                    fp.accumulated AS accumulated
                FROM
                    financial_paymentsummary fp
                WHERE
                    fp.user_id = %(user_id)s
                ORDER BY
                    fp.payments_date
            """

        filters = {"user_id": user.id}
        if date_from and date_to:
            filters.update({"begin": date_from, "end": date_to})

        with cursor_factory() as cursor:
            cursor.execute(query_payments, filters)
            payments = cursor.fetchall()

        payments_data = [
            {
                "label": data[0],
                "debit": float(data[1] or 0),
                "credit": float(data[2] or 0),
                "total": data[3],
                "difference": float(data[4] or 0),
                "accumulated": float(data[5] or 0),
            }
            for data in payments
        ]

        if date_from and date_to:
            query_fixed_debit = """
                SELECT
                    SUM(value) as fixed_debit_total
                FROM
                    financial_payment AS fixed_debit
                WHERE
                    user_id=%(user_id)s
                    AND type=1
                    AND status=0
                    AND active=true
                    AND fixed=true
                    AND "payment_date" BETWEEN %(begin)s AND %(end)s;
            """
        else:
            query_fixed_debit = """
                SELECT
                    SUM(value) as fixed_debit_total
                FROM
                    financial_payment AS fixed_debit
                WHERE
                    user_id=%(user_id)s
                    AND type=1
                    AND status=0
                    AND active=true
                    AND fixed=true;
            """

        with cursor_factory() as cursor:
            cursor.execute(query_fixed_debit, filters)
            fixed_debit = cursor.fetchone()

        if date_from and date_to:
            query_fixed_credit = """
                SELECT
                    SUM(value) as fixed_credit_total
                FROM
                    financial_payment AS fixed_credit
                WHERE
                    user_id=%(user_id)s
                    AND type=0
                    AND status=0
                    AND active=true
                    AND fixed=true
                    AND "payment_date" BETWEEN %(begin)s AND %(end)s;
            """
        else:
            query_fixed_credit = """
                SELECT
                    SUM(value) as fixed_credit_total
                FROM
                    financial_payment AS fixed_credit
                WHERE
                    user_id=%(user_id)s
                    AND type=0
                    AND status=0
                    AND active=true
                    AND fixed=true;
            """

        with cursor_factory() as cursor:
            cursor.execute(query_fixed_credit, filters)
            fixed_credit = cursor.fetchone()

        return {
            "payments": payments_data,
            "fixed_debit": float(fixed_debit[0] or 0),
            "fixed_credit": float(fixed_credit[0] or 0),
        }
