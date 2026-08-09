-- Safe bootstrap: existing databases and their data are preserved.
CREATE DATABASE IF NOT EXISTS instacart_dwh
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE instacart_dwh;

SELECT 'Database instacart_dwh is ready.' AS status;
