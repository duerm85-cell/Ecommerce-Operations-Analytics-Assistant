import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from etl.olist.config import OlistConfig, get_config
from etl.olist.load_ods import load_ods
from etl.olist.validator import OlistValidationError, hash_source_files


class TestOlistODS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = get_config()
        cls.synthetic_db = cls.config.project_root / "data" / "analytics.sqlite"
        cls.synthetic_hash_before = cls._sha256(cls.synthetic_db)
        cls.summary = load_ods(cls.config)
        cls.summary_after_reload = load_ods(cls.config)

    @staticmethod
    def _sha256(path):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _connect(self):
        return sqlite3.connect(self.summary.database_path)

    def test_ods_database_exists_at_dedicated_path(self):
        self.assertTrue(self.summary.database_path.is_file())
        self.assertNotEqual(self.summary.database_path, self.synthetic_db)

    def test_all_ods_tables_have_source_row_counts(self):
        connection = self._connect()
        try:
            for table_name, expected in self.summary.row_counts.items():
                actual = connection.execute(
                    f'SELECT COUNT(*) FROM "{table_name}"'
                ).fetchone()[0]
                self.assertEqual(actual, expected, table_name)
        finally:
            connection.close()

    def test_ods_rows_are_unchanged_after_reload(self):
        connection = self._connect()
        try:
            for table_name, expected in self.summary_after_reload.row_counts.items():
                actual = connection.execute(
                    f'SELECT COUNT(*) FROM "{table_name}"'
                ).fetchone()[0]
                self.assertEqual(actual, expected, table_name)
        finally:
            connection.close()
        self.assertEqual(
            self.summary.row_counts,
            self.summary_after_reload.row_counts,
        )

    def test_technical_columns_are_present(self):
        connection = self._connect()
        try:
            columns = {
                row[1]
                for row in connection.execute(
                    'PRAGMA table_info("ods_olist_orders")'
                ).fetchall()
            }
        finally:
            connection.close()
        self.assertTrue(
            {
                "_load_batch_id",
                "_source_file",
                "_source_row_number",
                "_loaded_at",
            }.issubset(columns)
        )

    def test_dataset_metadata_contract(self):
        connection = self._connect()
        try:
            metadata = dict(
                connection.execute(
                    "SELECT metadata_key, metadata_value FROM dataset_metadata"
                ).fetchall()
            )
        finally:
            connection.close()
        self.assertEqual(metadata["data_mode"], "olist_real")
        self.assertEqual(metadata["currency_code"], "BRL")
        self.assertEqual(metadata["historical_data"], "true")
        self.assertEqual(metadata["ads_available"], "false")
        self.assertEqual(metadata["cost_available"], "false")
        self.assertEqual(metadata["refund_status_available"], "false")
        self.assertEqual(metadata["raw_csv_hashes_unchanged"], "true")

    def test_etl_load_metadata_has_nine_completed_rows(self):
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT source_file, source_row_count, loaded_row_count,
                       file_sha256, load_status, currency_code
                FROM etl_load_metadata
                """
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(len(rows), 9)
        self.assertTrue(all(row[1] == row[2] for row in rows))
        self.assertTrue(all(len(row[3]) == 64 for row in rows))
        self.assertTrue(all(row[4] == "completed" for row in rows))
        self.assertTrue(all(row[5] == "BRL" for row in rows))

    def test_manifest_matches_current_raw_hashes(self):
        manifest = json.loads(self.summary.manifest_path.read_text(encoding="utf-8"))
        current_hashes = hash_source_files(self.config)
        manifest_hashes = {
            row["source_file"]: row["file_sha256"] for row in manifest["files"]
        }
        self.assertEqual(manifest_hashes, current_hashes)
        self.assertTrue(manifest["raw_csv_hashes_unchanged"])

    def test_raw_csv_hashes_are_unchanged(self):
        self.assertTrue(self.summary.raw_csv_hashes_unchanged)
        self.assertTrue(self.summary_after_reload.raw_csv_hashes_unchanged)

    def test_synthetic_database_is_untouched(self):
        self.assertEqual(self.synthetic_hash_before, self._sha256(self.synthetic_db))
        self.assertTrue(self.summary.synthetic_database_unchanged)
        self.assertTrue(self.summary_after_reload.synthetic_database_unchanged)

    def test_date_range_remains_historical(self):
        self.assertEqual(self.summary.date_min, "2016-09-04 21:15:19")
        self.assertEqual(self.summary.date_max, "2018-10-17 17:30:18")

    def test_validation_failure_does_not_replace_existing_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database = root / "olist.sqlite"
            database.write_bytes(b"existing-snapshot")
            config = OlistConfig(
                project_root=self.config.project_root,
                raw_dir=root / "missing-raw",
                ods_db_path=database,
                manifest_path=root / "manifest.json",
                failure_path=root / "failure.json",
            )
            with self.assertRaises(OlistValidationError):
                load_ods(config)
            self.assertEqual(database.read_bytes(), b"existing-snapshot")
            failure = json.loads(config.failure_path.read_text(encoding="utf-8"))
            self.assertEqual(failure["load_status"], "failed")


if __name__ == "__main__":
    unittest.main()
