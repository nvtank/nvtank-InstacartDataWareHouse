-- DESTRUCTIVE: run only through `make reset-db` after explicit confirmation.
DROP DATABASE IF EXISTS instacart_dwh;
CREATE DATABASE instacart_dwh
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
