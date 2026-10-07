# Dashboard Deliverables

## Olist Real Data

- `powerbi_data/olist_*.csv`: generated Analytics mart exports, intentionally Git-ignored.
- [`../docs/olist_powerbi_dashboard_spec.md`](../docs/olist_powerbi_dashboard_spec.md): required two-page Olist report, visual definitions, acceptance criteria, and manual build steps.

The Olist PBIX and screenshots have not yet been created. Existing Power BI files in this directory belong to the Synthetic V1.1/V1.2 legacy prototype and must not be presented as Olist output.

## Legacy Synthetic Prototype

- `powerbi_project/Ecommerce-Operations-Analytics-Assistant-v1.2.pbix`: validated V1.2 executive-storytelling report.
- `powerbi_project/Ecommerce-Operations-Analytics-Assistant-v1.1.pbix`: preserved V1.1 baseline.
- `powerbi_project/Ecommerce-Operations-Analytics-Assistant.pbip` plus `.Report` and `.SemanticModel`: version-controlled PBIP/PBIR/TMDL source.
- `powerbi_project/generate_pbir_report_v1_2.ps1`: deterministic V1.2 report-layout generator.
- `powerbi_theme/executive_storytelling_v1.2.json`: V1.2 native Power BI theme.
- `powerbi_screenshots/v1.2/`: four clean 1440×810 report screenshots.
- `interactive_dashboard.html`: dependency-free browser preview retained for reviewers without Power BI Desktop.
- `powerbi_data/products.csv`, `users.csv`, `orders.csv`, `ads.csv`, and `calendar.csv`: generated legacy CSV imports, intentionally Git-ignored.
- `dax_measures.md` and `powerbi_build_guide.md`: metric and refresh references.

The V1.2 PBIX is a real Power BI package that was generated, saved, reopened, and reconciled during the legacy release. See [`reports/powerbi_design_v1.2.md`](../reports/powerbi_design_v1.2.md) for storytelling decisions, KPI reconciliation, reopen evidence, and known limits.
