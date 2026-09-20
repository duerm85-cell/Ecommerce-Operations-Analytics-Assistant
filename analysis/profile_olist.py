"""Generate a read-only data profile for the Kaggle Olist CSV files."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data" / "raw" / "olist"
DEFAULT_REPORT = ROOT / "docs" / "olist_data_profile.md"

EXPECTED_FILES = [
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
]

KEY_CANDIDATES = {
    "olist_customers_dataset.csv": [
        (("customer_id",), "row identifier and orders foreign-key target"),
        (("customer_unique_id",), "person-level identifier; expected to repeat across purchases"),
    ],
    "olist_geolocation_dataset.csv": [
        (("geolocation_zip_code_prefix",), "non-unique geographic lookup key"),
        (("geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng", "geolocation_city", "geolocation_state"), "full geographic tuple"),
    ],
    "olist_order_items_dataset.csv": [
        (("order_id", "order_item_id"), "order-line composite key"),
    ],
    "olist_order_payments_dataset.csv": [
        (("order_id", "payment_sequential"), "payment-record composite key"),
    ],
    "olist_order_reviews_dataset.csv": [
        (("review_id",), "review identifier"),
        (("order_id",), "order relationship; may repeat"),
        (("review_id", "order_id"), "review/order composite candidate"),
    ],
    "olist_orders_dataset.csv": [
        (("order_id",), "order header key"),
        (("customer_id",), "customer-record foreign key; unique in this snapshot but not the person identifier"),
    ],
    "olist_products_dataset.csv": [
        (("product_id",), "product key"),
    ],
    "olist_sellers_dataset.csv": [
        (("seller_id",), "seller key"),
    ],
    "product_category_name_translation.csv": [
        (("product_category_name",), "Portuguese category key"),
        (("product_category_name_english",), "English category label"),
    ],
}


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    def cell(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(map(cell, headers)) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    lines.extend("| " + " | ".join(cell(v) for v in row) + " |" for row in rows)
    return "\n".join(lines)


def time_columns(frame: pd.DataFrame) -> list[str]:
    return [
        column
        for column in frame.columns
        if "timestamp" in column.lower() or column.lower().endswith("_date")
    ]


def key_profile(frame: pd.DataFrame, columns: tuple[str, ...]) -> dict[str, object]:
    missing_rows = int(frame[list(columns)].isna().any(axis=1).sum())
    duplicate_excess = int(frame.duplicated(subset=list(columns)).sum())
    duplicate_rows = int(frame.duplicated(subset=list(columns), keep=False).sum())
    distinct = int(frame[list(columns)].drop_duplicates().shape[0])
    return {
        "columns": ", ".join(columns),
        "distinct": distinct,
        "missing_rows": missing_rows,
        "duplicate_excess": duplicate_excess,
        "duplicate_rows": duplicate_rows,
        "unique_non_null": missing_rows == 0 and duplicate_excess == 0,
    }


def profile_file(path: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    frame = pd.read_csv(path, low_memory=False)
    columns = []
    for name in frame.columns:
        missing = int(frame[name].isna().sum())
        columns.append(
            {
                "name": name,
                "dtype": str(frame[name].dtype),
                "missing": missing,
                "missing_rate": missing / len(frame) if len(frame) else 0.0,
                "distinct_non_null": int(frame[name].nunique(dropna=True)),
            }
        )

    times = []
    for name in time_columns(frame):
        parsed = pd.to_datetime(frame[name], errors="coerce")
        valid = parsed.dropna()
        times.append(
            {
                "column": name,
                "valid": int(valid.size),
                "invalid_or_missing": int(parsed.isna().sum()),
                "minimum": valid.min().isoformat(sep=" ") if not valid.empty else "N/A",
                "maximum": valid.max().isoformat(sep=" ") if not valid.empty else "N/A",
            }
        )

    keys = []
    for candidate, note in KEY_CANDIDATES[path.name]:
        values = key_profile(frame, candidate)
        values["note"] = note
        keys.append(values)

    samples = frame.head(3).where(pd.notna(frame.head(3)), None).to_dict(orient="records")
    return frame, {
        "file": path.name,
        "bytes": path.stat().st_size,
        "rows": len(frame),
        "columns_count": len(frame.columns),
        "columns": columns,
        "full_row_duplicate_excess": int(frame.duplicated().sum()),
        "full_row_duplicate_rows": int(frame.duplicated(keep=False).sum()),
        "keys": keys,
        "times": times,
        "samples": samples,
    }


def relation_profile(
    child: pd.DataFrame,
    child_column: str,
    parent: pd.DataFrame,
    parent_column: str,
) -> dict[str, int]:
    child_values = child[child_column].dropna()
    parent_values = parent[parent_column].dropna()
    parent_set = set(parent_values)
    orphan_mask = ~child_values.isin(parent_set)
    return {
        "child_rows": int(child_values.size),
        "child_distinct": int(child_values.nunique()),
        "orphan_rows": int(orphan_mask.sum()),
        "orphan_distinct": int(child_values[orphan_mask].nunique()),
        "parent_rows": int(parent_values.size),
        "parent_distinct": int(parent_values.nunique()),
    }


def build_report(data_dir: Path, output: Path) -> None:
    missing_files = [name for name in EXPECTED_FILES if not (data_dir / name).is_file()]
    if missing_files:
        raise FileNotFoundError(f"missing expected Olist files: {missing_files}")

    frames: dict[str, pd.DataFrame] = {}
    profiles: dict[str, dict[str, object]] = {}
    for name in EXPECTED_FILES:
        frames[name], profiles[name] = profile_file(data_dir / name)

    customers = frames["olist_customers_dataset.csv"]
    geolocation = frames["olist_geolocation_dataset.csv"]
    items = frames["olist_order_items_dataset.csv"]
    payments = frames["olist_order_payments_dataset.csv"]
    reviews = frames["olist_order_reviews_dataset.csv"]
    orders = frames["olist_orders_dataset.csv"]
    products = frames["olist_products_dataset.csv"]
    sellers = frames["olist_sellers_dataset.csv"]
    translation = frames["product_category_name_translation.csv"]

    relation_specs = [
        ("orders.customer_id → customers.customer_id", orders, "customer_id", customers, "customer_id"),
        ("order_items.order_id → orders.order_id", items, "order_id", orders, "order_id"),
        ("order_items.product_id → products.product_id", items, "product_id", products, "product_id"),
        ("order_items.seller_id → sellers.seller_id", items, "seller_id", sellers, "seller_id"),
        ("payments.order_id → orders.order_id", payments, "order_id", orders, "order_id"),
        ("reviews.order_id → orders.order_id", reviews, "order_id", orders, "order_id"),
        ("products.product_category_name → translation.product_category_name", products, "product_category_name", translation, "product_category_name"),
        ("customers.zip_prefix → geolocation.zip_prefix", customers, "customer_zip_code_prefix", geolocation, "geolocation_zip_code_prefix"),
        ("sellers.zip_prefix → geolocation.zip_prefix", sellers, "seller_zip_code_prefix", geolocation, "geolocation_zip_code_prefix"),
    ]
    relations = [
        (label, relation_profile(child, child_col, parent, parent_col))
        for label, child, child_col, parent, parent_col in relation_specs
    ]

    unique_to_customer = customers.groupby("customer_unique_id")["customer_id"].nunique()
    item_counts = items.groupby("order_id").size()
    payment_counts = payments.groupby("order_id").size()
    review_counts = reviews.groupby("order_id").size()
    product_categories = products["product_category_name"].dropna()
    translation_keys = set(translation["product_category_name"].dropna())
    unmatched_categories = sorted(set(product_categories) - translation_keys)

    order_purchase = pd.to_datetime(orders["order_purchase_timestamp"], errors="coerce")
    downloaded_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")

    lines = [
        "# Olist 真实公开数据集审查报告",
        "",
        "> 本报告由 `analysis/profile_olist.py` 对原始 CSV 进行只读扫描生成。本阶段只认识数据，不进行字段映射、ETL、数据库或 Power BI 改造。",
        "",
        "## 1. 数据来源与版本",
        "",
        "- 数据集：Brazilian E-Commerce Public Dataset by Olist",
        "- Kaggle 标识：`olistbr/brazilian-ecommerce`",
        "- 官方页面：https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
        "- Kaggle 文件版本时间：2021-10-01（CLI 文件清单显示）",
        f"- 本地下载/画像时间：{downloaded_at}",
        "- 许可证：CC BY-NC-SA 4.0（Kaggle CLI 下载输出）",
        "- 原始目录：`data/raw/olist/`（由 Git 忽略，不应提交）",
        "- 金额语境：巴西雷亚尔 BRL；时间字段未携带时区。",
        "",
        "## 2. 文件清单",
        "",
        md_table(
            ["文件", "大小 MiB", "行数", "列数", "完整重复行（超额）", "唯一且非空的候选键"],
            [
                [
                    p["file"],
                    f"{p['bytes'] / 1024 / 1024:.2f}",
                    f"{p['rows']:,}",
                    p["columns_count"],
                    f"{p['full_row_duplicate_excess']:,}",
                    "; ".join(k["columns"] for k in p["keys"] if k["unique_non_null"]) or "无",
                ]
                for p in profiles.values()
            ],
        ),
        "",
        "## 3. 表关系与覆盖情况",
        "",
        md_table(
            ["关系", "子表行数", "子键去重数", "孤儿行", "孤儿键", "父键去重数"],
            [
                [label, f"{r['child_rows']:,}", f"{r['child_distinct']:,}", f"{r['orphan_rows']:,}", f"{r['orphan_distinct']:,}", f"{r['parent_distinct']:,}"]
                for label, r in relations
            ],
        ),
        "",
        "### 关键基数结论",
        "",
        f"- `customer_id` 有 {customers['customer_id'].nunique():,} 个，逐行唯一，用于 `orders.customer_id` 外键；`customer_unique_id` 有 {customers['customer_unique_id'].nunique():,} 个，代表跨订单的同一客户。",
        f"- 有 {(unique_to_customer > 1).sum():,} 个 `customer_unique_id` 对应多个 `customer_id`；单个客户最多对应 {int(unique_to_customer.max()):,} 个 customer records。因此复购/客户生命周期必须使用 `customer_unique_id`。",
        f"- 订单总数 {orders['order_id'].nunique():,}；有商品明细的订单 {item_counts.size:,}，其中 {(item_counts > 1).sum():,} 个订单包含多条 order items，单笔最多 {int(item_counts.max()):,} 条。",
        f"- 有支付记录的订单 {payment_counts.size:,}，其中 {(payment_counts > 1).sum():,} 个订单包含多笔 payment records，单笔最多 {int(payment_counts.max()):,} 条。",
        f"- 有评价记录的订单 {review_counts.size:,}，其中 {(review_counts > 1).sum():,} 个订单包含多条 review records，单笔最多 {int(review_counts.max()):,} 条。",
        f"- `products.product_category_name` 的非空类别共 {product_categories.nunique():,} 个；翻译表含 {translation['product_category_name'].nunique():,} 个葡萄牙语类别键；未匹配类别 {len(unmatched_categories):,} 个：{', '.join(unmatched_categories) if unmatched_categories else '无'}。",
        f"- 全局订单购买时间范围：{order_purchase.min().isoformat(sep=' ')} 至 {order_purchase.max().isoformat(sep=' ')}。",
        "",
        "### 关系语义",
        "",
        "- `orders` 是订单头；`order_items` 是订单商品明细，通过 `order_id` 一对多关联。",
        "- `order_items.product_id` 关联 `products.product_id`；`order_items.seller_id` 关联 `sellers.seller_id`。",
        "- `payments` 在订单粒度下可能多行，进入订单级分析前必须按 `order_id` 聚合或保留 payment sequence。",
        "- `reviews` 不是严格一订单一行，不能直接与 order items 同时展开连接，否则可能产生行数乘积。",
        "- `products.product_category_name` 通过葡萄牙语类别键左连接 `product_category_name_translation.product_category_name`，得到英文类别。",
        "- geolocation 同一邮编前缀有多条坐标，不能把它当作唯一维表直接连接；需要先确定聚合或去重规则。",
        "",
        "## 4. 每个 CSV 的详细画像",
    ]

    for name in EXPECTED_FILES:
        p = profiles[name]
        lines.extend(
            [
                "",
                f"### {name}",
                "",
                f"- 行数：{p['rows']:,}",
                f"- 列数：{p['columns_count']}",
                f"- 文件大小：{p['bytes']:,} bytes",
                f"- 完整重复行（超额）：{p['full_row_duplicate_excess']:,}",
                f"- 处于完整重复组中的行：{p['full_row_duplicate_rows']:,}",
                "",
                "#### 字段、dtype 与缺失值",
                "",
                md_table(
                    ["字段", "pandas dtype", "非空去重值", "缺失数", "缺失率"],
                    [[c["name"], c["dtype"], f"{c['distinct_non_null']:,}", f"{c['missing']:,}", f"{c['missing_rate']:.4%}"] for c in p["columns"]],
                ),
                "",
                "#### 主键候选与重复",
                "",
                md_table(
                    ["字段组合", "非空唯一", "组合去重数", "缺失行", "重复超额", "重复组内行", "说明"],
                    [[k["columns"], "是" if k["unique_non_null"] else "否", f"{k['distinct']:,}", f"{k['missing_rows']:,}", f"{k['duplicate_excess']:,}", f"{k['duplicate_rows']:,}", k["note"]] for k in p["keys"]],
                ),
            ]
        )
        if p["times"]:
            lines.extend(
                [
                    "",
                    "#### 时间范围",
                    "",
                    md_table(
                        ["时间字段", "有效值", "缺失/无法解析", "最小值", "最大值"],
                        [[t["column"], f"{t['valid']:,}", f"{t['invalid_or_missing']:,}", t["minimum"], t["maximum"]] for t in p["times"]],
                    ),
                ]
            )
        else:
            lines.extend(["", "#### 时间范围", "", "无时间字段。"])
        lines.extend(
            [
                "",
                "#### 前 3 行样例",
                "",
                "```json",
                json.dumps(p["samples"], ensure_ascii=False, indent=2, default=str),
                "```",
            ]
        )

    missing_summary = []
    for p in profiles.values():
        affected = [c for c in p["columns"] if c["missing"]]
        if affected:
            missing_summary.append(
                f"- `{p['file']}`：" + "; ".join(f"{c['name']} {c['missing']:,} ({c['missing_rate']:.2%})" for c in affected)
            )

    lines.extend(
        [
            "",
            "## 5. 主要数据质量发现",
            "",
            f"- geolocation 表包含 {profiles['olist_geolocation_dataset.csv']['full_row_duplicate_excess']:,} 条完整重复超额行，并且邮编前缀非唯一。",
            f"- orders 中无 order items 的订单有 {orders['order_id'].nunique() - item_counts.size:,} 个；无 payment records 的订单有 {orders['order_id'].nunique() - payment_counts.size:,} 个；无 review records 的订单有 {orders['order_id'].nunique() - review_counts.size:,} 个。",
            "- 订单交付/审批时间的缺失通常与 cancelled、unavailable 或未完成状态有关，不能无条件填充。",
            "- review 标题和正文存在大量空值，这是可选文本字段，不应按数值缺失规则处理。",
            "- products 的类别、名称/描述长度、图片数量和部分尺寸重量存在缺失；类别翻译应采用左连接保留未知类别。",
            "- 数据使用匿名标识；`customer_unique_id` 是客户分析键，`customer_id` 是订单关联所使用的 customer record 键。",
            "",
            "### 各表非零缺失字段",
            "",
            *(missing_summary or ["无缺失值。"]),
            "",
            "## 6. 后续 ETL 注意事项",
            "",
            "1. 明确事实粒度：orders 为订单头，order_items 为商品明细；计算订单数必须 distinct order_id。",
            "2. 客户复购、生命周期和 RFM 使用 customer_unique_id；orders 仍通过 customer_id 关联 customers。",
            "3. payment 与 review 在 order_id 下都可能多行，应分别预聚合后再与订单/商品事实组合，避免笛卡尔放大。",
            "4. 商品类别翻译使用 left join，保留 products 中的空类别或未匹配类别，并记录映射覆盖率。",
            "5. geolocation 需要按邮编前缀建立明确的去重/中心点规则后才能作为维表使用。",
            "6. 订单状态决定销售确认、取消、不可用和交付时间缺失的解释；下一阶段必须先制定收入、订单和交付指标口径。",
            "7. 原始金额是 BRL，不能直接进入现有 TWD 指标体系；币种隔离或转换规则必须在下一阶段显式设计。",
            "8. 时间字段没有时区信息；接入前需记录巴西业务时区假设，避免与现有 Asia/Taipei 日历混用。",
            "9. 保留原始 CSV 不变，并在处理层记录数据集版本、下载日期和文件校验信息。",
        ]
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {output}")
    for name in EXPECTED_FILES:
        print(f"{name}: {profiles[name]['rows']} rows, {profiles[name]['columns_count']} columns")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    build_report(args.data_dir.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
