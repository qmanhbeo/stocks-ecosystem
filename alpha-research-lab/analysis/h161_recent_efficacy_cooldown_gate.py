"""
H161: Recent efficacy / cooldown gate.

Purpose:
- activate the selector only when its own recent completed cycles have been working
- test whether selection alpha has short-memory efficacy that can be exploited without RL

Usage:
    conda run -n stocks python analysis/h161_recent_efficacy_cooldown_gate.py
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

from src.activation_alpha import (
    BENCHMARK_PATH,
    RL_MATRIX_PATH,
    STOCK_DIR,
    TRADABILITY_PATH,
    load_activation_experiment_inputs,
    run_activation_scenarios,
)
from src.activation_experiment_utils import print_top_activation_results, persist_activation_outputs
from src.deterministic_portfolio import simulate_strategy
from src.run_summary import write_run_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--top-results", type=int, default=20)
    return parser.parse_args()


def _gross_return(window: pd.Series) -> float:
    arr = pd.to_numeric(window, errors="coerce").to_numpy(dtype=np.float64)
    if arr.size == 0:
        return np.nan
    return float(np.prod(1.0 + arr) - 1.0)


def _selector_recent_gates(daily: pd.DataFrame, *, rebalance_every: int) -> dict[str, pd.Series]:
    work = daily[["signal_date", "portfolio_return"]].copy()
    work["signal_date"] = pd.to_datetime(work["signal_date"])
    work = work.sort_values("signal_date").drop_duplicates("signal_date")
    work["prev_cycle_ret"] = work["portfolio_return"].rolling(rebalance_every, min_periods=rebalance_every).apply(_gross_return, raw=False).shift(1)
    work["prev_two_cycle_ret"] = work["portfolio_return"].rolling(rebalance_every * 2, min_periods=rebalance_every * 2).apply(_gross_return, raw=False).shift(1)
    work["loss_flag"] = (pd.to_numeric(work["prev_cycle_ret"], errors="coerce") <= 0.0).astype(float)
    work["two_loss_streak"] = work["loss_flag"].rolling(2, min_periods=2).sum().shift(1)
    return {
        "recent__prev_cycle_pos": work["prev_cycle_ret"] > 0.0,
        "recent__prev_cycle_gt_m02": work["prev_cycle_ret"] > -0.02,
        "recent__prev_cycle_gt_m05": work["prev_cycle_ret"] > -0.05,
        "recent__prev_two_cycle_pos": work["prev_two_cycle_ret"] > 0.0,
        "recent__no_two_loss_streak": work["two_loss_streak"] < 2.0,
        "recent__combo_prev_pos_no_streak": (work["prev_cycle_ret"] > 0.0) & (work["two_loss_streak"] < 2.0),
    }


def main() -> None:
    args = parse_args()
    inputs = load_activation_experiment_inputs(
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
    )
    fee_leg = float(args.round_trip_cost) / 2.0
    hold_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))

    gates_by_selector: dict[str, dict[str, pd.Series]] = {}
    baseline_rows: list[dict[str, object]] = []
    for selector in inputs.selectors:
        always_on = simulate_strategy(
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
        )
        selector_gates = _selector_recent_gates(always_on.daily, rebalance_every=int(selector.rebalance_every))
        aligned: dict[str, pd.Series] = {}
        for gate_name, series in selector_gates.items():
            gate_frame = pd.DataFrame({"time": pd.to_datetime(always_on.daily["signal_date"]), "gate": series.values})
            gate_frame = gate_frame.drop_duplicates("time")
            aligned_series = gate_frame.set_index("time")["gate"].reindex(pd.to_datetime(inputs.market_inputs.dates))
            aligned[gate_name] = aligned_series.where(pd.notna(aligned_series), False).astype(bool)
        gates_by_selector[selector.name] = aligned
        baseline_rows.append(
            {
                "selector_name": selector.name,
                "portfolio_total_return": always_on.summary["portfolio_total_return"],
                "relative_total_return": always_on.summary["relative_total_return"],
            }
        )

    results, daily_outputs = run_activation_scenarios(
        activation_state=pd.DataFrame({"time": pd.to_datetime(inputs.market_inputs.dates)}),
        market_inputs=inputs.market_inputs,
        selectors=inputs.selectors,
        gates_by_selector=gates_by_selector,
        initial_notional_vnd=float(args.initial_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
    )

    print_top_activation_results(results, title="H161: RECENT EFFICACY / COOLDOWN GATES", top_n=int(args.top_results))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    results_path, best_daily_path = persist_activation_outputs(
        ts=ts,
        stem="h161_recent_efficacy_cooldown_gate",
        results=results,
        daily_outputs=daily_outputs,
    )
    best_non_baseline = results.loc[results["gate_name"] != "always_on"].head(1)
    summary = {
        "best_overall": best_non_baseline.iloc[0].to_dict() if not best_non_baseline.empty else {},
        "selector_baselines": baseline_rows,
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_activation_recent_efficacy",
        name="h161_recent_efficacy_cooldown_gate",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path) if best_daily_path is not None else None,
        },
        metadata={
            "matrix": str(args.matrix),
            "benchmark": str(args.benchmark),
        },
    )


if __name__ == "__main__":
    main()
