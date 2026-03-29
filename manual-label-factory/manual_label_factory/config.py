"""Configuration for the supervised labeling pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
from pathlib import Path
from typing import Dict, List


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent


def _shared_data_root() -> Path:
    configured = os.environ.get("STOCKS_DATA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return REPO_ROOT.parent / "data"


@dataclass(slots=True)
class SupervisedLabelConfig:
    """Centralized configuration for supervised labeling artifacts and behavior."""

    repo_root: Path = field(default_factory=lambda: REPO_ROOT)
    package_root: Path = field(default_factory=lambda: PACKAGE_ROOT)
    labels_root: Path = field(default_factory=lambda: _shared_data_root() / "labels" / "supervised")
    signal_features_root: Path = field(default_factory=lambda: _shared_data_root() / "features" / "signals")
    experiment_root: Path = field(default_factory=lambda: REPO_ROOT / "artifacts")
    raw_data_dir: Path = field(default_factory=lambda: _shared_data_root() / "stock")
    artifacts_dir: Path = field(default_factory=lambda: _shared_data_root() / "labels" / "supervised")
    configs_dir: Path = field(default_factory=lambda: PACKAGE_ROOT / "configs")
    splits_dir: Path = field(default_factory=lambda: _shared_data_root() / "labels" / "supervised" / "splits")
    sessions_dir: Path = field(default_factory=lambda: REPO_ROOT / "artifacts" / "labeling_sessions")
    labels_dir: Path = field(default_factory=lambda: _shared_data_root() / "labels" / "supervised" / "ranges")
    exports_dir: Path = field(default_factory=lambda: REPO_ROOT / "artifacts" / "signal_models")
    datasets_dir: Path = field(default_factory=lambda: _shared_data_root() / "features" / "signals" / "datasets")
    predictions_dir: Path = field(default_factory=lambda: _shared_data_root() / "features" / "signals" / "predictions")
    labels_jsonl_path: Path = field(default_factory=lambda: _shared_data_root() / "labels" / "supervised" / "ranges" / "range_labels.jsonl")
    manifest_path: Path = field(default_factory=lambda: _shared_data_root() / "labels" / "supervised" / "manifest.json")
    timeframe: str = "1D"
    split_mode: str = "ticker"
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    min_bars_required: int = 160
    chunk_length_min: int = 64
    chunk_length_max: int = 128
    default_chunk_length: int = 96
    lookback_window: int = 32
    allow_multiple_ranges: bool = True
    default_label: int = 0
    selected_label: int = 1
    random_seed: int = 1208
    supported_model_types: List[str] = field(default_factory=lambda: ["logistic_regression"])
    label_confidence_weights: Dict[str, float] = field(
        default_factory=lambda: {"low": 0.5, "medium": 0.75, "high": 1.0}
    )
    rl_integration_enabled: bool = True
    missing_signal_fill_value: float = 0.5
    prediction_column: str = "signal_prob_buyhold"
    prediction_label_column: str = "signal_pred_label"
    smoothed_prediction_column: str = "smoothed_signal_prob"
    bar_labels_filename: str = "bar_level_labels.parquet"
    supervised_dataset_filename: str = "supervised_dataset.parquet"
    model_filename: str = "signal_model.joblib"
    model_metadata_filename: str = "signal_model_metadata.json"
    evaluation_filename: str = "signal_model_evaluation.json"

    def ensure_directories(self) -> None:
        """Ensure all artifact directories exist."""
        directories = (
            self.artifacts_dir,
            self.configs_dir,
            self.splits_dir,
            self.sessions_dir,
            self.labels_dir,
            self.exports_dir,
            self.datasets_dir,
            self.predictions_dir,
        )
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def split_file_map(self) -> Dict[str, Path]:
        return {
            "train": self.splits_dir / "train_tickers.txt",
            "val": self.splits_dir / "val_tickers.txt",
            "test": self.splits_dir / "test_tickers.txt",
        }

    def to_dict(self) -> Dict[str, object]:
        raw = asdict(self)
        return {
            key: str(value) if isinstance(value, Path) else value
            for key, value in raw.items()
        }


def get_default_config() -> SupervisedLabelConfig:
    config = SupervisedLabelConfig()
    config.ensure_directories()
    return config
