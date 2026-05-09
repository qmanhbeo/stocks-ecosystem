"""
BR2: vol_expansion_degree_continuous

Hypothesis: vol_expansion is binary (top 20%), never tested CONTINUOUS.
H481 showed breadth is MONOTONIC not discrete. Vol expansion degree likely similar.
Test vol percentile (10/20/30/40/50%) for C23/C24/C26.
Different signals may prefer different vol thresholds. Mechanism: regime strength is continuous.

First test: vol_expansion percentile buckets (10/20/30/40/50%) × C23 signal vs forward IC.
Compare with binary top 20% baseline and random baseline.
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


BRANCH_NAME = "vol_expansion_degree_continuous"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "vol_expansion is binary (top 20%), never tested CONTINUOUS. "
        "H481 showed breadth is MONOTONIC not discrete. Vol expansion degree likely similar. "
        "Test vol percentile (10/20/30/40/50%) for C23/C24/C26. "
        "Different signals may prefer different vol thresholds. Mechanism: regime strength is continuous."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BR2 vol_expansion_degree_continuous test")
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
    order_stats["buy_volume"] = order_stats["buy_order_volume"]
    order_stats["sell_volume"] = order_stats["sell_order_volume"]
    order_stats["buy_sell_volume_imbalance"] = (
        (order_stats["buy_volume"] - order_stats["sell_volume"]) /
        (order_stats["buy_volume"] + order_stats["sell_volume"] + 1)
    )

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume", "buy_sell_volume_imbalance"]],
        on=["time", "ticker"],
        how="left",
    )

    panel["all_rows"] = True
    panel = panel.dropna(subset=["pct_change", "total_volume"])
    panel = panel[panel["total_volume"] > 0]
    panel = panel.sort_values(["ticker", "time"])

    panel["pct_change_vol"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(window=5, min_periods=3).std()
    )
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )
    panel = panel.dropna(subset=["vol_change"])

    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion_binary"] = vol_change_rank >= 0.8

    for pct in [10, 20, 30, 40, 50]:
        panel[f"vol_percentile_{pct}"] = vol_change_rank >= (pct / 100.0)

    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_volume_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = imbalance_rank >= 0.8
    panel["buy_heavy_expansion_binary"] = panel["buy_heavy"] & panel["vol_expansion_binary"]

    panel["near_ceiling"] = (panel["pct_change"] >= 5.0) & (panel["pct_change"] <= 7.0)
    panel["at_limit"] = panel["pct_change"] >= 6.5
    panel["limit_1_of_3"] = (
        panel.groupby("ticker")["at_limit"].transform(lambda x: x.rolling(3, min_periods=3).sum())
    )
    panel["limit_2_of_3"] = panel["limit_1_of_3"] >= 2
    panel["ceiling_2_expansion_binary"] = panel["limit_2_of_3"] & panel["vol_expansion_binary"]

    for pct in [10, 20, 30, 40, 50]:
        panel[f"buy_heavy_expansion_{pct}"] = panel["buy_heavy"] & panel[f"vol_percentile_{pct}"]
        panel[f"ceiling_2_expansion_{pct}"] = panel["limit_2_of_3"] & panel[f"vol_percentile_{pct}"]

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("vol_expansion_binary", "Vol expansion binary (top 20%)", family="vol_regime"),
    StateSpec("vol_percentile_10", "Vol expansion top 10%", family="vol_degree"),
    StateSpec("vol_percentile_20", "Vol expansion top 20%", family="vol_degree"),
    StateSpec("vol_percentile_30", "Vol expansion top 30%", family="vol_degree"),
    StateSpec("vol_percentile_40", "Vol expansion top 40%", family="vol_degree"),
    StateSpec("vol_percentile_50", "Vol expansion top 50%", family="vol_degree"),
    StateSpec("buy_heavy_expansion_binary", "H451: Buy-heavy + binary expansion", family="signal_regime"),
    StateSpec("buy_heavy_expansion_20", "Buy-heavy + top 20% vol", family="signal_regime"),
    StateSpec("buy_heavy_expansion_30", "Buy-heavy + top 30% vol", family="signal_regime"),
    StateSpec("buy_heavy_expansion_40", "Buy-heavy + top 40% vol", family="signal_regime"),
    StateSpec("ceiling_2_expansion_binary", "C24: Ceiling 2/3 + binary expansion", family="signal_regime"),
    StateSpec("ceiling_2_expansion_20", "C24: Ceiling 2/3 + top 20% vol", family="signal_regime"),
    StateSpec("ceiling_2_expansion_30", "C24: Ceiling 2/3 + top 30% vol", family="signal_regime"),
    StateSpec("ceiling_2_expansion_40", "C24: Ceiling 2/3 + top 40% vol", family="signal_regime"),
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

    binary_ic = results[results["name"] == "vol_expansion_binary"]["avg_ic"].iloc[0] if not results.empty else 0
    binary_lift = binary_ic - baseline_ic

    vol_pct_results = {}
    for pct in [10, 20, 30, 40, 50]:
        row = results[results["name"] == f"vol_percentile_{pct}"]
        if not row.empty:
            vol_pct_results[pct] = {
                "ic": row["avg_ic"].iloc[0],
                "lift": row["avg_ic"].iloc[0] - baseline_ic,
                "rows": row["pooled_rows"].iloc[0],
                "pos_years": row["positive_years"].iloc[0],
                "years": row["years"].iloc[0],
            }

    buy_exp_results = {}
    for pct in [20, 30, 40]:
        row = results[results["name"] == f"buy_heavy_expansion_{pct}"]
        if not row.empty:
            buy_exp_results[pct] = {
                "ic": row["avg_ic"].iloc[0],
                "lift": row["avg_ic"].iloc[0] - baseline_ic,
                "rows": row["pooled_rows"].iloc[0],
            }

    ceiling_exp_results = {}
    for pct in [20, 30, 40]:
        row = results[results["name"] == f"ceiling_2_expansion_{pct}"]
        if not row.empty:
            ceiling_exp_results[pct] = {
                "ic": row["avg_ic"].iloc[0],
                "lift": row["avg_ic"].iloc[0] - baseline_ic,
                "rows": row["pooled_rows"].iloc[0],
            }

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    vol_vals = [vol_pct_results[p]["ic"] for p in [10, 20, 30, 40, 50] if p in vol_pct_results]
    monotonic = all(vol_vals[i] <= vol_vals[i+1] for i in range(len(vol_vals)-1)) or \
               all(vol_vals[i] >= vol_vals[i+1] for i in range(len(vol_vals)-1))

    best_vol_pct = max(vol_pct_results.keys(), key=lambda p: vol_pct_results[p]["ic"])
    best_vol_lift = vol_pct_results[best_vol_pct]["lift"]
    best_signal_lift = max(
        max(buy_exp_results.values(), key=lambda x: x["ic"], default={"ic": 0})["ic"],
        max(ceiling_exp_results.values(), key=lambda x: x["ic"], default={"ic": 0})["ic"]
    ) - baseline_ic

    if best_vol_lift > 0.01 and (monotonic or best_vol_lift > binary_lift):
        decision = "PASSED"
    elif best_vol_lift > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "binary_lift": float(binary_lift),
            "best_vol_pct": int(best_vol_pct),
            "best_vol_lift": float(best_vol_lift),
            "best_signal_lift": float(best_signal_lift),
            "vol_pct_ics": {str(p): float(vol_pct_results[p]["ic"]) for p in vol_pct_results},
            "vol_pct_lifts": {str(p): float(vol_pct_results[p]["lift"]) for p in vol_pct_results},
            "monotonic": monotonic,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
        },
        artifacts={
            "results": str(results_path),
            "yearly": str(yearly_path),
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"Binary (top 20%): IC={binary_ic:.4f}, lift={binary_lift:+.4f}")
    print(f"\nVol percentile by degree:")
    for pct in [10, 20, 30, 40, 50]:
        if pct in vol_pct_results:
            v = vol_pct_results[pct]
            print(f"  top {pct}%: IC={v['ic']:.4f}, lift={v['lift']:+.4f}, rows={v['rows']}, pos_years={v['pos_years']}/{v['years']}")
    print(f"\nBuy-heavy expansion by degree:")
    for pct in [20, 30, 40]:
        if pct in buy_exp_results:
            v = buy_exp_results[pct]
            print(f"  top {pct}%: IC={v['ic']:.4f}, lift={v['lift']:+.4f}, rows={v['rows']}")
    print(f"\nCeiling 2 expansion by degree:")
    for pct in [20, 30, 40]:
        if pct in ceiling_exp_results:
            v = ceiling_exp_results[pct]
            print(f"  top {pct}%: IC={v['ic']:.4f}, lift={v['lift']:+.4f}, rows={v['rows']}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
