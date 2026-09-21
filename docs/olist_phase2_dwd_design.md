# Olist V2.0 Phase 2-A：DWD Data Warehouse Design

> 文档状态：设计评审稿  
> 当前阶段：只做模型分析与架构设计，不实施 DWD 代码  
> 数据模式：Olist Real Mode，与 Synthetic V1.1 保持隔离  
> 设计依据：当前仓库代码、Phase 1 ODS 实现、Olist 数据画像和 V2 架构基线

本文定义 Olist 从 ODS 到 DWD 的星型模型设计。它不创建 DWD 数据库表，不修改 ODS，不修改 Synthetic V1.1、Dashboard、Power BI 或 DAX，也不执行 commit 或 push。

## 1. Executive Summary

当前 V1.1 和 Olist 的数据粒度不同：

- V1.1 的 orders CSV 每行同时包含一个订单、一个 product_id 和 quantity，实际是单商品订单行模型。
- Olist 的 orders 是订单头；order_items、payments、reviews 分别是独立的一对多子事实。
- Olist 的 customer_id 是订单记录/地址级键，customer_unique_id 才是跨记录的人级客户键。
- Olist 货币是 BRL，订单购买时间是 2016–2018 历史窗口。
- Olist 不提供可信商品成本、退款状态或广告事实。

因此，DWD 不能把 Olist 压成 V1.1 的宽 orders 表。推荐的核心模型包含 9 张表：

| 类型 | 表 |
|---|---|
| Dimension | dim_customer、dim_product、dim_seller、dim_date |
| Bridge | bridge_customer_identity |
| Fact | fact_orders、fact_order_items、fact_payments、fact_reviews |

另外，品类翻译和地理聚合可以作为后续的辅助维度或桥接对象，但不改变核心 9 表设计。

核心原则：

1. 一张事实表只有一个明确粒度。
2. 多事实表不能直接互相展开连接。
3. 客户分析必须使用 customer_unique_id。
4. 商品金额、支付金额和评价事实分别聚合。
5. DWD 保留 Olist 原始状态和 BRL 语义，不伪造 cost、refund 或 ad spend。
6. Synthetic 和 Olist 通过 data_mode、source_name、currency_code 和指标可用性隔离。

## 2. Current V1.1 Model Review

本节依据 data/generate_data.py、analysis/run_analysis.py、database/schema.sql、dashboard/build_dashboard.py、Power BI TMDL/DAX 和测试代码，而不是只依据 README。

### 2.1 V1.1 整体数据流

~~~mermaid
flowchart LR
    A[Product baseline or public product attributes] --> B[data/generate_data.py]
    B --> C[products.csv]
    B --> D[users.csv]
    B --> E[orders.csv]
    B --> F[ads.csv]
    B --> G[calendar.csv]
    C --> H[analysis/run_analysis.py]
    D --> H
    E --> H
    F --> H
    G --> H
    H --> I[data/analytics.sqlite]
    H --> J[reports and Power BI CSVs]
    J --> K[Power BI four pages]
~~~

### 2.2 V1.1 表级评估

| 表 | 实际粒度 | 主键 | 外键/关系 | 主要字段 | 当前指标依赖 | Power BI 依赖 |
|---|---|---|---|---|---|---|
| products | 一个商品一行 | product_id | 被 orders.product_id 引用 | product_name、category、price、sold_count、rating、review_count、shop_name、location、crawl_time、source_url、data_source_type、hot_score、opportunity_score | 商品数、销量、价格、Hot Score、Opportunity Score、商品排行 | 商品机会页、Product Count、机会分数、Hot Score |
| users | 一个模拟用户一行 | user_id | 被 orders.user_id 引用 | age_group、region、register_date、acquisition_channel、repeat_propensity、data_source_type | Purchasing Users、Repeat Rate、RFM 输入 | 用户页、地区、渠道、RFM、customer_type |
| orders | 一个合成订单一行，同时带一个商品 | order_id | user_id、product_id、order_date | quantity、unit_price、discount_amount、gross_amount、refund_amount、net_sales、cost、status、currency、data_source_type | GMV、Net Sales、Completed Orders、Profit、Margin、AOV、Repeat Rate | Overview、Product、Customer、DAX 基础度量 |
| ads | 一个日期和广告活动一行 | date + campaign_id | date → calendar.date | impressions、clicks、spend、conversions、attributed_revenue、currency、data_source_type | CTR、CVR、CPC、CPA、ROAS | Advertising Return 页 |
| calendar | 一个日期一行 | date | 被 orders 和 ads 引用 | year、quarter、month、week、weekday、is_weekend、is_promotion | 月度趋势、促销/周末分析 | 日期筛选和时间智能 |

