# Olist Business Insights

These findings are calculated from the validated Olist analytics marts. Sales metrics use delivered orders, customers use `customer_unique_id`, and monetary values are BRL. The dataset is observational and historical; possible explanations are hypotheses, not causal conclusions.

## 1. Repeat purchasing is uncommon in this snapshot

**Finding:** Only 3.00% of purchasing customers placed at least two delivered orders.

**Evidence:** The dataset contains 93,358 purchasing customers and 2,801 repeat customers. A total of 90,557 customers, or 97.00%, have exactly one delivered order.

**Interpretation:** Most observed customer relationships are one-time purchases within the available history. The result may reflect marketplace shopping behavior, the observation window, or customer identity limitations outside the dataset.

**Possible action:** Prioritize first-to-second-purchase analysis and evaluate retention separately by acquisition cohort and category before designing repeat-purchase initiatives.

## 2. Customer recency segments contain most of the customer base

**Finding:** Hibernating and New Customers together represent 77.95% of purchasing customers under the documented RFM rules.

**Evidence:** Hibernating contains 36,650 customers (39.26%) and New Customers contains 36,118 (38.69%).

**Interpretation:** The customer base is concentrated at the two ends of recency while frequency remains low. Segment sizes depend on the deterministic RFM thresholds and should be treated as descriptive groupings.

**Possible action:** Use separate messaging and measurement for recently acquired one-time customers and older inactive one-time customers; do not treat both groups as the same retention problem.

## 3. Health and beauty is the largest merchandise category

**Finding:** `health_beauty` has the highest delivered Merchandise GMV.

**Evidence:** It generates BRL 1,233,131.72 from 8,647 delivered orders and 9,465 item records, equal to 9.33% of total Merchandise GMV. Its average review score is 4.23 and low-rating rate is 11.43%.

**Interpretation:** The category combines material revenue contribution with comparatively strong review outcomes in this dataset.

**Possible action:** Treat it as a priority category for assortment availability and seller-quality monitoring while checking whether its performance is concentrated among a small number of products or sellers.

## 4. Office furniture combines rating and freight risk signals

**Finding:** Among categories with at least 1,000 delivered orders, `office_furniture` has the highest low-rating rate.

**Evidence:** It has 1,254 orders, BRL 268,154.31 Merchandise GMV, a 3.64 average review score, a 22.02% low-rating rate, and a 25.01% freight ratio.

**Interpretation:** Lower ratings and higher freight burden occur together in this category. The data does not prove that freight or delivery caused the ratings because reviews are recorded at order level.

**Possible action:** Investigate seller, product, delivery-time, damage, and freight patterns within the category before selecting a remedy.

## 5. Freight burden varies materially across established categories

**Finding:** `electronics` has the highest freight ratio among categories with at least 500 delivered orders.

**Evidence:** Freight equals 29.46% of Merchandise GMV across 2,517 orders. `office_furniture` follows at 25.01%, while `furniture_decor` is 23.65%.

**Interpretation:** Categories with relatively low item value or heavier shipping requirements may carry a larger freight burden, but the category mart alone cannot identify the operational cause.

**Possible action:** Review freight ratio together with item price, product dimensions, seller location, and delivery distance when prioritizing logistics analysis.

## 6. November 2017 is the highest delivered-GMV month

**Finding:** The highest monthly Merchandise GMV occurs in 2017-11.

**Evidence:** November 2017 records 7,289 delivered orders and BRL 987,765.37 Merchandise GMV. Paid Value is BRL 1,153,528.05 and the average review score is 3.99.

**Interpretation:** The month shows the strongest delivered merchandise value in the observed period. The dataset does not contain campaign or traffic data that could explain the peak.

**Possible action:** Compare category mix, item prices, seller participation, and customer cohorts for this month with adjacent months; avoid attributing the peak to promotions without supporting data.

## 7. Merchandise GMV and Paid Value must remain separate

**Finding:** Delivered Paid Value exceeds delivered Merchandise GMV by BRL 2,200,963.66.

**Evidence:** Merchandise GMV is BRL 13,221,498.11, Paid Value is BRL 15,422,461.77, and freight value is BRL 2,198,275.64. Paid Value exceeds Merchandise GMV plus freight by a remaining BRL 2,688.02.

**Interpretation:** Payment totals and item-price totals represent different business concepts. Freight explains nearly all of the difference at aggregate level, while payment adjustments and source behavior can account for the small remainder.

**Possible action:** Present both measures with explicit labels and reconcile them at order level rather than renaming Paid Value as GMV or revenue.

## Data Boundary Note

The first and last observed purchase months are partial. September 2016 contains four placed orders, while September and October 2018 contain only 16 and 4 placed orders and no delivered orders in the current sales scope. These boundary months should be excluded from period-over-period trend conclusions unless partial-period treatment is explicit.
