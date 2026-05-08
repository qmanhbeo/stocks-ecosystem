"""
H466: crowd_exhaustion_reversal

Hypothesis: H445 showed exhaustion (high repeat + high attention) is WORST
at -0.0474 IC lift. After exhaustion, mean-reversion might kick in.
Test: day AFTER exhaustion state vs baseline. Also test "recovery day"
patterns.

Connection: H447 showed low_return_low_vol (contrarian) is STRONGEST.
H445 showed high repeat + high attention = worst. The REVERSAL of the
worst state might be the best opportunity.

First test: next-day IC following exhaustion state vs random.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import sys
from pathlib import Path

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


BRANCH_NAME = "crowd_exhaustion_reversal"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "H445 showed exhaustion (high repeat + high attention) is WORST (-0.0474 IC). "
        "After exhaustion, mean-reversion might kick in. Test: next-day following "
        "exhaustion vs random baseline."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H466 crowd_exhaustion_reversal test")
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

    panel = panel.merge(
        order_stats[["time", "ticker", "pct_change"]],
        on=["time", "ticker"],
        how="left",
    )

    panel = panel.sort_values(["ticker", "time"])

    panel["c16_rank"] = panel.groupby("time", sort=False)["s1_xs_proba"].rank(method="average", pct=True)
    panel["c16_top20"] = (panel["c16_rank"] >= 0.8).astype(bool)

    panel["pct_change_rank"] = panel.groupby("time", sort=False)["pct_change"].rank(method="average", pct=True)
    panel["high_return"] = (panel["pct_change_rank"] >= 0.8).astype(bool)

    panel["exhaustion_today"] = (panel["c16_top20"] & panel["high_return"]).astype(bool)

    panel["exhaustion_yesterday"] = panel.groupby("ticker")["exhaustion_today"].shift(1).fillna(False).astype(bool)
    panel["c16_top20_yesterday"] = panel.groupby("ticker")["c16_top20"].shift(1).fillna(False).astype(bool)

    panel["was_top20_not_today"] = (panel["c16_top20_yesterday"] & ~panel["c16_top20"]).astype(bool)
    panel["post_exhaustion_non_top"] = (panel["exhaustion_yesterday"] & ~panel["c16_top20"]).astype(bool)

    panel["two_days_exhaustion"] = panel.groupby("ticker")["exhaustion_today"].transform(
        lambda x: x.shift(1).fillna(False) & x.shift(2).fillna(False)
    ).astype(bool)

    panel["all_rows"] = True

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("exhaustion_today", "H445 worst state: top-C16 + high-return", family="exhaustion"),
    StateSpec("was_top20_not_today", "Yesterday top-C16, NOT today (dropped)", family="post_exhaustion", primary=True),
    StateSpec("post_exhaustion_non_top", "Yesterday exhaustion, today NOT top-C16", family="post_exhaustion"),
    StateSpec("two_days_exhaustion", "Two consecutive days of exhaustion", family="exhaustion"),
]

STATE_COLS = ["all_rows", "exhaustion_today", "was_top20_not_today", "post_exhaustion_non_top", "two_days_exhaustion"]


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
    validate_state_columns(panel, STATE_COLS, spec)

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

    exhaustion_ic = results[results["name"] == "exhaustion_today"]["avg_ic"].iloc[0] if not results.empty else 0
    was_dropped_ic = results[results["name"] == "was_top20_not_today"]["avg_ic"].iloc[0] if not results.empty else 0
    post_exhaustion_ic = results[results["name"] == "post_exhaustion_non_top"]["avg_ic"].iloc[0] if not results.empty else 0
    two_day_ic = results[results["name"] == "two_days_exhaustion"]["avg_ic"].iloc[0] if not results.empty else 0

    best = results[results["name"] != "all_rows"].sort_values("avg_ic", ascending=False).iloc[0] if not results.empty else {}
    best_name = best.get("name", "none")
    best_ic = best.get("avg_ic", 0)
    best_lift = best_ic - baseline_ic

    decision = "FAILED"
    if best_lift > 0.010:
        decision = "PASSED"
    elif best_lift > 0.003:
        decision = "MIXED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "exhaustion_today_ic": float(exhaustion_ic),
            "was_top20_not_today_ic": float(was_dropped_ic),
            "post_exhaustion_non_top_ic": float(post_exhaustion_ic),
            "two_days_exhaustion_ic": float(two_day_ic),
            "best_state": best_name,
            "best_lift": float(best_lift),
        },
        artifacts={"results": results_path, "yearly": yearly_path},
        metadata={"state_specs": [state.as_metadata() for state in STATE_SPECS], "hypothesis": SPEC.hypothesis},
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"  exhaustion_today (worst confirmed): {exhaustion_ic:.4f}")
    print(f"  was_top20_not_today (dropped TODAY): {was_dropped_ic:.4f} (lift: {was_dropped_ic - baseline_ic:+.4f})")
    print(f"  post_exhaustion_non_top: {post_exhaustion_ic:.4f}")
    print(f"  two_days_exhaustion: {two_day_ic:.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()