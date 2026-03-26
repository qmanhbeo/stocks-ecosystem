"""Merge daily news features into market dataframes."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from research_pipelines.news_features.config import NewsFeaturesConfig, get_default_config


def _feature_file_path(ticker: str, prediction_dir: Path) -> Path:
    return prediction_dir / f"{str(ticker).upper()}_news_features.parquet"


def merge_news_features(
    base_df: pd.DataFrame,
    ticker: str,
    prediction_dir: Optional[Path] = None,
    fill_strategy: str = "zeros",
    include_columns: Optional[Iterable[str]] = None,
    config: Optional[NewsFeaturesConfig] = None,
) -> pd.DataFrame:
    config = config or get_default_config()
    feature_root = Path(prediction_dir or config.predictions_dir)
    merged = base_df.copy()
    if "time" in merged.columns:
        merged["date"] = pd.to_datetime(merged["time"]).dt.strftime("%Y-%m-%d")
    elif "date" in merged.columns:
        merged["date"] = pd.to_datetime(merged["date"]).dt.strftime("%Y-%m-%d")
    else:
        raise ValueError("Base dataframe must include either 'time' or 'date'")

    columns = list(include_columns) if include_columns is not None else config.default_merge_columns()
    path = _feature_file_path(ticker, feature_root)
    fill_value = 0.0 if fill_strategy == "zeros" else config.missing_fill_value

    if not path.exists():
        for column in columns:
            merged[column] = fill_value
        return merged

    features = pd.read_parquet(path)
    if features.duplicated(subset=["date"]).any():
        duplicates = features.loc[features.duplicated(subset=["date"]), "date"].tolist()
        raise ValueError(f"Duplicate news feature dates found for {ticker}: {duplicates[:5]}")

    available_columns = ["date"] + [column for column in columns if column in features.columns]
    features = features[available_columns].copy()
    features["date"] = pd.to_datetime(features["date"]).dt.strftime("%Y-%m-%d")
    merged = merged.merge(features, on="date", how="left", validate="many_to_one")

    for column in columns:
        if column not in merged.columns:
            merged[column] = fill_value
        else:
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(fill_value)
    return merged
