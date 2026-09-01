"""Run four-domain analysis, metric reconciliation and visual exports."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
CHARTS = REPORTS / "charts"
DB_PATH = ROOT / "data" / "analytics.sqlite"
BLUE, GREEN, RED, INK, MUTED, BG = "#2563EB", "#10B981", "#EF4444", "#172033", "#667085", "#F5F7FB"


def load() -> dict[str, pd.DataFrame]:
    parse = {"orders": ["order_date"], "users": ["register_date"], "ads": ["date"], "calendar": ["date"], "products": ["crawl_time"]}
    return {name: pd.read_csv(DATA / f"{name}.csv", parse_dates=parse.get(name, [])) for name in ["products", "users", "orders", "ads", "calendar"]}

def _safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else float("nan")


def build_sqlite(t: dict[str, pd.DataFrame]) -> None:
    if DB_PATH.exists(): DB_PATH.unlink()
    with sqlite3.connect(DB_PATH) as conn:
        for name, frame in t.items(): frame.to_sql(name, conn, index=False, if_exists="replace")
        conn.executescript("""
        CREATE UNIQUE INDEX ux_products ON products(product_id);
        CREATE UNIQUE INDEX ux_users ON users(user_id);
        CREATE UNIQUE INDEX ux_orders ON orders(order_id);
        CREATE UNIQUE INDEX ux_calendar ON calendar(date);
        CREATE UNIQUE INDEX ux_ads ON ads(date,campaign_id);
        CREATE INDEX ix_orders_date_status ON orders(order_date,status);
        CREATE INDEX ix_orders_user ON orders(user_id);
        CREATE INDEX ix_orders_product ON orders(product_id);
        """)


def metrics(t: dict[str, pd.DataFrame]) -> dict[str, float]:
    o = t["orders"]; completed = o[o.status.eq("completed")]; transacted = o[o.status.isin(["completed", "refunded"])]
    user_orders = completed.groupby("user_id").order_id.nunique()
    a = t["ads"]
    return {
        "gmv": float(transacted.gross_amount.sum()), "net_sales": float(completed.net_sales.sum()),
        "orders": int(completed.order_id.nunique()), "gross_profit": float((completed.net_sales - completed.cost).sum()),
        "gross_margin": _safe_ratio((completed.net_sales - completed.cost).sum(), completed.net_sales.sum()),
        "aov": _safe_ratio(completed.net_sales.sum(), completed.order_id.nunique()), "users": int(completed.user_id.nunique()),
        "repeat_rate": float(user_orders.ge(2).mean()), "ctr": _safe_ratio(a.clicks.sum(), a.impressions.sum()),
        "cvr": _safe_ratio(a.conversions.sum(), a.clicks.sum()), "cpc": _safe_ratio(a.spend.sum(), a.clicks.sum()),
        "cpa": _safe_ratio(a.spend.sum(), a.conversions.sum()), "roas": _safe_ratio(a.attributed_revenue.sum(), a.spend.sum()),
    }


def analyze(t: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    p, o, u, a = t["products"], t["orders"], t["users"], t["ads"]
    co = o[o.status.eq("completed")].copy(); co["month"] = co.order_date.dt.strftime("%Y-%m")
    monthly = co.groupby("month").agg(net_sales=("net_sales","sum"), orders=("order_id","nunique"), cost=("cost","sum"), users=("user_id","nunique")).reset_index()
    monthly["gross_profit"] = monthly.net_sales-monthly.cost; monthly["aov"] = monthly.net_sales/monthly.orders; monthly["mom"] = monthly.net_sales.pct_change()
    product_perf = co.merge(p[["product_id","product_name","category","hot_score","opportunity_score","price"]], on="product_id").groupby(["product_id","product_name","category","hot_score","opportunity_score","price"]).agg(net_sales=("net_sales","sum"),units=("quantity","sum"),cost=("cost","sum")).reset_index()
    product_perf["gross_profit"] = product_perf.net_sales-product_perf.cost; product_perf["gross_margin"] = product_perf.gross_profit/product_perf.net_sales
    category = product_perf.groupby("category").agg(net_sales=("net_sales","sum"),gross_profit=("gross_profit","sum"),units=("units","sum")).reset_index(); category["gross_margin"] = category.gross_profit/category.net_sales
    user_perf = co.groupby("user_id").agg(last_order=("order_date","max"),frequency=("order_id","nunique"),monetary=("net_sales","sum")).reset_index()
    user_perf["recency"] = (pd.Timestamp("2025-12-31")-user_perf.last_order).dt.days
    user_perf["r_score"] = 6-pd.qcut(user_perf.recency.rank(method="first"),5,labels=False)-1
    user_perf["f_score"] = pd.qcut(user_perf.frequency.rank(method="first"),5,labels=False)+1
    user_perf["m_score"] = pd.qcut(user_perf.monetary.rank(method="first"),5,labels=False)+1
    conditions=[(user_perf.r_score>=4)&(user_perf.f_score>=4),user_perf.f_score>=4,(user_perf.r_score>=4)&(user_perf.f_score<=2),(user_perf.r_score<=2)&(user_perf.f_score>=3),(user_perf.r_score<=2)&(user_perf.f_score<=2)]
    user_perf["rfm_segment"] = np.select(conditions,["Champions","Loyal","New & Promising","At Risk","Hibernating"],default="Potential Loyalists")
    rfm = user_perf.groupby("rfm_segment").agg(users=("user_id","nunique"),revenue=("monetary","sum"),avg_frequency=("frequency","mean")).reset_index().sort_values("revenue",ascending=False)
    ads = a.groupby(["campaign_id","campaign_name","channel"]).agg(impressions=("impressions","sum"),clicks=("clicks","sum"),spend=("spend","sum"),conversions=("conversions","sum"),revenue=("attributed_revenue","sum")).reset_index()
    ads["ctr"]=ads.clicks.div(ads.impressions.replace(0,np.nan)); ads["cvr"]=ads.conversions.div(ads.clicks.replace(0,np.nan)); ads["cpc"]=ads.spend.div(ads.clicks.replace(0,np.nan)); ads["cpa"]=ads.spend.div(ads.conversions.replace(0,np.nan)); ads["roas"]=ads.revenue.div(ads.spend.replace(0,np.nan))
    return {"monthly":monthly,"products":product_perf.sort_values("net_sales",ascending=False),"categories":category.sort_values("net_sales",ascending=False),"rfm":rfm,"user_rfm":user_perf,"ads":ads.sort_values("roas",ascending=False)}


def _font(size: int, bold: bool=False):
    candidates = ["C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
    for path in candidates:
        try: return ImageFont.truetype(path,size)
        except OSError: pass
    return ImageFont.load_default()


def dashboard_image(path: Path, title: str, subtitle: str, cards: list[tuple[str,str]], labels: list[str], values: list[float], insight: str, accent: str=BLUE, row_limit: int=6) -> None:
    img=Image.new("RGB",(1440,810),BG); d=ImageDraw.Draw(img)
    d.rounded_rectangle((40,30,1400,780),radius=24,fill="white")
    d.text((78,62),title,font=_font(34,True),fill=INK); d.text((78,108),subtitle,font=_font(16),fill=MUTED)
    card_w=236 if len(cards)>=5 else 250
    card_gap=24 if len(cards)>=5 else 18
    value_font=22 if len(cards)>=5 else 25
    for i,(label,value) in enumerate(cards):
        x=78+i*(card_w+card_gap); d.rounded_rectangle((x,150,x+card_w,260),radius=14,fill="#F8FAFC",outline="#E7ECF3")
        d.text((x+20,170),label,font=_font(15),fill=MUTED); d.text((x+20,207),value,font=_font(value_font,True),fill=INK)
    d.text((78,305),"Key comparison",font=_font(19,True),fill=INK)
    maxv=max(values) if values else 1
    compact = row_limit > 6
    for i,(lab,val) in enumerate(zip(labels[:row_limit],values[:row_limit])):
        y=(348+i*27) if compact else (355+i*50); bar_h=15 if compact else 24; font_size=12 if compact else 14
        d.text((78,y),lab[:22],font=_font(font_size),fill=INK)
        d.rounded_rectangle((285,y,285+700*val/maxv,y+bar_h),radius=6,fill=accent)
        d.text((1000,y),f"{val:,.1f}",font=_font(font_size,True),fill=INK)
    d.rounded_rectangle((1120,320,1360,685),radius=16,fill="#EFF6FF")
    d.text((1145,350),"Action insight",font=_font(17,True),fill=accent)
    words=insight.split(); lines=[]; line=""
    for word in words:
        if len(line)+len(word)>26: lines.append(line); line=word
        else: line=(line+" "+word).strip()
    lines.append(line)
    d.multiline_text((1145,395),"\n".join(lines),font=_font(15),fill=INK,spacing=9)
    d.text((78,744),"Synthetic portfolio data • TWD • 2025 • Asia/Taipei",font=_font(13),fill=MUTED)
    img.save(path)


def export(t: dict[str,pd.DataFrame], a: dict[str,pd.DataFrame], m: dict[str,float]) -> None:
    REPORTS.mkdir(exist_ok=True); CHARTS.mkdir(exist_ok=True)
    for name,frame in a.items():
        if name != "user_rfm":
            frame.to_csv(REPORTS/f"{name}_analysis.csv",index=False,encoding="utf-8-sig")
    rfm_columns = ["user_id","recency","frequency","monetary","r_score","f_score","m_score","rfm_segment"]
    powerbi_users = t["users"].merge(a["user_rfm"][rfm_columns], on="user_id", how="left", validate="one_to_one")
    powerbi_users.to_csv(ROOT/"dashboard"/"powerbi_data"/"users.csv",index=False,encoding="utf-8-sig")
    legacy_detail = REPORTS / "user_rfm_analysis.csv"
    if legacy_detail.exists(): legacy_detail.unlink()
    (REPORTS/"kpi_summary.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    cat=a["categories"]; ads=a["ads"]; rfm=a["rfm"]; monthly=a["monthly"]
    dashboard_image(REPORTS/"dashboard_overview.png","01 · Operations overview","Monthly completed net sales (NT$ millions), Jan-Dec 2025",[("GMV",f"NT$ {m['gmv']/1e6:.1f}M"),("Net sales",f"NT$ {m['net_sales']/1e6:.1f}M"),("Gross margin",f"{m['gross_margin']:.1%}"),("AOV",f"NT$ {m['aov']:,.0f}"),("Repeat rate",f"{m['repeat_rate']:.1%}")],monthly.month.tolist(),monthly.net_sales.div(1e6).tolist(),"Protect promotion-driven volume with margin floors; track net sales, profit and AOV together.",row_limit=12)
    top=a["products"].head(6); dashboard_image(REPORTS/"dashboard_product.png","02 · Product analysis","Which products and price spaces deserve action?",[("Products",f"{len(t['products']):,}"),("Top-20 share",f"{a['products'].head(20).net_sales.sum()/a['products'].net_sales.sum():.1%}"),("Avg margin",f"{a['products'].gross_profit.sum()/a['products'].net_sales.sum():.1%}"),("Opportunity ≥70",f"{t['products'].opportunity_score.ge(70).sum():,}")],top.product_name.tolist(),top.net_sales.div(1e3).tolist(),"Use Hot Score for proven demand and Opportunity Score only as a shortlist; validate supplier margin and real competition.",GREEN)
    dashboard_image(REPORTS/"dashboard_customer.png","03 · Customer analysis","Who should receive retention investment?",[("Buyers",f"{m['users']:,}"),("Repeat rate",f"{m['repeat_rate']:.1%}"),("Champions",f"{int(rfm.loc[rfm.rfm_segment.eq('Champions'),'users'].sum()):,}"),("At risk",f"{int(rfm.loc[rfm.rfm_segment.eq('At Risk'),'users'].sum()):,}")],rfm.rfm_segment.tolist(),rfm.revenue.div(1e6).tolist(),"Separate value from risk: reward Champions, trigger category-specific win-back journeys for At Risk users.","#7C3AED")
    dashboard_image(REPORTS/"dashboard_ads.png","04 · Advertising analysis","Where should the next TWD of budget go?",[("Spend",f"NT$ {t['ads'].spend.sum()/1e6:.2f}M"),("CTR",f"{m['ctr']:.2%}"),("CVR",f"{m['cvr']:.2%}"),("CPA",f"NT$ {m['cpa']:,.0f}"),("ROAS",f"{m['roas']:.2f}x")],ads.campaign_name.tolist(),ads.roas.tolist(),"Scale campaigns above the portfolio ROAS only after checking capacity and marginal CPA; repair weak CVR before buying more traffic.",RED)
    promo=t["orders"].merge(t["calendar"][["date","is_promotion","is_weekend"]],left_on="order_date",right_on="date"); promo=promo[promo.status.eq("completed")]
    daily=promo.groupby(["order_date","is_promotion"]).net_sales.sum().reset_index(); uplift=daily.groupby("is_promotion").net_sales.mean(); promo_uplift=float(uplift.get(1,0)/uplift.get(0,1)-1)
    best_cat=cat.iloc[0]; best_ad=ads.iloc[0]; low_ad=ads.iloc[-1]; top_opp=t["products"].sort_values("opportunity_score",ascending=False).iloc[0]
    insights=f"""# Core business insights

