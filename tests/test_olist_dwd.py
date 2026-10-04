import sqlite3
import unittest

from etl.olist.build_dwd import build_dwd
from etl.olist.config import get_config
from etl.olist.dwd_quality import quality_report
from etl.olist.dwd_schema import DWD_PRIMARY_KEYS, DWD_TABLES


class TestOlistDWD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = get_config()
        cls.summary = build_dwd(cls.config)
        cls.connection = sqlite3.connect(cls.summary.database_path)
        cls.connection.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    def _count(self, sql, params=()):
        return self.connection.execute(sql, params).fetchone()[0]

    def test_all_nine_dwd_tables_exist(self):
        actual = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        self.assertEqual(set(DWD_TABLES) - actual, set())
        self.assertEqual(len(DWD_TABLES), 9)

    def test_dimension_bridge_and_fact_row_counts_match_source_grains(self):
        expected_pairs = (
            ("dim_product", "ods_olist_products"),
            ("dim_seller", "ods_olist_sellers"),
            ("bridge_customer_identity", "ods_olist_customers"),
            ("fact_orders", "ods_olist_orders"),
            ("fact_order_items", "ods_olist_order_items"),
            ("fact_payments", "ods_olist_order_payments"),
            ("fact_reviews", "ods_olist_order_reviews"),
        )
        for dwd_table, ods_table in expected_pairs:
            with self.subTest(table=dwd_table):
                self.assertEqual(
                    self._count(f'SELECT COUNT(*) FROM "{dwd_table}"'),
                    self._count(f'SELECT COUNT(*) FROM "{ods_table}"'),
                )
        self.assertEqual(
            self._count("SELECT COUNT(*) FROM dim_customer"),
            self._count(
                "SELECT COUNT(DISTINCT customer_unique_id) "
                "FROM ods_olist_customers"
            ),
        )
        self.assertGreater(self._count("SELECT COUNT(*) FROM dim_date"), 0)

    def test_all_primary_keys_are_non_null_and_unique(self):
        for table, columns in DWD_PRIMARY_KEYS.items():
            quoted = ", ".join(f'"{column}"' for column in columns)
            null_condition = " OR ".join(
                f'"{column}" IS NULL' for column in columns
            )
            duplicates = self._count(
                f"""
                SELECT COUNT(*) FROM (
                    SELECT {quoted}
                    FROM "{table}"
                    GROUP BY {quoted}
                    HAVING COUNT(*) > 1
                )
                """
            )
            with self.subTest(table=table):
                self.assertEqual(
                    self._count(
                        f'SELECT COUNT(*) FROM "{table}" WHERE {null_condition}'
                    ),
                    0,
                )
                self.assertEqual(duplicates, 0)

    def test_all_foreign_keys_are_complete(self):
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(),
            [],
        )

    def test_customer_unique_id_is_canonical_and_bridge_is_exact(self):
        mismatches = self._count(
            """
            SELECT COUNT(*)
            FROM bridge_customer_identity b
            JOIN ods_olist_customers c ON c.customer_id = b.customer_id
            WHERE b.customer_unique_id <> c.customer_unique_id
            """
        )
        order_mismatches = self._count(
            """
            SELECT COUNT(*)
            FROM fact_orders o
            JOIN bridge_customer_identity b ON b.customer_id = o.customer_id
            WHERE o.customer_unique_id <> b.customer_unique_id
            """
        )
        self.assertEqual(mismatches, 0)
        self.assertEqual(order_mismatches, 0)
        self.assertEqual(
            self._count("SELECT COUNT(*) FROM dim_customer"),
            self._count(
                "SELECT COUNT(DISTINCT customer_unique_id) "
                "FROM bridge_customer_identity"
            ),
        )

    def test_fact_grains_have_no_duplicate_records(self):
        checks = (
            ("fact_orders", "order_id"),
            ("fact_order_items", "order_id, order_item_id"),
            ("fact_payments", "order_id, payment_sequential"),
            ("fact_reviews", "review_id"),
        )
        for table, grain in checks:
            with self.subTest(table=table):
                self.assertEqual(
                    self._count(f'SELECT COUNT(*) FROM "{table}"'),
                    self._count(
                        f"SELECT COUNT(*) FROM ("
                        f'SELECT {grain} FROM "{table}" GROUP BY {grain})'
                    ),
                )

    def test_fact_orders_is_one_row_per_order_without_fact_expansion(self):
        self.assertEqual(
            self._count("SELECT COUNT(*) FROM fact_orders"),
            self._count("SELECT COUNT(DISTINCT order_id) FROM ods_olist_orders"),
        )
        mismatches = self._count(
            """
            WITH item_counts AS (
                SELECT order_id, COUNT(*) AS row_count
                FROM ods_olist_order_items GROUP BY order_id
            ),
            payment_counts AS (
                SELECT order_id, COUNT(*) AS row_count
                FROM ods_olist_order_payments GROUP BY order_id
            ),
            review_counts AS (
                SELECT order_id, COUNT(*) AS row_count
                FROM ods_olist_order_reviews GROUP BY order_id
            )
            SELECT COUNT(*)
            FROM fact_orders o
            LEFT JOIN item_counts i ON i.order_id = o.order_id
            LEFT JOIN payment_counts p ON p.order_id = o.order_id
            LEFT JOIN review_counts r ON r.order_id = o.order_id
            WHERE o.item_count <> COALESCE(i.row_count, 0)
               OR o.payment_record_count <> COALESCE(p.row_count, 0)
               OR o.review_record_count <> COALESCE(r.row_count, 0)
            """
        )
        self.assertEqual(mismatches, 0)

    def test_review_records_preserve_source_grain_with_single_dwd_key(self):
        columns = {
            row[1]: row[5]
            for row in self.connection.execute(
                'PRAGMA table_info("fact_reviews")'
            ).fetchall()
        }
        self.assertEqual(columns["review_id"], 1)
        self.assertIn("source_review_id", columns)
        self.assertEqual(
            self._count(
                """
                SELECT COUNT(*)
                FROM fact_reviews d
                JOIN ods_olist_order_reviews s
                  ON s.review_id = d.source_review_id
                 AND s.order_id = d.order_id
                """
            ),
            self._count("SELECT COUNT(*) FROM ods_olist_order_reviews"),
        )

    def test_brl_fields_and_metadata_are_present(self):
        expected_columns = {
            "fact_order_items": {"price_brl", "freight_value_brl"},
            "fact_payments": {"payment_value_brl"},
        }
        for table, required in expected_columns.items():
            columns = {
                row[1]
                for row in self.connection.execute(
                    f'PRAGMA table_info("{table}")'
                ).fetchall()
            }
            with self.subTest(table=table):
                self.assertTrue(required.issubset(columns))
        for table in ("fact_orders", "fact_order_items", "fact_payments"):
            with self.subTest(table=table):
                self.assertEqual(
                    self.connection.execute(
                        f'SELECT DISTINCT currency_code FROM "{table}"'
                    ).fetchall(),
                    [("BRL",)],
                )

    def test_original_order_statuses_are_preserved(self):
        source = set(
            self.connection.execute(
                "SELECT DISTINCT order_status FROM ods_olist_orders"
            ).fetchall()
        )
        dwd = set(
            self.connection.execute(
                "SELECT DISTINCT order_status FROM fact_orders"
            ).fetchall()
        )
        self.assertEqual(source, dwd)
        self.assertNotIn(("completed",), dwd)
        self.assertNotIn(("refunded",), dwd)

    def test_untranslated_and_missing_product_categories_are_retained(self):
        self.assertEqual(
            self._count("SELECT COUNT(*) FROM dim_product"),
            self._count("SELECT COUNT(*) FROM ods_olist_products"),
        )
        untranslated = self._count(
            """
            SELECT COUNT(*)
            FROM dim_product
            WHERE category_pt IN (
                'pc_gamer',
                'portateis_cozinha_e_preparadores_de_alimentos'
            )
              AND category_en IS NULL
              AND category_translation_status = 'untranslated'
            """
        )
        self.assertGreater(untranslated, 0)

    def test_date_dimension_covers_all_real_olist_dates(self):
        expected = self.connection.execute(
            """
            SELECT MIN(calendar_date), MAX(calendar_date)
            FROM (
                SELECT date(order_purchase_timestamp) AS calendar_date
                FROM ods_olist_orders
                UNION ALL SELECT date(order_approved_at) FROM ods_olist_orders
                UNION ALL SELECT date(order_delivered_carrier_date) FROM ods_olist_orders
                UNION ALL SELECT date(order_delivered_customer_date) FROM ods_olist_orders
                UNION ALL SELECT date(order_estimated_delivery_date) FROM ods_olist_orders
                UNION ALL SELECT date(shipping_limit_date) FROM ods_olist_order_items
                UNION ALL SELECT date(review_creation_date) FROM ods_olist_order_reviews
                UNION ALL SELECT date(review_answer_timestamp) FROM ods_olist_order_reviews
            )
            WHERE calendar_date IS NOT NULL
            """
        ).fetchone()
        actual = self.connection.execute(
            "SELECT MIN(calendar_date), MAX(calendar_date) FROM dim_date"
        ).fetchone()
        self.assertEqual(actual, expected)
        self.assertEqual(actual, ("2016-09-04", "2020-04-09"))
        self.assertEqual(
            self._count("SELECT COUNT(*) FROM dim_date"),
            self._count(
                "SELECT CAST(julianday(?) - julianday(?) + 1 AS INTEGER)",
                (expected[1], expected[0]),
            ),
        )

    def test_quality_report_and_gmv_join_safety_pass(self):
        report = quality_report(self.connection)
        self.assertTrue(report.passed, report.checks)
        self.assertEqual(len(report.checks), 12)
        self.assertEqual(report.checks["gmv_join_safety"], "passed")
        self.assertGreater(report.merchandise_value_brl, 0)
        self.assertTrue(self.summary.synthetic_database_unchanged)


if __name__ == "__main__":
    unittest.main()
