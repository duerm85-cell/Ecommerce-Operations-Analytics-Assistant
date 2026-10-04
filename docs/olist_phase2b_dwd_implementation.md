# Olist V2.0 Phase 2-B.1：DWD Layer Implementation

> 实施范围：Olist ODS → DWD
>
> 数据模式：`olist_real`
>
> 数据库：`data/olist_analytics.sqlite`
>
> 验证日期：2026-10-05

本文记录 Phase 2-B.1 的实际实现。该阶段只建设 Dimension、Bridge 和 Fact，不包含 DWS、ADS、KPI、RFM、Power BI、Dashboard 或 DAX。

## 1. 实现范围

本阶段在现有 Olist ODS 快照上事务性重建 9 张 DWD 表：

- Dimension：`dim_customer`、`dim_product`、`dim_seller`、`dim_date`
- Bridge：`bridge_customer_identity`
- Fact：`fact_orders`、`fact_order_items`、`fact_payments`、`fact_reviews`

实现文件：

- `etl/olist/dwd_schema.py`：表、主键、外键、约束和索引定义
- `etl/olist/build_dwd.py`：ODS 到 DWD 的转换与运行入口
- `etl/olist/dwd_quality.py`：DWD 粒度、完整性和防重复检查
- `tests/test_olist_dwd.py`：自动化测试

构建使用同一个 `data/olist_analytics.sqlite`，保留已有 ODS 表。建表、装载、质量检查和元数据更新在一个事务内完成；任何一步失败都会回滚本次 DWD 构建。

`data/analytics.sqlite` 属于 Synthetic V1.1。本阶段在构建前后比较其 SHA-256，确认该数据库没有变化。

## 2. ODS 输入

| ODS 表 | 用途 |
|---|---|
| `ods_olist_customers` | 客户记录、客户唯一身份和地址属性 |
| `ods_olist_orders` | 订单头、原始状态和履约时间 |
| `ods_olist_order_items` | 商品明细、商品金额、运费和卖家关系 |
| `ods_olist_order_payments` | 支付方式、分期数和支付金额 |
| `ods_olist_order_reviews` | 评价、评分和评价时间 |
| `ods_olist_products` | 商品属性和葡萄牙语品类 |
| `ods_olist_sellers` | 卖家属性 |
| `ods_olist_geolocation` | 邮编前缀是否存在的质量标记 |
| `ods_olist_category_translation` | 葡萄牙语品类到英文品类的映射 |
| `dataset_metadata` | 数据模式、币种、批次和构建状态 |

原始 CSV 和 ODS 业务字段均不被改写。DWD 只从现有 ODS 快照读取数据。

## 3. DWD 输出

本次验证生成的实际行数如下：

| 类型 | DWD 表 | 行数 | 粒度 |
|---|---|---:|---|
| Dimension | `dim_customer` | 96,096 | 一个 `customer_unique_id` 一行 |
| Dimension | `dim_product` | 32,951 | 一个 `product_id` 一行 |
| Dimension | `dim_seller` | 3,095 | 一个 `seller_id` 一行 |
| Dimension | `dim_date` | 1,314 | 一个自然日期一行 |
| Bridge | `bridge_customer_identity` | 99,441 | 一个 `customer_id` 一行 |
| Fact | `fact_orders` | 99,441 | 一个订单一行 |
| Fact | `fact_order_items` | 112,650 | 一个订单商品明细一行 |
| Fact | `fact_payments` | 103,886 | 一笔支付记录一行 |
| Fact | `fact_reviews` | 99,224 | 一个源评价记录一行 |

`dim_date` 动态覆盖所有 Olist 真实日期字段，当前范围为 2016-09-04 至 2020-04-09。范围包含订单购买、批准、承运、送达、预计送达、商品发货截止、评价创建和评价回答日期，没有 FY2025 数据。

## 4. 表粒度

### 4.1 Dimension

`dim_customer` 使用 `customer_unique_id` 作为主键。确定性地址规则选择该客户最新订单对应的 customer record，同时保存 customer record 数、首次/末次订单日期、订单数和 delivered 订单数。后续客户数、复购和 RFM 必须按 `customer_unique_id` 计算。

`dim_product` 使用 `product_id` 作为主键。它左连接品类翻译，保留 `category_pt`、`category_en` 和翻译状态。未翻译或缺失类别的商品仍保留。

`dim_seller` 使用 `seller_id` 作为主键。地理表的邮编前缀先去重后只用于生成 `matched`/`unmatched` 标记，避免 geolocation 多行把卖家维度放大。

`dim_date` 使用 `YYYYMMDD` 整数作为 `date_key`，按真实源日期动态生成连续日期。

### 4.2 Bridge

`bridge_customer_identity` 使用 `customer_id` 作为主键，并映射到 `customer_unique_id`。它保留所有 99,441 条 customer record，不把多个地址记录强制合并。当前 99,441 个 `customer_id` 对应 96,096 个 `customer_unique_id`。

### 4.3 Fact

