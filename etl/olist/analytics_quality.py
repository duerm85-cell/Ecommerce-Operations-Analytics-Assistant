"""Business-grain and reconciliation checks for the Olist analytics marts."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Iterable

from .analytics_schema import (
    ANALYTICS_PRIMARY_KEYS,
    ANALYTICS_TABLES,
    REQUIRED_DWD_TABLES,
)


class AnalyticsQualityError(ValueError):
    """Raised when an analytics business contract fails."""


@dataclass
class AnalyticsQualityReport:
    checks: dict[str, str]
    row_counts: dict[str, int]

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


def _close(left: float, right: float) -> bool:
    tolerance = max(0.000001, abs(right) * 0.000000001)
    return abs(left - right) <= tolerance


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


def _overview(connection: sqlite3.Connection) -> dict[str, object]:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT * FROM mart_business_overview WHERE snapshot_id = 'olist_all_time'"
    ).fetchone()
    result = dict(row) if row else {}
    connection.row_factory = None
    return result


def _gmv_reconciles(connection: sqlite3.Connection, overview: dict[str, object]) -> bool:
    direct = float(
        connection.execute(
            """
            SELECT COALESCE(SUM(i.price_brl), 0)
            FROM fact_order_items i
            JOIN fact_orders o ON o.order_id = i.order_id
            WHERE o.order_status = 'delivered'
            """
        ).fetchone()[0]
    )
    return _close(float(overview["merchandise_gmv_brl"]), direct)


def _paid_value_reconciles(
    connection: sqlite3.Connection, overview: dict[str, object]
) -> bool:
    direct = float(
        connection.execute(
            """
            SELECT COALESCE(SUM(p.payment_value_brl), 0)
            FROM fact_payments p
            JOIN fact_orders o ON o.order_id = p.order_id
            WHERE o.order_status = 'delivered'
            """
        ).fetchone()[0]
    )
    return _close(float(overview["paid_value_brl"]), direct)


def _customer_contract_valid(
    connection: sqlite3.Connection, overview: dict[str, object]
) -> bool:
    expected_customers = _count(
        connection,
        """
        SELECT COUNT(DISTINCT customer_unique_id)
        FROM fact_orders
        WHERE order_status = 'delivered'
        """,
    )
    expected_repeat = _count(
        connection,
        """
        SELECT COUNT(*) FROM (
            SELECT customer_unique_id
            FROM fact_orders
            WHERE order_status = 'delivered'
            GROUP BY customer_unique_id
            HAVING COUNT(DISTINCT order_id) >= 2
        )
        """,
    )
    rfm_columns = {
        row[1]
        for row in connection.execute(
            'PRAGMA table_info("mart_customer_rfm")'
        ).fetchall()
    }
    return (
        expected_customers == _count(connection, "SELECT COUNT(*) FROM mart_customer_rfm")
        and expected_customers == int(overview["purchasing_customers"])
        and expected_repeat == int(overview["repeat_customers"])
        and "customer_unique_id" in rfm_columns
        and "customer_id" not in rfm_columns
    )


def _rfm_contract_valid(connection: sqlite3.Connection) -> bool:
    invalid = _count(
        connection,
        """
        SELECT COUNT(*)
        FROM mart_customer_rfm r
        LEFT JOIN (
            SELECT customer_unique_id,
                   COUNT(DISTINCT order_id) AS frequency,
                   MAX(date(purchase_timestamp)) AS last_purchase_date
            FROM fact_orders
            WHERE order_status = 'delivered'
            GROUP BY customer_unique_id
        ) f ON f.customer_unique_id = r.customer_unique_id
        WHERE f.customer_unique_id IS NULL
           OR r.frequency <> f.frequency
           OR r.last_purchase_date <> f.last_purchase_date
           OR r.r_score NOT BETWEEN 1 AND 5
           OR r.f_score NOT BETWEEN 1 AND 5
           OR r.m_score NOT BETWEEN 1 AND 5
           OR r.rfm_score <> 100 * r.r_score + 10 * r.f_score + r.m_score
           OR r.recency_days < 0
           OR r.monetary_value_brl < 0
        """,
    )
    as_of_dates = _count(
        connection,
        "SELECT COUNT(DISTINCT as_of_date) FROM mart_customer_rfm",
    )
    return invalid == 0 and as_of_dates == 1


def _repeat_rate_valid(
    connection: sqlite3.Connection, overview: dict[str, object]
) -> bool:
    expected = float(overview["repeat_customers"]) / float(
        overview["purchasing_customers"]
    )
    invalid_rows = _count(
        connection,
        """
        SELECT COUNT(*)
        FROM mart_customer_segments
        WHERE repeat_purchase_rate NOT BETWEEN 0 AND 1
           OR customer_share NOT BETWEEN 0 AND 1
        """,
    )
    return (
        0 <= float(overview["repeat_purchase_rate"]) <= 1
        and _close(float(overview["repeat_purchase_rate"]), expected)
        and invalid_rows == 0
    )


def _review_contract_valid(
    connection: sqlite3.Connection, overview: dict[str, object]
) -> bool:
    direct = connection.execute(
        """
        SELECT AVG(r.review_score)
        FROM fact_reviews r
        JOIN fact_orders o ON o.order_id = r.order_id
        WHERE o.order_status = 'delivered'
        """
    ).fetchone()[0]
    invalid_categories = _count(
        connection,
        """
        SELECT COUNT(*)
        FROM mart_category_performance
        WHERE (average_review_score IS NOT NULL
               AND average_review_score NOT BETWEEN 1 AND 5)
           OR (low_rating_rate IS NOT NULL
               AND low_rating_rate NOT BETWEEN 0 AND 1)
        """,
    )
    return (
        direct is not None
        and _close(float(overview["average_review_score"]), float(direct))
        and invalid_categories == 0
    )


def _freight_contract_valid(
    connection: sqlite3.Connection, overview: dict[str, object]
) -> bool:
    category_freight = float(
        connection.execute(
            "SELECT COALESCE(SUM(freight_value_brl), 0) FROM mart_category_performance"
        ).fetchone()[0]
    )
    invalid = _count(
        connection,
        """
        SELECT COUNT(*)
        FROM mart_category_performance
        WHERE freight_value_brl < 0 OR freight_ratio < 0
        """,
    )
    return invalid == 0 and _close(
        category_freight, float(overview["freight_value_brl"])
    )


def _monthly_reconciles(
    connection: sqlite3.Connection, overview: dict[str, object]
) -> bool:
    row = connection.execute(
        """
        SELECT SUM(total_placed_orders), SUM(orders),
               SUM(merchandise_gmv_brl), SUM(paid_value_brl),
               SUM(units_sold), SUM(freight_value_brl),
               SUM(canceled_orders)
        FROM mart_monthly_performance
        """
    ).fetchone()
    invalid = _count(
        connection,
        """
        SELECT COUNT(*)
        FROM mart_monthly_performance
        WHERE cancel_rate NOT BETWEEN 0 AND 1
           OR (average_review_score IS NOT NULL
               AND average_review_score NOT BETWEEN 1 AND 5)
        """,
    )
    expected_months = _count(
        connection,
        "SELECT COUNT(DISTINCT substr(purchase_timestamp, 1, 7)) FROM fact_orders",
    )
    return (
        invalid == 0
        and expected_months
        == _count(connection, "SELECT COUNT(*) FROM mart_monthly_performance")
        and int(row[0]) == int(overview["total_placed_orders"])
        and int(row[1]) == int(overview["orders"])
        and _close(float(row[2]), float(overview["merchandise_gmv_brl"]))
        and _close(float(row[3]), float(overview["paid_value_brl"]))
        and int(row[4]) == int(overview["units_sold"])
        and _close(float(row[5]), float(overview["freight_value_brl"]))
        and int(row[6]) == int(overview["canceled_orders"])
    )


def _category_reconciles(
    connection: sqlite3.Connection, overview: dict[str, object]
) -> bool:
    row = connection.execute(
        """
        SELECT SUM(merchandise_gmv_brl), SUM(units_sold)
        FROM mart_category_performance
        """
    ).fetchone()
    source_categories = _count(
        connection,
        """
        SELECT COUNT(DISTINCT COALESCE(p.category_pt, '__missing__'))
        FROM fact_order_items i
        JOIN fact_orders o ON o.order_id = i.order_id
        JOIN dim_product p ON p.product_id = i.product_id
        WHERE o.order_status = 'delivered'
        """,
    )
    return (
        _close(float(row[0]), float(overview["merchandise_gmv_brl"]))
        and int(row[1]) == int(overview["units_sold"])
        and source_categories
        == _count(connection, "SELECT COUNT(*) FROM mart_category_performance")
    )


def _segments_reconcile(
    connection: sqlite3.Connection, overview: dict[str, object]
) -> bool:
    row = connection.execute(
        """
        SELECT SUM(customers), SUM(repeat_customers),
               SUM(total_monetary_value_brl), SUM(customer_share)
        FROM mart_customer_segments
        """
    ).fetchone()
    return (
        int(row[0]) == int(overview["purchasing_customers"])
        and int(row[1]) == int(overview["repeat_customers"])
        and _close(float(row[2]), float(overview["merchandise_gmv_brl"]))
        and _close(float(row[3]), 1.0)
    )


def _metric_definitions_complete(connection: sqlite3.Connection) -> bool:
    required = {
        "orders",
        "purchasing_customers",
        "repeat_customers",
        "repeat_purchase_rate",
        "merchandise_gmv_brl",
        "paid_value_brl",
        "units_sold",
        "aov_brl",
        "average_review_score",
        "cancel_rate",
        "customer_recency_days",
        "customer_frequency",
        "customer_monetary_value_brl",
        "rfm_score",
        "freight_ratio",
        "low_rating_rate",
    }
    actual = {
        row[0]
        for row in connection.execute(
            "SELECT metric_name FROM analytics_metric_definitions"
        ).fetchall()
    }
    return required.issubset(actual)


def quality_report(connection: sqlite3.Connection) -> AnalyticsQualityReport:
    """Return business-rule and reconciliation results without changing data."""

    tables = _table_names(connection)
    analytics_exist = set(ANALYTICS_TABLES).issubset(tables)
    dwd_exist = set(REQUIRED_DWD_TABLES).issubset(tables)
    checks: dict[str, str] = {
        "analytics_tables_exist": "passed" if analytics_exist else "failed",
        "dwd_inputs_exist": "passed" if dwd_exist else "failed",
    }

    if analytics_exist and dwd_exist:
        overview = _overview(connection)
        checks.update(
            {
                "primary_keys_unique": "passed"
                if all(
                    _primary_key_unique(connection, table, key)
                    for table, key in ANALYTICS_PRIMARY_KEYS.items()
                )
                else "failed",
                "foreign_keys_complete": "passed"
                if _foreign_keys_valid(connection)
                else "failed",
                "gmv_reconciliation": "passed"
                if _gmv_reconciles(connection, overview)
                else "failed",
                "paid_value_reconciliation": "passed"
                if _paid_value_reconciles(connection, overview)
                else "failed",
                "customer_unique_id_contract": "passed"
                if _customer_contract_valid(connection, overview)
                else "failed",
                "rfm_grain_and_scores": "passed"
                if _rfm_contract_valid(connection)
                else "failed",
                "repeat_rate_range_and_definition": "passed"
                if _repeat_rate_valid(connection, overview)
                else "failed",
                "review_score_range_and_reconciliation": "passed"
                if _review_contract_valid(connection, overview)
                else "failed",
                "freight_ratio_nonnegative": "passed"
                if _freight_contract_valid(connection, overview)
                else "failed",
                "monthly_reconciliation": "passed"
                if _monthly_reconciles(connection, overview)
                else "failed",
                "category_reconciliation": "passed"
                if _category_reconciles(connection, overview)
                else "failed",
                "segment_reconciliation": "passed"
                if _segments_reconcile(connection, overview)
                else "failed",
                "metric_definitions_complete": "passed"
                if _metric_definitions_complete(connection)
                else "failed",
            }
        )

    row_counts = {}
    if analytics_exist:
        row_counts = {
            table: _count(connection, f'SELECT COUNT(*) FROM "{table}"')
            for table in ANALYTICS_TABLES
        }
    return AnalyticsQualityReport(checks=checks, row_counts=row_counts)


def run_quality_checks(connection: sqlite3.Connection) -> AnalyticsQualityReport:
    report = quality_report(connection)
    failures = [name for name, status in report.checks.items() if status != "passed"]
    if failures:
        raise AnalyticsQualityError(
            f"Analytics quality checks failed: {', '.join(failures)}"
        )
    return report
