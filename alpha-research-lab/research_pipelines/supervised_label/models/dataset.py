"""Dataset access helpers for supervised signal modeling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from research_pipelines.supervised_label.config import SupervisedLabelConfig, get_default_config


METADATA_COLUMNS = {
    "ticker",
    "date",
    "time",
    "chunk_id",
    "label",
    "confidence",
    "confidence_weight",
    "session_id",
    "ticker_split",
    "dataset_split",
    "history_ready",
}


@dataclass
class DatasetSplit:
    frame: pd.DataFrame
    feature_columns: List[str]
    X: pd.DataFrame
    y: pd.Series
    sample_weights: pd.Series
    class_weights: Dict[int, float]


class SupervisedSignalDataset:
    """Tabular dataset wrapper for exported supervised labels/features."""

    def __init__(
        self,
        dataset_path: Optional[Path] = None,
        config: Optional[SupervisedLabelConfig] = None,
    ) -> None:
        self.config = config or get_default_config()
        self.dataset_path = Path(dataset_path) if dataset_path else self.config.datasets_dir / self.config.supervised_dataset_filename
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Supervised dataset parquet not found: {self.dataset_path}")
        self.frame = pd.read_parquet(self.dataset_path)
        if self.frame.empty:
            raise ValueError("Supervised dataset is empty")

    def infer_feature_columns(self) -> List[str]:
        return [column for column in self.frame.columns if column not in METADATA_COLUMNS]

    def get_split(
        self,
        split: str,
        split_strategy: str = "dataset",
        feature_columns: Optional[List[str]] = None,
        fallback_to_dataset: bool = True,
    ) -> DatasetSplit:
        if split_strategy not in {"dataset", "ticker"}:
            raise ValueError("split_strategy must be 'dataset' or 'ticker'")

        selected_feature_columns = feature_columns or self.infer_feature_columns()
        split_column = "dataset_split" if split_strategy == "dataset" else "ticker_split"
        frame = self.frame.loc[self.frame[split_column].astype(str) == split].copy()
        if frame.empty and split_strategy == "ticker" and fallback_to_dataset:
            frame = self.frame.loc[self.frame["dataset_split"].astype(str) == split].copy()
        if frame.empty:
            raise ValueError(f"No rows found for split='{split}' using strategy='{split_strategy}'")

        X = frame[selected_feature_columns].astype(float)
        y = frame["label"].astype(int)
        counts = y.value_counts().to_dict()
        total = float(len(frame))
        class_weights = {
            label: total / (len(counts) * count)
            for label, count in counts.items()
            if count > 0
        }
        sample_weights = frame["confidence_weight"].astype(float).copy()
        for label, weight in class_weights.items():
            sample_weights.loc[y == label] *= float(weight)
        return DatasetSplit(
            frame=frame,
            feature_columns=selected_feature_columns,
            X=X,
            y=y,
            sample_weights=sample_weights,
            class_weights={int(key): float(value) for key, value in class_weights.items()},
        )
