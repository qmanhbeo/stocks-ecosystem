"""Join tabular and embedding features into RL-ready daily exports."""

from __future__ import annotations

import argparse
from time import perf_counter
from typing import Optional

import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.io_utils import describe_path, update_manifest, write_parquet_atomic


def _news_feature_filename(ticker: str) -> str:
    return f"{str(ticker).upper()}_news_features.parquet"


def aggregate_daily_feature_dataframe(
    tabular_df: pd.DataFrame,
    embedding_df: pd.DataFrame,
    phobert_df: Optional[pd.DataFrame] = None,
    config: Optional[NewsFeaturesConfig] = None,
    log_progress: bool = False,
) -> pd.DataFrame:
    config = config or get_default_config()
    phobert_df = phobert_df if phobert_df is not None else pd.DataFrame()
    if tabular_df.empty and embedding_df.empty and phobert_df.empty:
        if log_progress:
            print("Aggregate build skipped because tabular, embedding, and PhoBERT datasets are empty", flush=True)
        return pd.DataFrame(columns=["ticker", "date", *config.default_merge_columns()])

    datasets = [
        ("tabular", tabular_df),
        ("embedding", embedding_df),
        ("phobert", phobert_df),
    ]
    available = [(name, frame.copy()) for name, frame in datasets if not frame.empty]
    if log_progress:
        summary = ", ".join(f"{name}_rows={len(frame)}" for name, frame in available) or "none"
        print(f"Aggregate stage 1/2: merging available datasets ({summary})", flush=True)

    for name, frame in available:
        if frame.duplicated(subset=["ticker", "date"]).any():
            raise ValueError(f"Duplicate ticker/date rows found in {name} news features")

    combined = available[0][1].copy()
    for name, frame in available[1:]:
        combined = combined.merge(frame, on=["ticker", "date"], how="outer", validate="one_to_one")

    combined = combined.sort_values(["ticker", "date"]).reset_index(drop=True)
    if log_progress:
        print(
            f"Aggregate stage 1/2 complete: combined_rows={len(combined)}, unique_tickers={combined['ticker'].nunique()}",
            flush=True,
        )
        print("Aggregate stage 2/2: coercing numeric columns and filling missing values", flush=True)
    numeric_columns = [column for column in combined.columns if column not in {"ticker", "date"}]
    for column in numeric_columns:
        combined[column] = pd.to_numeric(combined[column], errors="coerce").fillna(config.missing_fill_value)
    if log_progress:
        date_min = str(combined["date"].min()) if not combined.empty else None
        date_max = str(combined["date"].max()) if not combined.empty else None
        print(
            f"Aggregate summary: rows={len(combined)}, unique_tickers={combined['ticker'].nunique()}, "
            f"numeric_columns={len(numeric_columns)}, date_range={date_min} -> {date_max}",
            flush=True,
        )
    return combined


def aggregate_daily_feature_exports(config: Optional[NewsFeaturesConfig] = None) -> pd.DataFrame:
    config = config or get_default_config()
    overall_start = perf_counter()
    load_start = perf_counter()
    tabular = pd.read_parquet(config.tabular_dataset_path()) if config.tabular_dataset_path().exists() else pd.DataFrame()
    embedding = pd.read_parquet(config.embedding_dataset_path()) if config.embedding_dataset_path().exists() else pd.DataFrame()
    phobert = (
        pd.read_parquet(config.phobert_ticker_day_sentiment_path())
        if config.phobert_ticker_day_sentiment_path().exists()
        else pd.DataFrame()
    )
    load_elapsed = perf_counter() - load_start
    print(
        f"Loaded tabular_rows={len(tabular)}, embedding_rows={len(embedding)}, "
        f"phobert_rows={len(phobert)} in {load_elapsed:.1f}s",
        flush=True,
    )
    aggregate_start = perf_counter()
    combined = aggregate_daily_feature_dataframe(tabular, embedding, phobert_df=phobert, config=config, log_progress=True)
    aggregate_elapsed = perf_counter() - aggregate_start
    print(f"Aggregate build completed in {aggregate_elapsed:.1f}s. Writing outputs...", flush=True)
    write_start = perf_counter()
    write_parquet_atomic(combined, config.combined_dataset_path(), index=False)
    existing_prediction_files = {
        path.name: path
        for path in config.predictions_dir.glob("*_news_features.parquet")
        if path.is_file()
    }
    ticker_groups = list(combined.groupby("ticker", sort=True))
    total_tickers = len(ticker_groups)
    progress_interval = 1 if total_tickers <= 10 else 10
    written_filenames: set[str] = set()
    for ticker_index, (ticker, group) in enumerate(ticker_groups, start=1):
        filename = _news_feature_filename(str(ticker))
        written_filenames.add(filename)
        group.to_parquet(config.per_ticker_feature_path(str(ticker)), index=False)
        if ticker_index == 1 or ticker_index % progress_interval == 0 or ticker_index == total_tickers:
            print(
                f"Wrote per-ticker aggregate file {ticker_index}/{total_tickers}: {ticker}",
                flush=True,
            )
    for filename, path in sorted(existing_prediction_files.items()):
        if filename in written_filenames:
            continue
        path.unlink()
    write_elapsed = perf_counter() - write_start
    update_manifest(
        config=config,
        combined_feature_rows=int(len(combined)),
        combined_dataset_path=describe_path(config.combined_dataset_path(), config=config),
    )
    overall_elapsed = perf_counter() - overall_start
    print(
        f"Timing summary: load={load_elapsed:.1f}s, aggregate={aggregate_elapsed:.1f}s, "
        f"write={write_elapsed:.1f}s, total={overall_elapsed:.1f}s",
        flush=True,
    )
    print(f"Aggregated {len(combined)} combined news feature rows -> {config.combined_dataset_path()}")
    return combined


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Aggregate daily news features for RL consumption.")


def main() -> None:
    build_arg_parser().parse_args()
    aggregate_daily_feature_exports()


if __name__ == "__main__":
    main()
