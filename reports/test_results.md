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

Six unittest cases passed:

1. Minimum dataset scale.
2. Product, user, order and advertising-grain primary-key uniqueness.
3. Required-field completeness.
4. Price/rating/quantity/ad funnel bounds and order amount equations.
5. Orders-to-users and orders-to-products foreign-key coverage.
6. SQLite/Python/dashboard KPI parity for net sales and ROAS.

Result: `Ran 6 tests ... OK`.

## Visual verification

All four 1440×810 PNG previews were opened at original resolution. Titles, KPI cards, units, chart labels, insights and source/time footers were legible with no overlap or clipping. The HTML preview was generated and its embedded data/filter logic was inspected; native browser clicking was not automated in this environment.

