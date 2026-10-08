"""Quality checks for the Olist DWD layer."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Iterable

from .dwd_schema import DWD_PRIMARY_KEYS, DWD_TABLES, REQUIRED_ODS_TABLES


class DWDQualityError(ValueError):
    """Raised when a DWD contract or grain check fails."""


@dataclass
class DWDQualityReport:
    checks: dict[str, str]
    row_counts: dict[str, int]
    merchandise_value_brl: float

    @property
    def passed(self) -> bool:
        return all(value == "passed" for value in self.checks.values())


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


def _count(connection: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    return int(connection.execute(sql, params).fetchone()[0])


def _primary_key_unique(
    connection: sqlite3.Connection,
    table: str,
    columns: Iterable[str],
) -> bool:
    key_columns = list(columns)
    quoted = ", ".join(f'"{column}"' for column in key_columns)
    null_condition = " OR ".join(f'"{column}" IS NULL' for column in key_columns)
    nulls = _count(
        connection,
        f'SELECT COUNT(*) FROM "{table}" WHERE {null_condition}',
    )
    duplicates = _count(
        connection,
        f"""
        SELECT COUNT(*) FROM (
            SELECT {quoted}
            FROM "{table}"
            GROUP BY {quoted}
            HAVING COUNT(*) > 1
        )
        """,
    )
    return nulls == 0 and duplicates == 0


def _foreign_keys_valid(connection: sqlite3.Connection) -> bool:
    return not connection.execute("PRAGMA foreign_key_check").fetchall()


def _ods_row_counts_match(connection: sqlite3.Connection) -> bool:
    pairs = (
        ("dim_product", "ods_olist_products"),
        ("dim_seller", "ods_olist_sellers"),
        ("bridge_customer_identity", "ods_olist_customers"),
        ("fact_orders", "ods_olist_orders"),
        ("fact_order_items", "ods_olist_order_items"),
        ("fact_payments", "ods_olist_order_payments"),
        ("fact_reviews", "ods_olist_order_reviews"),
    )
    return all(
        _count(connection, f'SELECT COUNT(*) FROM "{dwd}"')
        == _count(connection, f'SELECT COUNT(*) FROM "{ods}"')
        for dwd, ods in pairs
    ) and _count(
        connection,
        "SELECT COUNT(*) FROM dim_customer",
    ) == _count(
        connection,
        "SELECT COUNT(DISTINCT customer_unique_id) FROM ods_olist_customers",
    )


def _bridge_mapping_valid(connection: sqlite3.Connection) -> bool:
    return (
        _count(
            connection,
            """
            SELECT COUNT(*)
            FROM bridge_customer_identity b
            JOIN ods_olist_customers c
              ON c.customer_id = b.customer_id
             AND c.customer_unique_id = b.customer_unique_id
            """,
        )
        == _count(connection, "SELECT COUNT(*) FROM bridge_customer_identity")
        and _count(
            connection,
            """
            SELECT COUNT(*)
            FROM fact_orders o
            JOIN bridge_customer_identity b
              ON b.customer_id = o.customer_id
             AND b.customer_unique_id = o.customer_unique_id
            """,
        )
        == _count(connection, "SELECT COUNT(*) FROM fact_orders")
    )


def _fact_grains_valid(connection: sqlite3.Connection) -> bool:
    return (
        _count(connection, "SELECT COUNT(*) FROM fact_orders")
        == _count(
            connection,
            "SELECT COUNT(DISTINCT order_id) FROM fact_orders",
        )
        and _count(connection, "SELECT COUNT(*) FROM fact_order_items")
        == _count(
            connection,
            """
            SELECT COUNT(*)
            FROM (
                SELECT order_id, order_item_id
                FROM fact_order_items
                GROUP BY order_id, order_item_id
            )
            """,
        )
        and _count(connection, "SELECT COUNT(*) FROM fact_payments")
        == _count(
            connection,
            """
            SELECT COUNT(*)
            FROM (
                SELECT order_id, payment_sequential
                FROM fact_payments
                GROUP BY order_id, payment_sequential
            )
            """,
        )
        and _count(connection, "SELECT COUNT(*) FROM fact_reviews")
        == _count(
            connection,
            "SELECT COUNT(DISTINCT review_id) FROM fact_reviews",
        )
    )


def _status_values_match_source(connection: sqlite3.Connection) -> bool:
    source = {
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT order_status FROM ods_olist_orders"
        ).fetchall()
    }
    dwd = {
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT order_status FROM fact_orders"
        ).fetchall()
    }
    return source == dwd and "completed" not in dwd and "refunded" not in dwd


def _currency_contract_valid(connection: sqlite3.Connection) -> bool:
    metadata = dict(
        connection.execute(
            "SELECT metadata_key, metadata_value FROM dataset_metadata"
        ).fetchall()
    )
    if metadata.get("currency_code") != "BRL":
        return False
    for table in ("fact_orders", "fact_order_items", "fact_payments"):
        values = {
            row[0]
            for row in connection.execute(
                f'SELECT DISTINCT currency_code FROM "{table}"'
            ).fetchall()
        }
        if values != {"BRL"}:
            return False
    return True


def _date_contract_valid(connection: sqlite3.Connection) -> bool:
    min_source, max_source = connection.execute(
        """
        SELECT MIN(calendar_date), MAX(calendar_date)
        FROM (
            SELECT date(order_purchase_timestamp) AS calendar_date
            FROM ods_olist_orders
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
        )
        WHERE calendar_date IS NOT NULL
        """
    ).fetchone()
    min_dwd, max_dwd = connection.execute(
        "SELECT MIN(calendar_date), MAX(calendar_date) FROM dim_date"
    ).fetchone()
    return min_source == min_dwd and max_source == max_dwd


def _gmv_join_safety_valid(connection: sqlite3.Connection) -> bool:
    direct_value = float(
        connection.execute(
            "SELECT COALESCE(SUM(price_brl), 0) FROM fact_order_items"
        ).fetchone()[0]
    )
    joined_value = float(
        connection.execute(
            """
            SELECT COALESCE(SUM(i.price_brl), 0)
            FROM fact_order_items i
            JOIN fact_orders o ON o.order_id = i.order_id
            JOIN dim_product p ON p.product_id = i.product_id
            JOIN dim_seller s ON s.seller_id = i.seller_id
            """
        ).fetchone()[0]
    )
    joined_rows = _count(
        connection,
        """
        SELECT COUNT(*)
        FROM fact_order_items i
        JOIN fact_orders o ON o.order_id = i.order_id
        JOIN dim_product p ON p.product_id = i.product_id
        JOIN dim_seller s ON s.seller_id = i.seller_id
        """,
    )
    item_rows = _count(connection, "SELECT COUNT(*) FROM fact_order_items")
    return joined_rows == item_rows and abs(direct_value - joined_value) < 0.000001


def _review_source_mapping_valid(connection: sqlite3.Connection) -> bool:
    return _count(
        connection,
        """
        SELECT COUNT(*)
        FROM fact_reviews r
        JOIN ods_olist_order_reviews s
          ON s.review_id = r.source_review_id
         AND s.order_id = r.order_id
        """,
    ) == _count(connection, "SELECT COUNT(*) FROM fact_reviews")


def quality_report(connection: sqlite3.Connection) -> DWDQualityReport:
    """Return a complete quality report without changing the database."""

    tables = _table_names(connection)
    all_expected = set(DWD_TABLES) | set(REQUIRED_ODS_TABLES)
    checks: dict[str, str] = {
        "dwd_tables_exist": "passed"
        if set(DWD_TABLES).issubset(tables)
        else "failed",
        "ods_inputs_exist": "passed"
        if set(REQUIRED_ODS_TABLES).issubset(tables)
        else "failed",
    }

    if checks["dwd_tables_exist"] == "passed":
        checks["primary_keys_unique"] = (
            "passed"
            if all(
                _primary_key_unique(connection, table, key)
                for table, key in DWD_PRIMARY_KEYS.items()
            )
            else "failed"
        )
        checks["foreign_keys_complete"] = (
            "passed" if _foreign_keys_valid(connection) else "failed"
        )
        checks["source_row_counts"] = (
            "passed" if _ods_row_counts_match(connection) else "failed"
        )
        checks["bridge_mapping"] = (
            "passed" if _bridge_mapping_valid(connection) else "failed"
        )
        checks["fact_grains"] = (
            "passed" if _fact_grains_valid(connection) else "failed"
        )
        checks["source_status_preserved"] = (
            "passed" if _status_values_match_source(connection) else "failed"
        )
        checks["currency_brl"] = (
            "passed" if _currency_contract_valid(connection) else "failed"
        )
        checks["date_range"] = (
            "passed" if _date_contract_valid(connection) else "failed"
        )
        checks["review_source_mapping"] = (
            "passed" if _review_source_mapping_valid(connection) else "failed"
        )
        checks["gmv_join_safety"] = (
            "passed" if _gmv_join_safety_valid(connection) else "failed"
        )

    row_counts = {}
    if set(DWD_TABLES).issubset(tables):
        row_counts = {
            table: _count(connection, f'SELECT COUNT(*) FROM "{table}"')
            for table in DWD_TABLES
        }
    merchandise_value = 0.0
    if "fact_order_items" in tables:
        merchandise_value = float(
            connection.execute(
                "SELECT COALESCE(SUM(price_brl), 0) FROM fact_order_items"
            ).fetchone()[0]
        )

    return DWDQualityReport(
        checks=checks,
        row_counts=row_counts,
        merchandise_value_brl=merchandise_value,
    )


def run_quality_checks(connection: sqlite3.Connection) -> DWDQualityReport:
    report = quality_report(connection)
    failures = [name for name, status in report.checks.items() if status != "passed"]
    if failures:
        raise DWDQualityError(f"DWD quality checks failed: {', '.join(failures)}")
    return report
