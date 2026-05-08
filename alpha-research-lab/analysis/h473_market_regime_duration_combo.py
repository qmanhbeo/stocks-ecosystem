"""
H473: market_regime_duration_combo

Hypothesis: How long vol_expansion has persisted affects signal quality.
Vol expansion that has lasted 3+ days vs one-day spike may have different dynamics.
D041 confirmed: vol_expansion is universal amplifier. Regime PERSISTENCE may matter too.

Data: Uses OHLCV volume to compute vol_expansion and its duration.
Compare with: C16 baseline, C23/C25/C26/C27 patterns.
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
from src.repo_paths import data_path

BRANCH_NAME = "market_regime_duration_combo"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "How long vol_expansion has persisted affects signal quality. "
        "Sustained vs sudden vol expansion may have different dynamics. "
        "Also test: regime BREAKS (vol contraction after sustained expansion) as reversal signal."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)

STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("vol_exp_sustained_3d", "Vol expansion sustained 3+ days + illiq", family="regime_duration"),
    StateSpec("vol_exp_sudden_1d", "Vol expansion sudden (1d only) + illiq", family="regime_duration"),
    StateSpec("vol_exp_5d_plus", "Vol expansion 5+ days + illiq", family="regime_duration"),
    StateSpec("vol_contraction_after_expansion", "Vol contraction after sustained expansion + illiq", family="regime_duration"),
    StateSpec("regime_no_change_5d", "No regime change in 5d + illiq", family="regime_duration"),
    StateSpec("vol_exp_first_3d", "Vol expansion first 3 days + illiq", family="regime_duration"),
    StateSpec("vol_exp_late_stage", "Vol expansion late stage (5d+) + illiq", family="regime_duration"),
    StateSpec("vol_exp_2d_streak", "Vol expansion 2 consecutive days + illiq", family="regime_duration"),
    StateSpec("vol_contraction_2d_plus", "Vol contraction 2+ days + illiq", family="regime_duration"),
]


def compute_regime_features(price_df):
    df = price_df.copy()
    if "time" not in df.columns or "ticker" not in df.columns:
        return df[["ticker", "time"]].assign(
            vol_expansion=0, vol_expansion_q80=False, illiq_rank=0.5, illiq_high=False,
            vol_exp_days=0, vol_contraction=False, vol_contraction_days=0,
            regime_change=False, regime_change_dir=0
        )
    df = df.sort_values(["ticker", "time"]).copy()

    df["vol_20d"] = df.groupby("ticker")["volume"].transform(
        lambda x: x.rolling(20, min_periods=10).mean()
    )
    df["vol_60d"] = df.groupby("ticker")["volume"].transform(
        lambda x: x.rolling(60, min_periods=20).mean()
    )
    df["vol_expansion"] = (df["vol_20d"] / df["vol_60d"].replace(0, np.nan) - 1).fillna(0)
    df["vol_expansion_q80"] = df.groupby("time")["vol_expansion"].transform(
        lambda x: x >= x.quantile(0.80)
    )

    ret = df["close"].pct_change(fill_method=None).abs()
    vol = df["volume"] / 1e6
    amihud = (ret / vol.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0)
    df["illiq_20d"] = amihud.rolling(20, min_periods=5).mean()
    df["illiq_rank"] = df.groupby("time")["illiq_20d"].transform(
        lambda x: x.rank(pct=True, na_option="keep")
    )
    df["illiq_high"] = df["illiq_rank"] >= 0.70

    df["vol_exp_rolling"] = df.groupby("ticker")["vol_expansion_q80"].transform(
        lambda x: x.rolling(10, min_periods=3).sum()
    )
    df["vol_exp_days"] = df["vol_exp_rolling"].fillna(0).astype(int)
    df["vol_exp_sustained"] = df["vol_exp_days"] >= 3
    df["vol_exp_sudden"] = df["vol_exp_days"] == 1
    df["vol_exp_5d_plus"] = df["vol_exp_days"] >= 5
    df["vol_exp_2d_streak"] = df["vol_exp_days"] >= 2

    df["vol_contraction"] = ~df["vol_expansion_q80"]
    df["vol_contraction_rolling"] = df.groupby("ticker")["vol_contraction"].transform(
        lambda x: x.rolling(5, min_periods=2).sum()
    )
    df["vol_contraction_days"] = df["vol_contraction_rolling"].fillna(0).astype(int)
    df["vol_contraction_2d_plus"] = df["vol_contraction_days"] >= 2

    df["regime_change"] = df.groupby("ticker")["vol_expansion_q80"].transform(lambda x: x != x.shift(1))
    df["regime_change_dir"] = np.where(
        df["regime_change"],
        np.where(df["vol_expansion_q80"], 1, -1),
        0
    )

    return df[["ticker", "time", "vol_expansion", "vol_expansion_q80", "illiq_rank",
               "illiq_high", "vol_exp_days", "vol_contraction", "vol_contraction_days",
               "regime_change", "regime_change_dir", "vol_exp_sustained", "vol_exp_sudden",
               "vol_exp_5d_plus", "vol_exp_2d_streak", "vol_contraction_2d_plus"]]


def load_panel(args, spec):
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )
    panel["all_rows"] = True

    price_files = sorted(data_path("stock").glob("gia_lich_su_*_1D.parquet"))
    if price_files:
        price_dfs = []
        for f in price_files:
            ticker = f.stem.replace("gia_lich_su_", "").replace("_1D", "")
            df = pd.read_parquet(f)
            if "date" in df.columns and "time" not in df.columns:
                df = df.rename(columns={"date": "time"})
            df["ticker"] = ticker
            price_dfs.append(df[["ticker", "time", "close", "volume"]])
        price_all = pd.concat(price_dfs, ignore_index=True)
        price_features = compute_regime_features(price_all)
        panel = panel.merge(price_features, on=["time", "ticker"], how="left")
    else:
        panel["vol_expansion"] = 0
        panel["vol_expansion_q80"] = False
        panel["illiq_rank"] = 0.5
        panel["illiq_high"] = False
        panel["vol_exp_days"] = 0
        panel["vol_contraction"] = False
        panel["vol_contraction_days"] = 0

    panel["vol_exp_sustained_3d"] = panel["vol_exp_sustained"] & panel["illiq_high"]
    panel["vol_exp_sudden_1d"] = panel["vol_exp_sudden"] & panel["illiq_high"]
    panel["vol_exp_5d_plus"] = panel["vol_exp_5d_plus"] & panel["illiq_high"]
    panel["vol_contraction_after_expansion"] = (
        panel["vol_contraction_2d_plus"] &
        panel.groupby("ticker")["vol_expansion_q80"].transform(lambda x: x.shift(1).fillna(False))
    ) & panel["illiq_high"]
    panel["regime_no_change_5d"] = (panel["vol_exp_days"] >= 5) & ~panel["regime_change"] & panel["illiq_high"]
    panel["vol_exp_first_3d"] = ((panel["vol_exp_days"] >= 1) & (panel["vol_exp_days"] <= 3)) & panel["illiq_high"]
    panel["vol_exp_late_stage"] = panel["vol_exp_5d_plus"] & panel["illiq_high"]
    panel["vol_exp_2d_streak"] = panel["vol_exp_2d_streak"] & panel["illiq_high"]
    panel["vol_contraction_2d_plus"] = panel["vol_contraction_2d_plus"] & panel["illiq_high"]

    return panel


def parse_args():
    parser = argparse.ArgumentParser(description="H473: market_regime_duration_combo")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    return parser.parse_args()


def run_branch(args):
    spec = replace(
        SPEC,
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        min_year_rows=int(SPEC.min_year_rows),
        min_phase_rows=int(SPEC.min_phase_rows),
    )
    context = build_experiment_context(spec, artifact_subdir="research_branches")
    panel = load_panel(args, spec)
    print(f"Panel: {panel.shape}, date range: {panel['time'].min()} - {panel['time'].max()}")

    state_names = [s.name for s in STATE_SPECS]
    validate_state_columns(panel, state_names, spec)

    results, yearly = evaluate_state_specs(
        panel,
        STATE_SPECS,
        score_col=S1_SCORE_COL,
        target_col=S1_TARGET_COL,
        spec=spec,
    )

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].values[0]

    print("\n=== State Results ===")
    print(f"{'State':30s} {'Avg IC':>8s} {'Lift':>8s} {'Rows':>8s} {'Pos Yrs':>8s}")
    print("-" * 65)
    for _, row in results.sort_values("avg_ic", ascending=False).iterrows():
        lift = (row["avg_ic"] or 0) - baseline_ic
        print(f"{row['name']:30s} {(row['avg_ic'] or 0):+.4f}  {lift:+.4f}  {row['pooled_rows']:7d}  {row['positive_years']}/{row['years']}")

    best = results.sort_values("avg_ic", ascending=False, na_position="last").iloc[0]
    lift = (best["avg_ic"] or 0) - baseline_ic

    if best["avg_ic"] and best["positive_years"] / best["years"] >= 0.7 and best["avg_ic"] > 0.15:
        decision = "PASSED"
    elif best["avg_ic"] and best["avg_ic"] > baseline_ic + 0.02:
        decision = "PASSED"
    elif best["avg_ic"] and best["avg_ic"] > baseline_ic + 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    print(f"\n=== Decision: {decision} ===")
    print(f"Best: {best['name']} (IC={best['avg_ic']}, lift={lift:.4f})")

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "branch": BRANCH_NAME,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "best_state": best["name"],
            "best_avg_ic": float(best["avg_ic"]) if best["avg_ic"] else None,
            "best_lift": float(lift),
            "baseline_ic": float(baseline_ic) if baseline_ic else None,
        },
        artifacts={
            "results": str(results_path),
            "yearly": str(yearly_path),
        },
        metadata={
            "hypothesis": SPEC.hypothesis,
            "state_specs": [s.as_metadata() for s in STATE_SPECS],
        },
    )
    return summary_path


def main():
    run_branch(parse_args())


if __name__ == "__main__":
    main()