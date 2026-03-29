"""
H159: Market regime gate.

Purpose:
- activate the selector only in favorable benchmark / macro states
- test whether the current edge needs a broad-market risk-on regime to monetize cleanly

Usage:
    conda run -n stocks python analysis/h159_market_regime_gate.py
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.activation_alpha import (
    ACTIVATION_STATE_PATH,
    BENCHMARK_PATH,
    RL_MATRIX_PATH,
    STOCK_DIR,
    TRADABILITY_PATH,
    align_activation_mask,
    build_quantile_gate,
    build_threshold_gate,
    load_activation_experiment_inputs,
    load_or_build_activation_state,
    run_activation_scenarios,
)
from src.activation_experiment_utils import print_top_activation_results, persist_activation_outputs
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

    low_vol_q60 = build_quantile_gate(activation_state["vni_realized_vol_20d"], quantile=0.60, operator="<=")
    gate_defs = {
        "mkt__above_ma20": activation_state["vni_above_ma20"] >= 1.0,
        "mkt__above_ma50": activation_state["vni_above_ma50"] >= 1.0,
        "mkt__above_ma20_ma50": (activation_state["vni_above_ma20"] >= 1.0) & (activation_state["vni_above_ma50"] >= 1.0),
        "mkt__drawdown_gt_m10": build_threshold_gate(activation_state["vni_drawdown_60d"], threshold=-0.10),
        "mkt__drawdown_gt_m05": build_threshold_gate(activation_state["vni_drawdown_60d"], threshold=-0.05),
        "mkt__low_vol_q60": low_vol_q60,
        "mkt__above_ma20_low_vol": (activation_state["vni_above_ma20"] >= 1.0) & low_vol_q60,
        "mkt__breadth_score_ge4": build_threshold_gate(activation_state["breadth_score"], threshold=4.0),
        "mkt__credit_risk_on_ge2": build_threshold_gate(activation_state["credit_risk_on"], threshold=2.0),
        "mkt__risk_on_combo": (
            (activation_state["vni_above_ma20"] >= 1.0)
            & build_threshold_gate(activation_state["breadth_score"], threshold=4.0)
            & low_vol_q60
        ),
    }
    gates = {
        name: align_activation_mask(
            activation_state.assign(_gate=pd.Series(series.values, index=activation_state.index)),
            dates=pd.to_datetime(inputs.market_inputs.dates),
            value_column="_gate",
        )
        for name, series in gate_defs.items()
    }

    results, daily_outputs = run_activation_scenarios(
        activation_state=activation_state,
        market_inputs=inputs.market_inputs,
        selectors=inputs.selectors,
        gates=gates,
        initial_notional_vnd=float(args.initial_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
    )

    print_top_activation_results(results, title="H159: MARKET REGIME GATES", top_n=int(args.top_results))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    results_path, best_daily_path = persist_activation_outputs(
        ts=ts,
        stem="h159_market_regime_gate",
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
        mode="portfolio_activation_market_regime",
        name="h159_market_regime_gate",
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
