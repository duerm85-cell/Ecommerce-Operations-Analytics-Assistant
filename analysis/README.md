# Analysis outputs

`run_analysis.py` implements the four required themes in one reproducible script:

- Product: category contribution, product net sales/units/margin, Hot Score and Opportunity Score.
- Sales: monthly net sales, completed orders, buyers, profit, AOV and MoM.
- Customer: fixed-window repeat rate and quintile RFM segmentation.
- Advertising: weighted CTR/CVR, CPC, CPA and ROAS by campaign.

The script creates a credential-free SQLite database, computes pandas results, exports analysis tables and dashboard PNGs, writes business insights, and reconciles seven KPIs between SQL and Python. Analysis tables in `reports/` are generated evidence; the source of truth remains the fixed-seed generator and metric dictionary.

