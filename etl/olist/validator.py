"""Read-only validation of the nine Olist source CSV files."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd

from .config import OlistConfig, SourceSpec


LOGGER = logging.getLogger(__name__)


class OlistValidationError(ValueError):
    """Raised when a source contract or relationship check fails."""


@dataclass
class ValidationReport:
    frames: dict[str, pd.DataFrame]
    hashes: dict[str, str]
    row_counts: dict[str, int]
    date_min: str
    date_max: str
    time_ranges: dict[str, tuple[str, str]]
    checks: dict[str, str]


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_source_files(config: OlistConfig) -> dict[str, str]:
    """Hash every required source file in a stable source-spec order."""

    hashes: dict[str, str] = {}
    for spec in config.source_specs:
        path = config.raw_dir / spec.filename
        if not path.is_file():
            raise OlistValidationError(f"missing source file: {path}")
        hashes[spec.filename] = sha256_file(path)
    return hashes


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception as exc:  # pragma: no cover - pandas parser detail
        raise OlistValidationError(f"unable to read {path.name}: {exc}") from exc


def _require_columns(frame: pd.DataFrame, spec: SourceSpec) -> None:
    missing = [column for column in spec.required_columns if column not in frame.columns]
    if missing:
        raise OlistValidationError(
            f"{spec.filename} missing required columns: {', '.join(missing)}"
        )


def _assert_unique(frame: pd.DataFrame, columns: tuple[str, ...], label: str) -> None:
    if not columns:
        return
    if frame.loc[:, list(columns)].isna().any(axis=1).any():
        raise OlistValidationError(f"{label} contains NULL key values")
    duplicate_count = int(frame.duplicated(list(columns), keep=False).sum())
    if duplicate_count:
        raise OlistValidationError(
            f"{label} is not unique; duplicate_rows={duplicate_count}"
        )


def _assert_nonnegative(frame: pd.DataFrame, column: str, label: str) -> None:
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.isna().any():
        raise OlistValidationError(f"{label}.{column} contains non-numeric values")
    if (values < 0).any():
        raise OlistValidationError(f"{label}.{column} contains negative values")


def _assert_foreign_key(
    child: pd.DataFrame,
    child_column: str,
    parent: pd.DataFrame,
    parent_column: str,
    label: str,
) -> None:
    child_values = child[child_column]
    if child_values.isna().any():
        raise OlistValidationError(f"{label} contains NULL foreign keys")
    orphan_mask = ~child_values.isin(parent[parent_column])
    orphan_count = int(orphan_mask.sum())
    if orphan_count:
        orphan_values = child_values[orphan_mask].drop_duplicates().head(5).tolist()
        raise OlistValidationError(
            f"{label} has orphan_rows={orphan_count}; sample_keys={orphan_values}"
        )


def _parse_time_column(
    frame: pd.DataFrame, column: str, label: str
) -> pd.Series:
    raw = frame[column]
    parsed = pd.to_datetime(raw, errors="coerce", format="mixed")
    invalid = raw.notna() & parsed.isna()
    if invalid.any():
        raise OlistValidationError(
            f"{label}.{column} contains unparseable timestamps; rows={int(invalid.sum())}"
        )
    return parsed


def _collect_time_ranges(
    frames: Mapping[str, pd.DataFrame],
    config: OlistConfig,
) -> dict[str, tuple[str, str]]:
    ranges: dict[str, tuple[str, str]] = {}
    for spec in config.source_specs:
        frame = frames[spec.filename]
        for column in spec.time_columns:
            parsed = _parse_time_column(frame, column, spec.filename).dropna()
            if parsed.empty:
                continue
            ranges[f"{spec.filename}.{column}"] = (
                parsed.min().isoformat(sep=" "),
                parsed.max().isoformat(sep=" "),
            )
    return ranges


def validate_sources(
    config: OlistConfig,
    logger: logging.Logger | None = None,
) -> ValidationReport:
    """Read and validate all Olist CSVs without modifying them."""

    log = logger or LOGGER
    frames: dict[str, pd.DataFrame] = {}
    for spec in config.source_specs:
        path = config.raw_dir / spec.filename
        if not path.is_file():
            raise OlistValidationError(f"missing source file: {path}")
        if path.stat().st_size == 0:
            raise OlistValidationError(f"source file is empty: {path}")
        frame = _read_csv(path)
        if frame.empty:
            raise OlistValidationError(f"source file has no data rows: {path}")
        _require_columns(frame, spec)
        frames[spec.filename] = frame

    log.info(
        "[olist][validate] source_files=%d/%d",
        len(frames),
        len(config.source_specs),
    )
    log.info("[olist][validate] schema=passed")

    for spec in config.source_specs:
        _assert_unique(frames[spec.filename], spec.unique_key, spec.filename)

    items = frames["olist_order_items_dataset.csv"]
    payments = frames["olist_order_payments_dataset.csv"]
    orders = frames["olist_orders_dataset.csv"]
    customers = frames["olist_customers_dataset.csv"]
    products = frames["olist_products_dataset.csv"]
    sellers = frames["olist_sellers_dataset.csv"]
    reviews = frames["olist_order_reviews_dataset.csv"]

    _assert_foreign_key(
        orders, "customer_id", customers, "customer_id", "orders.customer_id"
    )
    _assert_foreign_key(
        items, "order_id", orders, "order_id", "order_items.order_id"
    )
    _assert_foreign_key(
        items, "product_id", products, "product_id", "order_items.product_id"
    )
    _assert_foreign_key(
        items, "seller_id", sellers, "seller_id", "order_items.seller_id"
    )
    _assert_foreign_key(
        payments, "order_id", orders, "order_id", "payments.order_id"
    )
    _assert_foreign_key(
        reviews, "order_id", orders, "order_id", "reviews.order_id"
    )
    log.info("[olist][validate] foreign_keys=passed")

    _assert_nonnegative(items, "price", "order_items")
    _assert_nonnegative(items, "freight_value", "order_items")
    _assert_nonnegative(payments, "payment_value", "payments")

    review_scores = pd.to_numeric(reviews["review_score"], errors="coerce")
    if review_scores.isna().any() or not review_scores.between(1, 5).all():
        raise OlistValidationError("reviews.review_score is outside the valid range 1..5")

    time_ranges = _collect_time_ranges(frames, config)
    purchase_key = "olist_orders_dataset.csv.order_purchase_timestamp"
    if purchase_key not in time_ranges:
        raise OlistValidationError("orders.order_purchase_timestamp has no valid values")
    date_min, date_max = time_ranges[purchase_key]

    hashes = hash_source_files(config)
    log.info("[olist][validate] amounts=passed")
    log.info("[olist][validate] timestamps=passed")
    log.info("[olist][validate] geolocation_uniqueness=not_required")

    return ValidationReport(
        frames=frames,
        hashes=hashes,
        row_counts={name: int(frame.shape[0]) for name, frame in frames.items()},
        date_min=date_min,
        date_max=date_max,
        time_ranges=time_ranges,
        checks={
            "source_files": "passed",
            "schema": "passed",
            "primary_and_composite_keys": "passed",
            "foreign_keys": "passed",
            "amounts": "passed",
            "review_score": "passed",
            "timestamps": "passed",
            "geolocation_uniqueness": "not_required",
        },
    )
