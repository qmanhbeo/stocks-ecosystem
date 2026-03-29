"""
H183: Activated-vs-always-on live scoreboard for the current-year paper book.

Compares the current champion selector:
    full_library + k5_r5_eq

against the current champion activation overlay:
    h175__rel2_gt0

using the matrix-supported current-year slice.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
SHARED_MARKET_RULES_ROOT = WORKSPACE_ROOT / "shared-market-rules"
if str(SHARED_MARKET_RULES_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_MARKET_RULES_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared_market_rules import required_holding_age_for_sell

from src.activation_alpha import compute_cycle_metrics, load_activation_experiment_inputs
from src.activation_meta import ACTIVATION_META_PATH, load_or_build_activation_meta
from src.activation_meta_experiment_utils import (
    ACTIVATION_STATE_PATH,
    BENCHMARK_PATH,
    RL_MATRIX_PATH,
    STOCK_DIR,
    TRADABILITY_PATH,
    selector_recent_relative_ewm_from_prev,
)
from src.deterministic_portfolio import simulate_strategy
from src.run_summary import write_run_summary

OUT_DIR = Path("artifacts/portfolio_baselines")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--activation-state", type=str, default=str(ACTIVATION_STATE_PATH))
    parser.add_argument("--activation-meta", type=str, default=str(ACTIVATION_META_PATH))
    parser.add_argument("--history-start-year", type=int, default=2019)
    parser.add_argument("--evaluation-year", type=int, default=2026)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--incumbent-score-bonus", type=float, default=0.0)
    return parser.parse_args()


def _jsonable(value):
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _slice_year(daily: pd.DataFrame, year: int) -> pd.DataFrame:
    work = daily.copy()
    work["signal_date"] = pd.to_datetime(work["signal_date"])
    work["execution_date"] = pd.to_datetime(work["execution_date"])
    return work.loc[work["execution_date"].dt.year == int(year)].reset_index(drop=True)


def _summarize_slice(daily: pd.DataFrame) -> dict[str, object]:
    if daily.empty:
        return {
            "days": 0,
            "portfolio_total_return": None,
            "benchmark_total_return": None,
            "relative_total_return": None,
            "information_ratio_annualized": None,
            "max_drawdown": None,
            "avg_cash_weight": None,
            "avg_num_holdings": None,
            "latest_day": {},
            "cycle_metrics": compute_cycle_metrics(daily),
        }

    portfolio_curve = np.cumprod(1.0 + daily["portfolio_return"].to_numpy(dtype=np.float64))
    benchmark_curve = np.cumprod(1.0 + daily["benchmark_return"].to_numpy(dtype=np.float64))
    relative_curve = np.cumprod(1.0 + daily["relative_return"].to_numpy(dtype=np.float64))
    latest = daily.iloc[-1].to_dict()
    latest["signal_date"] = pd.Timestamp(latest["signal_date"])
    latest["execution_date"] = pd.Timestamp(latest["execution_date"])
    ir = None
    rel_arr = daily["relative_return"].to_numpy(dtype=np.float64)
    if len(rel_arr) > 1 and np.std(rel_arr, ddof=0) > 0:
        ir = float(np.mean(rel_arr) / np.std(rel_arr, ddof=0) * np.sqrt(252.0))
    peaks = np.maximum.accumulate(portfolio_curve)
    drawdown = float(np.min(portfolio_curve / np.clip(peaks, 1e-12, None) - 1.0))
    return {
        "days": int(len(daily)),
        "portfolio_total_return": float(portfolio_curve[-1] - 1.0),
        "benchmark_total_return": float(benchmark_curve[-1] - 1.0),
        "relative_total_return": float(relative_curve[-1] - 1.0),
        "information_ratio_annualized": ir,
        "max_drawdown": drawdown,
        "avg_cash_weight": float(pd.to_numeric(daily["cash_weight"], errors="coerce").mean()),
        "avg_num_holdings": float(pd.to_numeric(daily["num_holdings"], errors="coerce").mean()),
        "latest_day": _jsonable(latest),
        "cycle_metrics": compute_cycle_metrics(daily),
    }


def main() -> None:
    args = parse_args()
    inputs = load_activation_experiment_inputs(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.history_start_year),
        end_year=int(args.evaluation_year),
    )
    meta_state, meta_source = load_or_build_activation_meta(
        out_path=Path(args.activation_meta),
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        activation_state_path=Path(args.activation_state),
        start_year=int(args.history_start_year),
        end_year=int(args.evaluation_year),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
        initial_notional_vnd=float(args.initial_notional_vnd),
    )

    selector = next(selector for selector in inputs.selectors if selector.name == "full_library_k5_r5_eq")
    rel2 = selector_recent_relative_ewm_from_prev(meta_state, prefix="full", span=2)
    gate = rel2 > 0.0
    aligned = (
        pd.DataFrame({"time": pd.to_datetime(meta_state["time"]), "activation_scale": gate.astype(float), "recent_rel2": rel2})
        .drop_duplicates("time")
        .set_index("time")
        .reindex(pd.to_datetime(inputs.market_inputs.dates))
    )
    activation_scale = aligned["activation_scale"].fillna(0.0).to_numpy(dtype=np.float64)

    fee_leg = float(args.round_trip_cost) / 2.0
    hold_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))
    common_kwargs = dict(
        strategy_name=selector.strategy_name,
        signal_columns=list(selector.signal_columns),
        market_inputs=inputs.market_inputs,
        top_k=int(selector.top_k),
        rebalance_every=int(selector.rebalance_every),
        weighting=str(selector.weighting),
        initial_notional_vnd=float(args.initial_notional_vnd),
        max_adv_participation=0.0,
        required_holding_age=int(hold_age),
        buy_fee_rate=float(fee_leg),
        sell_fee_rate=float(fee_leg),
        capital_gains_tax_rate=0.0,
        incumbent_score_bonus=float(args.incumbent_score_bonus),
    )

    always_on = simulate_strategy(**common_kwargs)
    activated = simulate_strategy(**common_kwargs, activation_scale=activation_scale)

    always_on_slice = _slice_year(always_on.daily, int(args.evaluation_year))
    activated_slice = _slice_year(activated.daily, int(args.evaluation_year))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_path = OUT_DIR / f"{ts}_h183_live_activation_scoreboard_daily.parquet"
    daily = activated_slice.copy()
    daily["variant"] = "activated"
    base_daily = always_on_slice.copy()
    base_daily["variant"] = "always_on"
    pd.concat([daily, base_daily], ignore_index=True).to_parquet(daily_path, index=False)

    activated_summary = _summarize_slice(activated_slice)
    always_summary = _summarize_slice(always_on_slice)
    summary = {
        "meta_source": meta_source,
        "activation_rule": "h175__rel2_gt0",
        "incumbent_score_bonus": float(args.incumbent_score_bonus),
        "selector": selector.name,
        "evaluation_year": int(args.evaluation_year),
        "activated": activated_summary,
        "always_on": always_summary,
        "delta_relative_total_return": (
            None
            if activated_summary["relative_total_return"] is None or always_summary["relative_total_return"] is None
            else float(activated_summary["relative_total_return"] - always_summary["relative_total_return"])
        ),
        "delta_information_ratio_annualized": (
            None
            if activated_summary["information_ratio_annualized"] is None or always_summary["information_ratio_annualized"] is None
            else float(activated_summary["information_ratio_annualized"] - always_summary["information_ratio_annualized"])
        ),
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_live_activation_scoreboard",
        name="h183_live_activation_scoreboard",
        summary=summary,
        artifacts={"daily": str(daily_path)},
        metadata={
            "matrix": str(args.matrix),
            "activation_meta": str(args.activation_meta),
            "history_start_year": int(args.history_start_year),
            "evaluation_year": int(args.evaluation_year),
        },
    )

    print("\nH183: LIVE ACTIVATION SCOREBOARD")
    print(pd.DataFrame([{
        "variant": "activated",
        "relative_total_return": activated_summary["relative_total_return"],
        "information_ratio_annualized": activated_summary["information_ratio_annualized"],
        "avg_cash_weight": activated_summary["avg_cash_weight"],
        "latest_held_tickers": activated_summary["latest_day"].get("held_tickers", []),
    }, {
        "variant": "always_on",
        "relative_total_return": always_summary["relative_total_return"],
        "information_ratio_annualized": always_summary["information_ratio_annualized"],
        "avg_cash_weight": always_summary["avg_cash_weight"],
        "latest_held_tickers": always_summary["latest_day"].get("held_tickers", []),
    }]).to_string(index=False))


if __name__ == "__main__":
    main()
