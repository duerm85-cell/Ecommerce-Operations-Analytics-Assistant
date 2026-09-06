"""Build reproducible e-commerce data with an optional public product input.

Users, orders and advertising rows remain synthetic. Product master attributes
prefer a validated public ODS file and fall back to the original fixed-seed
generator when that file is missing or contains no rows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

LOG = logging.getLogger("generate_data")
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_PRODUCTS = ROOT / "crawler" / "raw_data" / "raw_products.csv"
RAW_PRODUCT_FIELDS = ["product_id", "product_name", "category", "price", "rating", "review_count"]
SEED = 20260801
START = pd.Timestamp("2025-01-01")
END = pd.Timestamp("2025-12-31")
CATEGORIES = {
    "Skincare": (480, 0.43),
    "Makeup": (350, 0.48),
    "Hair Care": (420, 0.38),
    "Feminine Care": (260, 0.34),
    "Fashion Accessories": (560, 0.52),
    "Wellness": (620, 0.45),
}
REGIONS = ["Taipei", "New Taipei", "Taoyuan", "Taichung", "Tainan", "Kaohsiung", "Other"]
CHANNELS = ["Organic", "Search Ads", "Social Ads", "Affiliate", "CRM"]
PROMO_DATES = pd.to_datetime(["2025-02-14", "2025-06-18", "2025-09-09", "2025-11-11", "2025-12-12"])
CATEGORY_KEYWORDS = {
    "Skincare": ("skin", "facial", "beauty care"),
    "Makeup": ("makeup", "cosmetic", "lipstick", "foundation", "mascara"),
    "Hair Care": ("hair", "shampoo", "conditioner"),
    "Feminine Care": ("feminine", "menstrual", "sanitary", "period care"),
    "Fashion Accessories": ("fashion", "accessor", "clothing", "jewelry", "jewellery", "handbag"),
    "Wellness": ("wellness", "health", "supplement", "vitamin", "fitness"),
}


def _minmax(s: pd.Series) -> pd.Series:
    spread = s.max() - s.min()
    return (s - s.min()) / spread if spread else pd.Series(0.0, index=s.index)


def make_products(rng: np.random.Generator, n: int) -> pd.DataFrame:
    cats = rng.choice(list(CATEGORIES), n, p=[.24, .21, .14, .13, .15, .13])
    medians = np.array([CATEGORIES[c][0] for c in cats])
    prices = np.maximum(79, rng.lognormal(np.log(medians), .42)).round().astype(int)
    quality = rng.beta(5.5, 2.0, n)
    demand = rng.lognormal(3.6 + quality * 1.6, .85)
    sold = np.maximum(1, demand).round().astype(int)
    reviews = np.maximum(0, (sold * rng.uniform(.035, .16, n))).round().astype(int)
    rating = np.clip(3.5 + quality * 1.45 + rng.normal(0, .10, n), 3.4, 5).round(2)
    names = [f"{c} Essential {i:04d}" for i, c in enumerate(cats, 1)]
    products = pd.DataFrame({
        "product_id": [f"P{i:05d}" for i in range(1, n + 1)],
        "product_name": names,
        "category": cats,
        "price": prices,
        "sold_count": sold,
        "rating": rating,
        "review_count": reviews,
        "shop_name": [f"Sample Shop {i:03d}" for i in rng.integers(1, 121, n)],
        "location": rng.choice(REGIONS, n, p=[.24, .18, .11, .15, .09, .11, .12]),
        "crawl_time": pd.Timestamp("2026-08-01 10:00:00+08:00"),
        "source_url": [f"https://example.com/compliant-sample/product/{i}" for i in range(1, n + 1)],
        "data_source_type": "synthetic_compliant_sample",
    })
    products["hot_score"] = (100 * (.50 * _minmax(np.log1p(products.sold_count)) + .20 * _minmax(products.rating) + .30 * _minmax(np.log1p(products.review_count)))).round(2)
    cat_stats = products.groupby("category").agg(cat_count=("product_id", "size"), cat_sales=("sold_count", "sum"))
    products = products.join(cat_stats, on="category")
    price_bin = pd.cut(products.price, [0, 100, 300, 500, np.inf], labels=["0-100", "101-300", "301-500", "501+"])
    density = products.assign(price_band=price_bin).groupby(["category", "price_band"], observed=True).product_id.transform("count")
    demand_score = .65 * _minmax(np.log1p(products.sold_count)) + .35 * _minmax(np.log1p(products.review_count))
    competition = .55 * _minmax(products.cat_count) + .45 * _minmax(density)
    products["opportunity_score"] = (100 * (.65 * demand_score + .35 * (1 - competition))).round(2)
    return products.drop(columns=["cat_count", "cat_sales"])


def _canonical_category(value: str) -> str:
    if value in CATEGORIES:
        return value
    key = value.casefold()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in key for keyword in keywords):
            return category
    raise ValueError(
        f"unsupported external category '{value}'; map it to one of {list(CATEGORIES)} before ingestion"
    )


def _read_external_products(raw_path: Path | None) -> pd.DataFrame | None:
    if raw_path is None or not raw_path.exists():
        return None
    try:
        raw = pd.read_csv(raw_path, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return None
    if raw.empty:
        return None
    missing = [field for field in RAW_PRODUCT_FIELDS if field not in raw.columns]
    if missing:
        raise ValueError(f"external product ODS is missing columns: {missing}")
    products = raw[RAW_PRODUCT_FIELDS].copy()
    for field in ["product_id", "product_name", "category"]:
        products[field] = products[field].astype("string").str.strip()
        if products[field].isna().any() or products[field].eq("").any():
            raise ValueError(f"external product ODS contains blank {field} values")
    for field in ["price", "rating", "review_count"]:
        products[field] = pd.to_numeric(products[field], errors="coerce")
        if products[field].isna().any():
            raise ValueError(f"external product ODS contains invalid {field} values")
    if products.product_id.duplicated().any():
        raise ValueError("external product ODS contains duplicate product_id values")
    if not products.price.gt(0).all():
        raise ValueError("external product prices must be greater than zero")
    if not products.rating.between(0.01, 5).all():
        raise ValueError("external product ratings must be greater than 0 and no greater than 5")
    if not products.review_count.ge(0).all() or not np.allclose(products.review_count, products.review_count.round()):
        raise ValueError("external product review_count values must be non-negative integers")
    products["review_count"] = products.review_count.astype(int)
    products["category"] = products.category.map(_canonical_category)
    return products


def _safe_external_ids(raw_ids: pd.Series, reserved: set[str]) -> list[str]:
    selected: list[str] = []
    used = set(reserved)
    for raw_id in raw_ids.astype(str):
        candidate = raw_id if len(raw_id) <= 16 else "E" + hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:15]
        if candidate in used:
            candidate = "E" + hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:15]
        if candidate in used:
            raise ValueError(f"external product_id collision after normalization: {raw_id}")
        selected.append(candidate)
        used.add(candidate)
    return selected


def make_products_prefer_external(
    rng: np.random.Generator,
    n: int,
    raw_path: Path | None = DEFAULT_RAW_PRODUCTS,
) -> tuple[pd.DataFrame, str]:
    """Keep the original product fallback and overlay validated ODS attributes."""
    products = make_products(rng, n)
    external = _read_external_products(raw_path)
    if external is None:
        LOG.info("product_source=synthetic_fallback path=%s", raw_path)
        return products, "synthetic_fallback"

    count = min(len(external), n)
    external = external.iloc[:count].copy()
    external_rows = products.iloc[:count].copy()
    reserved_ids = set(products.iloc[count:].product_id.astype(str))
    external_rows["product_id"] = _safe_external_ids(external.product_id, reserved_ids)
    external_rows["product_name"] = external.product_name.str.slice(0, 255).to_numpy()
    external_rows["category"] = external.category.to_numpy()
    external_rows["price"] = external.price.round(2).to_numpy()
    external_rows["rating"] = external.rating.round(2).to_numpy()
    external_rows["review_count"] = external.review_count.to_numpy()
    external_rows["shop_name"] = "External Market Dataset"
    external_rows["location"] = "External Market"
    external_rows["crawl_time"] = pd.Timestamp.fromtimestamp(raw_path.stat().st_mtime, tz="Asia/Taipei").floor("s")
    external_rows["source_url"] = "crawler/raw_data/raw_products.csv"
    external_rows["data_source_type"] = "external_market"
    products = pd.concat([external_rows, products.iloc[count:]], ignore_index=True)

    products["hot_score"] = (
        100
        * (
            .50 * _minmax(np.log1p(products.sold_count))
            + .20 * _minmax(products.rating)
            + .30 * _minmax(np.log1p(products.review_count))
        )
    ).round(2)
    category_count = products.groupby("category").product_id.transform("count")
    price_bin = pd.cut(products.price, [0, 100, 300, 500, np.inf], labels=["0-100", "101-300", "301-500", "501+"])
    density = products.assign(price_band=price_bin).groupby(["category", "price_band"], observed=True).product_id.transform("count")
    demand_score = .65 * _minmax(np.log1p(products.sold_count)) + .35 * _minmax(np.log1p(products.review_count))
    competition = .55 * _minmax(category_count) + .45 * _minmax(density)
    products["opportunity_score"] = (100 * (.65 * demand_score + .35 * (1 - competition))).round(2)
    source = "external_market" if count == n else "external_market+synthetic_fallback"
    LOG.info("product_source=%s external_rows=%s total_rows=%s path=%s", source, count, n, raw_path)
    return products, source


def make_users(rng: np.random.Generator, n: int) -> pd.DataFrame:
    propensity = rng.beta(1.7, 3.2, n)
    return pd.DataFrame({
        "user_id": [f"U{i:06d}" for i in range(1, n + 1)],
        "age_group": rng.choice(["18-24", "25-34", "35-44", "45-54", "55+"], n, p=[.18, .36, .25, .14, .07]),
        "region": rng.choice(REGIONS, n, p=[.25, .18, .11, .15, .09, .11, .11]),
        "register_date": START - pd.to_timedelta(rng.integers(0, 730, n), unit="D"),
        "acquisition_channel": rng.choice(CHANNELS, n, p=[.29, .23, .20, .12, .16]),
        "repeat_propensity": propensity.round(4),
        "data_source_type": "synthetic",
    })


def make_orders(rng: np.random.Generator, products: pd.DataFrame, users: pd.DataFrame, n: int) -> pd.DataFrame:
    day_index = pd.date_range(START, END, freq="D")
    weights = np.ones(len(day_index))
    weights *= np.where(day_index.dayofweek >= 5, 1.28, 1.0)
    for promo in PROMO_DATES:
        weights *= np.where(abs((day_index - promo).days) <= 1, 2.4, 1.0)
    weights /= weights.sum()
    dates = rng.choice(day_index.values, n, p=weights)
    user_w = .15 + users.repeat_propensity.to_numpy() * 2.5
    user_w /= user_w.sum()
    user_idx = rng.choice(len(users), n, p=user_w)
    product_w = np.power(products.sold_count.to_numpy(), .72)
    product_w /= product_w.sum()
    product_idx = rng.choice(len(products), n, p=product_w)
    quantity = rng.choice([1, 2, 3, 4], n, p=[.72, .20, .065, .015])
    unit_price = products.price.to_numpy()[product_idx].astype(float)
    is_promo = np.array([np.min(np.abs((PROMO_DATES - pd.Timestamp(d)).days)) <= 1 for d in dates])
    discount_rate = np.clip(rng.normal(.055 + .09 * is_promo, .035, n), 0, .28)
    gross_amount = unit_price * quantity
    discount_amount = (gross_amount * discount_rate).round(2)
    statuses = rng.choice(["completed", "refunded", "cancelled"], n, p=[.932, .042, .026])
    cat = products.category.to_numpy()[product_idx]
    margin = np.array([CATEGORIES[c][1] for c in cat])
    cost = (gross_amount * (1 - margin) * rng.normal(1, .025, n)).round(2)
    refund_amount = np.where(statuses == "refunded", gross_amount - discount_amount, 0).round(2)
    net_sales = np.where(statuses == "completed", gross_amount - discount_amount, 0).round(2)
    cost = np.where(statuses == "completed", cost, 0).round(2)
    return pd.DataFrame({
        "order_id": [f"O{i:08d}" for i in range(1, n + 1)],
        "user_id": users.user_id.to_numpy()[user_idx],
        "product_id": products.product_id.to_numpy()[product_idx],
        "order_date": pd.to_datetime(dates),
        "quantity": quantity,
        "unit_price": unit_price.round(2),
        "discount_amount": discount_amount,
        "gross_amount": gross_amount.round(2),
        "refund_amount": refund_amount,
        "net_sales": net_sales,
        "cost": cost,
        "status": statuses,
        "currency": "TWD",
        "data_source_type": "synthetic",
    }).sort_values(["order_date", "order_id"])


def make_ads(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    specs = [
        ("Search Ads", "Brand Search", .038, .085, 9.0, 850),
        ("Search Ads", "Category Search", .026, .061, 11.5, 690),
        ("Social Ads", "Prospecting Video", .014, .035, 7.5, 520),
        ("Social Ads", "Retargeting", .023, .072, 8.5, 780),
        ("Affiliate", "Creator Review", .031, .054, 6.5, 610),
        ("CRM", "Member Reactivation", .062, .095, 3.8, 720),
    ]
    for d in pd.date_range(START, END):
        promo = any(abs((d - p).days) <= 1 for p in PROMO_DATES)
        for i, (channel, name, ctr, cvr, cpc, aov) in enumerate(specs, 1):
            impressions = int(rng.lognormal(8.0, .25) * (1.55 if promo else 1))
            clicks = int(rng.binomial(impressions, min(.16, ctr * (1.10 if promo else 1))))
            conversions = int(rng.binomial(clicks, min(.25, cvr * (1.18 if promo else 1)))) if clicks else 0
            spend = round(clicks * max(1, rng.normal(cpc, cpc * .08)), 2)
            revenue = round(conversions * max(100, rng.normal(aov, aov * .12)), 2)
            rows.append((d, f"C{i:02d}", name, channel, impressions, clicks, spend, conversions, revenue))
    return pd.DataFrame(rows, columns=["date", "campaign_id", "campaign_name", "channel", "impressions", "clicks", "spend", "conversions", "attributed_revenue"]).assign(currency="TWD", data_source_type="synthetic")


def make_calendar() -> pd.DataFrame:
    d = pd.DataFrame({"date": pd.date_range(START, END)})
    iso = d.date.dt.isocalendar()
    d["year"] = d.date.dt.year
    d["quarter"] = "Q" + d.date.dt.quarter.astype(str)
    d["month"] = d.date.dt.strftime("%Y-%m")
    d["week"] = iso.week.astype(int)
    d["weekday"] = d.date.dt.day_name()
    d["is_weekend"] = d.date.dt.dayofweek.ge(5).astype(int)
    d["is_promotion"] = d.date.isin(PROMO_DATES).astype(int)
    return d


def generate(
    output: Path,
    samples: Path,
    powerbi: Path,
    products_n: int,
    users_n: int,
    orders_n: int,
    raw_products: Path | None = DEFAULT_RAW_PRODUCTS,
) -> dict[str, int]:
    rng = np.random.default_rng(SEED)
    # Extract and standardize the product ODS; an empty input keeps the original fallback.
    products, product_source = make_products_prefer_external(rng, products_n, raw_products)
    # Build DWD-grain entities. Internal users, orders and ads remain fixed-seed simulations.
    tables = {
        "products": products,
        "users": make_users(rng, users_n),
        "orders": None,
        "ads": make_ads(rng),
        "calendar": make_calendar(),
    }
    tables["orders"] = make_orders(rng, tables["products"], tables["users"], orders_n)
    # Load identical detail contracts for analysis, samples and the Power BI input directory.
    output.mkdir(parents=True, exist_ok=True); samples.mkdir(parents=True, exist_ok=True); powerbi.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(output / f"{name}.csv", index=False, encoding="utf-8-sig")
        df.to_csv(powerbi / f"{name}.csv", index=False, encoding="utf-8-sig")
        df.head(50).to_csv(samples / f"{name}_sample.csv", index=False, encoding="utf-8-sig")
    manifest = {"seed": SEED, "generated_at": "2026-08-01", "currency": "TWD", "timezone": "Asia/Taipei", "rows": {k: len(v) for k, v in tables.items()}, "classification": "100% synthetic; source URLs are non-production example.com placeholders"}
    if product_source != "synthetic_fallback":
        manifest["product_source"] = product_source
        manifest["classification"] = "External public product attributes; sold_count, users, orders and ads remain synthetic"
    (output / "generation_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest["rows"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=Path("data/processed"))
    ap.add_argument("--samples", type=Path, default=Path("data/sample"))
    ap.add_argument("--powerbi", type=Path, default=Path("dashboard/powerbi_data"))
    ap.add_argument("--products", type=int, default=800)
    ap.add_argument("--users", type=int, default=12000)
    ap.add_argument("--orders", type=int, default=60000)
    ap.add_argument("--raw-products", type=Path, default=DEFAULT_RAW_PRODUCTS)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(json.dumps(generate(args.output, args.samples, args.powerbi, args.products, args.users, args.orders, args.raw_products), indent=2))
