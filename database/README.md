# Database run guide

The SQL targets MySQL 8.0 and uses CTEs, window functions, checks and foreign keys. Create tables with `mysql -u <user> -p < database/schema.sql`, apply indexes, then either enable `LOCAL INFILE` and adapt `load_data.sql`, or use `python database/import_mysql.py` with `.env` values exported into the shell.

V1.0 also builds `data/analytics.sqlite` as a credential-free validation substitute. SQLite validates row counts, relationships and metric reconciliation; it does not prove MySQL-specific DDL execution. MySQL verification status is recorded in `reports/test_results.md`.

