-- MySQL 8.0 schema. Currency: TWD; business timezone: Asia/Taipei.
CREATE DATABASE IF NOT EXISTS ecommerce_analytics CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE ecommerce_analytics;

CREATE TABLE IF NOT EXISTS products (
  product_id VARCHAR(16) PRIMARY KEY,
  product_name VARCHAR(255) NOT NULL,
  category VARCHAR(64) NOT NULL,
  price DECIMAL(12,2) NOT NULL,
  sold_count INT UNSIGNED NOT NULL,
  rating DECIMAL(3,2) NOT NULL,
  review_count INT UNSIGNED NOT NULL,
  shop_name VARCHAR(128) NOT NULL,
  location VARCHAR(64) NOT NULL,
  crawl_time DATETIME NOT NULL,
  source_url VARCHAR(512) NOT NULL,
  data_source_type VARCHAR(32) NOT NULL,
  hot_score DECIMAL(6,2) NOT NULL,
  opportunity_score DECIMAL(6,2) NOT NULL,
  CHECK (price > 0), CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS users (
  user_id VARCHAR(16) PRIMARY KEY,
  age_group VARCHAR(16) NOT NULL,
  region VARCHAR(64) NOT NULL,
  register_date DATE NOT NULL,
  acquisition_channel VARCHAR(32) NOT NULL,
  repeat_propensity DECIMAL(6,4) NOT NULL,
  data_source_type VARCHAR(32) NOT NULL,
  CHECK (repeat_propensity BETWEEN 0 AND 1)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS calendar (
  date DATE PRIMARY KEY,
  year SMALLINT NOT NULL,
  quarter CHAR(2) NOT NULL,
  month CHAR(7) NOT NULL,
  week TINYINT UNSIGNED NOT NULL,
  weekday VARCHAR(12) NOT NULL,
  is_weekend TINYINT(1) NOT NULL,
  is_promotion TINYINT(1) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS orders (
  order_id VARCHAR(16) PRIMARY KEY,
  user_id VARCHAR(16) NOT NULL,
  product_id VARCHAR(16) NOT NULL,
  order_date DATE NOT NULL,
  quantity TINYINT UNSIGNED NOT NULL,
  unit_price DECIMAL(12,2) NOT NULL,
  discount_amount DECIMAL(12,2) NOT NULL,
  gross_amount DECIMAL(12,2) NOT NULL,
  refund_amount DECIMAL(12,2) NOT NULL,
  net_sales DECIMAL(12,2) NOT NULL,
  cost DECIMAL(12,2) NOT NULL,
  status ENUM('completed','refunded','cancelled') NOT NULL,
  currency CHAR(3) NOT NULL DEFAULT 'TWD',
  data_source_type VARCHAR(32) NOT NULL,
  CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(user_id),
  CONSTRAINT fk_orders_product FOREIGN KEY (product_id) REFERENCES products(product_id),
  CONSTRAINT fk_orders_date FOREIGN KEY (order_date) REFERENCES calendar(date),
  CHECK (quantity > 0), CHECK (unit_price > 0),
  CHECK (discount_amount >= 0 AND gross_amount >= 0 AND refund_amount >= 0 AND net_sales >= 0 AND cost >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ads (
  date DATE NOT NULL,
  campaign_id VARCHAR(16) NOT NULL,
  campaign_name VARCHAR(128) NOT NULL,
  channel VARCHAR(32) NOT NULL,
  impressions INT UNSIGNED NOT NULL,
  clicks INT UNSIGNED NOT NULL,
  spend DECIMAL(12,2) NOT NULL,
  conversions INT UNSIGNED NOT NULL,
  attributed_revenue DECIMAL(12,2) NOT NULL,
  currency CHAR(3) NOT NULL DEFAULT 'TWD',
  data_source_type VARCHAR(32) NOT NULL,
  PRIMARY KEY (date, campaign_id),
  CONSTRAINT fk_ads_date FOREIGN KEY (date) REFERENCES calendar(date),
  CHECK (clicks <= impressions), CHECK (conversions <= clicks), CHECK (spend >= 0)
) ENGINE=InnoDB;

