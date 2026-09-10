# Ecommerce Operations Analytics Assistant

> An end-to-end ecommerce operations analytics platform covering public product-market inputs, reproducible ETL, dimensional modeling, governed business metrics, SQL/Python analysis, data-quality validation, and Power BI decision dashboards.

The project models a realistic enterprise analytics workflow across products, customers, orders, advertising, and calendar data. Public product attributes can enter through a controlled ODS contract, while privacy-sensitive customer, transaction, and advertising records are generated with deterministic business rules so that the complete pipeline can be reproduced without distributing confidential data.

![Power BI executive overview](dashboard/powerbi_screenshots/v1.2/01_overview.png)

[中文项目说明](PROJECT_OVERVIEW_V1.2.md) · [Data architecture](docs/data_architecture.md) · [ETL pipeline](docs/etl_pipeline.md) · [Data quality](docs/data_quality.md)

## Project Overview

Ecommerce teams need consistent answers to four connected questions:

- How is the business performing, and where do revenue and profit come from?
- Which products and categories deserve additional investment?
- Which customer groups create value or show churn risk?
- Which advertising channels and campaigns use budget efficiently?

This repository implements the data flow behind those decisions rather than treating the dashboard as an isolated artifact. The same metric definitions are applied across Python, SQL, and DAX, with automated checks for schema integrity, business equations, reproducibility, and cross-engine consistency.

## Features

- **Public product input:** normalize compatible public CSV/ZIP datasets into a six-field product ODS without authentication or access-control bypasses.
- **Deterministic business data:** generate reproducible users, orders, advertising, and calendar data with explicit business constraints.
- **Layered data architecture:** map source data through ODS, DWD, DWS, and ADS responsibilities before presentation.
- **Governed metrics:** standardize GMV, net sales, gross profit, AOV, repeat rate, CTR, CVR, CPA, and ROAS.
- **SQL and Python analytics:** implement product, operations, RFM customer, and advertising analysis with pandas, SQLite, and MySQL-compatible SQL.
- **Cross-engine reconciliation:** compare Python and SQL results automatically and retain a validated DAX reconciliation record.
- **Decision dashboards:** provide four Power BI pages organized as conclusion → KPI → evidence → action.
- **Version-controlled BI assets:** include PBIP, PBIR, TMDL, DAX documentation, validated PBIX files, and clean screenshots.
- **Data-quality gates:** test keys, missingness, ranges, relationships, business equations, metric consistency, and dashboard structure.

## Technology stack

| Area | Technologies |
|---|---|
| Data pipeline and ETL | Python 3.12, pandas, NumPy |
| Storage and SQL | SQLite, MySQL 8-compatible schema and queries |
| Data modeling | Product, customer, order, advertising, and calendar entities; ODS/DWD/DWS/ADS logical layers |
| Business intelligence | Power BI Desktop, PBIP, PBIR, TMDL, DAX |
| Alternative dashboard | HTML, CSS, JavaScript |
| Quality and reproducibility | unittest, fixed random seed, SQL/Python/DAX reconciliation |
| Version control | Git |

## Architecture

```text
External Market Data          Business Simulation Data
        │                     users / orders / ads
        └──────────────┬──────────────┘
                       ↓
                  ODS raw layer
                       ↓
                 DWD detail layer
                       ↓
                DWS summary layer
                       ↓
              ADS application layer
                       ↓
       Power BI and browser decision dashboards
```

Repository mapping:

| Layer | Responsibility | Main implementation |
|---|---|---|
| Source | Public product inputs and deterministic business rules | `crawler/`, `data/generate_data.py` |
| ODS | Source-aligned product input contract | `crawler/raw_data/raw_products.csv` |
| DWD | Standardized entity-level detail | `data/processed/*.csv` |
| DWS | Monthly, product, category, RFM, and campaign summaries | `analysis/run_analysis.py`, SQLite, `database/analysis_queries.sql` |
| ADS | KPI and dashboard-ready outputs | `reports/`, `dashboard/powerbi_data/` |
| Presentation | Interactive business analysis | Power BI and `dashboard/interactive_dashboard.html` |

See [docs/data_architecture.md](docs/data_architecture.md) for layer responsibilities and quality gates.

## Data Sources

### External Market Data

The preferred product input is a license-compatible public dataset containing:

```text
product_id · product_name · category · price · rating · review_count
```

`crawler/product_crawler.py` accepts a local public CSV/ZIP or a directly accessible public URL, maps common source columns, validates values, and writes the normalized ODS file to `crawler/raw_data/raw_products.csv`.

