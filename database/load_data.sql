-- Run from the repository root after replacing the absolute paths below.
-- MySQL server must permit LOAD DATA LOCAL INFILE; otherwise use import_mysql.py.
USE ecommerce_analytics;
SET FOREIGN_KEY_CHECKS=0;
TRUNCATE TABLE ads; TRUNCATE TABLE orders; TRUNCATE TABLE calendar; TRUNCATE TABLE users; TRUNCATE TABLE products;
SET FOREIGN_KEY_CHECKS=1;

-- Example (repeat with the matching column list for each table):
-- LOAD DATA LOCAL INFILE 'C:/absolute/path/data/processed/products.csv'
-- INTO TABLE products CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
-- LINES TERMINATED BY '\n' IGNORE 1 LINES
-- (product_id,product_name,category,price,sold_count,rating,review_count,shop_name,location,@crawl_time,source_url,data_source_type,hot_score,opportunity_score)
-- SET crawl_time = STR_TO_DATE(SUBSTRING(@crawl_time,1,19),'%Y-%m-%d %H:%i:%s');

-- Recommended complete loader:
-- python database/import_mysql.py --data-dir data/processed

