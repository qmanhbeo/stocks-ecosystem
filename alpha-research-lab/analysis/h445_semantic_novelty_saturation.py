"""
H445 - Semantic Novelty Saturation

Hypothesis: News volume may be harmful when semantic novelty is exhausted, while
high novelty plus muted price response may be delayed alpha.

Connection: H440 found first-in-5d novelty works (+0.032 IC). This tests whether
combining novelty with attention creates exhaustion states or delayed alpha.

First test: Use first-in-N-days feature as novelty proxy, combine with article count
and S1 response to test exhaustion and delayed-alpha states.
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
    ExperimentSpec,
    StateSpec,
    load_s1_decision_panel,
)


BRANCH_NAME = "semantic_novelty_saturation"
MODE = "research_branch"

S1_SCORE = "s1_xs_proba"
S1_TARGET = "s1_barrier_hit_1d"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "News volume may be harmful when semantic novelty is exhausted, while "
        "high novelty plus muted price response may be delayed alpha."
    ),
    start_year=2015,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "H445: Test news novelty saturation with attention/response combos."
        )
    )
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--news-path", type=str, default="/home/manh/stocks-ecosystem/data/features/news/datasets/news_daily_features.parquet")
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def load_panel(args: argparse.Namespace, spec: ExperimentSpec) -> pd.DataFrame:
    """Load S1 panel and merge news features."""
    panel = load_s1_decision_panel(
        args.s1_path,
        start_year=spec.start_year,
        end_year=spec.end_year,
    )

    # Load news features
    news = pd.read_parquet(args.news_path)
    news["time"] = pd.to_datetime(news["date"])
    news = news.drop(columns=["date"])

    # Select key news features - use phobert counts which have data
    news_cols = ["ticker", "time", 
                 "phobert_article_count_1d", "phobert_article_count_5d", 
                 "phobert_sentiment_score_mean", 
                 "ollama_guarded_article_count_1d", 
                 "ollama_guarded_event_family_earnings_share",
                 "phobert_source_type_official_or_regulatory_share"]

    news_cols = [c for c in news_cols if c in news.columns]
    news_subset = news[news_cols].copy()

    panel = panel.merge(news_subset, on=["ticker", "time"], how="left")

    # Create first-in-N-days novelty flag (from H440: first-in-5d is strong)
    # Proxy: if 1d count > 0 but 5d count is close to 1d, then it's first-in-X (new)
    panel["first_in_5d_proxy"] = (panel["phobert_article_count_1d"] > 0) & (panel["phobert_article_count_5d"] <= panel["phobert_article_count_1d"] * 1.5)
    panel["repeat_coverage"] = (panel["phobert_article_count_5d"] > panel["phobert_article_count_1d"] * 3)  # Many past articles = repeat coverage

    # Create attention states
    panel["has_news"] = panel["phobert_article_count_1d"].fillna(0) > 0
    panel["high_attention"] = panel["phobert_article_count_1d"].fillna(0) > panel["phobert_article_count_1d"].median()
    panel["low_attention"] = panel["phobert_article_count_1d"].fillna(0) == 0
    panel["no_news"] = panel["phobert_article_count_1d"].fillna(0) == 0

    # Create response states
    panel["muted_response"] = panel[S1_SCORE].between(0.3, 0.5)  # Muted S1 response
    panel["strong_response"] = panel[S1_SCORE] > 0.6  # Strong S1 response

    # Create combined states:
    # Exhaustion: has news + high attention + repeat coverage (repeated coverage despite high attention)
    panel["exhaustion_state"] = panel["has_news"] & panel["repeat_coverage"]

    # Delayed alpha: has news + muted response (news but price not responding = delayed alpha)
    panel["delayed_alpha"] = panel["has_news"] & panel["muted_response"]

    # First news + muted response (novel news but no price response)
    panel["novel_delayed"] = panel["first_in_5d_proxy"] & panel["muted_response"]

    # First news + strong response (novel news with price response)
    panel["novel_responded"] = panel["first_in_5d_proxy"] & panel["strong_response"]

    return panel


def define_states() -> list[StateSpec]:
    """Define state specs based on novelty + attention combos."""
    return [
        StateSpec("all_rows", "All S1 panel rows - baseline", family="baseline", primary=True),
        StateSpec("has_news", "Has news (any)", family="news", baseline="all_rows"),
        StateSpec("no_news", "No news", family="news", baseline="all_rows"),
        StateSpec("first_in_5d", "First-in-5d proxy (novel)", family="novelty", baseline="all_rows"),
        StateSpec("repeat_coverage", "Repeat coverage (not novel)", family="novelty", baseline="all_rows"),
        StateSpec("high_attention", "High attention", family="attention", baseline="all_rows"),
        StateSpec("exhaustion", "Has news + repeat coverage (exhaustion)", family="combo", baseline="all_rows"),
        StateSpec("delayed_alpha", "Has news + muted response", family="combo", baseline="all_rows"),
        StateSpec("novel_delayed", "First-in-5d + muted response", family="combo", baseline="all_rows"),
        StateSpec("novel_responded", "First-in-5d + strong response", family="combo", baseline="all_rows"),
    ]


def compute_state_metrics(panel: pd.DataFrame, states: list[StateSpec]) -> pd.DataFrame:
    """Compute IC and row counts for each state."""
    results = []
    for state in states:
        if state.name == "all_rows":
            subset = panel
        elif state.name == "has_news":
            subset = panel[panel["has_news"]]
        elif state.name == "no_news":
            subset = panel[panel["no_news"]]
        elif state.name == "first_in_5d":
            subset = panel[panel["first_in_5d_proxy"]]
        elif state.name == "repeat_coverage":
            subset = panel[panel["repeat_coverage"]]
        elif state.name == "high_attention":
            subset = panel[panel["high_attention"]]
        elif state.name == "exhaustion":
            subset = panel[panel["exhaustion_state"]]
        elif state.name == "delayed_alpha":
            subset = panel[panel["delayed_alpha"]]
        elif state.name == "novel_delayed":
            subset = panel[panel["novel_delayed"]]
        elif state.name == "novel_responded":
            subset = panel[panel["novel_responded"]]
        else:
            continue

        if len(subset) > 100:
            ic = subset[S1_SCORE].corr(subset[S1_TARGET])
            results.append({
                "state": state.name,
                "ic": ic,
                "rows": len(subset),
                "years": len(subset["year"].unique()),
            })

    return pd.DataFrame(results)


def decision(results_df: pd.DataFrame) -> dict:
    """Decision logic: do novelty + attention combos add value?"""
    baseline = results_df[results_df["state"] == "all_rows"].iloc[0]
    baseline_ic = baseline["ic"]
    baseline_rows = baseline["rows"]

    print(f"\nBaseline IC: {baseline_ic:.4f} ({baseline_rows} rows)")

    # Print all results
    for _, row in results_df.iterrows():
        lift = row["ic"] - baseline_ic
        print(f"  {row['state']}: IC={row['ic']:.4f}, lift={lift:+.4f}, rows={row['rows']}")

    # Key tests:
    # 1. Does exhaustion hurt? (repeat coverage + attention)
    # 2. Does novel_delayed signal delayed alpha?
    # 3. Does novel_responded beat novel_delayed?

    exhaustion_row = results_df[results_df["state"] == "exhaustion"]
    delayed_row = results_df[results_df["state"] == "delayed_alpha"]
    novel_delayed_row = results_df[results_df["state"] == "novel_delayed"]
    novel_responded_row = results_df[results_df["state"] == "novel_responded"]
    first_in_5d_row = results_df[results_df["state"] == "first_in_5d"]
    repeat_row = results_df[results_df["state"] == "repeat_coverage"]

    exhaustion_lift = (exhaustion_row.iloc[0]["ic"] - baseline_ic) if len(exhaustion_row) > 0 else 0
    novel_delayed_lift = (novel_delayed_row.iloc[0]["ic"] - baseline_ic) if len(novel_delayed_row) > 0 else 0
    novel_responded_lift = (novel_responded_row.iloc[0]["ic"] - baseline_ic) if len(novel_responded_row) > 0 else 0

    first_lift = (first_in_5d_row.iloc[0]["ic"] - baseline_ic) if len(first_in_5d_row) > 0 else 0
    repeat_lift = (repeat_row.iloc[0]["ic"] - baseline_ic) if len(repeat_row) > 0 else 0

    print(f"\nKey comparisons:")
    print(f"First-in-5d: {first_lift:+.4f}")
    print(f"Repeat coverage: {repeat_lift:+.4f}")
    print(f"Novel + delayed: {novel_delayed_lift:+.4f}")
    print(f"Novel + responded: {novel_responded_lift:+.4f}")

    return {
        "baseline_ic": baseline_ic,
        "exhaustion_lift": exhaustion_lift,
        "novel_delayed_lift": novel_delayed_lift,
        "novel_responded_lift": novel_responded_lift,
        "first_lift": first_lift,
        "repeat_lift": repeat_lift,
        "exhaustion_hurts": exhaustion_lift < -0.005,
        "delayed_alpha_signal": novel_delayed_lift > 0.005 or novel_responded_lift > first_lift,
    }


def main():
    args = parse_args()
    spec = replace(SPEC, start_year=args.start_year, end_year=args.end_year)

    print(f"Loading S1 panel {args.s1_path}...")
    panel = load_panel(args, spec)

    panel["year"] = panel["time"].dt.year

    print(f"Panel loaded: {len(panel)} rows, {panel['time'].nunique()} dates")
    print(f"Years: {panel['year'].min()}-{panel['year'].max()}")

    states = define_states()
    print(f"\nEvaluating {len(states)} states...")

    results = compute_state_metrics(panel, states)
    print("\n=== State IC Results ===")
    print(results.to_string(index=False))

    verdict = decision(results)

    print(f"\n=== Verdict ===")
    if verdict["exhaustion_hurts"]:
        print(f"PASSED: Exhaustion state hurts (lift {verdict['exhaustion_lift']:+.4f})")
    elif verdict["delayed_alpha_signal"]:
        print(f"PASSED: Novel + response combos show signal")
    else:
        print(f"FAILED: No clear novelty saturation signal")

    # Write results to artifact
    output_path = ROOT / "artifacts" / "run_summaries" / f"h445_{BRANCH_NAME}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    import json
    artifact = {
        "experiment": BRANCH_NAME,
        "hypothesis": spec.hypothesis,
        "baseline_ic": float(verdict["baseline_ic"]),
        "exhaustion_lift": float(verdict["exhaustion_lift"]),
        "novel_delayed_lift": float(verdict["novel_delayed_lift"]),
        "novel_responded_lift": float(verdict["novel_responded_lift"]),
        "first_lift": float(verdict["first_lift"]),
        "repeat_lift": float(verdict["repeat_lift"]),
        "exhaustion_hurts": bool(verdict["exhaustion_hurts"]),
        "delayed_alpha_signal": bool(verdict["delayed_alpha_signal"]),
        "results": results.to_dict("records"),
        "verdict": "PASSED" if (verdict["exhaustion_hurts"] or verdict["delayed_alpha_signal"]) else "FAILED",
    }
    with open(output_path, "w") as f:
        json.dump(artifact, f, indent=2)

    print(f"\nArtifact written to: {output_path}")


if __name__ == "__main__":
    main()