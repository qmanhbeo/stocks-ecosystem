"""
H462: activation_rate_hidden_signal

Hypothesis: H388/H395 tested panel membership (fresh vs stale), not VELOCITY of activation.
A stock suddenly appearing vs gradual entry might signal different information.
Test: rank_change speed × vol_expansion vs forward IC.

First test: compute cross-sectional rank of xs_proba, compute rank delta (acceleration),
test high rank acceleration vs low in vol_expansion.
Compare with: Random baseline.

Data: Uses S1 xs_proba from decision panel.
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


BRANCH_NAME = "activation_rate_hidden_signal"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H388/H395 tested membership (fresh vs stale), not VELOCITY of activation. "
        "A stock suddenly appearing might signal different info than gradual entry. "
        "Test rank_change speed × vol_expansion vs forward IC."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H462 activation_rate_hidden_signal test")
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
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume"]],
        on=["time", "ticker"],
        how="left",
    )

    panel["all_rows"] = True

    panel = panel.dropna(subset=["pct_change", "total_volume"])
    panel = panel[panel["total_volume"] > 0]

    panel = panel.sort_values(["ticker", "time"])

    # Compute vol regime from order_stats
    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )

    # Compute cross-sectional rank of s1_xs_proba
    panel["xs_proba_rank"] = panel.groupby("time", sort=False)[S1_SCORE_COL].rank(method="average", pct=True)

    # Compute rank change (velocity of activation) - key new feature
    panel["rank_lag1"] = panel.groupby("ticker")["xs_proba_rank"].shift(1)
    panel["rank_lag2"] = panel.groupby("ticker")["xs_proba_rank"].shift(2)
    panel["rank_delta"] = panel["xs_proba_rank"] - panel["rank_lag1"]
    panel["rank_delta_2d"] = panel["xs_proba_rank"] - panel["rank_lag2"]

    # Acceleration of rank change
    panel["rank_accel"] = panel["rank_delta"] - (panel["rank_lag1"] - panel["rank_lag2"])

    panel = panel.dropna(subset=["vol_change", "rank_delta", "rank_delta_2d"])

    # Vol regime
    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8

    # Rank change quintiles
    rank_delta_rank = panel.groupby("time", sort=False)["rank_delta"].rank(method="average", pct=True)
    panel["rank_accelerating"] = rank_delta_rank >= 0.8  # Improving rank fast
    panel["rank_decelerating"] = rank_delta_rank <= 0.2  # Declining rank fast
    panel["rank_stable"] = (rank_delta_rank > 0.3) & (rank_delta_rank < 0.7)

    # Absolute rank quintiles
    abs_rank = panel.groupby("time", sort=False)["xs_proba_rank"].rank(method="average", pct=True)
    panel["high_rank"] = abs_rank >= 0.8
    panel["low_rank"] = abs_rank <= 0.2

    # Combos
    panel["rank_accel_expansion"] = panel["rank_accelerating"] & panel["vol_expansion"]
    panel["rank_decel_expansion"] = panel["rank_decelerating"] & panel["vol_expansion"]
    panel["high_rank_expansion"] = panel["high_rank"] & panel["vol_expansion"]
    panel["high_rank_expansion_accel"] = panel["high_rank"] & panel["rank_accelerating"] & panel["vol_expansion"]
    panel["low_rank_expansion"] = panel["low_rank"] & panel["vol_expansion"]
    panel["low_rank_expansion_decel"] = panel["low_rank"] & panel["rank_decelerating"] & panel["vol_expansion"]

    # Cross signal: rank_delta × existing signals
    order_stats2 = pd.read_parquet(args.order_stats_path)
    order_stats2 = order_stats2.rename(columns={"date": "time"})
    order_stats2["time"] = pd.to_datetime(order_stats2["time"])
    order_stats2 = order_stats2[order_stats2["time"].dt.year <= 2025]
    order_stats2["buy_sell_volume_imbalance"] = (
        (order_stats2["buy_order_volume"] - order_stats2["sell_order_volume"]) /
        (order_stats2["buy_order_volume"] + order_stats2["sell_order_volume"] + 1)
    )

    panel = panel.merge(
        order_stats2[["time", "ticker", "buy_sell_volume_imbalance"]],
        on=["time", "ticker"],
        how="left",
    )
    panel = panel.dropna(subset=["buy_sell_volume_imbalance"])

    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_volume_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = imbalance_rank >= 0.8
    panel["sell_heavy"] = imbalance_rank <= 0.2
    panel["buy_heavy_expansion"] = panel["buy_heavy"] & panel["vol_expansion"]

    # Rank acceleration × buy_heavy_expansion (cross of two signal families)
    panel["rank_accel_buy_expansion"] = panel["rank_accelerating"] & panel["buy_heavy_expansion"]
    panel["rank_decel_buy_expansion"] = panel["rank_decelerating"] & panel["buy_heavy_expansion"]
    panel["rank_accel_sell_expansion"] = panel["rank_accelerating"] & panel["sell_heavy"] & panel["vol_expansion"]

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    # Rank change alone
    StateSpec("rank_accelerating", "Rank accelerating (top 20% delta)", family="rank_change"),
    StateSpec("rank_decelerating", "Rank decelerating (bottom 20% delta)", family="rank_change"),
    StateSpec("rank_stable", "Rank stable (40-60%)", family="rank_change"),
    # Rank × vol regime
    StateSpec("rank_accel_expansion", "Rank accel + Vol expansion", family="rank_vol"),
    StateSpec("rank_decel_expansion", "Rank decel + Vol expansion", family="rank_vol"),
    StateSpec("high_rank_expansion", "High rank + Vol expansion", family="rank_vol"),
    StateSpec("low_rank_expansion", "Low rank + Vol expansion", family="rank_vol"),
    # Cross signal: rank_change × imbalance
    StateSpec("buy_heavy_expansion", "H451: Buy-heavy + Vol expansion", family="imbalance"),
    StateSpec("rank_accel_buy_expansion", "Rank accel + Buy-heavy + Vol expansion", family="cross", primary=True),
    StateSpec("rank_decel_buy_expansion", "Rank decel + Buy-heavy + Vol expansion", family="cross"),
    StateSpec("rank_accel_sell_expansion", "Rank accel + Sell-heavy + Vol expansion", family="cross"),
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

    # Rank change alone
    rank_accel_ic = results[results["name"] == "rank_accelerating"]["avg_ic"].iloc[0] if not results.empty else 0
    rank_decel_ic = results[results["name"] == "rank_decelerating"]["avg_ic"].iloc[0] if not results.empty else 0
    rank_stable_ic = results[results["name"] == "rank_stable"]["avg_ic"].iloc[0] if not results.empty else 0
    rank_accel_lift = rank_accel_ic - baseline_ic
    rank_decel_lift = rank_decel_ic - baseline_ic

    # Rank × vol
    rank_accel_exp_ic = results[results["name"] == "rank_accel_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    rank_decel_exp_ic = results[results["name"] == "rank_decel_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    high_rank_exp_ic = results[results["name"] == "high_rank_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    low_rank_exp_ic = results[results["name"] == "low_rank_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    rank_accel_exp_lift = rank_accel_exp_ic - baseline_ic
    rank_decel_exp_lift = rank_decel_exp_ic - baseline_ic

    # Cross signals
    buy_exp_ic = results[results["name"] == "buy_heavy_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    rank_accel_buy_ic = results[results["name"] == "rank_accel_buy_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    rank_decel_buy_ic = results[results["name"] == "rank_decel_buy_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    rank_accel_sell_ic = results[results["name"] == "rank_accel_sell_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    rank_accel_buy_lift = rank_accel_buy_ic - baseline_ic
    buy_exp_lift = buy_exp_ic - baseline_ic

    # Comparison
    rank_accel_vs_baseline_improvement = rank_accel_buy_lift - buy_exp_lift

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    # Hypothesis: rank acceleration improves signals
    if rank_accel_buy_lift > buy_exp_lift + 0.005 and rank_accel_lift > 0.005:
        decision = "PASSED"
    elif rank_accel_lift > 0.01 or rank_decel_lift > 0.01:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            # Rank change alone
            "rank_accelerating_ic": float(rank_accel_ic),
            "rank_decelerating_ic": float(rank_decel_ic),
            "rank_stable_ic": float(rank_stable_ic),
            "rank_accelerating_lift": float(rank_accel_lift),
            "rank_decelerating_lift": float(rank_decel_lift),
            # Rank × vol
            "rank_accel_expansion_ic": float(rank_accel_exp_ic),
            "rank_decel_expansion_ic": float(rank_decel_exp_ic),
            "high_rank_expansion_ic": float(high_rank_exp_ic),
            "low_rank_expansion_ic": float(low_rank_exp_ic),
            "rank_accel_expansion_lift": float(rank_accel_exp_lift),
            "rank_decel_expansion_lift": float(rank_decel_exp_lift),
            # Cross signals
            "buy_heavy_expansion_ic": float(buy_exp_ic),
            "rank_accel_buy_expansion_ic": float(rank_accel_buy_ic),
            "rank_decel_buy_expansion_ic": float(rank_decel_buy_ic),
            "rank_accel_sell_expansion_ic": float(rank_accel_sell_ic),
            "rank_accel_buy_expansion_lift": float(rank_accel_buy_lift),
            "buy_heavy_expansion_lift": float(buy_exp_lift),
            # Comparison
            "rank_accel_vs_buy_improvement": float(rank_accel_vs_baseline_improvement),
            "best_state_by_avg_year_ic": best_row.get("name"),
            "best_avg_year_ic": best_row.get("avg_ic"),
            "best_positive_years": best_row.get("positive_years"),
            "best_years": best_row.get("years"),
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
    print(f"\nRank change alone:")
    print(f"  rank_accelerating: {rank_accel_ic:.4f} (lift: {rank_accel_lift:+.4f})")
    print(f"  rank_decelerating: {rank_decel_ic:.4f} (lift: {rank_decel_lift:+.4f})")
    print(f"  rank_stable: {rank_stable_ic:.4f}")
    print(f"\nRank × Vol expansion:")
    print(f"  rank_accel_expansion: {rank_accel_exp_ic:.4f} (lift: {rank_accel_exp_lift:+.4f})")
    print(f"  rank_decel_expansion: {rank_decel_exp_ic:.4f} (lift: {rank_decel_exp_lift:+.4f})")
    print(f"  high_rank_expansion: {high_rank_exp_ic:.4f}")
    print(f"  low_rank_expansion: {low_rank_exp_ic:.4f}")
    print(f"\nCross signals:")
    print(f"  buy_heavy_expansion (baseline): {buy_exp_ic:.4f} (lift: {buy_exp_lift:+.4f})")
    print(f"  rank_accel_buy_expansion: {rank_accel_buy_ic:.4f} (lift: {rank_accel_buy_lift:+.4f})")
    print(f"  rank_decel_buy_expansion: {rank_decel_buy_ic:.4f}")
    print(f"  rank_accel_sell_expansion: {rank_accel_sell_ic:.4f}")
    print(f"\nImprovement:")
    print(f"  rank_accel_buy vs buy_heavy_expansion: {rank_accel_vs_baseline_improvement:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()