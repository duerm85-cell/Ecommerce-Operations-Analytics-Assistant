"""Configuration and source contracts for Olist Phase 1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SourceSpec:
    filename: str
    table_name: str
    required_columns: tuple[str, ...]
    unique_key: tuple[str, ...] = ()
    time_columns: tuple[str, ...] = ()


SOURCE_SPECS: tuple[SourceSpec, ...] = (
    SourceSpec(
        "olist_customers_dataset.csv",
        "ods_olist_customers",
        (
            "customer_id",
            "customer_unique_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ),
        ("customer_id",),
    ),
    SourceSpec(
        "olist_geolocation_dataset.csv",
        "ods_olist_geolocation",
        (
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
            "geolocation_city",
            "geolocation_state",
        ),
    ),
    SourceSpec(
        "olist_order_items_dataset.csv",
        "ods_olist_order_items",
        (
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
        ),
        ("order_id", "order_item_id"),
        ("shipping_limit_date",),
    ),
    SourceSpec(
        "olist_order_payments_dataset.csv",
        "ods_olist_order_payments",
        (
            "order_id",
            "payment_sequential",
            "payment_type",
            "payment_installments",
            "payment_value",
        ),
        ("order_id", "payment_sequential"),
    ),
    SourceSpec(
        "olist_order_reviews_dataset.csv",
        "ods_olist_order_reviews",
        (
            "review_id",
            "order_id",
            "review_score",
            "review_comment_title",
            "review_comment_message",
            "review_creation_date",
            "review_answer_timestamp",
        ),
        ("review_id", "order_id"),
        ("review_creation_date", "review_answer_timestamp"),
    ),
    SourceSpec(
        "olist_orders_dataset.csv",
        "ods_olist_orders",
        (
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ),
        ("order_id",),
        (
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ),
    ),
    SourceSpec(
        "olist_products_dataset.csv",
        "ods_olist_products",
        (
            "product_id",
            "product_category_name",
            "product_name_lenght",
            "product_description_lenght",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ),
        ("product_id",),
    ),
    SourceSpec(
        "olist_sellers_dataset.csv",
        "ods_olist_sellers",
        (
            "seller_id",
            "seller_zip_code_prefix",
            "seller_city",
            "seller_state",
        ),
        ("seller_id",),
    ),
    SourceSpec(
        "product_category_name_translation.csv",
        "ods_olist_category_translation",
        ("product_category_name", "product_category_name_english"),
        ("product_category_name",),
    ),
)


@dataclass(frozen=True)
class OlistConfig:
    project_root: Path
    raw_dir: Path
    ods_db_path: Path
    manifest_path: Path
    failure_path: Path

    @property
    def source_specs(self) -> tuple[SourceSpec, ...]:
        return SOURCE_SPECS


def get_config(
    raw_dir: Optional[Path] = None,
    ods_db_path: Optional[Path] = None,
    project_root: Optional[Path] = None,
) -> OlistConfig:
    """Return paths for the Olist Phase 1 loader.

    Optional overrides make the loader straightforward to run against a
    temporary fixture without changing the production defaults.
    """

    root = Path(project_root or PROJECT_ROOT).resolve()
    raw = Path(raw_dir or root / "data" / "raw" / "olist").resolve()
    database = Path(ods_db_path or root / "data" / "olist_analytics.sqlite").resolve()
    return OlistConfig(
        project_root=root,
        raw_dir=raw,
        ods_db_path=database,
        manifest_path=root / "data" / "olist_source_manifest.json",
        failure_path=root / "data" / "olist_load_failure.json",
    )
