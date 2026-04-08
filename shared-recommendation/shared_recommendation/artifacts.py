from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


class ArtifactKey:
    STOCK_DATA_DIR = "stock_data_dir"
    MARKET_DATA_DIR = "market_data_dir"
    HELP_ASSETS_DIR = "help_assets_dir"
    NEWS_PREDICTION_DIR = "news_prediction_dir"
    SIGNAL_PREDICTION_DIR = "signal_prediction_dir"
    LAB_SIGNAL_MATRIX = "lab_signal_matrix"
    LAB_SIGNAL_PREDICTION_DIR = "lab_signal_prediction_dir"
    TRADABILITY_DAILY = "tradability_daily"
    ACTIVATION_STATE_DAILY = "activation_state_daily"
    ACTIVATION_META_DAILY = "activation_meta_daily"


@dataclass(frozen=True)
class ArtifactSpec:
    key: str
    relative_path: str
    required_columns: tuple[str, ...] = ()
    time_column: str | None = None
    is_directory: bool = False


def shared_data_root() -> Path:
    configured = os.environ.get("STOCKS_DATA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return (WORKSPACE_ROOT / "data").resolve()


def artifact_spec(key: str) -> ArtifactSpec:
    try:
        return _ARTIFACT_SPECS[key]
    except KeyError as exc:
        raise KeyError(f"Unknown artifact key: {key}") from exc


def resolve_artifact_path(key: str, *, profile_name: str | None = None) -> Path:
    if key == "__recommendation_dir__":
        return default_recommendation_dir(profile_name or "default")
    spec = artifact_spec(key)
    return shared_data_root() / spec.relative_path


def default_stock_data_dir() -> Path:
    return resolve_artifact_path(ArtifactKey.STOCK_DATA_DIR)


def default_market_data_dir() -> Path:
    return resolve_artifact_path(ArtifactKey.MARKET_DATA_DIR)


def default_help_assets_dir() -> Path:
    return resolve_artifact_path(ArtifactKey.HELP_ASSETS_DIR)


def default_news_prediction_dir() -> Path:
    return resolve_artifact_path(ArtifactKey.NEWS_PREDICTION_DIR)


def default_signal_prediction_dir() -> Path:
    return resolve_artifact_path(ArtifactKey.SIGNAL_PREDICTION_DIR)


def default_lab_signal_matrix_path() -> Path:
    return resolve_artifact_path(ArtifactKey.LAB_SIGNAL_MATRIX)


def default_lab_signal_prediction_dir() -> Path:
    return resolve_artifact_path(ArtifactKey.LAB_SIGNAL_PREDICTION_DIR)


def default_tradability_path() -> Path:
    return resolve_artifact_path(ArtifactKey.TRADABILITY_DAILY)


def default_activation_state_path() -> Path:
    return resolve_artifact_path(ArtifactKey.ACTIVATION_STATE_DAILY)


def default_activation_meta_path() -> Path:
    return resolve_artifact_path(ArtifactKey.ACTIVATION_META_DAILY)


def default_recommendation_dir(profile_name: str) -> Path:
    return shared_data_root() / "features" / "recommendations" / str(profile_name)


def default_recommendation_candidates_path(profile_name: str) -> Path:
    return default_recommendation_dir(profile_name) / "latest_candidates.parquet"


def default_recommendation_manifest_path(profile_name: str) -> Path:
    return default_recommendation_dir(profile_name) / "manifest.json"


def latest_time_in_artifact(path: Path, *, time_column: str) -> pd.Timestamp | None:
    if not path.exists() or path.is_dir():
        return None
    try:
        frame = pd.read_parquet(path, columns=[time_column])
    except Exception:
        return None
    series = pd.to_datetime(frame[time_column], errors="coerce").dropna()
    if series.empty:
        return None
    return pd.Timestamp(series.max())


def assert_artifact_current(path: Path, spec: ArtifactSpec, as_of_date: pd.Timestamp) -> None:
    if spec.is_directory:
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Artifact directory is missing or unreadable: {path}")
        return
    if spec.time_column is None:
        return
    latest = latest_time_in_artifact(path, time_column=spec.time_column)
    if latest is None:
        raise ValueError(f"Artifact is missing or unreadable for freshness check: {path}")
    if latest.normalize() < pd.Timestamp(as_of_date).normalize():
        raise ValueError(
            f"Artifact {spec.key} is stale for {as_of_date.date()}: "
            f"latest available date is {latest.date()} at {path}"
        )


_ARTIFACT_SPECS: dict[str, ArtifactSpec] = {
    ArtifactKey.STOCK_DATA_DIR: ArtifactSpec(
        key=ArtifactKey.STOCK_DATA_DIR,
        relative_path="stock",
        is_directory=True,
    ),
    ArtifactKey.MARKET_DATA_DIR: ArtifactSpec(
        key=ArtifactKey.MARKET_DATA_DIR,
        relative_path="stock",
        is_directory=True,
    ),
    ArtifactKey.HELP_ASSETS_DIR: ArtifactSpec(
        key=ArtifactKey.HELP_ASSETS_DIR,
        relative_path="fx-commodities",
        is_directory=True,
    ),
    ArtifactKey.NEWS_PREDICTION_DIR: ArtifactSpec(
        key=ArtifactKey.NEWS_PREDICTION_DIR,
        relative_path="features/news/predictions",
        is_directory=True,
    ),
    ArtifactKey.SIGNAL_PREDICTION_DIR: ArtifactSpec(
        key=ArtifactKey.SIGNAL_PREDICTION_DIR,
        relative_path="features/signals/predictions/auto",
        is_directory=True,
    ),
    ArtifactKey.LAB_SIGNAL_MATRIX: ArtifactSpec(
        key=ArtifactKey.LAB_SIGNAL_MATRIX,
        relative_path="features/xs_rl_signal_matrix.parquet",
        required_columns=("time", "ticker"),
        time_column="time",
    ),
    ArtifactKey.LAB_SIGNAL_PREDICTION_DIR: ArtifactSpec(
        key=ArtifactKey.LAB_SIGNAL_PREDICTION_DIR,
        relative_path="features/signals/predictions/rl_lab_matrix",
        is_directory=True,
    ),
    ArtifactKey.TRADABILITY_DAILY: ArtifactSpec(
        key=ArtifactKey.TRADABILITY_DAILY,
        relative_path="features/execution/tradability_daily.parquet",
        required_columns=("time", "ticker", "can_buy_next_open"),
        time_column="time",
    ),
    ArtifactKey.ACTIVATION_STATE_DAILY: ArtifactSpec(
        key=ArtifactKey.ACTIVATION_STATE_DAILY,
        relative_path="features/activation_state_daily.parquet",
        required_columns=("time",),
        time_column="time",
    ),
    ArtifactKey.ACTIVATION_META_DAILY: ArtifactSpec(
        key=ArtifactKey.ACTIVATION_META_DAILY,
        relative_path="features/activation_meta_daily.parquet",
        required_columns=("time",),
        time_column="time",
    ),
}
