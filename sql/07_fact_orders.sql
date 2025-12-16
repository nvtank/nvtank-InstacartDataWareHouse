
USE instacart_dwh;

CREATE TABLE Fact_Orders (
    order_id INT COMMENT 'Business key from source',
    user_id INT NOT NULL,
    time_id INT NOT NULL,
    order_number INT NOT NULL COMMENT 'Order sequence for this user',
    days_since_prior_order FLOAT DEFAULT NULL 
        COMMENT 'Days since previous order (NULL for first order)',
    total_items INT NOT NULL DEFAULT 0 
        COMMENT 'Total products in this order (updated later)',
    reorder_ratio DECIMAL(5,4) DEFAULT 0.0000 
        COMMENT 'Ratio of reordered items (0-1, updated later)',
    order_dow TINYINT NOT NULL 
        COMMENT 'Denormalized for partitioning',
    
    -- Primary key must include partition key (order_dow)
    PRIMARY KEY (order_id, order_dow),
    
    -- Note: Foreign keys not supported on partitioned tables in MariaDB
    -- Referential integrity enforced in ETL layer
    
    INDEX idx_user (user_id),
    INDEX idx_time (time_id),
    INDEX idx_order_number (order_number),
    INDEX idx_days_since_prior (days_since_prior_order)
) ENGINE=InnoDB
  COMMENT='Order summary fact table (3.4M records)'
  PARTITION BY LIST (order_dow) (
    PARTITION p_sunday VALUES IN (0) COMMENT 'Sunday orders',
    PARTITION p_monday VALUES IN (1) COMMENT 'Monday orders',
    PARTITION p_tuesday VALUES IN (2) COMMENT 'Tuesday orders',
    PARTITION p_wednesday VALUES IN (3) COMMENT 'Wednesday orders',
    PARTITION p_thursday VALUES IN (4) COMMENT 'Thursday orders',
    PARTITION p_friday VALUES IN (5) COMMENT 'Friday orders',
    PARTITION p_saturday VALUES IN (6) COMMENT 'Saturday orders'
  );

SELECT 'Fact_Orders created with 7 partitions (by day of week)!' as Status;
