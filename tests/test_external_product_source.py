import tempfile
import unittest
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler.product_crawler import read_public_products
from data.generate_data import SEED, generate, make_products, make_products_prefer_external


class ExternalProductSourceTests(unittest.TestCase):
    def test_public_dataset_aliases_are_normalized(self):
        payload = (
            "product_id,product_name,category,discounted_price,rating,rating_count\n"
            'A001,"Skin Serum",Skincare,"₹1,099",4.4,"1,250"\n'
        ).encode("utf-8")
        records, rejected = read_public_products(payload)
        self.assertEqual(rejected, 0)
        self.assertEqual(records[0]["product_id"], "A001")
        self.assertEqual(records[0]["price"], 1099.0)
        self.assertEqual(records[0]["review_count"], 1250)

    def test_header_only_ods_preserves_original_product_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            raw = Path(folder) / "raw_products.csv"
            raw.write_text("product_id,product_name,category,price,rating,review_count\n", encoding="utf-8")
            actual, source = make_products_prefer_external(np.random.default_rng(SEED), 10, raw)
            expected = make_products(np.random.default_rng(SEED), 10)
            pd.testing.assert_frame_equal(actual, expected)
            self.assertEqual(source, "synthetic_fallback")

    def test_valid_external_products_are_preferred_without_breaking_pipeline(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw = root / "raw_products.csv"
            raw.write_text(
                "product_id,product_name,category,price,rating,review_count\n"
                "EXT001,Public Skin Serum,Skincare,499,4.7,320\n"
                "EXT002,Public Fashion Bag,Fashion Accessories,799,4.5,180\n",
                encoding="utf-8",
            )
            rows = generate(root / "out", root / "sample", root / "pbi", 10, 30, 100, raw)
            products = pd.read_csv(root / "out" / "products.csv")
            orders = pd.read_csv(root / "out" / "orders.csv")
            self.assertEqual(rows["products"], 10)
            self.assertEqual(products.loc[0, "product_name"], "Public Skin Serum")
            self.assertEqual(products.loc[0, "data_source_type"], "external_market")
            self.assertTrue(set(orders.product_id).issubset(set(products.product_id)))


if __name__ == "__main__":
    unittest.main()