The committed ODS file is header-only so the validated baseline remains reproducible and no third-party dataset is redistributed without a license review. If the file contains valid rows, the pipeline prefers those product attributes. If it is missing or header-only, the original fixed-seed product generator is used.

### Internal Business Data

Users, orders, and advertising rows remain simulated because real enterprise records can contain personal data, transaction details, budgets, attribution logic, and confidential operating results. The generated data preserves the relationships and constraints needed to validate the analytics workflow, but it does not represent a real company, marketplace, store, or customer.

Source selection, compliance boundaries, currency handling, and fallback behavior are documented in [docs/data_source.md](docs/data_source.md) and [crawler/README.md](crawler/README.md).

## Data Model

| Entity | Grain | Role |
|---|---|---|
| `products` | One row per product | Product attributes, public-market fields, demand proxies, and opportunity scores |
| `users` | One row per user | Region, registration, acquisition channel, and RFM inputs |
| `orders` | One row per order | Quantity, price, discount, cost, order status, and recognized sales |
| `ads` | One row per date and campaign | Impressions, clicks, spend, conversions, and attributed revenue |
| `calendar` | One row per date | Year, quarter, month, week, weekday, weekend, and promotion flags |

Orders reference products and users; order and advertising facts connect to the shared calendar. Field definitions are available in [docs/data_dictionary.md](docs/data_dictionary.md).

## Metrics

The metric layer includes:

- GMV and completed net sales;
- completed orders, gross profit, and gross margin;
- purchasing users, fixed-window repeat rate, and AOV;
- RFM recency, frequency, monetary value, scores, and segments;
- advertising CTR, CVR, CPC, CPA, attributed revenue, and ROAS;
- transparent Hot Score and Opportunity Score product shortlists.

Definitions, formulas, inclusion rules, and business interpretation are documented in [docs/business_metrics.md](docs/business_metrics.md) and [docs/metric_dictionary.md](docs/metric_dictionary.md).

## Dashboard

### Operations Overview

Executive view of revenue, profit, margin, ROAS, monthly performance, category contribution, and recommended actions.

![Power BI operations overview](dashboard/powerbi_screenshots/v1.2/01_overview.png)

### Product Opportunity

Product and category investment view combining opportunity, demand, revenue, margin, price bands, and action priorities.

![Power BI product opportunity](dashboard/powerbi_screenshots/v1.2/02_product_opportunity.png)

### Customer Value

Customer portfolio view focused on purchasing users, repeat behavior, RFM value segments, churn risk, and retention actions.

![Power BI customer value](dashboard/powerbi_screenshots/v1.2/03_customer_value.png)

### Advertising Return

Advertising efficiency view covering spend, attributed revenue, ROAS, CPA, CTR, CVR, and channel budget recommendations.

![Power BI advertising return](dashboard/powerbi_screenshots/v1.2/04_advertising_return.png)

The four pages are **经营总览**, **商品机会**, **用户价值**, and **广告回报**. They use synchronized business filters, native page navigation, clear-filter controls, dynamic conclusions, and a consistent TWD/FY2025 display contract.

Power BI deliverables:

- [Validated V1.2 PBIX](dashboard/powerbi_project/Ecommerce-Operations-Analytics-Assistant-v1.2.pbix)
- [Preserved V1.1 PBIX](dashboard/powerbi_project/Ecommerce-Operations-Analytics-Assistant-v1.1.pbix)
- [Version-controlled PBIP](dashboard/powerbi_project/Ecommerce-Operations-Analytics-Assistant.pbip)
- [Power BI build and refresh guide](dashboard/powerbi_build_guide.md)
- [V1.2 design report](reports/powerbi_design_v1.2.md)
- [Power BI validation record](reports/powerbi_validation.md)

The dependency-free [interactive HTML dashboard](dashboard/interactive_dashboard.html) provides a browser-based alternative for environments without Power BI Desktop.

## Quick start

### Prerequisites

- Python 3.12
- Power BI Desktop only if opening or refreshing the PBIX/PBIP assets
- MySQL 8 only if using the optional MySQL deployment path

