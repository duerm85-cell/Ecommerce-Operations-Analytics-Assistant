# Public product data input

The `crawler` module provides a conservative input layer for public product-market data. It supports local CSV/ZIP files and directly accessible public CSV/ZIP URLs. It never logs in, uses cookies, solves CAPTCHA, rotates proxies, or bypasses access controls.

## Files

```text
crawler/
├── product_crawler.py                 public CSV/ZIP normalizer
├── public_product_collector.py        minimal public JSON reference collector
├── raw_data/
│   └── raw_products.csv               product ODS contract
└── README.md
```

The committed `raw_products.csv` contains only the required header. This preserves the validated Power BI baseline while making the external input contract explicit. When the file contains valid rows, `data/generate_data.py` automatically prefers those product attributes. When it is missing or header-only, the pipeline uses the original fixed-seed product generator.

## ODS contract

| Field | Rule |
|---|---|
| `product_id` | Non-empty and unique source product identifier |
| `product_name` | Non-empty public product title |
| `category` | Non-empty source category; mapped during cleaning to the project taxonomy |
| `price` | Positive numeric TWD price |
| `rating` | Numeric value greater than 0 and no greater than 5 |
| `review_count` | Non-negative integer |

Common source columns such as `asin`, `title`, `discounted_price`, `rating_stars`, and `rating_count` are recognized automatically. Use `--map canonical_field=source_column` for other schemas.

## Recommended source order

1. A license-compatible Kaggle or other public e-commerce dataset downloaded as CSV/ZIP.
2. A documented public dataset endpoint that is accessible without authentication.
3. A public webpage or API only after reviewing its terms and `robots.txt` rules.

One compatible field example is the Kaggle [Amazon Sales Dataset](https://www.kaggle.com/datasets/karkavelrajaj/amazon-sales-dataset), which exposes product ID, product name, category, price, rating and rating-count fields under CC BY-NC-SA 4.0. Dataset licenses and redistribution rights must be checked before committing any rows. Product sources should also match the project's merchandise domain and category taxonomy.

## Usage

Normalize a previously downloaded public dataset without making a network request:

```powershell
python crawler/product_crawler.py `
  --source-file C:\path\to\public_products.csv `
  --output crawler/raw_data/raw_products.csv
```

Normalize a direct public CSV or ZIP URL after reviewing its terms:

```powershell
python crawler/product_crawler.py `
  --source-url "https://data.example.org/public-products.csv" `
  --acknowledge-terms `
  --output crawler/raw_data/raw_products.csv
```

Map non-standard column names:

```powershell
python crawler/product_crawler.py `
  --source-file C:\path\to\products.csv `
  --map product_id=asin `
  --map product_name=title `
  --map rating=rating_stars `
  --map review_count=rating_count
```

All downstream prices are TWD. If a licensed source uses another currency, apply a reviewed conversion factor during ingestion and document its date and source:

```powershell
python crawler/product_crawler.py `
  --source-file C:\path\to\products_in_source_currency.csv `
  --price-multiplier 1.0
```

The example multiplier is intentionally neutral; do not claim a currency conversion unless the rate and effective date have been verified.

## Safety and failure behavior

- URL collection requires the explicit `--acknowledge-terms` flag.
- `robots.txt` must be readable and allow the request.
- Downloads are limited to 25 MB and use a descriptive user agent.
- Invalid rows are rejected; the command reports accepted and rejected counts.
- Invalid schemas or an entirely invalid dataset stop with a clear error.
- The module does not collect customer, transaction or advertising data.

For provenance boundaries and the complete data flow, see [docs/data_source.md](../docs/data_source.md).
