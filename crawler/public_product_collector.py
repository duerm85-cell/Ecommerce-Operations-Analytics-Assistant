"""Conservative public-page collector framework.

Disabled by default: the V1.0 dataset is synthetic. This module demonstrates
robots checks, rate limiting, bounded retries, explicit field mapping and logs.
It must never be used to bypass login, CAPTCHA, access controls, or site terms.
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import asdict, dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

LOG = logging.getLogger("public_product_collector")
USER_AGENT = "EcommerceAnalyticsPortfolioBot/1.0 (+educational; contact-required-before-production)"


@dataclass
class ProductRecord:
    product_id: str
    product_name: str
    category: str
    price: float
    sold_count: int
    rating: float
    review_count: int
    shop_name: str
    location: str
    crawl_time: str
    source_url: str


def robots_allows(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser(robots_url)
    parser.read()
    return parser.can_fetch(USER_AGENT, url)


def fetch_public_json(url: str, timeout: int = 15, delay: float = 2.0, retries: int = 2) -> dict:
    if not robots_allows(url):
        raise PermissionError(f"robots.txt does not allow collection: {url}")
    for attempt in range(retries + 1):
        try:
            time.sleep(delay)
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=timeout) as response:
                content_type = response.headers.get("content-type", "")
                body = response.read()
            if "application/json" not in content_type:
                raise ValueError("Expected a documented public JSON endpoint")
            return json.loads(body.decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            LOG.warning("attempt=%s url=%s error=%s", attempt + 1, url, exc)
            if attempt == retries:
                raise
            time.sleep(delay * (2 ** attempt))
    raise RuntimeError("unreachable")


def map_record(payload: dict, source_url: str) -> ProductRecord:
    required = ["id", "name", "category", "price", "sold_count", "rating", "review_count", "shop_name", "location"]
    missing = [key for key in required if key not in payload]
    if missing:
        raise KeyError(f"missing required fields: {missing}")
    return ProductRecord(str(payload["id"]), str(payload["name"]), str(payload["category"]), float(payload["price"]), int(payload["sold_count"]), float(payload["rating"]), int(payload["review_count"]), str(payload["shop_name"]), str(payload["location"]), time.strftime("%Y-%m-%dT%H:%M:%S%z"), source_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch one explicitly approved public JSON endpoint")
    parser.add_argument("--url", required=True)
    parser.add_argument("--acknowledge-terms", action="store_true", help="Confirm manual terms review before any request")
    args = parser.parse_args()
    if not args.acknowledge_terms:
        raise SystemExit("Stopped: review terms/robots and pass --acknowledge-terms")
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(asdict(map_record(fetch_public_json(args.url), args.url)), ensure_ascii=False, indent=2))
