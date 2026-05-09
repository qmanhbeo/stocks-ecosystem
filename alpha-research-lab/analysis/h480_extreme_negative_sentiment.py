"""
H480: extreme_negative_sentiment

Hypothesis: EXTREME negative PhoBERT (bottom 10%) + next-day reversal?
H383 passed positive (positive news + strong flow), test EXTREME NEGATIVE for capitulation-reversal.

Mechanism: Extreme negative sentiment may signal capitulation / panic selling,
which could reverse the next day if the sentiment was overdone.

Decision rule:
- PASS: extreme_negative (bottom 10% prob_neg) has IC > +0.01 vs baseline
- MIXED: marginal improvement (+0.005 to +0.01)
- FAIL: no improvement or negative

Compare with random baseline (not S1/C16).
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


BRANCH_NAME = "extreme_negative_sentiment"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "EXTREME negative PhoBERT (bottom 10%) + next-day reversal? "
        "H383 passed positive (positive news + strong flow), test EXTREME NEGATIVE for capitulation-reversal."
    ),
    start_year=2018,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H480 extreme_negative_sentiment test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--phobert-path", type=str,
                        default=str(data_path("features/news/datasets/phobert_ticker_day_sentiment.parquet")))
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

    phobert = pd.read_parquet(args.phobert_path)
    phobert["time"] = pd.to_datetime(phobert["date"])
    phobert = phobert[phobert["time"].dt.year <= 2025]

    panel = panel.merge(
        phobert[["time", "ticker", "phobert_prob_neg_mean", "phobert_sentiment_score_mean", 
                 "phobert_article_count_1d", "phobert_neg_share"]],
        on=["time", "ticker"],
        how="left",
    )

    panel["all_rows"] = True

    panel = panel.dropna(subset=["phobert_prob_neg_mean"])
    panel = panel[panel["phobert_article_count_1d"] > 0]

    neg_rank = panel.groupby("time", sort=False)["phobert_prob_neg_mean"].rank(method="average", pct=True)

    panel["extreme_negative"] = neg_rank >= 0.90

    moderate_neg = (neg_rank >= 0.70) & (neg_rank < 0.90)
    panel["moderate_negative"] = moderate_neg

    sentiment_rank = panel.groupby("time", sort=False)["phobert_sentiment_score_mean"].rank(method="average", pct=True)
    panel["extreme_sentiment_negative"] = sentiment_rank <= 0.10

    panel["extreme_neg_high_share"] = panel["extreme_negative"] & (panel["phobert_neg_share"] >= 0.5)

    neg_score_rank = panel.groupby("time", sort=False)["phobert_prob_neg_mean"].rank(method="average", pct=True)
    bottom_5 = neg_score_rank <= 0.05
    panel["ultra_negative"] = bottom_5

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("extreme_negative", "Bottom 10% prob_neg (extreme negative)", family="sentiment", primary=True),
    StateSpec("moderate_negative", "70-90% prob_neg (moderate negative)", family="sentiment"),
    StateSpec("extreme_sentiment_negative", "Bottom 10% sentiment score (extremely negative)", family="sentiment"),
    StateSpec("ultra_negative", "Bottom 5% prob_neg (ultra negative)", family="sentiment"),
    StateSpec("extreme_neg_high_share", "Extreme negative + 50%+ negative share", family="sentiment"),
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
    extreme_neg_ic = results[results["name"] == "extreme_negative"]["avg_ic"].iloc[0] if not results.empty else 0
    moderate_neg_ic = results[results["name"] == "moderate_negative"]["avg_ic"].iloc[0] if not results.empty else 0
    extreme_sent_ic = results[results["name"] == "extreme_sentiment_negative"]["avg_ic"].iloc[0] if not results.empty else 0
    ultra_neg_ic = results[results["name"] == "ultra_negative"]["avg_ic"].iloc[0] if not results.empty else 0
    extreme_high_share_ic = results[results["name"] == "extreme_neg_high_share"]["avg_ic"].iloc[0] if not results.empty else 0

    extreme_neg_lift = extreme_neg_ic - baseline_ic
    extreme_sent_lift = extreme_sent_ic - baseline_ic
    ultra_neg_lift = ultra_neg_ic - baseline_ic

    best_lift = max(extreme_neg_lift, extreme_sent_lift, ultra_neg_lift)

    if best_lift > 0.01:
        decision = "PASSED"
    elif best_lift > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "extreme_negative_ic": float(extreme_neg_ic),
            "extreme_negative_lift": float(extreme_neg_lift),
            "moderate_negative_ic": float(moderate_neg_ic),
            "extreme_sentiment_negative_ic": float(extreme_sent_ic),
            "extreme_sentiment_negative_lift": float(extreme_sent_lift),
            "ultra_negative_ic": float(ultra_neg_ic),
            "ultra_negative_lift": float(ultra_neg_lift),
            "extreme_neg_high_share_ic": float(extreme_high_share_ic),
            "best_lift": float(best_lift),
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
    print(f"\nExtreme negative states:")
    print(f"  extreme_negative (bottom 10%): {extreme_neg_ic:.4f} (lift: {extreme_neg_lift:+.4f})")
    print(f"  moderate_negative: {moderate_neg_ic:.4f}")
    print(f"  extreme_sentiment_negative: {extreme_sent_ic:.4f} (lift: {extreme_sent_lift:+.4f})")
    print(f"  ultra_negative (bottom 5%): {ultra_neg_ic:.4f} (lift: {ultra_neg_lift:+.4f})")
    print(f"  extreme_neg_high_share: {extreme_high_share_ic:.4f}")
    print(f"\nBest lift: {best_lift:+.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()