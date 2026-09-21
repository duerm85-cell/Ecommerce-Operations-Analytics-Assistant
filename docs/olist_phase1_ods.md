# Olist V2.0 Phase 1：ODS 只读加载与源数据验证

> 状态：已实现并完成本地验证  
> 范围：Raw CSV → Source Validation → ODS → Metadata / Quality Checks  
> 边界：本阶段不进入 DWD、DWS、ADS、RFM、KPI、Power BI 或 DAX

## 1. Phase 1 范围

Phase 1 为 Olist 官方公开数据建立独立的源数据验证和 ODS 快照。它只保留、验证和装载原始事实，不改变日期、金额、订单状态或业务含义。

本阶段没有修改：

- data/generate_data.py
- analysis/run_analysis.py
- run_pipeline.py
- database/
- dashboard/
- Power BI、DAX
- 既有 Synthetic 测试
- data/raw/olist/ 中的原始 CSV

## 2. 新增代码结构

```text
etl/
├── __init__.py
└── olist/
    ├── __init__.py
    ├── config.py
    ├── validator.py
    └── load_ods.py

tests/
├── test_olist_source_validation.py
└── test_olist_ods.py
```

- config.py：定义 9 个源文件、ODS 表名、必需字段、唯一键、时间字段和默认路径。
- validator.py：只读扫描 CSV，执行 schema、主键、复合键、外键、金额、评分、时间和 SHA-256 校验。
- load_ods.py：使用独立 CLI 生成完整 SQLite ODS 快照、数据集元数据、加载元数据和 hash manifest。
- 两个测试文件：分别验证源合同和 ODS 行数、幂等性、元数据、hash、历史日期、原子失败及 Synthetic 隔离。

## 3. 原始文件

源目录：data/raw/olist/

| 原始文件 | 实际行数 |
|---|---:|
| olist_customers_dataset.csv | 99,441 |
| olist_geolocation_dataset.csv | 1,000,163 |
| olist_order_items_dataset.csv | 112,650 |
| olist_order_payments_dataset.csv | 103,886 |
| olist_order_reviews_dataset.csv | 99,224 |
| olist_orders_dataset.csv | 99,441 |
| olist_products_dataset.csv | 32,951 |
| olist_sellers_dataset.csv | 3,095 |
| product_category_name_translation.csv | 71 |

Loader 只读取这些文件。ODS 加载前后均重新计算 SHA-256，不向源目录写入数据。

## 4. ODS 表

数据库包含 9 张业务 ODS 表：

| ODS 表 | 粒度 | 实际行数 |
|---|---|---:|
| ods_olist_customers | 一个客户记录 | 99,441 |
| ods_olist_geolocation | 一个原始地理观测行 | 1,000,163 |
| ods_olist_order_items | 一个订单商品明细 | 112,650 |
| ods_olist_order_payments | 一笔订单支付记录 | 103,886 |
| ods_olist_order_reviews | 一个原始评价记录 | 99,224 |
| ods_olist_orders | 一个订单头 | 99,441 |
| ods_olist_products | 一个商品 | 32,951 |
| ods_olist_sellers | 一个卖家 | 3,095 |
| ods_olist_category_translation | 一个葡萄牙语品类翻译 | 71 |

另有两张元数据表：

- dataset_metadata：当前发布快照的数据模式、来源、币种、能力边界和日期范围。
- etl_load_metadata：当前批次按源文件记录的行数、hash、时间和状态。

没有创建 fact、dim、DWS 或 ADS 表。

## 5. 技术字段

每张 ODS 业务表在全部原始字段之后增加四个技术字段：

| 字段 | 含义 |
|---|---|
| _load_batch_id | 本次完整快照的批次 ID |
| _source_file | 记录来自哪个 CSV |
| _source_row_number | CSV 数据区内从 1 开始的行号 |
| _loaded_at | 以 UTC ISO-8601 记录的加载时间 |

