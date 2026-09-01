# Independent pre-release audit

Audit date: 2026-09-01. Scope: local GitHub release readiness; no remote configuration, push or publication.

## Findings and disposition

### High priority — fixed

- Power BI user input did not contain the RFM fields required by the documented Customer page. The analysis stage now enriches `dashboard/powerbi_data/users.csv` with RFM values and segments; a test verifies one-to-one coverage.
- MySQL `DATETIME` import could receive an ISO timestamp with a `+08:00` suffix. The importer now parses it strictly, converts to Asia/Taipei wall time and emits a MySQL-safe timezone-naive value.

### Medium priority — fixed

- The original overview preview silently showed only January–June. It now renders all twelve months and states the period and unit in the subtitle.
- Product and Customer HTML pages lacked working page-level filters. Product category and user region filters were added and validated in Edge alongside Overview category and Advertising channel filters.
- Tests did not fully enforce refund/cancellation equations, score formulas, date/currency contracts or deterministic generation. The suite was expanded from 6 to 12 cases without weakening existing assertions.
- Python ad ratios used direct division. Zero-denominator handling now produces a safe undefined result in analysis and zero display state in the browser; SQL and DAX already used `NULLIF`/`DIVIDE`.
- The repository tracked a 601 KB user-level RFM detail export that was unnecessary for public review. It was removed; the locally generated Power BI user dimension retains the required RFM fields and remains reproducible.
- Annual repeat-rate DAX could change its observation window under a date slicer. The FY2025 measures now explicitly remove the current calendar filter and apply the documented fixed window.

### Low priority — accepted limitation

- MySQL 8 service is present, but the available root account requires an unknown password. No credential, account or existing database was modified. DDL/query compatibility received static review and importer transformations were tested, but a real MySQL schema/load/query run remains manual.
- Power BI Desktop is unavailable. No PBIX was fabricated; the verified substitute remains CSV inputs, model documentation, DAX, screenshots, build instructions and the browser dashboard.
- Synthetic repeat rate is high because 60,000 orders are distributed across 12,000 users with heterogeneous repeat propensity. It is correctly calculated and prominently labeled as synthetic, but is not a market benchmark.

## Evidence

- Fresh virtual environment dependency installation: passed.
- Ignored-file-free clean pipeline reconstruction: passed.
- Repeated data build SHA-256 equality: passed for products, users, orders, ads, calendar and KPI summary.
- Independent KPI calculation: matched GMV, net sales, order count, gross profit/margin, AOV, repeat rate, CTR, CVR, CPC, CPA and ROAS.
- Automated suite: 12/12 passed.
- Headless Edge dashboard audit: four pages, four effective filters, zero empty charts, zero page errors.
- Markdown links and case-sensitive paths: passed.
- Secret, foreign-project, absolute-path, cache, empty-file and tracked-large-file scans: passed after fixes.
