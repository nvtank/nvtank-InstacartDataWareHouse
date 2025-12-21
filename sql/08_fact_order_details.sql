-- ============================================
-- Fact_Order_Details: Order Line Items Fact
-- ============================================
-- Source: order_products__prior.csv + order_products__train.csv
-- Total: 32,434,489 + 1,384,617 = 33,819,106 records
-- Partitioning: RANGE by order_id (500K per partition)
-- Granularity: 1 row = 1 product in 1 order
-- ============================================

USE instacart_dwh;

CREATE TABLE Fact_Order_Details (
    detail_id BIGINT AUTO_INCREMENT COMMENT 'Surrogate key',
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    time_id INT NOT NULL,
    add_to_cart_order SMALLINT NOT NULL 
        COMMENT 'Sequence in cart (1-N), max 32767',
    reordered BOOLEAN NOT NULL DEFAULT 0 
        COMMENT '1 if previously ordered by this user',
    quantity INT NOT NULL DEFAULT 1 
        COMMENT 'Always 1 in source data',
    
    -- Composite PK includes order_id for partition compatibility
    PRIMARY KEY (detail_id, order_id),
    
    -- Note: Foreign keys not supported on partitioned tables in MariaDB
    -- Referential integrity enforced in ETL layer
    
    INDEX idx_order (order_id),
    INDEX idx_product (product_id),
    INDEX idx_time (time_id),
    INDEX idx_reordered (reordered)
) ENGINE=InnoDB
  COMMENT='Order line items fact table (33M+ records)'
  PARTITION BY RANGE (order_id) (
    PARTITION p0 VALUES LESS THAN (500000) 
        COMMENT 'Orders 1-499,999',
    PARTITION p1 VALUES LESS THAN (1000000) 
        COMMENT 'Orders 500K-999,999',
    PARTITION p2 VALUES LESS THAN (1500000) 
        COMMENT 'Orders 1M-1,499,999',
    PARTITION p3 VALUES LESS THAN (2000000) 
        COMMENT 'Orders 1.5M-1,999,999',
    PARTITION p4 VALUES LESS THAN (2500000) 
        COMMENT 'Orders 2M-2,499,999',
    PARTITION p5 VALUES LESS THAN (3000000) 
        COMMENT 'Orders 2.5M-2,999,999',
    PARTITION p6 VALUES LESS THAN (3500000) 
        COMMENT 'Orders 3M-3,499,999',
    PARTITION p_max VALUES LESS THAN MAXVALUE 
        COMMENT 'Orders 3.5M+'
  );

SELECT 'Fact_Order_Details created with 8 RANGE partitions!' as Status;