原始空值继续以 SQLite NULL 保存；原始地理重复行不删除。原始时间字段按源字符串保存，validator 只做可解析性检查，因此没有日期平移或格式改写。

## 6. Source Validation 规则

加载发布前必须全部通过：

1. 9 个文件均存在、非空且可读取。
2. 每个文件包含配置中声明的必需字段。
3. customers.customer_id、orders.order_id、products.product_id、sellers.seller_id 唯一且非空。
4. order_items 的 (order_id, order_item_id) 唯一。
5. payments 的 (order_id, payment_sequential) 唯一。
6. review 数据的 (review_id, order_id) 唯一；不强制 review_id 单列唯一。
7. orders → customers、order_items → orders/products/sellers、payments → orders、reviews → orders 无孤儿键。
8. price、freight_value、payment_value 可解析且不小于 0。
9. review_score 在 1 到 5 范围内。
10. 所有非空关键时间值均可解析。
11. geolocation 邮编前缀不要求唯一，完整重复行原样进入 ODS。

本次结果：

```text
[olist][validate] source_files=9/9
[olist][validate] schema=passed
[olist][validate] foreign_keys=passed
[olist][validate] amounts=passed
[olist][validate] timestamps=passed
[olist][validate] geolocation_uniqueness=not_required
```

## 7. Hash 校验

机器可读 manifest：data/olist_source_manifest.json

| 原始文件 | SHA-256 |
|---|---|
| olist_customers_dataset.csv | 983a422239e1712ded753b3bf9ecf47dc73f144d306029dcfa99e70a226883d2 |
| olist_geolocation_dataset.csv | b514f6fc991b9566aeba02aa5d67e2c3630f034b60a0e05aa0d082a3b66d88d6 |
| olist_order_items_dataset.csv | 0bc4d068c4fe38cbb01bd90e8746e3c613fe7b4baef75fab7b0e329701c3e279 |
| olist_order_payments_dataset.csv | 4f713964f2815dbbaa40b9488268c55aac3627bfce5aa96cf58d1f3616de3cc0 |
| olist_order_reviews_dataset.csv | 012b61c7593e34f51fa614efdf802b9c7056ce6aae5307ddb93236e7cfc797d7 |
| olist_orders_dataset.csv | 8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf |
| olist_products_dataset.csv | 3e6569628a17fbc75fd206ee357b59e20364b9afa90f5b6cd5b4d624c58aa9cc |
| olist_sellers_dataset.csv | 1f643d2b950373b85735e7794b20986f528d7a000432e7c6f9bcbb44d0846a0e |
| product_category_name_translation.csv | a81f0d1f27b27e7293f761bc79e3ce8f348ee39c4b3ed3e49bde38f478586278 |

加载前后的 9 个摘要完全一致：

```text
raw_csv_hashes_unchanged=True
```

Loader 还会计算 data/analytics.sqlite 的加载前后 hash；任何变化都会使 Olist 加载失败。本次 Synthetic 数据库保持不变。

## 8. Dataset Metadata

dataset_metadata 当前内容：

| metadata_key | metadata_value |
|---|---|
| data_mode | olist_real |
| source_name | Olist Brazilian E-Commerce Public Dataset |
| source_dataset | olistbr/brazilian-ecommerce |
| currency_code | BRL |
| historical_data | true |
| ads_available | false |
| cost_available | false |
| refund_status_available | false |
| date_min | 2016-09-04 21:15:19 |
| date_max | 2018-10-17 17:30:18 |
| source_file_count | 9 |
| raw_csv_hashes_unchanged | true |

date_min 和 date_max 每次从有效的 order_purchase_timestamp 动态计算，没有硬编码 FY2025，也没有币种换算。

## 9. ODS 数据库位置

独立数据库：

```text
data/olist_analytics.sqlite
```

选择独立文件是为了把真实 Olist ODS 与 Synthetic V1.1 的 data/analytics.sqlite 完全隔离。本次生成的数据库约 272 MiB，包含 9 张 ODS 表和 2 张元数据表。

