
USE instacart_dwh;

-- ============================================
-- 1. Fact_Orders Partitions (LIST by dow)
-- ============================================
SELECT 
    '=== Fact_Orders Partitions ===' as Info;

SELECT 
    PARTITION_NAME as Partition,
    PARTITION_EXPRESSION as 'Partitioned By',
    PARTITION_DESCRIPTION as 'Values',
    TABLE_ROWS as 'Est. Rows',
    ROUND(DATA_LENGTH/1024/1024, 2) as 'Data (MB)',
    ROUND(INDEX_LENGTH/1024/1024, 2) as 'Index (MB)',
    ROUND((DATA_LENGTH + INDEX_LENGTH)/1024/1024, 2) as 'Total (MB)'
FROM INFORMATION_SCHEMA.PARTITIONS
WHERE TABLE_SCHEMA = 'instacart_dwh'
  AND TABLE_NAME = 'Fact_Orders'
ORDER BY PARTITION_ORDINAL_POSITION;

-- ============================================
-- 2. Fact_Order_Details Partitions (RANGE by order_id)
-- ============================================
SELECT 
    '=== Fact_Order_Details Partitions ===' as Info;

SELECT 
    PARTITION_NAME as Partition,
    PARTITION_EXPRESSION as 'Partitioned By',
    PARTITION_DESCRIPTION as 'Range',
    TABLE_ROWS as 'Est. Rows',
    ROUND(DATA_LENGTH/1024/1024, 2) as 'Data (MB)',
    ROUND(INDEX_LENGTH/1024/1024, 2) as 'Index (MB)',
    ROUND((DATA_LENGTH + INDEX_LENGTH)/1024/1024, 2) as 'Total (MB)'
FROM INFORMATION_SCHEMA.PARTITIONS
WHERE TABLE_SCHEMA = 'instacart_dwh'
  AND TABLE_NAME = 'Fact_Order_Details'
ORDER BY PARTITION_ORDINAL_POSITION;

-- ============================================
-- 3. Test Partition Pruning
-- ============================================
SELECT 
    '=== Testing Partition Pruning ===' as Info;

-- Test 1: Query single partition (Sunday orders)
EXPLAIN PARTITIONS
SELECT COUNT(*), AVG(total_items)
FROM Fact_Orders
WHERE order_dow = 0;
-- Expected: partitions: p_sunday

-- Test 2: Query weekend partitions
EXPLAIN PARTITIONS
SELECT order_dow, COUNT(*) as total_orders
FROM Fact_Orders
WHERE order_dow IN (0, 6)
GROUP BY order_dow;
-- Expected: partitions: p_sunday,p_saturday

-- Test 3: Query specific order_id range
EXPLAIN PARTITIONS
SELECT COUNT(*)
FROM Fact_Order_Details
WHERE order_id BETWEEN 500000 AND 1500000;
-- Expected: partitions: p1,p2

-- ============================================
-- 4. Storage Summary
-- ============================================
SELECT 
    '=== Total Storage Usage ===' as Info;

SELECT 
    TABLE_NAME,
    TABLE_ROWS as 'Est. Rows',
    ROUND(DATA_LENGTH/1024/1024, 2) as 'Data (MB)',
    ROUND(INDEX_LENGTH/1024/1024, 2) as 'Index (MB)',
    ROUND((DATA_LENGTH + INDEX_LENGTH)/1024/1024, 2) as 'Total (MB)',
    ENGINE,
    CREATE_OPTIONS
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'instacart_dwh'
ORDER BY (DATA_LENGTH + INDEX_LENGTH) DESC;