### 2.3 V1.1 的重要实现事实

data/generate_data.py 中，users、orders 和 ads 是固定种子模拟数据。即使 products 使用外部商品属性，sold_count、users、orders 和 ads 仍然是 Synthetic。

orders 的字段由 make_orders 生成：

- order_id
- user_id
- product_id
- order_date
- quantity
- unit_price
- discount_amount
- gross_amount
- refund_amount
- net_sales
- cost
- status
- currency
- data_source_type

order_id 每行唯一，但一个订单行同时包含商品和数量。因此它不能表示 Olist 的一个订单中有多个商品、多个卖家、多个支付或多个评价。

analysis/run_analysis.py 会：

1. 从 data/processed 读取五张 CSV。
2. 写入 data/analytics.sqlite。
3. 计算 GMV、Net Sales、Completed Orders、Gross Profit、Gross Margin、AOV、Purchasing Users、Repeat Rate 和广告 KPI。
4. 生成 monthly、product、category、RFM 和 ads 分析结果。
5. 输出 Power BI users RFM 字段。

### 2.4 V1.1 口径与硬编码限制

V1.1 使用 TWD 和 2025 日期范围。Power BI DAX 中的 Repeat Rate FY2025 和 RFM 逻辑使用固定 FY2025 窗口；Dashboard 文本也显示 Synthetic data、TWD、2025。V1.1 的 Profit、Margin、CTR、CVR、CPA、ROAS 都依赖 Synthetic cost 或 Synthetic ads。

这些依赖必须保留在 Synthetic Mode，不能直接套用到 Olist Real Mode。

## 3. Olist Source Model

### 3.1 Olist 原始表和粒度

| 源文件 | 行数 | 源粒度 | 关键键 |
|---|---:|---|---|
| olist_customers_dataset.csv | 99,441 | 一个客户记录/订单地址记录 | customer_id |
| olist_orders_dataset.csv | 99,441 | 一个订单头 | order_id |
| olist_order_items_dataset.csv | 112,650 | 一个订单商品明细 | order_id + order_item_id |
| olist_order_payments_dataset.csv | 103,886 | 一笔订单支付记录 | order_id + payment_sequential |
| olist_order_reviews_dataset.csv | 99,224 | 一个评价记录 | review_id + order_id |
| olist_products_dataset.csv | 32,951 | 一个商品 | product_id |
| olist_sellers_dataset.csv | 3,095 | 一个卖家 | seller_id |
| olist_geolocation_dataset.csv | 1,000,163 | 一个地理观测行 | 无业务唯一键 |
| product_category_name_translation.csv | 71 | 一个葡萄牙语品类翻译 | product_category_name |

### 3.2 已确认的基数

- 99,441 个 customer_id 对应 96,096 个 customer_unique_id。
- 2,997 个 customer_unique_id 对应多个 customer_id，最大为 17 个 customer record。
- 9,803 个订单包含多个商品明细，最大 21 条。
- 2,961 个订单包含多笔支付，最大 29 条。
- 547 个订单包含多条评价，最大 3 条。
- 订单购买时间为 2016-09-04 21:15:19 至 2018-10-17 17:30:18。
- 金额语境是 BRL，不做汇率转换。
- geolocation 具有约 261,831 条完整重复超额记录，邮编前缀不唯一。
- 品类翻译未覆盖 pc_gamer 和 portateis_cozinha_e_preparadores_de_alimentos。

### 3.3 源状态

实际订单状态是 delivered、shipped、canceled、unavailable、invoiced、processing、approved、created。

Olist 没有可靠的 refunded 状态，也没有广告成本和商品成本字段。

## 4. DWD Design Principles

### 4.1 保持业务粒度

DWD 允许解析时间、标准化列名、补充外键和质量标记，但不改变源事实的粒度。订单商品不能并入订单头，支付不能并入订单商品，评价不能并入订单头宽表。

### 4.2 事实和维度分离

- Dimension 保存相对稳定的描述属性。
- Fact 保存可计数、可加总或可追溯的业务事件。
- Bridge 解决一个业务键对应多个记录键的身份关系。

### 4.3 多事实防重复

商品金额、支付金额和评价数量必须分别在自己的事实表中聚合到 order_id，再与订单级结果关联。禁止直接将四张事实表展开连接后再 SUM price 或 payment_value，因为这会把一对多行数相乘。

### 4.4 来源可追溯

DWD 每张表建议保留 source_system、source_file、source_record_key、load_batch_id、data_mode 和 currency_code。原始业务字段仍然保留，派生字段与来源字段要区分命名。

### 4.5 时间和币种

Olist DWD 使用真实 2016–2018 日期和 BRL。不要引入 FY2025，不要将日期平移到 2025/2026，不要将 BRL 转成 TWD 或 USD。

