# Olist 真实公开数据集审查报告

> 本报告由 `analysis/profile_olist.py` 对原始 CSV 进行只读扫描生成。本阶段只认识数据，不进行字段映射、ETL、数据库或 Power BI 改造。

## 1. 数据来源与版本

- 数据集：Brazilian E-Commerce Public Dataset by Olist
- Kaggle 标识：`olistbr/brazilian-ecommerce`
- 官方页面：https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
- Kaggle 文件版本时间：2021-10-01（CLI 文件清单显示）
- 本地下载/画像时间：2026-09-20T20:26:45+08:00
- 许可证：CC BY-NC-SA 4.0（Kaggle CLI 下载输出）
- 原始目录：`data/raw/olist/`（由 Git 忽略，不应提交）
- 金额语境：巴西雷亚尔 BRL；时间字段未携带时区。

## 2. 文件清单

| 文件 | 大小 MiB | 行数 | 列数 | 完整重复行（超额） | 唯一且非空的候选键 |
| --- | --- | --- | --- | --- | --- |
| olist_customers_dataset.csv | 8.62 | 99,441 | 5 | 0 | customer_id |
| olist_geolocation_dataset.csv | 58.44 | 1,000,163 | 5 | 261,831 | 无 |
| olist_order_items_dataset.csv | 14.72 | 112,650 | 7 | 0 | order_id, order_item_id |
| olist_order_payments_dataset.csv | 5.51 | 103,886 | 5 | 0 | order_id, payment_sequential |
| olist_order_reviews_dataset.csv | 13.78 | 99,224 | 7 | 0 | review_id, order_id |
| olist_orders_dataset.csv | 16.84 | 99,441 | 8 | 0 | order_id; customer_id |
| olist_products_dataset.csv | 2.27 | 32,951 | 9 | 0 | product_id |
| olist_sellers_dataset.csv | 0.17 | 3,095 | 4 | 0 | seller_id |
| product_category_name_translation.csv | 0.00 | 71 | 2 | 0 | product_category_name; product_category_name_english |

## 3. 表关系与覆盖情况

| 关系 | 子表行数 | 子键去重数 | 孤儿行 | 孤儿键 | 父键去重数 |
| --- | --- | --- | --- | --- | --- |
| orders.customer_id → customers.customer_id | 99,441 | 99,441 | 0 | 0 | 99,441 |
| order_items.order_id → orders.order_id | 112,650 | 98,666 | 0 | 0 | 99,441 |
| order_items.product_id → products.product_id | 112,650 | 32,951 | 0 | 0 | 32,951 |
| order_items.seller_id → sellers.seller_id | 112,650 | 3,095 | 0 | 0 | 3,095 |
| payments.order_id → orders.order_id | 103,886 | 99,440 | 0 | 0 | 99,441 |
| reviews.order_id → orders.order_id | 99,224 | 98,673 | 0 | 0 | 99,441 |
| products.product_category_name → translation.product_category_name | 32,341 | 73 | 13 | 2 | 71 |
| customers.zip_prefix → geolocation.zip_prefix | 99,441 | 14,994 | 278 | 157 | 19,015 |
| sellers.zip_prefix → geolocation.zip_prefix | 3,095 | 2,246 | 7 | 7 | 19,015 |

### 关键基数结论

- `customer_id` 有 99,441 个，逐行唯一，用于 `orders.customer_id` 外键；`customer_unique_id` 有 96,096 个，代表跨订单的同一客户。
- 有 2,997 个 `customer_unique_id` 对应多个 `customer_id`；单个客户最多对应 17 个 customer records。因此复购/客户生命周期必须使用 `customer_unique_id`。
- 订单总数 99,441；有商品明细的订单 98,666，其中 9,803 个订单包含多条 order items，单笔最多 21 条。
- 有支付记录的订单 99,440，其中 2,961 个订单包含多笔 payment records，单笔最多 29 条。
- 有评价记录的订单 98,673，其中 547 个订单包含多条 review records，单笔最多 3 条。
- `products.product_category_name` 的非空类别共 73 个；翻译表含 71 个葡萄牙语类别键；未匹配类别 2 个：pc_gamer, portateis_cozinha_e_preparadores_de_alimentos。
- 全局订单购买时间范围：2016-09-04 21:15:19 至 2018-10-17 17:30:18。

