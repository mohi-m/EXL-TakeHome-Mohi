-- business_questions.sql
-- Five analytics queries for OmniRetail business questions.
-- Each block is prefixed with a numbered label (-- Q{n}: question text) so
-- src/reporting.py can pair them with business_questions.csv by position.

-- Q1: What is completed revenue by month?
SELECT
    SUBSTR(fo.order_date, 1, 7)          AS month,
    ROUND(SUM(fo.gross_order_amount), 2) AS completed_revenue
FROM fact_order fo
WHERE LOWER(fo.order_status) = 'completed'
  AND fo.order_date IS NOT NULL
GROUP BY SUBSTR(fo.order_date, 1, 7)
ORDER BY month;

-- Q2: Who are the top 10 customers by completed order value?
SELECT
    dc.customer_key,
    dc.full_name,
    ROUND(SUM(fo.gross_order_amount), 2) AS total_completed_value
FROM fact_order fo
JOIN dim_customer dc ON fo.customer_key = dc.customer_key
WHERE LOWER(fo.order_status) = 'completed'
GROUP BY dc.customer_key, dc.full_name
ORDER BY total_completed_value DESC
LIMIT 10;

-- Q3: Which orders have payment mismatches, missing payments, invalid customer references, invalid product references, or suspicious quantities?
SELECT
    fo.order_key,
    fo.order_status,
    fo.gross_order_amount,
    CASE WHEN fo.customer_key IS NULL
         THEN 'Yes' ELSE 'No' END                                               AS invalid_customer,
    CASE WHEN fo.product_key IS NULL
         THEN 'Yes' ELSE 'No' END                                               AS invalid_product,
    CASE WHEN fo.quantity IS NOT NULL AND fo.quantity <= 0
              AND LOWER(fo.order_status) = 'completed'
         THEN 'Yes' ELSE 'No' END                                               AS suspicious_qty,
    CASE WHEN fo.order_amount_variance IS NOT NULL
              AND ABS(fo.order_amount_variance) > 0.01
         THEN 'Yes' ELSE 'No' END                                               AS total_mismatch,
    CASE WHEN fp.payment_key IS NULL
              AND LOWER(fo.order_status) = 'completed'
         THEN 'Yes' ELSE 'No' END                                               AS missing_payment,
    CASE WHEN fp.payment_key IS NOT NULL
              AND LOWER(fp.payment_status) = 'settled'
              AND ABS(fp.payment_amount - fo.gross_order_amount) > 0.01
         THEN 'Yes' ELSE 'No' END                                               AS payment_mismatch
FROM fact_order fo
LEFT JOIN fact_payment fp ON fo.order_key = fp.order_key
WHERE fo.customer_key IS NULL
   OR fo.product_key IS NULL
   OR (fo.quantity IS NOT NULL AND fo.quantity <= 0 AND LOWER(fo.order_status) = 'completed')
   OR (fo.order_amount_variance IS NOT NULL AND ABS(fo.order_amount_variance) > 0.01)
   OR (fp.payment_key IS NULL AND LOWER(fo.order_status) = 'completed')
   OR (    fp.payment_key IS NOT NULL
       AND LOWER(fp.payment_status) = 'settled'
       AND ABS(fp.payment_amount - fo.gross_order_amount) > 0.01)
ORDER BY fo.order_key;

-- Q4: Which states have the highest completed revenue?
SELECT
    fo.shipping_state,
    ROUND(SUM(fo.gross_order_amount), 2) AS completed_revenue
FROM fact_order fo
WHERE LOWER(fo.order_status) = 'completed'
  AND fo.shipping_state IS NOT NULL
GROUP BY fo.shipping_state
ORDER BY completed_revenue DESC;

-- Q5: Is there any visible relationship between negative support tickets and order/payment exceptions?
-- Joins tickets → fact_order → fact_payment directly; no customer-table exceptions used.
SELECT
    fci.ticket_id,
    fci.customer_key,
    COALESCE(dc.full_name, 'Unknown')                              AS customer_name,
    fci.issue_category,
    COUNT(DISTINCT fo.order_key)                                   AS orders_placed,
    SUM(CASE WHEN fo.order_amount_variance IS NOT NULL
                  AND ABS(fo.order_amount_variance) > 0.01
             THEN 1 ELSE 0 END)                                    AS orders_with_total_mismatch,
    SUM(CASE WHEN LOWER(fo.order_status) = 'completed'
                  AND fp.payment_key IS NULL
             THEN 1 ELSE 0 END)                                    AS orders_missing_payment,
    SUM(CASE WHEN fp.payment_key IS NOT NULL
                  AND LOWER(fp.payment_status) = 'settled'
                  AND ABS(fp.payment_amount - fo.gross_order_amount) > 0.01
             THEN 1 ELSE 0 END)                                    AS orders_with_payment_mismatch,
    SUM(CASE WHEN fo.quantity IS NOT NULL AND fo.quantity <= 0
                  AND LOWER(fo.order_status) = 'completed'
             THEN 1 ELSE 0 END)                                    AS orders_with_suspicious_qty
FROM fact_customer_issue fci
LEFT JOIN dim_customer dc ON fci.customer_key = dc.customer_key
LEFT JOIN fact_order fo   ON fo.customer_key  = fci.customer_key
LEFT JOIN fact_payment fp ON fp.order_key     = fo.order_key
WHERE LOWER(fci.sentiment) = 'negative'
GROUP BY fci.ticket_id, fci.customer_key, dc.full_name, fci.issue_category
ORDER BY (orders_with_total_mismatch + orders_missing_payment + orders_with_payment_mismatch + orders_with_suspicious_qty) DESC,
         fci.ticket_id;
