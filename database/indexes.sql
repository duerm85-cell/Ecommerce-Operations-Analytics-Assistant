USE ecommerce_analytics;
CREATE INDEX idx_orders_date_status ON orders(order_date, status);
CREATE INDEX idx_orders_user_date ON orders(user_id, order_date);
CREATE INDEX idx_orders_product_date ON orders(product_id, order_date);
CREATE INDEX idx_products_category_scores ON products(category, hot_score, opportunity_score);
CREATE INDEX idx_users_channel_region ON users(acquisition_channel, region);
CREATE INDEX idx_ads_channel_campaign_date ON ads(channel, campaign_id, date);

