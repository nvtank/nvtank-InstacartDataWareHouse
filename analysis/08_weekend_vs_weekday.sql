-- Business question: how does weekend shopping differ from weekday shopping?
USE instacart_dwh;

WITH period_metrics AS (
    SELECT
        CASE WHEN times.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END AS day_type,
        COUNT(*) AS total_orders,
        COUNT(DISTINCT orders.user_id) AS unique_users,
        ROUND(AVG(orders.total_items), 2) AS avg_basket_size,
        ROUND(AVG(orders.reorder_ratio) * 100, 2) AS avg_reorder_pct,
        ROUND(AVG(orders.days_since_prior_order), 2) AS avg_days_between
    FROM Fact_Orders orders
    JOIN Dim_Time times ON orders.time_id = times.time_id
    GROUP BY CASE WHEN times.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END
),
department_volume AS (
    SELECT
        CASE WHEN times.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END AS day_type,
        departments.department_name,
        COUNT(*) AS item_count,
        ROW_NUMBER() OVER (
            PARTITION BY CASE WHEN times.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END
            ORDER BY COUNT(*) DESC, departments.department_name
        ) AS volume_rank
    FROM Fact_Order_Details details
    JOIN Fact_Orders orders ON details.order_id = orders.order_id
    JOIN Dim_Time times ON orders.time_id = times.time_id
    JOIN Dim_Product products ON details.product_id = products.product_id
    JOIN Dim_Department departments
        ON products.department_id = departments.department_id
    GROUP BY
        CASE WHEN times.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END,
        departments.department_name
)
SELECT
    metrics.*,
    volume.department_name AS top_department
FROM period_metrics metrics
LEFT JOIN department_volume volume
    ON metrics.day_type = volume.day_type AND volume.volume_rank = 1
ORDER BY metrics.day_type;
