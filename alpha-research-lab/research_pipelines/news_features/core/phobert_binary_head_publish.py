"""Publish additive PhoBERT binary-head datasets from trained local winners."""

from __future__ import annotations

import importlib.metadata
from itertools import islice
import json
from pathlib import Path
import tempfile
from time import perf_counter
from typing import Callable, Optional

import numpy as np
import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.local_runtime import (
    apply_local_transformers_runtime_defaults,
    ensure_expected_cuda_runtime,
)
from research_pipelines.news_features.core.build_phobert_sentiment_features import (
    PHOBERT_INPUT_COLUMNS,
    _prepare_phobert_input_articles_cache,
)
from research_pipelines.news_features.core.phobert_binary_head_common import (
    BinaryHeadSpec,
    article_feature_columns,
    current_utc_timestamp,
    daily_columns_for_spec,
    head_article_features_path,
    head_latest_winner_path,
    head_metadata_path,
    head_publish_checkpoint_dir,
    head_publish_checkpoint_manifest_path,
    head_publish_checkpoint_shard_path,
    head_publish_job_status_path,
    head_ticker_day_features_path,
    head_training_manifest_path,
    load_json_payload,
    path_signature,
    write_json_atomic,
    write_stage_run_summary,
)
from research_pipelines.news_features.io_utils import describe_path, update_manifest, write_parquet_atomic


BinaryHeadScoreFn = Callable[[list[str]], list[dict[str, object]]]

BINARY_HEAD_PUBLISH_CHECKPOINT_VERSION = 3


def _empty_article_dataframe(spec: BinaryHeadSpec) -> pd.DataFrame:
    return pd.DataFrame(columns=article_feature_columns(spec))


def _empty_daily_dataframe(spec: BinaryHeadSpec, config: NewsFeaturesConfig) -> pd.DataFrame:
    return pd.DataFrame(columns=["ticker", "date", *daily_columns_for_spec(config, spec)])


def _batched(values: list[str], batch_size: int):
    iterator = iter(values)
    while True:
        batch = list(islice(iterator, max(int(batch_size), 1)))
        if not batch:
            break
        yield batch


def _load_latest_winner(spec: BinaryHeadSpec, config: NewsFeaturesConfig) -> dict[str, object]:
    winner_payload = load_json_payload(head_latest_winner_path(config, spec))
    if not winner_payload:
        raise RuntimeError(f"{spec.name} publish requires a completed latest_winner.json first.")
    model_dir = Path(str(winner_payload.get("model_dir") or "")).expanduser()
    if not model_dir.exists():
        raise RuntimeError(f"Winner model directory is missing: {model_dir}")
    training_manifest = load_json_payload(head_training_manifest_path(config, spec))
    run_id = str(training_manifest.get("run_id") or model_dir.parent.parent.name or "unknown")
    candidate_name = str(winner_payload.get("candidate_name") or model_dir.parent.name or "unknown")
    decision_threshold = winner_payload.get("decision_threshold")
    if decision_threshold is None:
        decision_threshold = (training_manifest.get("winner") or {}).get("decision_threshold")
    winner_payload["run_id"] = run_id
    winner_payload["candidate_name"] = candidate_name
    winner_payload["model_dir"] = str(model_dir)
    winner_payload["resolved_model_id"] = f"{spec.dataset_prefix}::{run_id}::{candidate_name}"
    winner_payload["decision_threshold"] = float(
        decision_threshold
        if decision_threshold is not None
        else config.phobert_binary_head_default_positive_threshold(spec.name)
    )
    return winner_payload


