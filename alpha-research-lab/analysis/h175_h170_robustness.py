"""
H175: Robustify H170 smoothed recent efficacy.

Purpose:
- sweep threshold/window variants around H170
- add a selector-specific yearly walk-forward calibration path over the candidate family
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

from src.activation_alpha import run_activation_scenarios
from src.activation_experiment_utils import persist_activation_outputs, print_top_activation_results
from src.activation_meta_experiment_utils import (
    add_common_args,
    load_meta_bundle,
    quantile_gate,
    selector_baseline_rows,
    selector_prefix,
    subperiod_relative_return,
)
from src.run_summary import write_run_summary

OUT_DIR = Path("artifacts/portfolio_baselines")


def parse_args() -> argparse.Namespace:
    parser = add_common_args(argparse.ArgumentParser())
    parser.add_argument("--min-train-years", type=int, default=2)
    return parser.parse_args()


def _ewm_from_prev(meta_state: pd.DataFrame, *, prefix: str, span: int) -> pd.Series:
    prev = pd.to_numeric(meta_state[f"{prefix}_prev_cycle_relative_return"], errors="coerce")
    return prev.ewm(span=int(span), adjust=False, min_periods=1).mean()


def _selector_candidate_gates(meta_state: pd.DataFrame, *, prefix: str) -> dict[str, pd.Series]:
    rel2 = _ewm_from_prev(meta_state, prefix=prefix, span=2)
    rel3 = pd.to_numeric(meta_state[f"{prefix}_recent_cycle_relative_return_ewm3"], errors="coerce")
    rel4 = _ewm_from_prev(meta_state, prefix=prefix, span=4)
    rel5 = pd.to_numeric(meta_state[f"{prefix}_recent_cycle_relative_return_ewm5"], errors="coerce")
    hit3 = pd.to_numeric(meta_state[f"{prefix}_recent_hit_rate_ewm3"], errors="coerce")
    hit5 = pd.to_numeric(meta_state[f"{prefix}_recent_hit_rate_ewm5"], errors="coerce")
    return {
        "h175__rel2_gt0": rel2 > 0.0,
        "h175__rel3_gt0": rel3 > 0.0,
        "h175__rel4_gt0": rel4 > 0.0,
        "h175__rel5_gt0": rel5 > 0.0,
        "h175__rel3_gt_m005": rel3 > -0.005,
        "h175__rel3_gt_p005": rel3 > 0.005,
        "h175__hit3_ge55": hit3 >= 0.55,
        "h175__hit5_ge55": hit5 >= 0.55,
        "h175__hit5_ge60": hit5 >= 0.60,
        "h175__rel3_gt0_hit5_ge55": (rel3 > 0.0) & (hit5 >= 0.55),
        "h175__rel3_q60_hit5_ge55": quantile_gate(rel3, 0.60) & (hit5 >= 0.55),
    }


def _walk_forward_gate_from_candidates(
    *,
    meta_state: pd.DataFrame,
    candidate_gates: dict[str, pd.Series],
    selector_daily_outputs: dict[str, pd.DataFrame],
    min_train_years: int,
) -> tuple[pd.Series, pd.DataFrame]:
    years = sorted(meta_state["time"].dt.year.drop_duplicates().tolist())
    schedule = pd.Series(True, index=meta_state.index, dtype=bool)
    selected_rows: list[dict[str, object]] = []
    for pos, year in enumerate(years):
        year_mask = meta_state["time"].dt.year == int(year)
        if pos < int(min_train_years):
            selected_rows.append(
                {
                    "test_year": int(year),
                    "selected_gate": "always_on_warmup",
                    "train_start_year": years[0],
                    "train_end_year": int(year) - 1,
                    "train_relative_total_return": None,
                }
            )
            schedule.loc[year_mask] = True
            continue

        train_start = years[0]
        train_end = years[pos - 1]
        best_gate = "always_on_warmup"
        best_score = float("-inf")
        for gate_name, daily in selector_daily_outputs.items():
            score = subperiod_relative_return(daily, start_year=int(train_start), end_year=int(train_end))
            if score > best_score:
                best_score = score
                best_gate = gate_name
        if best_gate in candidate_gates:
            schedule.loc[year_mask] = candidate_gates[best_gate].loc[year_mask].astype(bool)
        else:
            schedule.loc[year_mask] = True
        selected_rows.append(
            {
                "test_year": int(year),
                "selected_gate": str(best_gate),
                "train_start_year": int(train_start),
                "train_end_year": int(train_end),
                "train_relative_total_return": None if not np.isfinite(best_score) else float(best_score),
            }
        )
    return schedule.astype(bool), pd.DataFrame(selected_rows)


def main() -> None:
    args = parse_args()
    inputs, meta_state, meta_source = load_meta_bundle(args)

    candidate_gates_by_selector: dict[str, dict[str, pd.Series]] = {}
    for selector in inputs.selectors:
        prefix = selector_prefix(selector)
        candidate_gates_by_selector[selector.name] = _selector_candidate_gates(meta_state, prefix=prefix)

    candidate_results, candidate_daily_outputs = run_activation_scenarios(
        activation_state=meta_state,
        market_inputs=inputs.market_inputs,
        selectors=inputs.selectors,
        gates_by_selector=candidate_gates_by_selector,
        initial_notional_vnd=float(args.initial_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
    )

    final_gates_by_selector: dict[str, dict[str, pd.Series]] = {}
    selected_parts: list[pd.DataFrame] = []
    for selector in inputs.selectors:
        selector_candidates = candidate_gates_by_selector[selector.name]
        selector_outputs = {
            gate_name: candidate_daily_outputs[(selector.name, gate_name)]
            for gate_name in selector_candidates
        }
        wf_gate, selected = _walk_forward_gate_from_candidates(
            meta_state=meta_state,
            candidate_gates=selector_candidates,
            selector_daily_outputs=selector_outputs,
            min_train_years=int(args.min_train_years),
        )
        selected.insert(0, "selector_name", selector.name)
        selected_parts.append(selected)
        selector_candidates = dict(selector_candidates)
        selector_candidates["h175__wf_best_train_rel"] = wf_gate
        final_gates_by_selector[selector.name] = selector_candidates

    results, daily_outputs = run_activation_scenarios(
        activation_state=meta_state,
        market_inputs=inputs.market_inputs,
        selectors=inputs.selectors,
        gates_by_selector=final_gates_by_selector,
        initial_notional_vnd=float(args.initial_notional_vnd),
        round_trip_cost=float(args.round_trip_cost),
        required_holding_age=int(args.required_holding_age),
    )

    print_top_activation_results(results, title="H175: H170 ROBUSTNESS", top_n=int(args.top_results))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    results_path, best_daily_path = persist_activation_outputs(
        ts=ts,
        stem="h175_h170_robustness",
        results=results,
        daily_outputs=daily_outputs,
    )
    selected_df = pd.concat(selected_parts, ignore_index=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    selected_path = OUT_DIR / f"{ts}_h175_h170_robustness_selected_rules.parquet"
    selected_df.to_parquet(selected_path, index=False)
    best_non_baseline = results.loc[results["gate_name"] != "always_on"].head(1)
    write_run_summary(
        ts=ts,
        mode="portfolio_activation_h170_robustness",
        name="h175_h170_robustness",
        summary={
            "meta_source": meta_source,
            "best_overall": best_non_baseline.iloc[0].to_dict() if not best_non_baseline.empty else {},
            "selector_baselines": selector_baseline_rows(results),
            "walk_forward_selection": selected_df.to_dict(orient="records"),
        },
        artifacts={
            "results": str(results_path),
            "best_daily": str(best_daily_path) if best_daily_path is not None else None,
            "selected_rules": str(selected_path),
        },
        metadata={
            "matrix": str(args.matrix),
            "activation_meta": str(args.activation_meta),
            "benchmark": str(args.benchmark),
            "meta_source": meta_source,
            "min_train_years": int(args.min_train_years),
        },
    )


if __name__ == "__main__":
    main()
