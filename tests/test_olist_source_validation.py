import unittest

from etl.olist.config import get_config
from etl.olist.validator import validate_sources


class TestOlistSourceValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = get_config()
        cls.report = validate_sources(cls.config)

    def test_all_nine_source_files_exist(self):
        self.assertEqual(len(self.report.frames), 9)
        for spec in self.config.source_specs:
            self.assertTrue((self.config.raw_dir / spec.filename).is_file())

    def test_required_columns_are_present(self):
        for spec in self.config.source_specs:
            self.assertTrue(
                set(spec.required_columns).issubset(self.report.frames[spec.filename].columns)
            )

    def test_core_and_composite_keys_are_unique(self):
        for spec in self.config.source_specs:
            if spec.unique_key:
                self.assertEqual(
                    self.report.frames[spec.filename]
                    .duplicated(list(spec.unique_key))
                    .sum(),
                    0,
                )

    def test_core_foreign_keys_have_no_orphans(self):
        self.assertEqual(self.report.checks["foreign_keys"], "passed")

    def test_amounts_are_nonnegative(self):
        self.assertEqual(self.report.checks["amounts"], "passed")

    def test_review_score_range_is_valid(self):
        self.assertEqual(self.report.checks["review_score"], "passed")

    def test_key_timestamps_are_parseable_and_historical(self):
        self.assertEqual(self.report.checks["timestamps"], "passed")
        self.assertLess(self.report.date_min, "2020-01-01")
        self.assertLess(self.report.date_max, "2020-01-01")

    def test_geolocation_is_allowed_to_repeat(self):
        geolocation = self.report.frames["olist_geolocation_dataset.csv"]
        self.assertGreater(int(geolocation.duplicated().sum()), 0)
        self.assertEqual(self.report.checks["geolocation_uniqueness"], "not_required")

    def test_raw_hashes_are_available_for_all_sources(self):
        self.assertEqual(set(self.report.hashes), {spec.filename for spec in self.config.source_specs})
        for digest in self.report.hashes.values():
            self.assertEqual(len(digest), 64)


if __name__ == "__main__":
    unittest.main()
