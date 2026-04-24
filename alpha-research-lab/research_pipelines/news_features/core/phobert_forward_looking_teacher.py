"""Teacher-label reconstruction for the PhoBERT forward-looking distillation lane."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from data_tools import extract_llm_news_features as hosted_llm
from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.core.phobert_forward_looking_common import (
    FORWARD_LOOKING_LABEL_SOURCE,
    FORWARD_LOOKING_TEACHER_VERSION,
    TEACHER_COLUMNS,
    directory_signature,
    empty_teacher_dataframe,
    load_json_payload,
    write_json_atomic,
    write_stage_run_summary,
)
from research_pipelines.news_features.io_utils import canonicalize_url, describe_path, update_manifest, write_parquet_atomic
from research_pipelines.supervised_label.models.baselines import label_distribution


def forward_looking_teacher_source_signature(config: NewsFeaturesConfig) -> dict[str, object]:
    raw_paths = sorted(path for path in config.source_raw_dir(config.default_source).glob("*.jsonl") if path.is_file())
    cache_paths = sorted(path for path in (config.data_root / "llm_cache").glob("*.jsonl") if path.is_file())
    return {
        "teacher_version": FORWARD_LOOKING_TEACHER_VERSION,
        "raw_news": directory_signature(raw_paths, label="raw_news"),
        "llm_cache": directory_signature(cache_paths, label="llm_cache"),
    }


def filtered_raw_articles_with_cache_ids(raw_path: Path) -> dict[str, dict[str, object]]:
    raw_articles = hosted_llm._load_articles(raw_path)
    filtered = [article for article in raw_articles if hosted_llm._is_financial_article(article)]
    lookup: dict[str, dict[str, object]] = {}
    for index, article in enumerate(filtered, start=1):
        lookup[f"{raw_path.stem}_{index:04d}"] = article
    return lookup


def normalize_teacher_record(raw_record: dict[str, object], fallback_id: str) -> dict[str, object]:
    normalized = hosted_llm._normalize_record(raw_record, fallback_id)
    label = normalized.get("is_forward_looking")
    return {
        "llm_cache_id": str(normalized.get("id", fallback_id) or fallback_id),
        "phobert_forward_looking_label": int(bool(label)) if label is not None else None,
    }


def build_phobert_forward_looking_teacher_labels(
    config: Optional[NewsFeaturesConfig] = None,
    *,
    force_rebuild: bool = False,
) -> pd.DataFrame:
    config = config or get_default_config()
    config.ensure_directories()
    teacher_path = config.phobert_forward_looking_teacher_labels_path()
    manifest_path = config.phobert_forward_looking_teacher_manifest_path()
    source_signature = forward_looking_teacher_source_signature(config)
    existing_manifest = load_json_payload(manifest_path)
    if (
        not force_rebuild
        and teacher_path.exists()
        and existing_manifest.get("status") == "complete"
        and existing_manifest.get("source_signature") == source_signature
    ):
        return pd.read_parquet(teacher_path)

    cache_paths = sorted(path for path in (config.data_root / "llm_cache").glob("*.jsonl") if path.is_file())
    rows: list[dict[str, object]] = []
    stats = {
        "cache_days_seen": 0,
        "cache_rows_seen": 0,
        "labeled_rows_kept": 0,
        "skipped_null_label_rows": 0,
        "missing_raw_day_count": 0,
        "missing_raw_article_count": 0,
    }
    for cache_path in cache_paths:
        raw_path = config.source_raw_dir(config.default_source) / cache_path.name
        stats["cache_days_seen"] += 1
        if not raw_path.exists():
            stats["missing_raw_day_count"] += 1
            continue
        raw_lookup = filtered_raw_articles_with_cache_ids(raw_path)
        with cache_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw_record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                stats["cache_rows_seen"] += 1
                normalized = normalize_teacher_record(raw_record, fallback_id="")
                label = normalized["phobert_forward_looking_label"]
                if label is None:
                    stats["skipped_null_label_rows"] += 1
                    continue
                article = raw_lookup.get(normalized["llm_cache_id"])
                if article is None:
                    stats["missing_raw_article_count"] += 1
                    continue
                rows.append(
                    {
                        "article_id": str(article.get("article_id", "") or "").strip(),
                        "source": str(article.get("source", "") or config.default_source),
                        "url": canonicalize_url(article.get("url", "")),
                        "published_at": article.get("published_at"),
                        "llm_cache_id": normalized["llm_cache_id"],
                        "phobert_forward_looking_label": int(label),
                        "phobert_forward_looking_label_source": FORWARD_LOOKING_LABEL_SOURCE,
                    }
                )
                stats["labeled_rows_kept"] += 1

    teacher_df = pd.DataFrame(rows, columns=TEACHER_COLUMNS)
    teacher_df = teacher_df[(teacher_df["article_id"] != "") & (teacher_df["url"] != "")].copy()
    teacher_df = teacher_df.sort_values(["published_at", "article_id", "llm_cache_id"]).reset_index(drop=True)
    write_parquet_atomic(teacher_df, teacher_path, index=False)
    payload = {
        "teacher_version": FORWARD_LOOKING_TEACHER_VERSION,
        "status": "complete",
        "source_signature": source_signature,
        "teacher_rows": int(len(teacher_df)),
        "label_distribution": label_distribution(teacher_df["phobert_forward_looking_label"].tolist()),
        "updated_at_utc": pd.Timestamp.utcnow().isoformat(),
        **stats,
    }
    write_json_atomic(manifest_path, payload)
    update_manifest(
        config=config,
        phobert_forward_looking_teacher_labels_dataset=describe_path(teacher_path, config=config),
    )
    write_stage_run_summary(
        mode="news_forward_looking_teacher_labels",
        name="phobert_forward_looking_teacher_labels",
        summary={
            "status": "complete",
            "teacher_rows": int(len(teacher_df)),
            "label_distribution": payload["label_distribution"],
            "cache_days_seen": int(stats["cache_days_seen"]),
            "cache_rows_seen": int(stats["cache_rows_seen"]),
            "missing_raw_day_count": int(stats["missing_raw_day_count"]),
            "missing_raw_article_count": int(stats["missing_raw_article_count"]),
        },
        artifacts={
            "teacher_labels": teacher_path,
            "teacher_manifest": manifest_path,
        },
        metadata={"source_signature": source_signature},
    )
    return teacher_df