## 5. Dimension Design

核心 Dimension 为 4 张表。每张表的业务粒度只有一个。

### 5.1 dim_customer

粒度：ONE ROW PER CUSTOMER，即一个 customer_unique_id 一行。

| 字段 | 来源 | 类型/规则 | 用途 |
|---|---|---|---|
| customer_unique_id | ods_olist_customers | PK，非空 | 人级客户主键 |
| preferred_customer_state | customers 聚合 | 确定性选择或主地址规则 | 客户州分析 |
| preferred_customer_city | customers 聚合 | 确定性选择或主地址规则 | 客户城市分析 |
| customer_record_count | customers 聚合 | count distinct customer_id | 识别地址/记录数量 |
| first_order_date | orders 聚合 | 最早有效购买日期 | 生命周期起点 |
| last_order_date | orders 聚合 | 最晚有效购买日期 | RFM Recency 输入 |
| delivered_order_count | orders 聚合 | distinct delivered order_id | 频次输入 |
| customer_status | DWD 规则 | active/one_time/repeat 等派生标签 | 客户分层 |
| geography_match_status | customers + geography | matched/unmatched | 地理质量标记 |
| data_mode | 运行元数据 | 固定为 olist_real | 双模式隔离 |

dim_customer 不保存单个订单地址的全部变化。具体 customer_id 与地址记录放在 bridge_customer_identity。

### 5.2 dim_product

粒度：一个 product_id 一行。

| 字段 | 来源 | 类型/规则 | 用途 |
|---|---|---|---|
| product_id | ods_olist_products | PK | 商品关联 |
| category_pt | products.product_category_name | 原始葡萄牙语值 | 稳定汇总键 |
| category_en | translation | 左连接；未匹配为空或原文别名 | 展示名称 |
| category_translation_status | DWD 规则 | translated/untranslated/missing | 翻译覆盖率 |
| product_name_length | products.product_name_lenght | 原始属性 | 商品质量分析 |
| product_description_length | products.product_description_lenght | 原始属性 | 商品内容分析 |
| product_photos_qty | products.product_photos_qty | 原始属性 | 商品内容分析 |
| product_weight_g | products.product_weight_g | 原始属性，可空 | 物流属性 |
| product_length_cm | products.product_length_cm | 原始属性，可空 | 物流属性 |
| product_height_cm | products.product_height_cm | 原始属性，可空 | 物流属性 |
| product_width_cm | products.product_width_cm | 原始属性，可空 | 物流属性 |
| data_mode | 运行元数据 | 固定为 olist_real | 双模式隔离 |

dim_product 不直接存放订单数量、GMV 或评分汇总。那些是事实聚合结果，避免维度随查询窗口变化。

### 5.3 dim_seller

粒度：一个 seller_id 一行。

| 字段 | 来源 | 类型/规则 | 用途 |
|---|---|---|---|
| seller_id | ods_olist_sellers | PK | 订单商品卖家关联 |
| seller_zip_code_prefix | sellers | 原始邮编前缀 | 地理关联 |
| seller_city | sellers | 原始城市 | 卖家地域 |
| seller_state | sellers | 原始州 | 卖家地域 |
| geography_match_status | sellers + geography | matched/unmatched | 地理质量标记 |
| data_mode | 运行元数据 | 固定为 olist_real | 双模式隔离 |

dim_seller 支持卖家数量、卖家地域、商品卖家覆盖和卖家集中度分析，但不把卖家收入预先写入维度。

### 5.4 dim_date

粒度：一个自然日期一行。

| 字段 | 来源/生成 | 规则 |
|---|---|---|
| date_key | 生成 | YYYYMMDD 整数主键 |
| calendar_date | 生成 | 实际日期 |
| year | 生成 | 2016–2018 及所需履约日期范围 |
| quarter | 生成 | Q1–Q4 |
| month | 生成 | YYYY-MM |
| month_number | 生成 | 1–12 |
| week | 生成 | ISO week |
| weekday | 生成 | 星期名称或编号 |
| is_weekend | 生成 | 周六/周日标记 |
| data_mode | 运行元数据 | olist_real |

日期范围由实际 Olist 日期动态确定。不要使用 FY2025。订单购买、批准、承运、送达和预计送达可以使用不同的日期外键角色。

## 6. Fact Design

核心 Fact 为 4 张表。

### 6.1 fact_orders

粒度：ONE ROW PER ORDER。主键：order_id。

