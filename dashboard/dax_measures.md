# Core DAX measures

The model uses `calendar[date]` → `orders[order_date]` and `calendar[date]` → `ads[date]` (1:*), plus `products[product_id]` → `orders[product_id]` and `users[user_id]` → `orders[user_id]`. Cross-filter direction is single, dimension to fact.

```DAX
GMV := CALCULATE(SUM(orders[gross_amount]), orders[status] IN {"completed", "refunded"})
Net Sales := CALCULATE(SUM(orders[net_sales]), orders[status] = "completed")
Completed Orders := CALCULATE(DISTINCTCOUNT(orders[order_id]), orders[status] = "completed")
Gross Profit := [Net Sales] - CALCULATE(SUM(orders[cost]), orders[status] = "completed")
Gross Margin % := DIVIDE([Gross Profit], [Net Sales])
AOV := DIVIDE([Net Sales], [Completed Orders])
Purchasing Users := CALCULATE(DISTINCTCOUNT(orders[user_id]), orders[status] = "completed")
Repeat Users := COUNTROWS(FILTER(VALUES(orders[user_id]), CALCULATE(DISTINCTCOUNT(orders[order_id]), orders[status] = "completed") >= 2))
Repeat Rate % := DIVIDE([Repeat Users], [Purchasing Users])
Impressions := SUM(ads[impressions])
Clicks := SUM(ads[clicks])
Ad Spend := SUM(ads[spend])
Conversions := SUM(ads[conversions])
Attributed Revenue := SUM(ads[attributed_revenue])
CTR % := DIVIDE([Clicks], [Impressions])
CVR % := DIVIDE([Conversions], [Clicks])
CPC := DIVIDE([Ad Spend], [Clicks])
CPA := DIVIDE([Ad Spend], [Conversions])
ROAS := DIVIDE([Attributed Revenue], [Ad Spend])
Net Sales PM := CALCULATE([Net Sales], DATEADD(calendar[date], -1, MONTH))
Net Sales MoM % := DIVIDE([Net Sales] - [Net Sales PM], [Net Sales PM])
```

