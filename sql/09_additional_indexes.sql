USE instacart_dwh;

-- Pattern 1: "Top products by time period"
-- Query: SELECT product_id, COUNT(*) FROM Fact_Order_Details 
--        WHERE time_id IN (...) GROUP BY product_id
CREATE INDEX idx_detail_time_product 
    ON Fact_Order_Details(time_id, product_id)
    COMMENT 'Optimize product analysis by time';

-- Pattern 2: "Reorder analysis by product"
-- Query: SELECT product_id, SUM(reordered), COUNT(*) 
--        FROM Fact_Order_Details GROUP BY product_id
CREATE INDEX idx_detail_product_reorder 
    ON Fact_Order_Details(product_id, reordered)
    COMMENT 'Optimize reorder rate queries';

-- Pattern 3: "User order history timeline"
-- Query: SELECT * FROM Fact_Orders 
--        WHERE user_id = ? ORDER BY time_id
CREATE INDEX idx_order_user_time 
    ON Fact_Orders(user_id, time_id)
    COMMENT 'Optimize user purchase timeline';

-- Pattern 4: "Basket analysis covering index"
-- Query: SELECT order_id, product_id, reordered 
--        FROM Fact_Order_Details WHERE order_id = ?
-- Note: This is a covering index (all columns in SELECT/WHERE)
CREATE INDEX idx_detail_order_product_reorder 
    ON Fact_Order_Details(order_id, product_id, reordered)
    COMMENT 'Covering index for basket queries';

-- Pattern 5: "Product + Time + Reorder analysis"
-- Query: SELECT product_id, time_id, SUM(reordered) 
--        FROM Fact_Order_Details GROUP BY product_id, time_id
CREATE INDEX idx_detail_product_time_reorder 
    ON Fact_Order_Details(product_id, time_id, reordered)
    COMMENT 'Optimize product-time-reorder aggregation';

SELECT 'Additional indexes created successfully!' as Status;

-- Show all indexes
SELECT 
    TABLE_NAME,
    INDEX_NAME,
    COLUMN_NAME,
    SEQ_IN_INDEX,
    INDEX_TYPE
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = 'instacart_dwh'
  AND TABLE_NAME IN ('Fact_Orders', 'Fact_Order_Details')
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;
