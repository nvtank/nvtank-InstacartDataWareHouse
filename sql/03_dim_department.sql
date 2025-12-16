
USE instacart_dwh;

CREATE TABLE Dim_Department (
    department_id INT PRIMARY KEY COMMENT 'Business key from source',
    department_name VARCHAR(50) NOT NULL,
    dept_category VARCHAR(20) NOT NULL DEFAULT 'General' 
        COMMENT 'Food, Beverage, Personal Care, etc.',
    
    UNIQUE KEY uk_dept_name (department_name),
    INDEX idx_category (dept_category)
) ENGINE=InnoDB COMMENT='Department dimension (21 records)';

SELECT 'Dim_Department created!' as Status;
