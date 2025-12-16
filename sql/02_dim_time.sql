
USE instacart_dwh;

CREATE TABLE Dim_Time (
    time_id INT PRIMARY KEY COMMENT 'Surrogate key: dow*100 + hour',
    order_dow TINYINT NOT NULL COMMENT 'Day of week (0=Sunday, 6=Saturday)',
    dow_name VARCHAR(10) NOT NULL COMMENT 'Sunday, Monday, ...',
    order_hour TINYINT NOT NULL COMMENT 'Hour of day (0-23)',
    hour_range VARCHAR(20) NOT NULL COMMENT 'Time slot: 00-06, 06-12, 12-18, 18-24',
    is_weekend BOOLEAN NOT NULL COMMENT 'TRUE if Saturday/Sunday',
    
    INDEX idx_dow (order_dow),
    INDEX idx_hour (order_hour),
    INDEX idx_weekend (is_weekend)
) ENGINE=InnoDB COMMENT='Time dimension for order analysis';

-- Pre-populate Time dimension (168 rows)
INSERT INTO Dim_Time (time_id, order_dow, dow_name, order_hour, hour_range, is_weekend)
SELECT 
    dow * 100 + hour AS time_id,
    dow AS order_dow,
    CASE dow
        WHEN 0 THEN 'Sunday'
        WHEN 1 THEN 'Monday'
        WHEN 2 THEN 'Tuesday'
        WHEN 3 THEN 'Wednesday'
        WHEN 4 THEN 'Thursday'
        WHEN 5 THEN 'Friday'
        WHEN 6 THEN 'Saturday'
    END AS dow_name,
    hour AS order_hour,
    CASE
        WHEN hour BETWEEN 0 AND 5 THEN '00-06 Night'
        WHEN hour BETWEEN 6 AND 11 THEN '06-12 Morning'
        WHEN hour BETWEEN 12 AND 17 THEN '12-18 Afternoon'
        ELSE '18-24 Evening'
    END AS hour_range,
    dow IN (0, 6) AS is_weekend
FROM
    (SELECT 0 AS dow UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 
     UNION SELECT 4 UNION SELECT 5 UNION SELECT 6) days
CROSS JOIN
    (SELECT 0 AS hour UNION SELECT 1 UNION SELECT 2 UNION SELECT 3
     UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7
     UNION SELECT 8 UNION SELECT 9 UNION SELECT 10 UNION SELECT 11
     UNION SELECT 12 UNION SELECT 13 UNION SELECT 14 UNION SELECT 15
     UNION SELECT 16 UNION SELECT 17 UNION SELECT 18 UNION SELECT 19
     UNION SELECT 20 UNION SELECT 21 UNION SELECT 22 UNION SELECT 23) hours
ORDER BY dow, hour;

SELECT 'Dim_Time created and populated with 168 rows!' as Status;
SELECT COUNT(*) as total_rows FROM Dim_Time;
