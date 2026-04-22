"""Build whole-article PhoBERT sentiment datasets from tagged news articles."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from itertools import islice
from time import perf_counter
from typing import Callable, Optional

import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.io_utils import describe_path, update_manifest, write_parquet_atomic


PhoBertScoreFn = Callable[[list[str]], list[dict[str, object]]]

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


def _load_phobert_scorer(config: NewsFeaturesConfig) -> tuple[PhoBertScoreFn, dict[str, object]]:
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

    tokenizer = AutoTokenizer.from_pretrained(config.phobert_model_name, use_fast=False)
    model = AutoModelForSequenceClassification.from_pretrained(config.phobert_model_name, dtype=dtype)
    model.to(device)
    model.eval()
    id2label = _resolve_id2label(config.phobert_model_name, model)

    def _score(texts: list[str]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for batch in _batched(texts, config.phobert_batch_size):
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
        score_fn, runtime_metadata = _load_phobert_scorer(config)
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


def build_phobert_sentiment_exports(
    config: Optional[NewsFeaturesConfig] = None,
    scorer: Optional[PhoBertScoreFn] = None,
    scorer_metadata: Optional[dict[str, object]] = None,
) -> pd.DataFrame:
    config = config or get_default_config()
    overall_start = perf_counter()
    load_start = perf_counter()
    normalized = pd.read_parquet(config.normalized_path()) if config.normalized_path().exists() else pd.DataFrame()
    tagged = pd.read_parquet(config.tagged_path()) if config.tagged_path().exists() else pd.DataFrame()
    load_elapsed = perf_counter() - load_start
    print(
        f"Loaded normalized_rows={len(normalized)} and tagged_rows={len(tagged)} for PhoBERT in {load_elapsed:.1f}s",
        flush=True,
    )
    build_start = perf_counter()
    article_rows, metadata = build_phobert_article_sentiment_dataframe(
        normalized_df=normalized,
        tagged_df=tagged,
        config=config,
        scorer=scorer,
        scorer_metadata=scorer_metadata,
        log_progress=True,
    )
    daily = build_phobert_daily_sentiment_dataframe(article_rows, config=config, log_progress=True)
    build_elapsed = perf_counter() - build_start
    print(f"PhoBERT build completed in {build_elapsed:.1f}s. Writing parquet...", flush=True)

    write_start = perf_counter()
    write_parquet_atomic(article_rows, config.phobert_article_sentiment_path(), index=False)
    write_parquet_atomic(daily, config.phobert_ticker_day_sentiment_path(), index=False)
    write_elapsed = perf_counter() - write_start

    metadata_path = config.datasets_dir / "phobert_metadata.json"
    metadata.update(
        {
            "article_score_rows": int(len(article_rows)),
            "daily_feature_rows": int(len(daily)),
        }
    )
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_manifest(
        config=config,
        phobert_model_id=str(metadata.get("phobert_model_id", config.phobert_model_name)),
        phobert_article_sentiment_rows=int(len(article_rows)),
        phobert_ticker_day_sentiment_rows=int(len(daily)),
        phobert_article_sentiment_dataset_path=describe_path(config.phobert_article_sentiment_path(), config=config),
        phobert_ticker_day_sentiment_dataset_path=describe_path(
            config.phobert_ticker_day_sentiment_path(), config=config
        ),
    )
    overall_elapsed = perf_counter() - overall_start
    print(
        f"Timing summary: load={load_elapsed:.1f}s, build={build_elapsed:.1f}s, "
        f"write={write_elapsed:.1f}s, total={overall_elapsed:.1f}s",
        flush=True,
    )
    print(
        f"Built {len(article_rows)} PhoBERT article rows and {len(daily)} ticker-day rows -> "
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
