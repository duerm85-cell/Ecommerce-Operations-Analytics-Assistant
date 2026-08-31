# Data dictionary

All monetary values use TWD. Dates use the Asia/Taipei business calendar. Every distributed row is synthetic; `source_url` in products is an `example.com` placeholder.

## products

| Field | Type | Meaning |
|---|---|---|
| product_id | VARCHAR(16) PK | Stable synthetic product key |
| product_name | VARCHAR(255) | Synthetic, non-branded display name |
| category | VARCHAR(64) | Platform-neutral merchandise category |
| price | DECIMAL(12,2) | Listed unit price, TWD |
| sold_count | INT | Synthetic market demand proxy, not real Shopee sales |
| rating | DECIMAL(3,2) | Synthetic score in [1,5] |
| review_count | INT | Synthetic review volume |
| shop_name | VARCHAR(128) | Synthetic shop label |
| location | VARCHAR(64) | Taiwan region label |
| crawl_time | DATETIME | Fixed sample snapshot time |
| source_url | VARCHAR(512) | Non-production placeholder URL |
| hot_score | DECIMAL(6,2) | Weighted normalized demand/quality score |
| opportunity_score | DECIMAL(6,2) | Demand minus competition/price-density score |

## users

`user_id` is the PK. `age_group`, `region`, `register_date`, and `acquisition_channel` support cohort analysis. `repeat_propensity` is a simulation parameter and must not be treated as a production feature or inferred personal trait.

## orders

`order_id` is the PK; `user_id` and `product_id` reference dimensions. `gross_amount = quantity × unit_price`; `net_sales` is recognized only for completed orders after discounts; refunded/cancelled orders have zero recognized net sales and cost. `refund_amount` records the returned post-discount amount. Status is one of `completed`, `refunded`, `cancelled`.

## ads

Daily campaign grain. `impressions`, `clicks`, `spend`, `conversions`, and `attributed_revenue` support CTR, CVR, CPC, CPA and ROAS. Attribution is synthetic last-touch-like revenue and is not causal incrementality.

## calendar

One row per date with year, quarter, month, ISO week, weekday, weekend and promotion flags.