def _load_binary_head_scorer(
    spec: BinaryHeadSpec,
    config: NewsFeaturesConfig,
    winner: dict[str, object],
    *,
    log_progress: bool = False,
) -> tuple[BinaryHeadScoreFn, dict[str, object]]:
    apply_local_transformers_runtime_defaults(config)
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise ImportError("PhoBERT binary-head publish requires torch and transformers.") from exc
    ensure_expected_cuda_runtime(torch, context=f"PhoBERT {spec.name} publish")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    precision = str(config.phobert_forward_looking_precision)
    if precision == "fp16":
        dtype = torch.float16
    elif precision == "fp32":
        dtype = torch.float32
    else:
        dtype = torch.float16 if device == "cuda" else torch.float32

    model_dir = Path(str(winner["model_dir"]))
    if log_progress:
        print(
            f"{spec.name} PhoBERT model load: model_dir={model_dir}, device={device}, "
            f"dtype={str(dtype).replace('torch.', '')}",
            flush=True,
        )
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, use_fast=False)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir, local_files_only=True, dtype=dtype)
    model.to(device)
    model.eval()
    positive_label = spec.positive_label_name.upper()
    decision_threshold = float(
        winner.get("decision_threshold", config.phobert_binary_head_default_positive_threshold(spec.name))
    )
    if log_progress:
        print(f"{spec.name} PhoBERT model load complete", flush=True)

    def _score(texts: list[str]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        total_texts = len(texts)
        batch_size = max(int(config.phobert_forward_looking_inference_batch_size), 1)
        total_batches = max((total_texts + batch_size - 1) // batch_size, 1)
        progress_interval = 1 if total_batches <= 10 else 25 if total_batches <= 100 else 100
        processed_texts = 0
        for batch_index, batch in enumerate(_batched(texts, batch_size), start=1):
            encoded = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=config.phobert_forward_looking_max_length,
                return_tensors="pt",
            )
            token_counts = encoded["attention_mask"].sum(dim=1).tolist()
            encoded = {key: value.to(device) for key, value in encoded.items()}
            with torch.inference_mode():
                logits = model(**encoded).logits
                probabilities = torch.softmax(logits.float(), dim=-1).cpu().tolist()
            for raw_text, token_count, vector in zip(batch, token_counts, probabilities):
                prob_negative = float(vector[0])
                prob_positive = float(vector[1])
                is_positive = bool(prob_positive >= decision_threshold)
                predicted_label = positive_label if is_positive else spec.negative_label_name.upper()
                rows.append(
                    {
                        f"{spec.dataset_prefix}_input_text_length": int(len(raw_text)),
                        f"{spec.dataset_prefix}_token_count": int(token_count),
                        f"{spec.dataset_prefix}_predicted_label": predicted_label,
                        f"{spec.dataset_prefix}_is_positive": is_positive,
                        f"{spec.dataset_prefix}_confidence": float(max(prob_negative, prob_positive)),
                        f"{spec.dataset_prefix}_prob_negative": prob_negative,
                        f"{spec.dataset_prefix}_prob_positive": prob_positive,
                    }
                )
            processed_texts += len(batch)
            if total_texts <= int(config.phobert_forward_looking_publish_checkpoint_rows):
                should_log_progress = batch_index == total_batches
            else:
                should_log_progress = (
                    batch_index == 1 or batch_index % progress_interval == 0 or batch_index == total_batches
                )
            if log_progress and should_log_progress:
                print(
                    f"{spec.name} PhoBERT scoring batch {batch_index}/{total_batches}; "
                    f"processed_texts={processed_texts}/{total_texts}",
                    flush=True,
                )
        return rows

    metadata = {
        f"{spec.dataset_prefix}_model_id": str(winner["resolved_model_id"]),
        f"{spec.dataset_prefix}_candidate_name": str(winner["candidate_name"]),
        f"{spec.dataset_prefix}_model_name": str(winner.get("model_name") or model_dir.name),
        f"{spec.dataset_prefix}_run_id": str(winner["run_id"]),
        f"{spec.dataset_prefix}_decision_threshold": float(decision_threshold),
        f"{spec.dataset_prefix}_device": device,
        f"{spec.dataset_prefix}_dtype": str(dtype).replace("torch.", ""),
        "torch_version": importlib.metadata.version("torch"),
        "transformers_version": importlib.metadata.version("transformers"),
    }
    return _score, metadata


def _apply_decision_threshold_to_score_frame(
    spec: BinaryHeadSpec,
    score_frame: pd.DataFrame,
    *,
    positive_threshold: float,
) -> pd.DataFrame:
    adjusted = score_frame.copy()
    positive_prob_column = f"{spec.dataset_prefix}_prob_positive"
    predicted_label_column = f"{spec.dataset_prefix}_predicted_label"
    is_positive_column = f"{spec.dataset_prefix}_is_positive"
    adjusted[positive_prob_column] = pd.to_numeric(adjusted[positive_prob_column], errors="coerce").fillna(0.0)
    adjusted[is_positive_column] = adjusted[positive_prob_column].ge(float(positive_threshold))
    adjusted[predicted_label_column] = np.where(
        adjusted[is_positive_column],
        spec.positive_label_name.upper(),
        spec.negative_label_name.upper(),
    )
    return adjusted


def _clear_publish_checkpoint_state(spec: BinaryHeadSpec, config: NewsFeaturesConfig) -> None:
    checkpoint_dir = head_publish_checkpoint_dir(config, spec)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    for path in checkpoint_dir.iterdir():
        if path.is_file():
            path.unlink(missing_ok=True)


def _load_publish_checkpoint_manifest(spec: BinaryHeadSpec, config: NewsFeaturesConfig) -> dict[str, object]:
    return load_json_payload(head_publish_checkpoint_manifest_path(config, spec))


def _write_publish_checkpoint_manifest(
    spec: BinaryHeadSpec,
    config: NewsFeaturesConfig,
    payload: dict[str, object],
) -> None:
    write_json_atomic(head_publish_checkpoint_manifest_path(config, spec), payload)


def _head_publish_run_signature(
    spec: BinaryHeadSpec,
    config: NewsFeaturesConfig,
    *,
    winner: dict[str, object],
    input_rows: int,
    input_source_signature: dict[str, object],
) -> dict[str, object]:
    model_dir_value = str(winner.get("model_dir") or "").strip()
    return {
        "checkpoint_version": BINARY_HEAD_PUBLISH_CHECKPOINT_VERSION,
        f"{spec.dataset_prefix}_model_id": str(winner["resolved_model_id"]),
        "latest_winner": path_signature(head_latest_winner_path(config, spec)),
        "winner_model_dir": path_signature(Path(model_dir_value)) if model_dir_value else {"path": "", "exists": False},
        "training_manifest": path_signature(head_training_manifest_path(config, spec)),
        "max_length": int(config.phobert_forward_looking_max_length),
        "precision": str(config.phobert_forward_looking_precision),
        "inference_batch_size": int(config.phobert_forward_looking_inference_batch_size),
        "decision_threshold": float(winner.get("decision_threshold", config.phobert_binary_head_default_positive_threshold(spec.name))),
        "publish_checkpoint_rows": int(config.phobert_forward_looking_publish_checkpoint_rows),
        "phobert_input_rows": int(input_rows),
        "phobert_input": path_signature(config.phobert_input_articles_path()),
        "phobert_input_source_signature": input_source_signature,
    }


def _publish_job_artifacts(spec: BinaryHeadSpec, config: NewsFeaturesConfig) -> dict[str, str]:
    artifact_paths = {
        "status_file": head_publish_job_status_path(config, spec),
        "latest_winner": head_latest_winner_path(config, spec),
        "training_manifest": head_training_manifest_path(config, spec),
        "article_dataset": head_article_features_path(config, spec),
        "ticker_day_dataset": head_ticker_day_features_path(config, spec),
        "checkpoint_manifest": head_publish_checkpoint_manifest_path(config, spec),
    }
    return {key: describe_path(path, config=config) for key, path in artifact_paths.items()}


def write_binary_head_publish_progress_line(spec: BinaryHeadSpec, phase: str, message: str) -> None:
    print(f"[{spec.publish_job_name}][{str(phase)}] {message}", flush=True)


def _write_publish_job_status(
    spec: BinaryHeadSpec,
    config: NewsFeaturesConfig,
    *,
    status: str,
    phase: str,
    progress_updates: Optional[dict[str, object]] = None,
    throughput_updates: Optional[dict[str, object]] = None,
    artifact_updates: Optional[dict[str, object]] = None,
    error: Optional[str] = None,
    started_at: Optional[str] = None,
) -> dict[str, object]:
    status_path = head_publish_job_status_path(config, spec)
    existing = load_json_payload(status_path)
    now = current_utc_timestamp()
    progress = dict(existing.get("progress") or {})
    progress.update(progress_updates or {})
    throughput = dict(existing.get("throughput") or {})
    throughput.update(throughput_updates or {})
    artifacts = dict(existing.get("artifacts") or {})
    artifacts.update(_publish_job_artifacts(spec, config))
    for key, value in (artifact_updates or {}).items():
        artifacts[str(key)] = None if value is None else describe_path(Path(str(value)), config=config)
    payload = {
        "job": spec.publish_job_name,
        "status": str(status),
        "started_at": str(started_at or existing.get("started_at") or now),
        "updated_at": now,
        "last_heartbeat": now,
        "phase": str(phase),
        "progress": progress,
        "throughput": throughput,
        "artifacts": artifacts,
    }
    if error is not None:
        payload["error"] = str(error)
    write_json_atomic(status_path, payload)
    return payload


def _raw_daily_dataframe(spec: BinaryHeadSpec, daily_state: dict[tuple[str, str], dict[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": ticker,
                "date": date,
                "article_count": state["article_count"],
                "positive_count": state["positive_count"],
                "share": state["positive_count"] / state["article_count"],
                "positive_prob_mean": state["positive_prob_sum"] / state["article_count"],
                "positive_prob_sum": state["positive_prob_sum"],
                "confidence_mean": state["confidence_sum"] / state["article_count"],
            }
            for (ticker, date), state in daily_state.items()
            if state["article_count"] > 0
        ]
    )


def _rename_daily_columns_for_spec(spec: BinaryHeadSpec, out: pd.DataFrame) -> pd.DataFrame:
    if spec.dataset_prefix == "phobert_article_scope":
        return out.rename(
            columns={
                "article_count": "phobert_article_scope_article_count_1d",
                "positive_count": "phobert_article_scope_stock_news_count_1d",
                "share": "phobert_article_scope_stock_news_share",
                "positive_prob_mean": "phobert_article_scope_stock_news_prob_mean",
                "positive_prob_sum": "phobert_article_scope_stock_news_prob_sum",
                "confidence_mean": "phobert_article_scope_confidence_mean",
                "article_count_5d": "phobert_article_scope_article_count_5d",
                "article_count_30d": "phobert_article_scope_article_count_30d",
                "positive_prob_5d": "phobert_article_scope_stock_news_prob_5d",
                "positive_prob_30d": "phobert_article_scope_stock_news_prob_30d",
            }
        )
    return out.rename(
        columns={
            "article_count": "phobert_source_type_article_count_1d",
            "positive_count": "phobert_source_type_official_or_regulatory_count_1d",
            "share": "phobert_source_type_official_or_regulatory_share",
            "positive_prob_mean": "phobert_source_type_official_or_regulatory_prob_mean",
            "positive_prob_sum": "phobert_source_type_official_or_regulatory_prob_sum",
            "confidence_mean": "phobert_source_type_confidence_mean",
            "article_count_5d": "phobert_source_type_article_count_5d",
            "article_count_30d": "phobert_source_type_article_count_30d",
            "positive_prob_5d": "phobert_source_type_official_or_regulatory_prob_5d",
            "positive_prob_30d": "phobert_source_type_official_or_regulatory_prob_30d",
        }
    )


def _daily_feature_frame_from_state(
    spec: BinaryHeadSpec,
    daily_state: dict[tuple[str, str], dict[str, float]],
    config: NewsFeaturesConfig,
    *,
    log_progress: bool = False,
) -> pd.DataFrame:
    if not daily_state:
        return _empty_daily_dataframe(spec, config)

    daily = _raw_daily_dataframe(spec, daily_state)
    daily["date"] = pd.to_datetime(daily["date"])
    frames: list[pd.DataFrame] = []
    ticker_groups = list(daily.groupby("ticker", sort=True))
    total_tickers = len(ticker_groups)
    progress_interval = 1 if total_tickers <= 10 else 10
    value_columns = [
        "article_count",
        "positive_count",
        "share",
        "positive_prob_mean",
        "positive_prob_sum",
        "confidence_mean",
    ]
    for ticker_index, (ticker, group) in enumerate(ticker_groups, start=1):
        group = group.sort_values("date").reset_index(drop=True)
        date_index = pd.date_range(group["date"].min(), group["date"].max(), freq="D")
        group = group.set_index("date").reindex(date_index)
        group["ticker"] = ticker
        for column in value_columns:
            group[column] = pd.to_numeric(group[column], errors="coerce").fillna(0.0)
        group["article_count_5d"] = group["article_count"].rolling(window=5, min_periods=1).sum()
        group["article_count_30d"] = group["article_count"].rolling(window=30, min_periods=1).sum()
        group["positive_prob_5d"] = group["positive_prob_sum"].rolling(window=5, min_periods=1).sum()
        group["positive_prob_30d"] = group["positive_prob_sum"].rolling(window=30, min_periods=1).sum()
        group = group.reset_index().rename(columns={"index": "date"})
        renamed = _rename_daily_columns_for_spec(spec, group)
        frames.append(renamed[["ticker", "date", *daily_columns_for_spec(config, spec)]])
        if log_progress and (
            ticker_index == 1 or ticker_index % progress_interval == 0 or ticker_index == total_tickers
        ):
            print(
                f"{spec.name} daily aggregation progress: processed {ticker_index}/{total_tickers} tickers",
                flush=True,
            )
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out.sort_values(["ticker", "date"]).reset_index(drop=True)


def _finalize_binary_head_from_checkpoints(
    spec: BinaryHeadSpec,
    *,
    config: NewsFeaturesConfig,
    checkpoint_manifest: dict[str, object],
) -> tuple[pd.DataFrame, dict[str, object]]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Binary-head PhoBERT checkpoint finalization requires pyarrow.") from exc

    article_schema = pa.schema(
        [
            ("article_id", pa.string()),
            ("ticker", pa.string()),
            ("date", pa.string()),
            ("published_at", pa.string()),
            ("url", pa.string()),
            ("source", pa.string()),
            ("match_source", pa.string()),
            ("title_hit", pa.int64()),
            ("body_hit", pa.int64()),
            (f"{spec.dataset_prefix}_model_id", pa.string()),
            (f"{spec.dataset_prefix}_input_text_length", pa.int64()),
            (f"{spec.dataset_prefix}_token_count", pa.int64()),
            (f"{spec.dataset_prefix}_predicted_label", pa.string()),
            (f"{spec.dataset_prefix}_is_positive", pa.bool_()),
            (f"{spec.dataset_prefix}_confidence", pa.float64()),
            (f"{spec.dataset_prefix}_prob_negative", pa.float64()),
            (f"{spec.dataset_prefix}_prob_positive", pa.float64()),
        ]
    )

    completed_batches = checkpoint_manifest.get("completed_batches") or {}
    batch_items = sorted(completed_batches.items(), key=lambda item: int(item[0]))
    total_batches = len(batch_items)
    progress_interval = 1 if total_batches <= 10 else 25
    daily_state: dict[tuple[str, str], dict[str, float]] = {}
    writer = None
    temp_article_path: Optional[Path] = None
    positive_prob_column = f"{spec.dataset_prefix}_prob_positive"
    positive_flag_column = f"{spec.dataset_prefix}_is_positive"
    confidence_column = f"{spec.dataset_prefix}_confidence"
    try:
        with tempfile.NamedTemporaryFile(
            dir=head_article_features_path(config, spec).parent,
            suffix=".parquet",
            delete=False,
        ) as handle:
            temp_article_path = Path(handle.name)

        for batch_index, (_batch_key, batch_meta) in enumerate(batch_items, start=1):
            shard_path_value = batch_meta.get("shard_path")
            if not shard_path_value or int(batch_meta.get("article_rows", 0)) == 0:
                if batch_index == 1 or batch_index % progress_interval == 0 or batch_index == total_batches:
                    print(
                        f"{spec.name} finalize shard {batch_index}/{total_batches}; "
                        f"article_rows={checkpoint_manifest.get('article_score_rows', 0)}",
                        flush=True,
                    )
                continue
            shard_path = Path(str(shard_path_value))
            if not shard_path.exists():
                raise FileNotFoundError(f"Missing {spec.name} checkpoint shard: {shard_path}")
            shard_df = pd.read_parquet(shard_path)
            if not shard_df.empty:
                table = pa.Table.from_pandas(
                    shard_df[article_feature_columns(spec)],
                    preserve_index=False,
                    schema=article_schema,
                )
                if writer is None:
                    writer = pq.ParquetWriter(temp_article_path, schema=article_schema)
                writer.write_table(table)
                grouped = (
                    shard_df.assign(_positive_true=shard_df[positive_flag_column].astype(float))
                    .groupby(["ticker", "date"], as_index=False)
                    .agg(
                        article_count=("article_id", "size"),
                        positive_count=("_positive_true", "sum"),
                        positive_prob_sum=(positive_prob_column, "sum"),
                        confidence_sum=(confidence_column, "sum"),
                    )
                )
                for row in grouped.to_dict(orient="records"):
                    key = (str(row["ticker"]), str(row["date"]))
                    state = daily_state.setdefault(
                        key,
                        {
                            "article_count": 0.0,
                            "positive_count": 0.0,
                            "positive_prob_sum": 0.0,
                            "confidence_sum": 0.0,
                        },
                    )
                    for field in state:
                        state[field] += float(row[field])
            if batch_index == 1 or batch_index % progress_interval == 0 or batch_index == total_batches:
                print(f"{spec.name} finalize shard {batch_index}/{total_batches}", flush=True)

        if writer is not None and temp_article_path is not None:
            writer.close()
            writer = None
            temp_article_path.replace(head_article_features_path(config, spec))
        else:
            write_parquet_atomic(_empty_article_dataframe(spec), head_article_features_path(config, spec), index=False)
    finally:
        if writer is not None:
            writer.close()
        if temp_article_path is not None and temp_article_path.exists():
            temp_article_path.unlink(missing_ok=True)

    daily = _daily_feature_frame_from_state(spec, daily_state, config, log_progress=True)
    write_parquet_atomic(daily, head_ticker_day_features_path(config, spec), index=False)

    checkpoint_manifest["status"] = "complete"
    checkpoint_manifest["daily_feature_rows"] = int(len(daily))
    checkpoint_manifest["completed_at_utc"] = pd.Timestamp.utcnow().isoformat()
    _write_publish_checkpoint_manifest(spec, config, checkpoint_manifest)

    for batch_meta in completed_batches.values():
        shard_path_value = batch_meta.get("shard_path")
        if shard_path_value:
            Path(str(shard_path_value)).unlink(missing_ok=True)

    metadata = {
        f"{spec.dataset_prefix}_model_id": checkpoint_manifest.get(f"{spec.dataset_prefix}_model_id"),
        "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
        "daily_feature_rows": int(len(daily)),
        "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
        "checkpoint_status": str(checkpoint_manifest.get("status", "unknown")),
        "checkpoint_completed_batches": int(checkpoint_manifest.get("completed_batch_count", 0)),
        "checkpoint_total_batches": int(checkpoint_manifest.get("total_batches", 0)),
    }
    return daily, metadata


def build_binary_head_feature_exports(
    spec: BinaryHeadSpec,
    config: Optional[NewsFeaturesConfig] = None,
    *,
    scorer: Optional[BinaryHeadScoreFn] = None,
    scorer_metadata: Optional[dict[str, object]] = None,
    checkpoint_batch_limit: Optional[int] = None,
) -> pd.DataFrame:
    config = config or get_default_config()
    config.ensure_directories()
    overall_start = perf_counter()
    started_at = current_utc_timestamp()
    phobert_input_rows = 0
    daily = _empty_daily_dataframe(spec, config)
    metadata: dict[str, object] = {}
    try:
        if not config.normalized_path().exists() or not config.tagged_path().exists():
            write_binary_head_publish_progress_line(
                spec,
                "preflight",
                "normalized or tagged inputs missing; publishing empty datasets",
            )
            article_rows = _empty_article_dataframe(spec)
            daily = _empty_daily_dataframe(spec, config)
            metadata = {
                f"{spec.dataset_prefix}_model_id": None,
                "phobert_input_rows": 0,
                "article_score_rows": 0,
                "daily_feature_rows": 0,
                "unique_article_count": 0,
                "checkpoint_status": "complete",
                "checkpoint_completed_batches": 0,
                "checkpoint_total_batches": 0,
            }
            write_parquet_atomic(article_rows, head_article_features_path(config, spec), index=False)
            write_parquet_atomic(daily, head_ticker_day_features_path(config, spec), index=False)
            _write_publish_job_status(
                spec,
                config,
                status="complete",
                phase="preflight",
                progress_updates=metadata,
                started_at=started_at,
            )
        else:
            try:
                import pyarrow.parquet as pq
            except ImportError as exc:
                raise ImportError("Binary-head PhoBERT export requires pyarrow.") from exc

            winner: dict[str, object]
            if scorer is None:
                winner = _load_latest_winner(spec, config)
            else:
                try:
                    winner = _load_latest_winner(spec, config)
                except RuntimeError:
                    override_model_id = str(
                        (scorer_metadata or {}).get(f"{spec.dataset_prefix}_model_id") or f"{spec.dataset_prefix}::scorer_override"
                    )
                    winner = {
                        "resolved_model_id": override_model_id,
                        "candidate_name": "scorer_override",
                        "model_name": override_model_id,
                        "model_dir": "",
                        "run_id": "scorer_override",
                        "decision_threshold": config.phobert_binary_head_default_positive_threshold(spec.name),
                    }
            _write_publish_job_status(
                spec,
                config,
                status="running",
                phase="preflight",
                progress_updates={"winner": winner["resolved_model_id"]},
                started_at=started_at,
            )
            normalized_file = pq.ParquetFile(config.normalized_path())
            normalized_rows = int(normalized_file.metadata.num_rows)
            tagged = pd.read_parquet(config.tagged_path())
            tagged["article_id"] = tagged["article_id"].astype(str)
            tagged_rows = int(len(tagged))
            write_binary_head_publish_progress_line(
                spec,
                "preflight",
                f"loaded normalized_rows={normalized_rows} tagged_rows={tagged_rows}",
            )
            input_manifest = _prepare_phobert_input_articles_cache(
                config=config,
                normalized_file=normalized_file,
                normalized_rows=normalized_rows,
                tagged=tagged,
            )
            input_file = pq.ParquetFile(config.phobert_input_articles_path())
            input_rows = int(input_file.metadata.num_rows)
            phobert_input_rows = input_rows
            input_source_signature = dict(input_manifest.get("source_signature") or {})
            write_binary_head_publish_progress_line(
                spec,
                "preflight",
                f"scoring universe input_rows={input_rows} from {config.phobert_input_articles_path()}",
            )
            if input_rows == 0:
                _clear_publish_checkpoint_state(spec, config)
                daily = _empty_daily_dataframe(spec, config)
                metadata = {
                    f"{spec.dataset_prefix}_model_id": winner["resolved_model_id"],
                    "phobert_input_rows": 0,
                    "article_score_rows": 0,
                    "daily_feature_rows": 0,
                    "unique_article_count": 0,
                    "checkpoint_status": "complete",
                    "checkpoint_completed_batches": 0,
                    "checkpoint_total_batches": 0,
                }
                write_parquet_atomic(_empty_article_dataframe(spec), head_article_features_path(config, spec), index=False)
                write_parquet_atomic(daily, head_ticker_day_features_path(config, spec), index=False)
                _write_publish_job_status(
                    spec,
                    config,
                    status="complete",
                    phase="preflight",
                    progress_updates=metadata,
                    started_at=started_at,
                )
            else:
                run_signature = _head_publish_run_signature(
                    spec,
                    config,
                    winner=winner,
                    input_rows=input_rows,
                    input_source_signature=input_source_signature,
                )
                checkpoint_manifest = _load_publish_checkpoint_manifest(spec, config)
                if checkpoint_manifest and checkpoint_manifest.get("run_signature") != run_signature:
                    write_binary_head_publish_progress_line(
                        spec,
                        "preflight",
                        "publish checkpoint signature changed; clearing old checkpoint shards",
                    )
                    _clear_publish_checkpoint_state(spec, config)
                    checkpoint_manifest = {}
                model_id_key = f"{spec.dataset_prefix}_model_id"
                expected_model_id = str(run_signature.get(model_id_key) or "")
                if checkpoint_manifest and str(checkpoint_manifest.get(model_id_key) or "") != expected_model_id:
                    write_binary_head_publish_progress_line(
                        spec,
                        "preflight",
                        "publish checkpoint model id changed; clearing old checkpoint shards",
                    )
                    _clear_publish_checkpoint_state(spec, config)
                    checkpoint_manifest = {}

                if (
                    checkpoint_manifest.get("status") == "complete"
                    and checkpoint_manifest.get("run_signature") == run_signature
                    and str(checkpoint_manifest.get(model_id_key) or "") == expected_model_id
                    and head_article_features_path(config, spec).exists()
                    and head_ticker_day_features_path(config, spec).exists()
                ):
                    write_binary_head_publish_progress_line(
                        spec,
                        "reuse",
                        "publish checkpoint already complete; reusing published datasets",
                    )
                    daily = pd.read_parquet(head_ticker_day_features_path(config, spec))
                    metadata = {
                        f"{spec.dataset_prefix}_model_id": checkpoint_manifest.get(f"{spec.dataset_prefix}_model_id"),
                        "phobert_input_rows": input_rows,
                        "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
                        "daily_feature_rows": int(len(daily)),
                        "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
                        "checkpoint_status": "complete",
                        "checkpoint_completed_batches": int(checkpoint_manifest.get("completed_batch_count", 0)),
                        "checkpoint_total_batches": int(checkpoint_manifest.get("total_batches", 0)),
                    }
                    _write_publish_job_status(
                        spec,
                        config,
                        status="complete",
                        phase="reuse",
                        progress_updates=metadata,
                        started_at=started_at,
                    )
                else:
                    total_batches = max(
                        (input_rows + int(config.phobert_forward_looking_publish_checkpoint_rows) - 1)
                        // int(config.phobert_forward_looking_publish_checkpoint_rows),
                        1,
                    )
                    if not checkpoint_manifest:
                        checkpoint_manifest = {
                            "checkpoint_version": BINARY_HEAD_PUBLISH_CHECKPOINT_VERSION,
                            "status": "in_progress",
                            "run_signature": run_signature,
                            f"{spec.dataset_prefix}_model_id": str(winner["resolved_model_id"]),
                            "phobert_input_rows": input_rows,
                            "normalized_rows": normalized_rows,
                            "tagged_rows": tagged_rows,
                            "total_batches": int(total_batches),
                            "completed_batch_count": 0,
                            "article_score_rows": 0,
                            "unique_article_count": 0,
                            "completed_batches": {},
                            "created_at_utc": pd.Timestamp.utcnow().isoformat(),
                        }
                        _write_publish_checkpoint_manifest(spec, config, checkpoint_manifest)
                        write_binary_head_publish_progress_line(
                            spec,
                            "score",
                            f"publish checkpoint start total_batches={total_batches} checkpoint_rows={config.phobert_forward_looking_publish_checkpoint_rows}",
                        )
                    else:
                        write_binary_head_publish_progress_line(
                            spec,
                            "score",
                            "publish checkpoint resume "
                            f"completed_batches={int(checkpoint_manifest.get('completed_batch_count', 0))}/{total_batches} "
                            f"article_rows={int(checkpoint_manifest.get('article_score_rows', 0))} "
                            f"unique_articles={int(checkpoint_manifest.get('unique_article_count', 0))}",
                        )

                    build_start = perf_counter()
                    runtime_metadata = dict(scorer_metadata or {})
                    if scorer is None:
                        _write_publish_job_status(
                            spec,
                            config,
                            status="running",
                            phase="model_load",
                            progress_updates={
                                "total_batches": int(total_batches),
                                "input_rows": int(input_rows),
                            },
                            started_at=started_at,
                        )
                        scorer, loaded_metadata = _load_binary_head_scorer(spec, config, winner, log_progress=True)
                        runtime_metadata.update(loaded_metadata)
                    else:
                        runtime_metadata.setdefault(f"{spec.dataset_prefix}_model_id", str(winner["resolved_model_id"]))
                    runtime_metadata.setdefault(
                        f"{spec.dataset_prefix}_decision_threshold",
                        float(
                            winner.get(
                                "decision_threshold",
                                config.phobert_binary_head_default_positive_threshold(spec.name),
                            )
                        ),
                    )

                    tagged = tagged[
                        ["article_id", "ticker", "date", "url", "source", "match_source", "title_hit", "body_hit"]
                    ].copy()
                    tagged_indexed = tagged.set_index("article_id", drop=False)

                    completed_batches = dict(checkpoint_manifest.get("completed_batches") or {})
                    article_score_rows = int(checkpoint_manifest.get("article_score_rows", 0))
                    unique_article_count = int(checkpoint_manifest.get("unique_article_count", 0))
                    processed_input_rows = 0
                    processed_new_batches = 0
                    progress_interval = 25000
                    text_column = f"{spec.dataset_prefix}_input_text"
                    required_score_columns = [
                        f"{spec.dataset_prefix}_input_text_length",
                        f"{spec.dataset_prefix}_token_count",
                        f"{spec.dataset_prefix}_confidence",
                        f"{spec.dataset_prefix}_prob_negative",
                        f"{spec.dataset_prefix}_prob_positive",
                    ]

                    for batch_index, batch in enumerate(
                        input_file.iter_batches(
                            batch_size=int(config.phobert_forward_looking_publish_checkpoint_rows),
                            columns=PHOBERT_INPUT_COLUMNS,
                        ),
                        start=1,
                    ):
                        batch_key = str(batch_index)
                        batch_row_count = int(batch.num_rows)
                        processed_input_rows += batch_row_count
                        existing_meta = completed_batches.get(batch_key)
                        if existing_meta is not None:
                            shard_path_value = existing_meta.get("shard_path")
                            if int(existing_meta.get("article_rows", 0)) == 0 or (
                                shard_path_value and Path(str(shard_path_value)).exists()
                            ):
                                if (
                                    processed_input_rows == batch_row_count
                                    or processed_input_rows % progress_interval == 0
                                    or processed_input_rows >= input_rows
                                ):
                                    write_binary_head_publish_progress_line(
                                        spec,
                                        "score",
                                        f"input scan {processed_input_rows}/{input_rows} "
                                        f"unique_articles={unique_article_count} article_rows={article_score_rows} (resume skip)",
                                    )
                                continue

                        normalized_batch = batch.to_pandas()
                        normalized_batch["article_id"] = normalized_batch["article_id"].astype(str)
                        batch_unique_articles = 0
                        batch_article_rows = 0
                        shard_path: Optional[Path] = None

                        if not normalized_batch.empty:
                            text_parts = [
                                normalized_batch["clean_title"].fillna(""),
                                normalized_batch["clean_summary"].fillna(""),
                                normalized_batch["clean_body_text"].fillna(""),
                            ]
                            normalized_batch[text_column] = (
                                text_parts[0].astype(str).str.strip()
                                + " "
                                + text_parts[1].astype(str).str.strip()
                                + " "
                                + text_parts[2].astype(str).str.strip()
                            ).str.replace(r"\s+", " ", regex=True).str.strip()
                            normalized_batch = normalized_batch[normalized_batch[text_column].str.len() > 0].copy()
                            if not normalized_batch.empty:
                                normalized_batch = (
                                    normalized_batch.assign(_sort_len=normalized_batch[text_column].str.len())
                                    .sort_values("_sort_len", kind="mergesort")
                                    .drop(columns="_sort_len")
                                    .reset_index(drop=True)
                                )

                        if not normalized_batch.empty:
                            batch_unique_articles = int(len(normalized_batch))
                            score_rows = scorer(normalized_batch[text_column].tolist())
                            score_frame = pd.DataFrame(score_rows)
                            for column in required_score_columns:
                                if column not in score_frame.columns:
                                    raise ValueError(f"{spec.name} scorer is missing required column: {column}")
                            score_frame = _apply_decision_threshold_to_score_frame(
                                spec,
                                score_frame,
                                positive_threshold=float(runtime_metadata[f"{spec.dataset_prefix}_decision_threshold"]),
                            )
                            derived_score_columns = [
                                *required_score_columns,
                                f"{spec.dataset_prefix}_predicted_label",
                                f"{spec.dataset_prefix}_is_positive",
                            ]

                            article_scores = normalized_batch[["article_id", "published_at"]].copy()
                            article_scores[f"{spec.dataset_prefix}_model_id"] = str(
                                runtime_metadata.get(f"{spec.dataset_prefix}_model_id", winner["resolved_model_id"])
                            )
                            article_scores[derived_score_columns] = score_frame[derived_score_columns]

                            batch_tagged = tagged_indexed.loc[article_scores["article_id"].tolist()].reset_index(drop=True)
                            article_rows_batch = batch_tagged.merge(
                                article_scores,
                                on="article_id",
                                how="inner",
                                validate="many_to_one",
                            )
                            article_rows_batch = article_rows_batch[article_feature_columns(spec)]
                            article_rows_batch["published_at"] = article_rows_batch["published_at"].astype(str)
                            batch_article_rows = int(len(article_rows_batch))
                            if batch_article_rows > 0:
                                shard_path = head_publish_checkpoint_shard_path(config, spec, batch_index)
                                write_parquet_atomic(article_rows_batch, shard_path, index=False)

                        article_score_rows += batch_article_rows
                        unique_article_count += batch_unique_articles
                        completed_batches[batch_key] = {
                            "batch_index": int(batch_index),
                            "input_batch_rows": int(batch_row_count),
                            "matched_unique_articles": int(batch_unique_articles),
                            "article_rows": int(batch_article_rows),
                            "shard_path": str(shard_path) if shard_path is not None else None,
                        }
                        elapsed = max(perf_counter() - build_start, 1e-9)
                        checkpoint_manifest.update(
                            {
                                "status": "in_progress",
                                "run_signature": run_signature,
                                f"{spec.dataset_prefix}_model_id": runtime_metadata.get(
                                    f"{spec.dataset_prefix}_model_id",
                                    winner["resolved_model_id"],
                                ),
                                "completed_batches": completed_batches,
                                "completed_batch_count": int(len(completed_batches)),
                                "article_score_rows": int(article_score_rows),
                                "unique_article_count": int(unique_article_count),
                                "last_completed_batch": int(batch_index),
                                "last_updated_utc": pd.Timestamp.utcnow().isoformat(),
                            }
                        )
                        _write_publish_checkpoint_manifest(spec, config, checkpoint_manifest)
                        processed_new_batches += 1

                        if (
                            processed_input_rows == batch_row_count
                            or processed_input_rows % progress_interval == 0
                            or processed_input_rows >= input_rows
                        ):
                            write_binary_head_publish_progress_line(
                                spec,
                                "score",
                                f"input scan {processed_input_rows}/{input_rows} "
                                f"unique_articles={unique_article_count} article_rows={article_score_rows}",
                            )
                        _write_publish_job_status(
                            spec,
                            config,
                            status="running",
                            phase="score",
                            progress_updates={
                                "input_rows": int(input_rows),
                                "processed_input_rows": int(processed_input_rows),
                                "total_batches": int(total_batches),
                                "completed_batches": int(len(completed_batches)),
                                "article_score_rows": int(article_score_rows),
                                "unique_article_count": int(unique_article_count),
                            },
                            throughput_updates={
                                "input_rows_per_second": float(processed_input_rows / elapsed),
                                "batches_per_second": float(len(completed_batches) / elapsed),
                            },
                            started_at=started_at,
                        )

                        if checkpoint_batch_limit is not None and processed_new_batches >= int(checkpoint_batch_limit):
                            write_binary_head_publish_progress_line(
                                spec,
                                "score",
                                f"checkpoint test stop after {processed_new_batches} new batches",
                            )
                            break

                    if int(checkpoint_manifest.get("completed_batch_count", 0)) == int(
                        checkpoint_manifest.get("total_batches", total_batches)
                    ):
                        write_binary_head_publish_progress_line(
                            spec,
                            "finalize",
                            "checkpoint scoring complete; finalizing published datasets",
                        )
                        _write_publish_job_status(
                            spec,
                            config,
                            status="running",
                            phase="finalize",
                            progress_updates={
                                "total_batches": int(total_batches),
                                "completed_batches": int(checkpoint_manifest.get("completed_batch_count", 0)),
                                "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
                            },
                            started_at=started_at,
                        )
                        daily, finalized_metadata = _finalize_binary_head_from_checkpoints(
                            spec,
                            config=config,
                            checkpoint_manifest=checkpoint_manifest,
                        )
                        metadata = dict(runtime_metadata)
                        metadata.update(finalized_metadata)
                        _write_publish_job_status(
                            spec,
                            config,
                            status="complete",
                            phase="finalize",
                            progress_updates=metadata,
                            started_at=started_at,
                        )
                    else:
                        daily = _empty_daily_dataframe(spec, config)
                        metadata = dict(runtime_metadata)
                        metadata.update(
                            {
                                "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
                                "daily_feature_rows": 0,
                                "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
                                "checkpoint_status": "in_progress",
                                "checkpoint_completed_batches": int(
                                    checkpoint_manifest.get("completed_batch_count", 0)
                                ),
                                "checkpoint_total_batches": int(
                                    checkpoint_manifest.get("total_batches", total_batches)
                                ),
                            }
                        )

            metadata_path = head_metadata_path(config, spec)
            metadata.update(
                {
                    "phobert_input_rows": int(phobert_input_rows),
                    "article_score_rows": int(metadata.get("article_score_rows", 0)),
                    "daily_feature_rows": int(len(daily)),
                }
            )
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            update_manifest(
                config=config,
                **{
                    f"{spec.dataset_prefix}_model_id": str(metadata.get(f"{spec.dataset_prefix}_model_id")),
                    f"{spec.dataset_prefix}_article_feature_rows": int(metadata.get("article_score_rows", 0)),
                    f"{spec.dataset_prefix}_ticker_day_feature_rows": int(len(daily)),
                    f"{spec.dataset_prefix}_checkpoint_status": str(
                        metadata.get("checkpoint_status", "complete" if len(daily) > 0 else "in_progress")
                    ),
                    f"{spec.dataset_prefix}_checkpoint_completed_batches": int(
                        metadata.get("checkpoint_completed_batches", 0)
                    ),
                    f"{spec.dataset_prefix}_article_dataset": describe_path(head_article_features_path(config, spec), config=config),
                    f"{spec.dataset_prefix}_ticker_day_dataset": describe_path(head_ticker_day_features_path(config, spec), config=config),
                },
            )
            if str(metadata.get("checkpoint_status")) == "complete":
                write_stage_run_summary(
                    mode=f"{spec.summary_prefix}_publish",
                    name=f"{spec.dataset_prefix}_publish",
                    summary={
                        "status": "complete",
                        "article_score_rows": int(metadata.get("article_score_rows", 0)),
                        "daily_feature_rows": int(len(daily)),
                        "unique_article_count": int(metadata.get("unique_article_count", 0)),
                    },
                    artifacts={
                        "article_dataset": head_article_features_path(config, spec),
                        "ticker_day_dataset": head_ticker_day_features_path(config, spec),
                        "latest_winner": head_latest_winner_path(config, spec),
                    },
                    metadata={
                        f"{spec.dataset_prefix}_model_id": metadata.get(f"{spec.dataset_prefix}_model_id"),
                        "checkpoint_manifest": describe_path(head_publish_checkpoint_manifest_path(config, spec), config=config),
                    },
                )
    except Exception as exc:
        _write_publish_job_status(
            spec,
            config,
            status="failed",
            phase="failed",
            error=str(exc),
            started_at=started_at,
        )
        raise

    elapsed = perf_counter() - overall_start
    write_binary_head_publish_progress_line(
        spec,
        "complete",
        f"publish complete in {elapsed:.1f}s daily_rows={len(daily)} article_rows={int(metadata.get('article_score_rows', 0))}",
    )
    return daily
