# GitHub Release Checklist

This checklist records the repository's publication readiness as an open-source ecommerce operations analytics project.

## Required release items

- [x] **README complete:** project overview, features, architecture, data sources, data model, metrics, dashboard, quick start, pipeline, testing, repository structure, documentation, limitations, and license are present.
- [x] **LICENSE complete:** the repository includes the standard MIT License with the current year and a generic contributor attribution.
- [x] **Documentation complete:** data architecture, ETL, data quality, data sources, data dictionary, business metrics, operational guidance, and Power BI validation are documented.
- [x] **Pipeline runnable:** `run_pipeline.py` completes the local data generation, analysis, dashboard build, and quality-gate sequence without requiring external database credentials.
- [x] **Tests pass:** the latest full validation completed 19 of 19 automated tests successfully.
- [x] **Data description complete:** external public product data and internal simulated business data are clearly separated, with privacy, licensing, currency, and fallback boundaries documented.
- [x] **Dashboard display ready:** four clean Power BI screenshots, the validated V1.2 PBIX, the preserved V1.1 PBIX, and version-controlled PBIP/PBIR/TMDL sources are available.

## Repository hygiene

- [x] Required paths exist: `README.md`, `LICENSE`, `docs/`, `data/`, `analysis/`, `dashboard/`, and `tests/`.
- [x] `.gitignore` covers virtual environments, Python caches, test caches, logs, local data outputs, Power BI local state, autosave files, and coverage outputs.
- [x] README contains no interview, resume, recruitment, job-search, or personal-contribution positioning.
- [x] Local Markdown links resolve.
- [x] Python source files pass syntax parsing.
- [x] No business logic, SQL, DAX, Power BI artifact, or baseline data result was changed during final release packaging.

## Publication steps requiring maintainer action

- [ ] Review the complete Git diff and confirm that all staged files are intended for release.
- [ ] Create a local release commit with a clear conventional commit message.
- [ ] Push the release branch to GitHub.
- [ ] Open and review a pull request before merging to the default branch.
- [ ] Confirm the GitHub repository description, topics, and About links match the README positioning.
- [ ] Optionally create a tagged release only after the merged commit has been verified.

## Latest verification record

- Branch at packaging time: `design/powerbi-v1.2`
- Pipeline: passed on 2026-09-07
- Automated tests: 19/19 passed
- Markdown validation: local links and structure passed
- Power BI baseline: V1.1 and V1.2 PBIX hashes unchanged during the engineering upgrades
- Release actions: no commit, push, pull request, tag, or GitHub Release performed by this checklist
