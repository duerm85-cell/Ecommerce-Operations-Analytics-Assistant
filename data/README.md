# 数据准备

## 数据集

Olist 管道使用 Kaggle 上的 [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)，标识为 `olistbr/brazilian-ecommerce`。它是公开历史市场数据，不是企业内部数据或实时生产系统。

## 为什么原始数据不进入 Git

原始 CSV、生成的 SQLite 和 Power BI 导出 CSV 都可重新下载或构建，且体积较大，因此由 `.gitignore` 排除：

```text
data/raw/olist/*.csv
data/olist_analytics.sqlite
dashboard/powerbi_data/olist_*.csv
```

仓库保留表结构、校验、转换、指标定义和复现命令。

## 下载

安装并认证 Kaggle CLI 后，在仓库根目录运行：

```powershell
New-Item -ItemType Directory -Force data\raw\olist
.\.venv\Scripts\kaggle.exe datasets download `
  -d olistbr/brazilian-ecommerce `
  -p data\raw\olist `
  --unzip
```

需要以下 9 个文件：

```text
olist_customers_dataset.csv
olist_geolocation_dataset.csv
olist_order_items_dataset.csv
olist_order_payments_dataset.csv
olist_order_reviews_dataset.csv
olist_orders_dataset.csv
olist_products_dataset.csv
olist_sellers_dataset.csv
product_category_name_translation.csv
```

Kaggle 凭据必须保留在用户自己的 Kaggle 配置目录，不要复制 token 或账户文件到仓库。

## 构建 ODS、DWD 与 Analytics

```powershell
.\.venv\Scripts\python.exe -m etl.olist.load_ods
.\.venv\Scripts\python.exe -m etl.olist.build_dwd
.\.venv\Scripts\python.exe -m etl.olist.build_analytics
```

命令输出 `data/olist_analytics.sqlite`，其中包含：

- 9 个来源对齐的 ODS 表与技术 lineage；
- dimensions、customer identity bridge 与独立 fact tables；
- overview、monthly、customer RFM、segment 与 category marts；
- 供 Power BI 使用的 6 个稳定 UTF-8 CSV。

## 验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试覆盖源文件、hash、ODS 行数、DWD 主外键与粒度、客户身份、GMV 防放大、Analytics 对账、RFM 粒度和 Legacy 回归。

## 与 Synthetic 隔离

`data/analytics.sqlite` 与 `data/processed/` 属于 Legacy Synthetic。Olist 管道不会覆盖它们，也不复用其中的用户、订单、广告、成本或币种。
