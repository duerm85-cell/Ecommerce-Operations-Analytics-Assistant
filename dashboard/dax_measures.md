# Power BI model and DAX measures

The V1.1 semantic model has six tables, four active one-to-many relationships and 37 explicit measures. Relationships filter in one direction from dimensions to facts:

- `calendar[date]` → `orders[order_date]`
- `calendar[date]` → `ads[date]`
- `products[product_id]` → `orders[product_id]`
- `users[user_id]` → `orders[user_id]`

The product `price_band` and user `customer_type` fields are created in Power Query. All measures below live in the dedicated `KPI Measures` table.

```DAX
GMV :=
CALCULATE(SUM(orders[gross_amount]), orders[status] IN {"completed", "refunded"})

Net Sales :=
CALCULATE(SUM(orders[net_sales]), orders[status] = "completed")

Completed Orders :=
CALCULATE(DISTINCTCOUNT(orders[order_id]), orders[status] = "completed")

Gross Profit :=
[Net Sales] - CALCULATE(SUM(orders[cost]), orders[status] = "completed")

Gross Margin % := DIVIDE([Gross Profit], [Net Sales])
AOV := DIVIDE([Net Sales], [Completed Orders])

Purchasing Users :=
CALCULATE(DISTINCTCOUNT(orders[user_id]), orders[status] = "completed")

Registered Users := DISTINCTCOUNT(users[user_id])

Purchasing Users FY2025 :=
CALCULATE(
    [Purchasing Users],
    REMOVEFILTERS(calendar),
    DATESBETWEEN(calendar[date], DATE(2025, 1, 1), DATE(2025, 12, 31))
)

Repeat Users FY2025 :=
COUNTROWS(
    FILTER(
        CALCULATETABLE(
            VALUES(orders[user_id]),
            REMOVEFILTERS(calendar),
            DATESBETWEEN(calendar[date], DATE(2025, 1, 1), DATE(2025, 12, 31)),
            orders[status] = "completed"
        ),
        CALCULATE(
            DISTINCTCOUNT(orders[order_id]),
            REMOVEFILTERS(calendar),
            DATESBETWEEN(calendar[date], DATE(2025, 1, 1), DATE(2025, 12, 31)),
            orders[status] = "completed"
        ) >= 2
    )
)

Repeat Rate FY2025 % := DIVIDE([Repeat Users FY2025], [Purchasing Users FY2025])

Product Count := DISTINCTCOUNT(products[product_id])
High Opportunity Products :=
CALCULATE(DISTINCTCOUNT(products[product_id]), products[opportunity_score] >= 70)
Units Sold := CALCULATE(SUM(orders[quantity]), orders[status] = "completed")

Average Recency := AVERAGE(users[recency])
Average Frequency := AVERAGE(users[frequency])
Average Monetary := AVERAGE(users[monetary])
New Customers := CALCULATE(DISTINCTCOUNT(users[user_id]), users[customer_type] = "New")
Repeat Customers := CALCULATE(DISTINCTCOUNT(users[user_id]), users[customer_type] = "Repeat")

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

Average Hot Score := AVERAGE(products[hot_score])
Average Opportunity Score := AVERAGE(products[opportunity_score])

Top 10 Product Net Sales :=
VAR ProductRank = RANKX(ALLSELECTED(products[product_name]), [Net Sales],, DESC, DENSE)
RETURN IF(ProductRank <= 10, [Net Sales])

Top 10 Product Gross Profit :=
VAR ProductRank = RANKX(ALLSELECTED(products[product_name]), [Net Sales],, DESC, DENSE)
RETURN IF(ProductRank <= 10, [Gross Profit])

Top 10 Opportunity Score :=
VAR OpportunityRank =
    RANKX(ALLSELECTED(products[product_name]), [Average Opportunity Score],, DESC, DENSE)
RETURN IF(OpportunityRank <= 10, [Average Opportunity Score])

Hot Score for Opportunity Top 10 :=
VAR OpportunityRank =
    RANKX(ALLSELECTED(products[product_name]), [Average Opportunity Score],, DESC, DENSE)
RETURN IF(OpportunityRank <= 10, [Average Hot Score])
```

## Formatting and behavior

- TWD values use `#,0 "TWD"` or `#,0.00 "TWD"`; quoted `TWD` prevents locale-dependent interpretation.
- Percentages use `0.0%` or `0.00%`; ROAS uses `0.00x`.
- `DIVIDE` returns blank for zero denominators instead of raising an error.
- The repeat-rate measures deliberately remove calendar filters and apply one fixed FY2025 window. Product, user and other compatible dimension filters remain active.
- Dense ranking returns all products tied at the tenth rank, so a visual can contain more than ten rows only when the boundary is tied. The validated synthetic data returns ten rows.
- Opportunity Score is precomputed by the Python pipeline: demand contributes positively while modeled competition and price crowding contribute negatively. The DAX measures only aggregate and rank that validated score.
