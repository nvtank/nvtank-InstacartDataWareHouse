
USE instacart_dwh;

-- ============================================
-- 1. Update Table Statistics
-- ============================================
SELECT 'Analyzing tables for query optimizer...' as Status;

ANALYZE TABLE Dim_Time;
ANALYZE TABLE Dim_Department;
ANALYZE TABLE Dim_Aisle;
ANALYZE TABLE Dim_Product;
ANALYZE TABLE Dim_User;

-- Analyze each partition separately for better statistics
ANALYZE TABLE Fact_Orders PARTITION (p_sunday);
ANALYZE TABLE Fact_Orders PARTITION (p_monday);
ANALYZE TABLE Fact_Orders PARTITION (p_tuesday);
ANALYZE TABLE Fact_Orders PARTITION (p_wednesday);
ANALYZE TABLE Fact_Orders PARTITION (p_thursday);
ANALYZE TABLE Fact_Orders PARTITION (p_friday);
ANALYZE TABLE Fact_Orders PARTITION (p_saturday);

ANALYZE TABLE Fact_Order_Details PARTITION (p0);
ANALYZE TABLE Fact_Order_Details PARTITION (p1);
ANALYZE TABLE Fact_Order_Details PARTITION (p2);
ANALYZE TABLE Fact_Order_Details PARTITION (p3);
ANALYZE TABLE Fact_Order_Details PARTITION (p4);
ANALYZE TABLE Fact_Order_Details PARTITION (p5);
ANALYZE TABLE Fact_Order_Details PARTITION (p6);
ANALYZE TABLE Fact_Order_Details PARTITION (p_max);

SELECT 'Table statistics updated!' as Status;

-- ============================================
-- 2. Optimize Tables (Defragment & Rebuild Indexes)
-- ============================================
SELECT 'Optimizing tables...' as Status;

OPTIMIZE TABLE Dim_Product;
OPTIMIZE TABLE Dim_User;
OPTIMIZE TABLE Fact_Orders;
OPTIMIZE TABLE Fact_Order_Details;

SELECT 'Tables optimized!' as Status;

-- ============================================
-- 3. Check Index Cardinality
-- ============================================
SELECT 
    TABLE_NAME,
    INDEX_NAME,
    COLUMN_NAME,
    CARDINALITY,
    SEQ_IN_INDEX
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = 'instacart_dwh'
  AND TABLE_NAME IN ('Fact_Orders', 'Fact_Order_Details')
  AND CARDINALITY IS NOT NULL
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;

-- ============================================
-- 4. Check for Fragmentation
-- ============================================
SELECT 
    TABLE_NAME,
    ROUND(DATA_LENGTH/1024/1024, 2) as 'Data (MB)',
    ROUND(DATA_FREE/1024/1024, 2) as 'Free Space (MB)',
    ROUND(DATA_FREE / (DATA_LENGTH + INDEX_LENGTH + DATA_FREE) * 100, 2) as 'Fragmentation %'
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'instacart_dwh'
  AND DATA_FREE > 0
ORDER BY DATA_FREE DESC;

SELECT 'Maintenance completed!' as Status;
