"""Join tabular and embedding features into RL-ready daily exports."""

from __future__ import annotations

import argparse
from time import perf_counter
from typing import Optional, Sequence

import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config
from research_pipelines.news_features.io_utils import describe_path, update_manifest, write_parquet_atomic


AGGREGATE_SOURCE_CHOICES = ("tabular", "embedding", "phobert", "phobert_forward_looking")


def _news_feature_filename(ticker: str) -> str:
    return f"{str(ticker).upper()}_news_features.parquet"


def _normalize_requested_sources(sources: Optional[Sequence[str]]) -> tuple[str, ...]:
    if sources is None:
        return AGGREGATE_SOURCE_CHOICES
    normalized = tuple(str(source).strip().lower() for source in sources if str(source).strip())
    unknown = sorted(set(normalized) - set(AGGREGATE_SOURCE_CHOICES))
    if unknown:
        raise ValueError(f"Unknown aggregate sources: {unknown}")
    if not normalized:
        raise ValueError("At least one aggregate source must be requested")
    return normalized


def _source_merge_columns(source: str, config: NewsFeaturesConfig) -> list[str]:
    if source == "tabular":
        return [
            "news_article_count_1d",
            "news_title_len_mean",
            "news_body_len_mean",
            "news_articles_with_title_hit",
            "news_articles_with_body_hit",
            "news_unique_urls_1d",
            "news_sentiment_keyword_score_sum",
            "news_sentiment_keyword_score_mean",
            *(f"news_article_count_{window}d" for window in config.rolling_windows),
        ]
    if source == "embedding":
        return list(config.embedding_columns())
    if source == "phobert":
        return list(config.phobert_daily_columns())
    if source == "phobert_forward_looking":
        return list(config.phobert_forward_looking_daily_columns())
    raise ValueError(f"Unknown aggregate source: {source}")


def _load_source_frame(source: str, config: NewsFeaturesConfig) -> pd.DataFrame:
    if source == "tabular" and config.tabular_dataset_path().exists():
        return pd.read_parquet(config.tabular_dataset_path())
    if source == "embedding" and config.embedding_dataset_path().exists():
        return pd.read_parquet(config.embedding_dataset_path())
    if source == "phobert" and config.phobert_ticker_day_sentiment_path().exists():
        return pd.read_parquet(config.phobert_ticker_day_sentiment_path())
    if source == "phobert_forward_looking" and config.phobert_forward_looking_ticker_day_features_path().exists():
        return pd.read_parquet(config.phobert_forward_looking_ticker_day_features_path())
    return pd.DataFrame()


def _ensure_full_merge_schema(
    combined: pd.DataFrame,
    config: NewsFeaturesConfig,
    log_progress: bool = False,
) -> pd.DataFrame:
    ordered_columns = ["ticker", "date", *config.default_merge_columns()]
    missing_columns = [column for column in ordered_columns if column not in combined.columns]
    if missing_columns:
        if log_progress:
            print(
                f"Aggregate schema fill: adding {len(missing_columns)} missing columns with "
                f"default={config.missing_fill_value}",
                flush=True,
            )
        for column in missing_columns:
            if column in {"ticker", "date"}:
                combined[column] = None
            else:
                combined[column] = config.missing_fill_value
    extra_columns = [column for column in combined.columns if column not in ordered_columns]
    return combined[ordered_columns + extra_columns]


def _coerce_numeric_feature_columns(combined: pd.DataFrame, config: NewsFeaturesConfig) -> pd.DataFrame:
    numeric_columns = [column for column in combined.columns if column not in {"ticker", "date"}]
    for column in numeric_columns:
        combined[column] = pd.to_numeric(combined[column], errors="coerce").fillna(config.missing_fill_value)
    return combined


def _finalize_combined_dataframe(
    combined: pd.DataFrame,
    *,
    config: NewsFeaturesConfig,
    log_progress: bool = False,
) -> pd.DataFrame:
    if combined.empty:
        return _ensure_full_merge_schema(
            pd.DataFrame(columns=["ticker", "date", *config.default_merge_columns()]),
            config=config,
            log_progress=log_progress,
        )
    combined = combined.sort_values(["ticker", "date"]).reset_index(drop=True)
    combined = _coerce_numeric_feature_columns(combined, config=config)
    if log_progress:
        date_min = str(combined["date"].min()) if not combined.empty else None
        date_max = str(combined["date"].max()) if not combined.empty else None
        print(
            f"Aggregate summary: rows={len(combined)}, unique_tickers={combined['ticker'].nunique()}, "
            f"numeric_columns={len([column for column in combined.columns if column not in {'ticker', 'date'}])}, "
            f"date_range={date_min} -> {date_max}",
            flush=True,
        )
    return _ensure_full_merge_schema(combined, config=config, log_progress=log_progress)


