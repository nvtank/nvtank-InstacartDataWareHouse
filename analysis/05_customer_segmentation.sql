-- ==========================================
-- Q5: Customer Segmentation Analysis
-- ==========================================
-- Business Question: Phân bố khách hàng theo segment?

USE instacart_dwh;

SELECT 
    u.user_segment,
    COUNT(DISTINCT u.user_id) as total_users,
    ROUND(COUNT(DISTINCT u.user_id) * 100.0 / SUM(COUNT(DISTINCT u.user_id)) OVER(), 2) as pct_users,
    ROUND(AVG(u.total_orders), 2) as avg_orders_per_user,
    ROUND(AVG(u.avg_basket_size), 2) as avg_basket_size,
    ROUND(AVG(u.avg_days_between_orders), 2) as avg_frequency_days,
    SUM(u.total_orders) as total_orders_by_segment,
    ROUND(SUM(u.total_orders) * 100.0 / SUM(SUM(u.total_orders)) OVER(), 2) as order_contribution_pct
FROM Dim_User u
GROUP BY u.user_segment
ORDER BY avg_orders_per_user DESC;
