"""Read-only Phase 4C audit of Phase 4A observations against trade-aligned targets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from vn_stock_rl.trade_episode.causal_features import CAUSAL_MARKET_FEATURE_NAMES
from vn_stock_rl.trade_episode.data import stock_bars_path
from vn_stock_rl.trade_episode.phase4a_data import (
    DATA_CUTOFF,
    TRAIN_TICKERS,
    UNSEEN_TICKERS,
    prepare_stock,
)
from vn_stock_rl.trade_episode.signals import ALPHA_FEATURE_NAMES, C16_ARTIFACT, S1_ARTIFACT

ANNUALIZATION_INTERVALS = 252
ANNUAL_BENCHMARK = 0.07
ENTRY_HORIZONS = (3, 10, 20)
EXIT_ENTRY_AGES = (3, 10, 20)
EXIT_CONTINUE_HORIZONS = (3, 10, 20)
MAX_EPISODE_STEPS = 756
MAX_HOLDING_INTERVALS = 756
MIN_TICKER_YEAR_ROWS = 40
BOOTSTRAP_REPLICATES = 2_000
BOOTSTRAP_SEED = 94_331
PARTITIONS = {
    "train": (pd.Timestamp("2015-01-01"), pd.Timestamp("2019-12-31")),
    "validation": (pd.Timestamp("2020-01-01"), pd.Timestamp("2022-12-31")),
    "exploratory": (pd.Timestamp("2023-01-01"), DATA_CUTOFF),
}
STATE_FEATURE_NAMES = [
    "position_in",
    "holding_intervals_normalized",
    "entry_relative_unrealized_log_return_scaled",
    "waiting_steps_normalized",
    "episode_steps_normalized",
]


def terminal_trade_reward(
    entry_price: float,
    exit_price: float,
    holding_intervals: int,
) -> float:
    """Return the unclipped Phase 4A reward for one completed trade."""

    values = np.asarray([entry_price, exit_price], dtype=np.float64)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Trade prices must be finite and positive")
    if int(holding_intervals) != holding_intervals or holding_intervals < 3:
        raise ValueError("holding_intervals must be an integer of at least three")
    return float(
        (ANNUALIZATION_INTERVALS / int(holding_intervals))
        * (np.log(float(exit_price)) - np.log(float(entry_price)))
        - np.log1p(ANNUAL_BENCHMARK)
    )


def entry_reward_samples(
    open_prices: np.ndarray,
    can_buy: np.ndarray,
    can_sell: np.ndarray,
    partition_ids: np.ndarray,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return decision indices and exact fixed-horizon rewards.

    A decision at ``t`` buys at open ``t+1``. The SELL decision occurs at
    close ``t+h`` and fills at open ``t+h+1``.
    """

    prices = np.asarray(open_prices, dtype=np.float64)
    buy = np.asarray(can_buy, dtype=bool)
    sell = np.asarray(can_sell, dtype=bool)
    partitions = np.asarray(partition_ids, dtype=object)
    if horizon < 3:
        raise ValueError("Entry horizon cannot be shorter than the three-interval minimum")
    if not (prices.ndim == buy.ndim == sell.ndim == partitions.ndim == 1):
        raise ValueError("prices, flags, and partition_ids must be one-dimensional")
    if not (len(prices) == len(buy) == len(sell) == len(partitions)):
        raise ValueError("prices, flags, and partition_ids must have equal lengths")

    decision_indices: list[int] = []
    rewards: list[float] = []
    for decision_index in range(max(0, len(prices) - horizon - 1)):
        entry_fill_index = decision_index + 1
        sell_decision_index = decision_index + horizon
        exit_fill_index = sell_decision_index + 1
        split = partitions[decision_index]
        if split is None or pd.isna(split):
            continue
        if not (
            partitions[entry_fill_index] == split
            and partitions[sell_decision_index] == split
            and partitions[exit_fill_index] == split
        ):
            continue
        if not (buy[decision_index] and sell[sell_decision_index]):
            continue
        decision_indices.append(decision_index)
        rewards.append(
            terminal_trade_reward(
                prices[decision_index + 1],
                prices[exit_fill_index],
                horizon,
            )
        )
    return np.asarray(decision_indices, dtype=np.int64), np.asarray(rewards, dtype=np.float64)