| 字段 | 来源 | 规则 |
|---|---|---|
| order_id | ods_olist_orders.order_id | PK |
| customer_id | ods_olist_orders.customer_id | FK → bridge_customer_identity.customer_id |
| customer_unique_id | customer bridge 解析 | FK → dim_customer.customer_unique_id |
| order_status | ods_olist_orders.order_status | 保留原始状态 |
| realization_status | DWD 规则 | delivered → realized，其余按状态分类 |
| purchase_timestamp | ods_olist_orders | 原始购买时间 |
| approved_at | ods_olist_orders | 可空 |
| delivered_carrier_at | ods_olist_orders | 可空 |
| delivered_customer_at | ods_olist_orders | 可空 |
| estimated_delivery_at | ods_olist_orders | 原始预计时间 |
| purchase_date_key | purchase_timestamp 派生 | FK → dim_date.date_key |
| delivered_date_key | delivered_customer_at 派生 | 可空日期角色 |
| item_count | order_items 聚合 | distinct order_item_id |
| payment_record_count | payments 聚合 | payment record 数量 |
| review_record_count | reviews 聚合 | review record 数量 |
| has_items | order_items 聚合 | 是否存在商品明细 |
| has_payment | payments 聚合 | 是否存在支付记录 |
| has_review | reviews 聚合 | 是否存在评价记录 |
| currency_code | 运行元数据 | BRL |
| data_mode | 运行元数据 | olist_real |

fact_orders 不放 item price、payment value 或 review score。这样一个订单无论有多少商品、支付或评价，订单仍然只有一行。

来源分工：

- 订单状态和时间来自 ods_olist_orders。
- customer_unique_id 来自 customer_id → customer_unique_id 的 bridge。
- item/payment/review counts 是 DWD 质量派生字段。

### 6.2 fact_order_items

粒度：ONE ROW PER ORDER ITEM。主键：order_id + order_item_id。

| 字段 | 来源 | 规则 |
|---|---|---|
| order_id | ods_olist_order_items | FK → fact_orders.order_id |
| order_item_id | ods_olist_order_items | 与 order_id 组成 PK |
| product_id | ods_olist_order_items | FK → dim_product.product_id |
| seller_id | ods_olist_order_items | FK → dim_seller.seller_id |
| shipping_limit_date | ods_olist_order_items | 保留原始时间 |
| shipping_limit_date_key | 派生 | 可空日期外键 |
| price_brl | order_items.price | 非负，商品金额 |
| freight_value_brl | order_items.freight_value | 非负，运费金额 |
| currency_code | 运行元数据 | BRL |
| data_mode | 运行元数据 | olist_real |

fact_order_items 不能合并到 fact_orders，因为一个订单最多有 21 条商品明细，且每行可能对应不同商品和卖家。

未来 Merchandise GMV 应来自 fact_order_items.price_brl 的订单级或选定状态聚合，而不是来自订单头重复字段。

### 6.3 fact_payments

粒度：ONE PAYMENT RECORD。主键：order_id + payment_sequential。

| 字段 | 来源 | 规则 |
|---|---|---|
| order_id | ods_olist_order_payments | FK → fact_orders.order_id |
| payment_sequential | payments | 与 order_id 组成 PK |
| payment_type | payments | 原始支付方式 |
| payment_installments | payments | 原始分期数 |
| payment_value_brl | payments.payment_value | 非负，支付金额 |
| currency_code | 运行元数据 | BRL |
| data_mode | 运行元数据 | olist_real |

Paid Value 必须先在 fact_payments 内按 order_id 求和，再连接到订单级结果。不能把 fact_payments 直接 join 到 fact_order_items 后再求和。

### 6.4 fact_reviews

粒度：ONE REVIEW RECORD。

建议主键：review_id + order_id；如果物理实现需要单列键，可以增加技术 review_row_id，但保留两个源字段。

| 字段 | 来源 | 规则 |
|---|---|---|
| review_id | ods_olist_order_reviews | 源评价标识；单列可能重复 |
| order_id | ods_olist_order_reviews | FK → fact_orders.order_id |
| review_score | reviews | 1–5 |
| review_comment_title | reviews | 可空 |
| review_comment_message | reviews | 可空 |
| review_creation_date | reviews | 原始评价时间 |
| review_answer_timestamp | reviews | 原始回答时间 |
| review_creation_date_key | 派生 | FK → dim_date.date_key，可空 |
| data_mode | 运行元数据 | olist_real |

评价不能直接宽表 join 到订单商品：一个订单最多有 3 条评价，直接展开会重复商品金额。评价数量、平均评分和覆盖率必须先按订单或商品单独聚合。

## 7. Bridge Design

### 7.1 bridge_customer_identity

粒度：ONE ROW PER CUSTOMER RECORD，即一个 customer_id 一行。主键：customer_id。

