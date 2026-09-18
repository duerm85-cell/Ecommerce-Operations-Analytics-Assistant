# Limitations and non-inferences

1. All product, shop, customer, order and advertising rows are synthetic. The project demonstrates method, not current Shopee Taiwan market truth.
2. Hot Score and Opportunity Score are transparent heuristic rankings whose weights encode business assumptions. They require weight sensitivity and real-world validation before use.
3. Repeat rate is fixed-window and naturally rises with order opportunities; compare cohorts with equal observation windows in production.
4. Advertising revenue is attributed revenue. ROAS does not measure incrementality, profit, saturation or cross-channel cannibalization.
5. Orders are one product per row in V1.0. A production model should separate order header and order line to support baskets and fulfillment.
6. Inventory, stockouts, shipping cost, platform fee, taxes and customer service cost are excluded; gross profit is therefore simplified.
7. The repository includes validated V1.1 and V1.2 PBIX files together with version-controlled PBIP/PBIR/TMDL sources. The PBIP refresh path requires setting the shared `DataRoot` parameter on a new machine, while the committed PBIX contains the validated snapshot. Native Power BI page rendering, filter interaction and headline KPI reconciliation were validated locally; Power BI Service publication and scheduled refresh are outside this repository's scope.
