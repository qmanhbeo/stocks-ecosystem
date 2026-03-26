"""Helpers for separating manual and auto signal-label variants."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

from .config import SupervisedLabelConfig


LABEL_VARIANTS: Tuple[str, str] = ("manual", "auto")
LABEL_VARIANT_CHOICES: Tuple[str, str, str] = ("manual", "auto", "both")


@dataclass(frozen=True)
class LabelVariantPaths:
    """Resolved file locations for one signal-label variant."""

    name: str
    labels_jsonl_path: Path
    datasets_dir: Path
    bar_labels_path: Path
    supervised_dataset_path: Path
    exports_dir: Path
    model_path: Path
    metadata_path: Path
    predictions_dir: Path

    def ensure_directories(self) -> None:
        for directory in (
            self.labels_jsonl_path.parent,
            self.datasets_dir,
            self.exports_dir,
            self.predictions_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def iter_label_variants(selection: str) -> Iterable[str]:
    if selection == "both":
        return LABEL_VARIANTS
    if selection not in LABEL_VARIANTS:
        raise ValueError(f"Unsupported label variant: {selection}")
    return (selection,)


def resolve_label_variant_paths(
    config: SupervisedLabelConfig,
    variant: str,
) -> LabelVariantPaths:
    if variant not in LABEL_VARIANTS:
        raise ValueError(f"Unsupported label variant: {variant}")

    label_filename = "range_labels.jsonl" if variant == "manual" else "heuristic_range_labels.jsonl"
    datasets_dir = config.datasets_dir / variant
    exports_dir = config.exports_dir / variant
    predictions_dir = config.predictions_dir / variant

    return LabelVariantPaths(
        name=variant,
        labels_jsonl_path=config.labels_dir / label_filename,
        datasets_dir=datasets_dir,
        bar_labels_path=datasets_dir / config.bar_labels_filename,
        supervised_dataset_path=datasets_dir / config.supervised_dataset_filename,
        exports_dir=exports_dir,
        model_path=exports_dir / config.model_filename,
        metadata_path=exports_dir / config.model_metadata_filename,
        predictions_dir=predictions_dir,
    )


def default_rl_signal_prediction_dir(config: SupervisedLabelConfig | None = None) -> Path:
    """Return the canonical signal-prediction directory for RL consumption."""

    resolved_config = config or SupervisedLabelConfig()
    return resolve_label_variant_paths(resolved_config, "auto").predictions_dir
