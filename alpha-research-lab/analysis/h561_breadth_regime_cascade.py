"""
H561: Breadth Regime Hierarchy (Cascade)

H550 found: C25 alone (0.2115) > C24×own_breadth (0.2080) > C23 (0.1896).
Each signal has different optimal breadth window.

Hypothesis: Test priority cascade: use strongest available signal each day
(C25 preferred, fall back to C24 with own-breadth, then C23).
Compare against equal-weight composite.

Pass criterion: cascade beats composite by > +0.01 IC
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import numpy as np
import pandas as pd

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
    normalize_time_ticker,
    restrict_years,
)
from src.repo_paths import data_path


BRANCH_NAME = "breadth_regime_cascade"
MODE = "research_branch"


def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Compute C23/C24/C25/C26 signals following H550 methodology."""
    panel = df.copy()

    panel["volatility"] = panel.groupby("ticker")["order_volume_ratio_rank"].transform(
        lambda x: x.rolling(5, min_periods=1).std()
    )
    panel["vol_expansion"] = panel.groupby("time", sort=False)["volatility"].rank(pct=True) >= 0.8

    panel["order_rank"] = panel.groupby("time", sort=False)["order_volume_ratio_rank"].rank(pct=True)
    panel["high_illiq"] = panel["order_rank"] >= 0.8

    panel["c16_low"] = panel["order_volume_ratio_rank"] < 0.2
    panel["c16_high"] = panel["order_volume_ratio_rank"] >= 0.8

    panel["c23_signal"] = panel["high_illiq"] & panel["vol_expansion"]

    if "pct_change" in panel.columns:
        panel["ceiling_proxy"] = panel["pct_change"] >= 5.0
    else:
        panel["ceiling_proxy"] = panel["order_volume_ratio_rank"] < 0.1
    panel["c24_signal"] = panel["ceiling_proxy"] & panel["vol_expansion"]

    if "pct_change" in panel.columns:
        panel["vwap_below_proxy"] = panel["pct_change"] <= -2.0
    else:
        panel["vwap_below_proxy"] = panel["order_volume_ratio_rank"] >= 0.9
    panel["c25_signal"] = panel["vwap_below_proxy"] & panel["vol_expansion"]

    panel["buy_heavy"] = panel["order_volume_ratio_rank"] < 0.15
    panel["c26_signal"] = panel["buy_heavy"] & panel["high_illiq"] & panel["vol_expansion"]

    panel["composite_signal"] = (
        panel["c23_signal"] | panel["c24_signal"] | panel["c25_signal"] | panel["c26_signal"]
    )

    return panel


