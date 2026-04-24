"""Build tabular daily news features from tagged articles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from time import perf_counter
from typing import Optional

import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.io_utils import (
    describe_path,
    load_feature_spec,
    update_manifest,
    write_parquet_atomic,
)


TABULAR_STAGE_COLUMNS = [
    "article_id",
    "ticker",
    "date",
    "url",
    "title_hit",
    "body_hit",
    "title_length",
    "body_length",
    "news_sentiment_keyword_score",
]
TABULAR_STAGE_VERSION = 1


def _ordered_tabular_columns(config: NewsFeaturesConfig) -> list[str]:
    ordered = [
        "ticker",
        "date",
        "news_article_count_1d",
        "news_title_len_mean",
        "news_body_len_mean",
        "news_articles_with_title_hit",
        "news_articles_with_body_hit",
        "news_unique_urls_1d",
        "news_sentiment_keyword_score_sum",
        "news_sentiment_keyword_score_mean",
    ]
    ordered.extend(f"news_article_count_{int(window)}d" for window in config.rolling_windows)
    return ordered


def _empty_tabular_dataframe(config: NewsFeaturesConfig) -> pd.DataFrame:
    return pd.DataFrame(columns=_ordered_tabular_columns(config))


def _keyword_score(text: str, positive_keywords: list[str], negative_keywords: list[str]) -> int:
    lower_text = str(text).lower()
    positive = sum(lower_text.count(keyword.lower()) for keyword in positive_keywords)
    negative = sum(lower_text.count(keyword.lower()) for keyword in negative_keywords)
    return positive - negative


def build_tabular_feature_dataframe(
    normalized_df: pd.DataFrame,
    tagged_df: pd.DataFrame,
    config: Optional[NewsFeaturesConfig] = None,
    log_progress: bool = False,
) -> pd.DataFrame:
    config = config or get_default_config()
    if normalized_df.empty or tagged_df.empty:
        if log_progress:
            print(
                f"Tabular build skipped because normalized_rows={len(normalized_df)} and tagged_rows={len(tagged_df)}",
                flush=True,
            )
        return _empty_tabular_dataframe(config)

    feature_spec = load_feature_spec(config=config)
    sentiment = feature_spec.get("sentiment", {})
    positive_keywords = list(sentiment.get("positive_keywords", []))
    negative_keywords = list(sentiment.get("negative_keywords", []))
    if log_progress:
        print(
            f"Tabular stage 1/4: merging {len(tagged_df)} tagged rows with {len(normalized_df)} normalized rows",
            flush=True,
        )

    merged = tagged_df.merge(
        normalized_df[
            [
                "article_id",
                "url",
                "clean_title",
                "clean_summary",
                "clean_body_text",
                "date",
            ]
        ],
        on=["article_id", "url", "date"],
        how="left",
        validate="many_to_one",
    )
    if log_progress:
        print(f"Tabular stage 1/4 complete: merged_rows={len(merged)}", flush=True)

    if log_progress:
        print("Tabular stage 2/4: computing per-article text stats and keyword sentiment", flush=True)
    merged["title_length"] = merged["clean_title"].fillna("").str.len().astype(float)
    merged["body_length"] = merged["clean_body_text"].fillna("").str.len().astype(float)
    merged["combined_text"] = (
        merged["clean_title"].fillna("")
        + " "
        + merged["clean_summary"].fillna("")
        + " "
        + merged["clean_body_text"].fillna("")
    )
    merged[config.keyword_score_column] = merged["combined_text"].map(
        lambda value: _keyword_score(value, positive_keywords, negative_keywords)
    )
    if log_progress:
        print(
            f"Tabular stage 2/4 complete: keyword_scored_rows={len(merged)}, "
            f"positive_keywords={len(positive_keywords)}, negative_keywords={len(negative_keywords)}",
            flush=True,
        )

    if log_progress:
        print("Tabular stage 3/4: aggregating per ticker/day", flush=True)
    daily = (
        merged.groupby(["ticker", "date"], as_index=False)
        .agg(
            news_article_count_1d=("article_id", "size"),
            news_title_len_mean=("title_length", "mean"),
            news_body_len_mean=("body_length", "mean"),
            news_articles_with_title_hit=("title_hit", "sum"),
            news_articles_with_body_hit=("body_hit", "sum"),
            news_unique_urls_1d=("url", "nunique"),
            news_sentiment_keyword_score_sum=(config.keyword_score_column, "sum"),
            news_sentiment_keyword_score_mean=(config.keyword_score_column, "mean"),
        )
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )
    daily["date"] = pd.to_datetime(daily["date"])
    if log_progress:
        print(
            f"Tabular stage 3/4 complete: daily_rows={len(daily)}, unique_tickers={daily['ticker'].nunique()}",
            flush=True,
        )

    frames: list[pd.DataFrame] = []
    rolling_windows = feature_spec.get("rolling_windows", config.rolling_windows)
    ticker_groups = list(daily.groupby("ticker", sort=True))
    total_tickers = len(ticker_groups)
    progress_interval = 1 if total_tickers <= 10 else 10
    if log_progress:
        print(
            f"Tabular stage 4/4: reindexing daily gaps and rolling windows for {total_tickers} tickers",
            flush=True,
        )
    for ticker_index, (ticker, group) in enumerate(ticker_groups, start=1):
        group = group.sort_values("date").reset_index(drop=True)
        date_index = pd.date_range(group["date"].min(), group["date"].max(), freq="D")
        group = group.set_index("date").reindex(date_index)
        group["ticker"] = ticker
        count_columns = [
            "news_article_count_1d",
            "news_articles_with_title_hit",
            "news_articles_with_body_hit",
            "news_unique_urls_1d",
            "news_sentiment_keyword_score_sum",
        ]
        mean_columns = [
            "news_title_len_mean",
            "news_body_len_mean",
            "news_sentiment_keyword_score_mean",
        ]
        for column in count_columns + mean_columns:
            group[column] = group[column].fillna(0.0)
        for window in rolling_windows:
            group[f"news_article_count_{int(window)}d"] = group["news_article_count_1d"].rolling(
                window=int(window),
                min_periods=1,
            ).sum()
        group = group.reset_index().rename(columns={"index": "date"})
        frames.append(group)
        if log_progress and (
            ticker_index == 1
            or ticker_index % progress_interval == 0
            or ticker_index == total_tickers
        ):
            print(
                f"Tabular stage 4/4 progress: processed {ticker_index}/{total_tickers} tickers; "
                f"accumulated_rows={sum(len(frame) for frame in frames)}",
                flush=True,
            )

    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"]).dt.strftime("%Y-%m-%d")
    ordered = _ordered_tabular_columns(config)
    result = combined[ordered].sort_values(["ticker", "date"]).reset_index(drop=True)
    if log_progress:
        print(
            f"Tabular summary: rows={len(result)}, unique_tickers={result['ticker'].nunique()}, "
            f"date_range={result['date'].min()} -> {result['date'].max()}",
            flush=True,
        )
    return result


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


def _load_tabular_stage_manifest(config: NewsFeaturesConfig) -> dict[str, object]:
    path = config.tabular_stage_manifest_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_tabular_stage_manifest(config: NewsFeaturesConfig, payload: dict[str, object]) -> None:
    _write_json_atomic(config.tabular_stage_manifest_path(), payload)


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


def _normalize_date_value(value: object) -> str:
    if pd.isna(value):
        return ""
    try:
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    except Exception:
        return str(value)


def _coerce_float(value: object) -> float:
    try:
        numeric = pd.to_numeric(value, errors="coerce")
    except Exception:
        return 0.0
    return 0.0 if pd.isna(numeric) else float(numeric)


def _tabular_join_key(article_id: object, url: object, date: object) -> str:
    return "\x1f".join(
        [
            "" if pd.isna(article_id) else str(article_id),
            "" if pd.isna(url) else str(url),
            _normalize_date_value(date),
        ]
    )


def _tabular_stage_source_signature(
    config: NewsFeaturesConfig,
    *,
    normalized_rows: int,
    tagged_rows: int,
    positive_keywords: list[str],
    negative_keywords: list[str],
) -> dict[str, object]:
    return {
        "stage_version": TABULAR_STAGE_VERSION,
        "normalized_rows": int(normalized_rows),
        "tagged_rows": int(tagged_rows),
        "normalized_input": _path_checkpoint_signature(config.normalized_path()),
        "tagged_input": _path_checkpoint_signature(config.tagged_path()),
        "positive_keywords": list(positive_keywords),
        "negative_keywords": list(negative_keywords),
    }


def _load_tabular_tagged_keys(config: NewsFeaturesConfig) -> tuple[set[str], int]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Streaming tabular feature builds require pyarrow.") from exc

    if not config.tagged_path().exists():
        return set(), 0

    tagged_file = pq.ParquetFile(config.tagged_path())
    tagged_rows = int(tagged_file.metadata.num_rows)
    keys: set[str] = set()
    batch_size = 50000
    scanned_rows = 0
    progress_interval = 100000
    for batch in tagged_file.iter_batches(
        batch_size=batch_size,
        columns=["article_id", "url", "date"],
    ):
        batch_df = batch.to_pandas()
        for row in batch_df.itertuples(index=False):
            keys.add(_tabular_join_key(row.article_id, row.url, row.date))
        scanned_rows += int(len(batch_df))
        if (
            scanned_rows == len(batch_df)
            or scanned_rows % progress_interval == 0
            or scanned_rows >= tagged_rows
        ):
            print(
                f"Tabular stage cache scan: collected tagged_keys={len(keys)} from "
                f"tagged_rows={scanned_rows}/{tagged_rows}",
                flush=True,
            )
    return keys, tagged_rows


def _build_tabular_article_lookup(
    *,
    config: NewsFeaturesConfig,
    tagged_keys: set[str],
    positive_keywords: list[str],
    negative_keywords: list[str],
) -> tuple[dict[str, dict[str, float]], int]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Streaming tabular feature builds require pyarrow.") from exc

    if not config.normalized_path().exists():
        return {}, 0

    normalized_file = pq.ParquetFile(config.normalized_path())
    normalized_rows = int(normalized_file.metadata.num_rows)
    requested_columns = [
        "article_id",
        "url",
        "date",
        "clean_title",
        "clean_summary",
        "clean_body_text",
    ]
    available_columns = set(normalized_file.schema_arrow.names)
    columns = [column for column in requested_columns if column in available_columns]
    lookup: dict[str, dict[str, float]] = {}
    scanned_rows = 0
    batch_size = 50000
    progress_interval = 100000
    for batch in normalized_file.iter_batches(batch_size=batch_size, columns=columns):
        batch_df = batch.to_pandas()
        for column in requested_columns:
            if column not in batch_df.columns:
                batch_df[column] = ""
        for row in batch_df.itertuples(index=False):
            key = _tabular_join_key(row.article_id, row.url, row.date)
            if key not in tagged_keys:
                continue
            if key in lookup:
                raise ValueError("Tabular feature build expected normalized article keys to be unique")
            clean_title = "" if pd.isna(row.clean_title) else str(row.clean_title)
            clean_summary = "" if pd.isna(row.clean_summary) else str(row.clean_summary)
            clean_body_text = "" if pd.isna(row.clean_body_text) else str(row.clean_body_text)
            combined_text = clean_title + " " + clean_summary + " " + clean_body_text
            lookup[key] = {
                "title_length": float(len(clean_title)),
                "body_length": float(len(clean_body_text)),
                "keyword_score": float(_keyword_score(combined_text, positive_keywords, negative_keywords)),
            }
        scanned_rows += int(len(batch_df))
        if (
            scanned_rows == len(batch_df)
            or scanned_rows % progress_interval == 0
            or scanned_rows >= normalized_rows
        ):
            print(
                f"Tabular stage cache: scanned normalized_rows={scanned_rows}/{normalized_rows}; "
                f"matched_articles={len(lookup)}",
                flush=True,
            )
    return lookup, normalized_rows


def _prepare_tabular_article_stage_cache(
    *,
    config: NewsFeaturesConfig,
    positive_keywords: list[str],
    negative_keywords: list[str],
) -> dict[str, object]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Streaming tabular feature builds require pyarrow.") from exc

    normalized_rows = 0
    tagged_rows = 0
    if config.normalized_path().exists():
        normalized_rows = int(pq.ParquetFile(config.normalized_path()).metadata.num_rows)
    if config.tagged_path().exists():
        tagged_rows = int(pq.ParquetFile(config.tagged_path()).metadata.num_rows)
    source_signature = _tabular_stage_source_signature(
        config,
        normalized_rows=normalized_rows,
        tagged_rows=tagged_rows,
        positive_keywords=positive_keywords,
        negative_keywords=negative_keywords,
    )

    current_manifest = _load_tabular_stage_manifest(config)
    if (
        config.tabular_stage_path().exists()
        and current_manifest.get("status") == "complete"
        and current_manifest.get("source_signature") == source_signature
    ):
        stage_rows = int(current_manifest.get("stage_rows", 0))
        print(
            f"Tabular stage cache reuse: stage_rows={stage_rows}, "
            f"matched_articles={int(current_manifest.get('matched_article_count', 0))}",
            flush=True,
        )
        return current_manifest

    tagged_keys, tagged_rows = _load_tabular_tagged_keys(config)
    article_lookup, normalized_rows = _build_tabular_article_lookup(
        config=config,
        tagged_keys=tagged_keys,
        positive_keywords=positive_keywords,
        negative_keywords=negative_keywords,
    )
    source_signature = _tabular_stage_source_signature(
        config,
        normalized_rows=normalized_rows,
        tagged_rows=tagged_rows,
        positive_keywords=positive_keywords,
        negative_keywords=negative_keywords,
    )

    stage_schema = pa.schema(
        [
            ("article_id", pa.string()),
            ("ticker", pa.string()),
            ("date", pa.string()),
            ("url", pa.string()),
            ("title_hit", pa.float64()),
            ("body_hit", pa.float64()),
            ("title_length", pa.float64()),
            ("body_length", pa.float64()),
            ("news_sentiment_keyword_score", pa.float64()),
        ]
    )
    stage_rows = 0
    stage_writer = None
    temp_stage_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(dir=config.datasets_dir, suffix=".parquet", delete=False) as handle:
            temp_stage_path = Path(handle.name)

        if config.tagged_path().exists():
            tagged_file = pq.ParquetFile(config.tagged_path())
            batch_size = 50000
            scanned_rows = 0
            progress_interval = 100000
            for batch in tagged_file.iter_batches(
                batch_size=batch_size,
                columns=["article_id", "ticker", "date", "url", "title_hit", "body_hit"],
            ):
                batch_df = batch.to_pandas()
                stage_batch_rows: list[dict[str, object]] = []
                for row in batch_df.itertuples(index=False):
                    key = _tabular_join_key(row.article_id, row.url, row.date)
                    stats = article_lookup.get(key)
                    stage_batch_rows.append(
                        {
                            "article_id": "" if pd.isna(row.article_id) else str(row.article_id),
                            "ticker": "" if pd.isna(row.ticker) else str(row.ticker),
                            "date": _normalize_date_value(row.date),
                            "url": "" if pd.isna(row.url) else str(row.url),
                            "title_hit": _coerce_float(row.title_hit),
                            "body_hit": _coerce_float(row.body_hit),
                            "title_length": float(stats["title_length"]) if stats else 0.0,
                            "body_length": float(stats["body_length"]) if stats else 0.0,
                            "news_sentiment_keyword_score": float(stats["keyword_score"]) if stats else 0.0,
                        }
                    )
                if stage_batch_rows:
                    stage_batch_df = pd.DataFrame(stage_batch_rows, columns=TABULAR_STAGE_COLUMNS)
                    table = pa.Table.from_pandas(
                        stage_batch_df,
                        preserve_index=False,
                        schema=stage_schema,
                    )
                    if stage_writer is None:
                        stage_writer = pq.ParquetWriter(temp_stage_path, schema=stage_schema)
                    stage_writer.write_table(table)
                    stage_rows += int(len(stage_batch_df))
                scanned_rows += int(len(batch_df))
                if (
                    scanned_rows == len(batch_df)
                    or scanned_rows % progress_interval == 0
                    or scanned_rows >= tagged_rows
                ):
                    print(
                        f"Tabular stage write: staged_rows={stage_rows}, "
                        f"scanned_tagged_rows={scanned_rows}/{tagged_rows}",
                        flush=True,
                    )

        if stage_writer is None:
            empty_stage = pd.DataFrame(columns=TABULAR_STAGE_COLUMNS)
            write_parquet_atomic(empty_stage, temp_stage_path, index=False)
        else:
            stage_writer.close()
            stage_writer = None

        temp_stage_path.replace(config.tabular_stage_path())
    finally:
        if stage_writer is not None:
            stage_writer.close()
        if temp_stage_path is not None and temp_stage_path.exists():
            temp_stage_path.unlink(missing_ok=True)

    manifest = {
        "status": "complete",
        "source_signature": source_signature,
        "matched_article_count": int(len(article_lookup)),
        "stage_rows": int(stage_rows),
        "stage_path": describe_path(config.tabular_stage_path(), config=config),
        "completed_at_utc": pd.Timestamp.utcnow().isoformat(),
    }
    _write_tabular_stage_manifest(config, manifest)
    return manifest


def _build_dense_ticker_frame(
    *,
    ticker: str,
    daily_states: dict[str, dict[str, object]],
    config: NewsFeaturesConfig,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for date in sorted(daily_states):
        state = daily_states[date]
        article_count = float(state["article_count"])
        keyword_sum = float(state["keyword_sum"])
        rows.append(
            {
                "ticker": ticker,
                "date": date,
                "news_article_count_1d": article_count,
                "news_title_len_mean": float(state["title_length_sum"]) / article_count if article_count else 0.0,
                "news_body_len_mean": float(state["body_length_sum"]) / article_count if article_count else 0.0,
                "news_articles_with_title_hit": float(state["title_hit_sum"]),
                "news_articles_with_body_hit": float(state["body_hit_sum"]),
                "news_unique_urls_1d": float(len(state["article_ids"])),
                "news_sentiment_keyword_score_sum": keyword_sum,
                "news_sentiment_keyword_score_mean": keyword_sum / article_count if article_count else 0.0,
            }
        )

    group = pd.DataFrame(rows)
    group["date"] = pd.to_datetime(group["date"])
    group = group.sort_values("date").reset_index(drop=True)
    date_index = pd.date_range(group["date"].min(), group["date"].max(), freq="D")
    group = group.set_index("date").reindex(date_index)
    group["ticker"] = ticker
    count_columns = [
        "news_article_count_1d",
        "news_articles_with_title_hit",
        "news_articles_with_body_hit",
        "news_unique_urls_1d",
        "news_sentiment_keyword_score_sum",
    ]
    mean_columns = [
        "news_title_len_mean",
        "news_body_len_mean",
        "news_sentiment_keyword_score_mean",
    ]
    for column in count_columns + mean_columns:
        group[column] = pd.to_numeric(group[column], errors="coerce").fillna(0.0)
    for window in config.rolling_windows:
        group[f"news_article_count_{int(window)}d"] = group["news_article_count_1d"].rolling(
            window=int(window),
            min_periods=1,
        ).sum()
    group = group.reset_index().rename(columns={"index": "date"})
    group["date"] = pd.to_datetime(group["date"]).dt.strftime("%Y-%m-%d")
    ordered = _ordered_tabular_columns(config)
    return group[ordered]


def _build_tabular_dataset_from_stage(
    *,
    config: NewsFeaturesConfig,
    return_dataframe: bool,
    log_progress: bool,
) -> pd.DataFrame:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Streaming tabular feature builds require pyarrow.") from exc

    ordered = _ordered_tabular_columns(config)
    if not config.tabular_stage_path().exists():
        empty = _empty_tabular_dataframe(config)
        write_parquet_atomic(empty, config.tabular_dataset_path(), index=False)
        return empty

    stage_file = pq.ParquetFile(config.tabular_stage_path())
    daily_by_ticker: dict[str, dict[str, dict[str, object]]] = {}
    stage_rows = int(stage_file.metadata.num_rows)
    scanned_rows = 0
    batch_size = 50000
    progress_interval = 100000
    if log_progress:
        print(
            f"Tabular final pass 1/2: aggregating article stage rows={stage_rows} into ticker/day states",
            flush=True,
        )
    for batch in stage_file.iter_batches(batch_size=batch_size, columns=TABULAR_STAGE_COLUMNS):
        batch_df = batch.to_pandas()
        for (ticker, date), group in batch_df.groupby(["ticker", "date"], sort=False):
            ticker_key = "" if pd.isna(ticker) else str(ticker)
            date_key = _normalize_date_value(date)
            ticker_state = daily_by_ticker.setdefault(ticker_key, {})
            state = ticker_state.setdefault(
                date_key,
                {
                    "article_count": 0.0,
                    "title_length_sum": 0.0,
                    "body_length_sum": 0.0,
                    "title_hit_sum": 0.0,
                    "body_hit_sum": 0.0,
                    "keyword_sum": 0.0,
                    "article_ids": set(),
                },
            )
            state["article_count"] += float(len(group))
            state["title_length_sum"] += float(pd.to_numeric(group["title_length"], errors="coerce").fillna(0.0).sum())
            state["body_length_sum"] += float(pd.to_numeric(group["body_length"], errors="coerce").fillna(0.0).sum())
            state["title_hit_sum"] += float(pd.to_numeric(group["title_hit"], errors="coerce").fillna(0.0).sum())
            state["body_hit_sum"] += float(pd.to_numeric(group["body_hit"], errors="coerce").fillna(0.0).sum())
            state["keyword_sum"] += float(
                pd.to_numeric(group["news_sentiment_keyword_score"], errors="coerce").fillna(0.0).sum()
            )
            state["article_ids"].update(group["article_id"].fillna("").astype(str).tolist())
        scanned_rows += int(len(batch_df))
        if log_progress and (
            scanned_rows == len(batch_df)
            or scanned_rows % progress_interval == 0
            or scanned_rows >= stage_rows
        ):
            print(
                f"Tabular final pass 1/2 progress: scanned_rows={scanned_rows}/{stage_rows}; "
                f"aggregated_tickers={len(daily_by_ticker)}",
                flush=True,
            )

    if not daily_by_ticker:
        empty = _empty_tabular_dataframe(config)
        write_parquet_atomic(empty, config.tabular_dataset_path(), index=False)
        return empty

    schema = pa.schema(
        [
            ("ticker", pa.string()),
            ("date", pa.string()),
            *[(column, pa.float64()) for column in ordered[2:]],
        ]
    )
    result_frames: list[pd.DataFrame] = []
    writer = None
    temp_output_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(dir=config.datasets_dir, suffix=".parquet", delete=False) as handle:
            temp_output_path = Path(handle.name)

        total_tickers = len(daily_by_ticker)
        progress_interval = 1 if total_tickers <= 10 else 10
        if log_progress:
            print(
                f"Tabular final pass 2/2: reindexing and rolling-window expansion for {total_tickers} tickers",
                flush=True,
            )
        for ticker_index, ticker in enumerate(sorted(daily_by_ticker), start=1):
            dense = _build_dense_ticker_frame(
                ticker=ticker,
                daily_states=daily_by_ticker[ticker],
                config=config,
            )
            table = pa.Table.from_pandas(dense, preserve_index=False, schema=schema)
            if writer is None:
                writer = pq.ParquetWriter(temp_output_path, schema=schema)
            writer.write_table(table)
            if return_dataframe:
                result_frames.append(dense)
            if log_progress and (
                ticker_index == 1
                or ticker_index % progress_interval == 0
                or ticker_index == total_tickers
            ):
                print(
                    f"Tabular final pass 2/2 progress: processed {ticker_index}/{total_tickers} tickers",
                    flush=True,
                )
        writer.close()
        writer = None
        temp_output_path.replace(config.tabular_dataset_path())
    finally:
        if writer is not None:
            writer.close()
        if temp_output_path is not None and temp_output_path.exists():
            temp_output_path.unlink(missing_ok=True)

    if return_dataframe:
        return pd.concat(result_frames, ignore_index=True) if result_frames else _empty_tabular_dataframe(config)
    return _empty_tabular_dataframe(config)


def _parquet_row_count(path: Path) -> int:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Streaming tabular feature builds require pyarrow.") from exc
    if not path.exists():
        return 0
    return int(pq.ParquetFile(path).metadata.num_rows)


def build_tabular_feature_exports(
    config: Optional[NewsFeaturesConfig] = None,
    *,
    return_dataframe: bool = True,
) -> pd.DataFrame:
    config = config or get_default_config()
    overall_start = perf_counter()
    feature_spec = load_feature_spec(config=config)
    sentiment = feature_spec.get("sentiment", {})
    positive_keywords = list(sentiment.get("positive_keywords", []))
    negative_keywords = list(sentiment.get("negative_keywords", []))

    stage_start = perf_counter()
    stage_manifest = _prepare_tabular_article_stage_cache(
        config=config,
        positive_keywords=positive_keywords,
        negative_keywords=negative_keywords,
    )
    stage_elapsed = perf_counter() - stage_start
    print(
        f"Tabular stage cache ready in {stage_elapsed:.1f}s: stage_rows={int(stage_manifest.get('stage_rows', 0))}",
        flush=True,
    )

    build_start = perf_counter()
    tabular = _build_tabular_dataset_from_stage(
        config=config,
        return_dataframe=return_dataframe,
        log_progress=True,
    )
    build_elapsed = perf_counter() - build_start
    update_manifest(
        config=config,
        tabular_feature_rows=int(len(tabular)) if return_dataframe else _parquet_row_count(config.tabular_dataset_path()),
        tabular_dataset_path=describe_path(config.tabular_dataset_path(), config=config),
    )
    overall_elapsed = perf_counter() - overall_start
    print(
        f"Tabular timing summary: stage={stage_elapsed:.1f}s, final_build={build_elapsed:.1f}s, total={overall_elapsed:.1f}s",
        flush=True,
    )
    print(f"Built tabular feature rows -> {config.tabular_dataset_path()}")
    if return_dataframe:
        return tabular
    return _empty_tabular_dataframe(config)


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Build daily tabular news features.")


def main() -> None:
    build_arg_parser().parse_args()
    build_tabular_feature_exports(return_dataframe=False)


if __name__ == "__main__":
    main()
