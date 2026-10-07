# Olist Power BI Dashboard Specification

## Delivery Status

The Olist analytics database and Power BI-ready CSV inputs are implemented and validated. The Olist report pages have **not** been created or saved in Power BI Desktop in this repository.

The existing PBIP/PBIX files are the validated Synthetic V1.1/V1.2 legacy dashboard. They must not be presented as an Olist dashboard.

## Data Inputs

Run:

```powershell
.\.venv\Scripts\python.exe -m etl.olist.build_analytics
```

This creates the following generated files in `dashboard/powerbi_data/`:

| CSV | Grain | Use |
|---|---|---|
| `olist_business_overview.csv` | One all-time snapshot | KPI cards |
| `olist_monthly_performance.csv` | One purchase month | Monthly trends |
| `olist_customer_rfm.csv` | One `customer_unique_id` | Customer distributions and drill-through |
| `olist_customer_segments.csv` | One RFM segment | Segment comparison |
| `olist_category_performance.csv` | One source category | Category performance |
| `olist_metric_definitions.csv` | One metric | Measure documentation |

These generated CSVs are intentionally Git-ignored. Power BI should import the marts directly instead of recreating joins across item, payment, and review facts.

## Report Scope

The report contains two pages. All monetary values are BRL. Sales and customer metrics use original Olist orders with `order_status = 'delivered'`. Cancel Rate uses original `canceled` orders divided by all placed orders.

Unsupported metrics must remain absent:

- CTR, CVR, CPA, ROAS
- Gross Profit and Gross Margin
- Product cost and ad spend
- Synthetic refund or advertising values

## Page 1 — Executive Overview

### Goal

Allow a reviewer to understand overall order volume, customer reach, merchandise value, payment value, service quality, and trend direction within 30 seconds.

### KPI Cards

1. Merchandise GMV — `merchandise_gmv_brl`
2. Orders — delivered `orders`
3. Purchasing Customers — distinct `customer_unique_id`
4. AOV — Merchandise GMV divided by delivered Orders
5. Repeat Purchase Rate — repeat customers divided by purchasing customers
6. Average Review Score — delivered-order review records

Optional secondary cards:

- Paid Value
- Units Sold
- Cancel Rate

### Visuals

| Visual | Source | Fields | Purpose |
|---|---|---|---|
| Monthly GMV Trend | `olist_monthly_performance.csv` | `month_key`, `merchandise_gmv_brl` | Show delivered merchandise value over time |
| Monthly Orders Trend | `olist_monthly_performance.csv` | `month_key`, `orders` | Separate order volume from value changes |
| Top Categories | `olist_category_performance.csv` | `category_display_name`, `merchandise_gmv_brl` | Identify category concentration |
| Order Status Distribution | DWD query or a separately exported status summary | Original `order_status`, orders | Show delivered, canceled, shipped, unavailable, and other source statuses |
| KPI Definition Tooltip | `olist_metric_definitions.csv` | name, definition, scope | Make metric boundaries auditable |

Geography should only be added after producing a documented state-level mart with a single deterministic customer/order geography rule. It is excluded from the current delivery to avoid using nonunique geolocation rows incorrectly.

### Recommended Interaction

- Month slicer using `month_key`
- Category selection cross-highlights monthly trends only if the model uses an appropriate shared category/date structure
- Tooltip displays order scope and metric definition

## Page 2 — Customer & Product Insights

### Goal

Connect customer retention and category quality signals to evidence-based actions.

### Customer Section

| Visual | Source | Fields | Question |
|---|---|---|---|
| RFM Segment Distribution | `olist_customer_segments.csv` | `rfm_segment`, `customers` | Which customer groups dominate? |
| Repeat vs One-time Customers | `olist_customer_rfm.csv` | `is_repeat_customer`, customer count | How large is the repeat base? |
| Customer Monetary Distribution | `olist_customer_rfm.csv` | `monetary_value_brl` | How concentrated is customer value? |
| Segment Value Table | `olist_customer_segments.csv` | customers, average frequency, total and average monetary | Which segments combine value and retention? |

### Product Section

| Visual | Source | Fields | Question |
|---|---|---|---|
| Category GMV | `olist_category_performance.csv` | category, GMV | Which categories create merchandise value? |
| Category Review Score | same | category, average review score | Which high-volume categories have weaker ratings? |
| Freight Ratio | same | category, freight ratio | Where is freight large relative to item value? |
| Risk Category Matrix | same | GMV, low rating rate, freight ratio, orders | Which material categories combine commercial value with quality or freight risk? |
| Top/Bottom Category Table | same | GMV, orders, ratings, low rating rate, freight ratio | Provide exact evidence behind rankings |

### Insight Narrative Pattern

Every page annotation or interview statement should follow:

```text
Finding → Evidence → Possible interpretation → Possible action
```

Use “may”, “is associated with”, or “requires investigation” for possible explanations. Order-level reviews and observational data do not prove that freight or delivery caused a rating.

## Minimal Power BI Model

The first Olist PBIX can use imported mart tables without relationships because each visual can read from one pre-aggregated table. This keeps the initial report simple and avoids cross-fact ambiguity.

If cross-filtering across pages is later required, introduce shared Date and Category dimensions from DWD with explicit one-to-many relationships. Do not connect customer RFM directly to category performance through ambiguous many-to-many paths.

## Formatting

- Currency: `R$ #,##0.00`
- Rates: `0.0%` or `0.00%` for small values
- Review score: `0.00`
- Orders and customers: whole numbers with thousands separators
- Titles should state “Delivered Orders” or “Delivered Merchandise GMV” when space permits
- Add a footer: `Olist public historical data | BRL | Delivered sales scope`

## Required Manual Power BI Steps

1. Run the ODS, DWD, and Analytics commands to generate the six CSVs.
2. Open Power BI Desktop and create a new Olist report; do not overwrite the legacy Synthetic PBIX.
3. Import the six `olist_*.csv` files from `dashboard/powerbi_data/`.
4. Set data types and BRL/percentage formats.
5. Build the two pages according to this specification.
6. Verify all six KPI cards against `mart_business_overview`.
7. Save the report with an explicit Olist filename, such as `Ecommerce-Operations-Analytics-Olist-v2.pbix`.
8. Reopen the PBIX, refresh it, and repeat KPI reconciliation.
9. Export screenshots to:
   - `docs/assets/olist_dashboard_overview.png`
   - `docs/assets/olist_dashboard_customer_product.png`
10. Only after visual and KPI validation, update the README to embed the screenshots and mark the Olist dashboard complete.

## Acceptance Criteria

- Two pages exist with the specified names and content.
- KPI values reconcile to the analytics overview table.
- Merchandise GMV and Paid Value are visibly distinct.
- Customer visuals use `customer_unique_id`-based marts.
- No unsupported profit or advertising metrics appear.
- Both screenshots exist and render correctly.
- PBIX reopen and refresh are documented.

Until these criteria are met, Power BI status must be reported as **Requires manual Power BI Desktop work**.
