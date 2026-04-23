"""Build whole-article PhoBERT sentiment datasets from tagged news articles."""

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
from research_pipelines.news_features.io_utils import describe_path, update_manifest, write_parquet_atomic


PhoBertScoreFn = Callable[[list[str]], list[dict[str, object]]]

PHOBERT_INPUT_COLUMNS = [
    "article_id",
    "published_at",
    "clean_title",
    "clean_summary",
    "clean_body_text",
]

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
    "phobert_model_id",
    "phobert_input_text_length",
    "phobert_segmented_text_length",
    "phobert_predicted_label",
    "phobert_confidence",
    "phobert_prob_neg",
    "phobert_prob_neu",
    "phobert_prob_pos",
    "phobert_sentiment_score",
    "phobert_sentiment_conf_weighted",
]


def _empty_article_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=ARTICLE_COLUMNS)


def _empty_daily_dataframe(config: NewsFeaturesConfig) -> pd.DataFrame:
    return pd.DataFrame(columns=["ticker", "date", *config.phobert_daily_columns()])


def _batched(values: list[str], batch_size: int):
    iterator = iter(values)
    while True:
        batch = list(islice(iterator, max(int(batch_size), 1)))
        if not batch:
            break
        yield batch


def _compose_article_text(row: pd.Series) -> str:
    parts = [row.get("clean_title", ""), row.get("clean_summary", ""), row.get("clean_body_text", "")]
    return " ".join(str(part).strip() for part in parts if str(part).strip())


def _label_score(label: str) -> float:
    canonical = str(label).strip().upper()
    if canonical == "NEG":
        return -1.0
    if canonical == "POS":
        return 1.0
    return 0.0


def _canonical_label(raw_label: str) -> str:
    label = str(raw_label).strip().upper()
    if "NEG" in label or label in {"0", "LABEL_0", "NEGATIVE"}:
        return "NEG"
    if "POS" in label or label in {"1", "LABEL_1", "POSITIVE"}:
        return "POS"
    if "NEU" in label or "NEUTRAL" in label or label in {"2", "LABEL_2"}:
        return "NEU"
    return label


def _resolve_id2label(model_id: str, model) -> dict[int, str]:
    overrides = {
        "Angelectronic/phobert-base-vietnamese-sentiment": {0: "NEG", 1: "POS", 2: "NEU"},
        "wonrax/phobert-base-vietnamese-sentiment": {0: "NEG", 1: "POS", 2: "NEU"},
        "sanvo/vietnamese-sentiment-phobert": {0: "NEG", 1: "NEU", 2: "POS"},
    }
    override = overrides.get(model_id)
    if override:
        return override

    config_map = getattr(model.config, "id2label", {}) or {}
    resolved: dict[int, str] = {}
    for key, value in config_map.items():
        try:
            idx = int(key)
        except (TypeError, ValueError):
            continue
        resolved[idx] = _canonical_label(str(value))
    if resolved:
        return resolved

    return {idx: f"LABEL_{idx}" for idx in range(getattr(model.config, "num_labels", 0))}