### Run the complete local pipeline

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_pipeline.py
```

The default run requires no database credentials. It generates deterministic data, builds the SQLite validation database, produces analysis and dashboard outputs, reconciles metrics, and runs the automated test suite.

### Run individual stages

```powershell
python data/generate_data.py --products 800 --users 12000 --orders 60000
python analysis/run_analysis.py
python dashboard/build_dashboard.py
python -m unittest discover -s tests -v
```

For MySQL 8, follow [database/README.md](database/README.md). Credentials must be supplied through environment variables based on [.env.example](.env.example); never commit `.env`.

## Pipeline

`run_pipeline.py` executes four fail-fast stages:

1. **Extract and detail load:** `data/generate_data.py` selects the external product ODS or fixed-seed fallback, generates internal business data, and writes standardized detail files.
2. **Transform and reconcile:** `analysis/run_analysis.py` builds SQLite, calculates KPIs and topic summaries, exports ADS outputs, and compares SQL with Python results.
3. **Build applications:** `dashboard/build_dashboard.py` regenerates the interactive browser dashboard.
4. **Quality gate:** unittest discovery validates data contracts, reproducibility, metrics, external product input, and Power BI structure.

Detailed execution, output locations, and failure behavior are described in [docs/etl_pipeline.md](docs/etl_pipeline.md).

## Testing

Run all tests:

```powershell
python -m unittest discover -s tests -v
```

The current suite contains 19 tests covering:

- minimum scale and required fields;
- primary-key uniqueness and foreign-key consistency;
- value ranges, order equations, dates, currency, and status contracts;
- Hot Score and Opportunity Score recomputation;
- external product mapping, preference, fallback, and downstream compatibility;
- fixed-seed file reproducibility;
- SQLite/Python/dashboard KPI consistency;
- Power BI entry files, pages, semantic-model structure, and screenshot dimensions.

The default dataset contains 800 products, 12,000 users, 60,000 orders, 2,190 daily campaign rows, and 365 calendar dates. The fixed seed is `20260801`.

The latest validated baseline includes GMV of TWD 39.30M, net sales of TWD 35.17M, gross profit of TWD 14.34M, a 40.8% gross margin, and ROAS of 7.92×. These values describe the included baseline only and are not external market benchmarks.

See [docs/data_quality.md](docs/data_quality.md), [reports/test_results.md](reports/test_results.md), and [reports/powerbi_validation.md](reports/powerbi_validation.md) for the quality framework and verification evidence.

## Repository Structure

```text
crawler/      public product input, ODS contract, and access boundaries
database/     MySQL 8 schema, indexes, loader, and business SQL analyses
data/         deterministic data generation, samples, and local detail outputs
analysis/     product, operations, RFM, and advertising transformations
dashboard/    PBIP/PBIX, DAX, screenshots, Power BI inputs, and browser dashboard
reports/      KPI outputs, analysis tables, validation records, and charts
tests/        data quality, reproducibility, metrics, ingestion, and BI checks
docs/         architecture, ETL, data sources, dictionaries, quality, and runbooks
```

## Documentation

| Document | Purpose |
|---|---|
| [Data architecture](docs/data_architecture.md) | Source, ODS, DWD, DWS, ADS, and Power BI responsibilities |
| [ETL pipeline](docs/etl_pipeline.md) | Extract, transform, load, orchestration, and failure behavior |
| [Data quality](docs/data_quality.md) | Validation rules and their automated test coverage |
| [Data sources](docs/data_source.md) | External/public versus internal/simulated data boundaries |
| [Data dictionary](docs/data_dictionary.md) | Entity fields, types, and meanings |
| [Business metrics](docs/business_metrics.md) | KPI definitions, formulas, and business significance |
| [Metric dictionary](docs/metric_dictionary.md) | Inclusion rules, scores, and RFM logic |
| [Operations runbook](docs/runbook.md) | Operational execution guidance |
| [Release checklist](docs/release_checklist.md) | GitHub publication readiness and verification status |

## Limitations

- The committed Power BI baseline uses fixed-seed generated data; it does not represent actual marketplace or store performance.
- External product input is a capability, not a bundled claim of market coverage. Dataset licenses, currencies, collection dates, and category mappings must be reviewed before use.
- Users, orders, and advertising remain simulated because sensitive enterprise records are not distributed.
- Advertising revenue is attributed revenue, not causal incrementality. ROAS does not represent profit.
- Hot Score and Opportunity Score are sample-relative screening tools, not proof of demand or low competition.
- The default executable database is SQLite. MySQL 8 assets are included, but a live MySQL service is not required or automatically modified.
- Refreshing PBIP on another machine requires setting the `DataRoot` Power Query parameter. The distributable PBIX embeds its validated data.
- The pipeline is designed for local analytical workloads and does not claim distributed processing, real-time ingestion, or production orchestration.

## Roadmap

- Add a terms-approved, license-compatible public product dataset profile without redistributing restricted data.
- Add seller-authorized export adapters and configurable field mappings.
- Extend the model with inventory, returns, and fulfillment data.
- Add score sensitivity analysis and causal promotion experiment templates.
- Add continuous integration and an optional hosted demonstration environment.

## License

This project is licensed under the [MIT License](LICENSE).
