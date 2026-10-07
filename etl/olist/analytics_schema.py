"""SQLite schema contracts for the lightweight Olist analytics layer."""

from __future__ import annotations


ANALYTICS_TABLES: tuple[str, ...] = (
    "mart_business_overview",
    "mart_monthly_performance",
    "mart_customer_rfm",
    "mart_customer_segments",
    "mart_category_performance",
    "analytics_metric_definitions",
)

ANALYTICS_PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "mart_business_overview": ("snapshot_id",),
    "mart_monthly_performance": ("month_key",),
    "mart_customer_rfm": ("customer_unique_id",),
    "mart_customer_segments": ("rfm_segment",),
    "mart_category_performance": ("category_id",),
    "analytics_metric_definitions": ("metric_name",),
}

REQUIRED_DWD_TABLES: tuple[str, ...] = (
    "dim_customer",
    "dim_product",
    "dim_seller",
    "dim_date",
    "bridge_customer_identity",
    "fact_orders",
    "fact_order_items",
    "fact_payments",
    "fact_reviews",
    "dataset_metadata",
)


CREATE_ANALYTICS_SQL = """
CREATE TABLE mart_business_overview (
    snapshot_id TEXT PRIMARY KEY CHECK (snapshot_id = 'olist_all_time'),
    as_of_date TEXT NOT NULL,
    order_scope TEXT NOT NULL CHECK (order_scope = 'delivered'),
    total_placed_orders INTEGER NOT NULL CHECK (total_placed_orders >= 0),
    orders INTEGER NOT NULL CHECK (orders >= 0),
    purchasing_customers INTEGER NOT NULL CHECK (purchasing_customers >= 0),
    repeat_customers INTEGER NOT NULL CHECK (repeat_customers >= 0),
    repeat_purchase_rate REAL NOT NULL CHECK (
        repeat_purchase_rate BETWEEN 0 AND 1
    ),
    merchandise_gmv_brl REAL NOT NULL CHECK (merchandise_gmv_brl >= 0),
    paid_value_brl REAL NOT NULL CHECK (paid_value_brl >= 0),
    units_sold INTEGER NOT NULL CHECK (units_sold >= 0),
    freight_value_brl REAL NOT NULL CHECK (freight_value_brl >= 0),
    aov_brl REAL NOT NULL CHECK (aov_brl >= 0),
    average_review_score REAL CHECK (average_review_score BETWEEN 1 AND 5),
    canceled_orders INTEGER NOT NULL CHECK (canceled_orders >= 0),
    cancel_rate REAL NOT NULL CHECK (cancel_rate BETWEEN 0 AND 1),
    currency_code TEXT NOT NULL CHECK (currency_code = 'BRL'),
    data_mode TEXT NOT NULL CHECK (data_mode = 'olist_real'),
    _analytics_build_id TEXT NOT NULL,
    _built_at TEXT NOT NULL
);

CREATE TABLE mart_monthly_performance (
    month_key TEXT PRIMARY KEY,
    total_placed_orders INTEGER NOT NULL CHECK (total_placed_orders >= 0),
    orders INTEGER NOT NULL CHECK (orders >= 0),
    purchasing_customers INTEGER NOT NULL CHECK (purchasing_customers >= 0),
    merchandise_gmv_brl REAL NOT NULL CHECK (merchandise_gmv_brl >= 0),
    paid_value_brl REAL NOT NULL CHECK (paid_value_brl >= 0),
    units_sold INTEGER NOT NULL CHECK (units_sold >= 0),
    freight_value_brl REAL NOT NULL CHECK (freight_value_brl >= 0),
    aov_brl REAL NOT NULL CHECK (aov_brl >= 0),
    average_review_score REAL CHECK (average_review_score BETWEEN 1 AND 5),
    canceled_orders INTEGER NOT NULL CHECK (canceled_orders >= 0),
    cancel_rate REAL NOT NULL CHECK (cancel_rate BETWEEN 0 AND 1),
    currency_code TEXT NOT NULL CHECK (currency_code = 'BRL'),
    data_mode TEXT NOT NULL CHECK (data_mode = 'olist_real'),
    _analytics_build_id TEXT NOT NULL,
    _built_at TEXT NOT NULL
);

CREATE TABLE mart_customer_rfm (
    customer_unique_id TEXT PRIMARY KEY,
    as_of_date TEXT NOT NULL,
    last_purchase_date TEXT NOT NULL,
    recency_days INTEGER NOT NULL CHECK (recency_days >= 0),
    frequency INTEGER NOT NULL CHECK (frequency > 0),
    monetary_value_brl REAL NOT NULL CHECK (monetary_value_brl >= 0),
    orders_per_customer REAL NOT NULL CHECK (orders_per_customer > 0),
    is_repeat_customer INTEGER NOT NULL CHECK (is_repeat_customer IN (0, 1)),
    r_score INTEGER NOT NULL CHECK (r_score BETWEEN 1 AND 5),
    f_score INTEGER NOT NULL CHECK (f_score BETWEEN 1 AND 5),
    m_score INTEGER NOT NULL CHECK (m_score BETWEEN 1 AND 5),
    rfm_score INTEGER NOT NULL CHECK (rfm_score BETWEEN 111 AND 555),
    rfm_segment TEXT NOT NULL,
    currency_code TEXT NOT NULL CHECK (currency_code = 'BRL'),
    data_mode TEXT NOT NULL CHECK (data_mode = 'olist_real'),
    _analytics_build_id TEXT NOT NULL,
    _built_at TEXT NOT NULL
);

CREATE TABLE mart_customer_segments (
    rfm_segment TEXT PRIMARY KEY,
    customers INTEGER NOT NULL CHECK (customers > 0),
    repeat_customers INTEGER NOT NULL CHECK (repeat_customers >= 0),
    repeat_purchase_rate REAL NOT NULL CHECK (
        repeat_purchase_rate BETWEEN 0 AND 1
    ),
    average_recency_days REAL NOT NULL CHECK (average_recency_days >= 0),
    average_frequency REAL NOT NULL CHECK (average_frequency > 0),
    total_monetary_value_brl REAL NOT NULL CHECK (
        total_monetary_value_brl >= 0
    ),
    average_monetary_value_brl REAL NOT NULL CHECK (
        average_monetary_value_brl >= 0
    ),
    customer_share REAL NOT NULL CHECK (customer_share BETWEEN 0 AND 1),
    currency_code TEXT NOT NULL CHECK (currency_code = 'BRL'),
    data_mode TEXT NOT NULL CHECK (data_mode = 'olist_real'),
    _analytics_build_id TEXT NOT NULL,
    _built_at TEXT NOT NULL
);

CREATE TABLE mart_category_performance (
    category_id TEXT PRIMARY KEY,
    category_pt TEXT,
    category_en TEXT,
    category_display_name TEXT NOT NULL,
    category_translation_status TEXT NOT NULL CHECK (
        category_translation_status IN ('translated', 'untranslated', 'missing')
    ),
    orders INTEGER NOT NULL CHECK (orders >= 0),
    units_sold INTEGER NOT NULL CHECK (units_sold >= 0),
    merchandise_gmv_brl REAL NOT NULL CHECK (merchandise_gmv_brl >= 0),
    average_item_price_brl REAL NOT NULL CHECK (average_item_price_brl >= 0),
    freight_value_brl REAL NOT NULL CHECK (freight_value_brl >= 0),
    freight_ratio REAL NOT NULL CHECK (freight_ratio >= 0),
    average_review_score REAL CHECK (average_review_score BETWEEN 1 AND 5),
    low_rating_rate REAL CHECK (low_rating_rate BETWEEN 0 AND 1),
    currency_code TEXT NOT NULL CHECK (currency_code = 'BRL'),
    data_mode TEXT NOT NULL CHECK (data_mode = 'olist_real'),
    _analytics_build_id TEXT NOT NULL,
    _built_at TEXT NOT NULL
);

CREATE TABLE analytics_metric_definitions (
    metric_name TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    definition TEXT NOT NULL,
    formula TEXT NOT NULL,
    order_scope TEXT NOT NULL,
    grain TEXT NOT NULL,
    source_fields TEXT NOT NULL,
    currency_code TEXT,
    _analytics_build_id TEXT NOT NULL,
    _built_at TEXT NOT NULL
);

CREATE INDEX ix_customer_rfm_segment
    ON mart_customer_rfm(rfm_segment);
CREATE INDEX ix_customer_rfm_monetary
    ON mart_customer_rfm(monetary_value_brl DESC);
CREATE INDEX ix_category_gmv
    ON mart_category_performance(merchandise_gmv_brl DESC);
"""
