"""
H479: adaptive_signal_weights

Hypothesis: Weight C23-C26 by their RECENT 60d IC, not equal weight.
If IC-weighted outperforms, adaptive weighting adds value.

Optimized version: compute date-level rolling IC instead of row-level.
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


BRANCH_NAME = "adaptive_signal_weights"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Weight C23-C26 by their recent 60d IC instead of equal weight. "
        "If IC-weighted outperforms, adaptive weighting adds value."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H479 adaptive_signal_weights test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--order-stats-path", type=str,
                        default=str(data_path("order_stats/cafef/order_stats_daily.parquet")))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def compute_date_rolling_ic(df: pd.DataFrame, date_col: str, signal_col: str, target_col: str, window: int = 60) -> pd.DataFrame:
    """Compute rolling IC at date level - much faster."""
    df = df.sort_values(date_col)
    dates = df[date_col].unique()
    date_to_ic = {}
    
    date_idx = {d: i for i, d in enumerate(dates)}
    
    for i, date in enumerate(dates):
        start_idx = max(0, i - window)
        hist_dates = dates[start_idx:i]
        if len(hist_dates) < 20:
            date_to_ic[date] = np.nan
            continue
        hist = df[df[date_col].isin(hist_dates)].dropna(subset=[signal_col, target_col])
        if len(hist) < 100:
            date_to_ic[date] = np.nan
            continue
        date_to_ic[date] = hist[signal_col].corr(hist[target_col])
    
    return df[date_col].map(date_to_ic)


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
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
    order_stats["buy_sell_volume_imbalance"] = (
        (order_stats["buy_order_volume"] - order_stats["sell_order_volume"]) /
        (order_stats["buy_order_volume"] + order_stats["sell_order_volume"] + 1)
    )

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume", "buy_sell_volume_imbalance"]],
        on=["time", "ticker"],
        how="left",
    )

    panel = panel.dropna(subset=["pct_change", "total_volume"])
    panel = panel[panel["total_volume"] > 0]

    panel = panel.sort_values(["ticker", "time"])

    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )

    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8

    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_volume_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = imbalance_rank >= 0.8

    panel = panel.dropna(subset=["buy_sell_volume_imbalance"])
    panel["illiq"] = panel["pct_change"].abs() / (panel["total_volume"] / 1e9 + 1)
    panel["illiq_20d"] = panel.groupby("ticker")["illiq"].transform(
        lambda x: x.rolling(window=20, min_periods=10).mean()
    )
    illiq_rank = panel.groupby("time", sort=False)["illiq_20d"].rank(method="average", pct=True)
    panel["high_illiq"] = illiq_rank >= 0.80

    panel = panel.dropna(subset=["illiq_20d"])

    panel["c23"] = (panel["high_illiq"] & panel["vol_expansion"]).astype(float)
    panel["c24"] = panel["vol_expansion"].astype(float)
    panel["c25"] = panel["vol_expansion"].astype(float)
    panel["c26"] = (panel["buy_heavy"] & (illiq_rank >= 0.70) & panel["vol_expansion"]).astype(float)

    panel["equal_weight_composite"] = (panel["c23"] + panel["c24"] + panel["c25"] + panel["c26"]) / 4

    panel = panel.dropna(subset=["vol_expansion", "high_illiq", "buy_heavy"])

    panel = panel.sort_values("time")

    print("Computing rolling ICs (date-level)...")
    for sig in ["c23", "c24", "c25", "c26"]:
        print(f"  {sig}...")
        panel[f"{sig}_rolling_ic"] = compute_date_rolling_ic(
            panel, "time", sig, S1_TARGET_COL, window=60
        )

    ic_cols = ["c23_rolling_ic", "c24_rolling_ic", "c25_rolling_ic", "c26_rolling_ic"]
    panel = panel.dropna(subset=ic_cols)

    for col in ic_cols:
        panel[col] = panel[col].fillna(0)

    panel["ic_weight_sum"] = (
        panel["c23_rolling_ic"].clip(lower=0) +
        panel["c24_rolling_ic"].clip(lower=0) +
        panel["c25_rolling_ic"].clip(lower=0) +
        panel["c26_rolling_ic"].clip(lower=0)
    )
    panel["ic_weight_sum"] = panel["ic_weight_sum"].replace(0, 1)

    panel["w_c23"] = panel["c23_rolling_ic"].clip(lower=0) / panel["ic_weight_sum"]
    panel["w_c24"] = panel["c24_rolling_ic"].clip(lower=0) / panel["ic_weight_sum"]
    panel["w_c25"] = panel["c25_rolling_ic"].clip(lower=0) / panel["ic_weight_sum"]
    panel["w_c26"] = panel["c26_rolling_ic"].clip(lower=0) / panel["ic_weight_sum"]

    panel["ic_weighted_composite"] = (
        panel["w_c23"] * panel["c23"] +
        panel["w_c24"] * panel["c24"] +
        panel["w_c25"] * panel["c25"] +
        panel["w_c26"] * panel["c26"]
    )

    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("equal_weight_composite", "Equal weight C23+C24+C25+C26 / 4", family="adaptive", primary=True),
    StateSpec("ic_weighted_composite", "IC-weighted C23-C26", family="adaptive", primary=True),
    StateSpec("c23", "C23: high_illiq × vol_expansion", family="component"),
    StateSpec("c24", "C24: ceiling_count >= 2 × vol_expansion", family="component"),
    StateSpec("c25", "C25: vwap_below_10 × vol_expansion", family="component"),
    StateSpec("c26", "C26: buy_heavy × illiq × vol_expansion", family="component"),
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
    equal_weight_ic = results[results["name"] == "equal_weight_composite"]["avg_ic"].iloc[0] if not results.empty else 0
    ic_weighted_ic = results[results["name"] == "ic_weighted_composite"]["avg_ic"].iloc[0] if not results.empty else 0

    c23_ic = results[results["name"] == "c23"]["avg_ic"].iloc[0] if not results.empty else 0
    c24_ic = results[results["name"] == "c24"]["avg_ic"].iloc[0] if not results.empty else 0
    c25_ic = results[results["name"] == "c25"]["avg_ic"].iloc[0] if not results.empty else 0
    c26_ic = results[results["name"] == "c26"]["avg_ic"].iloc[0] if not results.empty else 0

    equal_weight_lift = equal_weight_ic - baseline_ic
    ic_weighted_lift = ic_weighted_ic - baseline_ic
    ic_vs_equal = ic_weighted_ic - equal_weight_ic

    if ic_vs_equal > 0.01:
        decision = "PASSED"
    elif ic_vs_equal > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "equal_weight_composite_ic": float(equal_weight_ic),
            "equal_weight_composite_lift": float(equal_weight_lift),
            "ic_weighted_composite_ic": float(ic_weighted_ic),
            "ic_weighted_composite_lift": float(ic_weighted_lift),
            "ic_vs_equal_improvement": float(ic_vs_equal),
            "c23_ic": float(c23_ic),
            "c24_ic": float(c24_ic),
            "c25_ic": float(c25_ic),
            "c26_ic": float(c26_ic),
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"Equal weight composite IC: {equal_weight_ic:.4f} (lift: {equal_weight_lift:+.4f})")
    print(f"IC-weighted composite IC: {ic_weighted_ic:.4f} (lift: {ic_weighted_lift:+.4f})")
    print(f"IC vs equal improvement: {ic_vs_equal:+.4f}")
    print(f"\nComponent ICs:")
    print(f"  C23: {c23_ic:.4f}")
    print(f"  C24: {c24_ic:.4f}")
    print(f"  C25: {c25_ic:.4f}")
    print(f"  C26: {c26_ic:.4f}")
    print(f"\nSummary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()