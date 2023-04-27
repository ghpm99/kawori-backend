WITH payments AS (
    SELECT
        COUNT(id) AS payment_total,
        payment.payment_date
    FROM
        financial_payment AS payment
    WHERE
        1 = 1
        AND active = TRUE
        AND user_id = 1
    GROUP BY
        payment.payment_date
    ORDER BY
        payment.payment_date
),
fixed_debit_open AS (
    SELECT
        SUM(value) as fixed_debit_total,
        fixed_debit.payment_date
    FROM
        financial_payment AS fixed_debit
    WHERE
        1 = 1
        AND user_id = 1
        AND type = 1
        AND status = 0
        AND active = true
        AND fixed = true
    GROUP BY
        fixed_debit.payment_date
    ORDER BY
        fixed_debit.payment_date
),
fixed_credit_open AS (
    SELECT
        SUM(value) as fixed_credit_total,
        fixed_credit.payment_date
    FROM
        financial_payment AS fixed_credit
    WHERE
        1 = 1
        AND user_id = 1
        AND type = 0
        AND status = 0
        AND active = true
        AND fixed = true
    GROUP BY
        fixed_credit.payment_date
    ORDER BY
        fixed_credit.payment_date
),
debit_open AS (
    SELECT
        SUM(value) AS debit_total,
        debit.payment_date
    FROM
        financial_payment AS debit
    WHERE
        1 = 1
        AND TYPE = 1
        AND status = 0
        AND active = TRUE
        AND fixed = FALSE
        AND user_id = 1
    GROUP BY
        debit.payment_date
    ORDER BY
        debit.payment_date
),
credit_open AS (
    SELECT
        SUM(value) AS credit_total,
        credit.payment_date
    FROM
        financial_payment AS credit
    WHERE
        1 = 1
        AND TYPE = 0
        AND status = 0
        AND active = TRUE
        AND fixed = FALSE
        AND user_id = 1
    GROUP BY
        credit.payment_date
    ORDER BY
        credit.payment_date
),
fixed_debit AS (
    SELECT
        SUM(value) AS fixed_debit_total,
        fixed_debit.payment_date
    FROM
        financial_payment AS fixed_debit
    WHERE
        1 = 1
        AND TYPE = 1
        AND status = 0
        AND active = TRUE
        AND fixed = TRUE
        AND user_id = 1
    GROUP BY
        fixed_debit.payment_date
    ORDER BY
        fixed_debit.payment_date
),
fixed_credit AS (
    SELECT
        SUM(value) AS fixed_credit_total,
        fixed_credit.payment_date
    FROM
        financial_payment AS fixed_credit
    WHERE
        1 = 1
        AND TYPE = 0
        AND status = 0
        AND active = TRUE
        AND fixed = TRUE
        AND user_id = 1
    GROUP BY
        fixed_credit.payment_date
    ORDER BY
        fixed_credit.payment_date
),
debit_closed AS (
    SELECT
        SUM(value) as debit_total,
        debit.payment_date
    FROM
        financial_payment AS debit
    WHERE
        1 = 1
        AND type = 1
        AND status = 1
        AND active = true
        AND user_id = 1
    GROUP BY
        debit.payment_date
    ORDER BY
        debit.payment_date
),
credit_closed AS (
    SELECT
        SUM(value) as credit_total,
        credit.payment_date
    FROM
        financial_payment AS credit
    WHERE
        1 = 1
        AND type = 0
        AND status = 1
        AND active = true
        AND user_id = 1
    GROUP BY
        credit.payment_date
    ORDER BY
        credit.payment_date
)
SELECT
    payment_total AS total,
    date_part('month', payment.payment_date) AS payment_month,
    date_part('year', payment.payment_date) AS payment_year,
    debit_closed.debit_total AS debit_closed_total,
    credit_closed.credit_total AS credit_closed_total,
    debit_open.debit_total AS debit_open_total,
    credit_open.credit_total AS credit_open_total,
    fixed_debit.fixed_debit_total AS fixed_debit_open,
    fixed_credit.fixed_credit_total AS fixed_credit_open
FROM
    financial_payment AS payment
    LEFT JOIN payments ON payments.payment_date = payment.payment_date
    LEFT JOIN debit_open ON debit_open.payment_date = payment.payment_date
    LEFT JOIN credit_open ON credit_open.payment_date = payment.payment_date
    LEFT JOIN fixed_debit ON fixed_debit.payment_date = payment.payment_date
    LEFT JOIN fixed_credit ON fixed_credit.payment_date = payment.payment_date
    LEFT JOIN debit_closed ON debit_closed.payment_date = payment.payment_date
    LEFT JOIN credit_closed ON credit_closed.payment_date = payment.payment_date
WHERE
    1 = 1
    AND active = TRUE
    AND user_id = 1
GROUP BY
    total,
    date_part('year', payment.payment_date),
    date_part('month', payment.payment_date),
    debit_open_total,
    credit_open.credit_total,
    fixed_debit_total,
    fixed_credit_total,
    debit_closed_total,
    credit_closed_total
ORDER BY
    payment_year,
    payment_month;