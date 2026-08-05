USE instacart_dwh;

-- Every query must return zero. These contracts are also enforced by etl/quality.py.
SELECT 'duplicate_order_grain' AS check_name, COUNT(*) AS violations
FROM (
    SELECT order_id
    FROM Fact_Orders
    GROUP BY order_id
    HAVING COUNT(*) > 1
) duplicates
UNION ALL
SELECT 'duplicate_order_product_grain', COUNT(*)
FROM (
    SELECT order_id, product_id
    FROM Fact_Order_Details
    GROUP BY order_id, product_id
    HAVING COUNT(*) > 1
) duplicates
UNION ALL
SELECT 'unresolved_detail_time', COUNT(*)
FROM Fact_Order_Details
WHERE time_id IS NULL
UNION ALL
SELECT 'detail_time_mismatch', COUNT(*)
FROM Fact_Order_Details details
JOIN Fact_Orders orders ON details.order_id = orders.order_id
WHERE details.time_id <> orders.time_id
UNION ALL
SELECT 'orphan_detail_order', COUNT(*)
FROM Fact_Order_Details details
LEFT JOIN Fact_Orders orders ON details.order_id = orders.order_id
WHERE orders.order_id IS NULL
UNION ALL
SELECT 'orphan_detail_product', COUNT(*)
FROM Fact_Order_Details details
LEFT JOIN Dim_Product products ON details.product_id = products.product_id
WHERE products.product_id IS NULL
UNION ALL
SELECT 'invalid_first_order_interval', COUNT(*)
FROM Fact_Orders
WHERE order_number = 1 AND days_since_prior_order IS NOT NULL
UNION ALL
SELECT 'invalid_repeat_order_interval', COUNT(*)
FROM Fact_Orders
WHERE order_number > 1 AND days_since_prior_order IS NULL;
