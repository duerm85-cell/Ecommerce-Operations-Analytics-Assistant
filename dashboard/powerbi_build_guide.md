# Power BI build guide

PBIX status: not generated. The inspected environment does not expose Power BI Desktop, so creating or validating a genuine PBIX is not reliable. The repository instead delivers complete import CSVs, relationships, DAX, layouts, screenshots and a browser preview.

1. Run `python run_pipeline.py` to regenerate `dashboard/powerbi_data/*.csv`.
2. In Power BI Desktop choose **Get data → Text/CSV** and import products, users, orders, ads and calendar.
3. Assign Date type to calendar/date, orders/order_date and ads/date; decimal/currency to monetary fields; whole number to counts.
4. Create the four 1:* relationships described in `dax_measures.md`. Disable automatic date/time and use only the calendar table for time filtering.
5. Create a display table named `Measures`, add every measure from `dax_measures.md`, and format money as `NT$ #,0`; percentages as `0.0%` or `0.00%`; ROAS as `0.00x`.
6. Build the pages below at 16:9 (1440×810 reference). Use blue for regular metrics, green for positive results, red for risks and light gray for the canvas.

## Page specifications

- **01 Operations overview** — KPI cards: GMV, Net Sales, Completed Orders, Gross Profit, AOV, Repeat Rate. Monthly combo chart for Net Sales and Gross Margin. Category contribution bar chart. Slicers: date, category, region, acquisition channel. Insight box: growth must be interpreted with profit.
- **02 Product analysis** — cards for products, top-20 share, average margin and high-opportunity count. Top-product bar, units-vs-margin scatter, price-band distribution and high-volume/low-margin table. Slicers: category, product, price band.
- **03 Customer analysis** — cards for buyers, repeat rate, Champions and At Risk. RFM segment bars, region/channel mix, new-vs-repeat trend. Slicers: RFM segment, acquisition channel, date.
- **04 Advertising analysis** — cards for Spend, CTR, CVR, CPA and ROAS. Campaign ROAS bars, spend-vs-ROAS scatter and inefficient-campaign table. Slicers: date, channel, campaign.

After building, reconcile the unfiltered card values with `reports/kpi_summary.json`, then test that each slicer changes only visuals connected through intended relationships. Do not publish until all cards reconcile.

