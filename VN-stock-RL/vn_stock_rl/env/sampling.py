"""Sampling-related helpers shared by training entrypoints."""

from __future__ import annotations


def validate_fraction_bounds(min_fraction: float, max_fraction: float) -> tuple[float, float]:
    min_fraction = float(min_fraction)
    max_fraction = float(max_fraction)
    if not (0.0 < min_fraction <= 1.0):
        raise ValueError(f"min_fraction must be in (0, 1], got {min_fraction}")
    if not (0.0 < max_fraction <= 1.0):
        raise ValueError(f"max_fraction must be in (0, 1], got {max_fraction}")
    if min_fraction > max_fraction:
        raise ValueError(f"min_fraction must be <= max_fraction, got {min_fraction} > {max_fraction}")
    return min_fraction, max_fraction
