from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))

from shared_market_rules import required_holding_age_for_sell

from src.activation_alpha import (
    ACTIVATION_STATE_PATH,
    BENCHMARK_PATH,
    RL_MATRIX_PATH,
    STOCK_DIR,
    TRADABILITY_PATH,
    load_activation_experiment_inputs,
    load_or_build_activation_state,
    selector_definitions,
)
from src.deterministic_portfolio import simulate_strategy

ACTIVATION_META_PATH = Path("data/features/activation_meta_daily.parquet")


def _forward_gross_returns(series: pd.Series, window: int) -> pd.Series:
    arr = pd.to_numeric(series, errors="coerce").to_numpy(dtype=np.float64)
    out = np.full(arr.shape[0], np.nan, dtype=np.float64)
    if window <= 0:
        return pd.Series(out, index=series.index, dtype=float)
    for idx in range(arr.shape[0]):
        end = idx + int(window)
        if end > arr.shape[0]:
            break
        window_arr = arr[idx:end]
        if np.all(np.isfinite(window_arr)):
            out[idx] = float(np.prod(1.0 + window_arr) - 1.0)
    return pd.Series(out, index=series.index, dtype=float)


def _days_since_reset(reset_mask: pd.Series) -> pd.Series:
    out: list[int] = []
    last_reset = -1
    for idx, is_reset in enumerate(reset_mask.fillna(False).astype(bool).tolist()):
        if is_reset:
            last_reset = idx
            out.append(0)
        elif last_reset < 0:
            out.append(idx + 1)
        else:
            out.append(idx - last_reset)
    return pd.Series(out, index=reset_mask.index, dtype=float)


def _selector_meta_from_daily(
    daily: pd.DataFrame,
    *,
    prefix: str,
    rebalance_every: int,
) -> pd.DataFrame:
    work = daily.copy()
    work["time"] = pd.to_datetime(work["signal_date"])
    work = work.sort_values("time").drop_duplicates("time")

    port_ret = pd.to_numeric(work["portfolio_return"], errors="coerce")
    rel_ret = pd.to_numeric(work["relative_return"], errors="coerce")
    work[f"{prefix}_future_cycle_return"] = _forward_gross_returns(port_ret, int(rebalance_every))
    work[f"{prefix}_future_cycle_relative_return"] = _forward_gross_returns(rel_ret, int(rebalance_every))
    work[f"{prefix}_future_cycle_hit"] = (work[f"{prefix}_future_cycle_relative_return"] > 0.0).astype(float)

    work[f"{prefix}_prev_cycle_return"] = _forward_gross_returns(port_ret, int(rebalance_every)).shift(1)
    work[f"{prefix}_prev_cycle_relative_return"] = _forward_gross_returns(rel_ret, int(rebalance_every)).shift(1)
    work[f"{prefix}_prev_two_cycle_return"] = _forward_gross_returns(port_ret, int(rebalance_every) * 2).shift(1)
    work[f"{prefix}_prev_two_cycle_relative_return"] = _forward_gross_returns(rel_ret, int(rebalance_every) * 2).shift(1)
    work[f"{prefix}_prev_cycle_hit"] = (work[f"{prefix}_prev_cycle_relative_return"] > 0.0).astype(float)

    for span in (3, 5):
        work[f"{prefix}_recent_cycle_return_ewm{span}"] = pd.to_numeric(
            work[f"{prefix}_prev_cycle_return"], errors="coerce"
        ).ewm(span=span, adjust=False, min_periods=1).mean()
        work[f"{prefix}_recent_cycle_relative_return_ewm{span}"] = pd.to_numeric(
            work[f"{prefix}_prev_cycle_relative_return"], errors="coerce"
        ).ewm(span=span, adjust=False, min_periods=1).mean()
        work[f"{prefix}_recent_hit_rate_ewm{span}"] = pd.to_numeric(
            work[f"{prefix}_prev_cycle_hit"], errors="coerce"
        ).ewm(span=span, adjust=False, min_periods=1).mean()
        work[f"{prefix}_recent_turnover_ewm{span}"] = pd.to_numeric(
            work["turnover"], errors="coerce"
        ).ewm(span=span, adjust=False, min_periods=1).mean()
        work[f"{prefix}_recent_cash_weight_ewm{span}"] = pd.to_numeric(
            work["cash_weight"], errors="coerce"
        ).ewm(span=span, adjust=False, min_periods=1).mean()
        work[f"{prefix}_recent_blocked_buy_ewm{span}"] = pd.to_numeric(
            work["blocked_buy_count"], errors="coerce"
        ).ewm(span=span, adjust=False, min_periods=1).mean()
        work[f"{prefix}_recent_holding_age_ewm{span}"] = pd.to_numeric(
            work["avg_holding_age"], errors="coerce"
        ).ewm(span=span, adjust=False, min_periods=1).mean()

    portfolio_value = pd.to_numeric(work["portfolio_value_vnd"], errors="coerce")
    rolling_peak = portfolio_value.cummax()
    rolling_peak = rolling_peak.where(rolling_peak > 0.0)
    drawdown = portfolio_value / rolling_peak - 1.0
    work[f"{prefix}_selector_drawdown"] = drawdown
    work[f"{prefix}_days_since_peak"] = _days_since_reset(drawdown >= -1e-12)
    work[f"{prefix}_days_in_drawdown"] = np.where(drawdown < -1e-12, work[f"{prefix}_days_since_peak"], 0.0)
    trough20 = portfolio_value.rolling(20, min_periods=5).min()
    work[f"{prefix}_recovery_from_20d_trough"] = portfolio_value / trough20 - 1.0
    work[f"{prefix}_selector_drawdown_bucket"] = pd.cut(
        drawdown,
        bins=[-np.inf, -0.20, -0.10, -0.05, -1e-12, np.inf],
        labels=[0, 1, 2, 3, 4],
    ).astype(float)

    keep = [column for column in work.columns if column == "time" or column.startswith(f"{prefix}_")]
    return work[keep].copy()


