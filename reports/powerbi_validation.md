# Power BI V1.1 validation record

- Validation date: 2026-09-05 (Asia/Shanghai)
- Power BI Desktop: 2.157.879.0
- Dataset: fixed-seed FY2025 synthetic data (`20260801`)
- Currency: TWD

## Artifacts

- `dashboard/powerbi_project/Ecommerce-Operations-Analytics-Assistant.pbip`
- `dashboard/powerbi_project/Ecommerce-Operations-Analytics-Assistant.Report/`
- `dashboard/powerbi_project/Ecommerce-Operations-Analytics-Assistant.SemanticModel/`
- `dashboard/powerbi_project/Ecommerce-Operations-Analytics-Assistant-v1.1.pbix`

The PBIP, PBIR/TMDL folders and PBIX were created by Power BI Desktop or its bundled model APIs. The PBIX is a native 3,049,825-byte Power BI file, not a renamed archive or placeholder. SHA-256: `E4F08C3C933136A636994B91936D4A87E676E6DE64008B1D9BE770368B177B75`.

## Reopen and page checks

The saved PBIX was launched in a new Power BI Desktop process and reopened under the title `Ecommerce-Operations-Analytics-Assistant-v1.1`. Desktop accessibility inspection found all four page tabs:

1. `经营总览`
2. `商品分析`
3. `用户分析`
4. `广告分析`

The overview exposed populated cards for GMV, Net Sales, Gross Margin, AOV and fixed-window Repeat Rate. Each report page was inspected at 1440×810; no field-error banner, empty required chart, text collision or clipped title was observed. Real Desktop screenshots are stored in `dashboard/powerbi_screenshots/`.

An interaction test selected `Skincare` in the overview category slicer. Net Sales, Gross Margin, Purchasing Users, Repeat Rate and the connected charts changed. The selection was discarded afterward. Read-only DAX filters also verified date (`2025-01`), category (`Skincare`), region (`Taipei`), acquisition channel (`Organic`), advertising channel (`Search Ads`) and campaign (`Brand Search`) propagation.

## Semantic model checks

Power BI Desktop's bundled TMDL serializer deserialized the checked-in semantic-model definition successfully:

| Check | Result |
|---|---:|
| Tables | 6 |
| Relationships | 4 |
| Explicit measures | 37 |
| Shared M parameters | 1 (`DataRoot`) |
| Relationship direction | dimension → fact, single |
| Many-to-many relationships | 0 |

All five import partitions reference `DataRoot` plus a CSV filename. The checked-in TMDL contains no author-machine path. Full CSVs and `.pbi` cache files are regenerated/ignored and are not required to open the distributable PBIX.

## DAX reconciliation from the reopened PBIX

A read-only ADOMD query ran against the local Analysis Services model created by the reopened PBIX. Expected values come from `reports/kpi_summary.json`, which is produced independently by the Python/SQLite pipeline.

| KPI | Expected | Reopened PBIX DAX | Difference | Result |
|---|---:|---:|---:|---|
| GMV | 39,295,789.00 | 39,295,789.00 | 0.00 | PASS |
| Net Sales | 35,169,616.30 | 35,169,616.30 | 0.00 | PASS |
| Completed Orders | 55,890 | 55,890 | 0 | PASS |
| Gross Profit | 14,339,912.83 | 14,339,912.83 | < 0.000001 | PASS |
| Gross Margin | 0.4077358339 | 0.4077358339 | < 1e-12 | PASS |
| AOV | 629.2649185901 | 629.2649185901 | 0.00 | PASS |
| Purchasing Users | 11,381 | 11,381 | 0 | PASS |
| Repeat Rate FY2025 | 0.8961426940 | 0.8961426940 | 0.00 | PASS |
| CTR | 0.0326883814 | 0.0326883814 | 0.00 | PASS |
| CVR | 0.0762128892 | 0.0762128892 | 0.00 | PASS |
| CPA | 93.0594258734 | 93.0594258734 | 0.00 | PASS |
| ROAS | 7.9158801748 | 7.9158801748 | 0.00 | PASS |

The model also returned 37 measures and ten visible rows for both Top Sales Product and Top Opportunity Product checks.

## Scope boundaries

- GMV includes gross amount for `completed` and `refunded` orders; Net Sales, Gross Profit, Completed Orders and AOV use only `completed` orders.
- The annual repeat rate uses one fixed FY2025 window and removes calendar filters. This avoids comparing unequal observation windows.
- Advertising attributed revenue and order net sales are separate facts. ROAS is attribution efficiency, not causal lift.
- Power BI `DIVIDE` handles zero denominators for CTR, CVR, CPC, CPA, ROAS, AOV and margin.
- The PBIP requires a reviewer to set `DataRoot` once before refreshing on a new machine. The PBIX embeds data and requires no source-path change.
