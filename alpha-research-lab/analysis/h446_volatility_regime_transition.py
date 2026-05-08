"""
H446: volatility_regime_transition

Hypothesis: Volatility expansion vs contraction is a different state than static 
high/low vol. Connection: H411 tested volume levels, but volatility TRANSITION 
not tested. First test: compute vol_z 5d change (vol expansion vs contraction 
buckets), test forward IC against random baseline.

Data: Uses order_stats price_change_raw to compute volatility proxy.
Compare with: Random baseline (not S1/C16 as this is not a variation of those).
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


BRANCH_NAME = "volatility_regime_transition"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "Volatility expansion vs contraction is a different state than static "
        "high/low vol. Compute 5d vol change, bucket into expansion/contraction, "
        "test forward IC vs random baseline."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H446 volatility regime transition test")
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
    
    def parse_price_change(s):
        if pd.isna(s):
            return np.nan
        try:
            import re
            match = re.search(r'\(\s*([+-]?[\d,]+)\s*%\)', str(s))
            if match:
                return float(match.group(1).replace(',', '.'))
            return np.nan
        except:
            return np.nan
    
    order_stats["pct_change"] = order_stats["price_change_raw"].apply(parse_price_change)
    
    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change", "buy_order_volume", "sell_order_volume"]],
        on=["time", "ticker"],
        how="left",
    )
    
    panel["all_rows"] = True
    
    panel = panel.sort_values(["ticker", "time"])
    
    for col in ["pct_change", "buy_order_volume", "sell_order_volume"]:
        panel[f"{col}_vol"] = panel.groupby("ticker")[col].transform(
            lambda x: x.rolling(window=5, min_periods=3).std()
        )
    
    panel["vol_change"] = panel.groupby("ticker")["pct_change_vol"].transform(
        lambda x: x.diff()
    )
    
    panel = panel.dropna(subset=["vol_change"])
    
    vol_change_rank = panel.groupby("time", sort=False)["vol_change"].rank(method="average", pct=True)
    panel["vol_expansion"] = vol_change_rank >= 0.8
    panel["vol_contraction"] = vol_change_rank <= 0.2
    panel["vol_stable"] = ~panel["vol_expansion"] & ~panel["vol_contraction"]
    
    panel["vol_expansion_q5"] = vol_change_rank >= 0.8
    panel["vol_contraction_q1"] = vol_change_rank <= 0.2
    
    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("vol_expansion", "Volatility expanding (top 20% 5d vol change)", family="vol_regime"),
    StateSpec("vol_contraction", "Volatility contracting (bottom 20% 5d vol change)", family="vol_regime"),
    StateSpec("vol_stable", "Volatility stable (middle 60%)", family="vol_regime"),
    StateSpec("vol_expansion_q5", "Volatility expansion top quintile", family="vol_regime"),
    StateSpec("vol_contraction_q1", "Volatility contraction bottom quintile", family="vol_regime"),
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
    
    expansion_row = results[results["name"] == "vol_expansion"]
    contraction_row = results[results["name"] == "vol_contraction"]
    
    expansion_lift = (expansion_row["avg_ic"].iloc[0] - baseline_ic) if not expansion_row.empty else 0
    contraction_lift = (contraction_row["avg_ic"].iloc[0] - baseline_ic) if not contraction_row.empty else 0
    
    if expansion_lift > 0.005 and contraction_lift < -0.005:
        decision = "PASSED"
    elif expansion_lift < -0.005 and contraction_lift > 0.005:
        decision = "PASSED"
    elif abs(expansion_lift) < 0.003 and abs(contraction_lift) < 0.003:
        decision = "FAILED"
    else:
        decision = "MIXED"
    
    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "expansion_ic": float(expansion_row["avg_ic"].iloc[0]) if not expansion_row.empty else None,
            "contraction_ic": float(contraction_row["avg_ic"].iloc[0]) if not contraction_row.empty else None,
            "expansion_lift": float(expansion_lift),
            "contraction_lift": float(contraction_lift),
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
    print(f"Expansion lift: {expansion_lift:+.4f}")
    print(f"Contraction lift: {contraction_lift:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()