import json
import re
import unittest
import zipfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "dashboard" / "powerbi_project"
REPORT = PROJECT / "Ecommerce-Operations-Analytics-Assistant.Report"
MODEL = PROJECT / "Ecommerce-Operations-Analytics-Assistant.SemanticModel"
PBIX = PROJECT / "Ecommerce-Operations-Analytics-Assistant-v1.1.pbix"


class PowerBIProjectTests(unittest.TestCase):
    def test_native_powerbi_entry_files_exist(self):
        pbip = PROJECT / "Ecommerce-Operations-Analytics-Assistant.pbip"
        definition = REPORT / "definition.pbir"
        self.assertEqual(json.loads(pbip.read_text(encoding="utf-8"))["version"], "1.0")
        self.assertIn("datasetReference", json.loads(definition.read_text(encoding="utf-8")))
        self.assertGreater(PBIX.stat().st_size, 1_000_000)
        self.assertEqual(PBIX.read_bytes()[:4], b"PK\x03\x04")
        with zipfile.ZipFile(PBIX) as package:
            entries = set(package.namelist())
            self.assertIn("DataModel", entries)
            self.assertIn("Report/definition/pages/pages.json", entries)
            packaged_pages = [
                entry
                for entry in entries
                if re.fullmatch(r"Report/definition/pages/[^/]+/page\.json", entry)
            ]
            self.assertEqual(len(packaged_pages), 4)

    def test_four_page_pbir_is_complete(self):
        pages_root = REPORT / "definition" / "pages"
        metadata = json.loads((pages_root / "pages.json").read_text(encoding="utf-8"))
        self.assertEqual(len(metadata["pageOrder"]), 4)
        names = []
        visual_count = 0
        for page_id in metadata["pageOrder"]:
            page_root = pages_root / page_id
            page = json.loads((page_root / "page.json").read_text(encoding="utf-8"))
            names.append(page["displayName"])
            self.assertEqual((page["width"], page["height"]), (1440, 810))
            visual_files = list((page_root / "visuals").glob("*/visual.json"))
            self.assertGreaterEqual(len(visual_files), 9)
            for visual_file in visual_files:
                json.loads(visual_file.read_text(encoding="utf-8"))
            visual_count += len(visual_files)
        self.assertEqual(names, ["经营总览", "商品分析", "用户分析", "广告分析"])
        self.assertEqual(visual_count, 44)

    def test_tmdl_model_is_portable_and_complete(self):
        definition_root = MODEL / "definition"
        model_text = (definition_root / "model.tmdl").read_text(encoding="utf-8")
        relationships = (definition_root / "relationships.tmdl").read_text(encoding="utf-8")
        expressions = (definition_root / "expressions.tmdl").read_text(encoding="utf-8")
        measures = (definition_root / "tables" / "KPI Measures.tmdl").read_text(encoding="utf-8")
        table_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((definition_root / "tables").glob("*.tmdl"))
        )
        self.assertIn("ref expression DataRoot", model_text)
        self.assertIn("IsParameterQuery=true", expressions)
        self.assertNotRegex(table_text + expressions, r"[A-Za-z]:\\Users\\")
        self.assertEqual(len(re.findall(r"(?m)^relationship ", relationships)), 4)
        self.assertEqual(len(re.findall(r"(?m)^\tmeasure ", measures)), 37)
        for name in ["products", "users", "orders", "ads", "calendar"]:
            source = (definition_root / "tables" / f"{name}.tmdl").read_text(encoding="utf-8")
            self.assertIn(f'DataRoot & "\\{name}.csv"', source)

    def test_powerbi_screenshots_are_github_ready(self):
        screenshots = ROOT / "dashboard" / "powerbi_screenshots"
        for filename in [
            "powerbi_overview.png",
            "powerbi_product.png",
            "powerbi_customer.png",
            "powerbi_ads.png",
        ]:
            with Image.open(screenshots / filename) as image:
                self.assertEqual(image.size, (1440, 810))


if __name__ == "__main__":
    unittest.main()
