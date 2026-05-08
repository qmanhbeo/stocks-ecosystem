"""
H439: volatility_regime_transition

Hypothesis: Volatility expansion vs contraction is a different state than static high/low vol.
H411 tested volume levels, but volatility TRANSITION not tested. Connection: H411
tested volume levels, H435 tested signal strength. Volatility TRANSITION might capture
regime changes better than static volatility.

Mechanism: Compute vol_z 5d change (vol expansion vs contraction buckets), test
forward IC. High vol + expanding vs high vol + contracting are different regimes.

Test: Compute 5d rolling volatility, its change (delta), bucket by transition state,
test forward IC vs baseline. Compare against static volume_z and H413 ranker.
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


BRANCH_NAME = "h439_volatility_regime_transition"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Volatility expansion vs contraction is a different regime than static high/low vol. "
        "H411 tested volume levels but not volatility TRANSITION. Compute vol_z 5d change "
        "(vol expansion vs contraction buckets), test forward IC. High vol + expanding vs "
        "high vol + contracting are different regimes."
    ),
    start_year=2018,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)

STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("vol_z_q5", "High volatility (Q5)", family="vol_level"),
    StateSpec("vol_z_q1", "Low volatility (Q1)", family="vol_level"),
    StateSpec("vol_expanding", "Volatility expanding (5d delta > 0)", family="vol_transition"),
    StateSpec("vol_contracting", "Volatility contracting (5d delta < 0)", family="vol_transition"),
    StateSpec("high_vol_expanding", "High vol + expanding", family="combined"),
    StateSpec("high_vol_contracting", "High vol + contracting", family="combined"),
    StateSpec("low_vol_expanding", "Low vol + expanding", family="combined"),
    StateSpec("low_vol_contracting", "Low vol + contracting", family="combined"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H439 volatility_regime_transition")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def compute_volatility(panel: pd.DataFrame, days: int = 5) -> pd.DataFrame:
    df = panel.sort_values(["ticker", "time"])
    for lag in range(1, days + 1):
        shifted = df.groupby("ticker")[S1_SCORE_COL].shift(lag)
        df[f"ret_lag_{lag}"] = df[S1_SCORE_COL] - shifted
    ret_cols = [f"ret_lag_{lag}" for lag in range(1, days + 1)]
    df["ret_5d"] = df[ret_cols].mean(axis=1)
    df["vol_5d"] = df[ret_cols].std(axis=1).fillna(0)
    return df


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )
    panel["all_rows"] = True

    vol_path = ROOT / "data" / "features" / "xs_order_pressure_daily.parquet"
    vol = pd.read_parquet(vol_path, columns=["time", "ticker", "order_volume_ratio"])
    vol["time"] = pd.to_datetime(vol["time"], errors="coerce").dt.normalize()
    vol["ticker"] = vol["ticker"].astype(str).str.upper()
    vol = vol.dropna(subset=["time", "ticker"])
    vol = vol[vol["time"].dt.year <= 2025]
    vol = vol[vol["time"] >= pd.Timestamp("2018-01-01")]
    panel = panel.merge(vol[["time", "ticker", "order_volume_ratio"]], on=["time", "ticker"], how="left")
    panel["c16"] = panel["order_volume_ratio"].fillna(panel["order_volume_ratio"].median())
    panel = panel.dropna(subset=["c16"])

    panel = compute_volatility(panel, days=5)

    panel["vol_z"] = panel.groupby("time")["vol_5d"].transform(
        lambda x: (x - x.mean()) / (x.std() + 1e-9)
    )
    panel["vol_z"] = panel["vol_z"].clip(-5, 5)

    panel["vol_z_prior"] = panel.groupby("ticker")["vol_z"].shift(5)
    panel["vol_z_delta"] = panel["vol_z"] - panel["vol_z_prior"].fillna(0)

    q5_vol = panel["vol_z"].groupby(panel["time"]).quantile(0.80)
    panel["vol_z_q5"] = panel["vol_z"] > panel["time"].map(q5_vol)
    q1_vol = panel["vol_z"].groupby(panel["time"]).quantile(0.20)
    panel["vol_z_q1"] = panel["vol_z"] < panel["time"].map(q1_vol)

    panel["vol_expanding"] = panel["vol_z_delta"] > 0.2
    panel["vol_contracting"] = panel["vol_z_delta"] < -0.2

    panel["high_vol_expanding"] = panel["vol_z_q5"] & panel["vol_expanding"]
    panel["high_vol_contracting"] = panel["vol_z_q5"] & panel["vol_contracting"]
    panel["low_vol_expanding"] = panel["vol_z_q1"] & panel["vol_expanding"]
    panel["low_vol_contracting"] = panel["vol_z_q1"] & panel["vol_contracting"]

    return panel


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
    panel_path = write_dataframe_artifact(panel, context, f"{BRANCH_NAME}_panel")

    all_rows_ic = results[results["name"] == "all_rows"]["avg_ic"].values
    all_rows_ic_val = float(all_rows_ic[0]) if len(all_rows_ic) > 0 else None

    exp_ic = results[results["name"] == "vol_expanding"]["avg_ic"].values
    exp_val = float(exp_ic[0]) if len(exp_ic) > 0 else None
    con_ic = results[results["name"] == "vol_contracting"]["avg_ic"].values
    con_val = float(con_ic[0]) if len(con_ic) > 0 else None

    hve_ic = results[results["name"] == "high_vol_expanding"]["avg_ic"].values
    hve_val = float(hve_ic[0]) if len(hve_ic) > 0 else None
    hvc_ic = results[results["name"] == "high_vol_contracting"]["avg_ic"].values
    hvc_val = float(hvc_ic[0]) if len(hvc_ic) > 0 else None
    lve_ic = results[results["name"] == "low_vol_expanding"]["avg_ic"].values
    lve_val = float(lve_ic[0]) if len(lve_ic) > 0 else None
    lvc_ic = results[results["name"] == "low_vol_contracting"]["avg_ic"].values
    lvc_val = float(lvc_ic[0]) if len(lvc_ic) > 0 else None

    vol_q5_ic = results[results["name"] == "vol_z_q5"]["avg_ic"].values
    vol_q5_val = float(vol_q5_ic[0]) if len(vol_q5_ic) > 0 else None

    hve_vs_hvc = (hve_val - hvc_val) if hve_val is not None and hvc_val is not None else None
    exp_vs_con = (exp_val - con_val) if exp_val is not None and con_val is not None else None

    pos_years_hve = int(results[results["name"] == "high_vol_expanding"]["positive_years"].values[0]) if len(hve_ic) > 0 else 0
    total_years_hve = int(results[results["name"] == "high_vol_expanding"]["years"].values[0]) if len(hve_ic) > 0 else 0
    pos_years_hvc = int(results[results["name"] == "high_vol_contracting"]["positive_years"].values[0]) if len(hvc_ic) > 0 else 0
    total_years_hvc = int(results[results["name"] == "high_vol_contracting"]["years"].values[0]) if len(hvc_ic) > 0 else 0

    if hve_vs_hvc is not None and hve_vs_hvc > 0.01 and pos_years_hve >= total_years_hve * 0.6:
        decision = "PASSED"
    elif hve_vs_hvc is not None and hve_vs_hvc > 0.005 and pos_years_hve >= total_years_hve * 0.5:
        decision = "MIXED"
    elif exp_vs_con is not None and exp_vs_con > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "all_rows_avg_ic": all_rows_ic_val,
            "vol_expanding_avg_ic": exp_val,
            "vol_contracting_avg_ic": con_val,
            "exp_vs_con_lift": exp_vs_con,
            "high_vol_expanding_avg_ic": hve_val,
            "high_vol_expanding_pos_years": f"{pos_years_hve}/{total_years_hve}",
            "high_vol_contracting_avg_ic": hvc_val,
            "high_vol_contracting_pos_years": f"{pos_years_hvc}/{total_years_hvc}",
            "low_vol_expanding_avg_ic": lve_val,
            "low_vol_contracting_avg_ic": lvc_val,
            "hve_vs_hvc_lift": hve_vs_hvc,
            "vol_z_q5_avg_ic": vol_q5_val,
            "best_state": results.sort_values("avg_ic", ascending=False, na_position="last").iloc[0]["name"],
            "best_avg_ic": results.sort_values("avg_ic", ascending=False, na_position="last").iloc[0]["avg_ic"],
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
            "panel": panel_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nExpanding IC: {exp_val}, Contracting IC: {con_val}, lift: {exp_vs_con}")
    print(f"High vol+expanding IC: {hve_val} ({pos_years_hve}/{total_years_hve} pos years)")
    print(f"High vol+contracting IC: {hvc_val} ({pos_years_hvc}/{total_years_hvc} pos years)")
    print(f"HVE vs HVC lift: {hve_vs_hvc}")
    print(f"Decision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()