### 关系语义

- `orders` 是订单头；`order_items` 是订单商品明细，通过 `order_id` 一对多关联。
- `order_items.product_id` 关联 `products.product_id`；`order_items.seller_id` 关联 `sellers.seller_id`。
- `payments` 在订单粒度下可能多行，进入订单级分析前必须按 `order_id` 聚合或保留 payment sequence。
- `reviews` 不是严格一订单一行，不能直接与 order items 同时展开连接，否则可能产生行数乘积。
- `products.product_category_name` 通过葡萄牙语类别键左连接 `product_category_name_translation.product_category_name`，得到英文类别。
- geolocation 同一邮编前缀有多条坐标，不能把它当作唯一维表直接连接；需要先确定聚合或去重规则。

## 4. 每个 CSV 的详细画像

### olist_customers_dataset.csv

- 行数：99,441
- 列数：5
- 文件大小：9,033,957 bytes
- 完整重复行（超额）：0
- 处于完整重复组中的行：0

#### 字段、dtype 与缺失值

| 字段 | pandas dtype | 非空去重值 | 缺失数 | 缺失率 |
| --- | --- | --- | --- | --- |
| customer_id | str | 99,441 | 0 | 0.0000% |
| customer_unique_id | str | 96,096 | 0 | 0.0000% |
| customer_zip_code_prefix | int64 | 14,994 | 0 | 0.0000% |
| customer_city | str | 4,119 | 0 | 0.0000% |
| customer_state | str | 27 | 0 | 0.0000% |

#### 主键候选与重复

| 字段组合 | 非空唯一 | 组合去重数 | 缺失行 | 重复超额 | 重复组内行 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| customer_id | 是 | 99,441 | 0 | 0 | 0 | row identifier and orders foreign-key target |
| customer_unique_id | 否 | 96,096 | 0 | 3,345 | 6,342 | person-level identifier; expected to repeat across purchases |

#### 时间范围

无时间字段。

#### 前 3 行样例

```json
[
  {
    "customer_id": "06b8999e2fba1a1fbc88172c00ba8bc7",
    "customer_unique_id": "861eff4711a542e4b93843c6dd7febb0",
    "customer_zip_code_prefix": 14409,
    "customer_city": "franca",
    "customer_state": "SP"
  },
  {
    "customer_id": "18955e83d337fd6b2def6b18a428ac77",
    "customer_unique_id": "290c77bc529b7ac935b93aa66c333dc3",
    "customer_zip_code_prefix": 9790,
    "customer_city": "sao bernardo do campo",
    "customer_state": "SP"
  },
  {
    "customer_id": "4e7b3e00288586ebd08712fdd0374a03",
    "customer_unique_id": "060e732b5b29e8181a18229c7b0b2b5e",
    "customer_zip_code_prefix": 1151,
    "customer_city": "sao paulo",
    "customer_state": "SP"
  }
]
```

### olist_geolocation_dataset.csv

- 行数：1,000,163
- 列数：5
- 文件大小：61,273,883 bytes
- 完整重复行（超额）：261,831
- 处于完整重复组中的行：390,005

#### 字段、dtype 与缺失值

| 字段 | pandas dtype | 非空去重值 | 缺失数 | 缺失率 |
| --- | --- | --- | --- | --- |
| geolocation_zip_code_prefix | int64 | 19,015 | 0 | 0.0000% |
| geolocation_lat | float64 | 717,360 | 0 | 0.0000% |
| geolocation_lng | float64 | 717,613 | 0 | 0.0000% |
| geolocation_city | str | 8,011 | 0 | 0.0000% |
| geolocation_state | str | 27 | 0 | 0.0000% |

#### 主键候选与重复

