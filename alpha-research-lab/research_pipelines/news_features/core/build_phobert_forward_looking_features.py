"""Publish additive PhoBERT forward-looking datasets from the trained local winner."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from itertools import islice
from pathlib import Path
import tempfile
from time import perf_counter
from typing import Callable, Optional

import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.core.build_phobert_sentiment_features import (
    PHOBERT_INPUT_COLUMNS,
    _prepare_phobert_input_articles_cache,
)
from research_pipelines.news_features.core.phobert_forward_looking_common import (
    ForwardLookingTrainingError,
    current_utc_timestamp,
    load_json_payload,
    path_signature,
    write_json_atomic,
    write_stage_run_summary,
)
from research_pipelines.news_features.io_utils import describe_path, update_manifest, write_parquet_atomic


ForwardLookingScoreFn = Callable[[list[str]], list[dict[str, object]]]

PHOBERT_FORWARD_LOOKING_PUBLISH_JOB_NAME = "phobert_forward_looking_publish"
PHOBERT_FORWARD_LOOKING_PUBLISH_CHECKPOINT_VERSION = 2

ARTICLE_COLUMNS = [
    "article_id",
    "ticker",
    "date",
    "published_at",
    "url",
    "source",
    "match_source",
    "title_hit",
    "body_hit",
    "phobert_forward_looking_model_id",
    "phobert_forward_looking_input_text_length",
    "phobert_forward_looking_token_count",
    "phobert_forward_looking_predicted_label",
    "phobert_forward_looking_is_forward_looking",
    "phobert_forward_looking_confidence",
    "phobert_forward_looking_prob_not_forward",
    "phobert_forward_looking_prob_forward",
]


def _empty_article_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=ARTICLE_COLUMNS)


def _empty_daily_dataframe(config: NewsFeaturesConfig) -> pd.DataFrame:
    return pd.DataFrame(columns=["ticker", "date", *config.phobert_forward_looking_daily_columns()])


def _batched(values: list[str], batch_size: int):
    iterator = iter(values)
    while True:
        batch = list(islice(iterator, max(int(batch_size), 1)))
        if not batch:
            break
        yield batch


def _load_latest_winner(config: NewsFeaturesConfig) -> dict[str, object]:
    config.ensure_phobert_forward_looking_model_state()
    winner_payload = load_json_payload(config.phobert_forward_looking_latest_winner_path())
    if not winner_payload:
        raise ForwardLookingTrainingError(
            "PhoBERT forward-looking publish requires a completed latest_winner.json bundle first."
        )
    model_dir = Path(str(winner_payload.get("model_dir") or "")).expanduser()
    if not model_dir.exists():
        raise ForwardLookingTrainingError(f"Winner model directory is missing: {model_dir}")
    training_manifest = load_json_payload(config.phobert_forward_looking_training_manifest_path())
    run_id = str(training_manifest.get("run_id") or model_dir.parent.parent.name or "unknown")
    candidate_name = str(winner_payload.get("candidate_name") or model_dir.parent.name or "unknown")
    winner_payload["run_id"] = run_id
    winner_payload["candidate_name"] = candidate_name
    winner_payload["model_dir"] = str(model_dir)
    winner_payload["resolved_model_id"] = f"phobert_forward_looking::{run_id}::{candidate_name}"
    return winner_payload


def _resolve_forward_labels(model) -> tuple[str, str]:
    config_map = getattr(model.config, "id2label", {}) or {}
    resolved: dict[int, str] = {}
    for key, value in config_map.items():
        try:
            idx = int(key)
        except (TypeError, ValueError):
            continue
        resolved[idx] = str(value).strip().upper()
    if not resolved:
        resolved = {0: "NOT_FORWARD_LOOKING", 1: "FORWARD_LOOKING"}

    forward_label = next(
        (label for label in resolved.values() if "FORWARD" in label and "NOT" not in label),
        resolved[max(resolved)],
    )
    not_forward_label = next(
        (label for label in resolved.values() if "NOT" in label and "FORWARD" in label),
        resolved[min(resolved)],
    )
    return forward_label, not_forward_label


def _load_forward_looking_scorer(
    config: NewsFeaturesConfig,
    winner: dict[str, object],
    *,
    log_progress: bool = False,
) -> tuple[ForwardLookingScoreFn, dict[str, object]]:
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise ImportError(
            "Forward-looking PhoBERT publish requires torch and transformers. Install project dependencies first."
        ) from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if config.phobert_forward_looking_precision == "fp16":
        dtype = torch.float16
    elif config.phobert_forward_looking_precision == "fp32":
        dtype = torch.float32
    else:
        dtype = torch.float16 if device == "cuda" else torch.float32

    model_dir = Path(str(winner["model_dir"]))
    if log_progress:
        print(
            f"Forward-looking PhoBERT model load: model_dir={model_dir}, device={device}, "
            f"dtype={str(dtype).replace('torch.', '')}",
            flush=True,
        )

    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, use_fast=False)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_dir,
        local_files_only=True,
        dtype=dtype,
    )
    model.to(device)
    model.eval()
    forward_label, not_forward_label = _resolve_forward_labels(model)
    if log_progress:
        print("Forward-looking PhoBERT model load complete", flush=True)

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
                prob_map = {
                    str(getattr(model.config, "id2label", {}).get(index, f"LABEL_{index}")).strip().upper(): float(probability)
                    for index, probability in enumerate(vector)
                }
                predicted_label = max(prob_map, key=prob_map.get)
                forward_prob = float(prob_map.get(forward_label, 0.0))
                not_forward_prob = float(prob_map.get(not_forward_label, max(0.0, 1.0 - forward_prob)))
                rows.append(
                    {
                        "phobert_forward_looking_input_text_length": int(len(raw_text)),
                        "phobert_forward_looking_token_count": int(token_count),
                        "phobert_forward_looking_predicted_label": predicted_label,
                        "phobert_forward_looking_is_forward_looking": bool(predicted_label == forward_label),
                        "phobert_forward_looking_confidence": float(prob_map[predicted_label]),
                        "phobert_forward_looking_prob_not_forward": not_forward_prob,
                        "phobert_forward_looking_prob_forward": forward_prob,
                    }
                )
            processed_texts += len(batch)
            if log_progress and (
                batch_index == 1
                or batch_index % progress_interval == 0
                or batch_index == total_batches
            ):
                print(
                    f"Forward-looking PhoBERT scoring batch {batch_index}/{total_batches}; "
                    f"processed_texts={processed_texts}/{total_texts}",
                    flush=True,
                )
        return rows

    metadata = {
        "phobert_forward_looking_model_id": str(winner["resolved_model_id"]),
        "phobert_forward_looking_candidate_name": str(winner["candidate_name"]),
        "phobert_forward_looking_model_name": str(winner.get("model_name") or model_dir.name),
        "phobert_forward_looking_run_id": str(winner["run_id"]),
        "phobert_forward_looking_device": device,
        "phobert_forward_looking_dtype": str(dtype).replace("torch.", ""),
        "torch_version": importlib.metadata.version("torch"),
        "transformers_version": importlib.metadata.version("transformers"),
    }
    return _score, metadata


def _clear_publish_checkpoint_state(config: NewsFeaturesConfig) -> None:
    checkpoint_dir = config.phobert_forward_looking_publish_checkpoint_dir()
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    for path in checkpoint_dir.iterdir():
        if path.is_file():
            path.unlink(missing_ok=True)


def _load_publish_checkpoint_manifest(config: NewsFeaturesConfig) -> dict[str, object]:
    return load_json_payload(config.phobert_forward_looking_publish_checkpoint_manifest_path())


def _write_publish_checkpoint_manifest(config: NewsFeaturesConfig, payload: dict[str, object]) -> None:
    write_json_atomic(config.phobert_forward_looking_publish_checkpoint_manifest_path(), payload)


def _publish_run_signature(
    config: NewsFeaturesConfig,
    winner: dict[str, object],
    *,
    input_rows: int,
    input_source_signature: dict[str, object],
) -> dict[str, object]:
    return {
        "checkpoint_version": PHOBERT_FORWARD_LOOKING_PUBLISH_CHECKPOINT_VERSION,
        "phobert_forward_looking_model_id": str(winner["resolved_model_id"]),
        "latest_winner": path_signature(config.phobert_forward_looking_latest_winner_path()),
        "winner_model_dir": path_signature(Path(str(winner["model_dir"]))),
        "training_manifest": path_signature(config.phobert_forward_looking_training_manifest_path()),
        "phobert_forward_looking_max_length": int(config.phobert_forward_looking_max_length),
        "phobert_forward_looking_precision": str(config.phobert_forward_looking_precision),
        "phobert_forward_looking_inference_batch_size": int(config.phobert_forward_looking_inference_batch_size),
        "phobert_forward_looking_publish_checkpoint_rows": int(config.phobert_forward_looking_publish_checkpoint_rows),
        "phobert_input_rows": int(input_rows),
        "phobert_input": path_signature(config.phobert_input_articles_path()),
        "phobert_input_source_signature": input_source_signature,
    }


def _publish_job_artifacts(config: NewsFeaturesConfig) -> dict[str, str]:
    artifact_paths = {
        "status_file": config.phobert_forward_looking_publish_job_status_path(),
        "latest_winner": config.phobert_forward_looking_latest_winner_path(),
        "training_manifest": config.phobert_forward_looking_training_manifest_path(),
        "article_dataset": config.phobert_forward_looking_article_features_path(),
        "ticker_day_dataset": config.phobert_forward_looking_ticker_day_features_path(),
        "checkpoint_manifest": config.phobert_forward_looking_publish_checkpoint_manifest_path(),
    }
    return {key: describe_path(path, config=config) for key, path in artifact_paths.items()}


def write_forward_looking_publish_progress_line(phase: str, message: str) -> None:
    print(f"[{PHOBERT_FORWARD_LOOKING_PUBLISH_JOB_NAME}][{str(phase)}] {message}", flush=True)


def _write_publish_job_status(
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
    status_path = config.phobert_forward_looking_publish_job_status_path()
    existing = load_json_payload(status_path)
    now = current_utc_timestamp()

    progress = dict(existing.get("progress") or {})
    progress.update(progress_updates or {})

    throughput = dict(existing.get("throughput") or {})
    throughput.update(throughput_updates or {})

    artifacts = dict(existing.get("artifacts") or {})
    artifacts.update(_publish_job_artifacts(config))
    for key, value in (artifact_updates or {}).items():
        if value is None:
            artifacts[str(key)] = None
        else:
            artifacts[str(key)] = describe_path(Path(str(value)), config=config)

    payload = {
        "job": PHOBERT_FORWARD_LOOKING_PUBLISH_JOB_NAME,
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


def _daily_feature_frame_from_state(
    daily_state: dict[tuple[str, str], dict[str, float]],
    config: NewsFeaturesConfig,
    *,
    log_progress: bool = False,
) -> pd.DataFrame:
    if not daily_state:
        return _empty_daily_dataframe(config)

    daily = pd.DataFrame(
        [
            {
                "ticker": ticker,
                "date": date,
                "phobert_forward_looking_article_count_1d": state["article_count"],
                "phobert_forward_looking_true_count_1d": state["true_count"],
                "phobert_forward_looking_share": state["true_count"] / state["article_count"],
                "phobert_forward_looking_prob_mean": state["prob_sum"] / state["article_count"],
                "phobert_forward_looking_prob_sum": state["prob_sum"],
                "phobert_forward_looking_confidence_mean": state["confidence_sum"] / state["article_count"],
            }
            for (ticker, date), state in daily_state.items()
            if state["article_count"] > 0
        ]
    )
    daily["date"] = pd.to_datetime(daily["date"])
    frames: list[pd.DataFrame] = []
    ticker_groups = list(daily.groupby("ticker", sort=True))
    total_tickers = len(ticker_groups)
    progress_interval = 1 if total_tickers <= 10 else 10
    value_columns = [
        "phobert_forward_looking_article_count_1d",
        "phobert_forward_looking_true_count_1d",
        "phobert_forward_looking_share",
        "phobert_forward_looking_prob_mean",
        "phobert_forward_looking_prob_sum",
        "phobert_forward_looking_confidence_mean",
    ]
    for ticker_index, (ticker, group) in enumerate(ticker_groups, start=1):
        group = group.sort_values("date").reset_index(drop=True)
        date_index = pd.date_range(group["date"].min(), group["date"].max(), freq="D")
        group = group.set_index("date").reindex(date_index)
        group["ticker"] = ticker
        for column in value_columns:
            group[column] = pd.to_numeric(group[column], errors="coerce").fillna(0.0)
        group["phobert_forward_looking_article_count_5d"] = (
            group["phobert_forward_looking_article_count_1d"].rolling(window=5, min_periods=1).sum()
        )
        group["phobert_forward_looking_article_count_30d"] = (
            group["phobert_forward_looking_article_count_1d"].rolling(window=30, min_periods=1).sum()
        )
        group["phobert_forward_looking_prob_5d"] = (
            group["phobert_forward_looking_prob_sum"].rolling(window=5, min_periods=1).sum()
        )
        group["phobert_forward_looking_prob_30d"] = (
            group["phobert_forward_looking_prob_sum"].rolling(window=30, min_periods=1).sum()
        )
        group = group.reset_index().rename(columns={"index": "date"})
        frames.append(group[["ticker", "date", *config.phobert_forward_looking_daily_columns()]])
        if log_progress and (
            ticker_index == 1
            or ticker_index % progress_interval == 0
            or ticker_index == total_tickers
        ):
            print(
                f"Forward-looking daily aggregation progress: processed {ticker_index}/{total_tickers} tickers",
                flush=True,
            )
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out.sort_values(["ticker", "date"]).reset_index(drop=True)


def _finalize_forward_looking_from_checkpoints(
    *,
    config: NewsFeaturesConfig,
    checkpoint_manifest: dict[str, object],
) -> tuple[pd.DataFrame, dict[str, object]]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Forward-looking PhoBERT checkpoint finalization requires pyarrow.") from exc

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
            ("phobert_forward_looking_model_id", pa.string()),
            ("phobert_forward_looking_input_text_length", pa.int64()),
            ("phobert_forward_looking_token_count", pa.int64()),
            ("phobert_forward_looking_predicted_label", pa.string()),
            ("phobert_forward_looking_is_forward_looking", pa.bool_()),
            ("phobert_forward_looking_confidence", pa.float64()),
            ("phobert_forward_looking_prob_not_forward", pa.float64()),
            ("phobert_forward_looking_prob_forward", pa.float64()),
        ]
    )
    completed_batches = checkpoint_manifest.get("completed_batches") or {}
    batch_items = sorted(completed_batches.items(), key=lambda item: int(item[0]))
    total_batches = len(batch_items)
    progress_interval = 1 if total_batches <= 10 else 25
    daily_state: dict[tuple[str, str], dict[str, float]] = {}
    writer = None
    temp_article_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=config.phobert_forward_looking_article_features_path().parent,
            suffix=".parquet",
            delete=False,
        ) as handle:
            temp_article_path = Path(handle.name)

        for batch_index, (_batch_key, batch_meta) in enumerate(batch_items, start=1):
            shard_path_value = batch_meta.get("shard_path")
            if not shard_path_value or int(batch_meta.get("article_rows", 0)) == 0:
                if batch_index == 1 or batch_index % progress_interval == 0 or batch_index == total_batches:
                    print(
                        f"Forward-looking finalize shard {batch_index}/{total_batches}; "
                        f"article_rows={checkpoint_manifest.get('article_score_rows', 0)}",
                        flush=True,
                    )
                continue
            shard_path = Path(str(shard_path_value))
            if not shard_path.exists():
                raise FileNotFoundError(f"Missing forward-looking checkpoint shard: {shard_path}")
            shard_df = pd.read_parquet(shard_path)
            if not shard_df.empty:
                table = pa.Table.from_pandas(shard_df[ARTICLE_COLUMNS], preserve_index=False, schema=article_schema)
                if writer is None:
                    writer = pq.ParquetWriter(temp_article_path, schema=article_schema)
                writer.write_table(table)

                grouped = (
                    shard_df.assign(
                        _forward_true=shard_df["phobert_forward_looking_is_forward_looking"].astype(float),
                    )
                    .groupby(["ticker", "date"], as_index=False)
                    .agg(
                        article_count=("article_id", "size"),
                        true_count=("_forward_true", "sum"),
                        prob_sum=("phobert_forward_looking_prob_forward", "sum"),
                        confidence_sum=("phobert_forward_looking_confidence", "sum"),
                    )
                )
                for row in grouped.to_dict(orient="records"):
                    key = (str(row["ticker"]), str(row["date"]))
                    state = daily_state.setdefault(
                        key,
                        {
                            "article_count": 0.0,
                            "true_count": 0.0,
                            "prob_sum": 0.0,
                            "confidence_sum": 0.0,
                        },
                    )
                    for field in state:
                        state[field] += float(row[field])
            if batch_index == 1 or batch_index % progress_interval == 0 or batch_index == total_batches:
                print(f"Forward-looking finalize shard {batch_index}/{total_batches}", flush=True)

        if writer is not None and temp_article_path is not None:
            writer.close()
            writer = None
            temp_article_path.replace(config.phobert_forward_looking_article_features_path())
        else:
            write_parquet_atomic(_empty_article_dataframe(), config.phobert_forward_looking_article_features_path(), index=False)
    finally:
        if writer is not None:
            writer.close()
        if temp_article_path is not None and temp_article_path.exists():
            temp_article_path.unlink(missing_ok=True)

    daily = _daily_feature_frame_from_state(daily_state, config, log_progress=True)
    write_parquet_atomic(daily, config.phobert_forward_looking_ticker_day_features_path(), index=False)

    checkpoint_manifest["status"] = "complete"
    checkpoint_manifest["daily_feature_rows"] = int(len(daily))
    checkpoint_manifest["completed_at_utc"] = pd.Timestamp.utcnow().isoformat()
    _write_publish_checkpoint_manifest(config, checkpoint_manifest)

    for batch_meta in completed_batches.values():
        shard_path_value = batch_meta.get("shard_path")
        if shard_path_value:
            Path(str(shard_path_value)).unlink(missing_ok=True)

    metadata = {
        "phobert_forward_looking_model_id": checkpoint_manifest.get("phobert_forward_looking_model_id"),
        "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
        "daily_feature_rows": int(len(daily)),
        "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
        "checkpoint_status": str(checkpoint_manifest.get("status", "unknown")),
        "checkpoint_completed_batches": int(checkpoint_manifest.get("completed_batch_count", 0)),
        "checkpoint_total_batches": int(checkpoint_manifest.get("total_batches", 0)),
    }
    return daily, metadata


def build_phobert_forward_looking_feature_exports(
    config: Optional[NewsFeaturesConfig] = None,
    scorer: Optional[ForwardLookingScoreFn] = None,
    scorer_metadata: Optional[dict[str, object]] = None,
    checkpoint_batch_limit: Optional[int] = None,
) -> pd.DataFrame:
    config = config or get_default_config()
    config.ensure_directories()
    overall_start = perf_counter()
    started_at = current_utc_timestamp()
    phobert_input_rows = 0
    try:
        if not config.normalized_path().exists() or not config.tagged_path().exists():
            write_forward_looking_publish_progress_line("preflight", "normalized or tagged inputs missing; publishing empty datasets")
            article_rows = _empty_article_dataframe()
            daily = _empty_daily_dataframe(config)
            metadata = {
                "phobert_forward_looking_model_id": None,
                "phobert_input_rows": 0,
                "article_score_rows": 0,
                "daily_feature_rows": 0,
                "unique_article_count": 0,
                "checkpoint_status": "complete",
                "checkpoint_completed_batches": 0,
                "checkpoint_total_batches": 0,
            }
            write_parquet_atomic(article_rows, config.phobert_forward_looking_article_features_path(), index=False)
            write_parquet_atomic(daily, config.phobert_forward_looking_ticker_day_features_path(), index=False)
            _write_publish_job_status(
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
                raise ImportError("Streaming forward-looking PhoBERT export requires pyarrow.") from exc

            winner = _load_latest_winner(config)
            _write_publish_job_status(
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
            print(
                f"Loaded normalized_rows={normalized_rows} and tagged_rows={tagged_rows} for forward-looking PhoBERT",
                flush=True,
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
            print(
                f"Forward-looking scoring universe: input_rows={input_rows} from {config.phobert_input_articles_path()}",
                flush=True,
            )
            if input_rows == 0:
                _clear_publish_checkpoint_state(config)
                daily = _empty_daily_dataframe(config)
                metadata = {
                    "phobert_forward_looking_model_id": winner["resolved_model_id"],
                    "phobert_input_rows": 0,
                    "article_score_rows": 0,
                    "daily_feature_rows": 0,
                    "unique_article_count": 0,
                    "checkpoint_status": "complete",
                    "checkpoint_completed_batches": 0,
                    "checkpoint_total_batches": 0,
                }
                write_parquet_atomic(_empty_article_dataframe(), config.phobert_forward_looking_article_features_path(), index=False)
                write_parquet_atomic(daily, config.phobert_forward_looking_ticker_day_features_path(), index=False)
                _write_publish_job_status(
                    config,
                    status="complete",
                    phase="preflight",
                    progress_updates=metadata,
                    started_at=started_at,
                )
            else:
                run_signature = _publish_run_signature(
                    config,
                    winner,
                    input_rows=input_rows,
                    input_source_signature=input_source_signature,
                )
                checkpoint_manifest = _load_publish_checkpoint_manifest(config)
                if checkpoint_manifest and checkpoint_manifest.get("run_signature") != run_signature:
                    print("Forward-looking publish checkpoint signature changed; clearing old checkpoint shards", flush=True)
                    _clear_publish_checkpoint_state(config)
                    checkpoint_manifest = {}

                if (
                    checkpoint_manifest.get("status") == "complete"
                    and checkpoint_manifest.get("run_signature") == run_signature
                    and config.phobert_forward_looking_article_features_path().exists()
                    and config.phobert_forward_looking_ticker_day_features_path().exists()
                ):
                    print("Forward-looking publish checkpoint already complete; reusing published datasets", flush=True)
                    daily = pd.read_parquet(config.phobert_forward_looking_ticker_day_features_path())
                    metadata = {
                        "phobert_forward_looking_model_id": checkpoint_manifest.get("phobert_forward_looking_model_id"),
                        "phobert_input_rows": input_rows,
                        "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
                        "daily_feature_rows": int(len(daily)),
                        "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
                        "checkpoint_status": "complete",
                        "checkpoint_completed_batches": int(checkpoint_manifest.get("completed_batch_count", 0)),
                        "checkpoint_total_batches": int(checkpoint_manifest.get("total_batches", 0)),
                    }
                    _write_publish_job_status(
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
                            "checkpoint_version": PHOBERT_FORWARD_LOOKING_PUBLISH_CHECKPOINT_VERSION,
                            "status": "in_progress",
                            "run_signature": run_signature,
                            "phobert_forward_looking_model_id": str(winner["resolved_model_id"]),
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
                        _write_publish_checkpoint_manifest(config, checkpoint_manifest)
                        print(
                            f"Forward-looking publish checkpoint start: total_batches={total_batches}, "
                            f"checkpoint_rows={config.phobert_forward_looking_publish_checkpoint_rows}",
                            flush=True,
                        )
                    else:
                        print(
                            "Forward-looking publish checkpoint resume: "
                            f"completed_batches={int(checkpoint_manifest.get('completed_batch_count', 0))}/{total_batches}, "
                            f"article_rows={int(checkpoint_manifest.get('article_score_rows', 0))}, "
                            f"unique_articles={int(checkpoint_manifest.get('unique_article_count', 0))}",
                            flush=True,
                        )

                    build_start = perf_counter()
                    runtime_metadata = dict(scorer_metadata or {})
                    if scorer is None:
                        _write_publish_job_status(
                            config,
                            status="running",
                            phase="model_load",
                            progress_updates={
                                "total_batches": int(total_batches),
                                "input_rows": int(input_rows),
                            },
                            started_at=started_at,
                        )
                        scorer, loaded_metadata = _load_forward_looking_scorer(config, winner, log_progress=True)
                        runtime_metadata.update(loaded_metadata)
                    else:
                        runtime_metadata.setdefault("phobert_forward_looking_model_id", str(winner["resolved_model_id"]))

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
                                    print(
                                        f"Forward-looking input scan {processed_input_rows}/{input_rows}; "
                                        f"unique_articles={unique_article_count}, article_rows={article_score_rows} "
                                        "(resume skip)",
                                        flush=True,
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
                            normalized_batch["phobert_forward_looking_input_text"] = (
                                text_parts[0].astype(str).str.strip()
                                + " "
                                + text_parts[1].astype(str).str.strip()
                                + " "
                                + text_parts[2].astype(str).str.strip()
                            ).str.replace(r"\s+", " ", regex=True).str.strip()
                            normalized_batch = normalized_batch[
                                normalized_batch["phobert_forward_looking_input_text"].str.len() > 0
                            ].copy()
                            if not normalized_batch.empty:
                                normalized_batch = (
                                    normalized_batch.assign(
                                        _sort_len=normalized_batch["phobert_forward_looking_input_text"].str.len()
                                    )
                                    .sort_values("_sort_len", kind="mergesort")
                                    .drop(columns="_sort_len")
                                    .reset_index(drop=True)
                                )

                        if not normalized_batch.empty:
                            batch_unique_articles = int(len(normalized_batch))
                            score_rows = scorer(normalized_batch["phobert_forward_looking_input_text"].tolist())
                            score_frame = pd.DataFrame(score_rows)
                            required_score_columns = [
                                "phobert_forward_looking_input_text_length",
                                "phobert_forward_looking_token_count",
                                "phobert_forward_looking_predicted_label",
                                "phobert_forward_looking_is_forward_looking",
                                "phobert_forward_looking_confidence",
                                "phobert_forward_looking_prob_not_forward",
                                "phobert_forward_looking_prob_forward",
                            ]
                            for column in required_score_columns:
                                if column not in score_frame.columns:
                                    raise ValueError(f"Forward-looking scorer is missing required column: {column}")

                            article_scores = normalized_batch[["article_id", "published_at"]].copy()
                            article_scores["phobert_forward_looking_model_id"] = str(
                                runtime_metadata.get("phobert_forward_looking_model_id", winner["resolved_model_id"])
                            )
                            article_scores[required_score_columns] = score_frame[required_score_columns]

                            batch_tagged = tagged_indexed.loc[article_scores["article_id"].tolist()].reset_index(drop=True)
                            article_rows_batch = batch_tagged.merge(
                                article_scores,
                                on="article_id",
                                how="inner",
                                validate="many_to_one",
                            )
                            article_rows_batch = article_rows_batch[ARTICLE_COLUMNS]
                            article_rows_batch["published_at"] = article_rows_batch["published_at"].astype(str)
                            batch_article_rows = int(len(article_rows_batch))
                            if batch_article_rows > 0:
                                shard_path = config.phobert_forward_looking_publish_checkpoint_shard_path(batch_index)
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
                                "phobert_forward_looking_model_id": runtime_metadata.get(
                                    "phobert_forward_looking_model_id",
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
                        _write_publish_checkpoint_manifest(config, checkpoint_manifest)
                        processed_new_batches += 1

                        if (
                            processed_input_rows == batch_row_count
                            or processed_input_rows % progress_interval == 0
                            or processed_input_rows >= input_rows
                        ):
                            print(
                                f"Forward-looking input scan {processed_input_rows}/{input_rows}; "
                                f"unique_articles={unique_article_count}, article_rows={article_score_rows}",
                                flush=True,
                            )
                        _write_publish_job_status(
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
                            print(
                                f"Forward-looking checkpoint test stop after {processed_new_batches} new batches",
                                flush=True,
                            )
                            break

                    if int(checkpoint_manifest.get("completed_batch_count", 0)) == int(
                        checkpoint_manifest.get("total_batches", total_batches)
                    ):
                        print("Forward-looking checkpoint scoring complete. Finalizing published datasets...", flush=True)
                        _write_publish_job_status(
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
                        daily, finalized_metadata = _finalize_forward_looking_from_checkpoints(
                            config=config,
                            checkpoint_manifest=checkpoint_manifest,
                        )
                        metadata = dict(runtime_metadata)
                        metadata.update(finalized_metadata)
                        _write_publish_job_status(
                            config,
                            status="complete",
                            phase="finalize",
                            progress_updates=metadata,
                            started_at=started_at,
                        )
                    else:
                        daily = _empty_daily_dataframe(config)
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

            metadata_path = config.phobert_forward_looking_metadata_path()
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
                phobert_forward_looking_model_id=str(metadata.get("phobert_forward_looking_model_id")),
                phobert_forward_looking_article_feature_rows=int(metadata.get("article_score_rows", 0)),
                phobert_forward_looking_ticker_day_feature_rows=int(len(daily)),
                phobert_forward_looking_checkpoint_status=str(
                    metadata.get("checkpoint_status", "complete" if len(daily) > 0 else "in_progress")
                ),
                phobert_forward_looking_checkpoint_completed_batches=int(
                    metadata.get("checkpoint_completed_batches", 0)
                ),
            )
            if str(metadata.get("checkpoint_status")) == "complete":
                write_stage_run_summary(
                    mode="news_forward_looking_publish",
                    name="phobert_forward_looking_publish",
                    summary={
                        "status": "complete",
                        "article_score_rows": int(metadata.get("article_score_rows", 0)),
                        "daily_feature_rows": int(len(daily)),
                        "unique_article_count": int(metadata.get("unique_article_count", 0)),
                    },
                    artifacts={
                        "article_dataset": config.phobert_forward_looking_article_features_path(),
                        "ticker_day_dataset": config.phobert_forward_looking_ticker_day_features_path(),
                        "latest_winner": config.phobert_forward_looking_latest_winner_path(),
                    },
                    metadata={
                        "phobert_forward_looking_model_id": metadata.get("phobert_forward_looking_model_id"),
                        "checkpoint_manifest": describe_path(
                            config.phobert_forward_looking_publish_checkpoint_manifest_path(),
                            config=config,
                        ),
                    },
                )
    except Exception as exc:
        _write_publish_job_status(
            config,
            status="failed",
            phase="failed",
            error=str(exc),
            started_at=started_at,
        )
        raise

    elapsed = perf_counter() - overall_start
    print(
        f"Forward-looking PhoBERT publish complete in {elapsed:.1f}s: "
        f"daily_rows={len(daily)}, article_rows={int(metadata.get('article_score_rows', 0))}",
        flush=True,
    )
    return daily


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=(
            "Build additive PhoBERT forward-looking article and ticker-day datasets "
            "from the latest trained local winner."
        )
    )


def main() -> None:
    build_arg_parser().parse_args()
    config = get_default_config()
    build_phobert_forward_looking_feature_exports(config=config)


if __name__ == "__main__":
    main()