| 字段 | 来源 | 规则 |
|---|---|---|
| customer_id | ods_olist_customers | PK；订单外键目标 |
| customer_unique_id | ods_olist_customers | FK → dim_customer.customer_unique_id |
| customer_zip_code_prefix | customers | 原始地址前缀 |
| customer_city | customers | 原始城市 |
| customer_state | customers | 原始州 |
| geography_match_status | customers + geography | 匹配状态 |
| source_file | ODS 技术字段 | 可追溯 |
| load_batch_id | ODS 技术字段 | 批次追踪 |
| data_mode | 运行元数据 | olist_real |

在当前快照中，customer_id 逐行唯一，但 customer_unique_id 不是唯一：2,997 个 unique customer 映射到多个 customer_id。因此不能把 customer_id 直接用作客户维度主键。

### 7.2 为什么需要桥接表

orders.customer_id 只能回答“这个订单使用了哪条客户记录”。通过 bridge 才能得到 canonical customer_unique_id，进而回答真实客户的订单数、复购、首次/末次购买和 RFM。

桥表不删除多条 customer_id，也不将地址记录强行合并回 ODS。它是身份解析层，不是 RFM 结果表。

## 8. Customer Identity Strategy

### 8.1 customer_id

customer_id 是 Olist customers 表的记录级标识，同时被 orders.customer_id 引用。它用于订单追踪、源客户记录连接和地址分析。

限制：

- 它不能代表稳定的人级客户；
- 不能直接用来计算复购率或 RFM。

### 8.2 customer_unique_id

customer_unique_id 是跨 customer record 的人级客户标识，也是 dim_customer 的主键。Purchasing Users、Repeat Rate、RFM 和客户生命周期都使用该字段。

### 8.3 RFM 的正确路径

~~~text
fact_orders.customer_id
        ↓
bridge_customer_identity.customer_unique_id
        ↓
dim_customer.customer_unique_id
        ↓
按 customer_unique_id 聚合订单
~~~

如果直接用 customer_id，跨记录客户会被拆成多个“客户”，Frequency 会被低估，Purchasing Users 会被高估，RFM 和 Repeat Rate 都会失真。

## 9. Order Grain Strategy

fact_orders 必须是一订单一行，而不是一订单商品一行：

1. 订单状态和履约时间属于订单头。
2. 一个订单最多有 21 个商品明细。
3. 订单数和订单状态若放在商品粒度，会在连接支付和评价时放大。

订单级指标原则：

- Orders：COUNT DISTINCT fact_orders.order_id。
- Delivered Orders：筛选原始 delivered 或 realization_status = realized。
- Customer count：通过 customer_unique_id 去重。
- Item count、Payment count、Review count 分别从自己的事实表聚合。

## 10. Payment Grain Strategy

一个订单可以有多笔 payment record，最大 29 条。payment_sequential 只在订单内有意义，因此主键必须是 order_id + payment_sequential。

安全支付汇总：

~~~text
fact_payments
    GROUP BY order_id
    SUM(payment_value_brl) AS paid_value_brl
~~~

Merchandise GMV 来自 fact_order_items.price_brl；Paid Value 来自 fact_payments.payment_value_brl。两者可以对账，但不要求相等，也不能未经说明把 payment_value 改名为 Net Sales。

## 11. Review Grain Strategy

一个订单可能有多条评价，也可能没有评价。review_id 单列不是可靠唯一键，review_id + order_id 才是当前数据画像确认的候选复合键。

安全评价汇总：

~~~text
fact_reviews
    GROUP BY order_id
    COUNT(*) AS review_record_count
    AVG(review_score) AS average_review_score
~~~

评价缺失不应导致订单丢失。评分分析应同时报告评价覆盖率。评价行不能和 item、payment 同时宽连接。

## 12. Product Model

### 12.1 品类翻译

dim_product 同时保留：

- category_pt：原始葡萄牙语类别；
- category_en：翻译表匹配的英文类别；
- category_translation_status：translated、untranslated、missing。

未匹配的 pc_gamer 和 portateis_cozinha_e_preparadores_de_alimentos 不能丢弃。产品仍然进入 dim_product，category_en 可以为空或使用可审计的原文展示别名。

### 12.2 商品指标边界

dim_product 只保存商品属性和品类属性。商品金额、订单数、买家数、卖家数、评价分和历史机会信号都应来自事实聚合。

后续历史商品机会分析可使用 item price、订单数、unique customer 数、review score、seller 数和 freight value。不能直接复用 V1.1 的合成 hot_score、opportunity_score、cost 或 margin。

## 13. Date Model

dim_date 由有效 Olist 日期动态生成，至少覆盖订单购买、批准、承运、送达、预计送达、shipping limit、review creation 和 review answer 日期。

订单购买主范围为 2016-09-04 至 2018-10-17。shipping_limit_date 可延伸到 2020-04-09，应保留并标记。