def exit_reward_advantage(
    open_prices: np.ndarray,
    *,
    decision_index: int,
    entry_age: int,
    continue_horizon: int,
) -> float:
    """Reward(HOLD for h then sell) minus reward(SELL at next open)."""

    prices = np.asarray(open_prices, dtype=np.float64)
    entry_age = int(entry_age)
    continue_horizon = int(continue_horizon)
    entry_index = decision_index - entry_age
    now_fill_index = decision_index + 1
    later_fill_index = decision_index + continue_horizon + 1
    if entry_age < 3 or continue_horizon < 3:
        raise ValueError("Entry age and continuation horizon must be at least three")
    if entry_index < 0 or later_fill_index >= len(prices):
        raise IndexError("Exit counterfactual falls outside available prices")
    entry_price = prices[entry_index]
    reward_sell = terminal_trade_reward(entry_price, prices[now_fill_index], entry_age + 1)
    reward_hold = terminal_trade_reward(
        entry_price,
        prices[later_fill_index],
        entry_age + continue_horizon + 1,
    )
    return float(reward_hold - reward_sell)


def exit_state_features(
    *,
    current_close: float,
    entry_price: float,
    entry_volatility: float,
    entry_age: int,
) -> np.ndarray:
    """Construct the five observable Phase 4A agent-state fields for an IN state."""

    if min(current_close, entry_price, entry_volatility) <= 0:
        raise ValueError("Prices and volatility must be positive")
    if entry_age < 3:
        raise ValueError("An exit state requires the minimum three-interval hold")
    unrealized = (np.log(current_close) - np.log(entry_price)) / (
        entry_volatility * np.sqrt(max(1, entry_age))
    )
    return np.asarray(
        [
            1.0,
            entry_age / MAX_HOLDING_INTERVALS,
            unrealized,
            0.0,
            (entry_age + 1) / MAX_EPISODE_STEPS,
        ],
        dtype=np.float64,
    )


def _partition_ids(dates: pd.DatetimeIndex) -> np.ndarray:
    dates = pd.DatetimeIndex(dates).normalize()
    labels = np.full(len(dates), None, dtype=object)
    for name, (start, end) in PARTITIONS.items():
        labels[(dates >= start) & (dates <= end)] = name
    return labels


def _spearman(left: np.ndarray, right: np.ndarray) -> float | None:
    x = np.asarray(left, dtype=np.float64)
    y = np.asarray(right, dtype=np.float64)
    valid = np.isfinite(x) & np.isfinite(y)
    if int(valid.sum()) < MIN_TICKER_YEAR_ROWS:
        return None
    x = x[valid]
    y = y[valid]
    if np.ptp(x) <= 0 or np.ptp(y) <= 0:
        return None
    x_rank = pd.Series(x).rank(method="average").to_numpy(dtype=np.float64)
    y_rank = pd.Series(y).rank(method="average").to_numpy(dtype=np.float64)
    return float(np.corrcoef(x_rank, y_rank)[0, 1])


def _append_ticker_year_correlations(
    output: list[dict[str, Any]],
    *,
    features: np.ndarray,
    feature_names: list[str],
    target: np.ndarray,
    dates: pd.DatetimeIndex,
    ticker: str,
    ticker_group: str,
    split: str,
    task: str,
    horizon: int,
    entry_age: int | None,
    feature_set: str,
) -> None:
    years = pd.DatetimeIndex(dates).year.to_numpy()
    for year in np.unique(years):
        year_mask = years == year
        count = int(year_mask.sum())
        if count < MIN_TICKER_YEAR_ROWS:
            continue
        year_target = target[year_mask]
        for column_index, feature_name in enumerate(feature_names):
            rho = _spearman(features[year_mask, column_index], year_target)
            if rho is None:
                continue
            output.append(
                {
                    "split": split,
                    "ticker_group": ticker_group,
                    "ticker": ticker,
                    "year": int(year),
                    "task": task,
                    "horizon": int(horizon),
                    "entry_age": entry_age,
                    "feature_set": feature_set,
                    "feature": feature_name,
                    "rows": count,
                    "spearman_rho": rho,
                }
            )


def _key_seed(key: tuple[Any, ...]) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in key).encode()).digest()
    return BOOTSTRAP_SEED + int.from_bytes(digest[:4], "big")


