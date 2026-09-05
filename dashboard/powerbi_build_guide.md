# Power BI V1.1 build and refresh guide

## Delivery status

V1.1 includes genuine Power BI artifacts created with Power BI Desktop 2.157.879.0:

- `powerbi_project/Ecommerce-Operations-Analytics-Assistant-v1.1.pbix` — validated 3.05 MB report with embedded synthetic data.
- `powerbi_project/Ecommerce-Operations-Analytics-Assistant.pbip` — source-controlled project using enhanced PBIR report definitions and TMDL semantic-model definitions.
- `powerbi_screenshots/` — four 1440×810 screenshots captured from the real Power BI pages.

The PBIX and PBIP are native Power BI files. No extension renaming, archive substitution or placeholder artifact is used.

## Fastest review path

1. Download `Ecommerce-Operations-Analytics-Assistant-v1.1.pbix`.
2. Open it in Power BI Desktop.
3. Check pages `经营总览`, `商品分析`, `用户分析` and `广告分析`.
4. Change a date/category/region/channel/campaign slicer and confirm connected KPIs and charts update.

The PBIX embeds the validated FY2025 synthetic dataset, so this review path does not require Python or a refresh.

## PBIP source-control path

Full import CSVs and Power BI cache files are intentionally excluded from Git. To refresh the PBIP after cloning:

```powershell
python -m pip install -r requirements.txt
python run_pipeline.py
```

Then:

1. Open `dashboard/powerbi_project/Ecommerce-Operations-Analytics-Assistant.pbip`.
2. Choose **Transform data → Manage parameters**.
3. Set `DataRoot` to the absolute path of this checkout's `dashboard/powerbi_data` directory.
4. Apply changes and select **Refresh**.
5. Save the project. Do not commit `.pbi` cache or local settings.

The checked-in parameter contains a neutral example path, not the author's machine path. All five partitions read `DataRoot` plus their CSV filename.

## Model

Dimensions filter facts with one-to-many, single-direction relationships:

| From (1) | To (*) | Purpose |
|---|---|---|
| `calendar[date]` | `orders[order_date]` | order-date filtering |
| `calendar[date]` | `ads[date]` | advertising-date filtering |
| `products[product_id]` | `orders[product_id]` | product/category filtering |
| `users[user_id]` | `orders[user_id]` | customer/region/acquisition filtering |

`calendar` is the only date table. The model contains no many-to-many or bidirectional relationship. `KPI Measures` is a dedicated calculated table holding 37 explicit measures.

## Pages and interactions

- **经营总览** — GMV, Net Sales, Completed Orders, Gross Profit, Gross Margin, AOV, Purchasing Users and fixed-window Repeat Rate; 12-month sales trend; category contribution; date/category/region/acquisition slicers.
- **商品分析** — product count, units, sales and profit; Top 10 products; price bands; Hot Score and Opportunity Score; category slicer.
- **用户分析** — RFM groups, recency/frequency/monetary summaries, new/repeat users, region distribution; region/RFM/customer-type slicers.
- **广告分析** — Spend, Impressions, Clicks, Conversions, CTR, CVR, CPC, CPA and ROAS; monthly trend, campaign comparison and channel efficiency; date/channel/campaign slicers.

Page size is 1440×810. Amounts are TWD, ratios use explicit percentage or `x` formats, and every page displays a synthetic-data warning.

## Metric and scope notes

- GMV includes `completed` and `refunded` order gross amount before discount/refund.
- Net Sales, Completed Orders, Gross Profit and AOV use only `completed` orders.
- Repeat Rate uses a fixed FY2025 observation window: purchasing users with at least two completed orders divided by purchasing users with at least one completed order. It intentionally removes calendar filters to prevent unequal windows.
- Advertising revenue is attributed revenue from the ads fact. It is not order net sales and does not prove causal lift.
- `DIVIDE` protects all rate and cost measures from zero denominators.

Exact DAX is in `dax_measures.md`; the model-to-baseline reconciliation is in `../reports/powerbi_validation.md`.

## Regenerating project definitions

The committed scripts document the repeatable construction process:

- `powerbi_project/build_model_tom.ps1` creates and refreshes the six-table model through the Power BI Tabular Object Model against an explicitly selected local Desktop instance.
- `powerbi_project/generate_pbir_report.ps1` deterministically creates the four enhanced-PBIR pages, adds display/ranking measures, normalizes TWD formats and replaces author-specific partition paths with `DataRoot`.

These scripts are advanced maintenance tools, not required to open the committed PBIX.

## Validation record

The saved PBIX was closed/reopened as `Ecommerce-Operations-Analytics-Assistant-v1.1`; UI Automation found all four page tabs and populated KPI cards. A read-only ADOMD query against that reopened file found 37 measures and matched the 12 baseline KPIs within floating-point tolerance. The PBIP folder was also deserialized with Power BI Desktop's bundled TMDL serializer: 6 tables, 4 relationships, 1 `DataRoot` expression and 37 measures.
