"""SQLite schema contracts for the Olist DWD layer."""

from __future__ import annotations


DWD_TABLES: tuple[str, ...] = (
    "dim_customer",
    "dim_product",
    "dim_seller",
    "dim_date",
    "bridge_customer_identity",
    "fact_orders",
    "fact_order_items",
    "fact_payments",
    "fact_reviews",
)

DWD_DROP_ORDER: tuple[str, ...] = (
    "fact_reviews",
    "fact_payments",
    "fact_order_items",
    "fact_orders",
    "bridge_customer_identity",
    "dim_date",
    "dim_seller",
    "dim_product",
    "dim_customer",
)

DWD_PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "dim_customer": ("customer_unique_id",),
    "dim_product": ("product_id",),
    "dim_seller": ("seller_id",),
    "dim_date": ("date_key",),
    "bridge_customer_identity": ("customer_id",),
    "fact_orders": ("order_id",),
    "fact_order_items": ("order_id", "order_item_id"),
    "fact_payments": ("order_id", "payment_sequential"),
    "fact_reviews": ("review_id",),
}

REQUIRED_ODS_TABLES: tuple[str, ...] = (
    "ods_olist_customers",
    "ods_olist_geolocation",
    "ods_olist_order_items",
    "ods_olist_order_payments",
    "ods_olist_order_reviews",
    "ods_olist_orders",
    "ods_olist_products",
    "ods_olist_sellers",
    "ods_olist_category_translation",
    "dataset_metadata",
)