def _overlay_requested_sources_on_existing(
    existing_combined: pd.DataFrame,
    source_frames: dict[str, pd.DataFrame],
    *,
    config: NewsFeaturesConfig,
    log_progress: bool = False,
) -> pd.DataFrame:
    combined = existing_combined.copy()
    for source, frame in source_frames.items():
        source_columns = _source_merge_columns(source, config)
        overlay = frame.copy()
        if not overlay.empty:
            for column in source_columns:
                if column not in overlay.columns:
                    overlay[column] = config.missing_fill_value
            overlay = overlay[["ticker", "date", *source_columns]]
            overlay = overlay.rename(columns={column: f"__overlay__{column}" for column in source_columns})
        elif log_progress:
            print(f"Aggregate overlay: requested source={source} has no rows; clearing stale values", flush=True)

        if combined.empty:
            if overlay.empty:
                combined = pd.DataFrame(columns=["ticker", "date", *source_columns])
            else:
                combined = overlay.rename(columns={f"__overlay__{column}": column for column in source_columns})
                if log_progress:
                    print(
                        f"Aggregate overlay applied for source={source}: rows={len(combined)}, "
                        f"source_rows={len(frame)}",
                        flush=True,
                    )
                continue
        else:
            combined = combined.merge(overlay, on=["ticker", "date"], how="outer") if not overlay.empty else combined.copy()

        for column in source_columns:
            overlay_column = f"__overlay__{column}"
            if overlay_column in combined.columns:
                combined[column] = pd.to_numeric(combined[overlay_column], errors="coerce").fillna(config.missing_fill_value)
                combined = combined.drop(columns=[overlay_column])
            else:
                combined[column] = config.missing_fill_value

        if log_progress:
            print(
                f"Aggregate overlay applied for source={source}: rows={len(combined)}, "
                f"source_rows={len(frame)}",
                flush=True,
            )
    return _finalize_combined_dataframe(combined, config=config, log_progress=log_progress)


def aggregate_daily_feature_dataframe(
    tabular_df: pd.DataFrame,
    embedding_df: pd.DataFrame,
    phobert_df: Optional[pd.DataFrame] = None,
    phobert_forward_looking_df: Optional[pd.DataFrame] = None,
    config: Optional[NewsFeaturesConfig] = None,
    log_progress: bool = False,
) -> pd.DataFrame:
    config = config or get_default_config()
    phobert_df = phobert_df if phobert_df is not None else pd.DataFrame()
    phobert_forward_looking_df = (
        phobert_forward_looking_df if phobert_forward_looking_df is not None else pd.DataFrame()
    )
    if tabular_df.empty and embedding_df.empty and phobert_df.empty and phobert_forward_looking_df.empty:
        if log_progress:
            print(
                "Aggregate build skipped because tabular, embedding, PhoBERT, and forward-looking datasets are empty",
                flush=True,
            )
        return pd.DataFrame(columns=["ticker", "date", *config.default_merge_columns()])

    datasets = [
        ("tabular", tabular_df),
        ("embedding", embedding_df),
        ("phobert", phobert_df),
        ("phobert_forward_looking", phobert_forward_looking_df),
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

    if log_progress:
        print(
            f"Aggregate stage 1/2 complete: combined_rows={len(combined)}, unique_tickers={combined['ticker'].nunique()}",
            flush=True,
        )
        print("Aggregate stage 2/2: coercing numeric columns and filling missing values", flush=True)
    return _finalize_combined_dataframe(combined, config=config, log_progress=log_progress)


def aggregate_daily_feature_exports(
    config: Optional[NewsFeaturesConfig] = None,
    sources: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    config = config or get_default_config()
    requested_sources = _normalize_requested_sources(sources)
    overall_start = perf_counter()
    load_start = perf_counter()
    source_frames = {source: _load_source_frame(source, config) for source in requested_sources}
    load_elapsed = perf_counter() - load_start
    print(
        "Loaded requested_sources="
        f"{requested_sources}, "
        + ", ".join(f"{source}_rows={len(frame)}" for source, frame in source_frames.items())
        + f" in {load_elapsed:.1f}s",
        flush=True,
    )
    aggregate_start = perf_counter()
    if (
        config.combined_dataset_path().exists()
        and set(requested_sources) != set(AGGREGATE_SOURCE_CHOICES)
    ):
        existing_combined = pd.read_parquet(config.combined_dataset_path())
        print(
            f"Loaded existing combined dataset rows={len(existing_combined)} for partial overlay refresh",
            flush=True,
        )
        combined = _overlay_requested_sources_on_existing(
            existing_combined,
            source_frames,
            config=config,
            log_progress=True,
        )
    else:
        combined = aggregate_daily_feature_dataframe(
            source_frames.get("tabular", pd.DataFrame()),
            source_frames.get("embedding", pd.DataFrame()),
            phobert_df=source_frames.get("phobert", pd.DataFrame()),
            phobert_forward_looking_df=source_frames.get("phobert_forward_looking", pd.DataFrame()),
            config=config,
            log_progress=True,
        )
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
    parser = argparse.ArgumentParser(description="Aggregate daily news features for RL consumption.")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=AGGREGATE_SOURCE_CHOICES,
        default=list(AGGREGATE_SOURCE_CHOICES),
        help=(
            "Feature families to publish. Use '--sources phobert' for a light refresh that "
            "publishes RL-ready exports from the existing PhoBERT ticker-day dataset only."
        ),
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    aggregate_daily_feature_exports(sources=args.sources)


if __name__ == "__main__":
    main()