## 10. 幂等策略

采用 transactional snapshot rebuild：

1. 每次重新读取并验证全部 9 个源文件。
2. 在同一目录创建新的临时 SQLite 快照。
3. 向临时快照完整装载 9 张 ODS 表和元数据。
4. 验证 raw hash 与 Synthetic 数据库 hash。
5. 只有全部成功后，使用原子替换发布为 data/olist_analytics.sqlite。

每次运行生成新的 batch ID，但数据库只保存当前发布快照，不在旧表上追加。连续运行两次后的 9 张 ODS 表行数完全一致，没有 double load。

## 11. 事务与原子性策略

所有业务表和元数据先写入未发布的临时数据库。任意表、索引、元数据或 hash 校验失败时：

- 临时数据库回滚并删除；
- 已发布的 ODS 快照保持不变；
- data/olist_load_failure.json 记录 load_status=failed、批次时间和错误类型；
- CLI 返回非零退出码。

测试使用缺失源目录主动触发失败，确认已有数据库字节未被替换，并确认失败元数据状态为 failed。

## 12. 如何运行

在项目根目录使用当前 .venv：

```powershell
.venv\Scripts\python.exe -m etl.olist.load_ods
```

可选测试路径参数：

```powershell
.venv\Scripts\python.exe -m etl.olist.load_ods --raw-dir <path> --db-path <path>
```

正常日志只输出验证阶段、每张表行数、批次 ID 和数据库路径，不输出任何 Kaggle token、账号密码或 API key。

## 13. 如何测试

只运行 Olist 测试：

```powershell
.venv\Scripts\python.exe -m unittest tests.test_olist_source_validation tests.test_olist_ods -v
```

运行完整测试：

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

本次验证：

- Olist 新增测试：20 个，20/20 通过。
- 原有 Synthetic/Power BI 测试：19 个，19/19 通过。
- 当前合计：39 个测试。

沙箱内直接读取部分 Power BI 项目文件会出现 ACL PermissionError；在本机权限下只读重跑后，原有 19 个测试全部通过。测试代码没有为此修改。

## 14. 数据质量发现

- 原始 9 个文件、必需字段、核心主键、复合键和核心外键全部通过。
- geolocation 有 1,000,163 行，邮编前缀不唯一，并包含 261,831 个完整重复超额行；ODS 保留全部记录。
- 评价标题和正文有大量合理缺失，ODS 继续保存 NULL。
- orders 的批准、承运和实际送达时间存在缺失，但所有非空值均可解析。
- order purchase 时间保持 2016-09-04 21:15:19 至 2018-10-17 17:30:18。
- shipping_limit_date 最大值延伸到 2020-04-09 22:35:08；ODS 不删除、不修正，只记录为质量观察。
- 金额保持 BRL，不转换为 TWD 或 USD。

## 15. 已知限制

- ODS 只保存并验证来源事实，不提供适合分析的星型模型。
- geolocation 尚未聚合为唯一邮编维度。
- customer_id 与 customer_unique_id 尚未建立客户桥或人级维度。
- 订单、商品明细、支付和评价尚未形成 DWD 事实表。
- 不计算 GMV、Paid Value、AOV、Repeat Rate、RFM 或 Product Opportunity。
- Olist 没有真实成本、退款状态和广告事实；本阶段不补造这些字段。
- ODS SQLite 和 manifest 是本地生成产物，当前阶段没有执行 Git 提交。

## 16. 下一阶段边界

Phase 2 才可以开始 DWD 设计的实现，建议按以下顺序：

1. 建立 fact_order、fact_order_item、fact_payment、fact_review。
2. 建立 customer record 与 customer_unique_id 的身份桥。
3. 建立 product、seller、category、date 和去重地理维度。
4. 对多商品、多支付、多评价关系增加防重复聚合测试。
5. 继续保持 Olist Real 与 Synthetic V1.1 数据库、币种和时间语义隔离。

Phase 2 不应在本阶段自动开始。
