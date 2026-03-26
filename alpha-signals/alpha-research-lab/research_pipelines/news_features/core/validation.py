"""Validation helpers for news feature artifacts."""

from __future__ import annotations

import argparse

import pandas as pd

from research_pipelines.news_features.config import get_default_config
from research_pipelines.news_features.io_utils import discover_stock_tickers


def validate_normalized_dataframe(df: pd.DataFrame) -> None:
    required = {"article_id", "source", "url", "clean_title", "clean_body_text", "published_at", "date"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Normalized dataframe missing columns: {sorted(missing)}")
    if df["article_id"].duplicated().any():
        raise ValueError("Normalized dataframe contains duplicate article_id values")


def validate_tagged_dataframe(df: pd.DataFrame) -> None:
    required = {"article_id", "ticker", "date", "match_source", "title_hit", "body_hit"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Tagged dataframe missing columns: {sorted(missing)}")
    if df.duplicated(subset=["article_id", "ticker"]).any():
        raise ValueError("Tagged dataframe contains duplicate article_id/ticker rows")


def validate_news_artifacts() -> None:
    config = get_default_config()
    normalized = pd.read_parquet(config.normalized_path()) if config.normalized_path().exists() else pd.DataFrame()
    tagged = pd.read_parquet(config.tagged_path()) if config.tagged_path().exists() else pd.DataFrame()
    validate_normalized_dataframe(normalized)
    validate_tagged_dataframe(tagged)
    known_tickers = set(discover_stock_tickers(config=config))
    unknown = sorted(set(tagged["ticker"]) - known_tickers)
    if unknown:
        raise ValueError(f"Tagged dataframe contains unknown tickers: {unknown[:10]}")
    print("News feature artifacts are valid.")


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Validate news feature artifacts.")


def main() -> None:
    build_arg_parser().parse_args()
    validate_news_artifacts()


if __name__ == "__main__":
    main()
