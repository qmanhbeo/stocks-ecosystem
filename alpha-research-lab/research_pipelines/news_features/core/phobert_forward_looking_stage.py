"""Tagged-only staging for the PhoBERT forward-looking distillation lane."""

from __future__ import annotations

import math
from typing import Optional, Sequence

import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.core.build_phobert_sentiment_features import _prepare_phobert_input_articles_cache
from research_pipelines.news_features.core.phobert_forward_looking_common import (
    FORWARD_LOOKING_STAGE_VERSION,
    empty_stage_dataframe,
    load_json_payload,
    path_signature,
    write_json_atomic,
    write_stage_run_summary,
)
from research_pipelines.news_features.core.phobert_forward_looking_teacher import (
    build_phobert_forward_looking_teacher_labels,
)
from research_pipelines.news_features.io_utils import describe_path, update_manifest, write_parquet_atomic
from research_pipelines.supervised_label.models.baselines import label_distribution


def forward_looking_stage_source_signature(config: NewsFeaturesConfig) -> dict[str, object]:
    return {
        "stage_version": FORWARD_LOOKING_STAGE_VERSION,
        "teacher_labels": path_signature(config.phobert_forward_looking_teacher_labels_path()),
        "tagged_articles": path_signature(config.tagged_path()),
        "phobert_input_articles": path_signature(config.phobert_input_articles_path()),
        "train_fraction": float(config.phobert_forward_looking_train_fraction),
        "val_fraction": float(config.phobert_forward_looking_val_fraction),
    }


def ensure_phobert_input_cache(config: NewsFeaturesConfig) -> None:
    if not config.normalized_path().exists() or not config.tagged_path().exists():
        return
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Building forward-looking stage data requires pyarrow.") from exc
    normalized_file = pq.ParquetFile(config.normalized_path())
    tagged = pd.read_parquet(config.tagged_path())
    tagged["article_id"] = tagged["article_id"].astype(str)
    _prepare_phobert_input_articles_cache(
        config=config,
        normalized_file=normalized_file,
        normalized_rows=int(normalized_file.metadata.num_rows),
        tagged=tagged,
    )


def compose_training_text(row: pd.Series) -> str:
    parts = [
        str(row.get("clean_title", "") or "").strip(),
        str(row.get("clean_summary", "") or "").strip(),
        str(row.get("clean_body_text", "") or "").strip(),
    ]
    return " ".join(part for part in parts if part).strip()


def resolve_forward_looking_splits(
    dates: Sequence[str],
    *,
    train_fraction: float,
    val_fraction: float,
) -> dict[str, object]:
    unique_dates = sorted({str(date) for date in dates if str(date)})
    if not unique_dates:
        return {"split_by_date": {}, "boundaries": {}}
    if len(unique_dates) == 1:
        return {
            "split_by_date": {unique_dates[0]: "train"},
            "boundaries": {
                "train_end_date": unique_dates[0],
                "val_end_date": None,
                "test_start_date": None,
            },
        }
    if len(unique_dates) == 2:
        return {
            "split_by_date": {unique_dates[0]: "train", unique_dates[1]: "test"},
            "boundaries": {
                "train_end_date": unique_dates[0],
                "val_end_date": None,
                "test_start_date": unique_dates[1],
            },
        }

    train_days = max(int(math.floor(len(unique_dates) * float(train_fraction))), 1)
    val_days = max(int(math.floor(len(unique_dates) * float(val_fraction))), 1)
    remaining = len(unique_dates) - train_days - val_days
    if remaining < 1:
        val_days = max(val_days - 1, 1)
        remaining = len(unique_dates) - train_days - val_days
    if remaining < 1:
        train_days = max(train_days - 1, 1)
        remaining = len(unique_dates) - train_days - val_days
    test_days = max(remaining, 1)
    overflow = train_days + val_days + test_days - len(unique_dates)
    if overflow > 0:
        train_days = max(train_days - overflow, 1)
    val_start = train_days
    test_start = train_days + val_days
    split_by_date = {}
    for index, date in enumerate(unique_dates):
        if index < val_start:
            split_by_date[date] = "train"
        elif index < test_start:
            split_by_date[date] = "val"
        else:
            split_by_date[date] = "test"
    return {
        "split_by_date": split_by_date,
        "boundaries": {
            "train_end_date": unique_dates[val_start - 1] if val_start > 0 else None,
            "val_end_date": unique_dates[test_start - 1] if test_start > val_start else None,
            "test_start_date": unique_dates[test_start] if test_start < len(unique_dates) else None,
        },
    }


def load_phobert_input_rows(config: NewsFeaturesConfig, article_ids: set[str]) -> pd.DataFrame:
    if not article_ids or not config.phobert_input_articles_path().exists():
        return pd.DataFrame(columns=["article_id", "published_at", "clean_title", "clean_summary", "clean_body_text"])
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Loading forward-looking stage input rows requires pyarrow.") from exc
    rows: list[pd.DataFrame] = []
    parquet_file = pq.ParquetFile(config.phobert_input_articles_path())
    for batch in parquet_file.iter_batches(
        batch_size=5000,
        columns=["article_id", "published_at", "clean_title", "clean_summary", "clean_body_text"],
    ):
        batch_df = batch.to_pandas()
        batch_df["article_id"] = batch_df["article_id"].astype(str)
        batch_df = batch_df[batch_df["article_id"].isin(article_ids)].copy()
        if not batch_df.empty:
            rows.append(batch_df)
    if not rows:
        return pd.DataFrame(columns=["article_id", "published_at", "clean_title", "clean_summary", "clean_body_text"])
    merged = pd.concat(rows, ignore_index=True)
    return merged.drop_duplicates(subset=["article_id"], keep="first").reset_index(drop=True)


