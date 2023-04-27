CREATE MATERIALIZED VIEW public.partners_partnersummary TABLESPACE pg_default AS WITH
accesses AS (
    SELECT
        partners_accesses.partner_id,
        COALESCE(
            partners_accesses.ecommerce_id,
            partners_accesses.platform_id + 1
        ) AS ecommerce,
        partners_accesses.created_at :: DATE AS date,
        COUNT(partners_accesses.id) AS count
    FROM
        partners_accesses
    WHERE
        partners_accesses.partner_id IS NOT NULL
    GROUP BY
        partners_accesses.partner_id,
        (partners_accesses.created_at :: DATE),
        ecommerce
),
leads AS (
    SELECT
        partners_lead.partner_id,
        COALESCE(
            partners_lead.ecommerce_id,
            partners_lead.platform_id + 1
        ) AS ecommerce,
        partners_lead.created_at :: DATE AS date,
        COUNT(partners_lead.id) AS count
    FROM
        partners_lead
    GROUP BY
        partners_lead.partner_id,
        (partners_lead.created_at :: DATE),
        ecommerce
),
sales AS (
    SELECT
        partners_purchase.partner_id,
        COALESCE(
            partners_purchase.ecommerce_id,
            partners_purchase.platform_id + 1
        ) AS ecommerce,
        partners_purchase.created_at :: date AS date,
        COUNT(partners_purchase.id) AS count,
        SUM(partners_purchase.commission_value) AS commission,
        SUM(
            (
                (
                    COALESCE(
                        partners_purchase.price :: TEXT,
                        partners_purchase.extra #>>'{total_amount}')
                    ) :: TEXT
                ) :: DOUBLE PRECISION
            ) AS sum
            FROM
                partners_purchase
            GROUP BY
                partners_purchase.partner_id,
                (partners_purchase.created_at :: DATE),
                ecommerce
),
leads_accesses AS (
    SELECT
        COALESCE(accesses.partner_id, leads.partner_id) AS partner_id,
        COALESCE(accesses.ecommerce, leads.ecommerce) AS ecommerce_id,
        COALESCE(accesses.date, leads.date) AS date,
        leads.count AS leads_count,
        accesses.count AS accesses_count
    FROM
        accesses FULL
        JOIN leads ON leads.date = accesses.date
        AND leads.partner_id = accesses.partner_id
        AND leads.ecommerce = accesses.ecommerce
)
SELECT
    COALESCE(leads_accesses.partner_id, sales.partner_id) AS partner_id,
    COALESCE(leads_accesses.ecommerce_id, sales.ecommerce) AS ecommerce_id,
    COALESCE(leads_accesses.date, sales.date) AS date,
    CONCAT(
        '{
        "accesses": {
            "count": ',
        COALESCE(leads_accesses.accesses_count :: NUMERIC, 0),
        '},
        "leads": {
            "count": ',
        COALESCE(leads_accesses.leads_count :: NUMERIC, 0),
        '},
        "sales": {
            "count": ',
        COALESCE(sales.count :: NUMERIC, 0),
        ',
            "amount": ',
        COALESCE(sales.sum, 0.0 :: DOUBLE PRECISION),
        ',
            "commision": ',
        COALESCE(sales.commission, 0.0),
        '}
    }'
    ) :: JSON AS summary
FROM
    leads_accesses FULL
    JOIN sales ON sales.date = leads_accesses.date
    AND sales.partner_id = leads_accesses.partner_id
    AND sales.ecommerce = leads_accesses.ecommerce_id WITH DATA;