`fact_orders` 严格为一个 `order_id` 一行。item、payment 和 review 只以计数字段表示是否存在及记录数，明细仍存放在各自事实表。订单状态原样保留，没有生成 `completed` 或 `refunded`。

`fact_order_items` 的主键是 `(order_id, order_item_id)`。`price_brl` 和 `freight_value_brl` 来自源商品明细，币种固定为 BRL。

`fact_payments` 的主键是 `(order_id, payment_sequential)`。`payment_value_brl` 保持支付记录粒度；同一订单的多笔支付不会合并。

`fact_reviews` 保留全部源评价记录。由于源 `review_id` 单列可能重复，而本阶段要求 DWD 使用单列 `review_id` 主键，物理主键采用稳定的 `source_review_id:order_id`，同时在 `source_review_id` 保存原始评价标识。`(source_review_id, order_id)` 另设唯一约束，保证与 ODS 一一对应。

## 5. 字段规则

- 数据模式统一为 `olist_real`。
- 商品、运费和支付金额均为 BRL；字段使用 `_brl` 后缀，不执行汇率转换。
- `order_status` 完整保留 Olist 原始值。
- `category_pt` 保留源葡萄牙语品类，`category_en` 使用翻译表左连接生成。
- 未匹配翻译的商品不删除，`category_en` 保留 `NULL`，翻译状态为 `untranslated`。
- 缺失源品类的商品不删除，翻译状态为 `missing`。
- ODS 的 `_source_file`、`_source_row_number`、`_load_batch_id` 被传递到 Bridge 和 Fact，用于追溯。
- 每张 DWD 表记录 `_dwd_build_id` 和 `_built_at`。
- 商品、支付和评价事实不相互展开连接。

## 6. 主外键

| 表 | 主键 | 主要外键 |
|---|---|---|
| `dim_customer` | `customer_unique_id` | — |
| `dim_product` | `product_id` | — |
| `dim_seller` | `seller_id` | — |
| `dim_date` | `date_key` | — |
| `bridge_customer_identity` | `customer_id` | `customer_unique_id → dim_customer` |
| `fact_orders` | `order_id` | `customer_id → bridge`；`customer_unique_id → dim_customer`；`purchase_date_key → dim_date` |
| `fact_order_items` | `order_id, order_item_id` | `order_id → fact_orders`；`product_id → dim_product`；`seller_id → dim_seller` |
| `fact_payments` | `order_id, payment_sequential` | `order_id → fact_orders` |
| `fact_reviews` | `review_id` | `order_id → fact_orders` |

客户身份路径为：

```text
fact_orders.customer_id
    → bridge_customer_identity.customer_id
    → bridge_customer_identity.customer_unique_id
    → dim_customer.customer_unique_id
```

## 7. 质量检查

`etl/olist/dwd_quality.py` 在提交事务前执行以下 12 项检查：

1. 9 张 DWD 表全部存在。
2. 所需 ODS 输入全部存在。
3. 所有主键非空且唯一。
4. SQLite 外键检查无违规。
5. Dimension、Bridge 和 Fact 行数符合源粒度。
6. `customer_id → customer_unique_id` Bridge 映射正确。
7. 四张事实表粒度正确且无重复事实。
8. DWD 状态值与 ODS 原始状态集合一致。
9. 金额事实和元数据均为 BRL。
10. 日期维度完整覆盖真实日期范围。
11. DWD 评价与 ODS 评价一一对应。
12. 商品事实连接订单、商品和卖家维度后，行数和商品金额总和不增加。

本次构建结果为 12/12 通过。`tests/test_olist_dwd.py` 另执行 13 个测试，结果为 13/13 通过。

## 8. 运行方法

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m etl.olist.build_dwd
```

如当前终端已经激活项目虚拟环境，也可以执行：

```powershell
python -m etl.olist.build_dwd
```

运行成功后会输出：

- DWD build ID
- 数据库绝对路径
- 9 张表的行数
- 12 项质量检查结果
- Synthetic V1.1 数据库未变化标记

单独运行 DWD 测试：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_olist_dwd -v
```

运行全部测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 9. 限制

- 本阶段只实现 DWD，不生成 DWS、ADS、KPI 或可视化输入。
- Olist 是历史公开数据，不能解释为企业实时经营数据。
- 数据集没有可信商品成本、退款状态和广告事实，因此不计算 Profit、Margin、CTR、CVR、CPA 或 ROAS。
- `delivered` 仍是 Olist 原始状态，没有重命名为 `completed`。
- Merchandise value 与 paid value 属于不同事实，不能未经定义互相替代。
- 跨事实分析必须先在各自事实表按 `order_id` 聚合，再连接订单级结果。
- geolocation 邮编前缀不唯一，本阶段只生成匹配状态，不把地理观测行直接连接进事实。
- `pc_gamer` 和 `portateis_cozinha_e_preparadores_de_alimentos` 等未匹配翻译保持原品类并保留 `NULL category_en`。
- 本阶段没有修改 Synthetic V1.1、`data/generate_data.py`、`run_pipeline.py`、`analysis/`、`dashboard/`、Power BI、DAX 或原始 Olist CSV。