CREATE_DWD_SQL = """
CREATE TABLE dim_customer (
    customer_unique_id TEXT PRIMARY KEY,
    preferred_customer_zip_code_prefix INTEGER,
    preferred_customer_city TEXT,
    preferred_customer_state TEXT,
    customer_record_count INTEGER NOT NULL CHECK (customer_record_count > 0),
    first_order_date TEXT,
    last_order_date TEXT,
    total_order_count INTEGER NOT NULL CHECK (total_order_count >= 0),
    delivered_order_count INTEGER NOT NULL CHECK (delivered_order_count >= 0),
    source_system TEXT NOT NULL CHECK (source_system = 'olist'),
    data_mode TEXT NOT NULL CHECK (data_mode = 'olist_real'),
    _dwd_build_id TEXT NOT NULL,
    _built_at TEXT NOT NULL
);

CREATE TABLE dim_product (
    product_id TEXT PRIMARY KEY,
    category_pt TEXT,
    category_en TEXT,
    category_translation_status TEXT NOT NULL
        CHECK (category_translation_status IN ('translated', 'untranslated', 'missing')),
    product_name_length REAL,
    product_description_length REAL,
    product_photos_qty REAL,
    product_weight_g REAL,
    product_length_cm REAL,
    product_height_cm REAL,
    product_width_cm REAL,
    source_system TEXT NOT NULL CHECK (source_system = 'olist'),
    data_mode TEXT NOT NULL CHECK (data_mode = 'olist_real'),
    _dwd_build_id TEXT NOT NULL,
    _built_at TEXT NOT NULL
);

CREATE TABLE dim_seller (
    seller_id TEXT PRIMARY KEY,
    seller_zip_code_prefix INTEGER NOT NULL,
    seller_city TEXT NOT NULL,
    seller_state TEXT NOT NULL,
    geography_match_status TEXT NOT NULL
        CHECK (geography_match_status IN ('matched', 'unmatched')),
    source_system TEXT NOT NULL CHECK (source_system = 'olist'),
    data_mode TEXT NOT NULL CHECK (data_mode = 'olist_real'),
    _dwd_build_id TEXT NOT NULL,
    _built_at TEXT NOT NULL
);

CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,
    calendar_date TEXT NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    quarter TEXT NOT NULL,
    month TEXT NOT NULL,
    month_number INTEGER NOT NULL CHECK (month_number BETWEEN 1 AND 12),
    week INTEGER NOT NULL,
    weekday INTEGER NOT NULL CHECK (weekday BETWEEN 1 AND 7),
    is_weekend INTEGER NOT NULL CHECK (is_weekend IN (0, 1)),
    data_mode TEXT NOT NULL CHECK (data_mode = 'olist_real'),
    _dwd_build_id TEXT NOT NULL,
    _built_at TEXT NOT NULL
);

CREATE TABLE bridge_customer_identity (
    customer_id TEXT PRIMARY KEY,
    customer_unique_id TEXT NOT NULL,
    customer_zip_code_prefix INTEGER NOT NULL,
    customer_city TEXT NOT NULL,
    customer_state TEXT NOT NULL,
    geography_match_status TEXT NOT NULL
        CHECK (geography_match_status IN ('matched', 'unmatched')),
    source_file TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    load_batch_id TEXT NOT NULL,
    data_mode TEXT NOT NULL CHECK (data_mode = 'olist_real'),
    _dwd_build_id TEXT NOT NULL,
    _built_at TEXT NOT NULL,
    FOREIGN KEY (customer_unique_id) REFERENCES dim_customer(customer_unique_id)
);

CREATE TABLE fact_orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    customer_unique_id TEXT NOT NULL,
    order_status TEXT NOT NULL,
    purchase_timestamp TEXT NOT NULL,
    approved_timestamp TEXT,
    delivered_carrier_timestamp TEXT,
    delivered_timestamp TEXT,
    estimated_delivery_timestamp TEXT NOT NULL,
    purchase_date_key INTEGER NOT NULL,
    item_count INTEGER NOT NULL CHECK (item_count >= 0),
    payment_record_count INTEGER NOT NULL CHECK (payment_record_count >= 0),
    review_record_count INTEGER NOT NULL CHECK (review_record_count >= 0),
    has_items INTEGER NOT NULL CHECK (has_items IN (0, 1)),
    has_payment INTEGER NOT NULL CHECK (has_payment IN (0, 1)),
    has_review INTEGER NOT NULL CHECK (has_review IN (0, 1)),
    currency_code TEXT NOT NULL CHECK (currency_code = 'BRL'),
    source_file TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    load_batch_id TEXT NOT NULL,
    data_mode TEXT NOT NULL CHECK (data_mode = 'olist_real'),
    _dwd_build_id TEXT NOT NULL,
    _built_at TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES bridge_customer_identity(customer_id),
    FOREIGN KEY (customer_unique_id) REFERENCES dim_customer(customer_unique_id),
    FOREIGN KEY (purchase_date_key) REFERENCES dim_date(date_key)
);

CREATE TABLE fact_order_items (
    order_id TEXT NOT NULL,
    order_item_id INTEGER NOT NULL,
    product_id TEXT NOT NULL,
    seller_id TEXT NOT NULL,
    price_brl REAL NOT NULL CHECK (price_brl >= 0),
    freight_value_brl REAL NOT NULL CHECK (freight_value_brl >= 0),
    shipping_limit_date TEXT NOT NULL,
    currency_code TEXT NOT NULL CHECK (currency_code = 'BRL'),
    source_file TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    load_batch_id TEXT NOT NULL,
    data_mode TEXT NOT NULL CHECK (data_mode = 'olist_real'),
    _dwd_build_id TEXT NOT NULL,
    _built_at TEXT NOT NULL,
    PRIMARY KEY (order_id, order_item_id),
    FOREIGN KEY (order_id) REFERENCES fact_orders(order_id),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id),
    FOREIGN KEY (seller_id) REFERENCES dim_seller(seller_id)
);

CREATE TABLE fact_payments (
    order_id TEXT NOT NULL,
    payment_sequential INTEGER NOT NULL,
    payment_type TEXT NOT NULL,
    payment_installments INTEGER NOT NULL,
    payment_value_brl REAL NOT NULL CHECK (payment_value_brl >= 0),
    currency_code TEXT NOT NULL CHECK (currency_code = 'BRL'),
    source_file TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    load_batch_id TEXT NOT NULL,
    data_mode TEXT NOT NULL CHECK (data_mode = 'olist_real'),
    _dwd_build_id TEXT NOT NULL,
    _built_at TEXT NOT NULL,
    PRIMARY KEY (order_id, payment_sequential),
    FOREIGN KEY (order_id) REFERENCES fact_orders(order_id)
);

CREATE TABLE fact_reviews (
    review_id TEXT PRIMARY KEY,
    source_review_id TEXT NOT NULL,
    order_id TEXT NOT NULL,
    review_score INTEGER NOT NULL CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title TEXT,
    review_comment_message TEXT,
    review_creation_date TEXT NOT NULL,
    review_answer_timestamp TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    load_batch_id TEXT NOT NULL,
    data_mode TEXT NOT NULL CHECK (data_mode = 'olist_real'),
    _dwd_build_id TEXT NOT NULL,
    _built_at TEXT NOT NULL,
    UNIQUE (source_review_id, order_id),
    FOREIGN KEY (order_id) REFERENCES fact_orders(order_id)
);

CREATE INDEX ix_bridge_customer_unique
    ON bridge_customer_identity(customer_unique_id);
CREATE INDEX ix_fact_orders_customer_unique
    ON fact_orders(customer_unique_id);
CREATE INDEX ix_fact_orders_status_date
    ON fact_orders(order_status, purchase_date_key);
CREATE INDEX ix_fact_items_product
    ON fact_order_items(product_id);
CREATE INDEX ix_fact_items_seller
    ON fact_order_items(seller_id);
CREATE INDEX ix_fact_payments_order
    ON fact_payments(order_id);
CREATE INDEX ix_fact_reviews_order
    ON fact_reviews(order_id);
"""
