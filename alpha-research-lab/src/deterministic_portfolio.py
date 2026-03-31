from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import Mapping

import numpy as np
import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))

from shared_market_rules import can_execute_sell, compute_tradability_flags

RESERVED_COLUMNS = {"time", "ticker", "actual"}
WEIGHTING_RULES = ("equal", "linear", "square")
RECENT_CORE_COLUMNS = [
    "s1_proba",
    "c10_illiq_level_rank",
    "c11_ret_60d_lag_rank",
    "c12_gap_absorb_3",
    "c13_compress_blowoff_2",
    "c14_clv_volconf_resid_rank",
]
THESIS_FAMILY_COMPONENTS = {
    "momentum_continuation": ("s1_proba", "c11_ret_60d_lag_rank"),
    "breakout_followthrough": (
        "c8_vol_zscore_5d",
        "c12_gap_absorb_3",
        "c13_compress_blowoff_2",
        "c14_clv_volconf_resid_rank",
    ),
    "crowding_pressure": ("c7_ceiling_count_5d", "c10_illiq_level_rank"),
}
THESIS_FAMILY_NAMES = tuple(THESIS_FAMILY_COMPONENTS.keys())


@dataclass(frozen=True)
class ExecutionResult:
    executed_weights: np.ndarray
    buy_turnover: float
    sell_turnover: float
    total_turnover: float
    blocked_buy_indices: tuple[int, ...]
    blocked_sell_indices: tuple[int, ...]
    capacity_clipped_indices: tuple[int, ...]


@dataclass(frozen=True)
class StrategyRunResult:
    strategy_name: str
    signal_columns: tuple[str, ...]
    daily: pd.DataFrame
    summary: dict[str, object]
    blotter: pd.DataFrame | None = None


@dataclass(frozen=True)
class MarketInputs:
    dates: np.ndarray
    tickers: tuple[str, ...]
    benchmark_open: np.ndarray
    open_matrix: np.ndarray
    adv20_matrix: np.ndarray
    can_buy_matrix: np.ndarray
    can_sell_matrix: np.ndarray
    availability_matrix: np.ndarray
    score_matrices: Mapping[str, np.ndarray]
    tradability_source: str
    feature_matrices: Mapping[str, np.ndarray] = field(default_factory=dict)


def available_signal_columns(frame: pd.DataFrame) -> list[str]:
    return [col for col in frame.columns if col not in RESERVED_COLUMNS]


def default_strategy_names() -> tuple[str, ...]:
    return ("s1_only", "recent_core", "full_library")


def signal_fill_value(column: str) -> float:
    if column.endswith("_present"):
        return 0.0
    return 0.5


def resolve_strategy_columns(matrix_columns: list[str], strategy_name: str) -> list[str]:
    signal_columns = [col for col in matrix_columns if col not in RESERVED_COLUMNS]
    if strategy_name == "s1_only":
        cols = ["s1_proba"]
    elif strategy_name == "recent_core":
        cols = list(RECENT_CORE_COLUMNS)
    elif strategy_name == "full_library":
        cols = signal_columns
    else:
        raise ValueError(
            f"Unknown strategy {strategy_name!r}; expected one of {default_strategy_names()}"
        )

    missing = [col for col in cols if col not in signal_columns]
    if missing:
        raise ValueError(f"Strategy {strategy_name!r} requires missing columns: {missing}")
    return cols


def compute_strategy_scores(
    matrix: pd.DataFrame,
    strategy_columns: Mapping[str, list[str]],
) -> pd.DataFrame:
    scored = matrix[["time", "ticker", "actual"]].copy()
    for strategy_name, columns in strategy_columns.items():
        work = pd.DataFrame(index=matrix.index)
        for column in columns:
            numeric = pd.to_numeric(matrix[column], errors="coerce")
            if column.endswith("_present"):
                work[column] = numeric.fillna(0.0).clip(lower=0.0, upper=1.0)
            else:
                ranked = numeric.groupby(matrix["time"], sort=False).rank(method="average", pct=True)
                work[column] = ranked.fillna(signal_fill_value(column))
        scored[f"score__{strategy_name}"] = work.mean(axis=1)
    return scored


def load_price_panel(
    tickers: list[str],
    stock_dir: Path,
    *,
    adv_window: int = 20,
    adv_min_periods: int = 5,
) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for ticker in sorted(set(tickers)):
        path = stock_dir / f"gia_lich_su_{ticker}_1D.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path, columns=["time", "open", "high", "low", "close", "volume"])
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").reset_index(drop=True)
        df["ticker"] = ticker
        close = pd.to_numeric(df["close"], errors="coerce")
        high = pd.to_numeric(df["high"], errors="coerce")
        low = pd.to_numeric(df["low"], errors="coerce")
        volume = pd.to_numeric(df["volume"], errors="coerce")
        traded_value = close * volume
        df["adv20_value"] = traded_value.rolling(adv_window, min_periods=adv_min_periods).mean()
        df["adv5_value"] = traded_value.rolling(5, min_periods=3).mean()
        spread = high - low
        df["traded_value_vnd"] = traded_value
        df["clv"] = np.where(
            np.isfinite(spread) & (spread > 0.0),
            ((close - low) / spread).clip(0.0, 1.0),
            0.5,
        )
        parts.append(
            df[
                [
                    "time",
                    "ticker",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "traded_value_vnd",
                    "adv20_value",
                    "adv5_value",
                    "clv",
                ]
            ]
        )
    if not parts:
        return pd.DataFrame(
            columns=[
                "time",
                "ticker",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "traded_value_vnd",
                "adv20_value",
                "adv5_value",
                "clv",
            ]
        )
    return pd.concat(parts, ignore_index=True)


def load_or_build_tradability_panel(
    price_panel: pd.DataFrame,
    tradability_path: Path,
) -> tuple[pd.DataFrame, str]:
    if tradability_path.exists():
        tradability = pd.read_parquet(tradability_path)
        tradability["time"] = pd.to_datetime(tradability["time"])
        merged = price_panel[["time", "ticker"]].merge(
            tradability,
            on=["time", "ticker"],
            how="left",
            validate="one_to_one",
        )
        for column in [
            "has_volume",
            "is_ceiling",
            "is_floor",
            "can_buy_next_open",
            "can_sell_next_open",
        ]:
            merged[column] = merged[column].where(pd.notna(merged[column]), False).astype(bool)
        return merged, "artifact"

    parts: list[pd.DataFrame] = []
    for ticker, group in price_panel.groupby("ticker", sort=False):
        flags = compute_tradability_flags(group[["time", "ticker", "close", "volume"]].copy())
        parts.append(flags)
    tradability = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return tradability, "computed_on_the_fly"


def load_benchmark_open(benchmark_path: Path) -> pd.Series:
    benchmark = pd.read_parquet(benchmark_path, columns=["time", "open"])
    benchmark["time"] = pd.to_datetime(benchmark["time"])
    benchmark = benchmark.sort_values("time").drop_duplicates("time")
    return benchmark.set_index("time")["open"].astype(float)


