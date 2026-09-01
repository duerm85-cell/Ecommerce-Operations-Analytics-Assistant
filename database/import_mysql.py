"""Chunked CSV importer for MySQL 8; credentials come only from environment."""
from __future__ import annotations
import argparse, os
from pathlib import Path
import pandas as pd

TABLE_ORDER = ["products", "users", "calendar", "orders", "ads"]
DATE_COLUMNS = {
    "products": ["crawl_time"], "users": ["register_date"],
    "calendar": ["date"], "orders": ["order_date"], "ads": ["date"],
}

def normalize_for_mysql(table: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Convert CSV date values to MySQL-safe, timezone-naive Python values."""
    frame = frame.copy()
    for column in DATE_COLUMNS.get(table, []):
        parsed = pd.to_datetime(frame[column], errors="raise", utc=column == "crawl_time")
        if column == "crawl_time":
            # Source timestamps carry +08:00. DATETIME stores local wall time, not an offset.
            parsed = parsed.dt.tz_convert("Asia/Taipei").dt.tz_localize(None)
            frame[column] = parsed.dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            frame[column] = parsed.dt.strftime("%Y-%m-%d")
    return frame

def main() -> None:
    try:
        import pymysql
    except ImportError as exc:
        raise SystemExit("Install requirements first: python -m pip install -r requirements.txt") from exc
    ap = argparse.ArgumentParser(); ap.add_argument("--data-dir", type=Path, default=Path("data/processed")); args = ap.parse_args()
    required = ["MYSQL_HOST", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD"]
    missing = [k for k in required if not os.getenv(k)]
    if missing: raise SystemExit(f"Missing environment variables: {', '.join(missing)}")
    conn = pymysql.connect(host=os.environ["MYSQL_HOST"], port=int(os.getenv("MYSQL_PORT", "3306")), user=os.environ["MYSQL_USER"], password=os.environ["MYSQL_PASSWORD"], database=os.environ["MYSQL_DATABASE"], charset="utf8mb4", autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS=0")
            for table in reversed(TABLE_ORDER): cur.execute(f"TRUNCATE TABLE `{table}`")
            cur.execute("SET FOREIGN_KEY_CHECKS=1")
        for table in TABLE_ORDER:
            total = 0
            for frame in pd.read_csv(args.data_dir / f"{table}.csv", chunksize=5000):
                frame = normalize_for_mysql(table, frame)
                frame = frame.where(pd.notna(frame), None)
                cols = list(frame.columns); marks = ",".join(["%s"] * len(cols)); quoted = ",".join(f"`{c}`" for c in cols)
                with conn.cursor() as cur: cur.executemany(f"INSERT INTO `{table}` ({quoted}) VALUES ({marks})", list(frame.itertuples(index=False, name=None)))
                total += len(frame); conn.commit()
            print(f"{table}: {total} rows")
    finally: conn.close()

if __name__ == "__main__": main()
