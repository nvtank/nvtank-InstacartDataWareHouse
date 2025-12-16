-- ==========================================
-- Q9: Product Reorder Patterns
-- ==========================================
-- Business Question: Sản phẩm nào có tỷ lệ mua lại cao nhất?

USE instacart_dwh;

SELECT 
    p.product_id,
    p.product_name,
    d.department_name,
    a.aisle_name,
    COUNT(*) as total_purchases,
    SUM(CASE WHEN fod.reordered = 0 THEN 1 ELSE 0 END) as first_time_purchases,
    SUM(CASE WHEN fod.reordered = 1 THEN 1 ELSE 0 END) as reorder_purchases,
    ROUND(AVG(fod.reordered) * 100, 2) as reorder_rate_pct
FROM Fact_Order_Details fod
JOIN Dim_Product p ON fod.product_id = p.product_id
JOIN Dim_Department d ON p.department_id = d.department_id
JOIN Dim_Aisle a ON p.aisle_id = a.aisle_id
GROUP BY p.product_id, p.product_name, d.department_name, a.aisle_name
HAVING COUNT(*) >= 5000
ORDER BY reorder_rate_pct DESC
LIMIT 30;
