
USE instacart_dwh;

CREATE TABLE Dim_Aisle (
    aisle_id INT PRIMARY KEY COMMENT 'Business key from source',
    aisle_name VARCHAR(100) NOT NULL,
    aisle_type VARCHAR(30) NOT NULL DEFAULT 'General'
        COMMENT 'Fresh, Frozen, Dry Goods, Beverage, etc.',
    
    UNIQUE KEY uk_aisle_name (aisle_name),
    INDEX idx_aisle_type (aisle_type)
) ENGINE=InnoDB COMMENT='Aisle dimension (134 records)';

SELECT 'Dim_Aisle created!' as Status;
