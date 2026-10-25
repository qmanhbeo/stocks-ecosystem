"""Compact paired-block uncertainty helpers for Phase 4D."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd


def annualized_year_blocks(result: dict[str, Any]) -> dict[int, float]:
    frame = pd.DataFrame(result["daily_path"])
    if frame.empty:
        return {}
    # The initial close is a capital anchor, not a realized trading interval.
    frame = frame.loc[frame["regime"] != "warmup"]
    blocks: dict[int, float] = {}
    for year, group in frame.groupby("year", sort=True):
        count = int(len(group))
        if count:
            blocks[int(year)] = float(group["log_return"].sum() * 252.0 / count)
    return blocks


def hierarchical_paired_bootstrap(
    *,
    candidate_policy: str,
    comparator_policy: str,
    ticker_group: str,
    block_returns: dict[tuple[str, str, int], float],
    ticker_groups: dict[str, str],
    random_comparator_prefix: str | None = None,
    replicates: int = 2_000,
    seed: int = 64_045,
) -> dict[str, Any]:
    """Resample tickers, then paired ticker-year blocks, preserving the policy pairing."""

    candidate: dict[str, dict[int, float]] = defaultdict(dict)
    comparator: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for (policy, ticker, year), value in block_returns.items():
        if ticker_groups.get(ticker) != ticker_group:
            continue
        if policy == candidate_policy:
            candidate[ticker][year] = float(value)
        if policy == comparator_policy or (
            random_comparator_prefix is not None and policy.startswith(random_comparator_prefix)
        ):
            comparator[ticker][year].append(float(value))

    paired: dict[str, dict[int, list[tuple[float, float]]]] = defaultdict(lambda: defaultdict(list))
    for ticker, year_values in candidate.items():
        for year, cand_log in year_values.items():
            controls = comparator.get(ticker, {}).get(year, [])
            if controls:
                paired[ticker][year].extend((cand_log, value) for value in controls)
    eligible = {
        ticker: {year: values for year, values in years.items() if values}
        for ticker, years in paired.items()
    }
    eligible = {ticker: years for ticker, years in eligible.items() if years}
    if not eligible:
        return {"paired_tickers": 0, "paired_ticker_years": 0, "mean_cagr_difference": None}

    ticker_names = sorted(eligible)
    deltas: list[float] = []
    rng = np.random.default_rng(seed)
    for _ in range(replicates):
        sampled_tickers = rng.choice(ticker_names, size=len(ticker_names), replace=True)
        block_differences: list[float] = []
        for ticker in sampled_tickers:
            years = sorted(eligible[str(ticker)])
            sampled_years = rng.choice(years, size=len(years), replace=True)
            for year in sampled_years:
                pairs = eligible[str(ticker)][int(year)]
                candidate_log, comparator_log = pairs[int(rng.integers(0, len(pairs)))]
                # Compare annualized wealth factors (equivalent to CAGR points).
                block_differences.append(float(np.expm1(candidate_log) - np.expm1(comparator_log)))
        if block_differences:
            deltas.append(float(np.mean(block_differences)))

    point_differences = [
        float(np.mean([np.expm1(a) - np.expm1(b) for pairs in years.values() for a, b in pairs]))
        for years in eligible.values()
    ]
    ci_low, ci_high = np.quantile(np.asarray(deltas), [0.025, 0.975])
    return {
        "paired_tickers": len(eligible),
        "paired_ticker_years": sum(len(years) for years in eligible.values()),
        "equal_ticker_mean_annualized_cagr_difference": float(np.mean(point_differences)),
        "bootstrap_ci_95_low": float(ci_low),
        "bootstrap_ci_95_high": float(ci_high),
        "bootstrap_replicates": int(replicates),
        "bootstrap_seed": int(seed),
    }


def policy_group_summary(
    rows: list[dict[str, Any]], *, policy: str, ticker_group: str
) -> dict[str, Any]:
    selected = [
        row
        for row in rows
        if row.get("policy") == policy and row.get("ticker_group") == ticker_group
    ]
    if not selected:
        return {"policy": policy, "ticker_group": ticker_group, "ticker_count": 0}
    fields = (
        "chronological_portfolio_cagr",
        "total_calendar_return",
        "maximum_drawdown",
        "exposure_percentage",
        "number_of_trades",
        "win_rate",
        "mean_terminal_rl_reward",
        "mean_holding_duration",
        "mean_waiting_duration",
        "incomplete_open_positions",
    )
    summary: dict[str, Any] = {
        "policy": policy,
        "ticker_group": ticker_group,
        "ticker_count": len(selected),
        "aggregation": "equal-weight mean of separate stock paths; not a portfolio",
    }
    for field in fields:
        values = [float(row[field]) for row in selected if row.get(field) is not None]
        summary[field] = None if not values else float(np.mean(values))
    return summary
