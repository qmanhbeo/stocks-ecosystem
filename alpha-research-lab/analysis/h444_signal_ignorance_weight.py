"""
H444 - Signal Ignorance Weight

Hypothesis: True edge is knowing WHEN to ignore S1/C16, not weighting them.
S1/C16 in certain regimes hurt; ignorance is alpha.

First test: Use cross-sectional regime features (IC, temperature, breadth) to bucket S1 panel,
test whether S1 IC varies enough by regime to create an ignorance strategy vs always-on S1.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiment_contract import (
    S1_DEFAULT_PATH,
    ExperimentSpec,
    StateSpec,
    load_s1_decision_panel,
)


BRANCH_NAME = "signal_ignorance_weight"
MODE = "research_branch"

# S1 panel column names
S1_SCORE = "s1_xs_proba"
S1_TARGET = "s1_barrier_hit_1d"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "S1/C16 are robust across most regimes, but there may be specific regime "
        "corners where they degrade. The edge is knowing when to ignore them."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H444: Test whether regime-based S1/C16 ignorance beats always-on baseline."
        )
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
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

    # Build regime features from cross-sectional properties (no external data needed)
    # Compute per-date IC of S1 against target - this is our signal efficacy measure
    def calc_ic(group):
        if len(group) > 10:
            return group[S1_SCORE].corr(group[S1_TARGET])
        return np.nan

    date_ic = panel.groupby("time").apply(calc_ic).reset_index()
    date_ic.columns = ["time", "date_ic"]

    # Compute cross-sectional average score (market temperature) and breadth
    date_temp = panel.groupby("time").agg(
        avg_score=(S1_SCORE, "mean"),
        n_tickers=("ticker", "count"),
        pos_rate=(S1_TARGET, "mean"),  # actual positive rate = breadth
    ).reset_index()

    # Merge features
    date_stats = date_ic.merge(date_temp, on="time")

    # Add regime buckets based on IC and temperature
    date_stats["ic_bucket"] = pd.qcut(date_stats["date_ic"], q=5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
    date_stats["temp_bucket"] = pd.qcut(date_stats["avg_score"], q=5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
    date_stats["breadth_bucket"] = pd.qcut(date_stats["pos_rate"], q=5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")

    # Merge regime buckets back
    panel = panel.merge(date_stats[["time", "ic_bucket", "temp_bucket", "breadth_bucket", "date_ic", "avg_score"]], on="time", how="left")

    return panel


def define_states() -> list[StateSpec]:
    """Define state specs based on regime features."""
    return [
        StateSpec("all_rows", "All S1 panel rows - baseline", family="baseline", primary=True),
        StateSpec("high_ic", "High IC regime (Q5)", family="regime", baseline="all_rows"),
        StateSpec("low_ic", "Low IC regime (Q1)", family="regime", baseline="all_rows"),
        StateSpec("high_temp", "High temperature (Q5)", family="regime", baseline="all_rows"),
        StateSpec("low_temp", "Low temperature (Q1)", family="regime", baseline="all_rows"),
        StateSpec("high_breadth", "High breadth (Q5)", family="regime", baseline="all_rows"),
        StateSpec("low_breadth", "Low breadth (Q1)", family="regime", baseline="all_rows"),
        StateSpec("high_ic_high_temp", "High IC + high temp combo", family="combo", baseline="all_rows"),
        StateSpec("high_ic_low_temp", "High IC + low temp combo", family="combo", baseline="all_rows"),
        StateSpec("low_ic_high_temp", "Low IC + high temp combo", family="combo", baseline="all_rows"),
        StateSpec("low_ic_low_temp", "Low IC + low temp combo", family="combo", baseline="all_rows"),
        StateSpec("high_breadth_high_ic", "High breadth + high IC combo", family="combo", baseline="all_rows"),
        StateSpec("low_breadth_low_ic", "Low breadth + low IC combo", family="combo", baseline="all_rows"),
    ]


def compute_state_metrics(panel: pd.DataFrame, states: list[StateSpec]) -> pd.DataFrame:
    """Compute IC and row counts for each state."""
    results = []
    for state in states:
        if state.name == "all_rows":
            subset = panel
        elif state.name == "high_ic":
            subset = panel[panel["ic_bucket"] == "Q5"]
        elif state.name == "low_ic":
            subset = panel[panel["ic_bucket"] == "Q1"]
        elif state.name == "high_temp":
            subset = panel[panel["temp_bucket"] == "Q5"]
        elif state.name == "low_temp":
            subset = panel[panel["temp_bucket"] == "Q1"]
        elif state.name == "high_breadth":
            subset = panel[panel["breadth_bucket"] == "Q5"]
        elif state.name == "low_breadth":
            subset = panel[panel["breadth_bucket"] == "Q1"]
        elif state.name == "high_ic_high_temp":
            subset = panel[(panel["ic_bucket"] == "Q5") & (panel["temp_bucket"] == "Q5")]
        elif state.name == "high_ic_low_temp":
            subset = panel[(panel["ic_bucket"] == "Q5") & (panel["temp_bucket"] == "Q1")]
        elif state.name == "low_ic_high_temp":
            subset = panel[(panel["ic_bucket"] == "Q1") & (panel["temp_bucket"] == "Q5")]
        elif state.name == "low_ic_low_temp":
            subset = panel[(panel["ic_bucket"] == "Q1") & (panel["temp_bucket"] == "Q1")]
        elif state.name == "high_breadth_high_ic":
            subset = panel[(panel["breadth_bucket"] == "Q5") & (panel["ic_bucket"] == "Q5")]
        elif state.name == "low_breadth_low_ic":
            subset = panel[(panel["breadth_bucket"] == "Q1") & (panel["ic_bucket"] == "Q1")]
        else:
            continue

        if len(subset) > 100:
            ic = subset[S1_SCORE].corr(subset[S1_TARGET])
            results.append({
                "state": state.name,
                "ic": ic,
                "rows": len(subset),
                "years": len(subset["year"].unique()),
            })

    return pd.DataFrame(results)


def decision(results_df: pd.DataFrame) -> dict:
    """Decision logic: can any regime beat baseline with enough difference?"""
    baseline = results_df[results_df["state"] == "all_rows"].iloc[0]
    baseline_ic = baseline["ic"]
    baseline_rows = baseline["rows"]

    print(f"\nBaseline IC: {baseline_ic:.4f} ({baseline_rows} rows)")

    # Check if any regime has notably different IC
    best_state = None
    best_lift = 0
    for _, row in results_df.iterrows():
        if row["state"] == "all_rows":
            continue
        lift = row["ic"] - baseline_ic
        print(f"  {row['state']}: IC={row['ic']:.4f}, lift={lift:+.4f}, rows={row['rows']}")
        if lift > best_lift:
            best_lift = lift
            best_state = row["state"]

    # Check the worst regime for potential ignorance opportunity
    worst_state = None
    worst_lift = 0
    for _, row in results_df.iterrows():
        if row["state"] == "all_rows":
            continue
        lift = row["ic"] - baseline_ic
        if lift < worst_lift:
            worst_lift = lift
            worst_state = row["state"]

    print(f"\nBest regime: {best_state} (lift {best_lift:+.4f})")
    print(f"Worst regime: {worst_state} (lift {worst_lift:+.4f})")

    # Ignorance opportunity: can ignoring the worst regime help?
    # If worst regime has significantly lower IC, we could potentially ignore it
    # But if it's just slightly lower, not actionable

    return {
        "baseline_ic": baseline_ic,
        "best_regime": best_state,
        "best_lift": best_lift,
        "worst_regime": worst_state,
        "worst_lift": worst_lift,
        "ignorance_opportunity": abs(worst_lift) > 0.01,  # At least 1% IC difference
    }


def main():
    args = parse_args()
    spec = replace(SPEC, start_year=args.start_year, end_year=args.end_year)

    print(f"Loading S1 panel {args.s1_path}...")
    panel = load_panel(args, spec)

    # Extract year from time column
    panel["year"] = panel["time"].dt.year

    print(f"Panel loaded: {len(panel)} rows, {panel['time'].nunique()} dates")
    print(f"Years: {panel['year'].min()}-{panel['year'].max()}")

    states = define_states()
    print(f"\nEvaluating {len(states)} states...")

    results = compute_state_metrics(panel, states)
    print("\n=== State IC Results ===")
    print(results.to_string(index=False))

    verdict = decision(results)

    print(f"\n=== Verdict ===")
    if verdict["ignorance_opportunity"]:
        print(f"PASSED: Found ignorance opportunity - worst regime '{verdict['worst_regime']}' has {verdict['worst_lift']:+.4f} lift")
        print("The worst regime differs enough from baseline to potentially ignore.")
    elif verdict["best_lift"] > 0.015 and verdict["best_lift"] > abs(verdict["worst_lift"]):
        print(f"PASSED: Best regime '{verdict['best_regime']}' has strong lift {verdict['best_lift']:+.4f}")
        print("Use as regime conditioner for S1/C16.")
    else:
        print(f"FAILED: S1/C16 are robust across all regimes ({verdict['best_lift']:+.4f} best, {verdict['worst_lift']:+.4f} worst)")
        print("No actionable ignorance opportunity found.")

    # Write results to artifact
    output_path = ROOT / "artifacts" / "run_summaries" / f"h444_{BRANCH_NAME}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    import json
    artifact = {
        "experiment": BRANCH_NAME,
        "hypothesis": spec.hypothesis,
        "baseline_ic": verdict["baseline_ic"],
        "best_regime": verdict["best_regime"],
        "best_lift": verdict["best_lift"],
        "worst_regime": verdict["worst_regime"],
        "worst_lift": verdict["worst_lift"],
        "results": results.to_dict("records"),
        "verdict": "PASSED" if verdict["ignorance_opportunity"] or verdict["best_lift"] > 0.015 else "FAILED",
    }
    with open(output_path, "w") as f:
        json.dump(artifact, f, indent=2)

    print(f"\nArtifact written to: {output_path}")


if __name__ == "__main__":
    main()