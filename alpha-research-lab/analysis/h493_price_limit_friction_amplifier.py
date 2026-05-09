"""
BR7: price_limit_friction_amplifier

Hypothesis: C24 (multi-day ceiling) works at IC 0.2353. But FRICTION of hitting the
limit (not just count) might matter. C24 counts hits ≥2 in 3 days. But the STABILITY
of the queue before hitting the limit might amplify or attenuate the signal.
Mechanism: stable queue (low vol variance before limit hit) = stronger accumulation,
volatile queue = weak/unstable.

First test: ceiling_2 × vol_stability (low vol variance) vs ceiling_2 × vol_volatility
(high vol variance) vs C24 baseline. Compare with C24 ceiling analog.
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


BRANCH_NAME = "price_limit_friction_amplifier"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "C24 (multi-day ceiling) works at IC 0.2353. But FRICTION of hitting the "
        "limit might matter. Stable queue (low vol variance before limit hit) = stronger "
        "accumulation, volatile queue = weak. Test ceiling × vol_stability vs vol_volatility."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BR7 price_limit_friction_amplifier test")
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
    panel["vol_expansion"] = vol_change_rank >= 0.8

    imbalance_rank = panel.groupby("time", sort=False)["buy_sell_volume_imbalance"].rank(method="average", pct=True)
    panel["buy_heavy"] = imbalance_rank >= 0.8
    panel["buy_heavy_expansion"] = panel["buy_heavy"] & panel["vol_expansion"]

    panel["at_limit"] = panel["pct_change"] >= 6.5
    panel["near_ceiling"] = (panel["pct_change"] >= 5.0) & (panel["pct_change"] <= 7.0)
    panel["limit_1_of_3"] = (
        panel.groupby("ticker")["at_limit"].transform(lambda x: x.rolling(3, min_periods=3).sum())
    )
    panel["limit_2_of_3"] = panel["limit_1_of_3"] >= 2

    panel["vol_stability"] = panel.groupby("ticker")["pct_change"].transform(
        lambda x: x.rolling(5, min_periods=3).std()
    )
    panel["vol_stability_rank"] = panel.groupby("time", sort=False)["vol_stability"].rank(method="average", pct=True)
    panel["stable_queue"] = panel["vol_stability_rank"] <= 0.2
    panel["volatile_queue"] = panel["vol_stability_rank"] >= 0.8

    panel["ceiling_2_expansion"] = panel["limit_2_of_3"] & panel["vol_expansion"]
    panel["ceiling_2_stable"] = panel["limit_2_of_3"] & panel["stable_queue"]
    panel["ceiling_2_volatile"] = panel["limit_2_of_3"] & panel["volatile_queue"]
    panel["ceiling_2_expansion_stable"] = panel["limit_2_of_3"] & panel["vol_expansion"] & panel["stable_queue"]
    panel["ceiling_2_expansion_volatile"] = panel["limit_2_of_3"] & panel["vol_expansion"] & panel["volatile_queue"]

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("limit_2_of_3", "C24: ceiling hit 2+ times in 3 days", family="ceiling"),
    StateSpec("near_ceiling", "Near ceiling (5-7% change)", family="ceiling"),
    StateSpec("ceiling_2_expansion", "C24 × Vol expansion", family="combo", primary=True),
    StateSpec("ceiling_2_stable", "Ceiling 2/3 + stable queue (low vol std)", family="friction"),
    StateSpec("ceiling_2_volatile", "Ceiling 2/3 + volatile queue (high vol std)", family="friction"),
    StateSpec("ceiling_2_expansion_stable", "Ceiling 2/3 + exp + stable queue", family="friction"),
    StateSpec("ceiling_2_expansion_volatile", "Ceiling 2/3 + exp + volatile queue", family="friction"),
    StateSpec("buy_heavy_expansion", "C20: buy_heavy × vol expansion", family="signal"),
    StateSpec("stable_queue", "Stable queue alone (low vol std)", family="volatility"),
    StateSpec("volatile_queue", "Volatile queue alone (high vol std)", family="volatility"),
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

    c24_ic = results[results["name"] == "limit_2_of_3"]["avg_ic"].iloc[0] if not results.empty else 0
    c24_lift = c24_ic - baseline_ic

    c24_exp_ic = results[results["name"] == "ceiling_2_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    c24_exp_lift = c24_exp_ic - baseline_ic

    stable_ic = results[results["name"] == "ceiling_2_stable"]["avg_ic"].iloc[0] if not results.empty else 0
    volatile_ic = results[results["name"] == "ceiling_2_volatile"]["avg_ic"].iloc[0] if not results.empty else 0
    stable_lift = stable_ic - baseline_ic
    volatile_lift = volatile_ic - baseline_ic

    c24_exp_stable_ic = results[results["name"] == "ceiling_2_expansion_stable"]["avg_ic"].iloc[0] if not results.empty else 0
    c24_exp_volatile_ic = results[results["name"] == "ceiling_2_expansion_volatile"]["avg_ic"].iloc[0] if not results.empty else 0
    c24_exp_stable_lift = c24_exp_stable_ic - baseline_ic
    c24_exp_volatile_lift = c24_exp_volatile_ic - baseline_ic

    c20_ic = results[results["name"] == "buy_heavy_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    c20_lift = c20_ic - baseline_ic

    stable_alone_ic = results[results["name"] == "stable_queue"]["avg_ic"].iloc[0] if not results.empty else 0
    volatile_alone_ic = results[results["name"] == "volatile_queue"]["avg_ic"].iloc[0] if not results.empty else 0

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    friction_lift = stable_lift - volatile_lift
    triple_stable_lift = c24_exp_stable_lift - c24_exp_lift

    if c24_exp_stable_lift > c24_exp_lift + 0.01:
        decision = "PASSED"
    elif friction_lift > 0.01:
        decision = "MIXED"
    elif c24_exp_stable_lift > c24_lift + 0.01:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "c24_ic": float(c24_ic),
            "c24_lift": float(c24_lift),
            "c24_exp_ic": float(c24_exp_ic),
            "c24_exp_lift": float(c24_exp_lift),
            "ceiling_2_stable_ic": float(stable_ic),
            "ceiling_2_stable_lift": float(stable_lift),
            "ceiling_2_volatile_ic": float(volatile_ic),
            "ceiling_2_volatile_lift": float(volatile_lift),
            "ceiling_2_expansion_stable_ic": float(c24_exp_stable_ic),
            "ceiling_2_expansion_stable_lift": float(c24_exp_stable_lift),
            "ceiling_2_expansion_volatile_ic": float(c24_exp_volatile_ic),
            "ceiling_2_expansion_volatile_lift": float(c24_exp_volatile_lift),
            "friction_lift": float(friction_lift),
            "triple_stable_lift": float(triple_stable_lift),
            "c20_ic": float(c20_ic),
            "c20_lift": float(c20_lift),
            "stable_alone_ic": float(stable_alone_ic),
            "volatile_alone_ic": float(volatile_alone_ic),
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
    print(f"C24 (ceiling 2/3): IC={c24_ic:.4f}, lift={c24_lift:+.4f}")
    print(f"C24 × exp: IC={c24_exp_ic:.4f}, lift={c24_exp_lift:+.4f}")
    print(f"\nFriction × C24:")
    print(f"  stable: IC={stable_ic:.4f}, lift={stable_lift:+.4f}")
    print(f"  volatile: IC={volatile_ic:.4f}, lift={volatile_lift:+.4f}")
    print(f"  friction_lift: {friction_lift:+.4f}")
    print(f"\nFriction × C24 × exp:")
    print(f"  exp+stable: IC={c24_exp_stable_ic:.4f}, lift={c24_exp_stable_lift:+.4f}")
    print(f"  exp+volatile: IC={c24_exp_volatile_ic:.4f}, lift={c24_exp_volatile_lift:+.4f}")
    print(f"  triple_stable_lift: {triple_stable_lift:+.4f}")
    print(f"\nVolatility alone:")
    print(f"  stable_queue: IC={stable_alone_ic:.4f}")
    print(f"  volatile_queue: IC={volatile_alone_ic:.4f}")
    print(f"\nSummary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