def _bootstrap_interval(
    rows: list[dict[str, Any]], key: tuple[Any, ...]
) -> tuple[float | None, float | None]:
    by_ticker: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_ticker[str(row["ticker"])].append(float(row["spearman_rho"]))
    tickers = sorted(by_ticker)
    if len(tickers) < 2:
        return None, None
    rng = np.random.default_rng(_key_seed(key))
    ticker_draw_means = np.empty((len(tickers), BOOTSTRAP_REPLICATES), dtype=np.float64)
    for ticker_index, ticker in enumerate(tickers):
        year_rhos = np.asarray(by_ticker[ticker], dtype=np.float64)
        year_draws = rng.integers(0, len(year_rhos), size=(BOOTSTRAP_REPLICATES, len(year_rhos)))
        ticker_draw_means[ticker_index] = year_rhos[year_draws].mean(axis=1)
    sampled_ticker_indices = rng.integers(
        0,
        len(tickers),
        size=(BOOTSTRAP_REPLICATES, len(tickers)),
    )
    bootstrap_means = np.take_along_axis(
        ticker_draw_means.T,
        sampled_ticker_indices,
        axis=1,
    ).mean(axis=1)
    lower, upper = np.quantile(bootstrap_means, [0.025, 0.975])
    return float(lower), float(upper)


