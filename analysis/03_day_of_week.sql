-- ==========================================
-- Q3: Day of Week Analysis
-- ==========================================
-- Business Question: Ngày nào trong tuần có nhiều đơn nhất?

USE instacart_dwh;

SELECT 
    t.order_dow,
    t.dow_name,
    t.is_weekend,
    COUNT(DISTINCT fo.order_id) as total_orders,
    COUNT(DISTINCT fo.user_id) as unique_users,
    ROUND(AVG(fo.total_items), 2) as avg_basket_size,
    ROUND(AVG(fo.days_since_prior_order), 2) as avg_days_between_orders,
    ROUND(AVG(fo.reorder_ratio) * 100, 2) as avg_reorder_pct
FROM Fact_Orders fo
JOIN Dim_Time t ON fo.time_id = t.time_id
GROUP BY t.order_dow, t.dow_name, t.is_weekend
ORDER BY t.order_dow;