| 字段组合 | 非空唯一 | 组合去重数 | 缺失行 | 重复超额 | 重复组内行 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| geolocation_zip_code_prefix | 否 | 19,015 | 0 | 981,148 | 999,120 | non-unique geographic lookup key |
| geolocation_zip_code_prefix, geolocation_lat, geolocation_lng, geolocation_city, geolocation_state | 否 | 738,332 | 0 | 261,831 | 390,005 | full geographic tuple |

#### 时间范围

无时间字段。

#### 前 3 行样例

```json
[
  {
    "geolocation_zip_code_prefix": 1037,
    "geolocation_lat": -23.54562128115268,
    "geolocation_lng": -46.63929204800168,
    "geolocation_city": "sao paulo",
    "geolocation_state": "SP"
  },
  {
    "geolocation_zip_code_prefix": 1046,
    "geolocation_lat": -23.54608112703553,
    "geolocation_lng": -46.64482029837157,
    "geolocation_city": "sao paulo",
    "geolocation_state": "SP"
  },
  {
    "geolocation_zip_code_prefix": 1046,
    "geolocation_lat": -23.54612896641469,
    "geolocation_lng": -46.64295148361138,
    "geolocation_city": "sao paulo",
    "geolocation_state": "SP"
  }
]
```

### olist_order_items_dataset.csv

- 行数：112,650
- 列数：7
- 文件大小：15,438,671 bytes
- 完整重复行（超额）：0
- 处于完整重复组中的行：0

#### 字段、dtype 与缺失值

| 字段 | pandas dtype | 非空去重值 | 缺失数 | 缺失率 |
| --- | --- | --- | --- | --- |
| order_id | str | 98,666 | 0 | 0.0000% |
| order_item_id | int64 | 21 | 0 | 0.0000% |
| product_id | str | 32,951 | 0 | 0.0000% |
| seller_id | str | 3,095 | 0 | 0.0000% |
| shipping_limit_date | str | 93,318 | 0 | 0.0000% |
| price | float64 | 5,968 | 0 | 0.0000% |
| freight_value | float64 | 6,999 | 0 | 0.0000% |

#### 主键候选与重复

| 字段组合 | 非空唯一 | 组合去重数 | 缺失行 | 重复超额 | 重复组内行 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| order_id, order_item_id | 是 | 112,650 | 0 | 0 | 0 | order-line composite key |

#### 时间范围

| 时间字段 | 有效值 | 缺失/无法解析 | 最小值 | 最大值 |
| --- | --- | --- | --- | --- |
| shipping_limit_date | 112,650 | 0 | 2016-09-19 00:15:34 | 2020-04-09 22:35:08 |

#### 前 3 行样例

```json
[
  {
    "order_id": "00010242fe8c5a6d1ba2dd792cb16214",
    "order_item_id": 1,
    "product_id": "4244733e06e7ecb4970a6e2683c13e61",
    "seller_id": "48436dade18ac8b2bce089ec2a041202",
    "shipping_limit_date": "2017-09-19 09:45:35",
    "price": 58.9,
    "freight_value": 13.29
  },
  {
    "order_id": "00018f77f2f0320c557190d7a144bdd3",
    "order_item_id": 1,
    "product_id": "e5f2d52b802189ee658865ca93d83a8f",
    "seller_id": "dd7ddc04e1b6c2c614352b383efe2d36",
    "shipping_limit_date": "2017-05-03 11:05:13",
    "price": 239.9,
    "freight_value": 19.93
  },
  {
    "order_id": "000229ec398224ef6ca0657da4fc703e",
    "order_item_id": 1,
    "product_id": "c777355d18b72b67abbeef9df44fd0fd",
    "seller_id": "5b51032eddd242adc84c38acab88f23d",
    "shipping_limit_date": "2018-01-18 14:48:30",
    "price": 199.0,
    "freight_value": 17.87
  }
]
```

### olist_order_payments_dataset.csv

- 行数：103,886
- 列数：5
- 文件大小：5,777,138 bytes
- 完整重复行（超额）：0
- 处于完整重复组中的行：0

