"""
BR6: spread_as_new_dimension

Hypothesis: C23 uses Amihud illiq, C25 uses VWAP deviation. Bid-ask spread is an
INDEPENDENT liquidity dimension not yet tested. Spread × vol_expansion might
capture a different regime angle than illiq × vol_expansion.
Mechanism: spread measures transaction cost / market maker willingness, different from volume.

First test: spread (avg_buy_size / avg_sell_size ratio) × vol_expansion vs random baseline.
Compare: spread × vol_expansion vs illiq × vol_expansion (C23) controls.
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


BRANCH_NAME = "spread_as_new_dimension"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "C23 uses Amihud illiq, C25 uses VWAP deviation. Bid-ask spread is an "
        "INDEPENDENT liquidity dimension not yet tested. Spread × vol_expansion might "
        "capture a different regime angle than illiq × vol_expansion. "
        "Mechanism: spread measures transaction cost / market maker willingness."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BR6 spread_as_new_dimension test")
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
    order_stats["avg_buy_size"] = order_stats["buy_order_volume"] / (order_stats["buy_order_count"] + 1)
    order_stats["avg_sell_size"] = order_stats["sell_order_volume"] / (order_stats["sell_order_count"] + 1)
    order_stats["spread_ratio"] = order_stats["avg_buy_size"] / (order_stats["avg_sell_size"] + 1)
    order_stats["buy_volume"] = order_stats["buy_order_volume"]
    order_stats["sell_volume"] = order_stats["sell_order_volume"]
    order_stats["buy_sell_volume_imbalance"] = (
        (order_stats["buy_volume"] - order_stats["sell_volume"]) /
        (order_stats["buy_volume"] + order_stats["sell_volume"] + 1)
    )

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume", "spread_ratio", "buy_sell_volume_imbalance"]],
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

    spread_rank = panel.groupby("time", sort=False)["spread_ratio"].rank(method="average", pct=True)
    panel["wide_spread"] = spread_rank >= 0.8
    panel["tight_spread"] = spread_rank <= 0.2
    panel["wide_spread_expansion"] = panel["wide_spread"] & panel["vol_expansion"]
    panel["tight_spread_expansion"] = panel["tight_spread"] & panel["vol_expansion"]

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("wide_spread", "Wide spread (top 20% ratio)", family="spread"),
    StateSpec("tight_spread", "Tight spread (bottom 20% ratio)", family="spread"),
    StateSpec("vol_expansion", "Vol expansion (top 20%)", family="vol"),
    StateSpec("buy_heavy_expansion", "C20: buy_heavy × vol expansion", family="signal"),
    StateSpec("wide_spread_expansion", "Wide spread × Vol expansion", family="combo", primary=True),
    StateSpec("tight_spread_expansion", "Tight spread × Vol expansion", family="combo"),
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

    wide_spread_ic = results[results["name"] == "wide_spread"]["avg_ic"].iloc[0] if not results.empty else 0
    wide_spread_lift = wide_spread_ic - baseline_ic

    wide_spread_exp_ic = results[results["name"] == "wide_spread_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    wide_spread_exp_lift = wide_spread_exp_ic - baseline_ic

    tight_spread_exp_ic = results[results["name"] == "tight_spread_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    tight_spread_exp_lift = tight_spread_exp_ic - baseline_ic

    c20_ic = results[results["name"] == "buy_heavy_expansion"]["avg_ic"].iloc[0] if not results.empty else 0
    c20_lift = c20_ic - baseline_ic

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    spread_exp_vs_vol_exp = wide_spread_exp_ic - results[results["name"] == "vol_expansion"]["avg_ic"].iloc[0]

    if wide_spread_exp_lift > c20_lift + 0.005:
        decision = "PASSED"
    elif wide_spread_exp_lift > 0.01:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "wide_spread_ic": float(wide_spread_ic),
            "wide_spread_lift": float(wide_spread_lift),
            "wide_spread_expansion_ic": float(wide_spread_exp_ic),
            "wide_spread_expansion_lift": float(wide_spread_exp_lift),
            "tight_spread_expansion_ic": float(tight_spread_exp_ic),
            "tight_spread_expansion_lift": float(tight_spread_exp_lift),
            "c20_ic": float(c20_ic),
            "c20_lift": float(c20_lift),
            "spread_exp_vs_vol_exp": float(spread_exp_vs_vol_exp),
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
    print(f"\nSpread alone:")
    print(f"  wide_spread: IC={wide_spread_ic:.4f}, lift={wide_spread_lift:+.4f}")
    print(f"  tight_spread: IC={results[results['name']=='tight_spread']['avg_ic'].iloc[0]:.4f}")
    print(f"\nSpread × Vol expansion:")
    print(f"  wide_spread_expansion: IC={wide_spread_exp_ic:.4f}, lift={wide_spread_exp_lift:+.4f}")
    print(f"  tight_spread_expansion: IC={tight_spread_exp_ic:.4f}, lift={tight_spread_exp_lift:+.4f}")
    print(f"\nC20 reference: IC={c20_ic:.4f}, lift={c20_lift:+.4f}")
    print(f"\nSpread × vol vs vol alone: {spread_exp_vs_vol_exp:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()
