"""Normalize raw news articles into a clean parquet corpus."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from time import perf_counter
import tempfile
from typing import Optional

import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.io_utils import (
    canonicalize_url,
    describe_path,
    list_raw_news_files,
    read_jsonl,
    update_manifest,
)


WHITESPACE_RE = re.compile(r"\s+")
SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")


def clean_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def _empty_normalized_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "article_id",
            "source",
            "url",
            "title",
            "summary",
            "body_text",
            "clean_title",
            "clean_summary",
            "clean_body_text",
            "published_at",
            "date",
            "author",
            "section_name",
            "tags",
        ]
    )


def _preprocess_news_dataframe_with_stats(
    raw_df: pd.DataFrame,
    config: Optional[NewsFeaturesConfig] = None,
    log_progress: bool = False,
) -> tuple[pd.DataFrame, dict[str, object]]:
    # The dataframe-only path needs timezone settings, not filesystem side effects.
    config = config or NewsFeaturesConfig()
    if raw_df.empty:
        return _empty_normalized_dataframe(), {
            "input_rows": 0,
            "dropped_invalid_identity_rows": 0,
            "dropped_unparseable_timestamp_rows": 0,
            "dropped_empty_text_rows": 0,
            "dropped_duplicate_article_rows": 0,
            "normalized_rows": 0,
            "rows_with_section_name": 0,
            "date_min": None,
            "date_max": None,
        }

    stats: dict[str, object] = {"input_rows": int(len(raw_df))}
    df = raw_df.copy()
    if log_progress:
        print(f"Preprocess stage 1/6: preparing dataframe shell for {len(df)} rows", flush=True)
    for column in ("title", "summary", "body_text", "author"):
        if column not in df.columns:
            df[column] = ""
    if "tags" not in df.columns:
        df["tags"] = [[] for _ in range(len(df))]
    if "section_name" not in df.columns:
        df["section_name"] = ""

    if log_progress:
        print("Preprocess stage 2/6: validating article identity fields", flush=True)
    df["url"] = df["url"].map(canonicalize_url)
    df["article_id"] = df["article_id"].astype(str).str.strip()
    valid_identity_mask = (df["article_id"] != "") & (df["url"] != "")
    stats["dropped_invalid_identity_rows"] = int((~valid_identity_mask).sum())
    df = df[valid_identity_mask].copy()
    if log_progress:
        print(
            f"Preprocess stage 2/6 complete: kept {len(df)} rows after identity validation "
            f"(dropped={stats['dropped_invalid_identity_rows']})",
            flush=True,
        )

    if log_progress:
        print("Preprocess stage 3/6: parsing published_at timestamps", flush=True)
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    valid_timestamp_mask = df["published_at"].notna()
    stats["dropped_unparseable_timestamp_rows"] = int((~valid_timestamp_mask).sum())
    df = df[valid_timestamp_mask].copy()
    if log_progress:
        print(
            f"Preprocess stage 3/6 complete: kept {len(df)} rows with valid timestamps "
            f"(dropped={stats['dropped_unparseable_timestamp_rows']})",
            flush=True,
        )

    if log_progress:
        print("Preprocess stage 4/6: cleaning title, summary, and body text", flush=True)
    df["clean_title"] = df["title"].map(clean_text)
    df["clean_summary"] = df["summary"].map(clean_text)
    df["clean_body_text"] = df["body_text"].map(clean_text)
    valid_text_mask = (df["clean_title"] != "") & (df["clean_body_text"] != "")
    stats["dropped_empty_text_rows"] = int((~valid_text_mask).sum())
    df = df[valid_text_mask].copy()
    if log_progress:
        print(
            f"Preprocess stage 4/6 complete: kept {len(df)} rows with non-empty cleaned text "
            f"(dropped={stats['dropped_empty_text_rows']})",
            flush=True,
        )

    if log_progress:
        print("Preprocess stage 5/6: deduplicating by article_id", flush=True)
    before_dedup_count = len(df)
    df = df.drop_duplicates(subset=["article_id"], keep="first")
    stats["dropped_duplicate_article_rows"] = int(before_dedup_count - len(df))
    if log_progress:
        print(
            f"Preprocess stage 5/6 complete: kept {len(df)} unique articles "
            f"(dropped_duplicates={stats['dropped_duplicate_article_rows']})",
            flush=True,
        )

    if log_progress:
        print("Preprocess stage 6/6: converting to market timezone and finalizing columns", flush=True)
    published_local = df["published_at"].dt.tz_convert(config.market_timezone)
    df["date"] = published_local.dt.strftime("%Y-%m-%d")
    df["published_at"] = published_local.map(lambda ts: ts.isoformat())
    df["section_name"] = df["section_name"].map(clean_text)
    df.loc[df["section_name"] == "", "section_name"] = None
    if "source" not in df.columns:
        df["source"] = ""
    ordered_columns = [
        "article_id",
        "source",
        "url",
        "title",
        "summary",
        "body_text",
        "clean_title",
        "clean_summary",
        "clean_body_text",
        "published_at",
        "date",
        "author",
        "section_name",
        "tags",
    ]
    normalized = df[ordered_columns].sort_values(["date", "article_id"]).reset_index(drop=True)
    stats["normalized_rows"] = int(len(normalized))
    stats["rows_with_section_name"] = int(normalized["section_name"].notna().sum()) if not normalized.empty else 0
    stats["date_min"] = str(normalized["date"].min()) if not normalized.empty else None
    stats["date_max"] = str(normalized["date"].max()) if not normalized.empty else None
    if log_progress:
        print(
            f"Preprocess stage 6/6 complete: finalized {len(normalized)} normalized rows",
            flush=True,
        )
    return normalized, stats


def preprocess_news_dataframe(
    raw_df: pd.DataFrame,
    config: Optional[NewsFeaturesConfig] = None,
) -> pd.DataFrame:
    normalized, _stats = _preprocess_news_dataframe_with_stats(raw_df=raw_df, config=config)
    return normalized


def preprocess_news_exports(
    source: Optional[str] = None,
    config: Optional[NewsFeaturesConfig] = None,
) -> pd.DataFrame:
    config = config or get_default_config()
    config.ensure_directories()
    selected_source = source or config.default_source
    raw_files = list_raw_news_files(source=selected_source, config=config)
    overall_start = perf_counter()
    print(
        f"Loading raw news for source={selected_source} from {len(raw_files)} JSONL files under {config.source_raw_dir(selected_source)}",
        flush=True,
    )
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Streaming news preprocess requires pyarrow.") from exc

    normalized_columns = list(_empty_normalized_dataframe().columns)
    schema = pa.schema(
        [
            ("article_id", pa.string()),
            ("source", pa.string()),
            ("url", pa.string()),
            ("title", pa.string()),
            ("summary", pa.string()),
            ("body_text", pa.string()),
            ("clean_title", pa.string()),
            ("clean_summary", pa.string()),
            ("clean_body_text", pa.string()),
            ("published_at", pa.string()),
            ("date", pa.string()),
            ("author", pa.string()),
            ("section_name", pa.string()),
            ("tags", pa.list_(pa.string())),
        ]
    )

    stats: dict[str, object] = {
        "input_rows": 0,
        "dropped_invalid_identity_rows": 0,
        "dropped_unparseable_timestamp_rows": 0,
        "dropped_empty_text_rows": 0,
        "dropped_duplicate_article_rows": 0,
        "dropped_cross_file_duplicate_article_rows": 0,
        "normalized_rows": 0,
        "rows_with_section_name": 0,
        "date_min": None,
        "date_max": None,
    }
    seen_article_ids: set[str] = set()
    raw_rows = 0
    load_start = perf_counter()
    normalize_elapsed = 0.0
    progress_interval = 100
    normalized = _empty_normalized_dataframe()
    writer = None
    temp_path = None
    write_elapsed = 0.0
    try:
        with tempfile.NamedTemporaryFile(
            dir=config.normalized_path().parent,
            suffix=".parquet",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)

        for index, path in enumerate(raw_files, start=1):
            file_rows = read_jsonl(path)
            raw_rows += len(file_rows)
            stats["input_rows"] = int(stats["input_rows"]) + len(file_rows)
            if index == 1 or index % progress_interval == 0 or index == len(raw_files):
                print(
                    f"Loaded raw news file {index}/{len(raw_files)}: {path.name} "
                    f"(rows_in_file={len(file_rows)}, accumulated_rows={raw_rows})",
                    flush=True,
                )

            chunk_df = pd.DataFrame(file_rows)
            chunk_start = perf_counter()
            normalized_chunk, chunk_stats = _preprocess_news_dataframe_with_stats(
                raw_df=chunk_df,
                config=config,
                log_progress=False,
            )
            normalize_elapsed += perf_counter() - chunk_start
            for key in (
                "dropped_invalid_identity_rows",
                "dropped_unparseable_timestamp_rows",
                "dropped_empty_text_rows",
                "dropped_duplicate_article_rows",
                "rows_with_section_name",
            ):
                stats[key] = int(stats[key]) + int(chunk_stats.get(key, 0))

            if not normalized_chunk.empty:
                dedupe_mask = ~normalized_chunk["article_id"].isin(seen_article_ids)
                cross_file_dropped = int((~dedupe_mask).sum())
                stats["dropped_cross_file_duplicate_article_rows"] = int(
                    stats["dropped_cross_file_duplicate_article_rows"]
                ) + cross_file_dropped
                normalized_chunk = normalized_chunk.loc[dedupe_mask, normalized_columns].copy()

            if normalized_chunk.empty:
                continue

            seen_article_ids.update(normalized_chunk["article_id"].tolist())
            stats["normalized_rows"] = int(stats["normalized_rows"]) + len(normalized_chunk)
            chunk_date_min = str(normalized_chunk["date"].min())
            chunk_date_max = str(normalized_chunk["date"].max())
            stats["date_min"] = chunk_date_min if stats["date_min"] is None else min(str(stats["date_min"]), chunk_date_min)
            stats["date_max"] = chunk_date_max if stats["date_max"] is None else max(str(stats["date_max"]), chunk_date_max)

            normalized_chunk["tags"] = normalized_chunk["tags"].map(
                lambda value: [str(item) for item in (value or [])]
            )
            for column in normalized_columns:
                if column == "tags":
                    continue
                normalized_chunk[column] = normalized_chunk[column].where(
                    normalized_chunk[column].notna(), None
                )
            table = pa.Table.from_pandas(normalized_chunk[normalized_columns], preserve_index=False, schema=schema)
            if writer is None:
                writer = pq.ParquetWriter(temp_path, schema=table.schema)
            writer.write_table(table)

            if index == 1 or index % progress_interval == 0 or index == len(raw_files):
                print(
                    f"Preprocess progress {index}/{len(raw_files)}: "
                    f"normalized_rows={stats['normalized_rows']}, "
                    f"cross_file_dropped={stats['dropped_cross_file_duplicate_article_rows']}",
                    flush=True,
                )

        load_elapsed = perf_counter() - load_start
        print(
            f"Loaded {raw_rows} raw news rows in {load_elapsed:.1f}s. Normalizing and deduplicating...",
            flush=True,
        )
        print(f"Normalization completed in {normalize_elapsed:.1f}s. Writing parquet...", flush=True)
        write_start = perf_counter()
        if writer is not None and temp_path is not None:
            writer.close()
            writer = None
            temp_path.replace(config.normalized_path())
        else:
            normalized.to_parquet(config.normalized_path(), index=False)
        write_elapsed = perf_counter() - write_start
    finally:
        if writer is not None:
            writer.close()
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)

    update_manifest(
        config=config,
        normalized_articles=int(stats["normalized_rows"]),
        normalized_path=describe_path(config.normalized_path(), config=config),
    )
    print(
        "Preprocess summary: "
        f"input_rows={stats['input_rows']}, "
        f"dropped_invalid_identity={stats['dropped_invalid_identity_rows']}, "
        f"dropped_bad_timestamp={stats['dropped_unparseable_timestamp_rows']}, "
        f"dropped_empty_text={stats['dropped_empty_text_rows']}, "
        f"dropped_duplicates={stats['dropped_duplicate_article_rows']}",
        flush=True,
    )
    print(
        "Normalized dataset: "
        f"rows={stats['normalized_rows']}, "
        f"rows_with_section_name={stats['rows_with_section_name']}, "
        f"date_range={stats['date_min']} -> {stats['date_max']}",
        flush=True,
    )
    overall_elapsed = perf_counter() - overall_start
    print(
        f"Timing summary: load={load_elapsed:.1f}s, normalize={normalize_elapsed:.1f}s, "
        f"write={write_elapsed:.1f}s, total={overall_elapsed:.1f}s",
        flush=True,
    )
    print(f"Normalized {stats['normalized_rows']} news articles -> {config.normalized_path()}")
    return pd.read_parquet(config.normalized_path())


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize raw news JSONL into a parquet corpus.")
    parser.add_argument("--source", default=None, help="News source to preprocess (default: config default).")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    preprocess_news_exports(source=args.source)


if __name__ == "__main__":
    main()
