"""
H435: volume_adjusted_price_momentum

Hypothesis: Price return normalized by volume (return / volume_z) captures
"expensive" vs "cheap" moves. Same return on higher volume = real force;
same return on lower volume = crowd blowoff/fade. Different from H431 rank
delta (which tested rank change) and H432 divergence (which tested bucketed
states). This tests the continuous ratio as a new feature class.

Mechanism: return / volume_z cross-sectional rank captures flow efficiency.
High return + low volume = blowoff (low alpha);
High return + high volume = real force (high alpha);
Low return + high volume = hidden accumulation;
Low return + low volume = quiet distribution.

Test: compute 5d return, volume_z, efficiency ratio cross-sectional rank,
and efficiency buckets. Compare efficiency ratio IC vs plain volume_z and
vs plain return. Use random baselines (not S1/C16 direct variations).
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


BRANCH_NAME = "h435_volume_adjusted_price_momentum"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Return / volume_z cross-sectional rank captures flow efficiency "
        "(real force vs blowoff). Different feature class from H431 rank delta "
        "(which tested rank change) and H432 divergence (which tested bucketed "
        "states). Test ratio as continuous score."
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
    StateSpec("volume_z_q5", "High volume (Q5: volume_z > 80th pctile)", family="volume", baseline="all_rows"),
    StateSpec("volume_z_q1", "Low volume (Q1: volume_z < 20th pctile)", family="volume", baseline="all_rows"),
    StateSpec("ret_5d_q5", "High 5d return (Q5)", family="return", baseline="all_rows"),
    StateSpec("ret_5d_q1", "Low 5d return (Q5)", family="return", baseline="all_rows"),
    StateSpec("efficiency_q5", "High efficiency ratio: ret_5d / vol_z (Q5)", family="efficiency", baseline="all_rows"),
    StateSpec("efficiency_q1", "Low efficiency ratio: ret_5d / vol_z (Q1)", family="efficiency", baseline="all_rows"),
    StateSpec("real_force", "High return + high volume", family="flow_type", baseline="all_rows"),
    StateSpec("blowoff", "High return + low volume", family="flow_type", baseline="all_rows"),
    StateSpec("hidden_accumulation", "Low return + high volume", family="flow_type", baseline="all_rows"),
    StateSpec("quiet_distribution", "Low return + low volume", family="flow_type", baseline="all_rows"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H435 volume_adjusted_price_momentum")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def compute_returns(vol_df: pd.DataFrame, days: int = 5) -> pd.DataFrame:
    df = vol_df.sort_values(["ticker", "time"])
    for lag in range(1, days + 1):
        shifted = df.groupby("ticker")[S1_SCORE_COL].shift(lag)
        df[f"ret_lag_{lag}"] = df[S1_SCORE_COL] - shifted
    ret_cols = [f"ret_lag_{lag}" for lag in range(1, days + 1)]
    df["ret_5d"] = df[ret_cols].mean(axis=1)
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
    vol = vol.rename(columns={"order_volume_ratio": "volume"})
    vol["time"] = pd.to_datetime(vol["time"], errors="coerce").dt.normalize()
    vol["ticker"] = vol["ticker"].astype(str).str.upper()
    vol = vol.dropna(subset=["time", "ticker"])
    vol = vol[vol["time"].dt.year <= 2025]
    vol = vol[vol["time"] >= pd.Timestamp("2018-01-01")]

    panel = panel.merge(vol[["time", "ticker", "volume"]], on=["time", "ticker"], how="left")
    panel["volume"] = panel["volume"].fillna(panel["volume"].median())

    panel = compute_returns(panel, days=5)

    panel["volume_z"] = panel.groupby("time")["volume"].transform(
        lambda x: (x - x.mean()) / (x.std() + 1e-9)
    )
    panel["volume_z"] = panel["volume_z"].clip(-5, 5)

    panel["ret_5d_z"] = panel.groupby("time")["ret_5d"].transform(
        lambda x: (x - x.mean()) / (x.std() + 1e-9)
    )

    panel["efficiency_ratio"] = panel["ret_5d"] / (panel["volume_z"].abs() + 0.1)
    panel["efficiency_ratio_rank"] = panel.groupby("time")["efficiency_ratio"].rank(
        method="average", pct=True
    )

    q5_vol = panel["volume_z"].groupby(panel["time"]).quantile(0.80)
    panel["volume_z_q5"] = panel["volume_z"] > panel["time"].map(q5_vol)
    q1_vol = panel["volume_z"].groupby(panel["time"]).quantile(0.20)
    panel["volume_z_q1"] = panel["volume_z"] < panel["time"].map(q1_vol)

    q5_ret = panel["ret_5d"].groupby(panel["time"]).quantile(0.80)
    panel["ret_5d_q5"] = panel["ret_5d"] > panel["time"].map(q5_ret)
    q1_ret = panel["ret_5d"].groupby(panel["time"]).quantile(0.20)
    panel["ret_5d_q1"] = panel["ret_5d"] < panel["time"].map(q1_ret)

    q5_eff = panel["efficiency_ratio_rank"].groupby(panel["time"]).quantile(0.80)
    panel["efficiency_q5"] = panel["efficiency_ratio_rank"] > panel["time"].map(q5_eff)
    q1_eff = panel["efficiency_ratio_rank"].groupby(panel["time"]).quantile(0.20)
    panel["efficiency_q1"] = panel["efficiency_ratio_rank"] < panel["time"].map(q1_eff)

    vol_med = panel["volume_z"].median()
    ret_med = panel["ret_5d"].median()
    panel["real_force"] = (panel["ret_5d"] >= ret_med) & (panel["volume_z"] >= vol_med)
    panel["blowoff"] = (panel["ret_5d"] >= ret_med) & (panel["volume_z"] < vol_med)
    panel["hidden_accumulation"] = (panel["ret_5d"] < ret_med) & (panel["volume_z"] >= vol_med)
    panel["quiet_distribution"] = (panel["ret_5d"] < ret_med) & (panel["volume_z"] < vol_med)

    panel = panel.dropna(subset=["volume", "ret_5d"])
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

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    all_rows_ic = results[results["name"] == "all_rows"]["avg_ic"].values
    all_rows_ic_val = float(all_rows_ic[0]) if len(all_rows_ic) > 0 else None

    eff_q5_ic = results[results["name"] == "efficiency_q5"]["avg_ic"].values
    eff_q5_val = float(eff_q5_ic[0]) if len(eff_q5_ic) > 0 else None

    eff_q1_ic = results[results["name"] == "efficiency_q1"]["avg_ic"].values
    eff_q1_val = float(eff_q1_ic[0]) if len(eff_q1_ic) > 0 else None

    eff_lift = (eff_q5_val - eff_q1_val) if eff_q5_val is not None and eff_q1_val is not None else None

    vol_q5_ic = results[results["name"] == "volume_z_q5"]["avg_ic"].values
    vol_q5_val = float(vol_q5_ic[0]) if len(vol_q5_ic) > 0 else None
    ret_q5_ic = results[results["name"] == "ret_5d_q5"]["avg_ic"].values
    ret_q5_val = float(ret_q5_ic[0]) if len(ret_q5_ic) > 0 else None

    rf_ic = results[results["name"] == "real_force"]["avg_ic"].values
    rf_val = float(rf_ic[0]) if len(rf_ic) > 0 else None
    bo_ic = results[results["name"] == "blowoff"]["avg_ic"].values
    bo_val = float(bo_ic[0]) if len(bo_ic) > 0 else None
    ha_ic = results[results["name"] == "hidden_accumulation"]["avg_ic"].values
    ha_val = float(ha_ic[0]) if len(ha_ic) > 0 else None
    qd_ic = results[results["name"] == "quiet_distribution"]["avg_ic"].values
    qd_val = float(qd_ic[0]) if len(qd_ic) > 0 else None

    pos_years_eff_q5 = int(results[results["name"] == "efficiency_q5"]["positive_years"].values[0]) if len(eff_q5_ic) > 0 else 0
    total_years_eff_q5 = int(results[results["name"] == "efficiency_q5"]["years"].values[0]) if len(eff_q5_ic) > 0 else 0
    pos_years_vol_q5 = int(results[results["name"] == "volume_z_q5"]["positive_years"].values[0]) if len(vol_q5_ic) > 0 else 0
    total_years_vol_q5 = int(results[results["name"] == "volume_z_q5"]["years"].values[0]) if len(vol_q5_ic) > 0 else 0

    if eff_lift is not None and eff_lift > 0.01 and pos_years_eff_q5 >= total_years_eff_q5 * 0.6:
        decision = "PASSED"
    elif eff_lift is not None and eff_lift > 0.005 and pos_years_eff_q5 >= total_years_eff_q5 * 0.5:
        decision = "MIXED"
    elif rf_val is not None and ha_val is not None and (rf_val > eff_q5_val if eff_q5_val else False):
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "all_rows_avg_ic": all_rows_ic_val,
            "eff_q5_avg_ic": eff_q5_val,
            "eff_q1_avg_ic": eff_q1_val,
            "eff_q5_eff_q1_lift": eff_lift,
            "eff_q5_positive_years": pos_years_eff_q5,
            "eff_q5_total_years": total_years_eff_q5,
            "volume_z_q5_avg_ic": vol_q5_val,
            "volume_z_q5_positive_years": pos_years_vol_q5,
            "volume_z_q5_total_years": total_years_vol_q5,
            "ret_5d_q5_avg_ic": ret_q5_val,
            "real_force_avg_ic": rf_val,
            "blowoff_avg_ic": bo_val,
            "hidden_accumulation_avg_ic": ha_val,
            "quiet_distribution_avg_ic": qd_val,
            "best_state_by_avg_ic": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
            "panel": panel_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\neff_q5 lift: {eff_lift}, positive years: {pos_years_eff_q5}/{total_years_eff_q5}")
    print(f"real_force IC: {rf_val}, blowoff IC: {bo_val}, hidden_acc IC: {ha_val}, quiet_dist IC: {qd_val}")
    print(f"\ndecision: {decision}")
    print(f"summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
