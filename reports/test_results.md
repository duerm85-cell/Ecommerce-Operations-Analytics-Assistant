# V1.1 verification record

Execution date: 2026-09-05 (Asia/Shanghai host). Business calendar: FY2025, Asia/Taipei. All business data is synthetic.

## Environment observed

- Bundled Python 3.12: available; pandas, NumPy and Pillow imports passed.
- Power BI Desktop 2.157.879.0: installed and launched successfully.
- MySQL 8 binaries/service: present, but live schema execution was not attempted because the available root account requires an unknown password. No credential was guessed and no service/account/configuration was changed.
- SQLite: end-to-end executable validation passed.

## End-to-end pipeline

The exact project entry point was run with the available Python executable:

```powershell
python run_pipeline.py
```

It regenerated 800 products, 12,000 users, 60,000 orders, 2,190 ad rows and 365 calendar rows; rebuilt analysis/SQLite/dashboard outputs; and completed the test discovery step.

Core results: GMV TWD 39,295,789.00; Net Sales TWD 35,169,616.30; 55,890 completed orders; Gross Profit TWD 14,339,912.83; Gross Margin 40.7736%; AOV TWD 629.26; 11,381 purchasing users; Repeat Rate 89.6143%; CTR 3.2688%; CVR 7.6213%; CPA TWD 93.06; ROAS 7.9159×.

SQLite independently reconciled GMV, Net Sales, Completed Orders, Gross Profit, CTR, CVR and ROAS to the Python results. The reopened PBIX independently reconciled 12 headline KPIs; see `powerbi_validation.md`.

## Automated tests

Result:

```text
Ran 16 tests in 1.162s
OK
```

Coverage includes:

- minimum scale, primary-key uniqueness, required fields, date/currency/status contracts and foreign keys;
- completed/refunded/cancelled amount equations and advertising count inequalities;
- independent Hot Score and Opportunity Score recomputation;
- two-directory fixed-seed hash equality;
- MySQL timestamp normalization and SQLite/Python/dashboard metric parity;
- portable interactive HTML inputs;
- genuine PBIP/PBIX entry files, four 1440×810 PBIR pages, 44 valid visual definitions, 37 TMDL measures, four relationships, portable `DataRoot`, and four 1440×810 Desktop screenshots.

The final run used a new project-local `.venv` populated directly from `requirements.txt`; `pip check` reported no broken requirements. The first sandboxed run passed all data tests but could not read Desktop-generated Power BI files because their Windows ACL excludes the Codex sandbox identity. Re-running the same command with normal desktop permissions passed all 16 tests. A regular local clone does not inherit this host-only ACL artifact.

## Power BI verification

- PBIX reopened successfully in a new Desktop process.
- Four page tabs and populated KPI cards were detected.
- Category slicer interaction visibly changed connected KPIs/charts.
- Read-only ADOMD returned 37 measures and matched every recorded KPI.
- Power BI's bundled TMDL serializer parsed the checked-in model: 6 tables, 4 relationships, 1 shared `DataRoot` parameter and 37 measures.

## Clean reconstruction baseline

The earlier release audit exported the committed baseline into an isolated temporary directory, installed dependencies into a fresh environment and rebuilt it without ignored workspace files. V1.1 retains that deterministic pipeline and adds committed PBIP/PBIX assets plus structural tests. Full audit history is in `pre_release_audit.md`.
