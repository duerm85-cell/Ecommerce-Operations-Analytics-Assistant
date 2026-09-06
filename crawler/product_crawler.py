"""Load a public product CSV/ZIP and normalize it to the product ODS contract.

The collector uses only public, unauthenticated files. It does not implement
login, cookies, CAPTCHA handling, proxy rotation, or anti-bot bypasses.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import time
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

USER_AGENT = "EcommerceOperationsAnalytics/2.0 (+public-data; contact-before-production)"
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
REQUIRED_FIELDS = (
    "product_id",
    "product_name",
    "category",
    "price",
    "rating",
    "review_count",
)
FIELD_ALIASES = {
    "product_id": ("product_id", "id", "asin", "sku", "model_number"),
    "product_name": ("product_name", "name", "title", "product"),
    "category": ("category", "product_category", "main_category", "breadcrumbs"),
    "price": ("price", "discounted_price", "price_value", "unit_price", "actual_price"),
    "rating": ("rating", "review_score", "rating_stars", "average_rating"),
    "review_count": ("review_count", "rating_count", "ratings_count", "num_reviews"),
}


def _column_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _parse_number(value: object, field: str) -> float:
    text = str(value).strip().replace(",", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if match is None:
        raise ValueError(f"{field} is empty")
    return float(match.group(0))


def _resolve_columns(fieldnames: list[str], overrides: dict[str, str] | None = None) -> dict[str, str]:
    overrides = overrides or {}
    normalized = {_column_key(name): name for name in fieldnames}
    resolved: dict[str, str] = {}
    for field in REQUIRED_FIELDS:
        requested = overrides.get(field)
        candidates = (requested,) if requested else FIELD_ALIASES[field]
        source = None
        for name in candidates:
            if name and _column_key(name) in normalized:
                source = normalized[_column_key(name)]
                break
        if source is None:
            raise ValueError(f"cannot map required field '{field}' from columns: {fieldnames}")
        resolved[field] = source
    return resolved


def normalize_rows(
    rows: list[dict[str, str]],
    fieldnames: list[str],
    overrides: dict[str, str] | None = None,
    price_multiplier: float = 1.0,
) -> tuple[list[dict[str, object]], int]:
    """Normalize public-source rows and return valid records plus reject count."""
    columns = _resolve_columns(fieldnames, overrides)
    records: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    rejected = 0
    for row in rows:
        try:
            product_id = str(row.get(columns["product_id"], "")).strip()
            product_name = str(row.get(columns["product_name"], "")).strip()
            category = str(row.get(columns["category"], "")).strip()
            price = _parse_number(row.get(columns["price"], ""), "price") * price_multiplier
            rating = _parse_number(row.get(columns["rating"], ""), "rating")
            review_value = _parse_number(row.get(columns["review_count"], ""), "review_count")
            review_count = int(review_value)
            if not product_id or not product_name or not category:
                raise ValueError("identifier, name and category are required")
            if price <= 0 or not 0 < rating <= 5 or review_value < 0 or review_count != review_value:
                raise ValueError("numeric values are outside the accepted product contract")
            if product_id in seen_ids:
                raise ValueError("duplicate product_id")
        except (TypeError, ValueError):
            rejected += 1
            continue
        seen_ids.add(product_id)
        records.append(
            {
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "price": round(price, 2),
                "rating": round(rating, 2),
                "review_count": review_count,
            }
        )
    if not records:
        raise ValueError("source contains no valid product rows")
    return records, rejected


def _robots_allows(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source URL must use public HTTP or HTTPS")
    parser = RobotFileParser(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
    try:
        parser.read()
    except Exception as exc:  # urllib and parser failures differ by host
        raise RuntimeError(f"unable to verify robots.txt for {parsed.netloc}") from exc
    return parser.can_fetch(USER_AGENT, url)


def fetch_public_file(url: str, acknowledge_terms: bool, timeout: int = 20) -> bytes:
    """Download one bounded public file after an explicit terms acknowledgement."""
    if not acknowledge_terms:
        raise PermissionError("review source terms and pass --acknowledge-terms before downloading")
    if not _robots_allows(url):
        raise PermissionError(f"robots.txt does not allow collection: {url}")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/csv,application/zip,*/*"})
    try:
        with urlopen(request, timeout=timeout) as response:
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > MAX_DOWNLOAD_BYTES:
                raise ValueError("source exceeds the 25 MB download limit")
            payload = response.read(MAX_DOWNLOAD_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"public download failed: {url}") from exc
    if len(payload) > MAX_DOWNLOAD_BYTES:
        raise ValueError("source exceeds the 25 MB download limit")
    return payload


def _csv_payload(payload: bytes, archive_member: str | None = None) -> bytes:
    if payload.startswith(b"PK\x03\x04"):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if archive_member:
                if archive_member not in archive.namelist():
                    raise ValueError(f"archive member not found: {archive_member}")
                selected = archive_member
            elif len(members) == 1:
                selected = members[0]
            else:
                raise ValueError(f"ZIP must contain one CSV or use --archive-member; found {members}")
            return archive.read(selected)
    return payload


def read_public_products(
    payload: bytes,
    archive_member: str | None = None,
    overrides: dict[str, str] | None = None,
    price_multiplier: float = 1.0,
) -> tuple[list[dict[str, object]], int]:
    """Parse CSV or ZIP bytes and normalize the supported product fields."""
    content = _csv_payload(payload, archive_member)
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1252")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("source CSV has no header")
    return normalize_rows(list(reader), list(reader.fieldnames), overrides, price_multiplier)


def write_raw_products(records: list[dict[str, object]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REQUIRED_FIELDS))
        writer.writeheader()
        writer.writerows(records)


def _parse_overrides(items: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"invalid --map value: {item}; expected canonical=source")
        canonical, source = (part.strip() for part in item.split("=", 1))
        if canonical not in REQUIRED_FIELDS or not source:
            raise ValueError(f"invalid --map value: {item}")
        overrides[canonical] = source
    return overrides


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize a public product CSV/ZIP to the ODS contract")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-file", type=Path, help="Local public dataset CSV or ZIP")
    source.add_argument("--source-url", help="Public unauthenticated CSV or ZIP URL")
    parser.add_argument("--output", type=Path, default=Path("crawler/raw_data/raw_products.csv"))
    parser.add_argument("--archive-member", help="CSV member name when a ZIP contains multiple files")
    parser.add_argument("--map", action="append", default=[], metavar="FIELD=SOURCE_COLUMN")
    parser.add_argument("--price-multiplier", type=float, default=1.0, help="Audited conversion factor to TWD")
    parser.add_argument("--acknowledge-terms", action="store_true")
    args = parser.parse_args()

    overrides = _parse_overrides(args.map)
    if args.source_file:
        payload = args.source_file.read_bytes()
    else:
        payload = fetch_public_file(args.source_url, args.acknowledge_terms)
    if args.price_multiplier <= 0:
        raise ValueError("--price-multiplier must be greater than zero")
    records, rejected = read_public_products(payload, args.archive_member, overrides, args.price_multiplier)
    write_raw_products(records, args.output)
    print(f"wrote {len(records)} products to {args.output}; rejected {rejected} rows; collected_at={time.strftime('%Y-%m-%dT%H:%M:%S%z')}")


if __name__ == "__main__":
    main()
