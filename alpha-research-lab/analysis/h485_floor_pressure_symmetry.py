"""
H485 / BG: floor_pressure_symmetry

Hypothesis: C24 tests CEILING (+7%), never tested FLOOR (-7%).
Multi-day floor pressure = forced sell capitulation = reversal opportunity OR more pain.

Test:
- floor_count_3d: how many times in last 3 days stock hit -7% floor
- Compare floor vs ceiling symmetry: does floor pressure work the same as ceiling?
- floor_count × vol_expansion vs ceiling_count × vol_expansion analog

Decision rule:
- PASSED: floor_count >= 2 has IC > 0.15 AND lift > +0.02 vs baseline
- MIXED: floor_count >= 2 has IC > baseline but lift < +0.02
- FAILED: floor_count >= 2 IC <= baseline
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (
    S1_DEFAULT_PATH,
    S1_SCORE_COL,
    S1_TARGET_COL,
    ExperimentSpec,
    StateSpec,
    build_experiment_context,
    evaluate_state_specs,
    load_s1_decision_panel,
    validate_state_columns,
    write_dataframe_artifact,
)
from src.repo_paths import data_path


BRANCH_NAME = "floor_pressure_symmetry"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "C24 tests CEILING (+7%), never tested FLOOR (-7%). "
        "Test floor_count >= 2 × vol_expansion vs C24 ceiling analog. "
        "Mechanism: capitulation at daily floor."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H485 floor_pressure_symmetry")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    order_stats = pd.read_parquet(args.order_stats_path)
    order_stats = order_stats.rename(columns={"date": "time"})
    order_stats["time"] = pd.to_datetime(order_stats["time"])
    order_stats = order_stats[order_stats["time"].dt.year <= 2025]

    import re
    def parse_price_change(s):
        if pd.isna(s):
            return np.nan
        try:
            match = re.search(r'\(\s*([+-]?[\d,]+)\s*%\)', str(s))
            if match:
                return float(match.group(1).replace(',', '.'))
            return np.nan
        except:
            return np.nan

    order_stats["pct_change"] = order_stats["price_change_raw"].apply(parse_price_change)

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change"]],
        on=["time", "ticker"],
        how="left",
    )

    panel = panel.sort_values(["ticker", "time"])

    panel["at_ceiling"] = (panel["pct_change"] >= 6.5).astype(bool)
    panel["at_floor"] = (panel["pct_change"] <= -6.5).astype(bool)
    panel["near_floor"] = ((panel["pct_change"] > -7.0) & (panel["pct_change"] <= -5.0)).astype(bool)
    panel["mid_range"] = ~panel["at_ceiling"] & ~panel["at_floor"]

    for w in [3, 5]:
        panel[f"ceiling_count_{w}d"] = panel.groupby("ticker")["at_ceiling"].transform(
            lambda x: x.rolling(window=w, min_periods=2).sum()
        )
        panel[f"floor_count_{w}d"] = panel.groupby("ticker")["at_floor"].transform(
            lambda x: x.rolling(window=w, min_periods=2).sum()
        )

    panel["ceiling_1_of_3"] = (panel["ceiling_count_3d"] == 1).astype(bool)
    panel["ceiling_2_of_3"] = (panel["ceiling_count_3d"] >= 2).astype(bool)
    panel["floor_1_of_3"] = (panel["floor_count_3d"] == 1).astype(bool)
    panel["floor_2_of_3"] = (panel["floor_count_3d"] >= 2).astype(bool)

    pct_change_vol = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    vol_change = pct_change_vol.diff()
    panel["vol_change"] = vol_change
    panel = panel.dropna(subset=["vol_change"])

    vol_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = (vol_rank >= 0.8).astype(bool)

    panel["ceiling_2_expansion"] = (panel["ceiling_2_of_3"] & panel["vol_expansion"]).astype(bool)
    panel["floor_2_expansion"] = (panel["floor_2_of_3"] & panel["vol_expansion"]).astype(bool)
    panel["near_floor_expansion"] = (panel["near_floor"] & panel["vol_expansion"]).astype(bool)

    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("at_ceiling", "At ceiling (+6.5%+ change)", family="ceiling"),
    StateSpec("at_floor", "At floor (-6.5%- change)", family="floor"),
    StateSpec("near_floor", "Near floor (-5% to -7%)", family="floor"),
    StateSpec("ceiling_1_of_3", "Hit ceiling 1x in last 3 days", family="ceiling_count"),
    StateSpec("ceiling_2_of_3", "Hit ceiling 2+ times in last 3 days (C24)", family="ceiling_count", primary=True),
    StateSpec("floor_1_of_3", "Hit floor 1x in last 3 days", family="floor_count"),
    StateSpec("floor_2_of_3", "Hit floor 2+ times in last 3 days", family="floor_count"),
    StateSpec("ceiling_2_expansion", "Ceiling 2+ × Vol expansion (C24 analog)", family="combo", primary=True),
    StateSpec("floor_2_expansion", "Floor 2+ × Vol expansion", family="combo"),
    StateSpec("near_floor_expansion", "Near floor × Vol expansion", family="combo"),
]


def run_branch(args: argparse.Namespace) -> str:
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(args.min_year_rows),
        min_phase_rows=int(args.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    panel = load_panel(args, spec)

    validate_state_columns(panel, [state.name for state in STATE_SPECS], spec)

    results, yearly = evaluate_state_specs(
        panel,
        STATE_SPECS,
        score_col=S1_SCORE_COL,
        target_col=S1_TARGET_COL,
        spec=spec,
    )

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if not results.empty else 0

    ceiling_2_ic = results[results["name"] == "ceiling_2_of_3"]["avg_ic"].iloc[0] if not results.empty else 0
    floor_2_ic = results[results["name"] == "floor_2_of_3"]["avg_ic"].iloc[0] if not results.empty else 0
    ceiling_2_exp_ic = results[results["name"] == "ceiling_2_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    floor_2_exp_ic = results[results["name"] == "floor_2_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    near_floor_ic = results[results["name"] == "near_floor"]["avg_ic"].iloc[0] if not results.empty else 0
    near_floor_exp_ic = results[results["name"] == "near_floor_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    at_floor_ic = results[results["name"] == "at_floor"]["avg_ic"].iloc[0] if not results.empty else 0
    at_ceiling_ic = results[results["name"] == "at_ceiling"]["avg_ic"].iloc[0] if not results.empty else 0
    floor_1_ic = results[results["name"] == "floor_1_of_3"]["avg_ic"].iloc[0] if not results.empty else 0
    ceiling_1_ic = results[results["name"] == "ceiling_1_of_3"]["avg_ic"].iloc[0] if not results.empty else 0

    best = results[results["name"] != "all_rows"].sort_values("avg_ic", ascending=False).iloc[0] if not results.empty else {}
    best_name = best.get("name", "none")
    best_ic = best.get("avg_ic", 0)
    best_lift = best_ic - baseline_ic

    floor_2_lift = floor_2_ic - baseline_ic
    floor_2_exp_lift = floor_2_exp_ic - baseline_ic
    ceiling_2_lift = ceiling_2_ic - baseline_ic

    decision = "FAILED"
    if floor_2_exp_lift > 0.020 and floor_2_exp_ic > 0.15:
        decision = "PASSED"
    elif floor_2_exp_lift > 0 or floor_2_lift > 0:
        decision = "MIXED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "at_ceiling_ic": float(at_ceiling_ic),
            "at_floor_ic": float(at_floor_ic),
            "ceiling_1_of_3_ic": float(ceiling_1_ic),
            "ceiling_2_of_3_ic": float(ceiling_2_ic),
            "floor_1_of_3_ic": float(floor_1_ic),
            "floor_2_of_3_ic": float(floor_2_ic),
            "ceiling_2_expansion_ic": float(ceiling_2_exp_ic),
            "floor_2_expansion_ic": float(floor_2_exp_ic),
            "near_floor_ic": float(near_floor_ic),
            "near_floor_expansion_ic": float(near_floor_exp_ic),
            "floor_2_lift": float(floor_2_lift),
            "floor_2_exp_lift": float(floor_2_exp_lift),
            "ceiling_2_lift": float(ceiling_2_lift),
            "best_state": best_name,
            "best_lift": float(best_lift),
        },
        artifacts={"results": results_path, "yearly": yearly_path},
        metadata={"state_specs": [state.as_metadata() for state in STATE_SPECS], "hypothesis": SPEC.hypothesis},
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"\n=== FLOOR vs CEILING SYMMETRY ===")
    print(f"  at_ceiling (+6.5%+): {at_ceiling_ic:.4f}")
    print(f"  at_floor (-6.5%-):   {at_floor_ic:.4f}")
    print(f"  ceiling_1_of_3: {ceiling_1_ic:.4f}, floor_1_of_3: {floor_1_ic:.4f}")
    print(f"  ceiling_2_of_3: {ceiling_2_ic:.4f} (lift: {ceiling_2_lift:+.4f})")
    print(f"  floor_2_of_3:   {floor_2_ic:.4f} (lift: {floor_2_lift:+.4f})")
    print(f"\n=== VOL EXPANSION COMBOS ===")
    print(f"  ceiling_2_expansion: {ceiling_2_exp_ic:.4f}")
    print(f"  floor_2_expansion:  {floor_2_exp_ic:.4f} (lift: {floor_2_exp_lift:+.4f})")
    print(f"  near_floor_expansion: {near_floor_exp_ic:.4f}")
    print(f"\nBest state: {best_name} (IC: {best_ic:.4f}, lift: {best_lift:+.4f})")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()