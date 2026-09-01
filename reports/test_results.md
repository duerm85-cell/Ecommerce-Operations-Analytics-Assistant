# V1.0 verification record

Execution date: 2026-09-01 (Asia/Shanghai host). Data business calendar: 2025, Asia/Taipei.

## Environment observed

- Bundled Python 3.12.13: available.
- pandas, NumPy and Pillow: import verified.
- MySQL 8.0.33 binaries and Windows service: available; service running.
- MySQL schema execution: **not run** because local root authentication requires a password that was not provided. No password was guessed and no account/configuration was changed.
- Docker: not found.
- Power BI Desktop executable: not found/reliably invokable; PBIX not generated.

## Pipeline execution

`python run_pipeline.py` completed successfully and generated 800 products, 12,000 users, 60,000 orders, 2,190 ad rows and 365 calendar rows.

Python KPIs: GMV NT$39,295,789.00; net sales NT$35,169,616.30; completed orders 55,890; gross profit NT$14,339,912.83; gross margin 40.7736%; AOV NT$629.26; buyers 11,381; repeat rate 89.6143%; CTR 3.2688%; CVR 7.6213%; CPA NT$93.06; ROAS 7.9159×.

SQLite SQL independently reconciled GMV, net sales, completed orders, gross profit, CTR, CVR and ROAS to the Python values (floating tolerance 1e-9; monetary absolute tolerance NT$0.02).

## Automated tests

Twelve unittest cases passed. Coverage includes minimum scale; primary-key uniqueness; required fields; status-specific completed/refunded/cancelled amount equations; product/ad bounds; foreign keys; date/currency/status contracts; independent Hot and Opportunity Score recomputation; MySQL timestamp normalization; two-directory fixed-seed hash equality; portable Dashboard/RFM inputs; and SQLite/Python/dashboard KPI parity.

Result: `Ran 12 tests ... OK`.

## Visual verification

All four 1440×810 PNG previews were opened at original resolution. Titles, KPI cards, units, chart labels, insights and source/time footers were legible with no overlap or clipping. The HTML preview was opened in headless Microsoft Edge: four pages rendered, four filters changed KPI cards, all chart containers were non-empty and no page errors were emitted.

## Clean reconstruction

The committed baseline was exported into an isolated temporary directory, dependencies were installed into a new virtual environment, and `python run_pipeline.py` completed without access to the main workspace's ignored files. A second run produced identical SHA-256 hashes for all five generated source CSVs and `kpi_summary.json`. After audit repairs, a second ignored-file-free candidate copy was also rebuilt and tested successfully; details are in `pre_release_audit.md`.
