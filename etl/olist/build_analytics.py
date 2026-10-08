"""Build lightweight, Power BI-ready analytics marts from the Olist DWD layer."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .analytics_quality import AnalyticsQualityReport, run_quality_checks
from .analytics_schema import (
    ANALYTICS_PRIMARY_KEYS,
    ANALYTICS_TABLES,
    CREATE_ANALYTICS_SQL,
    REQUIRED_DWD_TABLES,
)
from .config import OlistConfig, get_config
from .validator import sha256_file


LOGGER = logging.getLogger(__name__)

ANALYTICS_EXPORTS: dict[str, str] = {
    "mart_business_overview": "olist_business_overview.csv",
    "mart_monthly_performance": "olist_monthly_performance.csv",
    "mart_customer_rfm": "olist_customer_rfm.csv",
    "mart_customer_segments": "olist_customer_segments.csv",
    "mart_category_performance": "olist_category_performance.csv",
    "analytics_metric_definitions": "olist_metric_definitions.csv",
}


METRIC_DEFINITIONS: tuple[tuple[str, ...], ...] = (
    (
        "orders",
        "Orders",
        "Distinct delivered orders.",
        "COUNT(DISTINCT order_id)",
        "order_status = delivered",
        "order",
        "fact_orders.order_id, fact_orders.order_status",
        "",
    ),
    (
        "purchasing_customers",
        "Purchasing Customers",
        "Distinct canonical customers with at least one delivered order.",
        "COUNT(DISTINCT customer_unique_id)",
        "order_status = delivered",
        "customer_unique_id",
        "fact_orders.customer_unique_id",
        "",
    ),
    (
        "repeat_customers",
        "Repeat Customers",
        "Canonical customers with at least two delivered orders.",
        "COUNT(customer_unique_id WHERE delivered_order_count >= 2)",
        "order_status = delivered",
        "customer_unique_id",
        "fact_orders.customer_unique_id, fact_orders.order_id",
        "",
    ),
    (
        "repeat_purchase_rate",
        "Repeat Purchase Rate",
        "Repeat customers divided by purchasing customers.",
        "repeat_customers / purchasing_customers",
        "order_status = delivered",
        "all-time or segment",
        "mart_customer_rfm.is_repeat_customer",
        "",
    ),
    (
        "merchandise_gmv_brl",
        "Merchandise GMV",
        "Item price value for delivered orders; freight and payments are excluded.",
        "SUM(fact_order_items.price_brl)",
        "order_status = delivered",
        "order item",
        "fact_order_items.price_brl, fact_orders.order_status",
        "BRL",
    ),
    (
        "paid_value_brl",
        "Paid Value",
        "Payment value associated with delivered orders; it is not merchandise GMV.",
        "SUM(fact_payments.payment_value_brl)",
        "order_status = delivered",
        "payment record",
        "fact_payments.payment_value_brl, fact_orders.order_status",
        "BRL",
    ),
    (
        "units_sold",
        "Units Sold",
        "Order-item records belonging to delivered orders.",
        "COUNT(fact_order_items order-item rows)",
        "order_status = delivered",
        "order item",
        "fact_order_items.order_id, fact_order_items.order_item_id",
        "",
    ),
    (
        "aov_brl",
        "Average Order Value",
        "Delivered merchandise GMV divided by delivered orders.",
        "merchandise_gmv_brl / orders",
        "order_status = delivered",
        "all-time or month",
        "fact_order_items.price_brl, fact_orders.order_id",
        "BRL",
    ),
    (
        "average_review_score",
        "Average Review Score",
        "Average source review score for delivered orders with reviews.",
        "AVG(fact_reviews.review_score)",
        "order_status = delivered",
        "review record",
        "fact_reviews.review_score, fact_reviews.order_id",
        "",
    ),
    (
        "cancel_rate",
        "Cancel Rate",
        "Canceled orders divided by all placed orders.",
        "COUNT(order_status = canceled) / COUNT(order_id)",
        "all placed orders",
        "all-time or month",
        "fact_orders.order_status, fact_orders.order_id",
        "",
    ),
    (
        "customer_recency_days",
        "Customer Recency",
        "Days from the deterministic as-of date to the latest delivered purchase.",
        "as_of_date - MAX(purchase_date)",
        "order_status = delivered",
        "customer_unique_id",
        "fact_orders.purchase_timestamp, fact_orders.customer_unique_id",
        "",
    ),
    (
        "customer_frequency",
        "Customer Frequency",
        "Distinct delivered orders per canonical customer.",
        "COUNT(DISTINCT order_id)",
        "order_status = delivered",
        "customer_unique_id",
        "fact_orders.order_id, fact_orders.customer_unique_id",
        "",
    ),
    (
        "customer_monetary_value_brl",
        "Customer Monetary Value",
        "Delivered merchandise GMV per canonical customer.",
        "SUM(fact_order_items.price_brl)",
        "order_status = delivered",
        "customer_unique_id",
        "fact_order_items.price_brl, fact_orders.customer_unique_id",
        "BRL",
    ),
    (
        "rfm_score",
        "RFM Score",
        "Three-digit deterministic score: recency percentile, frequency count band, monetary percentile.",
        "100 * r_score + 10 * f_score + m_score",
        "order_status = delivered",
        "customer_unique_id",
        "mart_customer_rfm.r_score, f_score, m_score",
        "",
    ),
    (
        "freight_ratio",
        "Freight Ratio",
        "Freight value divided by merchandise GMV for delivered category items.",
        "SUM(freight_value_brl) / SUM(price_brl)",
        "order_status = delivered",
        "category",
        "fact_order_items.freight_value_brl, fact_order_items.price_brl",
        "",
    ),
    (
        "low_rating_rate",
        "Low Rating Rate",
        "Share of attributed review records with review score at or below two.",
        "COUNT(review_score <= 2) / COUNT(review records)",
        "delivered orders with category and review",
        "category",
        "fact_reviews.review_score, fact_order_items.product_id",
        "",
    ),
)


@dataclass
class AnalyticsBuildSummary:
    build_id: str
    database_path: Path
    row_counts: dict[str, int]
    quality_checks: dict[str, str]
    overview: dict[str, object]
    exported_files: dict[str, int]
    synthetic_database_unchanged: bool
    build_status: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _build_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"analytics-{timestamp}-{uuid.uuid4().hex[:8]}"


def _database_hash(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


def _validate_dwd_contract(connection: sqlite3.Connection) -> None:
    missing = sorted(set(REQUIRED_DWD_TABLES) - _table_names(connection))
    if missing:
        raise ValueError(f"missing DWD inputs: {', '.join(missing)}")
    metadata = dict(
        connection.execute(
            "SELECT metadata_key, metadata_value FROM dataset_metadata"
        ).fetchall()
    )
    if metadata.get("data_mode") != "olist_real":
        raise ValueError("dataset_metadata.data_mode must be olist_real")
    if metadata.get("currency_code") != "BRL":
        raise ValueError("dataset_metadata.currency_code must be BRL")
    if metadata.get("dwd_build_status") != "completed":
        raise ValueError("DWD build must be completed before analytics")


def _create_schema(connection: sqlite3.Connection) -> None:
    for table in reversed(ANALYTICS_TABLES):
        connection.execute(f'DROP TABLE IF EXISTS "{table}"')
    for statement in CREATE_ANALYTICS_SQL.split(";"):
        statement = statement.strip()
        if statement:
            connection.execute(statement)


def _insert_business_overview(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    connection.execute(
        """
        INSERT INTO mart_business_overview (
            snapshot_id, as_of_date, order_scope, total_placed_orders, orders,
            purchasing_customers, repeat_customers, repeat_purchase_rate,
            merchandise_gmv_brl, paid_value_brl, units_sold,
            freight_value_brl, aov_brl, average_review_score,
            canceled_orders, cancel_rate, currency_code, data_mode,
            _analytics_build_id, _built_at
        )
        WITH item_by_order AS (
            SELECT order_id,
                   COUNT(*) AS units_sold,
                   SUM(price_brl) AS merchandise_gmv_brl,
                   SUM(freight_value_brl) AS freight_value_brl
            FROM fact_order_items
            GROUP BY order_id
        ),
        payment_by_order AS (
            SELECT order_id, SUM(payment_value_brl) AS paid_value_brl
            FROM fact_payments
            GROUP BY order_id
        ),
        review_by_order AS (
            SELECT order_id,
                   SUM(review_score) AS review_score_sum,
                   COUNT(*) AS review_count
            FROM fact_reviews
            GROUP BY order_id
        ),
        order_level AS (
            SELECT o.order_id,
                   o.customer_unique_id,
                   o.order_status,
                   o.purchase_timestamp,
                   COALESCE(i.units_sold, 0) AS units_sold,
                   COALESCE(i.merchandise_gmv_brl, 0) AS merchandise_gmv_brl,
                   COALESCE(i.freight_value_brl, 0) AS freight_value_brl,
                   COALESCE(p.paid_value_brl, 0) AS paid_value_brl,
                   COALESCE(r.review_score_sum, 0) AS review_score_sum,
                   COALESCE(r.review_count, 0) AS review_count
            FROM fact_orders o
            LEFT JOIN item_by_order i ON i.order_id = o.order_id
            LEFT JOIN payment_by_order p ON p.order_id = o.order_id
            LEFT JOIN review_by_order r ON r.order_id = o.order_id
        ),
        customer_orders AS (
            SELECT customer_unique_id, COUNT(*) AS delivered_orders
            FROM order_level
            WHERE order_status = 'delivered'
            GROUP BY customer_unique_id
        ),
        summary AS (
            SELECT
                date(MAX(CASE WHEN order_status = 'delivered'
                              THEN purchase_timestamp END), '+1 day') AS as_of_date,
                COUNT(*) AS total_placed_orders,
                SUM(CASE WHEN order_status = 'delivered' THEN 1 ELSE 0 END) AS orders,
                COUNT(DISTINCT CASE WHEN order_status = 'delivered'
                                    THEN customer_unique_id END) AS purchasing_customers,
                SUM(CASE WHEN order_status = 'delivered'
                         THEN merchandise_gmv_brl ELSE 0 END) AS merchandise_gmv_brl,
                SUM(CASE WHEN order_status = 'delivered'
                         THEN paid_value_brl ELSE 0 END) AS paid_value_brl,
                SUM(CASE WHEN order_status = 'delivered'
                         THEN units_sold ELSE 0 END) AS units_sold,
                SUM(CASE WHEN order_status = 'delivered'
                         THEN freight_value_brl ELSE 0 END) AS freight_value_brl,
                SUM(CASE WHEN order_status = 'delivered'
                         THEN review_score_sum ELSE 0 END) AS review_score_sum,
                SUM(CASE WHEN order_status = 'delivered'
                         THEN review_count ELSE 0 END) AS review_count,
                SUM(CASE WHEN order_status = 'canceled' THEN 1 ELSE 0 END)
                    AS canceled_orders
            FROM order_level
        ),
        repeat_summary AS (
            SELECT SUM(CASE WHEN delivered_orders >= 2 THEN 1 ELSE 0 END)
                       AS repeat_customers
            FROM customer_orders
        )
        SELECT
            'olist_all_time',
            s.as_of_date,
            'delivered',
            s.total_placed_orders,
            s.orders,
            s.purchasing_customers,
            r.repeat_customers,
            1.0 * r.repeat_customers / NULLIF(s.purchasing_customers, 0),
            s.merchandise_gmv_brl,
            s.paid_value_brl,
            s.units_sold,
            s.freight_value_brl,
            1.0 * s.merchandise_gmv_brl / NULLIF(s.orders, 0),
            1.0 * s.review_score_sum / NULLIF(s.review_count, 0),
            s.canceled_orders,
            1.0 * s.canceled_orders / NULLIF(s.total_placed_orders, 0),
            'BRL',
            'olist_real',
            ?,
            ?
        FROM summary s
        CROSS JOIN repeat_summary r
        """,
        (build_id, built_at),
    )


def _insert_monthly_performance(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    connection.execute(
        """
        INSERT INTO mart_monthly_performance (
            month_key, total_placed_orders, orders, purchasing_customers,
            merchandise_gmv_brl, paid_value_brl, units_sold,
            freight_value_brl, aov_brl, average_review_score,
            canceled_orders, cancel_rate, currency_code, data_mode,
            _analytics_build_id, _built_at
        )
        WITH item_by_order AS (
            SELECT order_id,
                   COUNT(*) AS units_sold,
                   SUM(price_brl) AS merchandise_gmv_brl,
                   SUM(freight_value_brl) AS freight_value_brl
            FROM fact_order_items
            GROUP BY order_id
        ),
        payment_by_order AS (
            SELECT order_id, SUM(payment_value_brl) AS paid_value_brl
            FROM fact_payments
            GROUP BY order_id
        ),
        review_by_order AS (
            SELECT order_id,
                   SUM(review_score) AS review_score_sum,
                   COUNT(*) AS review_count
            FROM fact_reviews
            GROUP BY order_id
        ),
        order_level AS (
            SELECT substr(o.purchase_timestamp, 1, 7) AS month_key,
                   o.order_id,
                   o.customer_unique_id,
                   o.order_status,
                   COALESCE(i.units_sold, 0) AS units_sold,
                   COALESCE(i.merchandise_gmv_brl, 0) AS merchandise_gmv_brl,
                   COALESCE(i.freight_value_brl, 0) AS freight_value_brl,
                   COALESCE(p.paid_value_brl, 0) AS paid_value_brl,
                   COALESCE(r.review_score_sum, 0) AS review_score_sum,
                   COALESCE(r.review_count, 0) AS review_count
            FROM fact_orders o
            LEFT JOIN item_by_order i ON i.order_id = o.order_id
            LEFT JOIN payment_by_order p ON p.order_id = o.order_id
            LEFT JOIN review_by_order r ON r.order_id = o.order_id
        )
        SELECT
            month_key,
            COUNT(*) AS total_placed_orders,
            SUM(CASE WHEN order_status = 'delivered' THEN 1 ELSE 0 END),
            COUNT(DISTINCT CASE WHEN order_status = 'delivered'
                                THEN customer_unique_id END),
            SUM(CASE WHEN order_status = 'delivered'
                     THEN merchandise_gmv_brl ELSE 0 END),
            SUM(CASE WHEN order_status = 'delivered'
                     THEN paid_value_brl ELSE 0 END),
            SUM(CASE WHEN order_status = 'delivered'
                     THEN units_sold ELSE 0 END),
            SUM(CASE WHEN order_status = 'delivered'
                     THEN freight_value_brl ELSE 0 END),
            COALESCE(
                1.0 * SUM(CASE WHEN order_status = 'delivered'
                               THEN merchandise_gmv_brl ELSE 0 END)
                    / NULLIF(SUM(CASE WHEN order_status = 'delivered'
                                      THEN 1 ELSE 0 END), 0),
                0
            ),
            1.0 * SUM(CASE WHEN order_status = 'delivered'
                           THEN review_score_sum ELSE 0 END)
                / NULLIF(SUM(CASE WHEN order_status = 'delivered'
                                  THEN review_count ELSE 0 END), 0),
            SUM(CASE WHEN order_status = 'canceled' THEN 1 ELSE 0 END),
            1.0 * SUM(CASE WHEN order_status = 'canceled' THEN 1 ELSE 0 END)
                / COUNT(*),
            'BRL',
            'olist_real',
            ?,
            ?
        FROM order_level
        GROUP BY month_key
        ORDER BY month_key
        """,
        (build_id, built_at),
    )


def _insert_customer_rfm(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    connection.execute(
        """
        INSERT INTO mart_customer_rfm (
            customer_unique_id, as_of_date, last_purchase_date, recency_days,
            frequency, monetary_value_brl, orders_per_customer,
            is_repeat_customer, r_score, f_score, m_score, rfm_score,
            rfm_segment, currency_code, data_mode,
            _analytics_build_id, _built_at
        )
        WITH order_merchandise AS (
            SELECT order_id, SUM(price_brl) AS merchandise_gmv_brl
            FROM fact_order_items
            GROUP BY order_id
        ),
        settings AS (
            SELECT date(MAX(purchase_timestamp), '+1 day') AS as_of_date
            FROM fact_orders
            WHERE order_status = 'delivered'
        ),
        customer_values AS (
            SELECT
                o.customer_unique_id,
                s.as_of_date,
                MAX(date(o.purchase_timestamp)) AS last_purchase_date,
                CAST(julianday(s.as_of_date)
                     - julianday(MAX(date(o.purchase_timestamp))) AS INTEGER)
                    AS recency_days,
                COUNT(DISTINCT o.order_id) AS frequency,
                SUM(COALESCE(m.merchandise_gmv_brl, 0)) AS monetary_value_brl
            FROM fact_orders o
            CROSS JOIN settings s
            LEFT JOIN order_merchandise m ON m.order_id = o.order_id
            WHERE o.order_status = 'delivered'
            GROUP BY o.customer_unique_id, s.as_of_date
        ),
        percentiles AS (
            SELECT c.*,
                   PERCENT_RANK() OVER (
                       ORDER BY recency_days DESC
                   ) AS recency_percentile,
                   PERCENT_RANK() OVER (
                       ORDER BY monetary_value_brl ASC
                   ) AS monetary_percentile
            FROM customer_values c
        ),
        scored AS (
            SELECT p.*,
                   MIN(5, CAST(recency_percentile * 5 AS INTEGER) + 1)
                       AS r_score,
                   CASE
                       WHEN frequency >= 5 THEN 5
                       WHEN frequency = 4 THEN 4
                       WHEN frequency = 3 THEN 3
                       WHEN frequency = 2 THEN 2
                       ELSE 1
                   END AS f_score,
                   MIN(5, CAST(monetary_percentile * 5 AS INTEGER) + 1)
                       AS m_score
            FROM percentiles p
        ),
        segmented AS (
            SELECT s.*,
                   100 * r_score + 10 * f_score + m_score AS rfm_score,
                   CASE
                       WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4
                           THEN 'Champions'
                       WHEN r_score >= 3 AND f_score >= 4
                           THEN 'Loyal Customers'
                       WHEN r_score >= 4 AND f_score BETWEEN 2 AND 3
                           THEN 'Potential Loyalists'
                       WHEN r_score >= 4 AND f_score = 1
                           THEN 'New Customers'
                       WHEN m_score >= 4 AND f_score >= 2
                           THEN 'Big Spenders'
                       WHEN r_score <= 2 AND f_score >= 3
                           THEN 'At Risk'
                       WHEN r_score <= 2 AND f_score <= 2
                           THEN 'Hibernating'
                       ELSE 'Needs Attention'
                   END AS rfm_segment
            FROM scored s
        )
        SELECT
            customer_unique_id,
            as_of_date,
            last_purchase_date,
            recency_days,
            frequency,
            monetary_value_brl,
            1.0 * frequency,
            CASE WHEN frequency >= 2 THEN 1 ELSE 0 END,
            r_score,
            f_score,
            m_score,
            rfm_score,
            rfm_segment,
            'BRL',
            'olist_real',
            ?,
            ?
        FROM segmented
        """,
        (build_id, built_at),
    )


def _insert_customer_segments(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    connection.execute(
        """
        INSERT INTO mart_customer_segments (
            rfm_segment, customers, repeat_customers, repeat_purchase_rate,
            average_recency_days, average_frequency,
            total_monetary_value_brl, average_monetary_value_brl,
            customer_share, currency_code, data_mode,
            _analytics_build_id, _built_at
        )
        SELECT
            rfm_segment,
            COUNT(*),
            SUM(is_repeat_customer),
            1.0 * SUM(is_repeat_customer) / COUNT(*),
            AVG(recency_days),
            AVG(frequency),
            SUM(monetary_value_brl),
            AVG(monetary_value_brl),
            1.0 * COUNT(*) / (SELECT COUNT(*) FROM mart_customer_rfm),
            'BRL',
            'olist_real',
            ?,
            ?
        FROM mart_customer_rfm
        GROUP BY rfm_segment
        """,
        (build_id, built_at),
    )


def _insert_category_performance(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    connection.execute(
        """
        INSERT INTO mart_category_performance (
            category_id, category_pt, category_en, category_display_name,
            category_translation_status, orders, units_sold,
            merchandise_gmv_brl, average_item_price_brl, freight_value_brl,
            freight_ratio, average_review_score, low_rating_rate,
            currency_code, data_mode, _analytics_build_id, _built_at
        )
        WITH delivered_items AS (
            SELECT
                i.order_id,
                i.order_item_id,
                COALESCE(p.category_pt, '__missing__') AS category_id,
                p.category_pt,
                p.category_en,
                COALESCE(p.category_en, p.category_pt, 'Uncategorized')
                    AS category_display_name,
                p.category_translation_status,
                i.price_brl,
                i.freight_value_brl
            FROM fact_order_items i
            JOIN fact_orders o ON o.order_id = i.order_id
            JOIN dim_product p ON p.product_id = i.product_id
            WHERE o.order_status = 'delivered'
        ),
        item_summary AS (
            SELECT
                category_id,
                MAX(category_pt) AS category_pt,
                MAX(category_en) AS category_en,
                MAX(category_display_name) AS category_display_name,
                MAX(category_translation_status) AS category_translation_status,
                COUNT(DISTINCT order_id) AS orders,
                COUNT(*) AS units_sold,
                SUM(price_brl) AS merchandise_gmv_brl,
                AVG(price_brl) AS average_item_price_brl,
                SUM(freight_value_brl) AS freight_value_brl
            FROM delivered_items
            GROUP BY category_id
        ),
        order_category AS (
            SELECT DISTINCT order_id, category_id
            FROM delivered_items
        ),
        review_summary AS (
            SELECT
                oc.category_id,
                AVG(r.review_score) AS average_review_score,
                1.0 * SUM(CASE WHEN r.review_score <= 2 THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(r.review_id), 0) AS low_rating_rate
            FROM order_category oc
            LEFT JOIN fact_reviews r ON r.order_id = oc.order_id
            GROUP BY oc.category_id
        )
        SELECT
            i.category_id,
            i.category_pt,
            i.category_en,
            i.category_display_name,
            i.category_translation_status,
            i.orders,
            i.units_sold,
            i.merchandise_gmv_brl,
            i.average_item_price_brl,
            i.freight_value_brl,
            CASE WHEN i.merchandise_gmv_brl = 0 THEN 0
                 ELSE i.freight_value_brl / i.merchandise_gmv_brl END,
            r.average_review_score,
            r.low_rating_rate,
            'BRL',
            'olist_real',
            ?,
            ?
        FROM item_summary i
        LEFT JOIN review_summary r ON r.category_id = i.category_id
        """,
        (build_id, built_at),
    )


def _insert_metric_definitions(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    rows = [definition + (build_id, built_at) for definition in METRIC_DEFINITIONS]
    connection.executemany(
        """
        INSERT INTO analytics_metric_definitions (
            metric_name, display_name, definition, formula, order_scope,
            grain, source_fields, currency_code,
            _analytics_build_id, _built_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, NULLIF(?, ''), ?, ?)
        """,
        rows,
    )


def _insert_analytics_rows(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    _insert_business_overview(connection, build_id, built_at)
    _insert_monthly_performance(connection, build_id, built_at)
    _insert_customer_rfm(connection, build_id, built_at)
    _insert_customer_segments(connection, build_id, built_at)
    _insert_category_performance(connection, build_id, built_at)
    _insert_metric_definitions(connection, build_id, built_at)


def _update_metadata(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    as_of_date = connection.execute(
        "SELECT as_of_date FROM mart_business_overview"
    ).fetchone()[0]
    rows = (
        ("analytics_build_id", build_id),
        ("analytics_built_at", built_at),
        ("analytics_table_count", str(len(ANALYTICS_TABLES))),
        ("analytics_build_status", "completed"),
        ("analytics_order_scope", "delivered"),
        ("analytics_as_of_date", as_of_date),
        (
            "analytics_aov_definition",
            "delivered merchandise_gmv_brl / delivered orders",
        ),
        (
            "analytics_repeat_rate_definition",
            "customers with >=2 delivered orders / customers with >=1 delivered order",
        ),
    )
    connection.executemany(
        """
        INSERT INTO dataset_metadata(metadata_key, metadata_value)
        VALUES (?, ?)
        ON CONFLICT(metadata_key) DO UPDATE
        SET metadata_value = excluded.metadata_value
        """,
        rows,
    )


def _overview_dict(connection: sqlite3.Connection) -> dict[str, object]:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT * FROM mart_business_overview"
    ).fetchone()
    result = dict(row) if row else {}
    connection.row_factory = None
    return result


def export_powerbi_csv(
    database_path: Path,
    export_dir: Path,
) -> dict[str, int]:
    """Export analytics tables as stable UTF-8 CSV inputs for Power BI."""

    export_dir.mkdir(parents=True, exist_ok=True)
    row_counts: dict[str, int] = {}
    connection = sqlite3.connect(database_path)
    try:
        for table, filename in ANALYTICS_EXPORTS.items():
            order_by = ", ".join(
                f'"{column}"' for column in ANALYTICS_PRIMARY_KEYS[table]
            )
            cursor = connection.execute(
                f'SELECT * FROM "{table}" ORDER BY {order_by}'
            )
            target = export_dir / filename
            temporary = target.with_suffix(target.suffix + ".tmp")
            count = 0
            with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(column[0] for column in cursor.description)
                while True:
                    rows = cursor.fetchmany(10_000)
                    if not rows:
                        break
                    writer.writerows(rows)
                    count += len(rows)
            temporary.replace(target)
            row_counts[filename] = count
    finally:
        connection.close()
    return row_counts


def build_analytics(
    config: OlistConfig | None = None,
    logger: logging.Logger | None = None,
    export_dir: Path | None = None,
) -> AnalyticsBuildSummary:
    """Rebuild the six analytics tables transactionally from DWD."""

    cfg = config or get_config()
    log = logger or LOGGER
    if not cfg.ods_db_path.is_file():
        raise FileNotFoundError(f"Olist database not found: {cfg.ods_db_path}")

    synthetic_db = cfg.project_root / "data" / "analytics.sqlite"
    synthetic_hash_before = _database_hash(synthetic_db)
    build_id = _build_id()
    built_at = _utc_now()

    connection = sqlite3.connect(cfg.ods_db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        _validate_dwd_contract(connection)
        connection.execute("BEGIN IMMEDIATE")
        _create_schema(connection)
        _insert_analytics_rows(connection, build_id, built_at)
        _update_metadata(connection, build_id, built_at)
        report: AnalyticsQualityReport = run_quality_checks(connection)
        overview = _overview_dict(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        log.exception("[olist][analytics] build_status=failed build_id=%s", build_id)
        raise
    finally:
        connection.close()

    synthetic_unchanged = _database_hash(synthetic_db) == synthetic_hash_before
    if not synthetic_unchanged:
        raise RuntimeError("data/analytics.sqlite changed during analytics build")

    powerbi_dir = Path(
        export_dir or cfg.project_root / "dashboard" / "powerbi_data"
    ).resolve()
    exported_files = export_powerbi_csv(cfg.ods_db_path, powerbi_dir)

    for table, count in report.row_counts.items():
        log.info("[olist][analytics] table=%s rows=%d", table, count)
    log.info(
        "[olist][analytics][complete] build_id=%s checks=%d/%d",
        build_id,
        len(report.checks),
        len(report.checks),
    )
    return AnalyticsBuildSummary(
        build_id=build_id,
        database_path=cfg.ods_db_path,
        row_counts=report.row_counts,
        quality_checks=report.checks,
        overview=overview,
        exported_files=exported_files,
        synthetic_database_unchanged=True,
        build_status="completed",
    )


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build Olist analytics marts from the DWD layer"
    )
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--export-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    _configure_logging()
    config = get_config(ods_db_path=args.db_path)
    try:
        summary = build_analytics(config, export_dir=args.export_dir)
    except Exception as exc:
        LOGGER.error("[olist][analytics][complete] status=failed error=%s", exc)
        return 1
    print(
        json.dumps(
            {
                "build_id": summary.build_id,
                "database_path": str(summary.database_path),
                "row_counts": summary.row_counts,
                "quality_checks": summary.quality_checks,
                "overview": summary.overview,
                "exported_files": summary.exported_files,
                "synthetic_database_unchanged": summary.synthetic_database_unchanged,
                "build_status": summary.build_status,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
