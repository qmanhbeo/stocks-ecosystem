"""
H178: Robustness stress for the H175 rel2_gt0 activation champion.

Purpose:
- test whether the new champion survives alternate start years
- test fee sensitivity without reopening the activation family
- inspect benchmark-relative subperiod stability
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

from src.activation_alpha import load_activation_experiment_inputs
from src.activation_meta import load_or_build_activation_meta
from src.activation_meta_experiment_utils import (
    ACTIVATION_META_PATH,
    ACTIVATION_STATE_PATH,
    BENCHMARK_PATH,
    RL_MATRIX_PATH,
    STOCK_DIR,
    TRADABILITY_PATH,
    selector_recent_relative_ewm_from_prev,
    subperiod_relative_return,
)
from src.deterministic_portfolio import StrategyRunResult, simulate_strategy
from src.run_summary import write_run_summary
from shared_market_rules import required_holding_age_for_sell

OUT_DIR = ROOT / "artifacts/portfolio_baselines"
META_OUT_DIR = ROOT / "artifacts/activation_meta"


def _parse_int_list(text: str) -> list[int]:
    values = [int(part.strip()) for part in str(text).split(",") if part.strip()]
    if not values:
        raise ValueError("Expected at least one integer value")
    return values


def _parse_float_list(text: str) -> list[float]:
    values = [float(part.strip()) for part in str(text).split(",") if part.strip()]
    if not values:
        raise ValueError("Expected at least one float value")
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, default=str(RL_MATRIX_PATH))
    parser.add_argument("--tradability", type=str, default=str(TRADABILITY_PATH))
    parser.add_argument("--stock-dir", type=str, default=str(STOCK_DIR))
    parser.add_argument("--benchmark", type=str, default=str(BENCHMARK_PATH))
    parser.add_argument("--activation-state", type=str, default=str(ACTIVATION_STATE_PATH))
    parser.add_argument("--activation-meta", type=str, default=str(ACTIVATION_META_PATH))
    parser.add_argument("--start-years", type=str, default="2016,2017,2018,2019")
    parser.add_argument("--meta-start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--round-trip-costs", type=str, default="0.001,0.003,0.005,0.007")
    parser.add_argument("--required-holding-age", type=int, default=3)
    parser.add_argument("--initial-notional-vnd", type=float, default=100_000_000.0)
    return parser.parse_args()


def _align_gate(meta_state: pd.DataFrame, *, dates: pd.Series) -> np.ndarray:
    series = selector_recent_relative_ewm_from_prev(meta_state, prefix="full", span=2) > 0.0
    aligned = (
        pd.DataFrame({"time": pd.to_datetime(meta_state["time"]), "gate": series.astype(float)})
        .drop_duplicates("time")
        .set_index("time")["gate"]
        .reindex(pd.to_datetime(dates))
        .fillna(0.0)
    )
    return aligned.to_numpy(dtype=np.float64)


def _run_selector(
    *,
    inputs,
    gate_scale: np.ndarray | None,
    round_trip_cost: float,
    initial_notional_vnd: float,
    required_holding_age: int,
) -> StrategyRunResult:
    selector = next(selector for selector in inputs.selectors if selector.name == "full_library_k5_r5_eq")
    hold_age = required_holding_age_for_sell(min_hold_days_override=int(required_holding_age))
    fee_leg = float(round_trip_cost) / 2.0
    return simulate_strategy(
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
        activation_scale=gate_scale,
    )


def _safe_subperiod(daily: pd.DataFrame, *, start_year: int, end_year: int) -> float | None:
    years = pd.to_datetime(daily["execution_date"]).dt.year
    if not bool(((years >= int(start_year)) & (years <= int(end_year))).any()):
        return None
    value = subperiod_relative_return(daily, start_year=int(start_year), end_year=int(end_year))
    if not np.isfinite(value):
        return None
    return float(value)


def main() -> None:
    args = parse_args()
    start_years = sorted(set(_parse_int_list(args.start_years)))
    costs = _parse_float_list(args.round_trip_costs)
    end_year = int(args.end_year)

    rows: list[dict[str, object]] = []
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    META_OUT_DIR.mkdir(parents=True, exist_ok=True)

    for cost in costs:
        meta_out = META_OUT_DIR / (
            f"h178_activation_meta_meta_start_{int(args.meta_start_year)}_fee_{str(cost).replace('.', 'p')}.parquet"
        )
        meta_state, meta_source = load_or_build_activation_meta(
            out_path=meta_out,
            matrix_path=Path(args.matrix),
            tradability_path=Path(args.tradability),
            stock_dir=Path(args.stock_dir),
            benchmark_path=Path(args.benchmark),
            activation_state_path=Path(args.activation_state),
            start_year=int(args.meta_start_year),
            end_year=end_year,
            round_trip_cost=float(cost),
            required_holding_age=int(args.required_holding_age),
            initial_notional_vnd=float(args.initial_notional_vnd),
        )
        for start_year in start_years:
            inputs = load_activation_experiment_inputs(
                matrix_path=Path(args.matrix),
                tradability_path=Path(args.tradability),
                stock_dir=Path(args.stock_dir),
                benchmark_path=Path(args.benchmark),
                start_year=int(start_year),
                end_year=end_year,
            )
            dates = pd.Series(pd.to_datetime(inputs.market_inputs.dates))
            gate_scale = _align_gate(meta_state, dates=dates)

            always_on = _run_selector(
                inputs=inputs,
                gate_scale=None,
                round_trip_cost=float(cost),
                initial_notional_vnd=float(args.initial_notional_vnd),
                required_holding_age=int(args.required_holding_age),
            )
            gated = _run_selector(
                inputs=inputs,
                gate_scale=gate_scale,
                round_trip_cost=float(cost),
                initial_notional_vnd=float(args.initial_notional_vnd),
                required_holding_age=int(args.required_holding_age),
            )

            scenario = {
                "start_year": int(start_year),
                "end_year": int(end_year),
                "round_trip_cost": float(cost),
                "meta_source": str(meta_source),
                "always_relative_total_return": float(always_on.summary["relative_total_return"]),
                "always_information_ratio": float(always_on.summary["information_ratio_annualized"] or 0.0),
                "always_max_drawdown": float(always_on.summary["max_drawdown"]),
                "gate_relative_total_return": float(gated.summary["relative_total_return"]),
                "gate_information_ratio": float(gated.summary["information_ratio_annualized"] or 0.0),
                "gate_max_drawdown": float(gated.summary["max_drawdown"]),
                "gate_portfolio_total_return": float(gated.summary["portfolio_total_return"]),
                "gate_portfolio_annualized_return": gated.summary.get("portfolio_annualized_return"),
                "gate_avg_cash_weight": float(gated.summary["avg_cash_weight"]),
                "delta_relative_total_return_vs_always_on": float(gated.summary["relative_total_return"])
                - float(always_on.summary["relative_total_return"]),
                "delta_information_ratio_vs_always_on": float(gated.summary["information_ratio_annualized"] or 0.0)
                - float(always_on.summary["information_ratio_annualized"] or 0.0),
                "subperiod_rel_2019_2021": _safe_subperiod(gated.daily, start_year=2019, end_year=2021),
                "subperiod_rel_2022_2023": _safe_subperiod(gated.daily, start_year=2022, end_year=2023),
                "subperiod_rel_2024_2025": _safe_subperiod(gated.daily, start_year=2024, end_year=2025),
            }
            subperiod_values = [
                value
                for value in [
                    scenario["subperiod_rel_2019_2021"],
                    scenario["subperiod_rel_2022_2023"],
                    scenario["subperiod_rel_2024_2025"],
                ]
                if value is not None and np.isfinite(value)
            ]
            scenario["worst_available_subperiod_relative_return"] = (
                float(min(subperiod_values)) if subperiod_values else None
            )
            rows.append(scenario)

    results = pd.DataFrame(rows).sort_values(
        by=[
            "delta_relative_total_return_vs_always_on",
            "delta_information_ratio_vs_always_on",
            "gate_relative_total_return",
            "start_year",
            "round_trip_cost",
        ],
        ascending=[False, False, False, True, True],
        ignore_index=True,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUT_DIR / f"{ts}_h178_h175_robustness_stress_results.parquet"
    results.to_parquet(results_path, index=False)

    beat_rel = int((results["delta_relative_total_return_vs_always_on"] > 0.0).sum())
    beat_ir = int((results["delta_information_ratio_vs_always_on"] > 0.0).sum())
    summary = {
        "scenario_count": int(len(results)),
        "beat_relative_count": beat_rel,
        "beat_relative_rate": round(float(beat_rel / max(len(results), 1)), 6),
        "beat_ir_count": beat_ir,
        "beat_ir_rate": round(float(beat_ir / max(len(results), 1)), 6),
        "best_scenario": results.iloc[0].to_dict() if not results.empty else {},
        "worst_scenario": results.iloc[-1].to_dict() if not results.empty else {},
    }
    write_run_summary(
        ts=ts,
        mode="portfolio_activation_h175_robustness_stress",
        name="h178_h175_robustness_stress",
        summary=summary,
        artifacts={"results": str(results_path)},
        metadata={
            "matrix": str(args.matrix),
            "activation_meta": str(args.activation_meta),
            "activation_state": str(args.activation_state),
            "benchmark": str(args.benchmark),
            "start_years": [int(value) for value in start_years],
            "meta_start_year": int(args.meta_start_year),
            "end_year": int(end_year),
            "round_trip_costs": [float(value) for value in costs],
        },
    )

    print("\nH178: H175 ROBUSTNESS STRESS")
    print(results.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
