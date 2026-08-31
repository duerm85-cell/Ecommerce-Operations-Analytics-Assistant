USE ecommerce_analytics;

-- 1. Monthly GMV, completed orders, net sales, profit, margin, AOV and MoM net-sales growth.
WITH monthly AS (
  SELECT DATE_FORMAT(order_date,'%Y-%m') month,
    SUM(CASE WHEN status IN ('completed','refunded') THEN gross_amount ELSE 0 END) gmv,
    COUNT(DISTINCT CASE WHEN status='completed' THEN order_id END) orders,
    SUM(net_sales) net_sales, SUM(net_sales-cost) gross_profit
  FROM orders GROUP BY 1
), lagged AS (
  SELECT monthly.*, LAG(net_sales) OVER (ORDER BY month) prior_net_sales FROM monthly
)
SELECT *, gross_profit/NULLIF(net_sales,0) gross_margin,
  net_sales/NULLIF(orders,0) aov,
  (net_sales-prior_net_sales)/NULLIF(prior_net_sales,0) mom_net_sales
FROM lagged ORDER BY month;

-- 2. Product sales rank inside category and cumulative category contribution.
WITH product_sales AS (
  SELECT p.category,p.product_id,p.product_name,SUM(o.net_sales) net_sales,SUM(o.quantity) units
  FROM products p JOIN orders o USING(product_id) WHERE o.status='completed'
  GROUP BY p.category,p.product_id,p.product_name
), ranked AS (
  SELECT *, DENSE_RANK() OVER(PARTITION BY category ORDER BY net_sales DESC) sales_rank,
    SUM(net_sales) OVER(PARTITION BY category ORDER BY net_sales DESC ROWS UNBOUNDED PRECEDING)
      / SUM(net_sales) OVER(PARTITION BY category) cumulative_share
  FROM product_sales
) SELECT * FROM ranked ORDER BY category,sales_rank;

-- 3. Category performance.
SELECT p.category, SUM(o.net_sales) net_sales, SUM(o.net_sales-o.cost) gross_profit,
  SUM(o.net_sales-o.cost)/NULLIF(SUM(o.net_sales),0) gross_margin, SUM(o.quantity) units
FROM orders o JOIN products p USING(product_id) WHERE o.status='completed'
GROUP BY p.category ORDER BY net_sales DESC;

-- 4. Annual repeat rate (fixed 2025 window).
WITH user_orders AS (
  SELECT user_id,COUNT(DISTINCT order_id) order_count FROM orders
  WHERE status='completed' AND order_date BETWEEN '2025-01-01' AND '2025-12-31' GROUP BY user_id
) SELECT COUNT(*) purchasing_users,SUM(order_count>=2) repeat_users,
  SUM(order_count>=2)/NULLIF(COUNT(*),0) repeat_rate FROM user_orders;

-- 5. RFM segmentation using quintiles, as of 2025-12-31.
WITH base AS (
 SELECT user_id,DATEDIFF('2025-12-31',MAX(order_date)) recency,
   COUNT(DISTINCT order_id) frequency,SUM(net_sales) monetary
 FROM orders WHERE status='completed' GROUP BY user_id
), scored AS (
 SELECT *, 6-NTILE(5) OVER(ORDER BY recency) r_score,
   NTILE(5) OVER(ORDER BY frequency) f_score,NTILE(5) OVER(ORDER BY monetary) m_score FROM base
) SELECT *, CASE WHEN r_score>=4 AND f_score>=4 THEN 'Champions'
 WHEN f_score>=4 THEN 'Loyal' WHEN r_score>=4 AND f_score<=2 THEN 'New & Promising'
 WHEN r_score<=2 AND f_score>=3 THEN 'At Risk' WHEN r_score<=2 AND f_score<=2 THEN 'Hibernating'
 ELSE 'Potential Loyalists' END rfm_segment FROM scored;

-- 6. Acquisition channel quality.
SELECT u.acquisition_channel,COUNT(DISTINCT o.user_id) buyers,SUM(o.net_sales) net_sales,
 SUM(o.net_sales)/NULLIF(COUNT(DISTINCT o.user_id),0) revenue_per_buyer
FROM users u JOIN orders o USING(user_id) WHERE o.status='completed' GROUP BY 1 ORDER BY net_sales DESC;

-- 7. Advertising efficiency by campaign.
SELECT campaign_id,campaign_name,channel,SUM(impressions) impressions,SUM(clicks) clicks,
 SUM(conversions) conversions,SUM(spend) spend,SUM(attributed_revenue) attributed_revenue,
 SUM(clicks)/NULLIF(SUM(impressions),0) ctr,SUM(conversions)/NULLIF(SUM(clicks),0) cvr,
 SUM(spend)/NULLIF(SUM(clicks),0) cpc,SUM(spend)/NULLIF(SUM(conversions),0) cpa,
 SUM(attributed_revenue)/NULLIF(SUM(spend),0) roas
FROM ads GROUP BY campaign_id,campaign_name,channel ORDER BY roas DESC;

-- 8. High-spend, low-return campaigns.
WITH perf AS (
 SELECT campaign_id,campaign_name,SUM(spend) spend,SUM(attributed_revenue)/NULLIF(SUM(spend),0) roas
 FROM ads GROUP BY campaign_id,campaign_name
) SELECT * FROM perf WHERE spend>(SELECT AVG(spend) FROM perf) AND roas<2 ORDER BY spend DESC;

-- 9. High-volume, low-margin products.
WITH perf AS (
 SELECT p.product_id,p.product_name,p.category,SUM(o.quantity) units,SUM(o.net_sales-o.cost)/NULLIF(SUM(o.net_sales),0) margin
 FROM products p JOIN orders o USING(product_id) WHERE o.status='completed' GROUP BY p.product_id,p.product_name,p.category
) SELECT * FROM perf WHERE units>=(SELECT AVG(units) FROM perf) AND margin<0.30 ORDER BY units DESC;

-- 10. Weekend and promotion uplift.
SELECT c.is_weekend,c.is_promotion,COUNT(DISTINCT c.date) days,SUM(o.net_sales) net_sales,
 SUM(o.net_sales)/COUNT(DISTINCT c.date) avg_daily_net_sales
FROM calendar c LEFT JOIN orders o ON o.order_date=c.date AND o.status='completed'
GROUP BY c.is_weekend,c.is_promotion ORDER BY c.is_promotion DESC,c.is_weekend DESC;

