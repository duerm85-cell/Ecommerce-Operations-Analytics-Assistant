import hashlib, json, sqlite3, tempfile, unittest
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"/"processed"
sys.path.insert(0, str(ROOT))
from data.generate_data import generate
from database.import_mysql import normalize_for_mysql

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
        self.assertTrue(self.p.price.gt(0).all()); self.assertTrue(self.p.rating.between(1,5).all()); self.assertTrue(self.p.hot_score.between(0,100).all()); self.assertTrue(self.p.opportunity_score.between(0,100).all()); self.assertTrue(self.o.quantity.between(1,4).all()); self.assertTrue((self.a.clicks<=self.a.impressions).all()); self.assertTrue((self.a.conversions<=self.a.clicks).all())
        self.assertTrue(((self.o.quantity*self.o.unit_price-self.o.gross_amount).abs()<.01).all())
        completed=self.o.status.eq("completed"); refunded=self.o.status.eq("refunded"); cancelled=self.o.status.eq("cancelled")
        self.assertTrue(((self.o.loc[completed,"gross_amount"]-self.o.loc[completed,"discount_amount"]-self.o.loc[completed,"net_sales"]).abs()<.01).all())
        self.assertTrue(self.o.loc[completed,"refund_amount"].eq(0).all())
        self.assertTrue(self.o.loc[refunded,"net_sales"].eq(0).all()); self.assertTrue(self.o.loc[refunded,"cost"].eq(0).all())
        self.assertTrue(((self.o.loc[refunded,"gross_amount"]-self.o.loc[refunded,"discount_amount"]-self.o.loc[refunded,"refund_amount"]).abs()<.01).all())
        self.assertTrue(self.o.loc[cancelled,["net_sales","refund_amount","cost"]].eq(0).all().all())
    def test_foreign_keys(self):
        self.assertTrue(set(self.o.user_id)<=set(self.u.user_id)); self.assertTrue(set(self.o.product_id)<=set(self.p.product_id))
    def test_sql_python_dashboard_kpis_match(self):
        expected=json.loads((ROOT/"reports"/"kpi_summary.json").read_text())
        with sqlite3.connect(ROOT/"data"/"analytics.sqlite") as c:
            net=c.execute("SELECT SUM(net_sales) FROM orders WHERE status='completed'").fetchone()[0]; roas=c.execute("SELECT SUM(attributed_revenue)/SUM(spend) FROM ads").fetchone()[0]
        self.assertAlmostEqual(net,expected["net_sales"],places=2); self.assertAlmostEqual(roas,expected["roas"],places=9)
    def test_date_currency_and_status_contract(self):
        dates=pd.to_datetime(self.o.order_date); self.assertEqual(dates.min(),pd.Timestamp("2025-01-01")); self.assertEqual(dates.max(),pd.Timestamp("2025-12-31"))
        self.assertEqual(set(self.o.currency),{"TWD"}); self.assertEqual(set(self.a.currency),{"TWD"}); self.assertEqual(set(self.o.status),{"completed","refunded","cancelled"})
    def test_hot_score_formula(self):
        def mm(s):
            spread=s.max()-s.min(); return (s-s.min())/spread if spread else pd.Series(0.0,index=s.index)
        expected=(100*(.50*mm(pd.Series(np.log1p(self.p.sold_count)))+.20*mm(self.p.rating)+.30*mm(pd.Series(np.log1p(self.p.review_count))))).round(2)
        self.assertTrue((expected-self.p.hot_score).abs().max()<.011)
    def test_opportunity_score_penalizes_competition(self):
        def mm(s):
            spread=s.max()-s.min(); return (s-s.min())/spread if spread else pd.Series(0.0,index=s.index)
        category_count=self.p.groupby("category").product_id.transform("count")
        band=pd.cut(self.p.price,[0,100,300,500,np.inf],labels=["0-100","101-300","301-500","501+"])
        density=self.p.assign(price_band=band).groupby(["category","price_band"],observed=True).product_id.transform("count")
        demand=.65*mm(np.log1p(self.p.sold_count))+.35*mm(np.log1p(self.p.review_count))
        competition=.55*mm(category_count)+.45*mm(density)
        expected=(100*(.65*demand+.35*(1-competition))).round(2)
        self.assertTrue((expected-self.p.opportunity_score).abs().max()<.011)
    def test_mysql_datetime_normalization(self):
        frame=normalize_for_mysql("products",pd.DataFrame({"crawl_time":["2026-08-01 10:00:00+08:00"]}))
        self.assertEqual(frame.loc[0,"crawl_time"],"2026-08-01 10:00:00")
    def test_seed_reproducibility(self):
        def hashes(root):
            generate(root/"out",root/"sample",root/"pbi",50,100,200)
            return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/"out").glob("*.csv"))}
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            self.assertEqual(hashes(Path(a)),hashes(Path(b)))
    def test_dashboard_is_portable_and_interactive(self):
        html=(ROOT/"dashboard"/"interactive_dashboard.html").read_text(encoding="utf-8")
        self.assertNotRegex(html,r"[A-Za-z]:[\\/]Users[\\/]"); self.assertNotIn("file://",html)
        for element in ["productCategory","userRegion","channel","renderProducts","renderUsers","renderAds"]: self.assertIn(element,html)
        powerbi_users=pd.read_csv(ROOT/"dashboard"/"powerbi_data"/"users.csv")
        for column in ["recency","frequency","monetary","r_score","f_score","m_score","rfm_segment"]: self.assertIn(column,powerbi_users.columns)
        self.assertEqual(len(powerbi_users),len(self.u)); self.assertFalse(powerbi_users.user_id.duplicated().any())

if __name__=="__main__": unittest.main()