#### 字段、dtype 与缺失值

| 字段 | pandas dtype | 非空去重值 | 缺失数 | 缺失率 |
| --- | --- | --- | --- | --- |
| order_id | str | 99,440 | 0 | 0.0000% |
| payment_sequential | int64 | 29 | 0 | 0.0000% |
| payment_type | str | 5 | 0 | 0.0000% |
| payment_installments | int64 | 24 | 0 | 0.0000% |
| payment_value | float64 | 29,077 | 0 | 0.0000% |

#### 主键候选与重复

| 字段组合 | 非空唯一 | 组合去重数 | 缺失行 | 重复超额 | 重复组内行 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| order_id, payment_sequential | 是 | 103,886 | 0 | 0 | 0 | payment-record composite key |

#### 时间范围

无时间字段。

#### 前 3 行样例

```json
[
  {
    "order_id": "b81ef226f3fe1789b1e8b2acac839d17",
    "payment_sequential": 1,
    "payment_type": "credit_card",
    "payment_installments": 8,
    "payment_value": 99.33
  },
  {
    "order_id": "a9810da82917af2d9aefd1278f1dcfa0",
    "payment_sequential": 1,
    "payment_type": "credit_card",
    "payment_installments": 1,
    "payment_value": 24.39
  },
  {
    "order_id": "25e8ea4e93396b6fa0d3dd708e76c1bd",
    "payment_sequential": 1,
    "payment_type": "credit_card",
    "payment_installments": 1,
    "payment_value": 65.71
  }
]
```

### olist_order_reviews_dataset.csv

- 行数：99,224
- 列数：7
- 文件大小：14,451,670 bytes
- 完整重复行（超额）：0
- 处于完整重复组中的行：0

#### 字段、dtype 与缺失值

| 字段 | pandas dtype | 非空去重值 | 缺失数 | 缺失率 |
| --- | --- | --- | --- | --- |
| review_id | str | 98,410 | 0 | 0.0000% |
| order_id | str | 98,673 | 0 | 0.0000% |
| review_score | int64 | 5 | 0 | 0.0000% |
| review_comment_title | str | 4,527 | 87,656 | 88.3415% |
| review_comment_message | str | 36,159 | 58,247 | 58.7025% |
| review_creation_date | str | 636 | 0 | 0.0000% |
| review_answer_timestamp | str | 98,248 | 0 | 0.0000% |

#### 主键候选与重复

| 字段组合 | 非空唯一 | 组合去重数 | 缺失行 | 重复超额 | 重复组内行 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| review_id | 否 | 98,410 | 0 | 814 | 1,603 | review identifier |
| order_id | 否 | 98,673 | 0 | 551 | 1,098 | order relationship; may repeat |
| review_id, order_id | 是 | 99,224 | 0 | 0 | 0 | review/order composite candidate |

#### 时间范围

| 时间字段 | 有效值 | 缺失/无法解析 | 最小值 | 最大值 |
| --- | --- | --- | --- | --- |
| review_creation_date | 99,224 | 0 | 2016-10-02 00:00:00 | 2018-08-31 00:00:00 |
| review_answer_timestamp | 99,224 | 0 | 2016-10-07 18:32:28 | 2018-10-29 12:27:35 |

#### 前 3 行样例

```json
[
  {
    "review_id": "7bc2406110b926393aa56f80a40eba40",
    "order_id": "73fc7af87114b39712e6da79b0a377eb",
    "review_score": 4,
    "review_comment_title": NaN,
    "review_comment_message": NaN,
    "review_creation_date": "2018-01-18 00:00:00",
    "review_answer_timestamp": "2018-01-18 21:46:59"
  },
  {
    "review_id": "80e641a11e56f04c1ad469d5645fdfde",
    "order_id": "a548910a1c6147796b98fdf73dbeba33",
    "review_score": 5,
    "review_comment_title": NaN,
    "review_comment_message": NaN,
    "review_creation_date": "2018-03-10 00:00:00",
    "review_answer_timestamp": "2018-03-11 03:05:13"
  },
  {
    "review_id": "228ce5500dc1d8e020d8d1322874b6f0",
    "order_id": "f9e4b658b201a9f2ecdecbb34bed034b",
    "review_score": 5,
    "review_comment_title": NaN,
    "review_comment_message": NaN,
    "review_creation_date": "2018-02-17 00:00:00",
    "review_answer_timestamp": "2018-02-18 14:36:24"
  }
]
```

