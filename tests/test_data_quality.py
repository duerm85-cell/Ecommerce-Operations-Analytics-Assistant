import json, sqlite3, unittest
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"/"processed"

class DataQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=pd.read_csv(DATA/"products.csv"); cls.u=pd.read_csv(DATA/"users.csv"); cls.o=pd.read_csv(DATA/"orders.csv"); cls.a=pd.read_csv(DATA/"ads.csv")
    def test_expected_scale(self):
        self.assertGreaterEqual(len(self.p),500); self.assertGreaterEqual(len(self.o),50000); self.assertGreaterEqual(len(self.u),8000)
    def test_primary_keys_unique(self):
        self.assertFalse(self.p.product_id.duplicated().any()); self.assertFalse(self.u.user_id.duplicated().any()); self.assertFalse(self.o.order_id.duplicated().any()); self.assertFalse(self.a.duplicated(["date","campaign_id"]).any())
    def test_required_fields_complete(self):
        for frame,cols in [(self.p,["product_id","product_name","category","price"]),(self.u,["user_id","region"]),(self.o,["order_id","user_id","product_id","order_date","status"]),(self.a,["date","campaign_id","impressions","clicks","spend"])]: self.assertEqual(int(frame[cols].isna().sum().sum()),0)
    def test_ranges_and_equations(self):
        self.assertTrue(self.p.price.gt(0).all()); self.assertTrue(self.p.rating.between(1,5).all()); self.assertTrue(self.o.quantity.between(1,4).all()); self.assertTrue((self.a.clicks<=self.a.impressions).all()); self.assertTrue((self.a.conversions<=self.a.clicks).all())
        self.assertTrue(((self.o.quantity*self.o.unit_price-self.o.gross_amount).abs()<.01).all())
        completed=self.o.status.eq("completed"); self.assertTrue(self.o.loc[~completed,"net_sales"].eq(0).all())
    def test_foreign_keys(self):
        self.assertTrue(set(self.o.user_id)<=set(self.u.user_id)); self.assertTrue(set(self.o.product_id)<=set(self.p.product_id))
    def test_sql_python_dashboard_kpis_match(self):
        expected=json.loads((ROOT/"reports"/"kpi_summary.json").read_text())
        with sqlite3.connect(ROOT/"data"/"analytics.sqlite") as c:
            net=c.execute("SELECT SUM(net_sales) FROM orders WHERE status='completed'").fetchone()[0]; roas=c.execute("SELECT SUM(attributed_revenue)/SUM(spend) FROM ads").fetchone()[0]
        self.assertAlmostEqual(net,expected["net_sales"],places=2); self.assertAlmostEqual(roas,expected["roas"],places=9)

if __name__=="__main__": unittest.main()

