"""Build tabular daily news features from tagged articles."""

from __future__ import annotations

import argparse
from time import perf_counter
from typing import Optional

import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.io_utils import describe_path, load_feature_spec, update_manifest


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
        columns = ["ticker", "date"] + config.default_merge_columns()[: 8 + len(config.rolling_windows)]
        return pd.DataFrame(columns=columns)

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
    ordered.extend(f"news_article_count_{int(window)}d" for window in rolling_windows)
    result = combined[ordered].sort_values(["ticker", "date"]).reset_index(drop=True)
    if log_progress:
        print(
            f"Tabular summary: rows={len(result)}, unique_tickers={result['ticker'].nunique()}, "
            f"date_range={result['date'].min()} -> {result['date'].max()}",
            flush=True,
        )
    return result


def build_tabular_feature_exports(config: Optional[NewsFeaturesConfig] = None) -> pd.DataFrame:
    config = config or get_default_config()
    overall_start = perf_counter()
    load_start = perf_counter()
    normalized = pd.read_parquet(config.normalized_path()) if config.normalized_path().exists() else pd.DataFrame()
    tagged = pd.read_parquet(config.tagged_path()) if config.tagged_path().exists() else pd.DataFrame()
    load_elapsed = perf_counter() - load_start
    print(
        f"Loaded normalized_rows={len(normalized)} and tagged_rows={len(tagged)} in {load_elapsed:.1f}s",
        flush=True,
    )
    build_start = perf_counter()
    tabular = build_tabular_feature_dataframe(normalized, tagged, config=config, log_progress=True)
    build_elapsed = perf_counter() - build_start
    print(f"Tabular feature build completed in {build_elapsed:.1f}s. Writing parquet...", flush=True)
    write_start = perf_counter()
    tabular.to_parquet(config.tabular_dataset_path(), index=False)
    write_elapsed = perf_counter() - write_start
    update_manifest(
        config=config,
        tabular_feature_rows=int(len(tabular)),
        tabular_dataset_path=describe_path(config.tabular_dataset_path(), config=config),
    )
    overall_elapsed = perf_counter() - overall_start
    print(
        f"Timing summary: load={load_elapsed:.1f}s, build={build_elapsed:.1f}s, "
        f"write={write_elapsed:.1f}s, total={overall_elapsed:.1f}s",
        flush=True,
    )
    print(f"Built {len(tabular)} tabular feature rows -> {config.tabular_dataset_path()}")
    return tabular


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Build daily tabular news features.")


def main() -> None:
    build_arg_parser().parse_args()
    build_tabular_feature_exports()


if __name__ == "__main__":
    main()
