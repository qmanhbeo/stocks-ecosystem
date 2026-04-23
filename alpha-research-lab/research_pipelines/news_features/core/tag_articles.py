"""Tag normalized news articles to stock tickers."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
from time import perf_counter
import tempfile
from typing import Dict, Iterable, List, Optional

import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.io_utils import describe_path, discover_stock_tickers, update_manifest


def _ticker_pattern(tickers: Iterable[str]) -> Optional[re.Pattern[str]]:
    values = sorted({str(ticker).upper() for ticker in tickers if str(ticker).strip()}, key=len, reverse=True)
    if not values:
        return None
    joined = "|".join(re.escape(value) for value in values)
    return re.compile(rf"(?<![A-Z0-9])({joined})(?![A-Z0-9])")


def tag_articles_dataframe(
    normalized_df: pd.DataFrame,
    tickers: Iterable[str],
    log_progress: bool = False,
    progress_every_articles: int = 50000,
) -> pd.DataFrame:
    pattern = _ticker_pattern(tickers)
    return _tag_articles_dataframe_with_pattern(
        normalized_df=normalized_df,
        pattern=pattern,
        tickers=tickers,
        log_progress=log_progress,
        progress_every_articles=progress_every_articles,
    )


def _tag_articles_dataframe_with_pattern(
    normalized_df: pd.DataFrame,
    pattern: Optional[re.Pattern[str]],
    tickers: Iterable[str],
    log_progress: bool = False,
    progress_every_articles: int = 50000,
) -> pd.DataFrame:
    if pattern is None or normalized_df.empty:
        return pd.DataFrame(
            columns=["article_id", "ticker", "date", "url", "source", "match_source", "title_hit", "body_hit"]
        )

    total_articles = int(len(normalized_df))
    progress_interval = max(int(progress_every_articles), 1)
    if log_progress:
        ticker_count = len({str(ticker).upper() for ticker in tickers if str(ticker).strip()})
        print(
            f"Tagging {total_articles} normalized articles against {ticker_count} ticker symbols",
            flush=True,
        )

    rows: List[Dict[str, object]] = []
    matched_articles = 0
    for article_index, article in enumerate(normalized_df.to_dict(orient="records"), start=1):
        title_text = str(article.get("clean_title", "")).upper()
        body_text = " ".join(
            part for part in [article.get("clean_summary", ""), article.get("clean_body_text", "")] if part
        ).upper()
        title_hits = set(pattern.findall(title_text))
        body_hits = set(pattern.findall(body_text))
        article_tickers = sorted(title_hits | body_hits)
        if article_tickers:
            matched_articles += 1
        for ticker in article_tickers:
            title_hit = int(ticker in title_hits)
            body_hit = int(ticker in body_hits)
            rows.append(
                {
                    "article_id": article["article_id"],
                    "ticker": ticker,
                    "date": article["date"],
                    "url": article["url"],
                    "source": article["source"],
                    "match_source": "title" if title_hit else "body",
                    "title_hit": title_hit,
                    "body_hit": body_hit,
                }
            )
        if log_progress and (
            article_index == 1
            or article_index % progress_interval == 0
            or article_index == total_articles
        ):
            print(
                f"Tagged article scan {article_index}/{total_articles}; "
                f"matched_articles={matched_articles}, accumulated_article_ticker_rows={len(rows)}",
                flush=True,
            )
    tagged = pd.DataFrame(rows)
    if tagged.empty:
        if log_progress:
            print("Tagging complete: no ticker matches found in normalized articles", flush=True)
        return tagged.reindex(
            columns=["article_id", "ticker", "date", "url", "source", "match_source", "title_hit", "body_hit"]
        )
    before_dedup_rows = int(len(tagged))
    tagged = tagged.drop_duplicates(subset=["article_id", "ticker"], keep="first")
    deduped = tagged.sort_values(["ticker", "date", "article_id"]).reset_index(drop=True)
    if log_progress:
        print(
            "Tagging summary: "
            f"article_ticker_rows={len(deduped)}, "
            f"matched_articles={matched_articles}, "
            f"unique_tickers={deduped['ticker'].nunique()}, "
            f"dropped_duplicate_pairs={before_dedup_rows - len(deduped)}",
            flush=True,
        )
    return deduped


def tag_articles_exports(config: Optional[NewsFeaturesConfig] = None) -> pd.DataFrame:
    config = config or get_default_config()
    config.ensure_directories()
    overall_start = perf_counter()
    load_start = perf_counter()
    if not config.normalized_path().exists():
        return pd.DataFrame(
            columns=["article_id", "ticker", "date", "url", "source", "match_source", "title_hit", "body_hit"]
        )

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Streaming ticker tagging requires pyarrow.") from exc

    parquet_file = pq.ParquetFile(config.normalized_path())
    normalized_rows = parquet_file.metadata.num_rows
    load_elapsed = perf_counter() - load_start
    tickers = discover_stock_tickers(config=config)
    pattern = _ticker_pattern(tickers)
    print(
        f"Loaded {normalized_rows} normalized articles from {config.normalized_path()} in {load_elapsed:.1f}s",
        flush=True,
    )
    print(f"Discovered {len(tickers)} stock tickers from {config.raw_stock_dir}", flush=True)

    tagged_columns = ["article_id", "ticker", "date", "url", "source", "match_source", "title_hit", "body_hit"]
    schema = pa.schema(
        [
            ("article_id", pa.string()),
            ("ticker", pa.string()),
            ("date", pa.string()),
            ("url", pa.string()),
            ("source", pa.string()),
            ("match_source", pa.string()),
            ("title_hit", pa.int64()),
            ("body_hit", pa.int64()),
        ]
    )
    tag_start = perf_counter()
    writer = None
    temp_path = None
    total_tagged_rows = 0
    processed_articles = 0
    progress_interval = 50000
    try:
        with tempfile.NamedTemporaryFile(
            dir=config.tagged_path().parent,
            suffix=".parquet",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)

        for batch in parquet_file.iter_batches(
            batch_size=5000,
            columns=["article_id", "date", "url", "source", "clean_title", "clean_summary", "clean_body_text"],
        ):
            batch_df = batch.to_pandas()
            processed_articles += len(batch_df)
            tagged_batch = _tag_articles_dataframe_with_pattern(
                normalized_df=batch_df,
                pattern=pattern,
                tickers=tickers,
                log_progress=False,
            )
            if not tagged_batch.empty:
                table = pa.Table.from_pandas(tagged_batch[tagged_columns], preserve_index=False, schema=schema)
                if writer is None:
                    writer = pq.ParquetWriter(temp_path, schema=table.schema)
                writer.write_table(table)
                total_tagged_rows += len(tagged_batch)
            if (
                processed_articles == len(batch_df)
                or processed_articles % progress_interval == 0
                or processed_articles >= normalized_rows
            ):
                print(
                    f"Tagged article scan {processed_articles}/{normalized_rows}; "
                    f"accumulated_article_ticker_rows={total_tagged_rows}",
                    flush=True,
                )

        tag_elapsed = perf_counter() - tag_start
        print(f"Ticker tagging completed in {tag_elapsed:.1f}s. Writing parquet...", flush=True)
        write_start = perf_counter()
        if writer is not None and temp_path is not None:
            writer.close()
            writer = None
            temp_path.replace(config.tagged_path())
        else:
            pd.DataFrame(columns=tagged_columns).to_parquet(config.tagged_path(), index=False)
        write_elapsed = perf_counter() - write_start
    finally:
        if writer is not None:
            writer.close()
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)

    update_manifest(
        config=config,
        tagged_articles=int(total_tagged_rows),
        tagged_path=describe_path(config.tagged_path(), config=config),
    )
    overall_elapsed = perf_counter() - overall_start
    print(
        f"Timing summary: load={load_elapsed:.1f}s, tag={tag_elapsed:.1f}s, "
        f"write={write_elapsed:.1f}s, total={overall_elapsed:.1f}s",
        flush=True,
    )
    print(f"Tagged {total_tagged_rows} article-ticker rows -> {config.tagged_path()}")
    return pd.read_parquet(config.tagged_path())


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Tag normalized news articles to stock tickers.")


def main() -> None:
    build_arg_parser().parse_args()
    tag_articles_exports()


if __name__ == "__main__":
    main()
