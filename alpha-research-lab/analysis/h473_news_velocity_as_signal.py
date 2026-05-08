"""
H473: news_velocity_as_signal

Hypothesis: The RATE of news arrival predicts differently than news NOVELTY (H440) or
news PRESENCE (H445). Fast-arriving news (sudden burst) may signal breaking information
that hasn't been priced yet. Slow/steady news may be already absorbed.

Connection to H440 (novelty) and H445 (presence):
- H440 found first-in-5d news = IC 0.123 vs repeat = 0.091 (+0.032 lift)
- H445 found no_news = IC 0.141 vs has_news = 0.104 (-0.037) — news is harmful
- AM tests the THIRD dimension: SPEED of news arrival (velocity), not novelty or presence.

Test: news count 3d delta (acceleration of news) vs forward IC.
Compare with: random baseline and H440 novelty controls.

Expected: High velocity (sudden burst) = breaking news = delayed alpha.
Low velocity (steady) = already-priced / mundane.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import numpy as np
import pandas as pd

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


BRANCH_NAME = "news_velocity_as_signal"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "News VELOCITY (3d count delta) tests a third dimension beyond novelty (H440) and "
        "presence (H445): fast-arriving news = breaking alpha, slow/steady = absorbed."
    ),
    start_year=2018,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H473 news_velocity_as_signal test")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument(
        "--news-path",
        type=str,
        default="/home/manh/stocks-ecosystem/data/features/news/datasets/news_daily_features.parquet",
    )
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

    nf_cols = [
        "date", "ticker",
        "phobert_article_count_1d",
        "phobert_article_count_5d",
        "phobert_sentiment_score_mean",
        "phobert_prob_pos_mean",
    ]
    nf = pd.read_parquet(args.news_path, columns=nf_cols)
    nf = nf.rename(columns={"date": "time"})
    nf["time"] = pd.to_datetime(nf["time"]).dt.normalize()
    nf = nf[nf["time"].dt.year.between(spec.start_year, spec.end_year)]

    panel = panel.merge(
        nf[["time", "ticker", "phobert_article_count_1d", "phobert_article_count_5d",
            "phobert_sentiment_score_mean", "phobert_prob_pos_mean"]],
        on=["time", "ticker"],
        how="left",
    )

    panel["all_rows"] = True

    panel["has_news"] = panel["phobert_article_count_1d"] > 0
    panel["no_news"] = ~panel["has_news"]

    panel["news_3d_delta"] = (
        panel["phobert_article_count_5d"] - panel["phobert_article_count_1d"]
    )
    panel["news_3d_delta"] = panel["news_3d_delta"].fillna(0)

    panel = panel.sort_values(["ticker", "time"])

    return panel


STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("has_news", "Has PhoBERT news (1d)", family="presence"),
    StateSpec("no_news", "No news (1d)", family="presence"),
    StateSpec("high_velocity", "High news velocity Q5 (3d delta top 20%)", family="velocity", primary=True),
    StateSpec("mid_velocity", "Mid news velocity Q3", family="velocity"),
    StateSpec("low_velocity", "Low news velocity Q1 (3d delta bottom 20%)", family="velocity"),
    StateSpec("high_vel_has_news", "High velocity + has news", family="vel_presence"),
    StateSpec("low_vel_has_news", "Low velocity + has news", family="vel_presence"),
    StateSpec("burst_has_news", "Velocity > 3 + has news (fast burst)", family="burst"),
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

    has_news_rows = panel["has_news"].sum()
    total_rows = len(panel)
    print(f"Panel: {total_rows} rows, has_news: {has_news_rows} ({100*has_news_rows/total_rows:.1f}%)")

    vel_rank = panel.groupby("time", sort=False)["news_3d_delta"].rank(method="average", pct=True)
    panel["high_velocity"] = vel_rank >= 0.8
    panel["mid_velocity"] = (vel_rank > 0.3) & (vel_rank < 0.7)
    panel["low_velocity"] = vel_rank <= 0.2

    panel["high_vel_has_news"] = panel["high_velocity"] & panel["has_news"]
    panel["low_vel_has_news"] = panel["low_velocity"] & panel["has_news"]

    panel["burst_has_news"] = (panel["news_3d_delta"] > 3) & panel["has_news"]

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

    baseline_row = results[results["name"] == "all_rows"]
    baseline_ic = float(baseline_row["avg_ic"].iloc[0]) if not baseline_row.empty else 0.0

    def get_ic(name):
        row = results[results["name"] == name]
        return float(row["avg_ic"].iloc[0]) if name in results["name"].values else None

    def get_lift(name):
        ic = get_ic(name)
        return (ic - baseline_ic) if ic is not None else None

    has_news_ic = get_ic("has_news")
    no_news_ic = get_ic("no_news")
    high_vel_ic = get_ic("high_velocity")
    mid_vel_ic = get_ic("mid_velocity")
    low_vel_ic = get_ic("low_velocity")
    high_vel_has_ic = get_ic("high_vel_has_news")
    low_vel_has_ic = get_ic("low_vel_has_news")
    burst_ic = get_ic("burst_has_news")

    h440_first_ref = 0.123
    h440_repeat_ref = 0.091

    best = results.sort_values("avg_ic", ascending=False, na_position="last").head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}

    has_news_lift = get_lift("has_news")
    high_vel_lift = get_lift("high_velocity")

    if high_vel_lift is not None and high_vel_lift > 0.005:
        decision = "PASSED"
    elif has_news_lift is not None and has_news_lift > 0:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "states_evaluated": int(len(results)),
            "baseline_ic": float(baseline_ic),
            "has_news_ic": has_news_ic,
            "no_news_ic": no_news_ic,
            "has_news_lift": has_news_lift,
            "high_velocity_ic": high_vel_ic,
            "mid_velocity_ic": mid_vel_ic,
            "low_velocity_ic": low_vel_ic,
            "high_velocity_lift": high_vel_lift,
            "high_vel_has_news_ic": high_vel_has_ic,
            "low_vel_has_news_ic": low_vel_has_ic,
            "burst_has_news_ic": burst_ic,
            "h440_first_ref": h440_first_ref,
            "h440_repeat_ref": h440_repeat_ref,
            "best_state": best_row.get("name"),
            "best_avg_ic": best_row.get("avg_ic"),
            "best_positive_years": best_row.get("positive_years"),
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

    print(results.sort_values("avg_ic", ascending=False, na_position="last")[["name","avg_ic","positive_years","years"]].to_string(index=False))
    print(f"\nDecision: {decision}")
    print(f"Baseline IC: {baseline_ic:.4f}")
    print(f"\nNews presence:")
    print(f"  has_news: {has_news_ic:.4f} (lift: {has_news_lift:+.4f})")
    print(f"  no_news: {no_news_ic:.4f}")
    print(f"  H440 first-in-5d ref: {h440_first_ref:.4f}")
    print(f"\nNews velocity:")
    print(f"  high_velocity (Q5): {high_vel_ic:.4f} (lift: {high_vel_lift:+.4f})")
    print(f"  mid_velocity (Q3): {mid_vel_ic:.4f}")
    print(f"  low_velocity (Q1): {low_vel_ic:.4f}")
    print(f"\nVelocity × presence:")
    print(f"  high_vel_has_news: {high_vel_has_ic:.4f}")
    print(f"  low_vel_has_news: {low_vel_has_ic:.4f}")
    print(f"  burst_has_news: {burst_ic:.4f}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()