def build_market_inputs(
    scored: pd.DataFrame,
    price_panel: pd.DataFrame,
    tradability: pd.DataFrame,
    benchmark_open: pd.Series,
    *,
    tradability_source: str,
    strategy_names: list[str],
    start_year: int,
    end_year: int,
    feature_frame: pd.DataFrame | None = None,
    feature_columns: list[str] | None = None,
) -> MarketInputs:
    universe = scored[(scored["time"].dt.year >= start_year) & (scored["time"].dt.year <= end_year)].copy()
    if universe.empty:
        raise ValueError(f"No signal rows in year range {start_year}-{end_year}")

    dates = np.asarray(sorted(universe["time"].drop_duplicates()), dtype="datetime64[ns]")
    tickers = tuple(sorted(universe["ticker"].drop_duplicates()))

    open_wide = (
        price_panel.pivot(index="time", columns="ticker", values="open")
        .reindex(index=pd.to_datetime(dates), columns=list(tickers))
        .sort_index()
    )
    adv20_wide = (
        price_panel.pivot(index="time", columns="ticker", values="adv20_value")
        .reindex(index=pd.to_datetime(dates), columns=list(tickers))
        .sort_index()
    )
    can_buy_wide = (
        tradability.pivot(index="time", columns="ticker", values="can_buy_next_open")
        .reindex(index=pd.to_datetime(dates), columns=list(tickers))
        .sort_index()
    )
    can_buy_wide = can_buy_wide.where(pd.notna(can_buy_wide), False).astype(bool)
    can_sell_wide = (
        tradability.pivot(index="time", columns="ticker", values="can_sell_next_open")
        .reindex(index=pd.to_datetime(dates), columns=list(tickers))
        .sort_index()
    )
    can_sell_wide = can_sell_wide.where(pd.notna(can_sell_wide), False).astype(bool)
    availability = (
        universe.assign(_available=True)
        .pivot(index="time", columns="ticker", values="_available")
        .reindex(index=pd.to_datetime(dates), columns=list(tickers))
        .sort_index()
    )
    availability = availability.where(pd.notna(availability), False).astype(bool)

    score_matrices: dict[str, np.ndarray] = {}
    for strategy_name in strategy_names:
        score_col = f"score__{strategy_name}"
        score_wide = (
            universe.pivot(index="time", columns="ticker", values=score_col)
            .reindex(index=pd.to_datetime(dates), columns=list(tickers))
            .sort_index()
        )
        score_matrices[strategy_name] = score_wide.to_numpy(dtype=np.float64)

    feature_matrices: dict[str, np.ndarray] = {}
    if feature_frame is not None:
        feature_universe = feature_frame[
            (feature_frame["time"].dt.year >= start_year) & (feature_frame["time"].dt.year <= end_year)
        ].copy()
        if not feature_universe.empty:
            columns = list(feature_columns) if feature_columns is not None else available_signal_columns(feature_universe)
            for column in columns:
                if column not in feature_universe.columns:
                    continue
                numeric = pd.to_numeric(feature_universe[column], errors="coerce")
                if column.endswith("_present"):
                    ranked_feature = numeric.fillna(0.0).clip(lower=0.0, upper=1.0)
                else:
                    ranked_feature = numeric.groupby(feature_universe["time"], sort=False).rank(method="average", pct=True)
                    ranked_feature = ranked_feature.fillna(signal_fill_value(column))
                ranked_wide = (
                    feature_universe.assign(_feature_value=ranked_feature)
                    .pivot(index="time", columns="ticker", values="_feature_value")
                    .reindex(index=pd.to_datetime(dates), columns=list(tickers))
                    .sort_index()
                )
                feature_matrices[str(column)] = ranked_wide.to_numpy(dtype=np.float64)

    benchmark = benchmark_open.reindex(pd.to_datetime(dates))
    return MarketInputs(
        dates=dates,
        tickers=tickers,
        benchmark_open=benchmark.to_numpy(dtype=np.float64),
        open_matrix=open_wide.to_numpy(dtype=np.float64),
        adv20_matrix=adv20_wide.to_numpy(dtype=np.float64),
        can_buy_matrix=can_buy_wide.to_numpy(dtype=bool),
        can_sell_matrix=can_sell_wide.to_numpy(dtype=bool),
        availability_matrix=availability.to_numpy(dtype=bool),
        score_matrices=score_matrices,
        tradability_source=str(tradability_source),
        feature_matrices=feature_matrices,
    )


def _safe_open_returns(open_t: np.ndarray, open_t1: np.ndarray) -> np.ndarray:
    returns = np.zeros_like(open_t, dtype=np.float64)
    valid = np.isfinite(open_t) & np.isfinite(open_t1) & (open_t > 0.0) & (open_t1 > 0.0)
    returns[valid] = (open_t1[valid] / open_t[valid]) - 1.0
    return returns


def _benchmark_return(open_t: float, open_t1: float) -> float:
    if not np.isfinite(open_t) or not np.isfinite(open_t1) or open_t <= 0.0 or open_t1 <= 0.0:
        return 0.0
    return float(open_t1 / open_t - 1.0)


def _update_holding_ages(
    previous_weights: np.ndarray,
    executed_weights: np.ndarray,
    previous_holding_ages: np.ndarray,
) -> np.ndarray:
    prev = np.asarray(previous_weights, dtype=np.float64)
    executed = np.asarray(executed_weights, dtype=np.float64)
    prev_ages = np.asarray(previous_holding_ages, dtype=np.int64)
    new_ages = np.zeros_like(prev_ages, dtype=np.int64)
    prev_active = prev > 1e-12
    exec_active = executed > 1e-12
    continued = prev_active & exec_active
    new_positions = (~prev_active) & exec_active
    new_ages[continued] = prev_ages[continued] + 1
    new_ages[new_positions] = 1
    return new_ages


def apply_execution_constraints(
    *,
    current_weights: np.ndarray,
    desired_weights: np.ndarray,
    holding_ages: np.ndarray,
    can_buy_next_open: np.ndarray,
    can_sell_next_open: np.ndarray,
    required_holding_age: int,
    max_weight_per_name: np.ndarray,
    max_buy_weight_delta: np.ndarray | None = None,
) -> ExecutionResult:
    current = np.asarray(current_weights, dtype=np.float64)
    desired = np.asarray(desired_weights, dtype=np.float64)
    ages = np.asarray(holding_ages, dtype=np.int64)
    can_buy = np.asarray(can_buy_next_open, dtype=bool)
    can_sell = np.asarray(can_sell_next_open, dtype=bool)
    max_weight = np.asarray(max_weight_per_name, dtype=np.float64)
    max_buy_delta = None if max_buy_weight_delta is None else np.asarray(max_buy_weight_delta, dtype=np.float64)

    executed = current.copy()
    blocked_sell_indices: list[int] = []
    for idx in range(len(current)):
        if desired[idx] >= current[idx] - 1e-12:
            continue
        if can_execute_sell(
            bool(can_sell[idx]),
            int(ages[idx]),
            min_hold_days_override=int(required_holding_age),
        ):
            executed[idx] = desired[idx]
        else:
            blocked_sell_indices.append(idx)

    cash_after_sells = max(1.0 - float(executed.sum()), 0.0)
    desired_buys = np.clip(desired - executed, 0.0, None)
    buy_headroom = np.maximum(max_weight - executed, 0.0)
    capped_buys = np.minimum(desired_buys, buy_headroom)
    if max_buy_delta is not None:
        capped_buys = np.minimum(capped_buys, np.maximum(max_buy_delta, 0.0))

    blocked_buy_mask = (desired_buys > 1e-12) & (~can_buy)
    capacity_clipped_mask = (desired_buys > capped_buys + 1e-12) & can_buy

    allowed_buys = capped_buys.copy()
    allowed_buys[~can_buy] = 0.0
    allowed_total = float(allowed_buys.sum())
    if allowed_total > 0.0 and cash_after_sells > 0.0:
        scale = min(1.0, cash_after_sells / allowed_total)
        executed += allowed_buys * scale

    buy_turnover = float(np.clip(executed - current, 0.0, None).sum())
    sell_turnover = float(np.clip(current - executed, 0.0, None).sum())
    return ExecutionResult(
        executed_weights=executed,
        buy_turnover=buy_turnover,
        sell_turnover=sell_turnover,
        total_turnover=buy_turnover + sell_turnover,
        blocked_buy_indices=tuple(np.flatnonzero(blocked_buy_mask).tolist()),
        blocked_sell_indices=tuple(blocked_sell_indices),
        capacity_clipped_indices=tuple(np.flatnonzero(capacity_clipped_mask).tolist()),
    )


