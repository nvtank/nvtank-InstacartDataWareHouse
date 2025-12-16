-- ==========================================
-- Q10: Partition Performance Test
-- ==========================================
-- Business Question: Hiệu năng của partitioning?

USE instacart_dwh;

-- Test 1: Query với partition pruning (chỉ scan 1 partition)
-- Expected: Nhanh hơn 7x so với non-partitioned table
EXPLAIN PARTITIONS
SELECT 
    COUNT(*) as sunday_orders,
    AVG(total_items) as avg_basket,
    AVG(reorder_ratio) as avg_reorder
FROM Fact_Orders
WHERE order_dow = 0;
-- Expected partitions: p_sunday only

-- Test 2: Query Sunday orders với chi tiết
SELECT 
    fo.order_dow,
    t.dow_name,
    COUNT(DISTINCT fo.order_id) as total_orders,
    AVG(fo.total_items) as avg_basket_size,
    AVG(fo.reorder_ratio) * 100 as avg_reorder_pct
FROM Fact_Orders fo
JOIN Dim_Time t ON fo.time_id = t.time_id
WHERE fo.order_dow = 0  -- Partition pruning: chỉ scan p_sunday
GROUP BY fo.order_dow, t.dow_name;

-- Test 3: Range partition pruning test
EXPLAIN PARTITIONS
SELECT 
    COUNT(*) as order_count,
    AVG(total_items) as avg_items
FROM Fact_Orders
WHERE order_id BETWEEN 1000000 AND 1500000;
-- Expected: Scan fewer partitions

-- Test 4: Performance comparison queries
-- Query A: With partition benefit
SELECT 
    order_dow,
    COUNT(*) as cnt
FROM Fact_Orders
WHERE order_dow IN (0, 6)  -- Weekend only (2 partitions)
GROUP BY order_dow;

-- Query B: All partitions
SELECT 
    order_dow,
    COUNT(*) as cnt
FROM Fact_Orders
GROUP BY order_dow
ORDER BY order_dow;
