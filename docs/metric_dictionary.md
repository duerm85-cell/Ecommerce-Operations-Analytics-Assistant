# Metric dictionary

| Metric | Formula | Inclusion rule |
|---|---|---|
| GMV | Sum gross_amount | Completed + refunded orders; excludes cancelled |
| Net sales | Sum net_sales | Completed orders only, after discount |
| Orders | Distinct order_id | Completed orders only unless labelled otherwise |
| Gross profit | Net sales − cost | Completed orders only |
| Gross margin | Gross profit / Net sales | Blank/zero when net sales is zero |
| AOV | Net sales / completed orders | TWD per completed order |
| Users | Distinct purchasing user_id | Completed orders in filter context |
| Repeat rate | Users with ≥2 completed orders / purchasing users | Fixed analysis window, 2025-01-01 to 2025-12-31 |
| CTR | Clicks / impressions | Weighted ratio, never average of daily CTRs |
| CVR | Conversions / clicks | Weighted ratio |
| CPC | Spend / clicks | TWD per click |
| CPA | Spend / conversions | TWD per attributed conversion |
| ROAS | Attributed revenue / spend | Revenue multiple, not profit or incrementality |

## Portfolio scores

**Hot Score** = 100 × (50% normalized log-sales + 20% normalized rating + 30% normalized log-reviews). Min-max normalization is within the complete sample. Log transforms prevent extreme sellers from dominating.

**Opportunity Score** = 100 × (65% demand + 35% inverse competition). Demand combines log-sales (65%) and log-reviews (35%). Competition combines category product count (55%) and category/price-band density (45%). It is a screening hypothesis, not proof of unmet demand; shortlisted products still require margin, supplier and real-market validation.

**RFM** uses completed orders through 2025-12-31. Recency, frequency and monetary values receive quintile scores. Recency is reversed so 5 is most recent. Segments: Champions (R≥4,F≥4), Loyal (F≥4), New & Promising (R≥4,F≤2), At Risk (R≤2,F≥3), Hibernating (R≤2,F≤2), Potential Loyalists (all others).

