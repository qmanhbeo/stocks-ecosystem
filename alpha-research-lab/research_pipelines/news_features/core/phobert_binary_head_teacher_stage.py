"""Teacher reconstruction and tagged-only stage building for PhoBERT binary heads."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from data_tools import extract_llm_news_features as hosted_llm
from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.core.build_phobert_sentiment_features import _prepare_phobert_input_articles_cache
from research_pipelines.news_features.core.phobert_binary_head_common import (
    BinaryHeadSpec,
    current_utc_timestamp,
    directory_signature,
    empty_stage_dataframe,
    empty_teacher_dataframe,
    head_stage_manifest_path,
    head_stage_path,
    head_teacher_labels_path,
    head_teacher_manifest_path,
    load_json_payload,
    path_signature,
    stage_columns,
    teacher_columns,
    write_json_atomic,
    write_stage_run_summary,
)
from research_pipelines.news_features.core.phobert_forward_looking_stage import (
    compose_training_text,
    load_phobert_input_rows,
    resolve_forward_looking_splits,
)
from research_pipelines.news_features.io_utils import canonicalize_url, describe_path, update_manifest, write_parquet_atomic
from research_pipelines.supervised_label.models.baselines import label_distribution


BINARY_HEAD_TEACHER_VERSION = 1
BINARY_HEAD_STAGE_VERSION = 2


def binary_head_teacher_source_signature(config: NewsFeaturesConfig) -> dict[str, object]:
    raw_paths = sorted(path for path in config.source_raw_dir(config.default_source).glob("*.jsonl") if path.is_file())
    cache_paths = sorted(path for path in (config.data_root / "llm_cache").glob("*.jsonl") if path.is_file())
    return {
        "teacher_version": BINARY_HEAD_TEACHER_VERSION,
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


def normalize_teacher_record(spec: BinaryHeadSpec, raw_record: dict[str, object], fallback_id: str) -> dict[str, object]:
    normalized = hosted_llm._normalize_record(raw_record, fallback_id)
    label = spec.teacher_label_fn(raw_record)
    return {
        "llm_cache_id": str(normalized.get("id", fallback_id) or fallback_id),
        f"{spec.dataset_prefix}_label": int(label) if label is not None else None,
    }


def build_binary_head_teacher_labels(
    spec: BinaryHeadSpec,
    config: Optional[NewsFeaturesConfig] = None,
    *,
    force_rebuild: bool = False,
) -> pd.DataFrame:
    config = config or get_default_config()
    config.ensure_directories()
    teacher_path = head_teacher_labels_path(config, spec)
    manifest_path = head_teacher_manifest_path(config, spec)
    source_signature = binary_head_teacher_source_signature(config)
    existing_manifest = load_json_payload(manifest_path)
    if (
        not force_rebuild
        and teacher_path.exists()
        and existing_manifest.get("status") == "complete"
        and existing_manifest.get("source_signature") == source_signature
    ):
        return pd.read_parquet(teacher_path)

    cache_paths = sorted(path for path in (config.data_root / "llm_cache").glob("*.jsonl") if path.is_file())
    label_column = f"{spec.dataset_prefix}_label"
    label_source_column = f"{spec.dataset_prefix}_label_source"
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
                normalized = normalize_teacher_record(spec, raw_record, fallback_id="")
                label = normalized[label_column]
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
                        label_column: int(label),
                        label_source_column: spec.label_source_name,
                    }
                )
                stats["labeled_rows_kept"] += 1

    teacher_df = pd.DataFrame(rows, columns=teacher_columns(spec))
    teacher_df = teacher_df[(teacher_df["article_id"] != "") & (teacher_df["url"] != "")].copy()
    teacher_df = teacher_df.sort_values(["published_at", "article_id", "llm_cache_id"]).reset_index(drop=True)
    write_parquet_atomic(teacher_df, teacher_path, index=False)
    payload = {
        "teacher_version": BINARY_HEAD_TEACHER_VERSION,
        "status": "complete",
        "source_signature": source_signature,
        "teacher_rows": int(len(teacher_df)),
        "label_distribution": label_distribution(teacher_df[label_column].tolist()),
        "updated_at_utc": current_utc_timestamp(),
        **stats,
    }
    write_json_atomic(manifest_path, payload)
    update_manifest(config=config, **{f"{spec.dataset_prefix}_teacher_labels_dataset": describe_path(teacher_path, config=config)})
    write_stage_run_summary(
        mode=f"{spec.summary_prefix}_teacher_labels",
        name=f"{spec.dataset_prefix}_teacher_labels",
        summary={
            "status": "complete",
            "teacher_rows": int(len(teacher_df)),
            "label_distribution": payload["label_distribution"],
            "cache_days_seen": int(stats["cache_days_seen"]),
            "cache_rows_seen": int(stats["cache_rows_seen"]),
        },
        artifacts={"teacher_labels": teacher_path, "teacher_manifest": manifest_path},
        metadata={"source_signature": source_signature},
    )
    return teacher_df


def binary_head_stage_source_signature(config: NewsFeaturesConfig, spec: BinaryHeadSpec) -> dict[str, object]:
    return {
        "stage_version": BINARY_HEAD_STAGE_VERSION,
        "teacher_labels": path_signature(head_teacher_labels_path(config, spec)),
        "tagged_articles": path_signature(config.tagged_path()),
        "phobert_input_articles": path_signature(config.phobert_input_articles_path()),
        "train_fraction": float(config.phobert_forward_looking_train_fraction),
        "val_fraction": float(config.phobert_forward_looking_val_fraction),
        "split_strategy": config.phobert_binary_head_split_strategy(spec.name),
        "split_seed": int(config.phobert_forward_looking_random_seed),
    }


def ensure_phobert_input_cache(config: NewsFeaturesConfig) -> None:
    if not config.normalized_path().exists() or not config.tagged_path().exists():
        return
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Building PhoBERT binary-head stage data requires pyarrow.") from exc
    normalized_file = pq.ParquetFile(config.normalized_path())
    tagged = pd.read_parquet(config.tagged_path())
    tagged["article_id"] = tagged["article_id"].astype(str)
    _prepare_phobert_input_articles_cache(
        config=config,
        normalized_file=normalized_file,
        normalized_rows=int(normalized_file.metadata.num_rows),
        tagged=tagged,
    )


def _resolve_split_sizes(total_items: int, *, train_fraction: float, val_fraction: float) -> dict[str, int]:
    total_items = int(total_items)
    if total_items <= 0:
        return {"train": 0, "val": 0, "test": 0}
    if total_items == 1:
        return {"train": 1, "val": 0, "test": 0}
    if total_items == 2:
        return {"train": 1, "val": 0, "test": 1}
    if total_items == 3:
        return {"train": 1, "val": 1, "test": 1}

    train_rows = max(int(math.floor(total_items * float(train_fraction))), 1)
    val_rows = max(int(math.floor(total_items * float(val_fraction))), 1)
    remaining = total_items - train_rows - val_rows
    if remaining < 1:
        val_rows = max(val_rows - 1, 1)
        remaining = total_items - train_rows - val_rows
    if remaining < 1:
        train_rows = max(train_rows - 1, 1)
        remaining = total_items - train_rows - val_rows
    test_rows = max(remaining, 1)
    overflow = train_rows + val_rows + test_rows - total_items
    if overflow > 0:
        train_rows = max(train_rows - overflow, 1)
    return {
        "train": int(train_rows),
        "val": int(val_rows),
        "test": int(max(total_items - train_rows - val_rows, 0)),
    }


def _stratify_labels_or_none(labels: np.ndarray) -> Optional[np.ndarray]:
    if labels.size <= 0:
        return None
    unique, counts = np.unique(labels, return_counts=True)
    if unique.size < 2:
        return None
    if int(counts.min()) < 2:
        return None
    return labels


def resolve_binary_head_splits(
    spec: BinaryHeadSpec,
    article_frame: pd.DataFrame,
    *,
    config: NewsFeaturesConfig,
    label_column: str,
) -> dict[str, object]:
    strategy = config.phobert_binary_head_split_strategy(spec.name)
    seed = int(config.phobert_forward_looking_random_seed)
    article_ids = article_frame["article_id"].astype(str).tolist()
    dates = article_frame["date"].astype(str).tolist()

    if strategy == "time":
        split_info = resolve_forward_looking_splits(
            dates,
            train_fraction=config.phobert_forward_looking_train_fraction,
            val_fraction=config.phobert_forward_looking_val_fraction,
        )
        split_by_date = dict(split_info["split_by_date"])
        return {
            "strategy": "time",
            "seed": None,
            "boundaries": dict(split_info["boundaries"]),
            "split_by_article_id": {
                article_id: str(split_by_date.get(date, "train"))
                for article_id, date in zip(article_ids, dates)
            },
        }

    if strategy != "stratified_random":
        raise ValueError(f"Unsupported binary-head split strategy for {spec.name}: {strategy}")

    total_items = int(len(article_frame))
    split_sizes = _resolve_split_sizes(
        total_items,
        train_fraction=config.phobert_forward_looking_train_fraction,
        val_fraction=config.phobert_forward_looking_val_fraction,
    )
    indices = np.arange(total_items)
    labels = article_frame[label_column].astype(int).to_numpy()
    train_size = int(split_sizes["train"])
    val_size = int(split_sizes["val"])
    test_size = int(split_sizes["test"])

    if train_size >= total_items:
        train_idx = indices
        temp_idx = np.asarray([], dtype=int)
    else:
        train_idx, temp_idx = train_test_split(
            indices,
            train_size=train_size,
            test_size=max(total_items - train_size, 0),
            random_state=seed,
            stratify=_stratify_labels_or_none(labels),
        )
    if val_size <= 0:
        val_idx = np.asarray([], dtype=int)
        test_idx = np.asarray(temp_idx, dtype=int)
    elif test_size <= 0:
        val_idx = np.asarray(temp_idx, dtype=int)
        test_idx = np.asarray([], dtype=int)
    else:
        temp_idx = np.asarray(temp_idx, dtype=int)
        temp_labels = labels[temp_idx]
        val_idx, test_idx = train_test_split(
            temp_idx,
            train_size=val_size,
            test_size=test_size,
            random_state=seed + 1,
            stratify=_stratify_labels_or_none(temp_labels),
        )

    split_by_index = {int(index): "train" for index in np.asarray(train_idx, dtype=int).tolist()}
    split_by_index.update({int(index): "val" for index in np.asarray(val_idx, dtype=int).tolist()})
    split_by_index.update({int(index): "test" for index in np.asarray(test_idx, dtype=int).tolist()})
    split_by_article_id = {
        str(article_id): str(split_by_index.get(int(index), "train"))
        for index, article_id in enumerate(article_ids)
    }
    return {
        "strategy": "stratified_random",
        "seed": int(seed),
        "boundaries": {},
        "split_by_article_id": split_by_article_id,
    }


def split_label_distribution_by_split(stage_df: pd.DataFrame, *, split_column: str, label_column: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for split_name, group in stage_df.groupby(split_column):
        distribution = label_distribution(group[label_column].astype(int).tolist())
        out[str(split_name)] = {key: int(value) for key, value in distribution.items()}
    return out


def build_binary_head_stage_dataset(
    spec: BinaryHeadSpec,
    config: Optional[NewsFeaturesConfig] = None,
    *,
    force_rebuild: bool = False,
) -> pd.DataFrame:
    config = config or get_default_config()
    config.ensure_directories()
    if not config.tagged_path().exists():
        stage_path = head_stage_path(config, spec)
        write_parquet_atomic(empty_stage_dataframe(spec), stage_path, index=False)
        return empty_stage_dataframe(spec)

    teacher_df = build_binary_head_teacher_labels(spec, config=config, force_rebuild=force_rebuild)
    ensure_phobert_input_cache(config)

    stage_path = head_stage_path(config, spec)
    manifest_path = head_stage_manifest_path(config, spec)
    source_signature = binary_head_stage_source_signature(config, spec)
    existing_manifest = load_json_payload(manifest_path)
    if (
        not force_rebuild
        and stage_path.exists()
        and existing_manifest.get("status") == "complete"
        and existing_manifest.get("source_signature") == source_signature
    ):
        return pd.read_parquet(stage_path)

    label_column = f"{spec.dataset_prefix}_label"
    label_source_column = f"{spec.dataset_prefix}_label_source"
    input_text_column = f"{spec.dataset_prefix}_input_text"
    input_length_column = f"{spec.dataset_prefix}_input_text_length"
    split_column = f"{spec.dataset_prefix}_split"

    if teacher_df.empty:
        write_parquet_atomic(empty_stage_dataframe(spec), stage_path, index=False)
        write_json_atomic(
            manifest_path,
            {
                "stage_version": BINARY_HEAD_STAGE_VERSION,
                "status": "complete",
                "source_signature": source_signature,
                "stage_rows": 0,
                "split_strategy": config.phobert_binary_head_split_strategy(spec.name),
                "split_label_distribution": {},
                "updated_at_utc": current_utc_timestamp(),
            },
        )
        return empty_stage_dataframe(spec)

    teacher_df = teacher_df.copy()
    teacher_df["article_id"] = teacher_df["article_id"].astype(str)
    conflict_counts = teacher_df.groupby("article_id")[label_column].nunique()
    conflicting_ids = set(conflict_counts[conflict_counts > 1].index.tolist())
    teacher_resolved = teacher_df[~teacher_df["article_id"].isin(conflicting_ids)].copy()
    teacher_resolved = (
        teacher_resolved.sort_values(["published_at", "article_id", "llm_cache_id"])
        .drop_duplicates(subset=["article_id"], keep="last")
        .reset_index(drop=True)
    )
    teacher_ids = set(teacher_resolved["article_id"].tolist())

    tagged = pd.read_parquet(config.tagged_path(), columns=["article_id", "date", "url", "source"])
    tagged["article_id"] = tagged["article_id"].astype(str)
    tagged_unique = tagged[tagged["article_id"].isin(teacher_ids)].drop_duplicates(subset=["article_id"], keep="first")
    tagged_ids = set(tagged_unique["article_id"].tolist())

    input_rows = load_phobert_input_rows(config, tagged_ids)
    input_rows["article_id"] = input_rows["article_id"].astype(str)
    teacher_resolved = teacher_resolved[["article_id", label_column, label_source_column]]
    merged = teacher_resolved.merge(
        tagged_unique[["article_id", "date", "url", "source"]],
        on="article_id",
        how="inner",
        validate="one_to_one",
    ).merge(
        input_rows[["article_id", "published_at", "clean_title", "clean_summary", "clean_body_text"]],
        on="article_id",
        how="inner",
        validate="one_to_one",
    )
    merged[input_text_column] = merged.apply(compose_training_text, axis=1)
    merged[input_length_column] = merged[input_text_column].str.len().astype(int)
    merged = merged[merged[input_length_column] > 0].copy()

    split_info = resolve_binary_head_splits(
        spec,
        merged[["article_id", "date", label_column]].copy(),
        config=config,
        label_column=label_column,
    )
    split_by_article_id = dict(split_info["split_by_article_id"])
    merged[split_column] = merged["article_id"].astype(str).map(split_by_article_id).fillna("train")
    stage_df = (
        merged[
            [
                "article_id",
                "source",
                "url",
                "date",
                "published_at",
                input_text_column,
                input_length_column,
                label_column,
                label_source_column,
                split_column,
            ]
        ]
        .sort_values(["date", "article_id"])
        .reset_index(drop=True)
    )
    write_parquet_atomic(stage_df, stage_path, index=False)
    split_counts = stage_df[split_column].value_counts().to_dict()
    split_label_distribution = split_label_distribution_by_split(
        stage_df,
        split_column=split_column,
        label_column=label_column,
    )
    payload = {
        "stage_version": BINARY_HEAD_STAGE_VERSION,
        "status": "complete",
        "source_signature": source_signature,
        "stage_rows": int(len(stage_df)),
        "teacher_rows": int(len(teacher_df)),
        "teacher_conflict_article_count": int(len(conflicting_ids)),
        "untagged_teacher_article_count": int(len(teacher_ids - tagged_ids)),
        "missing_input_cache_article_count": int(len(tagged_ids - set(input_rows["article_id"].tolist()))),
        "label_distribution": label_distribution(stage_df[label_column].tolist()),
        "split_counts": {key: int(value) for key, value in split_counts.items()},
        "split_strategy": str(split_info["strategy"]),
        "split_seed": split_info["seed"],
        "split_boundaries": dict(split_info["boundaries"]),
        "split_label_distribution": split_label_distribution,
        "updated_at_utc": current_utc_timestamp(),
    }
    write_json_atomic(manifest_path, payload)
    update_manifest(config=config, **{f"{spec.dataset_prefix}_stage_dataset": describe_path(stage_path, config=config)})
    write_stage_run_summary(
        mode=f"{spec.summary_prefix}_stage_build",
        name=f"{spec.dataset_prefix}_stage_build",
        summary={
            "status": "complete",
            "stage_rows": int(len(stage_df)),
            "split_counts": payload["split_counts"],
            "label_distribution": payload["label_distribution"],
            "split_strategy": payload["split_strategy"],
            "teacher_conflict_article_count": int(payload["teacher_conflict_article_count"]),
            "untagged_teacher_article_count": int(payload["untagged_teacher_article_count"]),
        },
        artifacts={"stage_dataset": stage_path, "stage_manifest": manifest_path},
        metadata={"source_signature": source_signature},
    )
    return stage_df