def build_activation_meta_frame(
    *,
    activation_state: pd.DataFrame,
    matrix_path: Path = RL_MATRIX_PATH,
    tradability_path: Path = TRADABILITY_PATH,
    stock_dir: Path = STOCK_DIR,
    benchmark_path: Path = BENCHMARK_PATH,
    start_year: int = 2015,
    end_year: int = 2025,
    round_trip_cost: float = 0.003,
    required_holding_age: int = 3,
    initial_notional_vnd: float = 100_000_000.0,
) -> pd.DataFrame:
    inputs = load_activation_experiment_inputs(
        matrix_path=matrix_path,
        tradability_path=tradability_path,
        stock_dir=stock_dir,
        benchmark_path=benchmark_path,
        start_year=start_year,
        end_year=end_year,
    )
    fee_leg = float(round_trip_cost) / 2.0
    hold_age = required_holding_age_for_sell(min_hold_days_override=int(required_holding_age))

    selector_meta_parts: list[pd.DataFrame] = []
    for selector in inputs.selectors:
        prefix = "full" if selector.strategy_name == "full_library" else "s1"
        result = simulate_strategy(
            strategy_name=selector.strategy_name,
            signal_columns=list(selector.signal_columns),
            market_inputs=inputs.market_inputs,
            top_k=int(selector.top_k),
            rebalance_every=int(selector.rebalance_every),
            weighting=str(selector.weighting),
            initial_notional_vnd=float(initial_notional_vnd),
            max_adv_participation=0.0,
            required_holding_age=int(hold_age),
            buy_fee_rate=float(fee_leg),
            sell_fee_rate=float(fee_leg),
            capital_gains_tax_rate=0.0,
        )
        selector_meta_parts.append(
            _selector_meta_from_daily(
                result.daily,
                prefix=prefix,
                rebalance_every=int(selector.rebalance_every),
            )
        )

    meta = activation_state.copy()
    meta["time"] = pd.to_datetime(meta["time"])
    for part in selector_meta_parts:
        meta = meta.merge(part, on="time", how="left", validate="one_to_one")

    delta_columns = [
        "full_top10_buyable_count",
        "full_top10_liq_open_count",
        "full_top5_blocked_buy_count",
        "liq_open_breadth_all",
        "buyable_breadth_all",
        "full_top1_minus_top5_spread",
        "full_top5_score_std",
        "full_top5_mean_clv",
        "full_top5_mean_tv_to_adv20_rank",
        "selector_top5_jaccard",
    ]
    for column in delta_columns:
        if column in meta.columns:
            numeric = pd.to_numeric(meta[column], errors="coerce")
            meta[f"delta_{column}_1d"] = numeric.diff()
            meta[f"delta_{column}_5d"] = numeric.diff(5)

    meta["selector_confidence_combo"] = (
        pd.to_numeric(meta.get("full_top1_minus_top5_spread"), errors="coerce").rank(method="average", pct=True)
        + pd.to_numeric(meta.get("full_top5_mean_score"), errors="coerce").rank(method="average", pct=True)
        + pd.to_numeric(meta.get("full_top5_score_std"), errors="coerce").rank(method="average", pct=True)
        + pd.to_numeric(meta.get("full_top5_prev_overlap_ratio"), errors="coerce").rank(method="average", pct=True)
    ) / 4.0

    meta["selector_entry_quality_combo"] = (
        pd.to_numeric(meta.get("full_top5_mean_clv"), errors="coerce").clip(0.0, 1.0)
        + pd.to_numeric(meta.get("full_top5_mean_tv_to_adv20_rank"), errors="coerce").clip(0.0, 1.0)
        + pd.to_numeric(meta.get("full_top5_buyable_count"), errors="coerce").clip(0.0, 5.0) / 5.0
    ) / 3.0

    for column in meta.columns:
        if column != "time":
            meta[column] = pd.to_numeric(meta[column], errors="coerce")
    meta = meta.sort_values("time").reset_index(drop=True)
    return meta


