# Data Setup

## Dataset

The Olist pipeline uses the **Brazilian E-Commerce Public Dataset by Olist**, published on Kaggle as [`olistbr/brazilian-ecommerce`](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).

It contains historical public marketplace data for orders, customers, order items, products, sellers, payments, reviews, geolocation, and product-category translations. It is not internal company data and does not represent a live production system.

## Why the Raw Data Is Not Stored in Git

The raw dataset and generated SQLite database are excluded from source control because they are downloadable/generated artifacts and add substantial repository size. The source code, table contracts, validation logic, and build instructions remain version controlled so another user can reproduce the data layers.

Git-ignored locations:

```text
data/raw/olist/*.csv
data/olist_analytics.sqlite
dashboard/powerbi_data/olist_*.csv
```

## Download

Install and authenticate the official Kaggle CLI, then run from the repository root:

```powershell
New-Item -ItemType Directory -Force data\raw\olist
.\.venv\Scripts\kaggle.exe datasets download `
  -d olistbr/brazilian-ecommerce `
  -p data\raw\olist `
  --unzip
```

Expected files:

```text
data/raw/olist/olist_customers_dataset.csv
data/raw/olist/olist_geolocation_dataset.csv
data/raw/olist/olist_order_items_dataset.csv
data/raw/olist/olist_order_payments_dataset.csv
data/raw/olist/olist_order_reviews_dataset.csv
data/raw/olist/olist_orders_dataset.csv
data/raw/olist/olist_products_dataset.csv
data/raw/olist/olist_sellers_dataset.csv
data/raw/olist/product_category_name_translation.csv
```

Kaggle credentials must remain in the user's normal Kaggle configuration directory. Do not copy credentials, tokens, or account files into this repository.

## Rebuild the Data Layers

Run the following commands from the repository root:

```powershell
.\.venv\Scripts\python.exe -m etl.olist.load_ods
.\.venv\Scripts\python.exe -m etl.olist.build_dwd
.\.venv\Scripts\python.exe -m etl.olist.build_analytics
```

The commands produce one local database:

```text
data/olist_analytics.sqlite
```

It contains:

- ODS copies of the nine source files with technical lineage columns;
- DWD dimensions, customer identity bridge, and independent fact tables;
- lightweight business marts for overview, monthly, customer RFM, segments, and categories.

The Analytics command also creates Power BI-ready CSV files in `dashboard/powerbi_data/`.

## Validation

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Validation covers source files, ODS row counts and hashes, DWD primary/foreign keys and grains, customer identity, GMV duplication risk, analytics reconciliation, RFM grain, metric ranges, and Power BI legacy artifact contracts.

## Separate Legacy Data

`data/analytics.sqlite` and `data/processed/` belong to the Synthetic V1.1 prototype. The Olist pipeline does not overwrite that database or reuse synthetic users, orders, advertising, costs, or currencies.
