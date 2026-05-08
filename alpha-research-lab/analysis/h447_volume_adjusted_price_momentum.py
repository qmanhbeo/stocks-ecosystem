"""
H447: volume_adjusted_price_momentum

Hypothesis: Price normalized by volume captures "expensive" vs "cheap" moves.
Same return on higher volume = real force (real demand), 
same return on lower volume = fade (crowd blowoff).

First test: return / volume-z buckets for forward IC.
Compare with: Random baseline (not S1/C16 variation).

Data: Uses order_stats pct_change (parsed from price_change_raw) and volume.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import pandas as pd
import numpy as np
import re

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


BRANCH_NAME = "volume_adjusted_price_momentum"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Price normalized by volume captures 'expensive' vs 'cheap' moves. "
        "Same return on higher volume = real force (real demand), "
        "same return on lower volume = fade (crowd blowoff). "
        "Test return / volume-z buckets for forward IC vs random baseline."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H447 volume-adjusted price momentum test")
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
    
    order_stats["pct_change"] = order_stats["price_change_raw"].apply(parse_price_change)
    order_stats["total_volume"] = order_stats["buy_order_volume"] + order_stats["sell_order_volume"]
    
    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "total_volume", "buy_order_volume", "sell_order_volume"]],
        on=["time", "ticker"],
        how="left",
    )
    
    panel["all_rows"] = True
    
    panel = panel.dropna(subset=["pct_change", "total_volume"])
    
    panel = panel[panel["total_volume"] > 0]
    
    panel["volume_z"] = panel.groupby("time", sort=False)["total_volume"].transform(
        lambda x: (x - x.mean()) / x.std()
    )
    
    panel["return_per_volume"] = panel["pct_change"] / (panel["volume_z"].abs() + 0.1)
    
    return_rank = panel.groupby("time", sort=False)["pct_change"].rank(method="average", pct=True)
    volume_rank = panel.groupby("time", sort=False)["total_volume"].rank(method="average", pct=True)
    
    panel["high_return_high_vol"] = (return_rank >= 0.7) & (volume_rank >= 0.7)
    panel["high_return_low_vol"] = (return_rank >= 0.7) & (volume_rank <= 0.3)
    panel["low_return_high_vol"] = (return_rank <= 0.3) & (volume_rank >= 0.7)
    panel["low_return_low_vol"] = (return_rank <= 0.3) & (volume_rank <= 0.3)
    
    panel["expensive_move"] = panel["return_per_volume"] >= panel.groupby("time")["return_per_volume"].transform(
        lambda x: x.quantile(0.8)
    )
    panel["cheap_move"] = panel["return_per_volume"] <= panel.groupby("time")["return_per_volume"].transform(
        lambda x: x.quantile(0.2)
    )
    
    panel["real_force"] = panel["high_return_high_vol"]
    panel["fade_move"] = panel["high_return_low_vol"]
    
    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("high_return_high_vol", "High return + High volume (real force)", family="vol_adj"),
    StateSpec("high_return_low_vol", "High return + Low volume (expensive move)", family="vol_adj"),
    StateSpec("low_return_high_vol", "Low return + High volume", family="vol_adj"),
    StateSpec("low_return_low_vol", "Low return + Low volume", family="vol_adj"),
    StateSpec("expensive_move", "Return/volume in top 20% (expensive)", family="vol_adj"),
    StateSpec("cheap_move", "Return/volume in bottom 20% (cheap)", family="vol_adj"),
    StateSpec("real_force", "High return + High volume", family="vol_adj"),
    StateSpec("fade_move", "High return + Low volume", family="vol_adj"),
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

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}
    
    baseline_ic = results[results["name"] == "all_rows"]["avg_ic"].iloc[0] if not results.empty else 0
    
    real_force_row = results[results["name"] == "real_force"]
    fade_move_row = results[results["name"] == "fade_move"]
    expensive_row = results[results["name"] == "expensive_move"]
    cheap_row = results[results["name"] == "cheap_move"]
    
    real_force_lift = (real_force_row["avg_ic"].iloc[0] - baseline_ic) if not real_force_row.empty and real_force_row["avg_ic"].notna().any() else 0
    fade_move_lift = (fade_move_row["avg_ic"].iloc[0] - baseline_ic) if not fade_move_row.empty and fade_move_row["avg_ic"].notna().any() else 0
    expensive_lift = (expensive_row["avg_ic"].iloc[0] - baseline_ic) if not expensive_row.empty and expensive_row["avg_ic"].notna().any() else 0
    cheap_lift = (cheap_row["avg_ic"].iloc[0] - baseline_ic) if not cheap_row.empty and cheap_row["avg_ic"].notna().any() else 0
    
    if real_force_lift > 0.005 and fade_move_lift < -0.005:
        decision = "PASSED"
    elif expensive_lift > 0.005 and cheap_lift < -0.005:
        decision = "PASSED"
    elif abs(real_force_lift) < 0.003 and abs(fade_move_lift) < 0.003:
        decision = "FAILED"
    else:
        decision = "MIXED"
    
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "real_force_ic": float(real_force_row["avg_ic"].iloc[0]) if not real_force_row.empty and real_force_row["avg_ic"].notna().any() else None,
            "fade_move_ic": float(fade_move_row["avg_ic"].iloc[0]) if not fade_move_row.empty and fade_move_row["avg_ic"].notna().any() else None,
            "real_force_lift": float(real_force_lift),
            "fade_move_lift": float(fade_move_lift),
            "expensive_lift": float(expensive_lift),
            "cheap_lift": float(cheap_lift),
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
    print(f"Real force lift: {real_force_lift:+.4f}")
    print(f"Fade move lift: {fade_move_lift:+.4f}")
    print(f"Expensive move lift: {expensive_lift:+.4f}")
    print(f"Cheap move lift: {cheap_lift:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()