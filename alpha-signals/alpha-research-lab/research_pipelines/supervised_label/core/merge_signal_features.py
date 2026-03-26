"""Merge supervised signal probabilities into market dataframes."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from research_pipelines.supervised_label.config import SupervisedLabelConfig, get_default_config


def _prediction_file_path(ticker: str, prediction_dir: Path) -> Path:
    return prediction_dir / f"{str(ticker).upper()}_signal_predictions.parquet"


def merge_signal_features(
    base_df: pd.DataFrame,
    ticker: str,
    prediction_dir: Optional[Path] = None,
    fill_value: Optional[float] = None,
    config: Optional[SupervisedLabelConfig] = None,
) -> pd.DataFrame:
    config = config or get_default_config()
    prediction_root = Path(prediction_dir or config.predictions_dir)
    merged = base_df.copy()
    if "time" in merged.columns:
        merged["date"] = pd.to_datetime(merged["time"]).dt.strftime("%Y-%m-%d")
    elif "date" in merged.columns:
        merged["date"] = pd.to_datetime(merged["date"]).dt.strftime("%Y-%m-%d")
    else:
        raise ValueError("Base dataframe must include either 'time' or 'date'")

    path = _prediction_file_path(ticker, prediction_root)
    fill = config.missing_signal_fill_value if fill_value is None else float(fill_value)

    if not path.exists():
        merged[config.prediction_column] = fill
        merged[config.prediction_label_column] = 0
        return merged

    predictions = pd.read_parquet(path)
    if predictions["date"].duplicated().any():
        duplicates = predictions.loc[predictions["date"].duplicated(), "date"].tolist()
        raise ValueError(f"Duplicate prediction dates found for {ticker}: {duplicates[:5]}")

    predictions["date"] = pd.to_datetime(predictions["date"]).dt.strftime("%Y-%m-%d")
    merged = merged.merge(predictions, on="date", how="left", validate="many_to_one")
    merged[config.prediction_column] = merged[config.prediction_column].fillna(fill)
    if config.prediction_label_column in merged.columns:
        merged[config.prediction_label_column] = merged[config.prediction_label_column].fillna(0).astype(int)
    return merged
