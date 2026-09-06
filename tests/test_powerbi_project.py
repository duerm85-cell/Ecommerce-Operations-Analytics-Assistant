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
PBIX_V11 = PROJECT / "Ecommerce-Operations-Analytics-Assistant-v1.1.pbix"
PBIX_V12 = PROJECT / "Ecommerce-Operations-Analytics-Assistant-v1.2.pbix"


class PowerBIProjectTests(unittest.TestCase):
    def assert_valid_pbix(self, path: Path):
        self.assertGreater(path.stat().st_size, 1_000_000)
        self.assertEqual(path.read_bytes()[:4], b"PK\x03\x04")
        with zipfile.ZipFile(path) as package:
            entries = set(package.namelist())
            self.assertIn("DataModel", entries)
            self.assertIn("Report/definition/pages/pages.json", entries)
            packaged_pages = [
                entry
                for entry in entries
                if re.fullmatch(r"Report/definition/pages/[^/]+/page\.json", entry)
            ]
            self.assertEqual(len(packaged_pages), 4)

    def test_native_powerbi_entry_files_and_both_pbix_versions_exist(self):
        pbip = PROJECT / "Ecommerce-Operations-Analytics-Assistant.pbip"
        definition = REPORT / "definition.pbir"
        self.assertEqual(json.loads(pbip.read_text(encoding="utf-8"))["version"], "1.0")
        self.assertIn("datasetReference", json.loads(definition.read_text(encoding="utf-8")))
        self.assert_valid_pbix(PBIX_V11)
        self.assert_valid_pbix(PBIX_V12)

    def test_four_page_executive_storytelling_pbir_is_complete(self):
        pages_root = REPORT / "definition" / "pages"
        metadata = json.loads((pages_root / "pages.json").read_text(encoding="utf-8"))
        self.assertEqual(len(metadata["pageOrder"]), 4)
        names = []
        visual_counts = []
        all_visual_text = []
        for page_id in metadata["pageOrder"]:
            page_root = pages_root / page_id
            page = json.loads((page_root / "page.json").read_text(encoding="utf-8"))
            names.append(page["displayName"])
            self.assertEqual((page["width"], page["height"]), (1440, 810))
            visual_files = list((page_root / "visuals").glob("*/visual.json"))
            visual_counts.append(len(visual_files))
            for visual_file in visual_files:
                text = visual_file.read_text(encoding="utf-8")
                json.loads(text)
                all_visual_text.append(text)
        self.assertEqual(names, ["经营总览", "商品机会", "用户价值", "广告回报"])
        self.assertEqual(visual_counts, [28, 22, 24, 24])
        combined = "\n".join(all_visual_text)
        for page_name in names:
            self.assertIn(page_name, combined)
        self.assertIn("ClearAllSlicers", combined)

    def test_tmdl_model_is_portable_preserves_base_measures_and_fixes_rfm_blank(self):
        definition_root = MODEL / "definition"
        model_text = (definition_root / "model.tmdl").read_text(encoding="utf-8")
        relationships = (definition_root / "relationships.tmdl").read_text(encoding="utf-8")
        expressions = (definition_root / "expressions.tmdl").read_text(encoding="utf-8")
        measures = (definition_root / "tables" / "KPI Measures.tmdl").read_text(encoding="utf-8")
        users = (definition_root / "tables" / "users.tmdl").read_text(encoding="utf-8")
        table_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((definition_root / "tables").glob("*.tmdl"))
        )
        self.assertIn('"DataRoot"', model_text)
        self.assertIn("IsParameterQuery=true", expressions)
        self.assertNotRegex(table_text + expressions, r"[A-Za-z]:\\Users\\")
        self.assertGreaterEqual(len(re.findall(r"(?m)^relationship ", relationships)), 4)
        self.assertEqual(len(re.findall(r"(?m)^\tmeasure ", measures)), 58)
        for required in [
            "GMV", "Net Sales", "Completed Orders", "Gross Profit", "Gross Margin %",
            "AOV", "Purchasing Users", "Repeat Rate FY2025 %", "CTR %", "CVR %",
            "CPA", "ROAS", "Overview Insight Text", "Product Insight Text",
            "Customer Insight Text", "Ads Insight Text",
        ]:
            self.assertRegex(measures, rf"(?m)^\tmeasure '{re.escape(required)}'|^\tmeasure {re.escape(required)} ")
        self.assertIn("RFM Segment Display", users)
        self.assertIn("未购买 / 未分群", users)
        self.assertIn("RFM Business Action", users)
        for name in ["products", "users", "orders", "ads", "calendar"]:
            source = (definition_root / "tables" / f"{name}.tmdl").read_text(encoding="utf-8")
            self.assertIn(f'DataRoot & "\\{name}.csv"', source)

    def test_v12_powerbi_screenshots_are_clean_1440p_assets(self):
        screenshots = ROOT / "dashboard" / "powerbi_screenshots" / "v1.2"
        for filename in [
            "01_overview.png",
            "02_product_opportunity.png",
            "03_customer_value.png",
            "04_advertising_return.png",
        ]:
            with Image.open(screenshots / filename) as image:
                self.assertEqual(image.size, (1440, 810))


if __name__ == "__main__":
    unittest.main()