### olist_orders_dataset.csv

- 行数：99,441
- 列数：8
- 文件大小：17,654,914 bytes
- 完整重复行（超额）：0
- 处于完整重复组中的行：0

#### 字段、dtype 与缺失值

| 字段 | pandas dtype | 非空去重值 | 缺失数 | 缺失率 |
| --- | --- | --- | --- | --- |
| order_id | str | 99,441 | 0 | 0.0000% |
| customer_id | str | 99,441 | 0 | 0.0000% |
| order_status | str | 8 | 0 | 0.0000% |
| order_purchase_timestamp | str | 98,875 | 0 | 0.0000% |
| order_approved_at | str | 90,733 | 160 | 0.1609% |
| order_delivered_carrier_date | str | 81,018 | 1,783 | 1.7930% |
| order_delivered_customer_date | str | 95,664 | 2,965 | 2.9817% |
| order_estimated_delivery_date | str | 459 | 0 | 0.0000% |

#### 主键候选与重复

| 字段组合 | 非空唯一 | 组合去重数 | 缺失行 | 重复超额 | 重复组内行 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| order_id | 是 | 99,441 | 0 | 0 | 0 | order header key |
| customer_id | 是 | 99,441 | 0 | 0 | 0 | customer-record foreign key; unique in this snapshot but not the person identifier |

#### 时间范围

| 时间字段 | 有效值 | 缺失/无法解析 | 最小值 | 最大值 |
| --- | --- | --- | --- | --- |
| order_purchase_timestamp | 99,441 | 0 | 2016-09-04 21:15:19 | 2018-10-17 17:30:18 |
| order_delivered_carrier_date | 97,658 | 1,783 | 2016-10-08 10:34:01 | 2018-09-11 19:48:28 |
| order_delivered_customer_date | 96,476 | 2,965 | 2016-10-11 13:46:32 | 2018-10-17 13:22:46 |
| order_estimated_delivery_date | 99,441 | 0 | 2016-09-30 00:00:00 | 2018-11-12 00:00:00 |

#### 前 3 行样例

```json
[
  {
    "order_id": "e481f51cbdc54678b7cc49136f2d6af7",
    "customer_id": "9ef432eb6251297304e76186b10a928d",
    "order_status": "delivered",
    "order_purchase_timestamp": "2017-10-02 10:56:33",
    "order_approved_at": "2017-10-02 11:07:15",
    "order_delivered_carrier_date": "2017-10-04 19:55:00",
    "order_delivered_customer_date": "2017-10-10 21:25:13",
    "order_estimated_delivery_date": "2017-10-18 00:00:00"
  },
  {
    "order_id": "53cdb2fc8bc7dce0b6741e2150273451",
    "customer_id": "b0830fb4747a6c6d20dea0b8c802d7ef",
    "order_status": "delivered",
    "order_purchase_timestamp": "2018-07-24 20:41:37",
    "order_approved_at": "2018-07-26 03:24:27",
    "order_delivered_carrier_date": "2018-07-26 14:31:00",
    "order_delivered_customer_date": "2018-08-07 15:27:45",
    "order_estimated_delivery_date": "2018-08-13 00:00:00"
  },
  {
    "order_id": "47770eb9100c2d0c44946d9cf07ec65d",
    "customer_id": "41ce2a54c0b03bf3443c3d931a367089",
    "order_status": "delivered",
    "order_purchase_timestamp": "2018-08-08 08:38:49",
    "order_approved_at": "2018-08-08 08:55:23",
    "order_delivered_carrier_date": "2018-08-08 13:50:00",
    "order_delivered_customer_date": "2018-08-17 18:06:29",
    "order_estimated_delivery_date": "2018-09-04 00:00:00"
  }
]
```