def compute_breadth_for_signals(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute date-level breadth and own-breadth filter for each signal."""
    for signal_name in ["c23_signal", "c24_signal", "c25_signal", "c26_signal"]:
        active_per_date = panel[panel[signal_name]].groupby("time")["ticker"].nunique().reset_index()
        active_per_date.columns = ["time", f"{signal_name}_active_tickers"]

        total_per_date = panel.groupby("time")["ticker"].nunique().reset_index()
        total_per_date.columns = ["time", "total_tickers"]

        breadth_df = active_per_date.merge(total_per_date, on="time", how="outer")
        breadth_df[f"{signal_name}_breadth"] = breadth_df[f"{signal_name}_active_tickers"] / breadth_df["total_tickers"]
        breadth_df[f"{signal_name}_breadth"] = breadth_df[f"{signal_name}_breadth"].fillna(0)

        signal_dates = breadth_df[breadth_df[f"{signal_name}_active_tickers"] > 0]
        if len(signal_dates) > 0:
            threshold = signal_dates[f"{signal_name}_breadth"].quantile(0.2)
            breadth_df[f"{signal_name}_low_breadth"] = breadth_df[f"{signal_name}_breadth"] <= threshold
        else:
            breadth_df[f"{signal_name}_low_breadth"] = False

        panel = panel.merge(breadth_df[["time", f"{signal_name}_breadth", f"{signal_name}_low_breadth"]],
                           on="time", how="left")

    return panel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H561: Breadth Regime Hierarchy Cascade")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def load_panel(args: argparse.Namespace) -> pd.DataFrame:
    s1_path = data_path("features/xs_barrier_vol_1d_hose_full.parquet")
    s1_df = pd.read_parquet(s1_path, columns=["time", "ticker", "xs_proba", "actual"])
    s1_df = normalize_time_ticker(s1_df, source="S1 panel")
    s1_df = restrict_years(s1_df, start_year=args.start_year, end_year=args.end_year, source="S1 panel")
    s1_df = s1_df.rename(columns={"xs_proba": "s1_xs_proba", "actual": "s1_barrier_hit_1d"})

    c16_path = data_path("features/xs_order_pressure_daily.parquet")
    c16_df = pd.read_parquet(c16_path)
    c16_df = normalize_time_ticker(c16_df, source="C16 panel")
    c16_df = restrict_years(c16_df, start_year=args.start_year, end_year=args.end_year, source="C16 panel")

    df = s1_df.merge(c16_df, on=["time", "ticker"], how="inner")
    print(f"Merged panel: {len(df)} rows, years {df['time'].dt.year.min()}-{df['time'].dt.year.max()}")

    panel = compute_signals(df)
    panel = compute_breadth_for_signals(panel)

    panel["cascade_c25_priority"] = panel["c25_signal"]
    panel["cascade_c24_breadth"] = panel["c24_signal"] & panel["c24_signal_low_breadth"]
    panel["cascade_c23_fallback"] = panel["c23_signal"] & ~panel["c25_signal"] & ~panel["cascade_c24_breadth"]

    panel["cascade_priority"] = panel["cascade_c25_priority"] | panel["cascade_c24_breadth"] | panel["cascade_c23_fallback"]

    return panel


def run_branch(args: argparse.Namespace) -> str:
    spec = ExperimentSpec(
        name=BRANCH_NAME,
        mode=MODE,
        hypothesis=(
            "Test priority cascade: use strongest available signal each day "
            "(C25 preferred, fall back to C24×own_breadth, then C23). "
            "H550 found each signal has different optimal breadth window."
        ),
        start_year=2015,
        end_year=2025,
        min_year_rows=500,
        min_phase_rows=500,
        target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
        score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
    )
    context = build_experiment_context(spec, artifact_subdir="research_branch")

    panel = load_panel(args)

    STATE_SPECS = [
        StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
        StateSpec("cascade_priority", "Cascade: C25优先→C24×breadth→C23", family="cascade"),
        StateSpec("composite_signal", "Composite of all signals (C23+C24+C25+C26)", family="composite"),
        StateSpec("c25_signal", "C25 alone", family="individual"),
        StateSpec("c24_signal_low_breadth", "C24 × own-breadth", family="individual"),
        StateSpec("c23_signal", "C23 alone", family="individual"),
    ]

    available_states = [s.name for s in STATE_SPECS if s.name in panel.columns]
    STATE_SPECS = [s for s in STATE_SPECS if s.name in available_states]

    validate_state_columns(panel, [state.name for state in STATE_SPECS], spec)

    results, yearly = evaluate_state_specs(
        panel,
        STATE_SPECS,
        score_col="s1_xs_proba",
        target_col="s1_barrier_hit_1d",
        spec=spec,
    )

    results_path = write_dataframe_artifact(results, context, f"{BRANCH_NAME}_results")
    yearly_path = write_dataframe_artifact(yearly, context, f"{BRANCH_NAME}_yearly")

    print("Results DataFrame:")
    print(results[["name", "avg_ic"]].to_string(index=False))
    print("\n")

    baseline = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if "all_rows" in results["name"].values else results["avg_ic"].mean()
    cascade = results[results["name"] == "cascade_priority"]["avg_ic"].iloc[0] if "cascade_priority" in results["name"].values else 0.0
    composite = results[results["name"] == "composite_signal"]["avg_ic"].iloc[0] if "composite_signal" in results["name"].values else 0.0

    cascade_vs_composite = cascade - composite

    if cascade_vs_composite > 0.01:
        decision = "PASSED"
    elif cascade_vs_composite > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": baseline,
            "cascade_ic": cascade,
            "composite_ic": composite,
            "cascade_vs_composite": cascade_vs_composite,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": "cascade priority beats composite",
        },
    )

    print("\n=== H561: Breadth Regime Cascade Test ===")
    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nBaseline IC: {baseline:.4f}")
    print(f"Cascade IC: {cascade:.4f}")
    print(f"Composite IC: {composite:.4f}")
    print(f"Cascade vs Composite: {cascade_vs_composite:.4f}")
    print(f"\nDecision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()