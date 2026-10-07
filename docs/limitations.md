# Limitations and Non-Inferences

## Olist Real Data

1. The Brazilian E-Commerce Public Dataset by Olist is historical public marketplace data. It is not a live company database and should not be presented as current operating performance.
2. Sales and customer metrics use original orders with `order_status = 'delivered'`. This is a documented analytics scope, not a new source status.
3. Merchandise GMV is delivered item price. Paid Value is delivered payment value. Neither should be renamed as audited revenue or net sales.
4. Olist does not provide reliable product cost, advertising spend, impressions, clicks, attributed revenue, or confirmed refund outcomes. Gross Profit, Margin, CTR, CVR, CPA, and ROAS are therefore unavailable in Real Data mode.
5. Reviews are recorded at order level. A category review can be attributed through an order-category relationship, but it cannot prove which item, seller, freight amount, or delivery event caused a score.
6. Geolocation contains duplicate observations and nonunique postal-code prefixes. It must be aggregated or matched under an explicit rule before geography analysis.
7. The first and last purchase months are partial. September 2016 and September/October 2018 should not be used for naive period-over-period comparisons.
8. RFM segments are deterministic descriptive rules for this snapshot. They are not causal predictions or machine learning outputs.
9. The Olist Analytics layer and Power BI-ready CSVs are complete, but the Olist PBIX and screenshots require manual Power BI Desktop work.

## Legacy Synthetic Prototype

1. Synthetic V1.1/V1.2 contains fixed-seed product, customer, order, advertising, cost, and TWD data. It demonstrates the earlier pipeline and must not be presented as real Olist or enterprise operating data.
2. Legacy Hot Score, Opportunity Score, profit, margin, and advertising KPIs belong only to the Synthetic workflow.
3. The existing validated V1.1/V1.2 PBIX, PBIP, PBIR, TMDL, and screenshots are legacy artifacts. They are retained for engineering history and regression tests; they are not the Olist dashboard.
