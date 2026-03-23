from payment.models import Payment


class ReportAmountInvoiceByTagUseCase:
    def execute(self, user, date_from, date_to, cursor_factory):
        query_params = {"user_id": user.id, "payment_type": Payment.TYPE_DEBIT}
        if date_from and date_to:
            query_params.update({"begin": date_from, "end": date_to})
            amount_invoice = """
                SELECT
                    ft.id,
                    ft."name",
                    COALESCE(ft.color, '#000'),
                    sum(fp.value)
                FROM
                    financial_tag ft
                INNER JOIN financial_invoice_tags fit ON
                    ft.id = fit.tag_id
                INNER JOIN financial_invoice fi ON
                    fit.invoice_id = fi.id
                INNER JOIN financial_payment fp ON
                    fp.invoice_id = fi.id
                WHERE
                    ft.user_id=%(user_id)s
                    AND fp.type=%(payment_type)s
                    AND fp."payment_date" BETWEEN %(begin)s AND %(end)s
                    AND fi.active=true
                    AND fp.active=true
                GROUP BY
                    ft.id
                ORDER BY
                    sum(fp.value) DESC;
            """
        else:
            amount_invoice = """
                SELECT
                    ft.id,
                    ft."name",
                    COALESCE(ft.color, '#000'),
                    sum(fp.value)
                FROM
                    financial_tag ft
                INNER JOIN financial_invoice_tags fit ON
                    ft.id = fit.tag_id
                INNER JOIN financial_invoice fi ON
                    fit.invoice_id = fi.id
                INNER JOIN financial_payment fp ON
                    fp.invoice_id = fi.id
                WHERE
                    ft.user_id=%(user_id)s
                    AND fp.type=%(payment_type)s
                    AND fi.active=true
                    AND fp.active=true
                GROUP BY
                    ft.id
                ORDER BY
                    sum(fp.value) DESC;
            """
        with cursor_factory() as cursor:
            cursor.execute(amount_invoice, query_params)
            amount_invoice_rows = cursor.fetchall()

        return [
            {
                "id": data[0],
                "name": data[1],
                "color": data[2],
                "amount": float(data[3]),
            }
            for data in amount_invoice_rows
        ]
