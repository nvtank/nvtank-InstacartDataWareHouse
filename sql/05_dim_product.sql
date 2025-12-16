
USE instacart_dwh;

CREATE TABLE Dim_Product (
    product_id INT PRIMARY KEY COMMENT 'Business key from source',
    product_name VARCHAR(255) NOT NULL,
    aisle_id INT NOT NULL,
    department_id INT NOT NULL,
    product_category VARCHAR(50) DEFAULT 'General',
    
    CONSTRAINT fk_product_aisle 
        FOREIGN KEY (aisle_id) REFERENCES Dim_Aisle(aisle_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_product_dept 
        FOREIGN KEY (department_id) REFERENCES Dim_Department(department_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    
    INDEX idx_aisle (aisle_id),
    INDEX idx_department (department_id),
    INDEX idx_product_name (product_name(50))
) ENGINE=InnoDB COMMENT='Product dimension (49,688 records)';

SELECT 'Dim_Product created!' as Status;
