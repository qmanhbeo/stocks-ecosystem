"""Build additive guarded local Ollama news datasets from tagged articles only.

Preferred operator alias: `build_ollama_probe_features.py`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from time import perf_counter
from typing import Callable, Optional
import urllib.request

import pandas as pd

from data_tools import extract_llm_news_features_legacy as legacy
from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.io_utils import describe_path, update_manifest, write_parquet_atomic


OllamaGuardedRawResponseFn = Callable[[dict[str, object]], str]

OLLAMA_GUARDED_INPUT_COLUMNS = [
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
    "local_model_name",
    "ollama_guarded_input_text_length",
    "ollama_guarded_confidence",
    "ollama_guarded_is_forward_looking",
    "ollama_guarded_is_rumor",
    "local_parse_ok",
    "local_abstained",
    "local_error",
]

OLLAMA_GUARDED_INPUT_CACHE_VERSION = 1
OLLAMA_GUARDED_CHECKPOINT_VERSION = 1
OLLAMA_GUARDED_PROMPT_VERSION = 2


def _empty_article_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=ARTICLE_COLUMNS)


def _empty_daily_dataframe(config: NewsFeaturesConfig) -> pd.DataFrame:
    return pd.DataFrame(columns=["ticker", "date", *config.ollama_guarded_daily_columns()])


def _nullable_schema(*types: str) -> dict[str, object]:
    return {"type": list(types) + ["null"]}


def _ollama_guarded_json_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "confidence": _nullable_schema("integer"),
            "is_forward_looking": _nullable_schema("boolean"),
            "is_rumor": _nullable_schema("boolean"),
        },
        "required": [
            "id",
            "confidence",
            "is_forward_looking",
            "is_rumor",
        ],
        "additionalProperties": True,
    }


def _extract_chat_content(body: dict[str, object]) -> str:
    message = body.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
        return "".join(parts)
    return ""


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _compose_input_text(row: pd.Series, max_body_chars: int) -> str:
    title = _clean_text(row.get("clean_title", ""))
    summary = _clean_text(row.get("clean_summary", ""))
    body = _clean_text(row.get("clean_body_text", ""))
    if max_body_chars > 0 and len(body) > max_body_chars:
        body = body[:max_body_chars].rstrip()
    parts = [part for part in [title, summary, body] if part]
    return " ".join(parts).strip()


def _article_payload_from_row(row: pd.Series, config: NewsFeaturesConfig) -> dict[str, object]:
    input_text = _compose_input_text(row, config.ollama_guarded_max_body_chars)
    return {
        "article_id": str(row.get("article_id", "") or ""),
        "published_at": row.get("published_at"),
        "clean_title": _clean_text(row.get("clean_title", "")),
        "clean_summary": _clean_text(row.get("clean_summary", "")),
        "clean_body_text": _clean_text(row.get("clean_body_text", "")),
        "input_text": input_text,
        "input_text_length": int(len(input_text)),
    }


def _build_ollama_guarded_prompt(article: dict[str, object]) -> str:
    return "\n".join(
        [
            "You are reading one Vietnamese CafeF financial news article.",
            "Score only three coarse local fields from the article text itself.",
            "Do not extract or invent tickers. Ticker linkage is handled separately and is not part of this task.",
            "Do not score sentiment here. Sentiment is handled by a separate PhoBERT lane.",
            "If a field is unclear, contradictory, or unsupported by the article, return null.",
            "Return one JSON object only. No markdown. No prose. No reasoning.",
            "",
            "Output fields:",
            "- id",
            "- confidence: 0 | 1 | 2 | null",
            "- is_forward_looking: true | false | null",
            "- is_rumor: true | false | null",
            "",
            f"Article id: {article['article_id']}",
            f"Title: {article['clean_title']}",
            f"Summary: {article['clean_summary']}",
            f"Body: {article['clean_body_text']}",
        ]
    )


def _call_ollama_chat(prompt: str, config: NewsFeaturesConfig) -> str:
    payload: dict[str, object] = {
        "model": config.ollama_guarded_model_name,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "keep_alive": config.ollama_guarded_keep_alive,
        "options": {
            "temperature": 0,
            "num_predict": int(config.ollama_guarded_num_predict),
            "num_ctx": int(config.ollama_guarded_num_ctx),
        },
    }
    if config.ollama_guarded_use_schema:
        payload["format"] = _ollama_guarded_json_schema()
    request = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=int(config.ollama_guarded_timeout_seconds)) as response:
        body = json.loads(response.read().decode("utf-8", errors="replace"))
    return _extract_chat_content(body)


def _stop_ollama_model(model_name: str) -> None:
    try:
        subprocess.run(
            ["ollama", "stop", model_name],
            capture_output=True,
            check=False,
            text=True,
        )
    except Exception:
        return


def _blank_inference_result(
    *,
    config: NewsFeaturesConfig,
    input_text_length: int,
    error: Optional[str],
    parse_ok: bool = False,
) -> dict[str, object]:
    return {
        "local_model_name": config.ollama_guarded_model_name,
        "ollama_guarded_input_text_length": int(input_text_length),
        "ollama_guarded_confidence": None,
        "ollama_guarded_is_forward_looking": None,
        "ollama_guarded_is_rumor": None,
        "local_parse_ok": bool(parse_ok),
        "local_abstained": True,
        "local_error": error,
    }


def _normalize_guarded_response(
    *,
    article_id: str,
    raw_text: str,
    config: NewsFeaturesConfig,
    input_text_length: int,
) -> dict[str, object]:
    parsed = legacy._extract_json_array(str(raw_text or "")) or []
    if not parsed:
        return _blank_inference_result(
            config=config,
            input_text_length=input_text_length,
            error="json_parse_fail",
        )

    raw_obj: Optional[dict[str, object]] = None
    for item in parsed:
        if isinstance(item, dict) and str(item.get("id", "") or "").strip() == article_id:
            raw_obj = item
            break
    if raw_obj is None:
        first = parsed[0]
        raw_obj = first if isinstance(first, dict) else None
    if raw_obj is None:
        return _blank_inference_result(
            config=config,
            input_text_length=input_text_length,
            error="json_parse_fail",
        )

    normalized = legacy._normalize_record(raw_obj, article_id)
    confidence = normalized.get("confidence")
    is_forward_looking = normalized.get("is_forward_looking")
    is_rumor = normalized.get("is_rumor")
    has_signal = any(value is not None for value in [confidence, is_forward_looking, is_rumor])
    return {
        "local_model_name": config.ollama_guarded_model_name,
        "ollama_guarded_input_text_length": int(input_text_length),
        "ollama_guarded_confidence": float(confidence) if confidence is not None else None,
        "ollama_guarded_is_forward_looking": is_forward_looking,
        "ollama_guarded_is_rumor": is_rumor,
        "local_parse_ok": True,
        "local_abstained": not has_signal,
        "local_error": None,
    }


def _infer_single_article(
    article: dict[str, object],
    *,
    config: NewsFeaturesConfig,
    raw_response_fn: Optional[OllamaGuardedRawResponseFn] = None,
) -> dict[str, object]:
    input_text_length = int(article.get("input_text_length", 0) or 0)
    if input_text_length <= 0:
        return _blank_inference_result(
            config=config,
            input_text_length=0,
            error="empty_article_text",
        )

    try:
        if raw_response_fn is not None:
            raw_text = raw_response_fn(article)
        else:
            prompt = _build_ollama_guarded_prompt(article)
            raw_text = _call_ollama_chat(prompt, config)
        return _normalize_guarded_response(
            article_id=str(article.get("article_id", "") or ""),
            raw_text=str(raw_text or ""),
            config=config,
            input_text_length=input_text_length,
        )
    except Exception:
        return _blank_inference_result(
            config=config,
            input_text_length=input_text_length,
            error="ollama_call_error",
        )
    finally:
        if raw_response_fn is None:
            _stop_ollama_model(config.ollama_guarded_model_name)


def _infer_article_frame(
    article_frame: pd.DataFrame,
    *,
    config: NewsFeaturesConfig,
    raw_response_fn: Optional[OllamaGuardedRawResponseFn] = None,
    log_progress: bool = False,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    total_articles = int(len(article_frame))
    progress_interval = 1 if total_articles <= 10 else 100
    for article_index, article_row in enumerate(article_frame.to_dict(orient="records"), start=1):
        article = _article_payload_from_row(pd.Series(article_row), config)
        result = _infer_single_article(article, config=config, raw_response_fn=raw_response_fn)
        rows.append(
            {
                "article_id": str(article["article_id"]),
                "published_at": article.get("published_at"),
                **result,
            }
        )
        if log_progress and (
            article_index == 1
            or article_index % progress_interval == 0
            or article_index == total_articles
        ):
            print(
                f"Ollama guarded scoring {article_index}/{total_articles}; "
                f"abstained_rows={sum(1 for row in rows if row['local_abstained'])}",
                flush=True,
            )
    return pd.DataFrame(rows)


def _prepare_direct_article_inputs(
    normalized_df: pd.DataFrame,
    tagged_df: pd.DataFrame,
    *,
    config: NewsFeaturesConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    normalized = normalized_df.copy()
    for column, default_value in (
        ("published_at", None),
        ("clean_title", ""),
        ("clean_summary", ""),
        ("clean_body_text", ""),
    ):
        if column not in normalized.columns:
            normalized[column] = default_value

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
                "published_at",
                "clean_title",
                "clean_summary",
                "clean_body_text",
            ]
        ]
        .drop_duplicates(subset=["article_id"])
        .reset_index(drop=True)
    )
    return merged, unique_articles


def build_ollama_guarded_article_feature_dataframe(
    normalized_df: pd.DataFrame,
    tagged_df: pd.DataFrame,
    config: Optional[NewsFeaturesConfig] = None,
    raw_response_fn: Optional[OllamaGuardedRawResponseFn] = None,
    log_progress: bool = False,
) -> tuple[pd.DataFrame, dict[str, object]]:
    config = config or get_default_config()
    if normalized_df.empty or tagged_df.empty:
        metadata = {
            "local_model_name": config.ollama_guarded_model_name,
            "article_score_rows": 0,
            "unique_article_count": 0,
        }
        return _empty_article_dataframe(), metadata

    merged, unique_articles = _prepare_direct_article_inputs(normalized_df, tagged_df, config=config)
    if unique_articles.empty:
        metadata = {
            "local_model_name": config.ollama_guarded_model_name,
            "article_score_rows": 0,
            "unique_article_count": 0,
        }
        return _empty_article_dataframe(), metadata

    if log_progress:
        print(
            f"Ollama guarded stage 1/2: scoring {len(unique_articles)} tagged unique articles",
            flush=True,
        )
    article_scores = _infer_article_frame(
        unique_articles,
        config=config,
        raw_response_fn=raw_response_fn,
        log_progress=log_progress,
    )
    if article_scores.empty:
        metadata = {
            "local_model_name": config.ollama_guarded_model_name,
            "article_score_rows": 0,
            "unique_article_count": int(len(unique_articles)),
        }
        return _empty_article_dataframe(), metadata

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
        on="article_id",
        how="inner",
        validate="many_to_one",
    )
    article_rows = article_rows[ARTICLE_COLUMNS].sort_values(["ticker", "date", "article_id"]).reset_index(drop=True)
    metadata = {
        "local_model_name": config.ollama_guarded_model_name,
        "article_score_rows": int(len(article_rows)),
        "unique_article_count": int(len(unique_articles)),
    }
    return article_rows, metadata


def build_ollama_guarded_daily_feature_dataframe(
    article_df: pd.DataFrame,
    config: Optional[NewsFeaturesConfig] = None,
    *,
    log_progress: bool = False,
) -> pd.DataFrame:
    config = config or get_default_config()
    if article_df.empty:
        return _empty_daily_dataframe(config)

    working = article_df.copy()
    forward_flags = working["ollama_guarded_is_forward_looking"].astype("boolean")
    rumor_flags = working["ollama_guarded_is_rumor"].astype("boolean")
    working["_confidence_valid"] = working["ollama_guarded_confidence"].notna().astype(float)
    working["_forward_valid"] = forward_flags.notna().astype(float)
    working["_forward_true"] = forward_flags.fillna(False).astype(float)
    working["_rumor_valid"] = rumor_flags.notna().astype(float)
    working["_rumor_true"] = rumor_flags.fillna(False).astype(float)
    working["_abstained"] = working["local_abstained"].astype(float)
    working["_parse_fail"] = (~working["local_parse_ok"]).astype(float)

    if log_progress:
        print(
            f"Ollama guarded daily aggregation: grouping {len(working)} article-ticker rows",
            flush=True,
        )
    daily = (
        working.groupby(["ticker", "date"], as_index=False)
        .agg(
            ollama_guarded_article_count_1d=("article_id", "size"),
            _confidence_sum=("ollama_guarded_confidence", "sum"),
            _confidence_count=("_confidence_valid", "sum"),
            _forward_true_sum=("_forward_true", "sum"),
            _forward_valid_count=("_forward_valid", "sum"),
            _rumor_true_sum=("_rumor_true", "sum"),
            _rumor_valid_count=("_rumor_valid", "sum"),
            _abstain_count=("_abstained", "sum"),
            _parse_fail_count=("_parse_fail", "sum"),
        )
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )
    daily["ollama_guarded_confidence_mean"] = daily["_confidence_sum"] / daily["_confidence_count"].replace(
        0.0,
        pd.NA,
    )
    daily["ollama_guarded_forward_looking_share"] = daily["_forward_true_sum"] / daily["_forward_valid_count"].replace(
        0.0,
        pd.NA,
    )
    daily["ollama_guarded_rumor_share"] = daily["_rumor_true_sum"] / daily["_rumor_valid_count"].replace(
        0.0,
        pd.NA,
    )
    daily["ollama_guarded_abstain_share"] = daily["_abstain_count"] / daily["ollama_guarded_article_count_1d"]
    daily["ollama_guarded_parse_fail_share"] = daily["_parse_fail_count"] / daily["ollama_guarded_article_count_1d"]
    daily["date"] = pd.to_datetime(daily["date"])

    frames: list[pd.DataFrame] = []
    ticker_groups = list(daily.groupby("ticker", sort=True))
    total_tickers = len(ticker_groups)
    progress_interval = 1 if total_tickers <= 10 else 10
    value_columns = [
        "ollama_guarded_article_count_1d",
        "ollama_guarded_confidence_mean",
        "ollama_guarded_forward_looking_share",
        "ollama_guarded_rumor_share",
        "ollama_guarded_abstain_share",
        "ollama_guarded_parse_fail_share",
    ]
    for ticker_index, (ticker, group) in enumerate(ticker_groups, start=1):
        group = group.sort_values("date").reset_index(drop=True)
        date_index = pd.date_range(group["date"].min(), group["date"].max(), freq="D")
        group = group.set_index("date").reindex(date_index)
        group["ticker"] = ticker
        for column in value_columns:
            group[column] = pd.to_numeric(group[column], errors="coerce").fillna(0.0)
        group["ollama_guarded_article_count_5d"] = (
            group["ollama_guarded_article_count_1d"].rolling(window=5, min_periods=1).sum()
        )
        group["ollama_guarded_article_count_30d"] = (
            group["ollama_guarded_article_count_1d"].rolling(window=30, min_periods=1).sum()
        )
        group = group.reset_index().rename(columns={"index": "date"})
        frames.append(group[["ticker", "date", *config.ollama_guarded_daily_columns()]])
        if log_progress and (
            ticker_index == 1
            or ticker_index % progress_interval == 0
            or ticker_index == total_tickers
        ):
            print(
                f"Ollama guarded daily aggregation progress: processed {ticker_index}/{total_tickers} tickers",
                flush=True,
            )

    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out.sort_values(["ticker", "date"]).reset_index(drop=True)


def _path_checkpoint_signature(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


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


def _load_json_payload(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_ollama_guarded_input_manifest(config: NewsFeaturesConfig) -> dict[str, object]:
    return _load_json_payload(config.ollama_guarded_input_manifest_path())


def _write_ollama_guarded_input_manifest(config: NewsFeaturesConfig, payload: dict[str, object]) -> None:
    _write_json_atomic(config.ollama_guarded_input_manifest_path(), payload)


def _load_ollama_guarded_checkpoint_manifest(config: NewsFeaturesConfig) -> dict[str, object]:
    return _load_json_payload(config.ollama_guarded_checkpoint_manifest_path())


def _write_ollama_guarded_checkpoint_manifest(config: NewsFeaturesConfig, payload: dict[str, object]) -> None:
    _write_json_atomic(config.ollama_guarded_checkpoint_manifest_path(), payload)


def _clear_ollama_guarded_checkpoint_state(config: NewsFeaturesConfig) -> None:
    checkpoint_dir = config.ollama_guarded_checkpoint_dir()
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    for path in checkpoint_dir.iterdir():
        if path.is_file():
            path.unlink(missing_ok=True)


def _ollama_guarded_input_source_signature(
    config: NewsFeaturesConfig,
    *,
    normalized_rows: int,
    tagged_rows: int,
) -> dict[str, object]:
    return {
        "input_cache_version": OLLAMA_GUARDED_INPUT_CACHE_VERSION,
        "normalized_rows": int(normalized_rows),
        "tagged_rows": int(tagged_rows),
        "normalized_input": _path_checkpoint_signature(config.normalized_path()),
        "tagged_input": _path_checkpoint_signature(config.tagged_path()),
    }


def _ollama_guarded_run_signature(
    config: NewsFeaturesConfig,
    *,
    input_rows: int,
    input_source_signature: dict[str, object],
) -> dict[str, object]:
    return {
        "checkpoint_version": OLLAMA_GUARDED_CHECKPOINT_VERSION,
        "prompt_version": OLLAMA_GUARDED_PROMPT_VERSION,
        "ollama_guarded_model_name": config.ollama_guarded_model_name,
        "ollama_guarded_timeout_seconds": int(config.ollama_guarded_timeout_seconds),
        "ollama_guarded_num_predict": int(config.ollama_guarded_num_predict),
        "ollama_guarded_num_ctx": int(config.ollama_guarded_num_ctx),
        "ollama_guarded_keep_alive": str(config.ollama_guarded_keep_alive),
        "ollama_guarded_use_schema": bool(config.ollama_guarded_use_schema),
        "ollama_guarded_max_body_chars": int(config.ollama_guarded_max_body_chars),
        "ollama_guarded_checkpoint_rows": int(config.ollama_guarded_checkpoint_rows),
        "ollama_guarded_input_rows": int(input_rows),
        "ollama_guarded_input": _path_checkpoint_signature(config.ollama_guarded_input_articles_path()),
        "ollama_guarded_input_source_signature": input_source_signature,
    }


def _prepare_ollama_guarded_input_articles_cache(
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
        raise ImportError("Preparing Ollama guarded input cache requires pyarrow.") from exc

    tagged_article_ids = {str(article_id) for article_id in tagged["article_id"].astype(str).tolist()}
    source_signature = _ollama_guarded_input_source_signature(
        config,
        normalized_rows=int(normalized_rows),
        tagged_rows=int(len(tagged)),
    )
    input_manifest = _load_ollama_guarded_input_manifest(config)
    input_path = config.ollama_guarded_input_articles_path()
    if input_path.exists() and input_manifest.get("source_signature") == source_signature:
        cached_rows = int(input_manifest.get("input_rows", 0))
        print(
            f"Ollama guarded input cache reuse: input_rows={cached_rows}, "
            f"unique_tagged_articles={len(tagged_article_ids)}",
            flush=True,
        )
        return input_manifest

    print(
        f"Ollama guarded input cache rebuild: scanning normalized_rows={normalized_rows} for "
        f"{len(tagged_article_ids)} unique tagged articles",
        flush=True,
    )
    input_schema = pa.schema([(column, pa.string()) for column in OLLAMA_GUARDED_INPUT_COLUMNS])
    writer = None
    temp_input_path: Optional[Path] = None
    input_rows = 0
    scanned_rows = 0
    seen_article_ids: set[str] = set()
    missing_article_ids = set(tagged_article_ids)
    batch_size = max(int(config.ollama_guarded_checkpoint_rows) * 10, 20000)
    progress_interval = 50000
    try:
        with tempfile.NamedTemporaryFile(dir=input_path.parent, suffix=".parquet", delete=False) as handle:
            temp_input_path = Path(handle.name)

        for batch_index, batch in enumerate(
            normalized_file.iter_batches(batch_size=batch_size, columns=OLLAMA_GUARDED_INPUT_COLUMNS),
            start=1,
        ):
            batch_df = batch.to_pandas()
            batch_row_count = int(len(batch_df))
            scanned_rows += batch_row_count
            batch_df["article_id"] = batch_df["article_id"].astype(str)
            batch_df = batch_df[batch_df["article_id"].isin(tagged_article_ids)].copy()
            if not batch_df.empty:
                batch_df = batch_df[~batch_df["article_id"].isin(seen_article_ids)].copy()
                if not batch_df.empty:
                    for column in OLLAMA_GUARDED_INPUT_COLUMNS:
                        batch_df[column] = batch_df[column].where(batch_df[column].notna(), "")
                        batch_df[column] = batch_df[column].astype(str)
                    batch_df = batch_df.drop_duplicates(subset=["article_id"], keep="first").reset_index(drop=True)
                    if not batch_df.empty:
                        table = pa.Table.from_pandas(
                            batch_df[OLLAMA_GUARDED_INPUT_COLUMNS],
                            preserve_index=False,
                            schema=input_schema,
                        )
                        if writer is None:
                            writer = pq.ParquetWriter(temp_input_path, schema=table.schema)
                        writer.write_table(table)
                        written_ids = set(batch_df["article_id"].tolist())
                        seen_article_ids.update(written_ids)
                        missing_article_ids.difference_update(written_ids)
                        input_rows += int(len(batch_df))
            if (
                scanned_rows == batch_row_count
                or scanned_rows % progress_interval == 0
                or scanned_rows >= normalized_rows
            ):
                print(
                    f"Ollama guarded input cache scan {scanned_rows}/{normalized_rows}; "
                    f"matched_input_rows={input_rows}, remaining_missing_articles={len(missing_article_ids)}, "
                    f"batch_index={batch_index}",
                    flush=True,
                )

        if missing_article_ids:
            missing_df = pd.DataFrame(
                [
                    {
                        "article_id": article_id,
                        "published_at": "",
                        "clean_title": "",
                        "clean_summary": "",
                        "clean_body_text": "",
                    }
                    for article_id in sorted(missing_article_ids)
                ],
                columns=OLLAMA_GUARDED_INPUT_COLUMNS,
            )
            table = pa.Table.from_pandas(missing_df, preserve_index=False, schema=input_schema)
            if writer is None:
                writer = pq.ParquetWriter(temp_input_path, schema=table.schema)
            writer.write_table(table)
            input_rows += int(len(missing_df))

        if writer is not None and temp_input_path is not None:
            writer.close()
            writer = None
            temp_input_path.replace(input_path)
        else:
            write_parquet_atomic(pd.DataFrame(columns=OLLAMA_GUARDED_INPUT_COLUMNS), input_path, index=False)
    finally:
        if writer is not None:
            writer.close()
        if temp_input_path is not None and temp_input_path.exists():
            temp_input_path.unlink(missing_ok=True)

    input_manifest = {
        "input_cache_version": OLLAMA_GUARDED_INPUT_CACHE_VERSION,
        "source_signature": source_signature,
        "input_rows": int(input_rows),
        "tagged_unique_article_count": int(len(tagged_article_ids)),
        "missing_normalized_article_count": int(len(missing_article_ids)),
        "updated_at_utc": pd.Timestamp.utcnow().isoformat(),
    }
    _write_ollama_guarded_input_manifest(config, input_manifest)
    print(
        f"Ollama guarded input cache ready: input_rows={input_rows} -> {input_path}",
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
                "ollama_guarded_article_count_1d": state["article_count"],
                "ollama_guarded_confidence_mean": (
                    state["confidence_sum"] / state["confidence_count"]
                    if state["confidence_count"] > 0
                    else float("nan")
                ),
                "ollama_guarded_forward_looking_share": (
                    state["forward_true_sum"] / state["forward_valid_count"]
                    if state["forward_valid_count"] > 0
                    else float("nan")
                ),
                "ollama_guarded_rumor_share": (
                    state["rumor_true_sum"] / state["rumor_valid_count"]
                    if state["rumor_valid_count"] > 0
                    else float("nan")
                ),
                "ollama_guarded_abstain_share": state["abstain_count"] / state["article_count"],
                "ollama_guarded_parse_fail_share": state["parse_fail_count"] / state["article_count"],
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
    fill_columns = [
        "ollama_guarded_article_count_1d",
        "ollama_guarded_confidence_mean",
        "ollama_guarded_forward_looking_share",
        "ollama_guarded_rumor_share",
        "ollama_guarded_abstain_share",
        "ollama_guarded_parse_fail_share",
    ]
    for ticker_index, (ticker, group) in enumerate(ticker_groups, start=1):
        group = group.sort_values("date").reset_index(drop=True)
        date_index = pd.date_range(group["date"].min(), group["date"].max(), freq="D")
        group = group.set_index("date").reindex(date_index)
        group["ticker"] = ticker
        for column in fill_columns:
            group[column] = pd.to_numeric(group[column], errors="coerce").fillna(0.0)
        group["ollama_guarded_article_count_5d"] = (
            group["ollama_guarded_article_count_1d"].rolling(window=5, min_periods=1).sum()
        )
        group["ollama_guarded_article_count_30d"] = (
            group["ollama_guarded_article_count_1d"].rolling(window=30, min_periods=1).sum()
        )
        group = group.reset_index().rename(columns={"index": "date"})
        frames.append(group[["ticker", "date", *config.ollama_guarded_daily_columns()]])
        if log_progress and (
            ticker_index == 1
            or ticker_index % progress_interval == 0
            or ticker_index == total_tickers
        ):
            print(
                f"Ollama guarded daily aggregation progress: processed {ticker_index}/{total_tickers} tickers",
                flush=True,
            )
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out.sort_values(["ticker", "date"]).reset_index(drop=True)


def _finalize_ollama_guarded_from_checkpoints(
    *,
    config: NewsFeaturesConfig,
    checkpoint_manifest: dict[str, object],
) -> tuple[pd.DataFrame, dict[str, object]]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Ollama guarded checkpoint finalization requires pyarrow.") from exc

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
            ("local_model_name", pa.string()),
            ("ollama_guarded_input_text_length", pa.int64()),
            ("ollama_guarded_confidence", pa.float64()),
            ("ollama_guarded_is_forward_looking", pa.bool_()),
            ("ollama_guarded_is_rumor", pa.bool_()),
            ("local_parse_ok", pa.bool_()),
            ("local_abstained", pa.bool_()),
            ("local_error", pa.string()),
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
            dir=config.ollama_guarded_article_features_path().parent,
            suffix=".parquet",
            delete=False,
        ) as handle:
            temp_article_path = Path(handle.name)

        for batch_index, (batch_key, batch_meta) in enumerate(batch_items, start=1):
            shard_path_value = batch_meta.get("shard_path")
            if not shard_path_value or int(batch_meta.get("article_rows", 0)) == 0:
                if batch_index == 1 or batch_index % progress_interval == 0 or batch_index == total_batches:
                    print(
                        f"Ollama guarded finalize shard {batch_index}/{total_batches}",
                        flush=True,
                    )
                continue

            shard_path = Path(str(shard_path_value))
            if not shard_path.exists():
                raise FileNotFoundError(f"Missing Ollama guarded checkpoint shard: {shard_path}")
            shard_df = pd.read_parquet(shard_path)
            if not shard_df.empty:
                table = pa.Table.from_pandas(shard_df[ARTICLE_COLUMNS], preserve_index=False, schema=article_schema)
                if writer is None:
                    writer = pq.ParquetWriter(temp_article_path, schema=article_schema)
                writer.write_table(table)

                forward_flags = shard_df["ollama_guarded_is_forward_looking"].astype("boolean")
                rumor_flags = shard_df["ollama_guarded_is_rumor"].astype("boolean")
                grouped = (
                    shard_df.assign(
                        _confidence_valid=shard_df["ollama_guarded_confidence"].notna().astype(float),
                        _forward_valid=forward_flags.notna().astype(float),
                        _forward_true=forward_flags.fillna(False).astype(float),
                        _rumor_valid=rumor_flags.notna().astype(float),
                        _rumor_true=rumor_flags.fillna(False).astype(float),
                        _abstain_count=shard_df["local_abstained"].astype(float),
                        _parse_fail_count=(~shard_df["local_parse_ok"]).astype(float),
                    )
                    .groupby(["ticker", "date"], as_index=False)
                    .agg(
                        article_count=("article_id", "size"),
                        confidence_sum=("ollama_guarded_confidence", "sum"),
                        confidence_count=("_confidence_valid", "sum"),
                        forward_true_sum=("_forward_true", "sum"),
                        forward_valid_count=("_forward_valid", "sum"),
                        rumor_true_sum=("_rumor_true", "sum"),
                        rumor_valid_count=("_rumor_valid", "sum"),
                        abstain_count=("_abstain_count", "sum"),
                        parse_fail_count=("_parse_fail_count", "sum"),
                    )
                )
                for row in grouped.to_dict(orient="records"):
                    key = (str(row["ticker"]), str(row["date"]))
                    state = daily_state.setdefault(
                        key,
                        {
                            "article_count": 0.0,
                            "confidence_sum": 0.0,
                            "confidence_count": 0.0,
                            "forward_true_sum": 0.0,
                            "forward_valid_count": 0.0,
                            "rumor_true_sum": 0.0,
                            "rumor_valid_count": 0.0,
                            "abstain_count": 0.0,
                            "parse_fail_count": 0.0,
                        },
                    )
                    for field in state:
                        state[field] += float(row[field])

            if batch_index == 1 or batch_index % progress_interval == 0 or batch_index == total_batches:
                print(
                    f"Ollama guarded finalize shard {batch_index}/{total_batches}",
                    flush=True,
                )

        if writer is not None and temp_article_path is not None:
            writer.close()
            writer = None
            temp_article_path.replace(config.ollama_guarded_article_features_path())
        else:
            write_parquet_atomic(_empty_article_dataframe(), config.ollama_guarded_article_features_path(), index=False)
    finally:
        if writer is not None:
            writer.close()
        if temp_article_path is not None and temp_article_path.exists():
            temp_article_path.unlink(missing_ok=True)

    daily = _daily_feature_frame_from_state(daily_state, config, log_progress=True)
    write_parquet_atomic(daily, config.ollama_guarded_ticker_day_features_path(), index=False)

    checkpoint_manifest["status"] = "complete"
    checkpoint_manifest["daily_feature_rows"] = int(len(daily))
    checkpoint_manifest["completed_at_utc"] = pd.Timestamp.utcnow().isoformat()
    _write_ollama_guarded_checkpoint_manifest(config, checkpoint_manifest)

    for batch_meta in completed_batches.values():
        shard_path_value = batch_meta.get("shard_path")
        if shard_path_value:
            Path(str(shard_path_value)).unlink(missing_ok=True)

    metadata = {
        "local_model_name": checkpoint_manifest.get("local_model_name", config.ollama_guarded_model_name),
        "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
        "daily_feature_rows": int(len(daily)),
        "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
        "checkpoint_status": str(checkpoint_manifest.get("status", "unknown")),
        "checkpoint_completed_batches": int(checkpoint_manifest.get("completed_batch_count", 0)),
        "checkpoint_total_batches": int(checkpoint_manifest.get("total_batches", 0)),
    }
    return daily, metadata


def build_ollama_guarded_feature_exports(
    config: Optional[NewsFeaturesConfig] = None,
    raw_response_fn: Optional[OllamaGuardedRawResponseFn] = None,
    *,
    checkpoint_batch_limit: Optional[int] = None,
) -> pd.DataFrame:
    config = config or get_default_config()
    config.ensure_directories()
    overall_start = perf_counter()
    load_start = perf_counter()
    guarded_input_rows = 0
    if not config.normalized_path().exists() or not config.tagged_path().exists():
        article_rows = _empty_article_dataframe()
        daily = _empty_daily_dataframe(config)
        metadata = {
            "local_model_name": config.ollama_guarded_model_name,
            "article_score_rows": 0,
            "daily_feature_rows": 0,
            "unique_article_count": 0,
        }
        load_elapsed = perf_counter() - load_start
        write_start = perf_counter()
        write_parquet_atomic(article_rows, config.ollama_guarded_article_features_path(), index=False)
        write_parquet_atomic(daily, config.ollama_guarded_ticker_day_features_path(), index=False)
        write_elapsed = perf_counter() - write_start
        build_elapsed = 0.0
    else:
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise ImportError("Streaming Ollama guarded export requires pyarrow.") from exc

        normalized_file = pq.ParquetFile(config.normalized_path())
        normalized_rows = normalized_file.metadata.num_rows
        tagged = pd.read_parquet(config.tagged_path())
        tagged["article_id"] = tagged["article_id"].astype(str)
        tagged_rows = len(tagged)
        load_elapsed = perf_counter() - load_start
        print(
            f"Loaded normalized_rows={normalized_rows} and tagged_rows={tagged_rows} for Ollama guarded lane in {load_elapsed:.1f}s",
            flush=True,
        )

        input_manifest = _prepare_ollama_guarded_input_articles_cache(
            config=config,
            normalized_file=normalized_file,
            normalized_rows=int(normalized_rows),
            tagged=tagged,
        )
        input_file = pq.ParquetFile(config.ollama_guarded_input_articles_path())
        input_rows = int(input_file.metadata.num_rows)
        guarded_input_rows = int(input_rows)
        input_source_signature = dict(input_manifest.get("source_signature") or {})
        print(
            f"Ollama guarded scoring universe: input_rows={input_rows} from {config.ollama_guarded_input_articles_path()}",
            flush=True,
        )

        if input_rows == 0:
            _clear_ollama_guarded_checkpoint_state(config)
            daily = _empty_daily_dataframe(config)
            metadata = {
                "local_model_name": config.ollama_guarded_model_name,
                "ollama_guarded_input_rows": 0,
                "article_score_rows": 0,
                "daily_feature_rows": 0,
                "unique_article_count": 0,
                "checkpoint_status": "complete",
                "checkpoint_completed_batches": 0,
                "checkpoint_total_batches": 0,
            }
            build_elapsed = 0.0
            write_start = perf_counter()
            write_parquet_atomic(_empty_article_dataframe(), config.ollama_guarded_article_features_path(), index=False)
            write_parquet_atomic(daily, config.ollama_guarded_ticker_day_features_path(), index=False)
            write_elapsed = perf_counter() - write_start
        else:
            run_signature = _ollama_guarded_run_signature(
                config,
                input_rows=input_rows,
                input_source_signature=input_source_signature,
            )
            checkpoint_manifest = _load_ollama_guarded_checkpoint_manifest(config)
            if checkpoint_manifest and checkpoint_manifest.get("run_signature") != run_signature:
                print("Ollama guarded checkpoint signature changed; clearing old checkpoint shards", flush=True)
                _clear_ollama_guarded_checkpoint_state(config)
                checkpoint_manifest = {}

            if (
                checkpoint_manifest.get("status") == "complete"
                and checkpoint_manifest.get("run_signature") == run_signature
                and config.ollama_guarded_article_features_path().exists()
                and config.ollama_guarded_ticker_day_features_path().exists()
            ):
                print("Ollama guarded checkpoint already complete; reusing published datasets", flush=True)
                daily = pd.read_parquet(config.ollama_guarded_ticker_day_features_path())
                metadata = {
                    "local_model_name": checkpoint_manifest.get("local_model_name", config.ollama_guarded_model_name),
                    "ollama_guarded_input_rows": int(input_rows),
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
                total_batches = max(
                    (int(input_rows) + int(config.ollama_guarded_checkpoint_rows) - 1)
                    // int(config.ollama_guarded_checkpoint_rows),
                    1,
                )
                if not checkpoint_manifest:
                    checkpoint_manifest = {
                        "checkpoint_version": OLLAMA_GUARDED_CHECKPOINT_VERSION,
                        "status": "in_progress",
                        "run_signature": run_signature,
                        "local_model_name": config.ollama_guarded_model_name,
                        "ollama_guarded_input_rows": int(input_rows),
                        "normalized_rows": int(normalized_rows),
                        "tagged_rows": int(tagged_rows),
                        "total_batches": int(total_batches),
                        "completed_batch_count": 0,
                        "article_score_rows": 0,
                        "unique_article_count": 0,
                        "completed_batches": {},
                        "created_at_utc": pd.Timestamp.utcnow().isoformat(),
                    }
                    _write_ollama_guarded_checkpoint_manifest(config, checkpoint_manifest)
                    print(
                        f"Ollama guarded checkpoint start: total_batches={total_batches}, "
                        f"checkpoint_rows={config.ollama_guarded_checkpoint_rows}",
                        flush=True,
                    )
                else:
                    print(
                        "Ollama guarded checkpoint resume: "
                        f"completed_batches={int(checkpoint_manifest.get('completed_batch_count', 0))}/{total_batches}, "
                        f"article_rows={int(checkpoint_manifest.get('article_score_rows', 0))}, "
                        f"unique_articles={int(checkpoint_manifest.get('unique_article_count', 0))}",
                        flush=True,
                    )

                build_start = perf_counter()
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
                        batch_size=int(config.ollama_guarded_checkpoint_rows),
                        columns=OLLAMA_GUARDED_INPUT_COLUMNS,
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
                                    f"Ollama guarded input scan {processed_input_rows}/{input_rows}; "
                                    f"unique_articles={unique_article_count}, article_rows={article_score_rows} "
                                    f"(resume skip)",
                                    flush=True,
                                )
                            continue

                    input_batch = batch.to_pandas()
                    input_batch["article_id"] = input_batch["article_id"].astype(str)
                    batch_unique_articles = int(len(input_batch))
                    batch_article_rows = 0
                    shard_path: Optional[Path] = None

                    inference_rows = _infer_article_frame(
                        input_batch,
                        config=config,
                        raw_response_fn=raw_response_fn,
                        log_progress=False,
                    )
                    if not inference_rows.empty:
                        batch_tagged = tagged_indexed.loc[inference_rows["article_id"].tolist()].reset_index(drop=True)
                        article_rows_batch = batch_tagged.merge(
                            inference_rows,
                            on="article_id",
                            how="inner",
                            validate="many_to_one",
                        )
                        article_rows_batch = article_rows_batch[ARTICLE_COLUMNS]
                        batch_article_rows = int(len(article_rows_batch))
                        if batch_article_rows > 0:
                            shard_path = config.ollama_guarded_checkpoint_shard_path(batch_index)
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
                            "local_model_name": config.ollama_guarded_model_name,
                            "completed_batches": completed_batches,
                            "completed_batch_count": int(len(completed_batches)),
                            "article_score_rows": int(article_score_rows),
                            "unique_article_count": int(unique_article_count),
                            "last_completed_batch": int(batch_index),
                            "last_updated_utc": pd.Timestamp.utcnow().isoformat(),
                        }
                    )
                    _write_ollama_guarded_checkpoint_manifest(config, checkpoint_manifest)
                    processed_new_batches += 1

                    if (
                        processed_input_rows == batch_row_count
                        or processed_input_rows % progress_interval == 0
                        or processed_input_rows >= input_rows
                    ):
                        print(
                            f"Ollama guarded input scan {processed_input_rows}/{input_rows}; "
                            f"unique_articles={unique_article_count}, article_rows={article_score_rows}",
                            flush=True,
                        )

                    if checkpoint_batch_limit is not None and processed_new_batches >= int(checkpoint_batch_limit):
                        print(
                            f"Ollama guarded checkpoint test stop after {processed_new_batches} new batches",
                            flush=True,
                        )
                        break

                if int(checkpoint_manifest.get("completed_batch_count", 0)) == int(
                    checkpoint_manifest.get("total_batches", total_batches)
                ):
                    print("Ollama guarded checkpoint scoring complete. Finalizing published datasets...", flush=True)
                    daily, finalized_metadata = _finalize_ollama_guarded_from_checkpoints(
                        config=config,
                        checkpoint_manifest=checkpoint_manifest,
                    )
                    metadata = dict(finalized_metadata)
                else:
                    daily = _empty_daily_dataframe(config)
                    metadata = {
                        "local_model_name": config.ollama_guarded_model_name,
                        "article_score_rows": int(checkpoint_manifest.get("article_score_rows", 0)),
                        "daily_feature_rows": 0,
                        "unique_article_count": int(checkpoint_manifest.get("unique_article_count", 0)),
                        "checkpoint_status": "in_progress",
                        "checkpoint_completed_batches": int(checkpoint_manifest.get("completed_batch_count", 0)),
                        "checkpoint_total_batches": int(checkpoint_manifest.get("total_batches", total_batches)),
                    }

                build_elapsed = perf_counter() - build_start
                write_elapsed = 0.0

    metadata.update(
        {
            "ollama_guarded_input_rows": int(guarded_input_rows),
            "article_score_rows": int(metadata.get("article_score_rows", 0)),
            "daily_feature_rows": int(len(daily)),
        }
    )
    update_manifest(
        config=config,
        ollama_guarded_model_name=str(metadata.get("local_model_name", config.ollama_guarded_model_name)),
        ollama_guarded_article_features_rows=int(metadata.get("article_score_rows", 0)),
        ollama_guarded_ticker_day_features_rows=int(len(daily)),
        ollama_guarded_checkpoint_status=str(
            metadata.get("checkpoint_status", "complete" if len(daily) > 0 else "in_progress")
        ),
        ollama_guarded_checkpoint_completed_batches=int(metadata.get("checkpoint_completed_batches", 0)),
        ollama_guarded_checkpoint_total_batches=int(metadata.get("checkpoint_total_batches", 0)),
        ollama_guarded_input_articles_rows=int(metadata.get("ollama_guarded_input_rows", 0)),
        ollama_guarded_article_features_dataset_path=describe_path(
            config.ollama_guarded_article_features_path(),
            config=config,
        ),
        ollama_guarded_ticker_day_features_dataset_path=describe_path(
            config.ollama_guarded_ticker_day_features_path(),
            config=config,
        ),
        ollama_guarded_input_articles_dataset_path=describe_path(
            config.ollama_guarded_input_articles_path(),
            config=config,
        ),
    )
    overall_elapsed = perf_counter() - overall_start
    print(
        f"Timing summary: load={load_elapsed:.1f}s, build={build_elapsed:.1f}s, "
        f"write={write_elapsed:.1f}s, total={overall_elapsed:.1f}s",
        flush=True,
    )
    print(
        f"Built {int(metadata.get('article_score_rows', 0))} Ollama guarded article rows and {len(daily)} ticker-day rows -> "
        f"{config.ollama_guarded_ticker_day_features_path()}",
        flush=True,
    )
    return daily


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Build additive guarded local Ollama news datasets.")


def main() -> None:
    build_arg_parser().parse_args()
    build_ollama_guarded_feature_exports()


if __name__ == "__main__":
    main()
