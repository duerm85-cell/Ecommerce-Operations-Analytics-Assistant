"""Transactional, idempotent ODS loader for the Olist public dataset."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import OlistConfig, SourceSpec, get_config
from .validator import (
    OlistValidationError,
    ValidationReport,
    hash_source_files,
    sha256_file,
    validate_sources,
)


LOGGER = logging.getLogger(__name__)
SYNTHETIC_DB_NAME = "data/analytics.sqlite"


@dataclass
class LoadSummary:
    batch_id: str
    database_path: Path
    manifest_path: Path
    row_counts: dict[str, int]
    date_min: str
    date_max: str
    raw_csv_hashes_unchanged: bool
    synthetic_database_unchanged: bool
    load_status: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _batch_id() -> str:
    return f"olist-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def _load_database_metadata(
    connection: sqlite3.Connection,
    report: ValidationReport,
    config: OlistConfig,
    batch_id: str,
    loaded_at: str,
) -> None:
    connection.execute(
        """
        CREATE TABLE dataset_metadata (
            metadata_key TEXT PRIMARY KEY,
            metadata_value TEXT NOT NULL
        )
        """
    )
    metadata = {
        "data_mode": "olist_real",
        "source_name": "Olist Brazilian E-Commerce Public Dataset",
        "source_dataset": "olistbr/brazilian-ecommerce",
        "currency_code": "BRL",
        "historical_data": "true",
        "ads_available": "false",
        "cost_available": "false",
        "refund_status_available": "false",
        "date_min": report.date_min,
        "date_max": report.date_max,
        "load_batch_id": batch_id,
        "loaded_at": loaded_at,
        "source_file_count": str(len(config.source_specs)),
        "raw_csv_hashes_unchanged": "true",
    }
    connection.executemany(
        "INSERT INTO dataset_metadata(metadata_key, metadata_value) VALUES (?, ?)",
        metadata.items(),
    )


def _load_etl_metadata(
    connection: sqlite3.Connection,
    report: ValidationReport,
    config: OlistConfig,
    batch_id: str,
    started_at: str,
    completed_at: str,
) -> None:
    connection.execute(
        """
        CREATE TABLE etl_load_metadata (
            metadata_id INTEGER PRIMARY KEY AUTOINCREMENT,
            load_batch_id TEXT NOT NULL,
            data_mode TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_dataset TEXT NOT NULL,
            source_file TEXT NOT NULL,
            source_row_count INTEGER NOT NULL,
            loaded_row_count INTEGER NOT NULL,
            file_sha256 TEXT NOT NULL,
            load_started_at TEXT NOT NULL,
            load_completed_at TEXT NOT NULL,
            load_status TEXT NOT NULL,
            currency_code TEXT NOT NULL,
            source_date_min TEXT,
            source_date_max TEXT
        )
        """
    )
    rows = [
        (
            batch_id,
            "olist_real",
            "Olist Brazilian E-Commerce Public Dataset",
            "olistbr/brazilian-ecommerce",
            spec.filename,
            report.row_counts[spec.filename],
            report.row_counts[spec.filename],
            report.hashes[spec.filename],
            started_at,
            completed_at,
            "completed",
            "BRL",
            report.date_min,
            report.date_max,
        )
        for spec in config.source_specs
    ]
    connection.executemany(
        """
        INSERT INTO etl_load_metadata (
            load_batch_id, data_mode, source_name, source_dataset, source_file,
            source_row_count, loaded_row_count, file_sha256, load_started_at,
            load_completed_at, load_status, currency_code, source_date_min,
            source_date_max
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def _add_technical_columns(
    frame: pd.DataFrame,
    spec: SourceSpec,
    batch_id: str,
    loaded_at: str,
) -> pd.DataFrame:
    loaded = frame.copy()
    loaded["_load_batch_id"] = batch_id
    loaded["_source_file"] = spec.filename
    loaded["_source_row_number"] = range(1, len(loaded) + 1)
    loaded["_loaded_at"] = loaded_at
    return loaded


def _create_key_indexes(connection: sqlite3.Connection, spec: SourceSpec) -> None:
    if not spec.unique_key:
        return
    columns = ", ".join(f'"{column}"' for column in spec.unique_key)
    index_name = f"ux_{spec.table_name}_{'_'.join(spec.unique_key)}"
    connection.execute(
        f'CREATE UNIQUE INDEX "{index_name}" ON "{spec.table_name}" ({columns})'
    )


def _write_manifest(
    report: ValidationReport,
    config: OlistConfig,
    batch_id: str,
    generated_at: str,
) -> None:
    payload = {
        "data_mode": "olist_real",
        "source_name": "Olist Brazilian E-Commerce Public Dataset",
        "source_dataset": "olistbr/brazilian-ecommerce",
        "currency_code": "BRL",
        "date_min": report.date_min,
        "date_max": report.date_max,
        "load_batch_id": batch_id,
        "generated_at": generated_at,
        "raw_csv_hashes_unchanged": True,
        "files": [
            {
                "source_file": spec.filename,
                "ods_table": spec.table_name,
                "source_row_count": report.row_counts[spec.filename],
                "file_sha256": report.hashes[spec.filename],
            }
            for spec in config.source_specs
        ],
    }
    config.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    config.manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_failure_record(
    config: OlistConfig,
    batch_id: str,
    started_at: str,
    error: Exception,
) -> None:
    payload = {
        "load_batch_id": batch_id,
        "load_started_at": started_at,
        "load_completed_at": _utc_now(),
        "load_status": "failed",
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    try:
        config.failure_path.parent.mkdir(parents=True, exist_ok=True)
        config.failure_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        LOGGER.exception("[olist][load] unable to write failure metadata")


def _synthetic_database_hash(config: OlistConfig) -> str | None:
    path = config.project_root / SYNTHETIC_DB_NAME
    return sha256_file(path) if path.is_file() else None


def load_ods(
    config: OlistConfig | None = None,
    logger: logging.Logger | None = None,
) -> LoadSummary:
    """Validate and publish a complete ODS snapshot atomically."""

    cfg = config or get_config()
    log = logger or LOGGER
    batch_id = _batch_id()
    started_at = _utc_now()
    synthetic_hash_before = _synthetic_database_hash(cfg)
    temp_path = cfg.ods_db_path.with_name(
        f".{cfg.ods_db_path.name}.{batch_id}.tmp"
    )

    try:
        report = validate_sources(cfg, logger=log)
        cfg.ods_db_path.parent.mkdir(parents=True, exist_ok=True)
        if temp_path.exists():
            temp_path.unlink()

        loaded_at = _utc_now()
        connection = sqlite3.connect(temp_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN")
            for spec in cfg.source_specs:
                frame = _add_technical_columns(
                    report.frames[spec.filename], spec, batch_id, loaded_at
                )
                frame.to_sql(
                    spec.table_name,
                    connection,
                    if_exists="replace",
                    index=False,
                )
                _create_key_indexes(connection, spec)
                log.info(
                    "[olist][load] %s rows=%d",
                    spec.table_name.replace("ods_olist_", ""),
                    len(frame),
                )

            completed_at = _utc_now()
            _load_database_metadata(connection, report, cfg, batch_id, loaded_at)
            _load_etl_metadata(
                connection, report, cfg, batch_id, started_at, completed_at
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        hashes_after = hash_source_files(cfg)
        raw_hashes_unchanged = hashes_after == report.hashes
        if not raw_hashes_unchanged:
            raise OlistValidationError("raw CSV SHA-256 changed during ODS load")

        synthetic_hash_after = _synthetic_database_hash(cfg)
        synthetic_unchanged = synthetic_hash_after == synthetic_hash_before
        if not synthetic_unchanged:
            raise RuntimeError("data/analytics.sqlite changed during ODS load")

        _write_manifest(report, cfg, batch_id, _utc_now())
        os.replace(temp_path, cfg.ods_db_path)
        log.info(
            "[olist][complete] batch_id=%s status=completed db=%s",
            batch_id,
            cfg.ods_db_path,
        )
        return LoadSummary(
            batch_id=batch_id,
            database_path=cfg.ods_db_path,
            manifest_path=cfg.manifest_path,
            row_counts={
                spec.table_name: report.row_counts[spec.filename]
                for spec in cfg.source_specs
            },
            date_min=report.date_min,
            date_max=report.date_max,
            raw_csv_hashes_unchanged=True,
            synthetic_database_unchanged=True,
            load_status="completed",
        )
    except Exception as exc:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                log.exception("[olist][load] unable to remove temporary database")
        _write_failure_record(cfg, batch_id, started_at, exc)
        log.error("[olist][load] load_status=failed error=%s", exc)
        raise


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load Olist CSVs into a read-only ODS snapshot"
    )
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--db-path", type=Path, default=None)
    args = parser.parse_args(argv)
    _configure_logging()
    config = get_config(raw_dir=args.raw_dir, ods_db_path=args.db_path)
    try:
        summary = load_ods(config)
    except (OlistValidationError, OSError, RuntimeError, sqlite3.Error) as exc:
        logging.getLogger(__name__).error(
            "[olist][complete] status=failed error=%s", exc
        )
        return 1
    print(
        json.dumps(
            {
                "database_path": str(summary.database_path),
                "manifest_path": str(summary.manifest_path),
                "batch_id": summary.batch_id,
                "date_min": summary.date_min,
                "date_max": summary.date_max,
                "raw_csv_hashes_unchanged": summary.raw_csv_hashes_unchanged,
                "synthetic_database_unchanged": summary.synthetic_database_unchanged,
                "row_counts": summary.row_counts,
                "load_status": summary.load_status,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
