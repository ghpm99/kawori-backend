CREATE MATERIALIZED VIEW public.financial_paymentsummary TABLESPACE pg_default AS WITH payments AS (
    SELECT
        date_trunc('month', payments.payment_date) :: date AS payments_date,
        COUNT(payments.id) as payment_total,
        payments.user_id as user_id
    FROM
        financial_payment AS payments
    WHERE
        1 = 1
        AND active = true
    GROUP BY
        payments_date,
        user_id
    ORDER BY
        payments_date
),
payments_closed AS (
    SELECT
        SUM(
            case
                when fp.type = 1 then value
                else 0
            end
        ) as debit_total,
        SUM(
            case
                when fp.type = 0 then value
                else 0
            end
        ) as credit_total,
        fp.user_id as user_id,
        date_trunc('month', fp.payment_date) :: date AS payments_date
    FROM
        financial_payment AS fp
    WHERE
        1 = 1
        AND active = true
        AND payment_date < date_trunc('month', now()) :: date
    GROUP BY
        payments_date,
        user_id
    ORDER BY
        payments_date
),
payments_current AS (
    SELECT
        SUM(
            case
                when fp.type = 1 then value
                else 0
            end
        ) as debit_total,
        SUM(
            case
                when fp.type = 0 then value
                else 0
            end
        ) as credit_total,
        fp.user_id as user_id,
        date_trunc('month', fp.payment_date) :: date AS payments_date
    FROM
        financial_payment AS fp
    WHERE
        1 = 1
        AND active = true
        AND payment_date BETWEEN date_trunc('month', now()) :: date
        AND NOW() :: date
    GROUP BY
        payments_date,
        user_id
    ORDER BY
        payments_date
),
payments_open AS (
    WITH fixed_debit_total AS (
        SELECT
            SUM(value) as total,
            fp.user_id as user_id
        FROM
            financial_payment AS fp
        WHERE
            1 = 1
            AND type = 1
            AND status = 0
            AND active = true
            AND fixed = true
        GROUP BY
            user_id
    ),
    fixed_credit_total AS (
        SELECT
            SUM(value) as total,
            fp.user_id as user_id
        FROM
            financial_payment AS fp
        WHERE
            1 = 1
            AND type = 0
            AND status = 0
            AND active = true
            AND fixed = true
        GROUP BY
            user_id
    ),
    open_payments AS (
        SELECT
            SUM(
                case
                    when fp.type = 1 then value
                    else 0
                end
            ) as debit_total,
            SUM(
                case
                    when fp.type = 0 then value
                    else 0
                end
            ) as credit_total,
            fp.user_id as user_id,
            date_trunc('month', fp.payment_date) :: date AS payments_date
        FROM
            financial_payment AS fp
        WHERE
            1 = 1
            AND active = TRUE
            AND fixed = FALSE
            AND payment_date > NOW() :: date
        GROUP BY
            payments_date,
            user_id
        ORDER BY
            payments_date
    )
    SELECT
        op.debit_total + COALESCE(fixed_debit_total.total, 0) as debit_total,
        op.credit_total + COALESCE(fixed_credit_total.total, 0) as credit_total,
        op.payments_date,
        op.user_id
    FROM
        open_payments as op
        LEFT JOIN fixed_debit_total on op.user_id = fixed_debit_total.user_id
        LEFT JOIN fixed_credit_total on op.user_id = fixed_credit_total.user_id
)
SELECT
    payments.payments_date AS payments_date,
    payments.user_id as user_id,
    payments.payment_total AS total,
    COALESCE(
        payments_closed.debit_total,
        payments_current.debit_total,
        payments_open.debit_total,
        0
    ) as debit,
    COALESCE(
        payments_closed.credit_total,
        payments_current.credit_total,
        payments_open.credit_total,
        0
    ) as credit
FROM
    payments AS payments
    LEFT JOIN payments_closed ON payments.payments_date = payments_closed.payments_date
    AND payments.user_id = payments_closed.user_id
    LEFT JOIN payments_current ON payments.payments_date = payments_current.payments_date
    AND payments.user_id = payments_current.user_id
    LEFT JOIN payments_open ON payments.payments_date = payments_open.payments_date
    AND payments.user_id = payments_open.user_id
GROUP BY
    payments.payments_date,
    payments.user_id,
    total,
    debit,
    credit
ORDER BY
    payments_date WITH DATA;