def build_phobert_forward_looking_stage_dataset(
    config: Optional[NewsFeaturesConfig] = None,
    *,
    force_rebuild: bool = False,
) -> pd.DataFrame:
    config = config or get_default_config()
    config.ensure_directories()
    if not config.tagged_path().exists():
        write_parquet_atomic(empty_stage_dataframe(), config.phobert_forward_looking_stage_path(), index=False)
        return empty_stage_dataframe()

    teacher_df = build_phobert_forward_looking_teacher_labels(config=config, force_rebuild=force_rebuild)
    ensure_phobert_input_cache(config)

    stage_path = config.phobert_forward_looking_stage_path()
    manifest_path = config.phobert_forward_looking_stage_manifest_path()
    source_signature = forward_looking_stage_source_signature(config)
    existing_manifest = load_json_payload(manifest_path)
    if (
        not force_rebuild
        and stage_path.exists()
        and existing_manifest.get("status") == "complete"
        and existing_manifest.get("source_signature") == source_signature
    ):
        return pd.read_parquet(stage_path)

    if teacher_df.empty:
        write_parquet_atomic(empty_stage_dataframe(), stage_path, index=False)
        payload = {
            "stage_version": FORWARD_LOOKING_STAGE_VERSION,
            "status": "complete",
            "source_signature": source_signature,
            "stage_rows": 0,
            "updated_at_utc": pd.Timestamp.utcnow().isoformat(),
        }
        write_json_atomic(manifest_path, payload)
        return empty_stage_dataframe()

    teacher_df = teacher_df.copy()
    teacher_df["article_id"] = teacher_df["article_id"].astype(str)
    conflict_counts = teacher_df.groupby("article_id")["phobert_forward_looking_label"].nunique()
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

    teacher_resolved = teacher_resolved[["article_id", "phobert_forward_looking_label", "phobert_forward_looking_label_source"]]
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
    merged["phobert_forward_looking_input_text"] = merged.apply(compose_training_text, axis=1)
    merged["phobert_forward_looking_input_text_length"] = merged["phobert_forward_looking_input_text"].str.len().astype(int)
    merged = merged[merged["phobert_forward_looking_input_text_length"] > 0].copy()

    split_info = resolve_forward_looking_splits(
        merged["date"].astype(str).tolist(),
        train_fraction=config.phobert_forward_looking_train_fraction,
        val_fraction=config.phobert_forward_looking_val_fraction,
    )
    split_by_date = dict(split_info["split_by_date"])
    merged["phobert_forward_looking_split"] = merged["date"].astype(str).map(split_by_date).fillna("train")
    stage_df = (
        merged[
            [
                "article_id",
                "source",
                "url",
                "date",
                "published_at",
                "phobert_forward_looking_input_text",
                "phobert_forward_looking_input_text_length",
                "phobert_forward_looking_label",
                "phobert_forward_looking_label_source",
                "phobert_forward_looking_split",
            ]
        ]
        .sort_values(["date", "article_id"])
        .reset_index(drop=True)
    )
    write_parquet_atomic(stage_df, stage_path, index=False)

    split_counts = stage_df["phobert_forward_looking_split"].value_counts().to_dict()
    payload = {
        "stage_version": FORWARD_LOOKING_STAGE_VERSION,
        "status": "complete",
        "source_signature": source_signature,
        "stage_rows": int(len(stage_df)),
        "teacher_rows": int(len(teacher_df)),
        "teacher_conflict_article_count": int(len(conflicting_ids)),
        "untagged_teacher_article_count": int(len(teacher_ids - tagged_ids)),
        "missing_input_cache_article_count": int(len(tagged_ids - set(input_rows["article_id"].tolist()))),
        "label_distribution": label_distribution(stage_df["phobert_forward_looking_label"].tolist()),
        "split_counts": {key: int(value) for key, value in split_counts.items()},
        "split_boundaries": split_info["boundaries"],
        "updated_at_utc": pd.Timestamp.utcnow().isoformat(),
    }
    write_json_atomic(manifest_path, payload)
    update_manifest(
        config=config,
        phobert_forward_looking_stage_dataset=describe_path(stage_path, config=config),
    )
    write_stage_run_summary(
        mode="news_forward_looking_stage_build",
        name="phobert_forward_looking_stage_build",
        summary={
            "status": "complete",
            "stage_rows": int(len(stage_df)),
            "split_counts": payload["split_counts"],
            "label_distribution": payload["label_distribution"],
            "teacher_conflict_article_count": int(payload["teacher_conflict_article_count"]),
            "untagged_teacher_article_count": int(payload["untagged_teacher_article_count"]),
        },
        artifacts={
            "stage_dataset": stage_path,
            "stage_manifest": manifest_path,
        },
        metadata={"source_signature": source_signature},
    )
    return stage_df