def _load_phobert_scorer(
    config: NewsFeaturesConfig,
    *,
    log_progress: bool = False,
) -> tuple[PhoBertScoreFn, dict[str, object]]:
    try:
        import torch
        from pyvi import ViTokenizer
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise ImportError(
            "PhoBERT sentiment features require torch, transformers, and pyvi. Install project dependencies first."
        ) from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if config.phobert_precision == "fp16":
        dtype = torch.float16
    elif config.phobert_precision == "fp32":
        dtype = torch.float32
    else:
        dtype = torch.float16 if device == "cuda" else torch.float32

    if log_progress:
        print(
            f"PhoBERT model load: model={config.phobert_model_name}, device={device}, dtype={str(dtype).replace('torch.', '')}",
            flush=True,
        )

    def _load_from_pretrained(loader, *, loader_name: str, **kwargs: object):
        if config.phobert_prefer_local_files:
            try:
                return loader.from_pretrained(
                    config.phobert_model_name,
                    local_files_only=True,
                    **kwargs,
                )
            except Exception:
                if log_progress:
                    print(
                        f"PhoBERT {loader_name} local cache miss; falling back to Hugging Face",
                        flush=True,
                    )
        return loader.from_pretrained(config.phobert_model_name, **kwargs)

    tokenizer = _load_from_pretrained(AutoTokenizer, loader_name="tokenizer", use_fast=False)
    model = _load_from_pretrained(
        AutoModelForSequenceClassification,
        loader_name="model",
        dtype=dtype,
    )
    model.to(device)
    model.eval()
    id2label = _resolve_id2label(config.phobert_model_name, model)
    if log_progress:
        print("PhoBERT model load complete", flush=True)

    def _score(texts: list[str]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        total_texts = len(texts)
        total_batches = max((total_texts + config.phobert_batch_size - 1) // config.phobert_batch_size, 1)
        progress_interval = 1 if total_batches <= 10 else 25
        processed_texts = 0
        for batch_index, batch in enumerate(_batched(texts, config.phobert_batch_size), start=1):
            segmented_batch = [ViTokenizer.tokenize(text) if str(text).strip() else "" for text in batch]
            encoded = tokenizer(
                segmented_batch,
                padding=True,
                truncation=True,
                max_length=config.phobert_max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            with torch.inference_mode():
                logits = model(**encoded).logits
                probabilities = torch.softmax(logits.float(), dim=-1).cpu().tolist()
            for raw_text, segmented_text, vector in zip(batch, segmented_batch, probabilities):
                prob_map = {
                    id2label.get(index, f"LABEL_{index}"): float(probability)
                    for index, probability in enumerate(vector)
                }
                predicted_label = max(prob_map, key=prob_map.get)
                rows.append(
                    {
                        "phobert_input_text_length": int(len(raw_text)),
                        "phobert_segmented_text_length": int(len(segmented_text)),
                        "phobert_predicted_label": predicted_label,
                        "phobert_confidence": float(prob_map[predicted_label]),
                        "phobert_prob_neg": float(prob_map.get("NEG", 0.0)),
                        "phobert_prob_neu": float(prob_map.get("NEU", 0.0)),
                        "phobert_prob_pos": float(prob_map.get("POS", 0.0)),
                    }
                )
            processed_texts += len(batch)
            if log_progress and (
                batch_index == 1
                or batch_index % progress_interval == 0
                or batch_index == total_batches
            ):
                print(
                    f"PhoBERT scoring batch {batch_index}/{total_batches}; processed_texts={processed_texts}/{total_texts}",
                    flush=True,
                )
        return rows

    metadata = {
        "phobert_model_id": config.phobert_model_name,
        "phobert_device": device,
        "phobert_dtype": str(dtype).replace("torch.", ""),
        "torch_version": importlib.metadata.version("torch"),
        "transformers_version": importlib.metadata.version("transformers"),
        "pyvi_version": importlib.metadata.version("pyvi"),
    }
    return _score, metadata


def build_phobert_article_sentiment_dataframe(
    normalized_df: pd.DataFrame,
    tagged_df: pd.DataFrame,
    config: Optional[NewsFeaturesConfig] = None,
    scorer: Optional[PhoBertScoreFn] = None,
    scorer_metadata: Optional[dict[str, object]] = None,
    log_progress: bool = False,
) -> tuple[pd.DataFrame, dict[str, object]]:
    config = config or get_default_config()
    if normalized_df.empty or tagged_df.empty:
        metadata = {
            "phobert_model_id": config.phobert_model_name,
            "article_score_rows": 0,
            "unique_article_count": 0,
        }
        return _empty_article_dataframe(), metadata

    normalized = normalized_df.copy()
    for column, default_value in (
        ("published_at", None),
        ("clean_title", ""),
        ("clean_summary", ""),
        ("clean_body_text", ""),
    ):
        if column not in normalized.columns:
            normalized[column] = default_value

    if log_progress:
        print(
            f"PhoBERT stage 1/3: merging tagged_rows={len(tagged_df)} with normalized_rows={len(normalized_df)}",
            flush=True,
        )
    merged = tagged_df.merge(
        normalized[
            [
                "article_id",
                "url",
                "date",
                "source",
                "published_at",
                "clean_title",
                "clean_summary",
                "clean_body_text",
            ]
        ],
        on=["article_id", "url", "date", "source"],
        how="left",
        validate="many_to_one",
    )
    unique_articles = (
        merged[
            [
                "article_id",
                "url",
                "date",
                "source",
                "published_at",
                "clean_title",
                "clean_summary",
                "clean_body_text",
            ]
        ]
        .drop_duplicates(subset=["article_id", "url", "date", "source"])
        .copy()
    )
    unique_articles["phobert_input_text"] = unique_articles.apply(_compose_article_text, axis=1)
    unique_articles = unique_articles[unique_articles["phobert_input_text"].str.len() > 0].reset_index(drop=True)
    if unique_articles.empty:
        metadata = {
            "phobert_model_id": config.phobert_model_name,
            "article_score_rows": 0,
            "unique_article_count": 0,
        }
        return _empty_article_dataframe(), metadata

    score_fn = scorer
    metadata = dict(scorer_metadata or {})
    if score_fn is None:
        score_fn, runtime_metadata = _load_phobert_scorer(config, log_progress=log_progress)
        metadata.update(runtime_metadata)
    else:
        metadata.setdefault("phobert_model_id", config.phobert_model_name)

    if log_progress:
        print(f"PhoBERT stage 2/3: scoring {len(unique_articles)} unique article texts", flush=True)
    score_rows = score_fn(unique_articles["phobert_input_text"].tolist())
    if len(score_rows) != len(unique_articles):
        raise ValueError("PhoBERT scorer must return exactly one score row per unique article text")
    score_frame = pd.DataFrame(score_rows)

    required_score_columns = [
        "phobert_input_text_length",
        "phobert_segmented_text_length",
        "phobert_predicted_label",
        "phobert_confidence",
        "phobert_prob_neg",
        "phobert_prob_neu",
        "phobert_prob_pos",
    ]
    missing_columns = [column for column in required_score_columns if column not in score_frame.columns]
    if missing_columns:
        raise ValueError(f"PhoBERT scorer is missing required columns: {missing_columns}")

    article_scores = unique_articles[["article_id", "url", "date", "source", "published_at"]].copy()
    article_scores["phobert_model_id"] = str(metadata.get("phobert_model_id", config.phobert_model_name))
    article_scores[required_score_columns] = score_frame[required_score_columns]
    article_scores["phobert_predicted_label"] = article_scores["phobert_predicted_label"].map(_canonical_label)
    article_scores["phobert_sentiment_score"] = article_scores["phobert_predicted_label"].map(_label_score)
    article_scores["phobert_sentiment_conf_weighted"] = (
        article_scores["phobert_sentiment_score"] * article_scores["phobert_confidence"].astype(float)
    )

    article_rows = merged[
        [
            "article_id",
            "ticker",
            "date",
            "url",
            "source",
            "match_source",
            "title_hit",
            "body_hit",
        ]
    ].merge(
        article_scores,
        on=["article_id", "url", "date", "source"],
        how="inner",
        validate="many_to_one",
    )
    article_rows = article_rows[ARTICLE_COLUMNS].sort_values(["ticker", "date", "article_id"]).reset_index(drop=True)
    metadata.update(
        {
            "article_score_rows": int(len(article_rows)),
            "unique_article_count": int(len(unique_articles)),
        }
    )
    if log_progress:
        print(
            f"PhoBERT stage 3/3 complete: article_score_rows={len(article_rows)}, "
            f"unique_articles={len(unique_articles)}",
            flush=True,
        )
    return article_rows, metadata


def build_phobert_daily_sentiment_dataframe(
    article_df: pd.DataFrame,
    config: Optional[NewsFeaturesConfig] = None,
    log_progress: bool = False,
) -> pd.DataFrame:
    config = config or get_default_config()
    if article_df.empty:
        return _empty_daily_dataframe(config)

    working = article_df.copy()
    working["is_pos"] = (working["phobert_predicted_label"] == "POS").astype(float)
    working["is_neu"] = (working["phobert_predicted_label"] == "NEU").astype(float)
    working["is_neg"] = (working["phobert_predicted_label"] == "NEG").astype(float)

    if log_progress:
        print(
            f"PhoBERT daily aggregation: grouping {len(working)} article-ticker rows into ticker-day features",
            flush=True,
        )
    daily = (
        working.groupby(["ticker", "date"], as_index=False)
        .agg(
            phobert_article_count_1d=("article_id", "size"),
            phobert_sentiment_score_mean=("phobert_sentiment_score", "mean"),
            phobert_sentiment_score_sum=("phobert_sentiment_score", "sum"),
            phobert_sentiment_conf_weighted_mean=("phobert_sentiment_conf_weighted", "mean"),
            phobert_sentiment_conf_weighted_sum=("phobert_sentiment_conf_weighted", "sum"),
            phobert_prob_pos_mean=("phobert_prob_pos", "mean"),
            phobert_prob_neu_mean=("phobert_prob_neu", "mean"),
            phobert_prob_neg_mean=("phobert_prob_neg", "mean"),
            phobert_pos_share=("is_pos", "mean"),
            phobert_neu_share=("is_neu", "mean"),
            phobert_neg_share=("is_neg", "mean"),
        )
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )
    daily["date"] = pd.to_datetime(daily["date"])

    frames: list[pd.DataFrame] = []
    for ticker, group in daily.groupby("ticker", sort=True):
        group = group.sort_values("date").reset_index(drop=True)
        date_index = pd.date_range(group["date"].min(), group["date"].max(), freq="D")
        group = group.set_index("date").reindex(date_index)
        group["ticker"] = ticker
        fill_columns = [column for column in group.columns if column != "ticker"]
        for column in fill_columns:
            group[column] = pd.to_numeric(group[column], errors="coerce").fillna(0.0)

        # Rolling PhoBERT state mirrors the existing LLM convention:
        # daily confidence-weighted sentiment intensity is summed over trailing windows.
        group["phobert_article_count_5d"] = (
            group["phobert_article_count_1d"].rolling(window=5, min_periods=1).sum()
        )
        group["phobert_article_count_30d"] = (
            group["phobert_article_count_1d"].rolling(window=30, min_periods=1).sum()
        )
        group["phobert_sentiment_5d"] = (
            group["phobert_sentiment_conf_weighted_mean"].rolling(window=5, min_periods=1).sum()
        )
        group["phobert_sentiment_30d"] = (
            group["phobert_sentiment_conf_weighted_mean"].rolling(window=30, min_periods=1).sum()
        )
        group = group.reset_index().rename(columns={"index": "date"})
        frames.append(group[["ticker", "date", *config.phobert_daily_columns()]])

    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out.sort_values(["ticker", "date"]).reset_index(drop=True)


PHOBERT_INPUT_CACHE_VERSION = 1
PHOBERT_CHECKPOINT_VERSION = 2


def _path_checkpoint_signature(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _phobert_input_source_signature(
    config: NewsFeaturesConfig,
    *,
    normalized_rows: int,
    tagged_rows: int,
) -> dict[str, object]:
    return {
        "input_cache_version": PHOBERT_INPUT_CACHE_VERSION,
        "normalized_rows": int(normalized_rows),
        "tagged_rows": int(tagged_rows),
        "normalized_input": _path_checkpoint_signature(config.normalized_path()),
        "tagged_input": _path_checkpoint_signature(config.tagged_path()),
    }


def _phobert_run_signature(
    config: NewsFeaturesConfig,
    *,
    input_rows: int,
    input_source_signature: dict[str, object],
) -> dict[str, object]:
    return {
        "checkpoint_version": PHOBERT_CHECKPOINT_VERSION,
        "phobert_model_name": config.phobert_model_name,
        "phobert_batch_size": int(config.phobert_batch_size),
        "phobert_max_length": int(config.phobert_max_length),
        "phobert_precision": str(config.phobert_precision),
        "phobert_checkpoint_rows": int(config.phobert_checkpoint_rows),
        "phobert_prefer_local_files": bool(config.phobert_prefer_local_files),
        "phobert_input_rows": int(input_rows),
        "phobert_input": _path_checkpoint_signature(config.phobert_input_articles_path()),
        "phobert_input_source_signature": input_source_signature,
    }


def _load_phobert_checkpoint_manifest(config: NewsFeaturesConfig) -> dict[str, object]:
    path = config.phobert_checkpoint_manifest_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".json", delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def _write_phobert_checkpoint_manifest(config: NewsFeaturesConfig, payload: dict[str, object]) -> None:
    _write_json_atomic(config.phobert_checkpoint_manifest_path(), payload)


def _load_phobert_input_manifest(config: NewsFeaturesConfig) -> dict[str, object]:
    path = config.phobert_input_manifest_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_phobert_input_manifest(config: NewsFeaturesConfig, payload: dict[str, object]) -> None:
    _write_json_atomic(config.phobert_input_manifest_path(), payload)


def _clear_phobert_checkpoint_state(config: NewsFeaturesConfig) -> None:
    checkpoint_dir = config.phobert_checkpoint_dir()
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    for path in checkpoint_dir.iterdir():
        if path.is_file():
            path.unlink(missing_ok=True)


def _prepare_phobert_input_articles_cache(
    *,
    config: NewsFeaturesConfig,
    normalized_file,
    normalized_rows: int,
    tagged: pd.DataFrame,
) -> dict[str, object]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Preparing PhoBERT input cache requires pyarrow.") from exc

    tagged_article_ids = set(tagged["article_id"].astype(str).tolist())
    source_signature = _phobert_input_source_signature(
        config,
        normalized_rows=int(normalized_rows),
        tagged_rows=int(len(tagged)),
    )
    input_manifest = _load_phobert_input_manifest(config)
    input_path = config.phobert_input_articles_path()
    if (
        input_path.exists()
        and input_manifest.get("source_signature") == source_signature
    ):
        cached_rows = int(
            input_manifest.get("input_rows", pq.ParquetFile(input_path).metadata.num_rows)
        )
        print(
            f"PhoBERT input cache reuse: input_rows={cached_rows}, unique_tagged_articles={len(tagged_article_ids)}",
            flush=True,
        )
        input_manifest["input_rows"] = cached_rows
        return input_manifest

    print(
        f"PhoBERT input cache rebuild: scanning normalized_rows={normalized_rows} for "
        f"{len(tagged_article_ids)} unique tagged articles",
        flush=True,
    )
    input_schema = pa.schema([(column, pa.string()) for column in PHOBERT_INPUT_COLUMNS])
    input_writer = None
    temp_input_path: Optional[Path] = None
    input_rows = 0
    scanned_rows = 0
    input_batch_size = max(int(config.phobert_checkpoint_rows) * 10, 20000)
    progress_interval = 50000
    try:
        with tempfile.NamedTemporaryFile(
            dir=input_path.parent,
            suffix=".parquet",
            delete=False,
        ) as handle:
            temp_input_path = Path(handle.name)

        for batch_index, batch in enumerate(
            normalized_file.iter_batches(batch_size=input_batch_size, columns=PHOBERT_INPUT_COLUMNS),
            start=1,
        ):
            batch_df = batch.to_pandas()
            batch_row_count = int(len(batch_df))
            scanned_rows += batch_row_count
            batch_df["article_id"] = batch_df["article_id"].astype(str)
            batch_df = batch_df[batch_df["article_id"].isin(tagged_article_ids)].copy()
            matched_rows = int(len(batch_df))
            if matched_rows > 0:
                for column in PHOBERT_INPUT_COLUMNS:
                    batch_df[column] = batch_df[column].fillna("").astype(str)
                table = pa.Table.from_pandas(
                    batch_df[PHOBERT_INPUT_COLUMNS],
                    preserve_index=False,
                    schema=input_schema,
                )
                if input_writer is None:
                    input_writer = pq.ParquetWriter(temp_input_path, schema=table.schema)
                input_writer.write_table(table)
                input_rows += matched_rows
            if (
                scanned_rows == batch_row_count
                or scanned_rows % progress_interval == 0
                or scanned_rows >= normalized_rows
            ):
                print(
                    f"PhoBERT input cache scan {scanned_rows}/{normalized_rows}; "
                    f"matched_input_rows={input_rows}, last_batch_matches={matched_rows}, batch_index={batch_index}",
                    flush=True,
                )

        if input_writer is not None and temp_input_path is not None:
            input_writer.close()
            input_writer = None
            temp_input_path.replace(input_path)
        else:
            write_parquet_atomic(pd.DataFrame(columns=PHOBERT_INPUT_COLUMNS), input_path, index=False)
    finally:
        if input_writer is not None:
            input_writer.close()
        if temp_input_path is not None and temp_input_path.exists():
            temp_input_path.unlink(missing_ok=True)

    input_manifest = {
        "input_cache_version": PHOBERT_INPUT_CACHE_VERSION,
        "source_signature": source_signature,
        "input_rows": int(input_rows),
        "tagged_unique_article_count": int(len(tagged_article_ids)),
        "updated_at_utc": pd.Timestamp.utcnow().isoformat(),
    }
    _write_phobert_input_manifest(config, input_manifest)
    print(
        f"PhoBERT input cache ready: input_rows={input_rows} -> {input_path}",
        flush=True,
    )
    return input_manifest


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
                "phobert_article_count_1d": state["article_count"],
                "phobert_sentiment_score_sum": state["sentiment_score_sum"],
                "phobert_sentiment_conf_weighted_sum": state["sentiment_conf_weighted_sum"],
                "phobert_prob_pos_mean": state["prob_pos_sum"] / state["article_count"],
                "phobert_prob_neu_mean": state["prob_neu_sum"] / state["article_count"],
                "phobert_prob_neg_mean": state["prob_neg_sum"] / state["article_count"],
                "phobert_pos_share": state["pos_count"] / state["article_count"],
                "phobert_neu_share": state["neu_count"] / state["article_count"],
                "phobert_neg_share": state["neg_count"] / state["article_count"],
                "phobert_sentiment_score_mean": state["sentiment_score_sum"] / state["article_count"],
                "phobert_sentiment_conf_weighted_mean": state["sentiment_conf_weighted_sum"] / state["article_count"],
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
    for ticker_index, (ticker, group) in enumerate(ticker_groups, start=1):
        group = group.sort_values("date").reset_index(drop=True)
        date_index = pd.date_range(group["date"].min(), group["date"].max(), freq="D")
        group = group.set_index("date").reindex(date_index)
        group["ticker"] = ticker
        fill_columns = [column for column in group.columns if column != "ticker"]
        for column in fill_columns:
            group[column] = pd.to_numeric(group[column], errors="coerce").fillna(0.0)
        group["phobert_article_count_5d"] = (
            group["phobert_article_count_1d"].rolling(window=5, min_periods=1).sum()
        )
        group["phobert_article_count_30d"] = (
            group["phobert_article_count_1d"].rolling(window=30, min_periods=1).sum()
        )
        group["phobert_sentiment_5d"] = (
            group["phobert_sentiment_conf_weighted_mean"].rolling(window=5, min_periods=1).sum()
        )
        group["phobert_sentiment_30d"] = (
            group["phobert_sentiment_conf_weighted_mean"].rolling(window=30, min_periods=1).sum()
        )
        group = group.reset_index().rename(columns={"index": "date"})
        frames.append(group[["ticker", "date", *config.phobert_daily_columns()]])
        if log_progress and (
            ticker_index == 1
            or ticker_index % progress_interval == 0
            or ticker_index == total_tickers
        ):
            print(
                f"PhoBERT daily aggregation progress: processed {ticker_index}/{total_tickers} tickers",
                flush=True,
            )
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out.sort_values(["ticker", "date"]).reset_index(drop=True)


def _finalize_phobert_from_checkpoints(
    *,
    config: NewsFeaturesConfig,
    checkpoint_manifest: dict[str, object],
) -> tuple[pd.DataFrame, dict[str, object]]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("PhoBERT checkpoint finalization requires pyarrow.") from exc

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
            ("phobert_model_id", pa.string()),
            ("phobert_input_text_length", pa.int64()),
            ("phobert_segmented_text_length", pa.int64()),
            ("phobert_predicted_label", pa.string()),
            ("phobert_confidence", pa.float64()),
            ("phobert_prob_neg", pa.float64()),
            ("phobert_prob_neu", pa.float64()),
            ("phobert_prob_pos", pa.float64()),
            ("phobert_sentiment_score", pa.float64()),
            ("phobert_sentiment_conf_weighted", pa.float64()),
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
            dir=config.phobert_article_sentiment_path().parent,
            suffix=".parquet",
            delete=False,
        ) as handle:
            temp_article_path = Path(handle.name)

        for batch_index, (batch_key, batch_meta) in enumerate(batch_items, start=1):
            shard_path_value = batch_meta.get("shard_path")
            if not shard_path_value or int(batch_meta.get("article_rows", 0)) == 0:
                if batch_index == 1 or batch_index % progress_interval == 0 or batch_index == total_batches:
                    print(
                        f"PhoBERT finalize shard {batch_index}/{total_batches}; "
                        f"article_rows={checkpoint_manifest.get('article_score_rows', 0)}",
                        flush=True,
                    )
                continue
            shard_path = Path(str(shard_path_value))
            if not shard_path.exists():
                raise FileNotFoundError(f"Missing PhoBERT checkpoint shard: {shard_path}")
            shard_df = pd.read_parquet(shard_path)
            if not shard_df.empty:
                table = pa.Table.from_pandas(shard_df[ARTICLE_COLUMNS], preserve_index=False, schema=article_schema)
                if writer is None:
                    writer = pq.ParquetWriter(temp_article_path, schema=table.schema)
                writer.write_table(table)

                grouped = (
                    shard_df.assign(
                        _is_pos=(shard_df["phobert_predicted_label"] == "POS").astype(float),
                        _is_neu=(shard_df["phobert_predicted_label"] == "NEU").astype(float),
                        _is_neg=(shard_df["phobert_predicted_label"] == "NEG").astype(float),
                    )
                    .groupby(["ticker", "date"], as_index=False)
                    .agg(
                        article_count=("article_id", "size"),
                        sentiment_score_sum=("phobert_sentiment_score", "sum"),
                        sentiment_conf_weighted_sum=("phobert_sentiment_conf_weighted", "sum"),
                        prob_pos_sum=("phobert_prob_pos", "sum"),
                        prob_neu_sum=("phobert_prob_neu", "sum"),
                        prob_neg_sum=("phobert_prob_neg", "sum"),
                        pos_count=("_is_pos", "sum"),
                        neu_count=("_is_neu", "sum"),
                        neg_count=("_is_neg", "sum"),
                    )
                )
                for row in grouped.to_dict(orient="records"):
                    key = (str(row["ticker"]), str(row["date"]))
                    state = daily_state.setdefault(
                        key,
                        {
                            "article_count": 0.0,
                            "sentiment_score_sum": 0.0,
                            "sentiment_conf_weighted_sum": 0.0,
                            "prob_pos_sum": 0.0,
                            "prob_neu_sum": 0.0,
                            "prob_neg_sum": 0.0,
                            "pos_count": 0.0,
                            "neu_count": 0.0,
                            "neg_count": 0.0,
                        },
                    )
                    for field in state:
                        state[field] += float(row[field])
            if batch_index == 1 or batch_index % progress_interval == 0 or batch_index == total_batches:
                print(
                    f"PhoBERT finalize shard {batch_index}/{total_batches}",
                    flush=True,
                )

        if writer is not None and temp_article_path is not None:
            writer.close()
            writer = None
            temp_article_path.replace(config.phobert_article_sentiment_path())
        else:
            write_parquet_atomic(_empty_article_dataframe(), config.phobert_article_sentiment_path(), index=False)
    finally:
        if writer is not None:
            writer.close()
        if temp_article_path is not None and temp_article_path.exists():
            temp_article_path.unlink(missing_ok=True)

    daily = _daily_feature_frame_from_state(daily_state, config, log_progress=True)
    write_parquet_atomic(daily, config.phobert_ticker_day_sentiment_path(), index=False)

    checkpoint_manifest["status"] = "complete"
    checkpoint_manifest["daily_feature_rows"] = int(len(daily))
    checkpoint_manifest["completed_at_utc"] = pd.Timestamp.utcnow().isoformat()
    _write_phobert_checkpoint_manifest(config, checkpoint_manifest)

    for batch_meta in completed_batches.values():
        shard_path_value = batch_meta.get("shard_path")
        if shard_path_value:
            Path(str(shard_path_value)).unlink(missing_ok=True)

    metadata = {
        "phobert_model_id": checkpoint_manifest.get("phobert_model_id", config.phobert_model_name),
        "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
        "daily_feature_rows": int(len(daily)),
        "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
        "checkpoint_status": str(checkpoint_manifest.get("status", "unknown")),
        "checkpoint_completed_batches": int(checkpoint_manifest.get("completed_batch_count", 0)),
        "checkpoint_total_batches": int(checkpoint_manifest.get("total_batches", 0)),
    }
    return daily, metadata


def build_phobert_sentiment_exports(
    config: Optional[NewsFeaturesConfig] = None,
    scorer: Optional[PhoBertScoreFn] = None,
    scorer_metadata: Optional[dict[str, object]] = None,
    checkpoint_batch_limit: Optional[int] = None,
) -> pd.DataFrame:
    config = config or get_default_config()
    config.ensure_directories()
    overall_start = perf_counter()
    load_start = perf_counter()
    phobert_input_rows = 0
    if not config.normalized_path().exists() or not config.tagged_path().exists():
        article_rows = _empty_article_dataframe()
        daily = _empty_daily_dataframe(config)
        metadata = {
            "phobert_model_id": config.phobert_model_name,
            "article_score_rows": 0,
            "daily_feature_rows": 0,
            "unique_article_count": 0,
        }
        load_elapsed = perf_counter() - load_start
        write_start = perf_counter()
        write_parquet_atomic(article_rows, config.phobert_article_sentiment_path(), index=False)
        write_parquet_atomic(daily, config.phobert_ticker_day_sentiment_path(), index=False)
        write_elapsed = perf_counter() - write_start
        build_elapsed = 0.0
    else:
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise ImportError("Streaming PhoBERT export requires pyarrow.") from exc

        normalized_file = pq.ParquetFile(config.normalized_path())
        normalized_rows = normalized_file.metadata.num_rows
        tagged = pd.read_parquet(config.tagged_path())
        tagged["article_id"] = tagged["article_id"].astype(str)
        tagged_rows = len(tagged)
        load_elapsed = perf_counter() - load_start
        print(
            f"Loaded normalized_rows={normalized_rows} and tagged_rows={tagged_rows} for PhoBERT in {load_elapsed:.1f}s",
            flush=True,
        )
        input_manifest = _prepare_phobert_input_articles_cache(
            config=config,
            normalized_file=normalized_file,
            normalized_rows=int(normalized_rows),
            tagged=tagged,
        )
        input_file = pq.ParquetFile(config.phobert_input_articles_path())
        input_rows = int(input_file.metadata.num_rows)
        phobert_input_rows = int(input_rows)
        input_source_signature = dict(input_manifest.get("source_signature") or {})
        print(
            f"PhoBERT scoring universe: input_rows={input_rows} from {config.phobert_input_articles_path()}",
            flush=True,
        )
        if input_rows == 0:
            _clear_phobert_checkpoint_state(config)
            daily = _empty_daily_dataframe(config)
            metadata = {
                "phobert_model_id": config.phobert_model_name,
                "phobert_input_rows": 0,
                "article_score_rows": 0,
                "daily_feature_rows": 0,
                "unique_article_count": 0,
                "checkpoint_status": "complete",
                "checkpoint_completed_batches": 0,
                "checkpoint_total_batches": 0,
            }
            build_elapsed = 0.0
            write_start = perf_counter()
            write_parquet_atomic(_empty_article_dataframe(), config.phobert_article_sentiment_path(), index=False)
            write_parquet_atomic(daily, config.phobert_ticker_day_sentiment_path(), index=False)
            write_elapsed = perf_counter() - write_start
        else:
            run_signature = _phobert_run_signature(
                config,
                input_rows=input_rows,
                input_source_signature=input_source_signature,
            )
            checkpoint_manifest = _load_phobert_checkpoint_manifest(config)
            if checkpoint_manifest and checkpoint_manifest.get("run_signature") != run_signature:
                print("PhoBERT checkpoint signature changed; clearing old checkpoint shards", flush=True)
                _clear_phobert_checkpoint_state(config)
                checkpoint_manifest = {}

            if (
                checkpoint_manifest.get("status") == "complete"
                and checkpoint_manifest.get("run_signature") == run_signature
                and config.phobert_article_sentiment_path().exists()
                and config.phobert_ticker_day_sentiment_path().exists()
            ):
                print("PhoBERT checkpoint already complete; reusing published datasets", flush=True)
                daily = pd.read_parquet(config.phobert_ticker_day_sentiment_path())
                metadata = {
                    "phobert_model_id": checkpoint_manifest.get("phobert_model_id", config.phobert_model_name),
                    "phobert_input_rows": int(input_rows),
                    "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
                    "daily_feature_rows": int(len(daily)),
                    "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
                    "checkpoint_status": "complete",
                    "checkpoint_completed_batches": int(checkpoint_manifest.get("completed_batch_count", 0)),
                    "checkpoint_total_batches": int(checkpoint_manifest.get("total_batches", 0)),
                }
                build_elapsed = 0.0
                write_elapsed = 0.0
            else:
                total_batches = max((int(input_rows) + int(config.phobert_checkpoint_rows) - 1) // int(config.phobert_checkpoint_rows), 1)
                if not checkpoint_manifest:
                    checkpoint_manifest = {
                        "checkpoint_version": PHOBERT_CHECKPOINT_VERSION,
                        "status": "in_progress",
                        "run_signature": run_signature,
                        "phobert_model_id": config.phobert_model_name,
                        "phobert_input_rows": int(input_rows),
                        "normalized_rows": int(normalized_rows),
                        "tagged_rows": int(tagged_rows),
                        "total_batches": int(total_batches),
                        "completed_batch_count": 0,
                        "article_score_rows": 0,
                        "unique_article_count": 0,
                        "completed_batches": {},
                        "created_at_utc": pd.Timestamp.utcnow().isoformat(),
                    }
                    _write_phobert_checkpoint_manifest(config, checkpoint_manifest)
                    print(
                        f"PhoBERT checkpoint start: total_batches={total_batches}, "
                        f"checkpoint_rows={config.phobert_checkpoint_rows}",
                        flush=True,
                    )
                else:
                    print(
                        "PhoBERT checkpoint resume: "
                        f"completed_batches={int(checkpoint_manifest.get('completed_batch_count', 0))}/{total_batches}, "
                        f"article_rows={int(checkpoint_manifest.get('article_score_rows', 0))}, "
                        f"unique_articles={int(checkpoint_manifest.get('unique_article_count', 0))}",
                        flush=True,
                    )

                build_start = perf_counter()
                metadata = dict(scorer_metadata or {})
                if scorer is None:
                    scorer, runtime_metadata = _load_phobert_scorer(config, log_progress=True)
                    metadata.update(runtime_metadata)
                else:
                    metadata.setdefault("phobert_model_id", config.phobert_model_name)

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
                        batch_size=int(config.phobert_checkpoint_rows),
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
                                    f"PhoBERT input scan {processed_input_rows}/{input_rows}; "
                                    f"unique_articles={unique_article_count}, article_rows={article_score_rows} "
                                    f"(resume skip)",
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
                        normalized_batch["phobert_input_text"] = (
                            text_parts[0].astype(str).str.strip()
                            + " "
                            + text_parts[1].astype(str).str.strip()
                            + " "
                            + text_parts[2].astype(str).str.strip()
                        ).str.replace(r"\s+", " ", regex=True).str.strip()
                        normalized_batch = normalized_batch[normalized_batch["phobert_input_text"].str.len() > 0].copy()
                        if not normalized_batch.empty:
                            # Group similar-length texts together to reduce tokenizer padding waste.
                            normalized_batch = (
                                normalized_batch.assign(
                                    _phobert_sort_len=normalized_batch["phobert_input_text"].str.len()
                                )
                                .sort_values("_phobert_sort_len", kind="mergesort")
                                .drop(columns="_phobert_sort_len")
                                .reset_index(drop=True)
                            )

                    if not normalized_batch.empty:
                        batch_unique_articles = int(len(normalized_batch))
                        score_rows = scorer(normalized_batch["phobert_input_text"].tolist())
                        score_frame = pd.DataFrame(score_rows)
                        required_score_columns = [
                            "phobert_input_text_length",
                            "phobert_segmented_text_length",
                            "phobert_predicted_label",
                            "phobert_confidence",
                            "phobert_prob_neg",
                            "phobert_prob_neu",
                            "phobert_prob_pos",
                        ]
                        for column in required_score_columns:
                            if column not in score_frame.columns:
                                raise ValueError(f"PhoBERT scorer is missing required column: {column}")

                        article_scores = normalized_batch[["article_id", "published_at"]].copy()
                        article_scores["phobert_model_id"] = str(metadata.get("phobert_model_id", config.phobert_model_name))
                        article_scores[required_score_columns] = score_frame[required_score_columns]
                        article_scores["phobert_predicted_label"] = article_scores["phobert_predicted_label"].map(_canonical_label)
                        article_scores["phobert_sentiment_score"] = article_scores["phobert_predicted_label"].map(_label_score)
                        article_scores["phobert_sentiment_conf_weighted"] = (
                            article_scores["phobert_sentiment_score"] * article_scores["phobert_confidence"].astype(float)
                        )

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
                            shard_path = config.phobert_checkpoint_shard_path(batch_index)
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
                    checkpoint_manifest.update(
                        {
                            "status": "in_progress",
                            "run_signature": run_signature,
                            "phobert_model_id": metadata.get("phobert_model_id", config.phobert_model_name),
                            "completed_batches": completed_batches,
                            "completed_batch_count": int(len(completed_batches)),
                            "article_score_rows": int(article_score_rows),
                            "unique_article_count": int(unique_article_count),
                            "last_completed_batch": int(batch_index),
                            "last_updated_utc": pd.Timestamp.utcnow().isoformat(),
                        }
                    )
                    _write_phobert_checkpoint_manifest(config, checkpoint_manifest)
                    processed_new_batches += 1

                    if (
                        processed_input_rows == batch_row_count
                        or processed_input_rows % progress_interval == 0
                        or processed_input_rows >= input_rows
                    ):
                        print(
                            f"PhoBERT input scan {processed_input_rows}/{input_rows}; "
                            f"unique_articles={unique_article_count}, article_rows={article_score_rows}",
                            flush=True,
                        )

                    if checkpoint_batch_limit is not None and processed_new_batches >= int(checkpoint_batch_limit):
                        print(
                            f"PhoBERT checkpoint test stop after {processed_new_batches} new batches",
                            flush=True,
                        )
                        break

                if int(checkpoint_manifest.get("completed_batch_count", 0)) == int(checkpoint_manifest.get("total_batches", total_batches)):
                    print("PhoBERT checkpoint scoring complete. Finalizing published datasets...", flush=True)
                    daily, finalized_metadata = _finalize_phobert_from_checkpoints(
                        config=config,
                        checkpoint_manifest=checkpoint_manifest,
                    )
                    metadata.update(finalized_metadata)
                else:
                    daily = _empty_daily_dataframe(config)
                    metadata.update(
                        {
                            "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
                            "daily_feature_rows": 0,
                            "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
                            "checkpoint_status": "in_progress",
                            "checkpoint_completed_batches": int(checkpoint_manifest.get("completed_batch_count", 0)),
                            "checkpoint_total_batches": int(checkpoint_manifest.get("total_batches", total_batches)),
                        }
                    )

                build_elapsed = perf_counter() - build_start
                write_elapsed = 0.0

    metadata_path = config.datasets_dir / "phobert_metadata.json"
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
        phobert_model_id=str(metadata.get("phobert_model_id", config.phobert_model_name)),
        phobert_article_sentiment_rows=int(metadata.get("article_score_rows", 0)),
        phobert_ticker_day_sentiment_rows=int(len(daily)),
        phobert_checkpoint_status=str(metadata.get("checkpoint_status", "complete" if len(daily) > 0 else "in_progress")),
        phobert_checkpoint_completed_batches=int(metadata.get("checkpoint_completed_batches", 0)),
        phobert_checkpoint_total_batches=int(metadata.get("checkpoint_total_batches", 0)),
        phobert_input_articles_rows=int(metadata.get("phobert_input_rows", 0)),
        phobert_article_sentiment_dataset_path=describe_path(config.phobert_article_sentiment_path(), config=config),
        phobert_ticker_day_sentiment_dataset_path=describe_path(
            config.phobert_ticker_day_sentiment_path(), config=config
        ),
        phobert_input_articles_dataset_path=describe_path(config.phobert_input_articles_path(), config=config),
    )
    overall_elapsed = perf_counter() - overall_start
    print(
        f"Timing summary: load={load_elapsed:.1f}s, build={build_elapsed:.1f}s, "
        f"write={write_elapsed:.1f}s, total={overall_elapsed:.1f}s",
        flush=True,
    )
    print(
        f"Built {int(metadata.get('article_score_rows', 0))} PhoBERT article rows and {len(daily)} ticker-day rows -> "
        f"{config.phobert_ticker_day_sentiment_path()}",
        flush=True,
    )
    return daily


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Build whole-article PhoBERT sentiment features.")


def main() -> None:
    build_arg_parser().parse_args()
    build_phobert_sentiment_exports()


if __name__ == "__main__":
    main()
