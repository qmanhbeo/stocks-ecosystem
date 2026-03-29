"""
H162: Composite activation score.

Purpose:
- combine the strongest deterministic activation ingredients into a compact activation score
- test whether a small interpretable composite is better than single-gate activation rules

Usage:
    conda run -n stocks python analysis/h162_composite_activation_score.py
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
    ACTIVATION_STATE_PATH,
    BENCHMARK_PATH,
    RL_MATRIX_PATH,
    STOCK_DIR,
    TRADABILITY_PATH,
    build_quantile_gate,
    load_activation_experiment_inputs,
    load_or_build_activation_state,
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
    parser.add_argument("--activation-state", type=str, default=str(ACTIVATION_STATE_PATH))
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--round-trip-cost", type=float, default=0.003)
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    parser.add_argument("--top-results", type=int, default=20)
    return parser.parse_args()


def _pct_rank(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.rank(method="average", pct=True).fillna(0.5).astype(float)


def _gross_return(window: pd.Series) -> float:
    arr = pd.to_numeric(window, errors="coerce").to_numpy(dtype=np.float64)
    if arr.size == 0:
        return np.nan
    return float(np.prod(1.0 + arr) - 1.0)


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
    activation_state, activation_source = load_or_build_activation_state(
        out_path=Path(args.activation_state),
        matrix_path=Path(args.matrix),
        tradability_path=Path(args.tradability),
        stock_dir=Path(args.stock_dir),
        benchmark_path=Path(args.benchmark),
        start_year=2015,
        end_year=int(args.end_year),
    )
    activation_state = activation_state[
        (activation_state["time"].dt.year >= int(args.start_year))
        & (activation_state["time"].dt.year <= int(args.end_year))
    ].copy()

    common = activation_state[["time"]].copy()
    common["opp_component"] = (
        _pct_rank(activation_state["full_top1_minus_top5_spread"])
        + _pct_rank(activation_state["full_top5_mean_score"])
        + _pct_rank(activation_state["full_top5_score_std"])
        + _pct_rank(activation_state["selector_top5_overlap"])
    ) / 4.0
    common["trad_component"] = (
        activation_state["full_top10_buyable_count"].clip(lower=0.0, upper=10.0) / 10.0
        + activation_state["full_top10_liq_open_count"].clip(lower=0.0, upper=10.0) / 10.0
        + (1.0 - activation_state["full_top5_blocked_buy_count"].clip(lower=0.0, upper=5.0) / 5.0)
        + activation_state["liq_open_breadth_all"].clip(lower=0.0, upper=1.0)
    ) / 4.0
    common["market_component"] = (
        activation_state["vni_above_ma20"].clip(lower=0.0, upper=1.0)
        + activation_state["vni_above_ma50"].clip(lower=0.0, upper=1.0)
        + (1.0 - _pct_rank(activation_state["vni_realized_vol_20d"]))
        + _pct_rank(activation_state["vni_drawdown_60d"])
    ) / 4.0
    common["structure_component"] = (
        _pct_rank(activation_state["xs_dispersion_z20"])
        + activation_state["xs_breadth_up_5d"].clip(lower=0.0, upper=1.0)
        + activation_state["xs_breadth_up_20d"].clip(lower=0.0, upper=1.0)
    ) / 3.0

    fee_leg = float(args.round_trip_cost) / 2.0
    hold_age = required_holding_age_for_sell(min_hold_days_override=int(args.required_holding_age))
    gates_by_selector: dict[str, dict[str, pd.Series]] = {}
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
        recent = always_on.daily[["signal_date", "portfolio_return"]].copy()
        recent["time"] = pd.to_datetime(recent["signal_date"])
        recent = recent.sort_values("time").drop_duplicates("time")
        recent["prev_cycle_ret"] = recent["portfolio_return"].rolling(selector.rebalance_every, min_periods=selector.rebalance_every).apply(_gross_return, raw=False).shift(1)
        recent["recent_component"] = _pct_rank(recent["prev_cycle_ret"])
        selector_frame = common.merge(recent[["time", "recent_component"]], on="time", how="left")
        selector_frame["recent_component"] = selector_frame["recent_component"].fillna(0.5)
        selector_frame["composite_activation_score"] = (
            selector_frame["opp_component"]
            + selector_frame["trad_component"]
            + selector_frame["market_component"]
            + selector_frame["structure_component"]
            + selector_frame["recent_component"]
        ) / 5.0
        gates_by_selector[selector.name] = {
            "comp__score_q55": build_quantile_gate(selector_frame["composite_activation_score"], quantile=0.55),
            "comp__score_q60": build_quantile_gate(selector_frame["composite_activation_score"], quantile=0.60),
            "comp__score_q65": build_quantile_gate(selector_frame["composite_activation_score"], quantile=0.65),
            "comp__score_q70": build_quantile_gate(selector_frame["composite_activation_score"], quantile=0.70),
            "comp__score_q60_recent_q60": (
                build_quantile_gate(selector_frame["composite_activation_score"], quantile=0.60)
                & build_quantile_gate(selector_frame["recent_component"], quantile=0.60)
            ),
        }
        gates_by_selector[selector.name] = {
            gate_name: selector_frame[["time"]].assign(gate=series.values).set_index("time")["gate"]
            .reindex(pd.to_datetime(inputs.market_inputs.dates)).where(lambda s: pd.notna(s), False).astype(bool)
            for gate_name, series in gates_by_selector[selector.name].items()
        }

    results, daily_outputs = run_activation_scenarios(
        activation_state=activation_state,
        market_inputs=inputs.market_inputs,
        selectors=inputs.selectors,
        gates_by_selector=gates_by_selector,
        initial_notional_vnd=float(args.initial_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
    )

    print_top_activation_results(results, title="H162: COMPOSITE ACTIVATION SCORE", top_n=int(args.top_results))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    results_path, best_daily_path = persist_activation_outputs(
        ts=ts,
        stem="h162_composite_activation_score",
        results=results,
        daily_outputs=daily_outputs,
    )
    best_non_baseline = results.loc[results["gate_name"] != "always_on"].head(1)
    summary = {
        "activation_source": activation_source,
        "best_overall": best_non_baseline.iloc[0].to_dict() if not best_non_baseline.empty else {},
        "selector_baselines": {
            selector: results.loc[(results["selector_name"] == selector) & (results["gate_name"] == "always_on")]
            .head(1)
            .to_dict(orient="records")
            for selector in results["selector_name"].drop_duplicates().tolist()
        },
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_activation_composite",
        name="h162_composite_activation_score",
        summary=summary,
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path) if best_daily_path is not None else None,
        },
        metadata={
            "matrix": str(args.matrix),
            "activation_state": str(args.activation_state),
            "activation_source": activation_source,
            "benchmark": str(args.benchmark),
        },
    )


if __name__ == "__main__":
    main()