### olist_products_dataset.csv

- 行数：32,951
- 列数：9
- 文件大小：2,379,446 bytes
- 完整重复行（超额）：0
- 处于完整重复组中的行：0

#### 字段、dtype 与缺失值

| 字段 | pandas dtype | 非空去重值 | 缺失数 | 缺失率 |
| --- | --- | --- | --- | --- |
| product_id | str | 32,951 | 0 | 0.0000% |
| product_category_name | str | 73 | 610 | 1.8512% |
| product_name_lenght | float64 | 66 | 610 | 1.8512% |
| product_description_lenght | float64 | 2,960 | 610 | 1.8512% |
| product_photos_qty | float64 | 19 | 610 | 1.8512% |
| product_weight_g | float64 | 2,204 | 2 | 0.0061% |
| product_length_cm | float64 | 99 | 2 | 0.0061% |
| product_height_cm | float64 | 102 | 2 | 0.0061% |
| product_width_cm | float64 | 95 | 2 | 0.0061% |

#### 主键候选与重复

| 字段组合 | 非空唯一 | 组合去重数 | 缺失行 | 重复超额 | 重复组内行 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| product_id | 是 | 32,951 | 0 | 0 | 0 | product key |

#### 时间范围

无时间字段。

#### 前 3 行样例

```json
[
  {
    "product_id": "1e9e8ef04dbcff4541ed26657ea517e5",
    "product_category_name": "perfumaria",
    "product_name_lenght": 40.0,
    "product_description_lenght": 287.0,
    "product_photos_qty": 1.0,
    "product_weight_g": 225.0,
    "product_length_cm": 16.0,
    "product_height_cm": 10.0,
    "product_width_cm": 14.0
  },
  {
    "product_id": "3aa071139cb16b67ca9e5dea641aaa2f",
    "product_category_name": "artes",
    "product_name_lenght": 44.0,
    "product_description_lenght": 276.0,
    "product_photos_qty": 1.0,
    "product_weight_g": 1000.0,
    "product_length_cm": 30.0,
    "product_height_cm": 18.0,
    "product_width_cm": 20.0
  },
  {
    "product_id": "96bd76ec8810374ed1b65e291975717f",
    "product_category_name": "esporte_lazer",
    "product_name_lenght": 46.0,
    "product_description_lenght": 250.0,
    "product_photos_qty": 1.0,
    "product_weight_g": 154.0,
    "product_length_cm": 18.0,
    "product_height_cm": 9.0,
    "product_width_cm": 15.0
  }
]
```

### olist_sellers_dataset.csv

- 行数：3,095
- 列数：4
- 文件大小：174,703 bytes
- 完整重复行（超额）：0
- 处于完整重复组中的行：0

#### 字段、dtype 与缺失值

| 字段 | pandas dtype | 非空去重值 | 缺失数 | 缺失率 |
| --- | --- | --- | --- | --- |
| seller_id | str | 3,095 | 0 | 0.0000% |
| seller_zip_code_prefix | int64 | 2,246 | 0 | 0.0000% |
| seller_city | str | 611 | 0 | 0.0000% |
| seller_state | str | 23 | 0 | 0.0000% |

#### 主键候选与重复

| 字段组合 | 非空唯一 | 组合去重数 | 缺失行 | 重复超额 | 重复组内行 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| seller_id | 是 | 3,095 | 0 | 0 | 0 | seller key |

#### 时间范围

无时间字段。

#### 前 3 行样例

```json
[
  {
    "seller_id": "3442f8959a84dea7ee197c632cb2df15",
    "seller_zip_code_prefix": 13023,
    "seller_city": "campinas",
    "seller_state": "SP"
  },
  {
    "seller_id": "d1b65fc7debc3361ea86b5f14c68d2e2",
    "seller_zip_code_prefix": 13844,
    "seller_city": "mogi guacu",
    "seller_state": "SP"
  },
  {
    "seller_id": "ce3ad9de960102d0677a81f5d0bb7b2d",
    "seller_zip_code_prefix": 20031,
    "seller_city": "rio de janeiro",
    "seller_state": "RJ"
  }
]
```

