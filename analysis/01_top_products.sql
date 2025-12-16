USE instacart_dwh;

SELECT 
    p.product_id,
    p.product_name,
    COUNT(*) as total_quantity,
    SUM(fod.reordered) as times_reordered,
    ROUND(AVG(fod.reordered) * 100, 2) as reorder_rate_pct
FROM Fact_Order_Details fod
JOIN Dim_Product p ON fod.product_id = p.product_id
GROUP BY p.product_id, p.product_name
ORDER BY total_quantity DESC
LIMIT 20;
