CREATE MATERIALIZED VIEW public.financial_paymentsummary TABLESPACE pg_default AS WITH payments AS (
    SELECT
        date_trunc('month', payments.payment_date) :: date AS payments_date,
        COUNT(payments.id) AS payment_total,
        payments.user_id AS user_id
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
        ) AS debit_total,
        SUM(
            case
                when fp.type = 0 then value
                else 0
            end
        ) AS credit_total,
        fp.user_id AS user_id,
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
        ) AS debit_total,
        SUM(
            case
                when fp.type = 0 then value
                else 0
            end
        ) AS credit_total,
        fp.user_id AS user_id,
        date_trunc('month', fp.payment_date) :: date AS payments_date
    FROM
        financial_payment AS fp
    WHERE
        1 = 1
        AND active = true
        AND payment_date BETWEEN date_trunc('month', now()) :: date
        AND (
            date_trunc('month', now()) + interval '1 month' - interval '1 day'
        ) :: date
    GROUP BY
        payments_date,
        user_id
    ORDER BY
        payments_date
),
payments_open AS (
    WITH fixed_debit_total AS (
        SELECT
            SUM(value) AS total,
            fp.user_id AS user_id
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
            SUM(value) AS total,
            fp.user_id AS user_id
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
            ) AS debit_total,
            SUM(
                case
                    when fp.type = 0 then value
                    else 0
                end
            ) AS credit_total,
            fp.user_id AS user_id,
            date_trunc('month', fp.payment_date) :: date AS payments_date
        FROM
            financial_payment AS fp
        WHERE
            1 = 1
            AND active = TRUE
            AND fixed = FALSE
            AND payment_date > (date_trunc('month', now()) + interval '1 month') :: date
        GROUP BY
            payments_date,
            user_id
        ORDER BY
            payments_date
    )
    SELECT
        op.debit_total + COALESCE(fixed_debit_total.total, 0) AS debit_total,
        op.credit_total + COALESCE(fixed_credit_total.total, 0) AS credit_total,
        op.payments_date,
        op.user_id
    FROM
        open_payments AS op
        LEFT JOIN fixed_debit_total on op.user_id = fixed_debit_total.user_id
        LEFT JOIN fixed_credit_total on op.user_id = fixed_credit_total.user_id
)
SELECT
    payments.payments_date AS payments_date,
    payments.user_id AS user_id,
    payments.payment_total AS total,
    COALESCE(
        payments_closed.debit_total,
        payments_current.debit_total,
        payments_open.debit_total,
        0
    ) AS debit,
    COALESCE(
        payments_closed.credit_total,
        payments_current.credit_total,
        payments_open.credit_total,
        0
    ) AS credit,
    SUM(
        COALESCE(
            payments_closed.credit_total,
            payments_current.credit_total,
            payments_open.credit_total,
            0
        ) - COALESCE(
            payments_closed.debit_total,
            payments_current.debit_total,
            payments_open.debit_total,
            0
        )
    ) AS dif,
    (
        SELECT
            SUM(
                COALESCE(
                    PC.credit_total,
                    PCR.credit_total,
                    PO.credit_total,
                    0
                ) - COALESCE(
                    PC.debit_total,
                    PCR.debit_total,
                    PO.debit_total,
                    0
                )
            )
        FROM
            payments AS p
            LEFT JOIN payments_closed AS PC ON p.payments_date = PC.payments_date
            AND p.user_id = PC.user_id
            LEFT JOIN payments_current AS PCR ON p.payments_date = PCR.payments_date
            AND p.user_id = PCR.user_id
            LEFT JOIN payments_open AS PO ON p.payments_date = PO.payments_date
            AND p.user_id = PO.user_id
        WHERE
            p.payments_date <= payments.payments_date
            AND p.user_id = payments.user_id
    ) AS accumulated
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