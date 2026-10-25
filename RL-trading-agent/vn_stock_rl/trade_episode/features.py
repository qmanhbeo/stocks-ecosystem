from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FeatureStandardizer:
    """Train-only standardization with training-mean imputation for causal features."""

    mean: np.ndarray
    scale: np.ndarray

    @classmethod
    def fit(cls, training_features: np.ndarray) -> "FeatureStandardizer":
        values = np.asarray(training_features, dtype=np.float64)
        if values.ndim != 2 or values.shape[0] == 0:
            raise ValueError("training_features must be a non-empty 2D array")
        if np.isinf(values).any():
            raise ValueError("training_features must not contain infinite values")
        if np.isnan(values).all(axis=0).any():
            raise ValueError("Every feature needs at least one finite training value")
        mean = np.nanmean(values, axis=0)
        scale = np.nanstd(values, axis=0)
        scale = np.where(scale > np.finfo(np.float64).eps, scale, 1.0)
        return cls(mean=mean, scale=scale)

    def transform(self, features: np.ndarray) -> np.ndarray:
        values = np.asarray(features, dtype=np.float64)
        if values.ndim != 2 or values.shape[1] != self.mean.shape[0]:
            raise ValueError("features have a different column count from the fitted scaler")
        if np.isinf(values).any():
            raise ValueError("features must not contain infinite values")
        # Missing feature values are imputed to the training mean, hence zero
        # after scaling. Callers should include an availability indicator when
        # missingness itself carries information.
        imputed = np.where(np.isnan(values), self.mean, values)
        transformed = (imputed - self.mean) / self.scale
        return transformed.astype(np.float32)


def chronological_splits(
    row_count: int,
    *,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
) -> dict[str, slice]:
    """Return contiguous, non-overlapping train/validation/test row slices."""

    if row_count < 3:
        raise ValueError("At least three rows are required for chronological splits")
    if not (0.0 < train_fraction < 1.0):
        raise ValueError("train_fraction must be in (0, 1)")
    if not (0.0 < validation_fraction < 1.0):
        raise ValueError("validation_fraction must be in (0, 1)")
    if train_fraction + validation_fraction >= 1.0:
        raise ValueError("train_fraction + validation_fraction must be < 1")

    train_end = int(row_count * train_fraction)
    validation_end = train_end + int(row_count * validation_fraction)
    if train_end < 1 or validation_end <= train_end or validation_end >= row_count:
        raise ValueError("Fractions leave an empty train, validation, or test split")
    return {
        "train": slice(0, train_end),
        "validation": slice(train_end, validation_end),
        "test": slice(validation_end, row_count),
    }
