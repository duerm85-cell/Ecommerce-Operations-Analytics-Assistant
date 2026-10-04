"""Build the Olist DWD layer from the existing ODS snapshot."""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import OlistConfig, get_config
from .dwd_quality import DWDQualityReport, run_quality_checks
from .dwd_schema import (
    CREATE_DWD_SQL,
    DWD_DROP_ORDER,
    DWD_TABLES,
    REQUIRED_ODS_TABLES,
)
from .validator import sha256_file


LOGGER = logging.getLogger(__name__)


@dataclass
class DWDBuildSummary:
    build_id: str
    database_path: Path
    row_counts: dict[str, int]
    quality_checks: dict[str, str]
    synthetic_database_unchanged: bool
    build_status: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _build_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"dwd-{timestamp}-{uuid.uuid4().hex[:8]}"


def _database_hash(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


def _validate_ods_contract(connection: sqlite3.Connection) -> None:
    missing = sorted(set(REQUIRED_ODS_TABLES) - _table_names(connection))
    if missing:
        raise ValueError(f"missing ODS inputs: {', '.join(missing)}")
    metadata = dict(
        connection.execute(
            "SELECT metadata_key, metadata_value FROM dataset_metadata"
        ).fetchall()
    )
    if metadata.get("data_mode") != "olist_real":
        raise ValueError("dataset_metadata.data_mode must be olist_real")
    if metadata.get("currency_code") != "BRL":
        raise ValueError("dataset_metadata.currency_code must be BRL")


def _create_schema(connection: sqlite3.Connection) -> None:
    for table in DWD_DROP_ORDER:
        connection.execute(f'DROP TABLE IF EXISTS "{table}"')
    for statement in CREATE_DWD_SQL.split(";"):
        statement = statement.strip()
        if statement:
            connection.execute(statement)


def _insert_dim_customer(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    connection.execute(
        """
        INSERT INTO dim_customer (
            customer_unique_id,
            preferred_customer_zip_code_prefix,
            preferred_customer_city,
            preferred_customer_state,
            customer_record_count,
            first_order_date,
            last_order_date,
            total_order_count,
            delivered_order_count,
            source_system,
            data_mode,
            _dwd_build_id,
            _built_at
        )
        WITH ranked_records AS (
            SELECT
                c.customer_unique_id,
                c.customer_id,
                c.customer_zip_code_prefix,
                c.customer_city,
                c.customer_state,
                o.order_purchase_timestamp,
                ROW_NUMBER() OVER (
                    PARTITION BY c.customer_unique_id
                    ORDER BY o.order_purchase_timestamp DESC, c.customer_id
                ) AS record_rank
            FROM ods_olist_customers c
            LEFT JOIN ods_olist_orders o
              ON o.customer_id = c.customer_id
        ),
        customer_stats AS (
            SELECT
                c.customer_unique_id,
                COUNT(DISTINCT c.customer_id) AS customer_record_count,
                MIN(date(o.order_purchase_timestamp)) AS first_order_date,
                MAX(date(o.order_purchase_timestamp)) AS last_order_date,
                COUNT(DISTINCT o.order_id) AS total_order_count,
                COUNT(DISTINCT CASE
                    WHEN o.order_status = 'delivered' THEN o.order_id
                END) AS delivered_order_count
            FROM ods_olist_customers c
            LEFT JOIN ods_olist_orders o
              ON o.customer_id = c.customer_id
            GROUP BY c.customer_unique_id
        )
        SELECT
            r.customer_unique_id,
            r.customer_zip_code_prefix,
            r.customer_city,
            r.customer_state,
            s.customer_record_count,
            s.first_order_date,
            s.last_order_date,
            s.total_order_count,
            s.delivered_order_count,
            'olist',
            'olist_real',
            ?,
            ?
        FROM ranked_records r
        JOIN customer_stats s
          ON s.customer_unique_id = r.customer_unique_id
        WHERE r.record_rank = 1
        """,
        (build_id, built_at),
    )


def _insert_dim_product(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    connection.execute(
        """
        INSERT INTO dim_product (
            product_id,
            category_pt,
            category_en,
            category_translation_status,
            product_name_length,
            product_description_length,
            product_photos_qty,
            product_weight_g,
            product_length_cm,
            product_height_cm,
            product_width_cm,
            source_system,
            data_mode,
            _dwd_build_id,
            _built_at
        )
        SELECT
            p.product_id,
            p.product_category_name,
            t.product_category_name_english,
            CASE
                WHEN p.product_category_name IS NULL
                  OR TRIM(p.product_category_name) = '' THEN 'missing'
                WHEN t.product_category_name_english IS NULL THEN 'untranslated'
                ELSE 'translated'
            END,
            p.product_name_lenght,
            p.product_description_lenght,
            p.product_photos_qty,
            p.product_weight_g,
            p.product_length_cm,
            p.product_height_cm,
            p.product_width_cm,
            'olist',
            'olist_real',
            ?,
            ?
        FROM ods_olist_products p
        LEFT JOIN ods_olist_category_translation t
          ON t.product_category_name = p.product_category_name
        """,
        (build_id, built_at),
    )


def _insert_dim_seller(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    connection.execute(
        """
        INSERT INTO dim_seller (
            seller_id,
            seller_zip_code_prefix,
            seller_city,
            seller_state,
            geography_match_status,
            source_system,
            data_mode,
            _dwd_build_id,
            _built_at
        )
        SELECT
            s.seller_id,
            s.seller_zip_code_prefix,
            s.seller_city,
            s.seller_state,
            CASE WHEN g.geolocation_zip_code_prefix IS NOT NULL
                THEN 'matched' ELSE 'unmatched'
            END,
            'olist',
            'olist_real',
            ?,
            ?
        FROM ods_olist_sellers s
        LEFT JOIN (
            SELECT DISTINCT geolocation_zip_code_prefix
            FROM ods_olist_geolocation
        ) g
          ON g.geolocation_zip_code_prefix = s.seller_zip_code_prefix
        """,
        (build_id, built_at),
    )


def _insert_dim_date(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    connection.execute(
        """
        INSERT INTO dim_date (
            date_key,
            calendar_date,
            year,
            quarter,
            month,
            month_number,
            week,
            weekday,
            is_weekend,
            data_mode,
            _dwd_build_id,
            _built_at
        )
        WITH RECURSIVE source_dates(calendar_date) AS (
            SELECT date(order_purchase_timestamp) FROM ods_olist_orders
            UNION ALL
            SELECT date(order_approved_at) FROM ods_olist_orders
            UNION ALL
            SELECT date(order_delivered_carrier_date) FROM ods_olist_orders
            UNION ALL
            SELECT date(order_delivered_customer_date) FROM ods_olist_orders
            UNION ALL
            SELECT date(order_estimated_delivery_date) FROM ods_olist_orders
            UNION ALL
            SELECT date(shipping_limit_date) FROM ods_olist_order_items
            UNION ALL
            SELECT date(review_creation_date) FROM ods_olist_order_reviews
            UNION ALL
            SELECT date(review_answer_timestamp) FROM ods_olist_order_reviews
        ),
        bounds AS (
            SELECT MIN(calendar_date) AS start_date,
                   MAX(calendar_date) AS end_date
            FROM source_dates
            WHERE calendar_date IS NOT NULL
        ),
        dates(calendar_date, end_date) AS (
            SELECT start_date, end_date FROM bounds
            UNION ALL
            SELECT date(calendar_date, '+1 day'), end_date
            FROM dates
            WHERE calendar_date < end_date
        )
        SELECT
            CAST(strftime('%Y%m%d', calendar_date) AS INTEGER),
            calendar_date,
            CAST(strftime('%Y', calendar_date) AS INTEGER),
            'Q' || CAST(
                ((CAST(strftime('%m', calendar_date) AS INTEGER) - 1) / 3) + 1
                AS INTEGER
            ),
            strftime('%Y-%m', calendar_date),
            CAST(strftime('%m', calendar_date) AS INTEGER),
            CAST(strftime('%W', calendar_date) AS INTEGER),
            ((CAST(strftime('%w', calendar_date) AS INTEGER) + 6) % 7) + 1,
            CASE strftime('%w', calendar_date)
                WHEN '0' THEN 1
                WHEN '6' THEN 1
                ELSE 0
            END,
            'olist_real',
            ?,
            ?
        FROM dates
        """,
        (build_id, built_at),
    )


def _insert_bridge(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    connection.execute(
        """
        INSERT INTO bridge_customer_identity (
            customer_id,
            customer_unique_id,
            customer_zip_code_prefix,
            customer_city,
            customer_state,
            geography_match_status,
            source_file,
            source_row_number,
            load_batch_id,
            data_mode,
            _dwd_build_id,
            _built_at
        )
        SELECT
            c.customer_id,
            c.customer_unique_id,
            c.customer_zip_code_prefix,
            c.customer_city,
            c.customer_state,
            CASE WHEN g.geolocation_zip_code_prefix IS NOT NULL
                THEN 'matched' ELSE 'unmatched'
            END,
            c._source_file,
            c._source_row_number,
            c._load_batch_id,
            'olist_real',
            ?,
            ?
        FROM ods_olist_customers c
        LEFT JOIN (
            SELECT DISTINCT geolocation_zip_code_prefix
            FROM ods_olist_geolocation
        ) g
          ON g.geolocation_zip_code_prefix = c.customer_zip_code_prefix
        """,
        (build_id, built_at),
    )


def _insert_fact_orders(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    connection.execute(
        """
        INSERT INTO fact_orders (
            order_id,
            customer_id,
            customer_unique_id,
            order_status,
            purchase_timestamp,
            approved_timestamp,
            delivered_carrier_timestamp,
            delivered_timestamp,
            estimated_delivery_timestamp,
            purchase_date_key,
            item_count,
            payment_record_count,
            review_record_count,
            has_items,
            has_payment,
            has_review,
            currency_code,
            source_file,
            source_row_number,
            load_batch_id,
            data_mode,
            _dwd_build_id,
            _built_at
        )
        WITH item_counts AS (
            SELECT order_id, COUNT(*) AS item_count
            FROM ods_olist_order_items
            GROUP BY order_id
        ),
        payment_counts AS (
            SELECT order_id, COUNT(*) AS payment_record_count
            FROM ods_olist_order_payments
            GROUP BY order_id
        ),
        review_counts AS (
            SELECT order_id, COUNT(*) AS review_record_count
            FROM ods_olist_order_reviews
            GROUP BY order_id
        )
        SELECT
            o.order_id,
            o.customer_id,
            b.customer_unique_id,
            o.order_status,
            o.order_purchase_timestamp,
            o.order_approved_at,
            o.order_delivered_carrier_date,
            o.order_delivered_customer_date,
            o.order_estimated_delivery_date,
            CAST(strftime('%Y%m%d', o.order_purchase_timestamp) AS INTEGER),
            COALESCE(i.item_count, 0),
            COALESCE(p.payment_record_count, 0),
            COALESCE(r.review_record_count, 0),
            CASE WHEN i.item_count IS NULL THEN 0 ELSE 1 END,
            CASE WHEN p.payment_record_count IS NULL THEN 0 ELSE 1 END,
            CASE WHEN r.review_record_count IS NULL THEN 0 ELSE 1 END,
            'BRL',
            o._source_file,
            o._source_row_number,
            o._load_batch_id,
            'olist_real',
            ?,
            ?
        FROM ods_olist_orders o
        JOIN bridge_customer_identity b
          ON b.customer_id = o.customer_id
        LEFT JOIN item_counts i
          ON i.order_id = o.order_id
        LEFT JOIN payment_counts p
          ON p.order_id = o.order_id
        LEFT JOIN review_counts r
          ON r.order_id = o.order_id
        """,
        (build_id, built_at),
    )


def _insert_fact_order_items(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    connection.execute(
        """
        INSERT INTO fact_order_items (
            order_id,
            order_item_id,
            product_id,
            seller_id,
            price_brl,
            freight_value_brl,
            shipping_limit_date,
            currency_code,
            source_file,
            source_row_number,
            load_batch_id,
            data_mode,
            _dwd_build_id,
            _built_at
        )
        SELECT
            order_id,
            order_item_id,
            product_id,
            seller_id,
            price,
            freight_value,
            shipping_limit_date,
            'BRL',
            _source_file,
            _source_row_number,
            _load_batch_id,
            'olist_real',
            ?,
            ?
        FROM ods_olist_order_items
        """,
        (build_id, built_at),
    )


def _insert_fact_payments(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    connection.execute(
        """
        INSERT INTO fact_payments (
            order_id,
            payment_sequential,
            payment_type,
            payment_installments,
            payment_value_brl,
            currency_code,
            source_file,
            source_row_number,
            load_batch_id,
            data_mode,
            _dwd_build_id,
            _built_at
        )
        SELECT
            order_id,
            payment_sequential,
            payment_type,
            payment_installments,
            payment_value,
            'BRL',
            _source_file,
            _source_row_number,
            _load_batch_id,
            'olist_real',
            ?,
            ?
        FROM ods_olist_order_payments
        """,
        (build_id, built_at),
    )


def _insert_fact_reviews(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    connection.execute(
        """
        INSERT INTO fact_reviews (
            review_id,
            source_review_id,
            order_id,
            review_score,
            review_comment_title,
            review_comment_message,
            review_creation_date,
            review_answer_timestamp,
            source_file,
            source_row_number,
            load_batch_id,
            data_mode,
            _dwd_build_id,
            _built_at
        )
        SELECT
            review_id || ':' || order_id,
            review_id,
            order_id,
            review_score,
            review_comment_title,
            review_comment_message,
            review_creation_date,
            review_answer_timestamp,
            _source_file,
            _source_row_number,
            _load_batch_id,
            'olist_real',
            ?,
            ?
        FROM ods_olist_order_reviews
        """,
        (build_id, built_at),
    )


def _insert_dwd_rows(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    _insert_dim_customer(connection, build_id, built_at)
    _insert_dim_product(connection, build_id, built_at)
    _insert_dim_seller(connection, build_id, built_at)
    _insert_dim_date(connection, build_id, built_at)
    _insert_bridge(connection, build_id, built_at)
    _insert_fact_orders(connection, build_id, built_at)
    _insert_fact_order_items(connection, build_id, built_at)
    _insert_fact_payments(connection, build_id, built_at)
    _insert_fact_reviews(connection, build_id, built_at)


def _update_metadata(
    connection: sqlite3.Connection, build_id: str, built_at: str
) -> None:
    rows = (
        ("dwd_build_id", build_id),
        ("dwd_built_at", built_at),
        ("dwd_table_count", str(len(DWD_TABLES))),
        ("dwd_build_status", "completed"),
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


def build_dwd(
    config: OlistConfig | None = None,
    logger: logging.Logger | None = None,
) -> DWDBuildSummary:
    """Rebuild all nine DWD tables transactionally inside the Olist database."""

    cfg = config or get_config()
    log = logger or LOGGER
    if not cfg.ods_db_path.is_file():
        raise FileNotFoundError(f"Olist ODS database not found: {cfg.ods_db_path}")

    synthetic_db = cfg.project_root / "data" / "analytics.sqlite"
    synthetic_hash_before = _database_hash(synthetic_db)
    build_id = _build_id()
    built_at = _utc_now()

    connection = sqlite3.connect(cfg.ods_db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        _validate_ods_contract(connection)
        connection.execute("BEGIN IMMEDIATE")
        _create_schema(connection)
        _insert_dwd_rows(connection, build_id, built_at)
        _update_metadata(connection, build_id, built_at)
        report: DWDQualityReport = run_quality_checks(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        log.exception("[olist][dwd] build_status=failed build_id=%s", build_id)
        raise
    finally:
        connection.close()

    synthetic_unchanged = _database_hash(synthetic_db) == synthetic_hash_before
    if not synthetic_unchanged:
        raise RuntimeError("data/analytics.sqlite changed during DWD build")

    for table, count in report.row_counts.items():
        log.info("[olist][dwd] table=%s rows=%d", table, count)
    log.info(
        "[olist][dwd][complete] build_id=%s checks=%d/%d",
        build_id,
        len(report.checks),
        len(report.checks),
    )
    return DWDBuildSummary(
        build_id=build_id,
        database_path=cfg.ods_db_path,
        row_counts=report.row_counts,
        quality_checks=report.checks,
        synthetic_database_unchanged=True,
        build_status="completed",
    )


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the Olist DWD tables from the existing ODS snapshot"
    )
    parser.add_argument("--db-path", type=Path, default=None)
    args = parser.parse_args(argv)
    _configure_logging()
    config = get_config(ods_db_path=args.db_path)
    try:
        summary = build_dwd(config)
    except Exception as exc:
        LOGGER.error("[olist][dwd][complete] status=failed error=%s", exc)
        return 1
    print(
        json.dumps(
            {
                "build_id": summary.build_id,
                "database_path": str(summary.database_path),
                "row_counts": summary.row_counts,
                "quality_checks": summary.quality_checks,
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
