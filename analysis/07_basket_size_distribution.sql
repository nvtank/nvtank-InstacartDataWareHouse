-- ==========================================
-- Q7: Basket Size Distribution Analysis
-- ==========================================
-- Business Question: Giỏ hàng trung bình có bao nhiêu sản phẩm?

USE instacart_dwh;

SELECT 
    CASE 
        WHEN fo.total_items BETWEEN 1 AND 5 THEN '1-5 items'
        WHEN fo.total_items BETWEEN 6 AND 10 THEN '6-10 items'
        WHEN fo.total_items BETWEEN 11 AND 20 THEN '11-20 items'
        WHEN fo.total_items BETWEEN 21 AND 30 THEN '21-30 items'
        ELSE '30+ items'
    END as basket_size_group,
    COUNT(DISTINCT fo.order_id) as total_orders,
    ROUND(COUNT(DISTINCT fo.order_id) * 100.0 / SUM(COUNT(DISTINCT fo.order_id)) OVER(), 2) as pct_of_orders,
    ROUND(AVG(fo.total_items), 2) as avg_items_in_group,
    ROUND(AVG(fo.reorder_ratio) * 100, 2) as avg_reorder_pct,
    ROUND(AVG(fo.days_since_prior_order), 2) as avg_days_between
FROM Fact_Orders fo
GROUP BY basket_size_group
ORDER BY 
    CASE basket_size_group
        WHEN '1-5 items' THEN 1
        WHEN '6-10 items' THEN 2
        WHEN '11-20 items' THEN 3
        WHEN '21-30 items' THEN 4
        ELSE 5
    END;
