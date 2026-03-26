"""Tag normalized news articles to stock tickers."""

from __future__ import annotations

import argparse
import re
from time import perf_counter
from typing import Dict, Iterable, List, Optional

import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.io_utils import discover_stock_tickers, update_manifest


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
    overall_start = perf_counter()
    load_start = perf_counter()
    normalized = pd.read_parquet(config.normalized_path()) if config.normalized_path().exists() else pd.DataFrame()
    load_elapsed = perf_counter() - load_start
    tickers = discover_stock_tickers(config=config)
    print(
        f"Loaded {len(normalized)} normalized articles from {config.normalized_path()} in {load_elapsed:.1f}s",
        flush=True,
    )
    print(f"Discovered {len(tickers)} stock tickers from {config.raw_stock_dir}", flush=True)
    tag_start = perf_counter()
    tagged = tag_articles_dataframe(normalized, tickers, log_progress=True)
    tag_elapsed = perf_counter() - tag_start
    print(f"Ticker tagging completed in {tag_elapsed:.1f}s. Writing parquet...", flush=True)
    write_start = perf_counter()
    tagged.to_parquet(config.tagged_path(), index=False)
    write_elapsed = perf_counter() - write_start
    update_manifest(
        config=config,
        tagged_articles=int(len(tagged)),
        tagged_path=str(config.tagged_path().relative_to(config.repo_root)),
    )
    overall_elapsed = perf_counter() - overall_start
    print(
        f"Timing summary: load={load_elapsed:.1f}s, tag={tag_elapsed:.1f}s, "
        f"write={write_elapsed:.1f}s, total={overall_elapsed:.1f}s",
        flush=True,
    )
    print(f"Tagged {len(tagged)} article-ticker rows -> {config.tagged_path()}")
    return tagged


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Tag normalized news articles to stock tickers.")


def main() -> None:
    build_arg_parser().parse_args()
    tag_articles_exports()


if __name__ == "__main__":
    main()
