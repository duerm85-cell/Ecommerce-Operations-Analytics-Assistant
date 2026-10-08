import sqlite3
import unittest

from etl.olist.analytics_quality import quality_report
from etl.olist.analytics_schema import ANALYTICS_PRIMARY_KEYS, ANALYTICS_TABLES
from etl.olist.build_analytics import ANALYTICS_EXPORTS, build_analytics
from etl.olist.build_dwd import build_dwd
from etl.olist.config import get_config


class TestOlistAnalytics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = get_config()
        build_dwd(cls.config)
        cls.summary = build_analytics(cls.config)
        cls.connection = sqlite3.connect(cls.summary.database_path)
        cls.connection.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    def _count(self, sql, params=()):
        return self.connection.execute(sql, params).fetchone()[0]

    def _overview(self):
        self.connection.row_factory = sqlite3.Row
        row = self.connection.execute(
            "SELECT * FROM mart_business_overview"
        ).fetchone()
        result = dict(row)
        self.connection.row_factory = None
        return result

    def test_all_analytics_tables_exist(self):
        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        self.assertEqual(set(ANALYTICS_TABLES) - tables, set())
        self.assertEqual(len(ANALYTICS_TABLES), 6)

    def test_analytics_table_grains_are_unique(self):
        for table, columns in ANALYTICS_PRIMARY_KEYS.items():
            grain = ", ".join(columns)
            with self.subTest(table=table):
                self.assertEqual(
                    self._count(f'SELECT COUNT(*) FROM "{table}"'),
                    self._count(
                        f"SELECT COUNT(*) FROM ("
                        f'SELECT {grain} FROM "{table}" GROUP BY {grain})'
                    ),
                )

    def test_merchandise_gmv_reconciles_without_fact_duplication(self):
        direct = self.connection.execute(
            """
            SELECT SUM(i.price_brl)
            FROM fact_order_items i
            JOIN fact_orders o ON o.order_id = i.order_id
            WHERE o.order_status = 'delivered'
            """
        ).fetchone()[0]
        overview = self._overview()
        self.assertAlmostEqual(overview["merchandise_gmv_brl"], direct, places=5)
        self.assertAlmostEqual(
            self._count("SELECT SUM(merchandise_gmv_brl) FROM mart_category_performance"),
            direct,
            places=5,
        )

    def test_paid_value_is_separate_and_reconciles_to_payments(self):
        direct = self.connection.execute(
            """
            SELECT SUM(p.payment_value_brl)
            FROM fact_payments p
            JOIN fact_orders o ON o.order_id = p.order_id
            WHERE o.order_status = 'delivered'
            """
        ).fetchone()[0]
        overview = self._overview()
        self.assertAlmostEqual(overview["paid_value_brl"], direct, places=5)
        self.assertNotEqual(
            overview["paid_value_brl"], overview["merchandise_gmv_brl"]
        )

    def test_customer_analysis_uses_customer_unique_id(self):
        columns = {
            row[1]
            for row in self.connection.execute(
                'PRAGMA table_info("mart_customer_rfm")'
            ).fetchall()
        }
        self.assertIn("customer_unique_id", columns)
        self.assertNotIn("customer_id", columns)
        expected = self._count(
            """
            SELECT COUNT(DISTINCT customer_unique_id)
            FROM fact_orders
            WHERE order_status = 'delivered'
            """
        )
        self.assertEqual(self._count("SELECT COUNT(*) FROM mart_customer_rfm"), expected)
        self.assertEqual(self._overview()["purchasing_customers"], expected)

    def test_rfm_is_one_row_per_purchasing_customer(self):
        self.assertEqual(
            self._count("SELECT COUNT(*) FROM mart_customer_rfm"),
            self._count(
                "SELECT COUNT(DISTINCT customer_unique_id) FROM mart_customer_rfm"
            ),
        )
        invalid = self._count(
            """
            SELECT COUNT(*)
            FROM mart_customer_rfm
            WHERE recency_days < 0
               OR frequency < 1
               OR monetary_value_brl < 0
               OR r_score NOT BETWEEN 1 AND 5
               OR f_score NOT BETWEEN 1 AND 5
               OR m_score NOT BETWEEN 1 AND 5
               OR rfm_score <> 100 * r_score + 10 * f_score + m_score
            """
        )
        self.assertEqual(invalid, 0)

    def test_repeat_purchase_rate_matches_customer_frequency(self):
        expected_repeat = self._count(
            "SELECT COUNT(*) FROM mart_customer_rfm WHERE frequency >= 2"
        )
        purchasing = self._count("SELECT COUNT(*) FROM mart_customer_rfm")
        overview = self._overview()
        self.assertEqual(overview["repeat_customers"], expected_repeat)
        self.assertAlmostEqual(
            overview["repeat_purchase_rate"],
            expected_repeat / purchasing,
            places=12,
        )
        self.assertGreaterEqual(overview["repeat_purchase_rate"], 0)
        self.assertLessEqual(overview["repeat_purchase_rate"], 1)

    def test_review_scores_remain_in_valid_range(self):
        overview = self._overview()
        self.assertGreaterEqual(overview["average_review_score"], 1)
        self.assertLessEqual(overview["average_review_score"], 5)
        self.assertEqual(
            self._count(
                """
                SELECT COUNT(*) FROM mart_category_performance
                WHERE (average_review_score IS NOT NULL
                       AND average_review_score NOT BETWEEN 1 AND 5)
                   OR (low_rating_rate IS NOT NULL
                       AND low_rating_rate NOT BETWEEN 0 AND 1)
                """
            ),
            0,
        )

    def test_freight_ratio_is_nonnegative_and_reconciles(self):
        self.assertEqual(
            self._count(
                "SELECT COUNT(*) FROM mart_category_performance "
                "WHERE freight_ratio < 0 OR freight_value_brl < 0"
            ),
            0,
        )
        self.assertAlmostEqual(
            self._count("SELECT SUM(freight_value_brl) FROM mart_category_performance"),
            self._overview()["freight_value_brl"],
            places=5,
        )

    def test_monthly_aggregation_reconciles_to_overview(self):
        monthly = self.connection.execute(
            """
            SELECT SUM(total_placed_orders), SUM(orders),
                   SUM(merchandise_gmv_brl), SUM(paid_value_brl),
                   SUM(units_sold), SUM(canceled_orders)
            FROM mart_monthly_performance
            """
        ).fetchone()
        overview = self._overview()
        self.assertEqual(monthly[0], overview["total_placed_orders"])
        self.assertEqual(monthly[1], overview["orders"])
        self.assertAlmostEqual(monthly[2], overview["merchandise_gmv_brl"], places=5)
        self.assertAlmostEqual(monthly[3], overview["paid_value_brl"], places=5)
        self.assertEqual(monthly[4], overview["units_sold"])
        self.assertEqual(monthly[5], overview["canceled_orders"])

    def test_category_aggregation_reconciles_to_item_facts(self):
        category = self.connection.execute(
            """
            SELECT SUM(merchandise_gmv_brl), SUM(units_sold)
            FROM mart_category_performance
            """
        ).fetchone()
        overview = self._overview()
        self.assertAlmostEqual(category[0], overview["merchandise_gmv_brl"], places=5)
        self.assertEqual(category[1], overview["units_sold"])
        self.assertGreater(
            self._count(
                """
                SELECT COUNT(*) FROM mart_category_performance
                WHERE category_translation_status <> 'translated'
                """
            ),
            0,
        )

    def test_aov_definition_is_merchandise_gmv_per_delivered_order(self):
        overview = self._overview()
        self.assertEqual(overview["order_scope"], "delivered")
        self.assertAlmostEqual(
            overview["aov_brl"],
            overview["merchandise_gmv_brl"] / overview["orders"],
            places=10,
        )
        definition = self.connection.execute(
            """
            SELECT definition FROM analytics_metric_definitions
            WHERE metric_name = 'aov_brl'
            """
        ).fetchone()[0]
        self.assertIn("Delivered merchandise GMV", definition)

    def test_customer_segments_reconcile_to_customer_rfm(self):
        segment = self.connection.execute(
            """
            SELECT SUM(customers), SUM(repeat_customers), SUM(customer_share),
                   SUM(total_monetary_value_brl)
            FROM mart_customer_segments
            """
        ).fetchone()
        overview = self._overview()
        self.assertEqual(segment[0], overview["purchasing_customers"])
        self.assertEqual(segment[1], overview["repeat_customers"])
        self.assertAlmostEqual(segment[2], 1.0, places=10)
        self.assertAlmostEqual(segment[3], overview["merchandise_gmv_brl"], places=5)

    def test_complete_quality_report_passes(self):
        report = quality_report(self.connection)
        self.assertTrue(report.passed, report.checks)
        self.assertEqual(len(report.checks), 15)
        self.assertTrue(self.summary.synthetic_database_unchanged)

    def test_powerbi_csv_exports_match_analytics_row_counts(self):
        export_dir = self.config.project_root / "dashboard" / "powerbi_data"
        for table, filename in ANALYTICS_EXPORTS.items():
            path = export_dir / filename
            with self.subTest(file=filename):
                self.assertTrue(path.is_file())
                self.assertEqual(
                    self.summary.exported_files[filename],
                    self._count(f'SELECT COUNT(*) FROM "{table}"'),
                )
                self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
