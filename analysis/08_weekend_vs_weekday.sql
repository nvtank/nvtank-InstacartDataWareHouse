-- ==========================================
-- Q8: Weekend vs Weekday Analysis
-- ==========================================
-- Business Question: Hành vi mua sắm cuối tuần khác gì ngày thường?

USE instacart_dwh;

SELECT 
    CASE 
        WHEN t.is_weekend = 1 THEN 'Weekend'
        ELSE 'Weekday'
    END as day_type,
    COUNT(DISTINCT fo.order_id) as total_orders,
    COUNT(DISTINCT fo.user_id) as unique_users,
    ROUND(AVG(fo.total_items), 2) as avg_basket_size,
    ROUND(AVG(fo.reorder_ratio) * 100, 2) as avg_reorder_pct,
    ROUND(AVG(fo.days_since_prior_order), 2) as avg_days_between,
    -- Top department by order count
    (SELECT d.department_name
     FROM Fact_Order_Details fod2
     JOIN Dim_Product p2 ON fod2.product_id = p2.product_id
     JOIN Dim_Department d ON p2.department_id = d.department_id
     JOIN Fact_Orders fo2 ON fod2.order_id = fo2.order_id
     JOIN Dim_Time t2 ON fo2.time_id = t2.time_id
     WHERE (t2.is_weekend = 1 AND day_type = 'Weekend') 
        OR (t2.is_weekend = 0 AND day_type = 'Weekday')
     GROUP BY d.department_id, d.department_name
     ORDER BY COUNT(*) DESC
     LIMIT 1
    ) as top_department
FROM Fact_Orders fo
JOIN Dim_Time t ON fo.time_id = t.time_id
GROUP BY day_type
ORDER BY day_type;