建议以 purchase_date_key 作为 fact_orders 主活动日期关系，其他日期使用角色维度或非活动关系。不要创建 FY2025 过滤条件。

## 14. Mermaid ER Diagram

~~~mermaid
erDiagram
    DIM_CUSTOMER ||--o{ BRIDGE_CUSTOMER_IDENTITY : maps
    BRIDGE_CUSTOMER_IDENTITY ||--o{ FACT_ORDERS : identifies
    DIM_CUSTOMER ||--o{ FACT_ORDERS : owns
    DIM_DATE ||--o{ FACT_ORDERS : purchase_date
    FACT_ORDERS ||--o{ FACT_ORDER_ITEMS : contains
    FACT_ORDERS ||--o{ FACT_PAYMENTS : has
    FACT_ORDERS ||--o{ FACT_REVIEWS : receives
    DIM_PRODUCT ||--o{ FACT_ORDER_ITEMS : sold_as
    DIM_SELLER ||--o{ FACT_ORDER_ITEMS : fulfilled_by
    DIM_CATEGORY ||--o{ DIM_PRODUCT : classifies
    DIM_DATE ||--o{ FACT_ORDER_ITEMS : shipping_date
    DIM_DATE ||--o{ FACT_REVIEWS : review_date

    DIM_CUSTOMER {
        string customer_unique_id PK
        string preferred_customer_state
        string preferred_customer_city
        date first_order_date
        date last_order_date
        int delivered_order_count
    }
    BRIDGE_CUSTOMER_IDENTITY {
        string customer_id PK
        string customer_unique_id FK
        int customer_zip_code_prefix
        string customer_city
        string customer_state
    }
    FACT_ORDERS {
        string order_id PK
        string customer_id FK
        string customer_unique_id FK
        string order_status
        string realization_status
        datetime purchase_timestamp
        int purchase_date_key FK
        int item_count
        int payment_record_count
        int review_record_count
    }
    FACT_ORDER_ITEMS {
        string order_id PK
        int order_item_id PK
        string product_id FK
        string seller_id FK
        decimal price_brl
        decimal freight_value_brl
        datetime shipping_limit_date
    }
    FACT_PAYMENTS {
        string order_id PK
        int payment_sequential PK
        string payment_type
        int payment_installments
        decimal payment_value_brl
    }
    FACT_REVIEWS {
        string review_id PK
        string order_id PK
        int review_score
        datetime review_creation_date
        datetime review_answer_timestamp
    }
    DIM_PRODUCT {
        string product_id PK
        string category_pt FK
        string category_en
        string category_translation_status
    }
    DIM_SELLER {
        string seller_id PK
        int seller_zip_code_prefix
        string seller_city
        string seller_state
    }
    DIM_CATEGORY {
        string category_pt PK
        string category_en
    }
    DIM_DATE {
        int date_key PK
        date calendar_date
        int year
        string quarter
        string month
        int week
    }
~~~

关系说明：

- DIM_CUSTOMER 1:N BRIDGE_CUSTOMER_IDENTITY。
- BRIDGE_CUSTOMER_IDENTITY 1:N FACT_ORDERS。
- DIM_CUSTOMER 1:N FACT_ORDERS。
- FACT_ORDERS 1:N FACT_ORDER_ITEMS。
- FACT_ORDERS 1:N FACT_PAYMENTS。
- FACT_ORDERS 1:N FACT_REVIEWS。
- DIM_PRODUCT 1:N FACT_ORDER_ITEMS。
- DIM_SELLER 1:N FACT_ORDER_ITEMS。
- DIM_DATE 1:N 各日期事实角色。

## 15. KPI Compatibility Matrix

| KPI | 需要的表 | 主要字段 | 计算粒度 | Olist 支持 | 规则 |
|---|---|---|---|---|---|
| Merchandise GMV | fact_orders + fact_order_items | order_status、price_brl | item 聚合到 order | 部分支持 | 推荐 delivered 商品 price_brl；不是旧 gross_amount |
| Paid Value | fact_orders + fact_payments | payment_value_brl | payment 聚合到 order | 支持 | 先按 order_id 汇总 |
| Revenue / Net Sales | orders + items + payments | price、payment_value | order/item | 不具备严格同义 | 可提供 Delivered Merchandise Sales 代理，不直接叫 Net Sales |
| AOV | order/item 聚合 | GMV 或 Paid Value、订单数 | order | 部分支持 | 区分 Merchandise AOV 和 Paid Value AOV |
| Completed Orders | fact_orders | order_id、order_status | order | 部分支持 | delivered 作为 completed-like，不创建 refunded |
| Purchasing Users | fact_orders + dim_customer | customer_unique_id | customer | 支持 | canonical customer 去重 |
| Repeat Rate | orders + bridge + customer | unique customer、order_id | customer | 支持 | delivered 订单中至少两单的客户比例 |
| RFM | orders + items + bridge + customer | purchase date、order_id、price_brl | customer_unique_id | 支持 | as-of date 可配置，不固定 FY2025 |
| Review Score | fact_reviews | review_score | review/order/product | 支持 | 同时报告评价覆盖率 |
| Gross Profit | 无可信 cost | cost 缺失 | order/item | 不支持 | 不估算成本 |
| Gross Margin | 无可信 cost/refund | cost、refund 缺失 | order/item | 不支持 | Real Mode 为 N/A |
| CTR | 无 ads fact | impressions、clicks 缺失 | campaign/date | 不支持 | 无广告曝光和点击 |
| CVR | 无 ads fact | conversions/clicks 缺失 | campaign/date | 不支持 | 不把支付当广告转化 |
| CPA | 无 ads fact | spend、conversions 缺失 | campaign/date | 不支持 | 不制造 ad spend |
| ROAS | 无 ads fact | attributed revenue、spend 缺失 | campaign/date | 不支持 | 仅 Synthetic Mode 保留 |

### 15.1 GMV 推荐定义

~~~text
Merchandise GMV (BRL)
    = SUM(fact_order_items.price_brl)
      for orders whose selected status is delivered

Paid Value (BRL)
    = SUM(fact_payments.payment_value_brl)
      for the same selected order set
~~~

如果需要下单口径，单独命名 Placed Merchandise GMV。不要把下单、已送达和支付口径混成一个 GMV。

### 15.2 不可支持 KPI

Olist Real Mode 必须隐藏、显示 N/A 或 unavailable：

- Gross Profit
- Gross Margin
- CTR
- CVR
- CPA
- ROAS

不能使用 0、支付金额、商品价格差、评价分或合成广告行填充。

## 16. Order Status Mapping

标准层保留原始 order_status，并额外生成 realization_status。不要覆盖源状态，不要创造 refunded。

| 原始状态 | DWD realization_status | 默认已实现销售 | 说明 |
|---|---|---:|---|
| delivered | realized | 是 | 默认 completed-like 订单 |
| shipped | in_flight | 否 | 已发货但未确认送达 |
| invoiced | in_flight | 否 | 已开票但未确认送达 |
| processing | in_flight | 否 | 处理中 |
| approved | in_flight | 否 | 已批准但未完成 |
| created | in_flight | 否 | 已创建 |
| canceled | canceled | 否 | 不能推断退款 |
| unavailable | unfulfilled | 否 | 不可用/未履约 |

## 17. Data Quality Checks

Phase 2-B 应新增以下检查：

### 17.1 粒度和主键

- fact_orders.order_id 唯一。
- fact_order_items 的 order_id + order_item_id 唯一。
- fact_payments 的 order_id + payment_sequential 唯一。
- fact_reviews 的 review_id + order_id 唯一。
- 四张维度表各自主键唯一。
- bridge_customer_identity.customer_id 唯一。

### 17.2 外键

- fact_orders.customer_id → bridge。
- fact_orders.customer_unique_id → dim_customer。
- fact_order_items.order_id → fact_orders。
- item product/seller → 对应维度。
- payment/review order_id → fact_orders。
- 日期键 → dim_date。

### 17.3 金额与防重复

- price_brl、freight_value_brl、payment_value_brl 非负。
- item、payment、review 分别按 order_id 聚合。
- 订单数不因商品明细增加。
- Merchandise GMV 不因支付行增加。
- Paid Value 不因商品行增加。
- 评价缺失不导致订单丢失。
- canceled/unavailable 不进入默认 realized 销售。

### 17.4 身份、翻译和日期

- 每个 customer_id 只映射一个 customer_unique_id。
- dim_customer 一行对应一个 customer_unique_id。
- RFM Frequency 使用 distinct order_id。
- 翻译覆盖率单独报告，两个未匹配类别仍保留。
- 订单购买日期保持 2016–2018。
- shipping_limit_date 的 2020 尾部值不删除。
- data_mode 固定 olist_real，currency_code 固定 BRL。

## 18. Power BI Impact

| 页面 | 可以保留 | 必须修改或隐藏 | 需要增加 |
|---|---|---|---|
| Operations Overview | 订单趋势、订单数、客户数、商品金额、Paid Value | Gross Profit、Gross Margin、旧 Net Sales | BRL、数据源、日期范围、Delivered/Placed 口径 |
| Product Opportunity | 商品、品类、价格、订单商品数、评价 | Synthetic Hot/Opportunity Score、成本/利润排序 | category_pt/en、seller count、评价覆盖率、历史机会信号 |
| Customer Value | 客户分层、RFM、复购 | user_id 和 FY2025 固定窗口 | customer_unique_id、as-of date、订单状态、BRL |
| Advertising Return | Synthetic Mode 现有广告页 | Olist Real Mode 全部广告 KPI | unavailable 或仅 Synthetic Scenario 标签 |

未来语义模型需要核心 9 张 DWD 表和 dataset metadata。当前 DAX 使用 orders.net_sales、orders.cost、ads.spend 和 FY2025 日期；Olist 适配不能把 payment_value 填入 net_sales，不能把成本填 0，也不能把支付或评价映射成广告转化。

本阶段不修改任何 Power BI、TMDL、DAX 或页面。

## 19. Synthetic/Olist Dual Mode

### 19.1 推荐入口

未来推荐显式模式参数：

~~~text
python run_pipeline.py --mode synthetic
python run_pipeline.py --mode olist
~~~

当前 run_pipeline.py 不在 Phase 2-A 修改。Phase 2-B 应先提供 Olist 独立 DWD 入口，再单独审查主入口调度。

### 19.2 模式契约

| 属性 | Synthetic Mode | Olist Real Mode |
|---|---|---|
| data_mode | synthetic | olist_real |
| source_name | Project Simulation | Olist Brazilian E-Commerce Public Dataset |
| currency_code | TWD | BRL |
| date window | 2025 | 2016–2018 |
| customer key | user_id | customer_unique_id |
| realized status | completed | delivered |
| cost | synthetic | unavailable |
| ads | synthetic | unavailable |
| refund | simulated refunded | unavailable |

防混淆措施：

1. Olist 使用独立 ODS/DWD 数据库，不覆盖 data/analytics.sqlite。
2. 输出表写入 data_mode、source_name、currency_code。
3. 文件名和数据库路径区分模式。
4. Dashboard 显示 Real/Synthetic、来源、币种和日期。
5. 测试按模式隔离。
6. 不把 Olist 历史 BRL 结果写回 V1.1 TWD CSV。

## 20. Phase 2-B Implementation Plan

Phase 2-B 才开始编码。建议新增：

| 文件 | 目的 |
|---|---|
| etl/olist/build_dwd.py | 从 ODS 构建维度、桥和事实 |
| etl/olist/dwd_schema.py | 声明 DWD 字段、键、类型和版本 |
| etl/olist/dwd_quality.py | 粒度、外键、防重复、金额和状态检查 |
| tests/test_olist_dwd.py | DWD 关系和质量测试 |
| tests/fixtures/olist/ | 小型多商品、多支付、多评价、重复客户 fixture |
| docs/olist_phase2b_dwd_implementation.md | 实施和验证记录 |

建议 DWD 数据库：

~~~text
data/olist_dwd.sqlite
~~~

不要覆盖 ODS 的 data/olist_analytics.sqlite 或 Synthetic 的 data/analytics.sqlite。

### 20.1 实施顺序

1. 从 ODS 读取源表和 dataset_metadata。
2. 构建 bridge_customer_identity。
3. 构建四张维度。
4. 构建 fact_orders。
5. 构建三个子事实。
6. 对 item、payment、review 分别聚合并执行防重复测试。
7. 生成 DWD 质量报告。
8. 验证 Synthetic 19/19 基线不受影响。
9. DWD 稳定后再设计 DWS/ADS。

### 20.2 Phase 2-B 不应修改

除非另一个阶段明确批准，不应直接修改：

- data/raw/olist/*.csv
- data/generate_data.py
- data/analytics.sqlite
- analysis/run_analysis.py
- database/schema.sql
- database/analysis_queries.sql
- dashboard/build_dashboard.py
- Power BI、TMDL、PBIR、DAX
- 现有 Synthetic 测试

如果需要主入口模式调度，应先新增独立入口并通过回归，再由单独变更审查 run_pipeline.py。

## 结论

Olist DWD 应以订单头、订单商品、支付、评价四种事实粒度为基础，以 customer_unique_id、product_id、seller_id 和 date_key 为分析连接点，以 bridge_customer_identity 解决 customer_id 到人级客户的身份关系。

- fact_orders：一订单一行。
- fact_order_items：一订单商品一行。
- fact_payments：一笔支付一行。
- fact_reviews：一条评价一行。
- Merchandise GMV 来自 price_brl。
- Paid Value 来自 payment_value_brl。
- RFM 和 Repeat Rate 使用 customer_unique_id。
- Profit、Margin、ROAS、CTR、CVR、CPA 在 Olist Real Mode 不可支持。

当前工作仍停留在设计阶段，没有开始 Phase 2-B 编码。
