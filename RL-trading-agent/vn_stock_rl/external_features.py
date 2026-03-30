"""Shared research export contracts consumed by the RL runtime."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = REPO_ROOT.parent.parent
SHARED_RECOMMENDATION_ROOT = WORKSPACE_ROOT / "shared-recommendation"
if str(SHARED_RECOMMENDATION_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_RECOMMENDATION_ROOT))

from shared_recommendation.artifacts import (
    default_help_assets_dir as shared_default_help_assets_dir,
    default_lab_signal_matrix_path as shared_default_lab_signal_matrix_path,
    default_lab_signal_prediction_dir as shared_default_lab_signal_prediction_dir,
    default_market_data_dir as shared_default_market_data_dir,
    default_news_prediction_dir as shared_default_news_prediction_dir,
    default_signal_prediction_dir as shared_default_signal_prediction_dir,
    default_stock_data_dir as shared_default_stock_data_dir,
    shared_data_root as shared_shared_data_root,
)

DEFAULT_NEWS_ROLLING_WINDOWS = (3, 5)
DEFAULT_NEWS_EMBEDDING_DIM = 16
SIGNAL_MISSING_FILL_VALUE = 0.5
SIGNAL_PREDICTION_COLUMN = "signal_prob_buyhold"
SIGNAL_SMOOTHED_COLUMN = "smoothed_signal_prob"
SIGNAL_LOGIT_COLUMN = "signal_logit"
SIGNAL_LABEL_COLUMN = "signal_pred_label"


def shared_data_root() -> Path:
    return shared_shared_data_root()


def default_stock_data_dir() -> Path:
    return shared_default_stock_data_dir()


def default_market_data_dir() -> Path:
    return shared_default_market_data_dir()


def default_help_assets_dir() -> Path:
    return shared_default_help_assets_dir()


def default_news_prediction_dir() -> Path:
    return shared_default_news_prediction_dir()


def default_signal_prediction_dir() -> Path:
    return shared_default_signal_prediction_dir()


def default_lab_signal_matrix_path() -> Path:
    return shared_default_lab_signal_matrix_path()


def default_lab_signal_prediction_dir() -> Path:
    return shared_default_lab_signal_prediction_dir()


def default_news_feature_columns() -> List[str]:
    columns = [
        "news_article_count_1d",
        "news_title_len_mean",
        "news_body_len_mean",
        "news_articles_with_title_hit",
        "news_articles_with_body_hit",
        "news_unique_urls_1d",
        "news_sentiment_keyword_score_sum",
        "news_sentiment_keyword_score_mean",
    ]
    columns.extend(f"news_article_count_{window}d" for window in DEFAULT_NEWS_ROLLING_WINDOWS)
    columns.extend(f"news_embed_{index:02d}" for index in range(DEFAULT_NEWS_EMBEDDING_DIM))
    return columns


def default_tabular_news_feature_columns() -> List[str]:
    return [column for column in default_news_feature_columns() if not column.startswith("news_embed_")]


def default_signal_feature_columns() -> List[str]:
    return [SIGNAL_PREDICTION_COLUMN, SIGNAL_SMOOTHED_COLUMN]


def all_signal_feature_columns() -> List[str]:
    return [
        SIGNAL_PREDICTION_COLUMN,
        SIGNAL_SMOOTHED_COLUMN,
        SIGNAL_LOGIT_COLUMN,
        SIGNAL_LABEL_COLUMN,
    ]


def resolve_news_feature_config(
    configured_columns: Optional[List[str]],
    prediction_dir: Optional[str],
) -> Tuple[List[str], Optional[str]]:
    if configured_columns is None:
        return [], prediction_dir

    columns = [str(column).strip() for column in configured_columns if str(column).strip()]
    resolved_dir = prediction_dir or str(default_news_prediction_dir())
    if not columns:
        return [], resolved_dir
    return columns, resolved_dir


def resolve_signal_feature_config(
    configured_columns: Optional[List[str]],
    prediction_dir: Optional[str],
) -> Tuple[List[str], Optional[str]]:
    if configured_columns is None:
        return [], prediction_dir

    columns = [str(column).strip() for column in configured_columns if str(column).strip()]
    resolved_dir = prediction_dir or str(default_signal_prediction_dir())
    if not columns:
        return [], resolved_dir
    return columns, resolved_dir


def merge_news_features(
    base_df,
    ticker: str,
    prediction_dir: Optional[Path] = None,
    include_columns: Optional[Iterable[str]] = None,
) :
    import pandas as pd

    merged = base_df.copy()
    if "time" in merged.columns:
        merged["date"] = pd.to_datetime(merged["time"]).dt.strftime("%Y-%m-%d")
    elif "date" in merged.columns:
        merged["date"] = pd.to_datetime(merged["date"]).dt.strftime("%Y-%m-%d")
    else:
        raise ValueError("Base dataframe must include either 'time' or 'date'")

    columns = list(include_columns) if include_columns is not None else default_news_feature_columns()
    feature_path = Path(prediction_dir or default_news_prediction_dir()) / f"{str(ticker).upper()}_news_features.parquet"
    if not feature_path.exists():
        for column in columns:
            merged[column] = 0.0
        return merged

    features = pd.read_parquet(feature_path)
    if features.duplicated(subset=["date"]).any():
        duplicates = features.loc[features.duplicated(subset=["date"]), "date"].tolist()
        raise ValueError(f"Duplicate news feature dates found for {ticker}: {duplicates[:5]}")

    available_columns = ["date"] + [column for column in columns if column in features.columns]
    features = features[available_columns].copy()
    features["date"] = pd.to_datetime(features["date"]).dt.strftime("%Y-%m-%d")
    merged = merged.merge(features, on="date", how="left", validate="many_to_one")

    for column in columns:
        if column not in merged.columns:
            merged[column] = 0.0
        else:
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    return merged


def merge_signal_features(
    base_df,
    ticker: str,
    prediction_dir: Optional[Path] = None,
    include_columns: Optional[Iterable[str]] = None,
) :
    import pandas as pd

    merged = base_df.copy()
    if "time" in merged.columns:
        merged["date"] = pd.to_datetime(merged["time"]).dt.strftime("%Y-%m-%d")
    elif "date" in merged.columns:
        merged["date"] = pd.to_datetime(merged["date"]).dt.strftime("%Y-%m-%d")
    else:
        raise ValueError("Base dataframe must include either 'time' or 'date'")

    columns = list(include_columns) if include_columns is not None else default_signal_feature_columns()
    feature_path = Path(prediction_dir or default_signal_prediction_dir()) / f"{str(ticker).upper()}_signal_predictions.parquet"
    if not feature_path.exists():
        for column in columns:
            fill_value = signal_fill_value_for_column(column)
            merged[column] = int(fill_value) if column == SIGNAL_LABEL_COLUMN else fill_value
        return merged

    predictions = pd.read_parquet(feature_path)
    if predictions["date"].duplicated().any():
        duplicates = predictions.loc[predictions["date"].duplicated(), "date"].tolist()
        raise ValueError(f"Duplicate prediction dates found for {ticker}: {duplicates[:5]}")

    available_columns = ["date"] + [column for column in columns if column in predictions.columns]
    predictions = predictions[available_columns].copy()
    predictions["date"] = pd.to_datetime(predictions["date"]).dt.strftime("%Y-%m-%d")
    merged = merged.merge(predictions, on="date", how="left", validate="many_to_one")

    for column in columns:
        fill_value = signal_fill_value_for_column(column)
        if column not in merged.columns:
            merged[column] = fill_value
        if column == SIGNAL_LABEL_COLUMN:
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(fill_value).astype(int)
        else:
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(fill_value)
    return merged


def signal_fill_value_for_column(column: str) -> float:
    if column in {SIGNAL_PREDICTION_COLUMN, SIGNAL_SMOOTHED_COLUMN}:
        return SIGNAL_MISSING_FILL_VALUE
    return 0.0
