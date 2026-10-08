# Olist Analytics 层

## 目的

Analytics 层由 Olist DWD 构建少量面向分析的 marts，为 Power BI 提供稳定输入，避免在原始一对多粒度直接 join order items、payments 和 reviews。

使用以下命令重建：

```powershell
.\.venv\Scripts\python.exe -m etl.olist.build_analytics
```

输出数据库为 `data/olist_analytics.sqlite`。

同一命令还会向 `dashboard/powerbi_data/` 导出 Power BI CSV：

- `olist_business_overview.csv`
- `olist_monthly_performance.csv`
- `olist_customer_rfm.csv`
- `olist_customer_segments.csv`
- `olist_category_performance.csv`
- `olist_metric_definitions.csv`

这些文件是可重建产物，由 Git 排除。每个 CSV 使用稳定文件名、列顺序、确定性行排序和带 BOM 的 UTF-8 编码。

## 业务口径

Sales and customer value metrics use orders whose original Olist status is `delivered`. The source status is not renamed or changed. Cancel Rate uses `canceled` orders divided by all placed orders.

All customer metrics use `customer_unique_id`. The record-level `customer_id` is not used as the final customer identity.

All monetary fields are BRL. No currency conversion, product cost, profit, margin, advertising metric, or synthetic value is introduced.

## Analytics 表

| Table | Grain | Current rows | Purpose |
|---|---|---:|---|
| `mart_business_overview` | One all-time snapshot | 1 | Executive KPIs |
| `mart_monthly_performance` | One purchase month | 25 | Orders and value trends |
| `mart_customer_rfm` | One purchasing `customer_unique_id` | 93,358 | Customer value and RFM |
| `mart_customer_segments` | One RFM segment | 8 | Segment comparison |
| `mart_category_performance` | One source product category | 74 | Category sales, freight, and review analysis |
| `analytics_metric_definitions` | One metric definition | 16 | Auditable formulas and scopes |

## 核心指标定义

### Orders

Distinct `order_id` where `order_status = 'delivered'`.

### Purchasing Customers

Distinct `customer_unique_id` with at least one delivered order.

### Merchandise GMV

```text
SUM(fact_order_items.price_brl)
for delivered orders
```

Freight is excluded. Payment value is not used as merchandise GMV.

### Paid Value

```text
SUM(fact_payments.payment_value_brl)
for delivered orders
```

Paid Value and Merchandise GMV are separate measures because payment totals can include freight and other payment-level effects.

### Units Sold

Count of order-item records belonging to delivered orders.

### AOV

```text
Merchandise GMV / Delivered Orders
```

AOV therefore represents average delivered merchandise value per order, excluding freight.

### Repeat Purchase Rate

```text
Customers with at least 2 delivered orders
------------------------------------------------
Customers with at least 1 delivered order
```

Both numerator and denominator use `customer_unique_id`.

### Average Review Score

Average source review score for review records attached to delivered orders. Orders without reviews remain in order and GMV metrics but are excluded from the review average denominator.

### Cancel Rate

```text
Orders whose original status is canceled / All placed orders
```

## RFM 定义

RFM includes customers with at least one delivered order.

- **Recency:** days between the deterministic as-of date and the customer's latest delivered purchase date.
- **Frequency:** distinct delivered orders for the customer.
- **Monetary:** sum of delivered `price_brl` for the customer, excluding freight and payment value.
- **As-of date:** one day after the latest delivered purchase timestamp in the dataset. The current value is `2018-08-30`.

Scores are deterministic:

- `r_score`: percentile rank of Recency, with more recent customers receiving higher scores.
- `f_score`: delivered order count bands: one order = 1, two = 2, three = 3, four = 4, five or more = 5.
- `m_score`: percentile rank of Monetary, with higher value receiving higher scores.
- `rfm_score`: `100 × r_score + 10 × f_score + m_score`.

Segments are assigned in a fixed rule order: Champions, Loyal Customers, Potential Loyalists, New Customers, Big Spenders, At Risk, Hibernating, and Needs Attention. This is a rule-based analytical segmentation, not a machine learning model.

## 品类指标

The category mart uses `category_en` as the display name when available. Untranslated Portuguese categories and products with missing categories remain in the mart.

- Category GMV: delivered item `price_brl`.
- Orders: distinct delivered orders containing the category.
- Units Sold: delivered item records.
- Average Item Price: average delivered item price.
- Freight Value: delivered item freight.
- Freight Ratio: freight value divided by Merchandise GMV.
- Average Review Score: average review score attributed through distinct order-category relationships.
- Low Rating Rate: share of attributed review records whose score is 1 or 2.

Reviews are associated with an order rather than a specific item. When an order contains multiple categories, its reviews are attributed once to each distinct category in that order. This supports category comparison but should not be interpreted as an item-level causal review.

## 多事实表防放大

Order items, payments, and reviews are aggregated independently to `order_id` before they are combined for overview and monthly marts. Category monetary metrics come only from order items. Customer Monetary comes only from delivered order-item value.

This prevents one order with multiple items, payments, and reviews from multiplying amounts.

## 当前全周期快照

| Metric | Value |
|---|---:|
| Delivered Orders | 96,478 |
| Purchasing Customers | 93,358 |
| Repeat Customers | 2,801 |
| Repeat Purchase Rate | 3.00% |
| Merchandise GMV | BRL 13,221,498.11 |
| Paid Value | BRL 15,422,461.77 |
| Units Sold | 110,197 |
| Freight Value | BRL 2,198,275.64 |
| AOV | BRL 137.04 |
| Average Review Score | 4.156 |
| Canceled Orders | 625 |
| Cancel Rate | 0.629% |

## 质量检查

The build executes business checks before committing the transaction:

- all analytics tables exist;
- primary and foreign keys are valid;
- Merchandise GMV reconciles to delivered item facts;
- Paid Value reconciles independently to payment facts;
- all customer metrics use `customer_unique_id`;
- RFM is one row per purchasing customer;
- Repeat Purchase Rate is within `[0, 1]` and matches customer frequency;
- review scores and low-rating rates are valid;
- freight values and ratios are nonnegative;
- monthly, category, and segment marts reconcile to the overview;
- required metric definitions are present.

## 限制

- Olist is a historical public dataset and does not represent a live company system.
- Delivered is used as the documented effective sales scope; it is not a replacement source status.
- The data does not support product cost, gross profit, gross margin, advertising KPIs, or confirmed refunds.
- Reviews are order-level and cannot identify which item caused a score.
- RFM segments are descriptive rules for this snapshot and are not causal predictions.
