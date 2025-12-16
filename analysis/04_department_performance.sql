
USE instacart_dwh;

SELECT 
    d.department_id,
    d.department_name,
    d.dept_category,
    COUNT(*) as total_items_sold,
    SUM(fod.reordered) as reordered_items,
    ROUND(AVG(fod.reordered) * 100, 2) as reorder_rate_pct
FROM Fact_Order_Details fod
JOIN Dim_Product p ON fod.product_id = p.product_id
JOIN Dim_Department d ON p.department_id = d.department_id
GROUP BY d.department_id, d.department_name, d.dept_category
ORDER BY total_items_sold DESC;