def summarize_correlations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate ticker-year associations with equal ticker weight and clustered CI."""

    if not rows:
        return []
    frame = pd.DataFrame(rows)
    group_columns = [
        "split",
        "ticker_group",
        "task",
        "horizon",
        "entry_age",
        "feature_set",
        "feature",
    ]
    summaries: list[dict[str, Any]] = []
    for key_tuple, group in frame.groupby(group_columns, dropna=False, sort=True):
        key = dict(zip(group_columns, key_tuple, strict=True))
        per_ticker = group.groupby("ticker")["spearman_rho"].mean()
        ticker_balanced_mean = float(per_ticker.mean())
        ci_low, ci_high = _bootstrap_interval(group.to_dict("records"), tuple(key.values()))
        summaries.append(
            {
                **key,
                "ticker_year_count": int(len(group)),
                "ticker_count": int(group["ticker"].nunique()),
                "sample_row_count": int(group["rows"].sum()),
                "equal_ticker_mean_rho": ticker_balanced_mean,
                "median_ticker_year_rho": float(group["spearman_rho"].median()),
                "positive_ticker_year_fraction": float((group["spearman_rho"] > 0).mean()),
                "bootstrap_95ci_low": ci_low,
                "bootstrap_95ci_high": ci_high,
                "bootstrap_replicates": BOOTSTRAP_REPLICATES,
                "bootstrap_seed": _key_seed(tuple(key.values())),
            }
        )
    return summaries


def _state_matrix(
    stock,
    decision_indices: np.ndarray,
    *,
    task: str,
    entry_age: int | None = None,
) -> tuple[np.ndarray, np.ndarray, list[str], list[str], np.ndarray]:
    market_names = list(CAUSAL_MARKET_FEATURE_NAMES)
    alpha_names = list(ALPHA_FEATURE_NAMES)
    market = np.asarray(stock.market_features[decision_indices], dtype=np.float64)
    alpha = np.asarray(stock.alpha_features[decision_indices], dtype=np.float64)
    if task == "entry":
        state = np.zeros((len(decision_indices), len(STATE_FEATURE_NAMES)), dtype=np.float64)
    else:
        if entry_age is None:
            raise ValueError("entry_age is required for exit states")
        state_rows: list[np.ndarray] = []
        for decision_index in decision_indices:
            entry_index = int(decision_index) - int(entry_age)
            entry_decision_index = entry_index - 1
            state_rows.append(
                exit_state_features(
                    current_close=float(stock.closes[decision_index]),
                    entry_price=float(stock.opens[entry_index]),
                    entry_volatility=float(stock.daily_volatility_scale[entry_decision_index]),
                    entry_age=int(entry_age),
                )
            )
        state = np.vstack(state_rows) if state_rows else np.empty((0, 5), dtype=np.float64)
    market_only = np.column_stack((market, state))
    plus_alpha = np.column_stack((market, alpha, state))
    return (
        market_only,
        plus_alpha,
        market_names + STATE_FEATURE_NAMES,
        market_names + alpha_names + STATE_FEATURE_NAMES,
        state,
    )


def _collect_entry(
    stock,
    ticker_group: str,
    split: str,
    horizon: int,
    correlations: list[dict[str, Any]],
    sample_counts: dict[str, int],
) -> None:
    partition_ids = _partition_ids(stock.dates)
    decision_indices, reward = entry_reward_samples(
        stock.opens,
        stock.can_buy,
        stock.can_sell,
        partition_ids,
        horizon,
    )
    selected = partition_ids[decision_indices] == split
    decision_indices = decision_indices[selected]
    reward = reward[selected]
    sample_counts[f"entry|{ticker_group}|{stock.ticker}|{split}|h{horizon}"] = int(len(reward))
    if not len(reward):
        return
    dates = stock.dates[decision_indices]
    market_only, plus_alpha, market_names, plus_names, _ = _state_matrix(
        stock, decision_indices, task="entry"
    )
    _append_ticker_year_correlations(
        correlations,
        features=market_only,
        feature_names=market_names,
        target=reward,
        dates=dates,
        ticker=stock.ticker,
        ticker_group=ticker_group,
        split=split,
        task="entry",
        horizon=horizon,
        entry_age=None,
        feature_set="market_only",
    )
    _append_ticker_year_correlations(
        correlations,
        features=plus_alpha,
        feature_names=plus_names,
        target=reward,
        dates=dates,
        ticker=stock.ticker,
        ticker_group=ticker_group,
        split=split,
        task="entry",
        horizon=horizon,
        entry_age=None,
        feature_set="market_plus_s1_c16",
    )


def _collect_exit(
    stock,
    ticker_group: str,
    split: str,
    entry_age: int,
    horizon: int,
    correlations: list[dict[str, Any]],
    sample_counts: dict[str, int],
) -> None:
    prices = stock.opens
    partition_ids = _partition_ids(stock.dates)
    decision_indices: list[int] = []
    advantages: list[float] = []
    latest_decision = len(prices) - horizon - 2
    for decision_index in range(entry_age + 1, latest_decision + 1):
        entry_index = decision_index - entry_age
        entry_decision_index = entry_index - 1
        future_sell_decision = decision_index + horizon
        future_exit_fill = future_sell_decision + 1
        if entry_decision_index < 0 or future_exit_fill >= len(prices):
            continue
        if partition_ids[decision_index] != split:
            continue
        if not (
            partition_ids[entry_decision_index] == split
            and partition_ids[entry_index] == split
            and partition_ids[future_sell_decision] == split
            and partition_ids[future_exit_fill] == split
        ):
            continue
        if not (
            stock.can_buy[entry_decision_index]
            and stock.can_sell[decision_index]
            and stock.can_sell[future_sell_decision]
        ):
            continue
        decision_indices.append(decision_index)
        advantages.append(
            exit_reward_advantage(
                prices,
                decision_index=decision_index,
                entry_age=entry_age,
                continue_horizon=horizon,
            )
        )
    indices = np.asarray(decision_indices, dtype=np.int64)
    target = np.asarray(advantages, dtype=np.float64)
    sample_counts[f"exit|{ticker_group}|{stock.ticker}|{split}|age{entry_age}|h{horizon}"] = int(
        len(target)
    )
    if not len(target):
        return
    dates = stock.dates[indices]
    market_only, plus_alpha, market_names, plus_names, _ = _state_matrix(
        stock, indices, task="exit", entry_age=entry_age
    )
    for features, names, feature_set in (
        (market_only, market_names, "market_only"),
        (plus_alpha, plus_names, "market_plus_s1_c16"),
    ):
        _append_ticker_year_correlations(
            correlations,
            features=features,
            feature_names=names,
            target=target,
            dates=dates,
            ticker=stock.ticker,
            ticker_group=ticker_group,
            split=split,
            task="exit_hold_advantage",
            horizon=horizon,
            entry_age=entry_age,
            feature_set=feature_set,
        )


def _prepared_input_fingerprint(stock) -> str:
    digest = hashlib.sha256()
    arrays = (
        pd.DatetimeIndex(stock.dates).asi8,
        stock.opens,
        stock.closes,
        stock.market_features,
        stock.alpha_features,
        stock.daily_volatility_scale,
        stock.can_buy,
        stock.can_sell,
    )
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode())
        digest.update(str(contiguous.shape).encode())
        digest.update(contiguous.tobytes())
    return digest.hexdigest()


def _file_stats(data_root: Path, tickers: tuple[str, ...]) -> dict[str, dict[str, int]]:
    paths = {f"ohlcv_{ticker}": stock_bars_path(ticker, data_root=data_root) for ticker in tickers}
    paths.update(
        {
            "s1": data_root / S1_ARTIFACT,
            "c16": data_root / C16_ARTIFACT,
            "tradability": data_root / "features" / "execution" / "tradability_daily.parquet",
        }
    )
    return {
        name: {"size_bytes": int(path.stat().st_size), "mtime_ns": int(path.stat().st_mtime_ns)}
        for name, path in paths.items()
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError("No feature association rows were generated")
    frame.to_csv(path, index=False, lineterminator="\n")


def run_audit(
    *,
    data_root: Path,
    config_path: Path,
    protocol_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[3]
    config = json.loads(config_path.read_text(encoding="utf-8"))
    cutoff = pd.Timestamp(config["date_cutoff"])
    if cutoff != DATA_CUTOFF:
        raise ValueError(f"Configured cutoff must match Phase 4A cutoff {DATA_CUTOFF.date()}")
    if tuple(config["training_tickers"]) != tuple(TRAIN_TICKERS):
        raise ValueError("Configured training tickers do not match the Phase 4A universe")
    if tuple(config["unseen_tickers"]) != tuple(UNSEEN_TICKERS):
        raise ValueError("Configured unseen tickers do not match the Phase 4A universe")
    if tuple(config["entry_horizons_intervals"]) != ENTRY_HORIZONS:
        raise ValueError("Configured entry horizons do not match the frozen audit code")
    if tuple(config["exit_entry_ages_intervals"]) != EXIT_ENTRY_AGES:
        raise ValueError("Configured exit ages do not match the frozen audit code")
    if tuple(config["exit_continue_horizons_intervals"]) != EXIT_CONTINUE_HORIZONS:
        raise ValueError("Configured exit horizons do not match the frozen audit code")
    tickers = tuple(config["training_tickers"]) + tuple(config["unseen_tickers"])
    output_dir = output_dir.resolve()
    expected_results_root = (
        repo_root / "RL-trading-agent" / "research" / "trade_episode" / "phase4c" / "results"
    ).resolve()
    if output_dir != expected_results_root:
        raise ValueError(
            f"Refusing output outside the isolated Phase 4C results directory: {output_dir}"
        )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty results directory: {output_dir}")

    try:
        run_code_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
        ).strip()
        run_branch = subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=repo_root, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        run_code_sha = None
        run_branch = None
    config_sha = hashlib.sha256(config_path.read_bytes()).hexdigest()
    protocol_sha = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    before = _file_stats(data_root, tickers)
    prepared = {ticker: prepare_stock(ticker, data_root=data_root) for ticker in tickers}
    fingerprints = {
        ticker: _prepared_input_fingerprint(stock) for ticker, stock in prepared.items()
    }
    for ticker, stock in prepared.items():
        if pd.DatetimeIndex(stock.dates).max().normalize() > cutoff:
            raise RuntimeError(f"{ticker}: post-cutoff row reached prepared data")
        if (
            not np.isfinite(stock.market_features).all()
            or not np.isfinite(stock.alpha_features).all()
        ):
            raise RuntimeError(f"{ticker}: prepared observations contain non-finite values")

    correlations: list[dict[str, Any]] = []
    sample_counts: dict[str, int] = {}
    ticker_groups = {ticker: "training_universe" for ticker in config["training_tickers"]}
    ticker_groups.update({ticker: "unseen_ticker" for ticker in config["unseen_tickers"]})
    for ticker in tickers:
        stock = prepared[ticker]
        ticker_group = ticker_groups[ticker]
        for split in PARTITIONS:
            for horizon in ENTRY_HORIZONS:
                _collect_entry(
                    stock,
                    ticker_group,
                    split,
                    horizon,
                    correlations,
                    sample_counts,
                )
            for entry_age in EXIT_ENTRY_AGES:
                for horizon in EXIT_CONTINUE_HORIZONS:
                    _collect_exit(
                        stock,
                        ticker_group,
                        split,
                        entry_age,
                        horizon,
                        correlations,
                        sample_counts,
                    )

    summaries = summarize_correlations(correlations)
    after = _file_stats(data_root, tickers)
    if before != after:
        raise RuntimeError("Shared data metadata changed during the Phase 4C audit")
    try:
        end_code_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
        ).strip()
        end_config_sha = hashlib.sha256(config_path.read_bytes()).hexdigest()
        end_protocol_sha = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Could not verify the audit's source/config provenance") from exc
    if end_code_sha != run_code_sha:
        raise RuntimeError("Git HEAD changed while the Phase 4C audit was running")
    if end_config_sha != config_sha or end_protocol_sha != protocol_sha:
        raise RuntimeError("Phase 4C config or protocol changed while the audit was running")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Results directory changed while audit was running: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    association_path = output_dir / "phase4c_feature_associations.csv"
    metrics_path = output_dir / "phase4c_metrics.json"
    _write_csv(association_path, summaries)

    result = {
        "experiment_id": config["experiment_id"],
        "execution_date_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "run_code_git_sha": run_code_sha,
        "git_branch": run_branch,
        "config_path": str(config_path.resolve()),
        "config_sha256": config_sha,
        "protocol_path": str(protocol_path.resolve()),
        "protocol_sha256": protocol_sha,
        "source_data_root": str(data_root.resolve()),
        "source_data_read_only": True,
        "input_file_stats_before": before,
        "input_file_stats_after": after,
        "shared_data_metadata_unchanged": before == after,
        "prepared_input_fingerprints_sha256": fingerprints,
        "date_cutoff": str(cutoff.date()),
        "max_prepared_observation_date": max(
            str(pd.DatetimeIndex(stock.dates).max().date()) for stock in prepared.values()
        ),
        "post_cutoff_rows_used": False,
        "training_tickers": list(config["training_tickers"]),
        "unseen_tickers": list(config["unseen_tickers"]),
        "partition_bounds": {
            name: [str(start.date()), str(end.date())] for name, (start, end) in PARTITIONS.items()
        },
        "entry_horizons_intervals": list(ENTRY_HORIZONS),
        "exit_entry_ages_intervals": list(EXIT_ENTRY_AGES),
        "exit_continue_horizons_intervals": list(EXIT_CONTINUE_HORIZONS),
        "minimum_holding_intervals": 3,
        "annualization_intervals": ANNUALIZATION_INTERVALS,
        "annual_benchmark": ANNUAL_BENCHMARK,
        "training_performed": False,
        "model_fit_performed": False,
        "metric": (
            "within-ticker-calendar-year Spearman rho; equal-ticker mean; "
            "hierarchical ticker/year bootstrap"
        ),
        "minimum_rows_per_ticker_year": MIN_TICKER_YEAR_ROWS,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "correlation_record_count": len(correlations),
        "summary_row_count": len(summaries),
        "sample_counts_by_ticker_and_scenario": sample_counts,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "outputs": {
            "associations_csv": str(association_path.resolve()),
            "metrics_json": str(metrics_path.resolve()),
        },
    }
    metrics_path.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    default_config = (
        repo_root
        / "RL-trading-agent"
        / "configs"
        / "trade_episode"
        / "phase4c_target_alignment.json"
    )
    default_protocol = (
        repo_root
        / "RL-trading-agent"
        / "research"
        / "trade_episode"
        / "phase4c"
        / "target_alignment_protocol.md"
    )
    default_output = (
        repo_root / "RL-trading-agent" / "research" / "trade_episode" / "phase4c" / "results"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=os.environ.get("STOCKS_DATA_ROOT"))
    parser.add_argument("--config", type=Path, default=default_config)
    parser.add_argument("--protocol", type=Path, default=default_protocol)
    parser.add_argument("--output-dir", type=Path, default=default_output)
    args = parser.parse_args()
    if args.data_root is None:
        parser.error("Set STOCKS_DATA_ROOT or pass --data-root")
    result = run_audit(
        data_root=args.data_root.expanduser().resolve(),
        config_path=args.config.resolve(),
        protocol_path=args.protocol.resolve(),
        output_dir=args.output_dir.resolve(),
    )
    print(
        f"Phase4C complete: {result['correlation_record_count']} ticker-year records, "
        f"{result['summary_row_count']} summaries; data unchanged; cutoff={result['date_cutoff']}"
    )


if __name__ == "__main__":
    main()
