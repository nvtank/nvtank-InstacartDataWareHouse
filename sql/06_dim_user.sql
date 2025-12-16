
USE instacart_dwh;

CREATE TABLE Dim_User (
    user_id INT PRIMARY KEY COMMENT 'Business key from source',
    user_segment VARCHAR(20) NOT NULL DEFAULT 'New' 
        COMMENT 'Customer segment: New, Regular, VIP',
    first_order_dow TINYINT DEFAULT NULL
        COMMENT 'Day of week of first order',
    avg_basket_size DECIMAL(6,2) DEFAULT 0.00 
        COMMENT 'Average items per order',
    total_orders INT DEFAULT 0
        COMMENT 'Total number of orders',
    total_products_purchased INT DEFAULT 0
        COMMENT 'Total products bought across all orders',
    avg_days_between_orders DECIMAL(6,2) DEFAULT NULL
        COMMENT 'Average days between consecutive orders',
    last_order_date_id INT DEFAULT NULL
        COMMENT 'Reference to last order time_id',
    
    INDEX idx_segment (user_segment),
    INDEX idx_total_orders (total_orders),
    INDEX idx_basket_size (avg_basket_size)
) ENGINE=InnoDB COMMENT='User dimension (~206K users)';

SELECT 'Dim_User created!' as Status;
