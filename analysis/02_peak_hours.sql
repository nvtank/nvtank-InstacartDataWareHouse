USE instacart_dwh;

SELECT 
    t.order_hour,
    t.hour_range,
    CASE WHEN t.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END as day_type,
    COUNT(DISTINCT fo.order_id) as total_orders,
    COUNT(DISTINCT fo.user_id) as unique_users,
    ROUND(AVG(fo.total_items), 2) as avg_basket_size,
    ROUND(AVG(fo.reorder_ratio) * 100, 2) as avg_reorder_pct
FROM Fact_Orders fo
JOIN Dim_Time t ON fo.time_id = t.time_id
GROUP BY t.order_hour, t.hour_range, day_type
ORDER BY total_orders DESC;