### product_category_name_translation.csv

- 行数：71
- 列数：2
- 文件大小：2,613 bytes
- 完整重复行（超额）：0
- 处于完整重复组中的行：0

#### 字段、dtype 与缺失值

| 字段 | pandas dtype | 非空去重值 | 缺失数 | 缺失率 |
| --- | --- | --- | --- | --- |
| product_category_name | str | 71 | 0 | 0.0000% |
| product_category_name_english | str | 71 | 0 | 0.0000% |

#### 主键候选与重复

| 字段组合 | 非空唯一 | 组合去重数 | 缺失行 | 重复超额 | 重复组内行 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| product_category_name | 是 | 71 | 0 | 0 | 0 | Portuguese category key |
| product_category_name_english | 是 | 71 | 0 | 0 | 0 | English category label |

#### 时间范围

无时间字段。

#### 前 3 行样例

```json
[
  {
    "product_category_name": "beleza_saude",
    "product_category_name_english": "health_beauty"
  },
  {
    "product_category_name": "informatica_acessorios",
    "product_category_name_english": "computers_accessories"
  },
  {
    "product_category_name": "automotivo",
    "product_category_name_english": "auto"
  }
]
```

## 5. 主要数据质量发现

- geolocation 表包含 261,831 条完整重复超额行，并且邮编前缀非唯一。
- orders 中无 order items 的订单有 775 个；无 payment records 的订单有 1 个；无 review records 的订单有 768 个。
- 订单交付/审批时间的缺失通常与 cancelled、unavailable 或未完成状态有关，不能无条件填充。
- review 标题和正文存在大量空值，这是可选文本字段，不应按数值缺失规则处理。
- products 的类别、名称/描述长度、图片数量和部分尺寸重量存在缺失；类别翻译应采用左连接保留未知类别。
- 数据使用匿名标识；`customer_unique_id` 是客户分析键，`customer_id` 是订单关联所使用的 customer record 键。

### 各表非零缺失字段

- `olist_order_reviews_dataset.csv`：review_comment_title 87,656 (88.34%); review_comment_message 58,247 (58.70%)
- `olist_orders_dataset.csv`：order_approved_at 160 (0.16%); order_delivered_carrier_date 1,783 (1.79%); order_delivered_customer_date 2,965 (2.98%)
- `olist_products_dataset.csv`：product_category_name 610 (1.85%); product_name_lenght 610 (1.85%); product_description_lenght 610 (1.85%); product_photos_qty 610 (1.85%); product_weight_g 2 (0.01%); product_length_cm 2 (0.01%); product_height_cm 2 (0.01%); product_width_cm 2 (0.01%)

## 6. 后续 ETL 注意事项

1. 明确事实粒度：orders 为订单头，order_items 为商品明细；计算订单数必须 distinct order_id。
2. 客户复购、生命周期和 RFM 使用 customer_unique_id；orders 仍通过 customer_id 关联 customers。
3. payment 与 review 在 order_id 下都可能多行，应分别预聚合后再与订单/商品事实组合，避免笛卡尔放大。
4. 商品类别翻译使用 left join，保留 products 中的空类别或未匹配类别，并记录映射覆盖率。
5. geolocation 需要按邮编前缀建立明确的去重/中心点规则后才能作为维表使用。
6. 订单状态决定销售确认、取消、不可用和交付时间缺失的解释；下一阶段必须先制定收入、订单和交付指标口径。
7. 原始金额是 BRL，不能直接进入现有 TWD 指标体系；币种隔离或转换规则必须在下一阶段显式设计。
8. 时间字段没有时区信息；接入前需记录巴西业务时区假设，避免与现有 Asia/Taipei 日历混用。
9. 保留原始 CSV 不变，并在处理层记录数据集版本、下载日期和文件校验信息。
