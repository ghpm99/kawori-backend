WITH payments AS (
    SELECT
        date_part('year', payments.payment_date) as payments_year,
        date_part('month', payments.payment_date) as payments_month,
        COUNT(payments.id) as payment_total,
        SUM(value) as payment_value
    FROM
        financial_payment AS payments
    WHERE
        1 = 1
        AND active = true
        AND user_id = 1
    GROUP BY
        date_part('year', payments.payment_date),
        date_part('month', payments.payment_date)
    ORDER BY
        date_part('year', payments.payment_date),
        date_part('month', payments.payment_date)
),
all_debit_open AS (
    SELECT
        SUM(value) as fixed_debit_total
    FROM
        financial_payment AS fixed_debit
    WHERE
        1 = 1
        AND user_id = 1
        AND type = 1
        AND status = 0
        AND active = true
        AND fixed = true
),
debit_open AS (
    SELECT
        SUM(value) as debit_total,
        date_part('year', debit_open.payment_date) as debit_year,
        date_part('month', debit_open.payment_date) as debit_month
    FROM
        financial_payment AS debit_open
    WHERE
        1 = 1
        AND type = 1
        AND status = 0
        AND active = true
        AND fixed = false
        AND user_id = 1
    GROUP BY
        date_part('year', debit_open.payment_date),
        date_part('month', debit_open.payment_date)
    ORDER BY
        date_part('year', debit_open.payment_date),
        date_part('month', debit_open.payment_date)
),
all_credit_open AS (
    SELECT
        SUM(value) as fixed_credit_total
    FROM
        financial_payment AS fixed_credit
    WHERE
        1 = 1
        AND user_id = 1
        AND type = 0
        AND status = 0
        AND active = true
        AND fixed = true
),
credit_open AS (
    SELECT
        SUM(value) as credit_total,
        date_part('year', credit_open.payment_date) as credit_year,
        date_part('month', credit_open.payment_date) as credit_month
    FROM
        financial_payment AS credit_open
    WHERE
        1 = 1
        AND type = 0
        AND status = 0
        AND active = true
        AND fixed = false
        AND user_id = 1
    GROUP BY
        date_part('year', credit_open.payment_date),
        date_part('month', credit_open.payment_date)
    ORDER BY
        date_part('year', credit_open.payment_date),
        date_part('month', credit_open.payment_date)
),
fixed_debit_open AS (
    SELECT
        SUM(value) as fixed_debit_total,
        date_part('year', fixed_debit_open.payment_date) as fixed_debit_year,
        date_part('month', fixed_debit_open.payment_date) as fixed_debit_month
    FROM
        financial_payment AS fixed_debit_open
    WHERE
        1 = 1
        AND type = 1
        AND status = 0
        AND active = true
        AND fixed = true
        AND user_id = 1
    GROUP BY
        date_part('year', fixed_debit_open.payment_date),
        date_part('month', fixed_debit_open.payment_date)
    ORDER BY
        date_part('year', fixed_debit_open.payment_date),
        date_part('month', fixed_debit_open.payment_date)
),
fixed_credit_open AS (
    SELECT
        SUM(value) as fixed_credit_total,
        date_part('year', fixed_credit_open.payment_date) as fixed_credit_year,
        date_part('month', fixed_credit_open.payment_date) as fixed_credit_month
    FROM
        financial_payment AS fixed_credit_open
    WHERE
        1 = 1
        AND type = 0
        AND status = 0
        AND active = true
        AND fixed = true
        AND user_id = 1
    GROUP BY
        date_part('year', fixed_credit_open.payment_date),
        date_part('month', fixed_credit_open.payment_date)
    ORDER BY
        date_part('year', fixed_credit_open.payment_date),
        date_part('month', fixed_credit_open.payment_date)
),
debit_closed AS (
    SELECT
        SUM(value) as debit_total,
        date_part('year', debit_closed.payment_date) as debit_year,
        date_part('month', debit_closed.payment_date) as debit_month
    FROM
        financial_payment AS debit_closed
    WHERE
        1 = 1
        AND type = 1
        AND status = 1
        AND active = true
        AND user_id = 1
    GROUP BY
        date_part('year', debit_closed.payment_date),
        date_part('month', debit_closed.payment_date)
    ORDER BY
        date_part('year', debit_closed.payment_date),
        date_part('month', debit_closed.payment_date)
),
credit_closed AS (
    SELECT
        SUM(value) as credit_total,
        date_part('year', credit_closed.payment_date) as credit_year,
        date_part('month', credit_closed.payment_date) as credit_month
    FROM
        financial_payment AS credit_closed
    WHERE
        1 = 1
        AND type = 0
        AND status = 1
        AND active = true
        AND user_id = 1
    GROUP BY
        date_part('year', credit_closed.payment_date),
        date_part('month', credit_closed.payment_date)
    ORDER BY
        date_part('year', credit_closed.payment_date),
        date_part('month', credit_closed.payment_date)
)
SELECT
    date_part('month', payment.payment_date) AS payment_month,
    date_part('year', payment.payment_date) AS payment_year,
    payments.payment_total AS total,
    debit_closed.debit_total as debit_total_closed,
    credit_closed.credit_total as credit_total_closed,
    debit_open.debit_total + all_debit_open.fixed_debit_total as debit_total_open,
    credit_open.credit_total + all_credit_open.fixed_credit_total as credit_total_open,
    fixed_debit_open.fixed_debit_total as fixed_debit_open,
    fixed_credit_open.fixed_credit_total as fixed_credit_open
FROM
    financial_payment AS payment
    FROM all_debit_open
    FROM all_credit_open
    LEFT JOIN payments ON payments.payments_year = date_part('year', payment.payment_date)
    AND payments.payments_month = date_part('month', payment.payment_date)
    LEFT JOIN debit_open ON debit_open.debit_year = date_part('year', payment.payment_date)
    AND debit_open.debit_month = date_part('month', payment.payment_date)
    LEFT JOIN credit_open ON credit_open.credit_year = date_part('year', payment.payment_date)
    AND credit_open.credit_month = date_part('month', payment.payment_date)
    LEFT JOIN fixed_debit_open ON fixed_debit_open.fixed_debit_year = date_part('year', payment.payment_date)
    AND fixed_debit_open.fixed_debit_month = date_part('month', payment.payment_date)
    LEFT JOIN fixed_credit_open ON fixed_credit_open.fixed_credit_year = date_part('year', payment.payment_date)
    AND fixed_credit_open.fixed_credit_month = date_part('month', payment.payment_date)
    LEFT JOIN debit_closed ON debit_closed.debit_year = date_part('year', payment.payment_date)
    AND debit_closed.debit_month = date_part('month', payment.payment_date)
    LEFT JOIN credit_closed ON credit_closed.credit_year = date_part('year', payment.payment_date)
    AND credit_closed.credit_month = date_part('month', payment.payment_date)
WHERE
    1 = 1
    AND active = true
    AND user_id = 1
GROUP BY
    date_part('year', payment.payment_date),
    date_part('month', payment.payment_date),
    payments.payment_total,
    debit_open.debit_total,
    credit_open.credit_total,
    fixed_debit_open.fixed_debit_total,
    fixed_credit_open.fixed_credit_total,
    debit_closed.debit_total,
    credit_closed.credit_total
ORDER BY
    payment_year,
    payment_month;