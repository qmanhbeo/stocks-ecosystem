"""Repair raw Cafef JSONL buckets using timestamps encoded in article URLs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import shutil
from pathlib import Path
from typing import Optional

import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.io_utils import read_jsonl, update_source_manifest, write_jsonl_records
from vn_stock_rl.data_tools.fetch_news import infer_cafef_url_timestamp


def _repair_record_timestamp(record: dict[str, object]) -> tuple[dict[str, object], str]:
    payload = dict(record)
    url = str(payload.get("url", "")).strip()
    inferred = infer_cafef_url_timestamp(url)
    if inferred is None:
        existing = pd.to_datetime(payload.get("published_at"), utc=True, errors="coerce")
        if pd.isna(existing):
            payload["published_at"] = None
            payload["published_at_source"] = "unparsable"
            return payload, "unparsable"
        inferred = pd.Timestamp(existing)
        payload.setdefault("published_at_source", "html")
    else:
        payload["published_at_source"] = "url"
    payload["published_at"] = inferred.strftime("%Y-%m-%dT%H:%M:%SZ")
    return payload, inferred.strftime("%Y-%m-%d")


def repair_raw_news_dates(
    source: str = "cafef",
    config: Optional[NewsFeaturesConfig] = None,
) -> dict[str, object]:
    config = config or get_default_config()
    raw_dir = config.source_raw_dir(source)
    raw_files = sorted(raw_dir.glob("*.jsonl"))
    if not raw_files:
        raise FileNotFoundError(f"No raw JSONL files found under {raw_dir}")

    backup_dir = config.source_dir(source) / f"raw_backup_rebucket_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    for path in raw_files:
        shutil.move(str(path), str(backup_dir / path.name))

    grouped_rows: dict[str, list[dict[str, object]]] = {}
    total_rows = 0
    corrected_rows = 0

    for backup_file in sorted(backup_dir.glob("*.jsonl")):
        original_bucket = backup_file.stem
        for row in read_jsonl(backup_file):
            total_rows += 1
            repaired_row, repaired_bucket = _repair_record_timestamp(row)
            if repaired_bucket != original_bucket or repaired_row.get("published_at") != row.get("published_at"):
                corrected_rows += 1
            grouped_rows.setdefault(repaired_bucket, []).append(repaired_row)

    for bucket, rows in grouped_rows.items():
        target_path = raw_dir / f"{bucket}.jsonl"
        rows_sorted = sorted(rows, key=lambda item: (str(item.get("published_at", "")), str(item.get("article_id", ""))))
        write_jsonl_records(target_path, rows_sorted, append=False)

    summary = {
        "source": source,
        "backup_dir": str(backup_dir),
        "raw_file_count": len(grouped_rows),
        "article_count": total_rows,
        "corrected_rows": corrected_rows,
        "last_rebucket_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    update_source_manifest(source=source, payload=summary, config=config)
    print(
        f"Rebucketed {total_rows} raw articles across {len(grouped_rows)} daily files. Backup stored at {backup_dir}",
        flush=True,
    )
    print(f"Corrected rows: {corrected_rows}", flush=True)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repair raw Cafef JSONL buckets using URL-encoded timestamps.")
    parser.add_argument("--source", default="cafef", help="News source to repair (default: cafef)")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    repair_raw_news_dates(source=args.source)


if __name__ == "__main__":
    main()