All findings describe fixed-seed synthetic portfolio data, not the real Taiwan Shopee market.

1. **Promotion days raised average daily completed net sales by {promo_uplift:.1%}.** A plausible cause is simulated traffic and discount uplift. Action: retain event inventory buffers but introduce SKU margin floors. Validate with promotion gross profit, AOV and cancellation/refund rate.
2. **{best_cat.category} generated the most net sales (NT$ {best_cat.net_sales:,.0f}) at a {best_cat.gross_margin:.1%} gross margin.** Mix and demand weights explain the result. Action: protect availability for top contributors and test bundles in adjacent categories. Validate incremental margin and attach rate.
3. **The annual buyer repeat rate was {m['repeat_rate']:.1%}.** Repeat propensity is intentionally heterogeneous. Action: run separate Champions loyalty and At Risk win-back treatments. Validate 30/60-day repeat rate, retained margin and unsubscribe rate.
4. **{best_ad.campaign_name} led campaign ROAS at {best_ad.roas:.2f}x, while {low_ad.campaign_name} was lowest at {low_ad.roas:.2f}x.** Differences come from simulated CTR/CVR/CPC. Action: shift a capped test budget toward the leader and diagnose creative vs landing-page leakage for the laggard. Validate marginal CPA and ROAS, not blended averages.
5. **{top_opp.product_name} ranked highest on Opportunity Score ({top_opp.opportunity_score:.1f}).** This reflects high synthetic demand with lower modeled crowding. Action: shortlist it for supplier and real-market research, not immediate launch. Validate real search volume, competitor count, landed margin and return risk.

