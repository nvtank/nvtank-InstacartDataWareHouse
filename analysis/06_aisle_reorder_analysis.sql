-- ==========================================
-- Q6: Aisle Reorder Rate Analysis (OPTIMIZED - SIMPLE VERSION)
-- ==========================================
-- Business Question: Aisle nào có tỷ lệ mua lại cao nhất?
-- Tối ưu: Chỉ JOIN 1 table (Dim_Product) để tăng tốc

USE instacart_dwh;

SELECT 
    a.aisle_id,
    a.aisle_name,
    a.aisle_type,
    COUNT(*) as total_items,
    SUM(fod.reordered) as reordered_items,
    ROUND(AVG(fod.reordered) * 100, 2) as reorder_rate_pct
FROM Fact_Order_Details fod
JOIN Dim_Product p ON fod.product_id = p.product_id
JOIN Dim_Aisle a ON p.aisle_id = a.aisle_id
GROUP BY a.aisle_id, a.aisle_name, a.aisle_type
HAVING COUNT(*) >= 10000  -- Only aisles with significant volume
ORDER BY reorder_rate_pct DESC
LIMIT 20;
