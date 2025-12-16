USE instacart_dwh;

-- Overall metrics
SELECT 
    'Total Orders' as metric,
    FORMAT(COUNT(DISTINCT order_id), 0) as value,
    'Tổng số đơn hàng' as description
FROM Fact_Orders

UNION ALL

SELECT 
    'Total Users',
    FORMAT(COUNT(DISTINCT user_id), 0),
    'Tổng số khách hàng'
FROM Dim_User

UNION ALL

SELECT 
    'Total Products',
    FORMAT(COUNT(DISTINCT product_id), 0),
    'Tổng số sản phẩm'
FROM Dim_Product

UNION ALL

SELECT 
    'Total Items Sold',
    FORMAT(COUNT(*), 0),
    'Tổng số items đã bán'
FROM Fact_Order_Details

UNION ALL

SELECT 
    'Avg Basket Size',
    FORMAT(AVG(total_items), 2),
    'Số sản phẩm trung bình/đơn'
FROM Fact_Orders

UNION ALL

SELECT 
    'Avg Reorder Rate',
    CONCAT(FORMAT(AVG(reorder_ratio) * 100, 2), '%'),
    'Tỷ lệ mua lại trung bình'
FROM Fact_Orders

UNION ALL

SELECT 
    'Most Popular Day',
    (SELECT dow_name 
     FROM Fact_Orders fo 
     JOIN Dim_Time t ON fo.time_id = t.time_id 
     GROUP BY dow_name 
     ORDER BY COUNT(*) DESC 
     LIMIT 1
    ),
    'Ngày có nhiều đơn nhất'
FROM Fact_Orders
LIMIT 1

UNION ALL

SELECT 
    'Most Popular Hour',
    (SELECT CONCAT(order_hour, ':00') 
     FROM Fact_Orders fo 
     JOIN Dim_Time t ON fo.time_id = t.time_id 
     GROUP BY order_hour 
     ORDER BY COUNT(*) DESC 
     LIMIT 1
    ),
    'Giờ có nhiều đơn nhất'
FROM Fact_Orders
LIMIT 1

UNION ALL

SELECT 
    'Top Department',
    (SELECT department_name
     FROM Fact_Order_Details fod
     JOIN Dim_Product p ON fod.product_id = p.product_id
     JOIN Dim_Department d ON p.department_id = d.department_id
     GROUP BY d.department_id, d.department_name
     ORDER BY COUNT(*) DESC
     LIMIT 1
    ),
    'Ngành hàng bán chạy nhất'
FROM Fact_Order_Details
LIMIT 1

UNION ALL

SELECT 
    'Top Product',
    (SELECT product_name
     FROM Fact_Order_Details fod
     JOIN Dim_Product p ON fod.product_id = p.product_id
     GROUP BY p.product_id, p.product_name
     ORDER BY COUNT(*) DESC
     LIMIT 1
    ),
    'Sản phẩm bán chạy nhất'
FROM Fact_Order_Details
LIMIT 1;