def persist_activation_meta(
    *,
    out_path: Path = ACTIVATION_META_PATH,
    matrix_path: Path = RL_MATRIX_PATH,
    tradability_path: Path = TRADABILITY_PATH,
    stock_dir: Path = STOCK_DIR,
    benchmark_path: Path = BENCHMARK_PATH,
    activation_state_path: Path = ACTIVATION_STATE_PATH,
    start_year: int = 2015,
    end_year: int = 2025,
    round_trip_cost: float = 0.003,
    required_holding_age: int = 3,
    initial_notional_vnd: float = 100_000_000.0,
) -> pd.DataFrame:
    activation_state, _ = load_or_build_activation_state(
        out_path=activation_state_path,
        matrix_path=matrix_path,
        tradability_path=tradability_path,
        stock_dir=stock_dir,
        benchmark_path=benchmark_path,
        start_year=start_year,
        end_year=end_year,
    )
    frame = build_activation_meta_frame(
        activation_state=activation_state,
        matrix_path=matrix_path,
        tradability_path=tradability_path,
        stock_dir=stock_dir,
        benchmark_path=benchmark_path,
        start_year=start_year,
        end_year=end_year,
        round_trip_cost=round_trip_cost,
        required_holding_age=required_holding_age,
        initial_notional_vnd=initial_notional_vnd,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out_path, index=False)
    return frame


def load_or_build_activation_meta(
    *,
    out_path: Path = ACTIVATION_META_PATH,
    matrix_path: Path = RL_MATRIX_PATH,
    tradability_path: Path = TRADABILITY_PATH,
    stock_dir: Path = STOCK_DIR,
    benchmark_path: Path = BENCHMARK_PATH,
    activation_state_path: Path = ACTIVATION_STATE_PATH,
    start_year: int = 2015,
    end_year: int = 2025,
    round_trip_cost: float = 0.003,
    required_holding_age: int = 3,
    initial_notional_vnd: float = 100_000_000.0,
) -> tuple[pd.DataFrame, str]:
    required_columns = {
        "full_future_cycle_relative_return",
        "s1_future_cycle_relative_return",
        "full_recent_cycle_relative_return_ewm3",
        "s1_recent_cycle_relative_return_ewm3",
        "full_selector_drawdown",
        "s1_selector_drawdown",
        "delta_liq_open_breadth_all_1d",
        "selector_confidence_combo",
        "selector_entry_quality_combo",
    }
    if out_path.exists():
        frame = pd.read_parquet(out_path)
        frame["time"] = pd.to_datetime(frame["time"])
        if required_columns.issubset(frame.columns):
            return frame, "artifact"
    frame = persist_activation_meta(
        out_path=out_path,
        matrix_path=matrix_path,
        tradability_path=tradability_path,
        stock_dir=stock_dir,
        benchmark_path=benchmark_path,
        activation_state_path=activation_state_path,
        start_year=start_year,
        end_year=end_year,
        round_trip_cost=round_trip_cost,
        required_holding_age=required_holding_age,
        initial_notional_vnd=initial_notional_vnd,
    )
    return frame, "built"
