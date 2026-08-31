# Local runbook

## Prerequisites

- Python 3.10+ with packages in `requirements.txt`
- Optional MySQL 8 for database-specific execution
- Optional Power BI Desktop for the genuine PBIX build

## Clean execution

From the repository root, run `python run_pipeline.py`. The command is idempotent: generated CSV, SQLite, reports, screenshots and HTML are rebuilt from seed `20260801`. It does not contact any website or external account.

Full CSVs live in `data/processed` and `dashboard/powerbi_data`; both are Git-ignored. Tracked 50-row samples allow reviewers to inspect contracts without committing large files. The generated SQLite file is also ignored.

## Failure recovery

- Missing Python package: install `requirements.txt`, then rerun.
- MySQL access denied: create a least-privilege local database user; do not place a password in a command committed to history.
- Power BI unavailable: review the browser preview and build guide; do not fabricate a PBIX.
- Collector blocked by terms/robots/access control: stop. Keep the synthetic workflow and document the limitation.