def _max_drawdown(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return 0.0
    peaks = np.maximum.accumulate(arr)
    peaks = np.clip(peaks, 1e-12, None)
    drawdowns = (arr / peaks) - 1.0
    return float(drawdowns.min())


def _annualized_ratio(returns: np.ndarray) -> float | None:
    arr = np.asarray(returns, dtype=np.float64)
    if arr.size == 0:
        return None
    std = float(arr.std(ddof=0))
    if std <= 0.0:
        return None
    return float(arr.mean() / std * np.sqrt(252.0))


def _annualized_return(final_value: float, initial_value: float, periods: int) -> float | None:
    if periods <= 0 or initial_value <= 0.0 or final_value <= 0.0:
        return None
    return float((final_value / initial_value) ** (252.0 / periods) - 1.0)


def compute_capacity_weight_limits(
    *,
    adv20_value_vnd: np.ndarray,
    portfolio_value_vnd: float,
    max_adv_participation: float,
    max_position_vnd: float,
) -> np.ndarray:
    adv = np.asarray(adv20_value_vnd, dtype=np.float64)
    safe_value = max(float(portfolio_value_vnd), 1e-12)
    limits = np.ones_like(adv, dtype=np.float64)

    if max_adv_participation > 0.0:
        adv_limits = np.nan_to_num(
            adv * float(max_adv_participation) / safe_value,
            nan=0.0,
            posinf=1.0,
            neginf=0.0,
        )
        limits = np.minimum(limits, adv_limits)

    if max_position_vnd > 0.0:
        absolute_limit = np.full_like(limits, float(max_position_vnd) / safe_value, dtype=np.float64)
        limits = np.minimum(limits, absolute_limit)

    return np.clip(limits, 0.0, 1.0)


def compute_selected_target_weights(
    scores: np.ndarray,
    selected_indices: list[int] | tuple[int, ...],
    *,
    weighting: str,
) -> np.ndarray:
    scores_arr = np.asarray(scores, dtype=np.float64)
    target = np.zeros_like(scores_arr, dtype=np.float64)
    if not selected_indices:
        return target
    if weighting not in WEIGHTING_RULES:
        raise ValueError(f"Unknown weighting {weighting!r}; expected one of {WEIGHTING_RULES}")

    selected = np.asarray(selected_indices, dtype=np.int64)
    if weighting == "equal":
        raw = np.ones(len(selected), dtype=np.float64)
    else:
        selected_scores = scores_arr[selected]
        finite_scores = np.where(np.isfinite(selected_scores), selected_scores, np.nan)
        floor = np.nanmin(finite_scores) if np.any(np.isfinite(finite_scores)) else 0.0
        shifted = np.clip(selected_scores - float(floor), 0.0, None) + 1e-6
        raw = shifted if weighting == "linear" else shifted ** 2

    raw_sum = float(raw.sum())
    if raw_sum <= 0.0 or not np.isfinite(raw_sum):
        raw = np.ones(len(selected), dtype=np.float64)
        raw_sum = float(raw.sum())

    target[selected] = raw / raw_sum
    return target


def _rank_positions_desc(scores: np.ndarray, eligible_mask: np.ndarray) -> np.ndarray:
    score_arr = np.asarray(scores, dtype=np.float64)
    eligible = np.asarray(eligible_mask, dtype=bool) & np.isfinite(score_arr)
    out = np.full(score_arr.shape, np.nan, dtype=np.float64)
    ranked_pool = np.flatnonzero(eligible)
    if ranked_pool.size == 0:
        return out
    order = np.lexsort((ranked_pool, -score_arr[ranked_pool]))
    ranked = ranked_pool[order]
    out[ranked] = np.arange(1, len(ranked) + 1, dtype=np.float64)
    return out


def _build_thesis_family_matrix(feature_matrices: Mapping[str, np.ndarray]) -> tuple[np.ndarray, tuple[str, ...]]:
    family_names: list[str] = []
    family_parts: list[np.ndarray] = []
    for family_name, components in THESIS_FAMILY_COMPONENTS.items():
        mats = [np.asarray(feature_matrices[column], dtype=np.float64) for column in components if column in feature_matrices]
        if not mats:
            continue
        stacked = np.stack(mats, axis=0)
        valid_counts = np.sum(np.isfinite(stacked), axis=0)
        summed = np.nansum(stacked, axis=0)
        family_score = np.divide(
            summed,
            valid_counts,
            out=np.full_like(summed, np.nan, dtype=np.float64),
            where=valid_counts > 0,
        )
        family_parts.append(family_score)
        family_names.append(family_name)
    if not family_parts:
        return np.zeros((0, 0, 0), dtype=np.float64), tuple()
    return np.stack(family_parts, axis=0), tuple(family_names)


def _compute_exit_signal_mask(
    *,
    exit_rule_name: str | None,
    exit_rule_params: Mapping[str, object] | None,
    scores: np.ndarray,
    rank_positions: np.ndarray,
    holding_ages: np.ndarray,
    held_mask: np.ndarray,
    eligible_mask: np.ndarray,
    required_holding_age: int,
    top_k: int,
    blocked_sell_streaks: np.ndarray,
    entry_scores: np.ndarray,
    entry_rank_positions: np.ndarray,
    return_since_entry: np.ndarray,
    adv20_current: np.ndarray,
    entry_adv20_values: np.ndarray,
    peak_return_since_entry: np.ndarray,
    underwater_days_since_entry: np.ndarray,
    entry_thesis_family_codes: np.ndarray,
    entry_thesis_scores: np.ndarray,
    current_thesis_scores: np.ndarray | None,
    current_feature_values: Mapping[str, np.ndarray] | None = None,
) -> np.ndarray:
    exit_mask = np.zeros_like(held_mask, dtype=bool)
    if not exit_rule_name:
        return exit_mask

    params = dict(exit_rule_params or {})
    legal_to_exit = np.asarray(held_mask, dtype=bool) & (np.asarray(holding_ages, dtype=np.int64) >= int(required_holding_age))
    if not np.any(legal_to_exit):
        return exit_mask

    score_arr = np.asarray(scores, dtype=np.float64)
    rank_arr = np.asarray(rank_positions, dtype=np.float64)
    eligible = np.asarray(eligible_mask, dtype=bool)
    held = np.asarray(held_mask, dtype=bool)
    blocked_streak = np.asarray(blocked_sell_streaks, dtype=np.int64)
    entry_score_arr = np.asarray(entry_scores, dtype=np.float64)
    entry_rank_arr = np.asarray(entry_rank_positions, dtype=np.float64)
    entry_return_arr = np.asarray(return_since_entry, dtype=np.float64)
    peak_return_arr = np.asarray(peak_return_since_entry, dtype=np.float64)
    underwater_days_arr = np.asarray(underwater_days_since_entry, dtype=np.int64)
    adv_current_arr = np.asarray(adv20_current, dtype=np.float64)
    entry_adv_arr = np.asarray(entry_adv20_values, dtype=np.float64)

    nonheld_pool = eligible & ~held & np.isfinite(score_arr)
    best_nonheld_score = float(np.nanmax(score_arr[nonheld_pool])) if np.any(nonheld_pool) else float("nan")
    score_margin = np.nan_to_num(best_nonheld_score - score_arr, nan=-np.inf)
    raw_rank_threshold = params.get("rank_exit_threshold", top_k)
    rank_threshold = top_k if raw_rank_threshold is None else int(raw_rank_threshold)
    rank_violation = np.nan_to_num(rank_arr, nan=np.inf) > float(rank_threshold)
    score_drop = np.nan_to_num(entry_score_arr - score_arr, nan=0.0)
    adv_ratio = np.nan_to_num(
        adv_current_arr / np.clip(entry_adv_arr, 1e-12, None),
        nan=np.inf,
        posinf=np.inf,
        neginf=0.0,
    )

    family = str(exit_rule_name)
    if family == "multi_rule_any":
        rules = list(params.get("rules", []))
        combo = np.zeros_like(held_mask, dtype=bool)
        for rule in rules:
            if not isinstance(rule, Mapping):
                continue
            combo |= _compute_exit_signal_mask(
                exit_rule_name=str(rule.get("name") or ""),
                exit_rule_params=rule.get("params"),
                scores=scores,
                rank_positions=rank_positions,
                holding_ages=holding_ages,
                held_mask=held_mask,
                eligible_mask=eligible_mask,
                required_holding_age=required_holding_age,
                top_k=top_k,
                blocked_sell_streaks=blocked_sell_streaks,
                entry_scores=entry_scores,
                entry_rank_positions=entry_rank_positions,
                return_since_entry=return_since_entry,
                adv20_current=adv20_current,
                entry_adv20_values=entry_adv20_values,
                peak_return_since_entry=peak_return_since_entry,
                underwater_days_since_entry=underwater_days_since_entry,
                entry_thesis_family_codes=entry_thesis_family_codes,
                entry_thesis_scores=entry_thesis_scores,
                current_thesis_scores=current_thesis_scores,
                current_feature_values=current_feature_values,
            )
        exit_mask = combo
    elif family == "rank_decay":
        margin = float(params.get("replacement_margin", 0.0))
        margin_ok = np.ones_like(score_margin, dtype=bool) if margin <= 0.0 else score_margin >= margin
        exit_mask = legal_to_exit & rank_violation & margin_ok
    elif family == "time_plus_decay":
        extra_hold = int(params.get("min_hold_extra_days", 0))
        eligible_after_extra = held & (np.asarray(holding_ages, dtype=np.int64) >= int(required_holding_age) + extra_hold)
        mode = str(params.get("mode", "or"))
        score_drop_threshold = float(params.get("score_drop_threshold", 0.05))
        score_violation = score_drop >= score_drop_threshold
        if mode == "rank_only":
            exit_mask = eligible_after_extra & rank_violation
        elif mode == "score_only":
            exit_mask = eligible_after_extra & score_violation
        elif mode == "and":
            exit_mask = eligible_after_extra & rank_violation & score_violation
        else:
            exit_mask = eligible_after_extra & (rank_violation | score_violation)
    elif family == "sticky_winner":
        rank_buffer = int(params.get("rank_buffer", 0))
        margin = float(params.get("replacement_margin", 0.02))
        buffered_violation = np.nan_to_num(rank_arr, nan=np.inf) > float(top_k + rank_buffer)
        exit_mask = legal_to_exit & buffered_violation & (score_margin >= margin)
    elif family == "liquidity_deterioration":
        blocked_streak_threshold = int(params.get("blocked_sell_streak_threshold", 2))
        adv_drop_ratio_threshold = float(params.get("adv20_ratio_threshold", 0.70))
        exit_mask = legal_to_exit & (
            (blocked_streak >= blocked_streak_threshold)
            | (adv_ratio <= adv_drop_ratio_threshold)
        )
    elif family == "strength_exhaustion":
        return_threshold = float(params.get("return_since_entry_threshold", 0.15))
        score_drop_threshold = float(params.get("score_drop_threshold", 0.05))
        exit_mask = legal_to_exit & (entry_return_arr >= return_threshold) & (score_drop >= score_drop_threshold)
    elif family == "replacement_pressure":
        margin = float(params.get("replacement_margin", 0.02))
        exit_mask = legal_to_exit & (score_margin >= margin)
    elif family == "thesis_inconsistency":
        thesis_drop_threshold = float(params.get("thesis_drop_threshold", 0.15))
        score_drop_threshold = float(params.get("score_drop_threshold", 0.05))
        valid_codes = np.asarray(entry_thesis_family_codes, dtype=np.int64)
        current_thesis = np.full_like(score_arr, np.nan, dtype=np.float64)
        if current_thesis_scores is not None and current_thesis_scores.size > 0:
            valid_idx = legal_to_exit & (valid_codes >= 0) & (valid_codes < current_thesis_scores.shape[0])
            held_positions = np.flatnonzero(valid_idx)
            if held_positions.size > 0:
                current_thesis[held_positions] = current_thesis_scores[valid_codes[held_positions], held_positions]
        thesis_drop = np.nan_to_num(np.asarray(entry_thesis_scores, dtype=np.float64) - current_thesis, nan=0.0)
        exit_mask = legal_to_exit & np.isfinite(current_thesis) & (thesis_drop >= thesis_drop_threshold) & (score_drop >= score_drop_threshold)
    elif family == "failed_followthrough":
        grace_days = int(params.get("grace_days", 2))
        peak_return_threshold = float(params.get("peak_return_threshold", 0.03))
        current_return_threshold = float(params.get("current_return_threshold", 0.0))
        score_drop_threshold = float(params.get("score_drop_threshold", 0.0))
        eligible_after_grace = held & (np.asarray(holding_ages, dtype=np.int64) >= int(required_holding_age) + grace_days)
        exit_mask = (
            eligible_after_grace
            & (peak_return_arr <= peak_return_threshold)
            & (entry_return_arr <= current_return_threshold)
            & (score_drop >= score_drop_threshold)
        )
    elif family == "time_under_water":
        grace_days = int(params.get("grace_days", 5))
        underwater_days_threshold = int(params.get("underwater_days_threshold", 3))
        peak_return_threshold = float(params.get("peak_return_threshold", 0.05))
        eligible_after_grace = held & (np.asarray(holding_ages, dtype=np.int64) >= int(required_holding_age) + grace_days)
        exit_mask = (
            eligible_after_grace
            & (underwater_days_arr >= underwater_days_threshold)
            & (peak_return_arr <= peak_return_threshold)
            & (entry_return_arr <= 0.0)
        )
    elif family == "continuation_hazard":
        continue_prob_threshold = float(params.get("continue_prob_threshold", 0.50))
        thesis_change = np.full_like(score_arr, 0.0, dtype=np.float64)
        if current_thesis_scores is not None and current_thesis_scores.size > 0:
            valid_codes = np.asarray(entry_thesis_family_codes, dtype=np.int64)
            valid_idx = legal_to_exit & (valid_codes >= 0) & (valid_codes < current_thesis_scores.shape[0])
            held_positions = np.flatnonzero(valid_idx)
            if held_positions.size > 0:
                thesis_change[held_positions] = (
                    current_thesis_scores[valid_codes[held_positions], held_positions]
                    - np.asarray(entry_thesis_scores, dtype=np.float64)[held_positions]
                )
        feature_lookup: dict[str, np.ndarray] = {
            "holding_age_before": np.asarray(holding_ages, dtype=np.float64),
            "score_change_since_entry": np.nan_to_num(score_arr - entry_score_arr, nan=0.0),
            "return_since_entry": np.nan_to_num(entry_return_arr, nan=0.0),
            "peak_return_since_entry": np.nan_to_num(peak_return_arr, nan=0.0),
            "underwater_days_since_entry": np.asarray(underwater_days_arr, dtype=np.float64),
            "blocked_sell_streak": np.asarray(blocked_streak, dtype=np.float64),
            "thesis_score_change_since_entry": np.nan_to_num(thesis_change, nan=0.0),
            "score_rank": np.nan_to_num(rank_arr, nan=0.0),
            "entry_rank": np.nan_to_num(entry_rank_arr, nan=0.0),
        }
        for feature_name, values in (current_feature_values or {}).items():
            feature_lookup[str(feature_name)] = np.nan_to_num(np.asarray(values, dtype=np.float64), nan=0.0)
        linear = float(params.get("intercept", 0.0))
        legacy_map = {
            "coef_holding_age_before": "holding_age_before",
            "coef_score_change_since_entry": "score_change_since_entry",
            "coef_return_since_entry": "return_since_entry",
            "coef_peak_return_since_entry": "peak_return_since_entry",
            "coef_underwater_days_since_entry": "underwater_days_since_entry",
            "coef_blocked_sell_streak": "blocked_sell_streak",
            "coef_thesis_score_change_since_entry": "thesis_score_change_since_entry",
            "coef_score_rank": "score_rank",
            "coef_entry_rank": "entry_rank",
        }
        for param_name, feature_name in legacy_map.items():
            coef = float(params.get(param_name, 0.0))
            if coef != 0.0:
                linear += coef * feature_lookup[feature_name]
        for param_name, value in params.items():
            if not str(param_name).startswith("coef__"):
                continue
            feature_name = str(param_name).split("coef__", 1)[1]
            feature_values = feature_lookup.get(feature_name)
            if feature_values is None:
                continue
            linear += float(value) * feature_values
        continue_prob = 1.0 / (1.0 + np.exp(-np.clip(linear, -50.0, 50.0)))
        exit_mask = legal_to_exit & (continue_prob < continue_prob_threshold)
    else:
        raise ValueError(f"Unknown exit_rule_name {exit_rule_name!r}")

    return exit_mask.astype(bool)


def _build_blotter_rows(
    *,
    strategy_name: str,
    tickers: tuple[str, ...],
    signal_date: pd.Timestamp,
    execution_date: pd.Timestamp,
    scores: np.ndarray,
    adv20_value_vnd: np.ndarray,
    current_weights: np.ndarray,
    desired_weights: np.ndarray,
    executed_weights: np.ndarray,
    selected_indices: list[int],
    blocked_buy_indices: tuple[int, ...],
    blocked_sell_indices: tuple[int, ...],
    capacity_clipped_indices: tuple[int, ...],
    can_buy_next_open: np.ndarray,
    can_sell_next_open: np.ndarray,
    holding_ages: np.ndarray,
    portfolio_value_before_rebalance_vnd: float,
    capacity_weight_limits: np.ndarray,
    weighting: str,
    rank_positions: np.ndarray,
    entry_scores: np.ndarray,
    entry_rank_positions: np.ndarray,
    return_since_entry: np.ndarray,
    peak_return_since_entry: np.ndarray,
    underwater_days_since_entry: np.ndarray,
    blocked_sell_streaks: np.ndarray,
    exit_signal_indices: tuple[int, ...],
    entry_thesis_family_names: tuple[str | None, ...],
    entry_thesis_scores: np.ndarray,
    current_thesis_scores: np.ndarray,
) -> list[dict[str, object]]:
    detail_indices = sorted(
        set(selected_indices)
        | set(np.flatnonzero(current_weights > 1e-12).tolist())
        | set(np.flatnonzero(desired_weights > 1e-12).tolist())
        | set(np.flatnonzero(executed_weights > 1e-12).tolist())
        | set(blocked_buy_indices)
        | set(blocked_sell_indices)
        | set(capacity_clipped_indices)
    )
    if not detail_indices:
        return []

    blocked_buy = set(blocked_buy_indices)
    blocked_sell = set(blocked_sell_indices)
    capacity_clipped = set(capacity_clipped_indices)
    exit_signal = set(exit_signal_indices)
    rows: list[dict[str, object]] = []
    safe_value = max(float(portfolio_value_before_rebalance_vnd), 1e-12)

    for idx in detail_indices:
        adv_value = float(adv20_value_vnd[idx]) if np.isfinite(adv20_value_vnd[idx]) else float("nan")
        current_weight = float(current_weights[idx])
        desired_weight = float(desired_weights[idx])
        executed_weight = float(executed_weights[idx])
        current_notional = current_weight * safe_value
        desired_notional = desired_weight * safe_value
        executed_notional = executed_weight * safe_value
        denom = adv_value if np.isfinite(adv_value) and adv_value > 0.0 else np.nan

        if desired_weight > current_weight + 1e-12:
            requested_action = "buy"
        elif desired_weight < current_weight - 1e-12:
            requested_action = "sell"
        else:
            requested_action = "hold"

        if executed_weight > current_weight + 1e-12:
            executed_action = "buy"
        elif executed_weight < current_weight - 1e-12:
            executed_action = "sell"
        else:
            executed_action = "hold"

        rows.append(
            {
                "strategy": strategy_name,
                "signal_date": signal_date.isoformat(),
                "execution_date": execution_date.isoformat(),
                "ticker": tickers[idx],
                "weighting_rule": weighting,
                "signal_score": float(scores[idx]) if np.isfinite(scores[idx]) else None,
                "score_rank": float(rank_positions[idx]) if np.isfinite(rank_positions[idx]) else None,
                "entry_score": float(entry_scores[idx]) if np.isfinite(entry_scores[idx]) else None,
                "entry_rank": float(entry_rank_positions[idx]) if np.isfinite(entry_rank_positions[idx]) else None,
                "score_change_since_entry": float(scores[idx] - entry_scores[idx])
                if np.isfinite(scores[idx]) and np.isfinite(entry_scores[idx]) else None,
                "return_since_entry": float(return_since_entry[idx]) if np.isfinite(return_since_entry[idx]) else None,
                "peak_return_since_entry": float(peak_return_since_entry[idx]) if np.isfinite(peak_return_since_entry[idx]) else None,
                "underwater_days_since_entry": int(underwater_days_since_entry[idx]),
                "blocked_sell_streak": int(blocked_sell_streaks[idx]),
                "entry_thesis_family": entry_thesis_family_names[idx],
                "entry_thesis_score": float(entry_thesis_scores[idx]) if np.isfinite(entry_thesis_scores[idx]) else None,
                "current_thesis_score": float(current_thesis_scores[idx]) if np.isfinite(current_thesis_scores[idx]) else None,
                "thesis_score_change_since_entry": float(current_thesis_scores[idx] - entry_thesis_scores[idx])
                if np.isfinite(current_thesis_scores[idx]) and np.isfinite(entry_thesis_scores[idx]) else None,
                "exit_signal": bool(idx in exit_signal),
                "selected": bool(idx in selected_indices),
                "holding_age_before": int(holding_ages[idx]),
                "held_before": bool(current_weight > 1e-12),
                "held_after": bool(executed_weight > 1e-12),
                "requested_action": requested_action,
                "executed_action": executed_action,
                "can_buy_next_open": bool(can_buy_next_open[idx]),
                "can_sell_next_open": bool(can_sell_next_open[idx]),
                "buy_blocked": bool(idx in blocked_buy),
                "sell_blocked": bool(idx in blocked_sell),
                "capacity_clipped": bool(idx in capacity_clipped),
                "current_weight": current_weight,
                "desired_weight": desired_weight,
                "executed_weight": executed_weight,
                "current_notional_vnd": current_notional,
                "target_notional_vnd": desired_notional,
                "executed_notional_vnd": executed_notional,
                "turnover_weight": float(abs(executed_weight - current_weight)),
                "turnover_vnd": float(abs(executed_notional - current_notional)),
                "adv20_value_vnd": adv_value if np.isfinite(adv_value) else None,
                "capacity_weight_limit": float(capacity_weight_limits[idx]),
                "capacity_limit_notional_vnd": float(capacity_weight_limits[idx] * safe_value),
                "current_pct_adv20": float(current_notional / denom) if np.isfinite(denom) else None,
                "target_pct_adv20": float(desired_notional / denom) if np.isfinite(denom) else None,
                "executed_pct_adv20": float(executed_notional / denom) if np.isfinite(denom) else None,
            }
        )

    return rows


def summarize_daily_results(
    daily: pd.DataFrame,
    *,
    initial_notional_vnd: float,
    top_k: int,
) -> dict[str, object]:
    if daily.empty:
        return {
            "days": 0,
            "final_portfolio_value_vnd": float(initial_notional_vnd),
            "final_benchmark_value_vnd": float(initial_notional_vnd),
            "portfolio_total_return": 0.0,
            "benchmark_total_return": 0.0,
            "relative_total_return": 0.0,
            "portfolio_sharpe_annualized": None,
            "information_ratio_annualized": None,
            "max_drawdown": 0.0,
            "positive_years": 0,
            "total_years": 0,
            "avg_daily_turnover": 0.0,
            "avg_cash_weight": 1.0,
            "avg_num_holdings": 0.0,
            "avg_invested_weight": 0.0,
            "avg_universe_size": 0.0,
            "avg_selected_count": 0.0,
            "rebalance_days": 0,
            "blocked_buy_events": 0,
            "blocked_sell_events": 0,
            "capacity_clipped_events": 0,
            "avg_holding_age": 0.0,
            "avg_pending_entry_count": 0.0,
            "exit_rule_trigger_events": 0,
            "avg_exit_signal_count": 0.0,
            "per_year": [],
            "top_k": int(top_k),
        }

    final_portfolio_value = float(daily["portfolio_value_vnd"].iloc[-1])
    final_benchmark_value = float(daily["benchmark_value_vnd"].iloc[-1])
    portfolio_total_return = final_portfolio_value / float(initial_notional_vnd) - 1.0
    benchmark_total_return = final_benchmark_value / float(initial_notional_vnd) - 1.0
    relative_total_return = final_portfolio_value / max(final_benchmark_value, 1e-12) - 1.0
    portfolio_annualized_return = _annualized_return(
        final_portfolio_value,
        float(initial_notional_vnd),
        int(len(daily)),
    )
    benchmark_annualized_return = _annualized_return(
        final_benchmark_value,
        float(initial_notional_vnd),
        int(len(daily)),
    )
    relative_annualized_return = _annualized_return(
        final_portfolio_value / max(final_benchmark_value, 1e-12),
        1.0,
        int(len(daily)),
    )

    portfolio_return = daily["portfolio_return"].to_numpy(dtype=np.float64)
    relative_return = daily["relative_return"].to_numpy(dtype=np.float64)

    daily = daily.copy()
    daily["year"] = pd.to_datetime(daily["execution_date"]).dt.year
    per_year = []
    for year, group in daily.groupby("year", sort=True):
        port_gross = float(np.prod(1.0 + group["portfolio_return"].to_numpy(dtype=np.float64)) - 1.0)
        bench_gross = float(np.prod(1.0 + group["benchmark_return"].to_numpy(dtype=np.float64)) - 1.0)
        rel_gross = float(
            np.prod(
                (1.0 + group["portfolio_return"].to_numpy(dtype=np.float64))
                / np.clip(1.0 + group["benchmark_return"].to_numpy(dtype=np.float64), 1e-12, None)
            )
            - 1.0
        )
        per_year.append(
            {
                "year": int(year),
                "portfolio_return": round(port_gross, 6),
                "benchmark_return": round(bench_gross, 6),
                "relative_return": round(rel_gross, 6),
                "avg_turnover": round(float(group["turnover"].mean()), 6),
                "avg_cash_weight": round(float(group["cash_weight"].mean()), 6),
                "avg_num_holdings": round(float(group["num_holdings"].mean()), 4),
                "days": int(len(group)),
            }
        )

    return {
        "days": int(len(daily)),
        "final_portfolio_value_vnd": round(final_portfolio_value, 2),
        "final_benchmark_value_vnd": round(final_benchmark_value, 2),
        "portfolio_total_return": round(portfolio_total_return, 6),
        "benchmark_total_return": round(benchmark_total_return, 6),
        "relative_total_return": round(relative_total_return, 6),
        "portfolio_annualized_return": round(portfolio_annualized_return, 6)
        if portfolio_annualized_return is not None else None,
        "benchmark_annualized_return": round(benchmark_annualized_return, 6)
        if benchmark_annualized_return is not None else None,
        "relative_annualized_return": round(relative_annualized_return, 6)
        if relative_annualized_return is not None else None,
        "portfolio_sharpe_annualized": round(_annualized_ratio(portfolio_return), 6)
        if _annualized_ratio(portfolio_return) is not None else None,
        "information_ratio_annualized": round(_annualized_ratio(relative_return), 6)
        if _annualized_ratio(relative_return) is not None else None,
        "max_drawdown": round(_max_drawdown(daily["portfolio_value_vnd"].to_numpy(dtype=np.float64)), 6),
        "positive_years": int(sum(1 for row in per_year if row["portfolio_return"] > 0.0)),
        "total_years": int(len(per_year)),
        "avg_daily_turnover": round(float(daily["turnover"].mean()), 6),
        "avg_cash_weight": round(float(daily["cash_weight"].mean()), 6),
        "avg_num_holdings": round(float(daily["num_holdings"].mean()), 4),
        "avg_invested_weight": round(float((1.0 - daily["cash_weight"]).mean()), 6),
        "avg_universe_size": round(float(daily["eligible_universe_size"].mean()), 4),
        "avg_selected_count": round(float(daily["selected_count"].mean()), 4),
        "rebalance_days": int((daily["turnover"] > 1e-12).sum()),
        "blocked_buy_events": int(daily["blocked_buy_count"].sum()),
        "blocked_sell_events": int(daily["blocked_sell_count"].sum()),
        "capacity_clipped_events": int(daily["capacity_clipped_count"].sum()),
        "avg_holding_age": round(float(daily["avg_holding_age"].mean()), 4),
        "avg_pending_entry_count": round(float(daily["pending_entry_count"].mean()), 4)
        if "pending_entry_count" in daily.columns else 0.0,
        "exit_rule_trigger_events": int(daily["exit_signal_count"].sum())
        if "exit_signal_count" in daily.columns else 0,
        "avg_exit_signal_count": round(float(daily["exit_signal_count"].mean()), 4)
        if "exit_signal_count" in daily.columns else 0.0,
        "per_year": per_year,
        "top_k": int(top_k),
    }


def simulate_strategy(
    *,
    strategy_name: str,
    signal_columns: list[str],
    market_inputs: MarketInputs,
    top_k: int,
    rebalance_every: int,
    weighting: str,
    initial_notional_vnd: float,
    max_adv_participation: float,
    required_holding_age: int,
    buy_fee_rate: float,
    sell_fee_rate: float,
    capital_gains_tax_rate: float,
    min_score: float | None = None,
    min_adv20_value_vnd: float = 0.0,
    max_position_vnd: float = 0.0,
    max_names_if_liquidity_thin: int | None = None,
    entry_allowed_matrix: np.ndarray | None = None,
    entry_slice_days: int = 1,
    daily_buy_adv_participation: float = 0.0,
    min_deployable_weight: float = 0.0,
    capture_blotter: bool = False,
    activation_mask: np.ndarray | None = None,
    activation_scale: np.ndarray | None = None,
    incumbent_score_bonus: float | np.ndarray = 0.0,
    sector_labels: tuple[str | None, ...] | None = None,
    max_names_per_sector: int | None = None,
    exit_rule_name: str | None = None,
    exit_rule_params: Mapping[str, object] | None = None,
) -> StrategyRunResult:
    if top_k <= 0:
        raise ValueError("top_k must be > 0")
    if rebalance_every <= 0:
        raise ValueError("rebalance_every must be > 0")
    if weighting not in WEIGHTING_RULES:
        raise ValueError(f"Unknown weighting {weighting!r}; expected one of {WEIGHTING_RULES}")
    if entry_slice_days <= 0:
        raise ValueError("entry_slice_days must be > 0")
    if min_deployable_weight < 0.0 or min_deployable_weight > 1.0:
        raise ValueError("min_deployable_weight must be within [0, 1]")
    if max_names_per_sector is not None and max_names_per_sector <= 0:
        raise ValueError("max_names_per_sector must be > 0 when provided")

    dates = pd.to_datetime(market_inputs.dates)
    tickers = market_inputs.tickers
    n_dates = len(dates)
    n_tickers = len(tickers)
    if n_dates < 2:
        raise ValueError("Need at least two dates to simulate open-to-open portfolio returns")

    score_matrix = np.asarray(market_inputs.score_matrices[strategy_name], dtype=np.float64)
    open_matrix = np.asarray(market_inputs.open_matrix, dtype=np.float64)
    adv20_matrix = np.asarray(market_inputs.adv20_matrix, dtype=np.float64)
    can_buy_matrix = np.asarray(market_inputs.can_buy_matrix, dtype=bool)
    can_sell_matrix = np.asarray(market_inputs.can_sell_matrix, dtype=bool)
    availability_matrix = np.asarray(market_inputs.availability_matrix, dtype=bool)
    benchmark_open = np.asarray(market_inputs.benchmark_open, dtype=np.float64)
    thesis_family_matrix, thesis_family_names = _build_thesis_family_matrix(getattr(market_inputs, "feature_matrices", {}) or {})
    if entry_allowed_matrix is None:
        entry_allowed = np.ones_like(availability_matrix, dtype=bool)
    else:
        entry_allowed = np.asarray(entry_allowed_matrix, dtype=bool)
        if entry_allowed.shape != availability_matrix.shape:
            raise ValueError(
                "entry_allowed_matrix must match availability_matrix shape "
                f"{availability_matrix.shape}; got {entry_allowed.shape}"
            )
    if activation_mask is not None and activation_scale is not None:
        raise ValueError("Provide at most one of activation_mask or activation_scale")
    if activation_scale is not None:
        activation_schedule = np.asarray(activation_scale, dtype=np.float64)
        if activation_schedule.shape != (n_dates,):
            raise ValueError(
                "activation_scale must match dates shape "
                f"({n_dates},); got {activation_schedule.shape}"
            )
        activation_schedule = np.clip(
            np.nan_to_num(activation_schedule, nan=0.0, posinf=1.0, neginf=0.0),
            0.0,
            1.0,
        )
    elif activation_mask is not None:
        activation_allowed = np.asarray(activation_mask, dtype=bool)
        if activation_allowed.shape != (n_dates,):
            raise ValueError(
                "activation_mask must match dates shape "
                f"({n_dates},); got {activation_allowed.shape}"
            )
        activation_schedule = activation_allowed.astype(np.float64)
    else:
        activation_schedule = np.ones(n_dates, dtype=np.float64)
    if np.isscalar(incumbent_score_bonus):
        incumbent_bonus_schedule = np.full(n_dates, float(incumbent_score_bonus), dtype=np.float64)
    else:
        incumbent_bonus_schedule = np.asarray(incumbent_score_bonus, dtype=np.float64)
        if incumbent_bonus_schedule.shape != (n_dates,):
            raise ValueError(
                "incumbent_score_bonus must be scalar or match dates shape "
                f"({n_dates},); got {incumbent_bonus_schedule.shape}"
            )
        incumbent_bonus_schedule = np.nan_to_num(incumbent_bonus_schedule, nan=0.0)
    if sector_labels is not None and len(sector_labels) != n_tickers:
        raise ValueError(
            "sector_labels must align with tickers "
            f"({n_tickers}); got {len(sector_labels)}"
        )

    weights = np.zeros(n_tickers, dtype=np.float64)
    holding_ages = np.zeros(n_tickers, dtype=np.int64)
    cash_weight = 1.0
    portfolio_value = float(initial_notional_vnd)
    benchmark_value = float(initial_notional_vnd)
    last_rebalance_step = -rebalance_every
    pending_entry_target = np.zeros(n_tickers, dtype=np.float64)
    pending_entry_days_left = np.zeros(n_tickers, dtype=np.int64)
    pending_plan_started_count = 0
    pending_entry_days_total = 0
    partial_fill_count = 0
    expired_entry_plan_count = 0
    entry_scores = np.full(n_tickers, np.nan, dtype=np.float64)
    entry_rank_positions = np.full(n_tickers, np.nan, dtype=np.float64)
    entry_open_prices = np.full(n_tickers, np.nan, dtype=np.float64)
    entry_adv20_values = np.full(n_tickers, np.nan, dtype=np.float64)
    peak_return_since_entry = np.full(n_tickers, 0.0, dtype=np.float64)
    underwater_days_since_entry = np.zeros(n_tickers, dtype=np.int64)
    entry_thesis_family_codes = np.full(n_tickers, -1, dtype=np.int64)
    entry_thesis_scores = np.full(n_tickers, np.nan, dtype=np.float64)
    blocked_sell_streaks = np.zeros(n_tickers, dtype=np.int64)

    records: list[dict[str, object]] = []
    blotter_records: list[dict[str, object]] = []
    for step in range(n_dates - 1):
        open_t = open_matrix[step]
        open_t1 = open_matrix[step + 1]
        asset_returns = _safe_open_returns(open_t, open_t1)
        benchmark_ret = _benchmark_return(benchmark_open[step], benchmark_open[step + 1])

        asset_values_before = weights * portfolio_value * (1.0 + asset_returns)
        cash_value_before = cash_weight * portfolio_value
        value_before_rebalance = float(asset_values_before.sum() + cash_value_before)
        if value_before_rebalance <= 0.0:
            value_before_rebalance = 1e-12

        drifted_weights = asset_values_before / value_before_rebalance
        benchmark_value *= 1.0 + benchmark_ret

        do_rebalance = bool(
            drifted_weights.sum() <= 1e-12 or (step - last_rebalance_step) >= rebalance_every
        )
        activation_exposure = float(activation_schedule[step])
        activation_on = activation_exposure > 1e-12
        scores = score_matrix[step]
        adv20_for_execution = adv20_matrix[step]
        capacity_weights = compute_capacity_weight_limits(
            adv20_value_vnd=adv20_for_execution,
            portfolio_value_vnd=value_before_rebalance,
            max_adv_participation=max_adv_participation,
            max_position_vnd=max_position_vnd,
        )
        daily_buy_limits = None
        if daily_buy_adv_participation > 0.0:
            daily_buy_limits = compute_capacity_weight_limits(
                adv20_value_vnd=adv20_for_execution,
                portfolio_value_vnd=value_before_rebalance,
                max_adv_participation=daily_buy_adv_participation,
                max_position_vnd=0.0,
            )
        eligible = availability_matrix[step].copy()
        if min_score is not None:
            eligible &= scores >= float(min_score)
        if min_adv20_value_vnd > 0.0:
            eligible &= np.isfinite(adv20_for_execution) & (adv20_for_execution >= float(min_adv20_value_vnd))
        if min_deployable_weight > 0.0:
            eligible &= capacity_weights >= float(min_deployable_weight)
        held_mask = drifted_weights > 1e-12
        eligible &= held_mask | entry_allowed[step]
        rank_positions = _rank_positions_desc(scores, availability_matrix[step])
        return_since_entry = np.full(n_tickers, np.nan, dtype=np.float64)
        valid_entry_return = (
            held_mask
            & np.isfinite(entry_open_prices)
            & (entry_open_prices > 0.0)
            & np.isfinite(open_t)
            & (open_t > 0.0)
        )
        return_since_entry[valid_entry_return] = open_t[valid_entry_return] / entry_open_prices[valid_entry_return] - 1.0
        peak_return_since_entry = np.where(
            held_mask & np.isfinite(return_since_entry),
            np.maximum(peak_return_since_entry, np.nan_to_num(return_since_entry, nan=-np.inf)),
            peak_return_since_entry,
        )
        peak_return_since_entry = np.where(held_mask, peak_return_since_entry, 0.0)
        underwater_days_since_entry = np.where(
            held_mask & np.isfinite(return_since_entry) & (return_since_entry <= 0.0),
            underwater_days_since_entry + 1,
            underwater_days_since_entry,
        ).astype(np.int64)
        underwater_days_since_entry = np.where(held_mask, underwater_days_since_entry, 0).astype(np.int64)
        blocked_sell_streaks = np.where(
            held_mask & ~can_sell_matrix[step],
            blocked_sell_streaks + 1,
            0,
        ).astype(np.int64)
        blocked_sell_streaks = np.where(held_mask, blocked_sell_streaks, 0).astype(np.int64)
        if thesis_family_matrix.size > 0:
            current_thesis_scores = thesis_family_matrix[:, step, :]
        else:
            current_thesis_scores = np.zeros((0, n_tickers), dtype=np.float64)
        current_feature_values = {
            str(feature_name): np.asarray(feature_matrix[step], dtype=np.float64)
            for feature_name, feature_matrix in (getattr(market_inputs, "feature_matrices", {}) or {}).items()
            if np.asarray(feature_matrix).ndim == 2 and np.asarray(feature_matrix).shape[0] > step
        }
        current_entry_thesis_scores = np.full(n_tickers, np.nan, dtype=np.float64)
        if current_thesis_scores.size > 0:
            valid_thesis_positions = held_mask & (entry_thesis_family_codes >= 0) & (entry_thesis_family_codes < current_thesis_scores.shape[0])
            thesis_idx = np.flatnonzero(valid_thesis_positions)
            if thesis_idx.size > 0:
                current_entry_thesis_scores[thesis_idx] = current_thesis_scores[entry_thesis_family_codes[thesis_idx], thesis_idx]

        selected_indices: list[int] = []
        desired_weights = drifted_weights.copy()
        exit_signal_mask = np.zeros(n_tickers, dtype=bool)
        if do_rebalance:
            if activation_on and np.any(eligible):
                ranked_pool = np.flatnonzero(eligible)
                ranked_scores = scores[ranked_pool]
                effective_scores = ranked_scores.copy()
                current_incumbent_bonus = float(incumbent_bonus_schedule[step])
                if current_incumbent_bonus > 0.0:
                    incumbent_mask = drifted_weights[ranked_pool] > 1e-12
                    effective_scores[incumbent_mask] += current_incumbent_bonus
                order = np.lexsort((ranked_pool, -ranked_scores, -effective_scores))
                selection_cap = int(top_k)
                if max_names_if_liquidity_thin is not None and len(ranked_pool) < top_k:
                    selection_cap = min(selection_cap, int(max_names_if_liquidity_thin))
                ranked_candidates = ranked_pool[order[: len(order)]].tolist()
                if exit_rule_name:
                    exit_signal_mask = _compute_exit_signal_mask(
                        exit_rule_name=exit_rule_name,
                        exit_rule_params=exit_rule_params,
                        scores=scores,
                        rank_positions=rank_positions,
                        holding_ages=holding_ages,
                        held_mask=held_mask,
                        eligible_mask=availability_matrix[step],
                        required_holding_age=required_holding_age,
                        top_k=top_k,
                        blocked_sell_streaks=blocked_sell_streaks,
                        entry_scores=entry_scores,
                        entry_rank_positions=entry_rank_positions,
                        return_since_entry=return_since_entry,
                        adv20_current=adv20_for_execution,
                        entry_adv20_values=entry_adv20_values,
                        peak_return_since_entry=peak_return_since_entry,
                        underwater_days_since_entry=underwater_days_since_entry,
                        entry_thesis_family_codes=entry_thesis_family_codes,
                        entry_thesis_scores=entry_thesis_scores,
                        current_thesis_scores=current_thesis_scores,
                        current_feature_values=current_feature_values,
                    )
                    retained = [idx for idx in ranked_candidates if held_mask[idx] and not exit_signal_mask[idx]]
                    if max_names_per_sector is not None and sector_labels is not None:
                        counts: dict[str | None, int] = {}
                        retained_kept: list[int] = []
                        for idx in retained:
                            sector = sector_labels[idx]
                            if counts.get(sector, 0) >= int(max_names_per_sector):
                                continue
                            retained_kept.append(idx)
                            counts[sector] = counts.get(sector, 0) + 1
                            if len(retained_kept) >= selection_cap:
                                break
                        retained = retained_kept
                        remaining_candidates: list[int] = []
                        for idx in ranked_candidates:
                            if held_mask[idx]:
                                continue
                            sector = sector_labels[idx]
                            if counts.get(sector, 0) >= int(max_names_per_sector):
                                continue
                            remaining_candidates.append(idx)
                            if len(retained) + len(remaining_candidates) >= selection_cap:
                                break
                        selected_indices = retained + remaining_candidates[: max(selection_cap - len(retained), 0)]
                    else:
                        remaining_candidates = [idx for idx in ranked_candidates if not held_mask[idx]]
                        selected_indices = retained[:selection_cap]
                        if len(selected_indices) < selection_cap:
                            selected_indices.extend(remaining_candidates[: selection_cap - len(selected_indices)])
                elif max_names_per_sector is not None and sector_labels is not None:
                    counts: dict[str | None, int] = {}
                    selected_indices = []
                    for idx in ranked_candidates:
                        sector = sector_labels[idx]
                        if counts.get(sector, 0) >= int(max_names_per_sector):
                            continue
                        selected_indices.append(idx)
                        counts[sector] = counts.get(sector, 0) + 1
                        if len(selected_indices) >= selection_cap:
                            break
                else:
                    selected_indices = ranked_candidates[: min(selection_cap, len(ranked_candidates))]
                if selected_indices:
                    desired_weights = compute_selected_target_weights(
                        scores,
                        selected_indices,
                        weighting=weighting,
                    )
                    desired_weights *= activation_exposure
                    last_rebalance_step = step
                else:
                    desired_weights = np.zeros(n_tickers, dtype=np.float64)
            elif activation_on:
                desired_weights = np.zeros(n_tickers, dtype=np.float64)
            else:
                desired_weights = np.zeros(n_tickers, dtype=np.float64)
                last_rebalance_step = step
            pending_entry_target = np.zeros(n_tickers, dtype=np.float64)
            pending_entry_days_left = np.zeros(n_tickers, dtype=np.int64)
        elif entry_slice_days > 1 and np.any(pending_entry_days_left > 0):
            active_pending = pending_entry_days_left > 0
            pending_entry_days_total += int(np.count_nonzero(active_pending))
            desired_weights = np.maximum(desired_weights, pending_entry_target)

        can_buy_next_open = can_buy_matrix[step] & np.isfinite(open_t1) & (open_t1 > 0.0)
        can_sell_next_open = can_sell_matrix[step] & np.isfinite(open_t1) & (open_t1 > 0.0)

        execution_result = apply_execution_constraints(
            current_weights=drifted_weights,
            desired_weights=desired_weights,
            holding_ages=holding_ages,
            can_buy_next_open=can_buy_next_open,
            can_sell_next_open=can_sell_next_open,
            required_holding_age=required_holding_age,
            max_weight_per_name=capacity_weights,
            max_buy_weight_delta=daily_buy_limits,
        )

        if entry_slice_days > 1:
            requested_buy_mask = desired_weights > drifted_weights + 1e-12
            partial_fill_mask = (
                requested_buy_mask
                & (execution_result.executed_weights > drifted_weights + 1e-12)
                & (execution_result.executed_weights < desired_weights - 1e-12)
            )
            partial_fill_count += int(np.count_nonzero(partial_fill_mask))

        transaction_cost = (
            execution_result.buy_turnover * float(buy_fee_rate)
            + execution_result.sell_turnover * (float(sell_fee_rate) + float(capital_gains_tax_rate))
        )
        if capture_blotter:
            blotter_records.extend(
                _build_blotter_rows(
                    strategy_name=strategy_name,
                    tickers=tickers,
                    signal_date=dates[step],
                    execution_date=dates[step + 1],
                    scores=scores,
                    adv20_value_vnd=adv20_for_execution,
                    current_weights=drifted_weights,
                    desired_weights=desired_weights,
                    executed_weights=execution_result.executed_weights,
                    selected_indices=selected_indices,
                    blocked_buy_indices=execution_result.blocked_buy_indices,
                    blocked_sell_indices=execution_result.blocked_sell_indices,
                    capacity_clipped_indices=execution_result.capacity_clipped_indices,
                    can_buy_next_open=can_buy_next_open,
                    can_sell_next_open=can_sell_next_open,
                    holding_ages=holding_ages,
                    portfolio_value_before_rebalance_vnd=value_before_rebalance,
                    capacity_weight_limits=capacity_weights,
                    weighting=weighting,
                    rank_positions=rank_positions,
                    entry_scores=entry_scores,
                    entry_rank_positions=entry_rank_positions,
                    return_since_entry=return_since_entry,
                    peak_return_since_entry=peak_return_since_entry,
                    underwater_days_since_entry=underwater_days_since_entry,
                    blocked_sell_streaks=blocked_sell_streaks,
                    exit_signal_indices=tuple(np.flatnonzero(exit_signal_mask).tolist()),
                    entry_thesis_family_names=tuple(
                        thesis_family_names[code] if 0 <= code < len(thesis_family_names) else None
                        for code in entry_thesis_family_codes
                    ),
                    entry_thesis_scores=entry_thesis_scores,
                    current_thesis_scores=current_entry_thesis_scores,
                )
            )
        value_after_rebalance = value_before_rebalance * max(1.0 - transaction_cost, 0.0)
        new_positions_mask = (~held_mask) & (execution_result.executed_weights > 1e-12)
        sold_mask = held_mask & (execution_result.executed_weights <= 1e-12)
        weights = execution_result.executed_weights
        holding_ages = _update_holding_ages(
            previous_weights=drifted_weights,
            executed_weights=weights,
            previous_holding_ages=holding_ages,
        )
        entry_scores = np.where(new_positions_mask, scores, entry_scores)
        entry_scores = np.where(sold_mask, np.nan, entry_scores)
        entry_rank_positions = np.where(new_positions_mask, rank_positions, entry_rank_positions)
        entry_rank_positions = np.where(sold_mask, np.nan, entry_rank_positions)
        entry_open_prices = np.where(new_positions_mask, open_t1, entry_open_prices)
        entry_open_prices = np.where(sold_mask, np.nan, entry_open_prices)
        entry_adv20_values = np.where(new_positions_mask, adv20_for_execution, entry_adv20_values)
        entry_adv20_values = np.where(sold_mask, np.nan, entry_adv20_values)
        if thesis_family_matrix.size > 0:
            current_entry_family_scores = current_thesis_scores
            best_family_codes = np.argmax(current_entry_family_scores, axis=0).astype(np.int64)
            best_family_scores = np.take_along_axis(current_entry_family_scores, best_family_codes.reshape(1, -1), axis=0).reshape(-1)
            best_family_codes = np.where(np.any(np.isfinite(current_entry_family_scores), axis=0), best_family_codes, -1)
            best_family_scores = np.where(best_family_codes >= 0, best_family_scores, np.nan)
        else:
            best_family_codes = np.full(n_tickers, -1, dtype=np.int64)
            best_family_scores = np.full(n_tickers, np.nan, dtype=np.float64)
        entry_thesis_family_codes = np.where(new_positions_mask, best_family_codes, entry_thesis_family_codes)
        entry_thesis_family_codes = np.where(sold_mask, -1, entry_thesis_family_codes)
        entry_thesis_scores = np.where(new_positions_mask, best_family_scores, entry_thesis_scores)
        entry_thesis_scores = np.where(sold_mask, np.nan, entry_thesis_scores)
        peak_return_since_entry = np.where(new_positions_mask, 0.0, peak_return_since_entry)
        peak_return_since_entry = np.where(sold_mask, 0.0, peak_return_since_entry)
        underwater_days_since_entry = np.where(new_positions_mask, 0, underwater_days_since_entry).astype(np.int64)
        underwater_days_since_entry = np.where(sold_mask, 0, underwater_days_since_entry).astype(np.int64)
        blocked_sell_streaks = np.where(sold_mask, 0, blocked_sell_streaks)
        blocked_sell_streaks = np.where(new_positions_mask, 0, blocked_sell_streaks)
        if entry_slice_days > 1:
            if do_rebalance:
                new_pending_mask = desired_weights > weights + 1e-12
                pending_entry_target = np.where(new_pending_mask, desired_weights, 0.0)
                pending_entry_days_left = np.where(new_pending_mask, int(entry_slice_days) - 1, 0)
                pending_plan_started_count += int(np.count_nonzero(new_pending_mask))
            else:
                active_pending = pending_entry_days_left > 0
                expired_mask = active_pending & (pending_entry_days_left == 1) & (pending_entry_target > weights + 1e-12)
                expired_entry_plan_count += int(np.count_nonzero(expired_mask))
                still_active_mask = active_pending & ~expired_mask
                pending_entry_days_left = np.where(still_active_mask, pending_entry_days_left - 1, 0)
                pending_entry_target = np.where(still_active_mask, pending_entry_target, 0.0)
        cash_weight = float(max(1.0 - float(weights.sum()), 0.0))
        portfolio_return = value_after_rebalance / portfolio_value - 1.0
        portfolio_value = float(value_after_rebalance)

        active_mask = weights > 1e-12
        avg_holding_age = float(np.mean(holding_ages[active_mask])) if np.any(active_mask) else 0.0
        records.append(
            {
                "strategy": strategy_name,
                "signal_date": dates[step].isoformat(),
                "execution_date": dates[step + 1].isoformat(),
                "portfolio_value_vnd": portfolio_value,
                "benchmark_value_vnd": float(benchmark_value),
                "portfolio_return": float(portfolio_return),
                "benchmark_return": float(benchmark_ret),
                "relative_return": float(portfolio_return - benchmark_ret),
                "turnover": float(execution_result.total_turnover),
                "buy_turnover": float(execution_result.buy_turnover),
                "sell_turnover": float(execution_result.sell_turnover),
                "cash_weight": float(cash_weight),
                "num_holdings": int(np.count_nonzero(active_mask)),
                "avg_holding_age": float(avg_holding_age),
                "blocked_buy_count": int(len(execution_result.blocked_buy_indices)),
                "blocked_sell_count": int(len(execution_result.blocked_sell_indices)),
                "capacity_clipped_count": int(len(execution_result.capacity_clipped_indices)),
                "eligible_universe_size": int(np.count_nonzero(eligible)),
                "selected_count": int(len(selected_indices) if do_rebalance else np.count_nonzero(weights > 1e-12)),
                "pending_entry_count": int(np.count_nonzero(pending_entry_days_left > 0)),
                "rebalance_triggered": bool(do_rebalance),
                "exit_rule_name": str(exit_rule_name) if exit_rule_name else None,
                "exit_signal_count": int(np.count_nonzero(exit_signal_mask)),
                "activation_on": bool(activation_on),
                "activation_scale": float(activation_exposure),
                "weighting_rule": weighting,
                "requested_tickers": [tickers[idx] for idx in selected_indices],
                "exit_signal_tickers": [tickers[idx] for idx in np.flatnonzero(exit_signal_mask)],
                "held_tickers": [tickers[idx] for idx in np.flatnonzero(active_mask)],
            }
        )

    daily = pd.DataFrame.from_records(records)
    summary = summarize_daily_results(
        daily,
        initial_notional_vnd=initial_notional_vnd,
        top_k=top_k,
    )
    if entry_slice_days > 1:
        avg_pending_entry_days = (
            float(pending_entry_days_total) / float(pending_plan_started_count)
            if pending_plan_started_count > 0 else 0.0
        )
        summary.update(
            {
                "entry_slice_days": int(entry_slice_days),
                "avg_pending_entry_days": round(avg_pending_entry_days, 4),
                "expired_entry_plan_count": int(expired_entry_plan_count),
                "partial_fill_count": int(partial_fill_count),
            }
        )
    if daily_buy_adv_participation > 0.0:
        summary["daily_buy_adv_participation"] = round(float(daily_buy_adv_participation), 6)
    if min_deployable_weight > 0.0:
        summary["min_deployable_weight"] = round(float(min_deployable_weight), 6)
    blotter = pd.DataFrame.from_records(blotter_records) if capture_blotter else None
    return StrategyRunResult(
        strategy_name=strategy_name,
        signal_columns=tuple(signal_columns),
        daily=daily,
        summary=summary,
        blotter=blotter,
    )
