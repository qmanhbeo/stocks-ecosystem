"""Paired ticker/block uncertainty summaries for Phase 4B."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable

import numpy as np


def bootstrap_paired_blocks(
    ppo_values: dict[tuple[str, Hashable], list[float]],
    control_values: dict[tuple[str, Hashable], list[float]],
    *,
    replicates: int,
    seed: int,
) -> dict[str, float | int | None]:
    """Resample tickers, then calendar blocks, plus PPO seeds/control runs."""

    common = sorted(
        set(ppo_values).intersection(control_values),
        key=lambda item: (item[0], str(item[1])),
    )
    if not common or replicates < 1:
        return {
            "paired_block_count": 0,
            "ticker_count": 0,
            "mean_paired_excess_return": None,
            "ci95_lower": None,
            "ci95_upper": None,
        }
    by_ticker: dict[str, list[Hashable]] = defaultdict(list)
    for ticker, block in common:
        if not ppo_values[(ticker, block)] or not control_values[(ticker, block)]:
            continue
        by_ticker[ticker].append(block)
    tickers = sorted(by_ticker)
    if not tickers:
        return {
            "paired_block_count": 0,
            "ticker_count": 0,
            "mean_paired_excess_return": None,
            "ci95_lower": None,
            "ci95_upper": None,
        }

    per_ticker_block_differences: dict[str, list[float]] = defaultdict(list)
    for ticker in tickers:
        for block in by_ticker[ticker]:
            key = (ticker, block)
            per_ticker_block_differences[ticker].append(
                float(np.mean(ppo_values[key]) - np.mean(control_values[key]))
            )
    point = float(np.mean([np.mean(per_ticker_block_differences[ticker]) for ticker in tickers]))

    rng = np.random.default_rng(seed)
    bootstrap_means = np.empty(replicates, dtype=np.float64)
    for iteration in range(replicates):
        sampled_tickers = rng.choice(tickers, size=len(tickers), replace=True)
        ticker_means = []
        for ticker in sampled_tickers:
            blocks = by_ticker[str(ticker)]
            sampled_blocks = rng.choice(len(blocks), size=len(blocks), replace=True)
            differences = []
            for block_index in sampled_blocks:
                key = (str(ticker), blocks[int(block_index)])
                agent_samples = ppo_values[key]
                null_samples = control_values[key]
                agent_value = float(agent_samples[int(rng.integers(0, len(agent_samples)))])
                control_value = float(null_samples[int(rng.integers(0, len(null_samples)))])
                differences.append(agent_value - control_value)
            ticker_means.append(float(np.mean(differences)))
        bootstrap_means[iteration] = float(np.mean(ticker_means))
    lower, upper = np.quantile(bootstrap_means, [0.025, 0.975])
    return {
        "paired_block_count": int(sum(map(len, per_ticker_block_differences.values()))),
        "ticker_count": int(len(tickers)),
        "mean_paired_excess_return": point,
        "ci95_lower": float(lower),
        "ci95_upper": float(upper),
    }


def empirical_percentile(value: float, sample) -> float | None:
    """Mid-rank percentile for a single realized path in a Monte Carlo null."""

    values = np.asarray(sample, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        return None
    less = int(np.sum(values < value))
    equal = int(np.sum(values == value))
    return float((less + 0.5 * equal) / len(values) * 100.0)