## Limitations

The data is fully synthetic, scores are relative to this sample, ad revenue is attributed rather than causal, and no inventory or customer-level personal data exists. Findings demonstrate analytical method and must not be presented as real platform benchmarks.
"""
    (REPORTS/"insights.md").write_text(insights,encoding="utf-8")


def reconcile_sql(m: dict[str,float]) -> dict[str,float]:
    with sqlite3.connect(DB_PATH) as conn:
        row=conn.execute("""SELECT SUM(CASE WHEN status IN ('completed','refunded') THEN gross_amount ELSE 0 END),SUM(net_sales),COUNT(DISTINCT CASE WHEN status='completed' THEN order_id END),SUM(net_sales-cost) FROM orders""").fetchone()
        ad=conn.execute("SELECT SUM(clicks)*1.0/SUM(impressions),SUM(conversions)*1.0/SUM(clicks),SUM(attributed_revenue)*1.0/SUM(spend) FROM ads").fetchone()
    sql={"gmv":row[0],"net_sales":row[1],"orders":row[2],"gross_profit":row[3],"ctr":ad[0],"cvr":ad[1],"roas":ad[2]}
    for key,val in sql.items():
        if not np.isclose(val,m[key],rtol=1e-9,atol=.02): raise AssertionError(f"metric mismatch {key}: sql={val} python={m[key]}")
    return sql


def main() -> None:
    t=load(); build_sqlite(t); a=analyze(t); m=metrics(t); export(t,a,m); sql=reconcile_sql(m)
    print(json.dumps({"rows":{k:len(v) for k,v in t.items()},"kpis":m,"sql_reconciled":list(sql)},indent=2))

if __name__ == "__main__": main()
