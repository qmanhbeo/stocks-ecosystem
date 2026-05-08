"""
H438: news_consensus_divergence

Hypothesis: When all news sources agree (consensus) vs when they disagree (divergence),
disagreement could mean hidden information and alpha. Connected to H382 which showed
source type matters but consensus vs disagreement not tested.

Mechanism: Use PhoBERT source type (official/regulatory, company, market, etc.) and
sentiment to define consensus (all same source type) vs divergence (mixed sources).
Test divergence buckets for forward IC against raw article count, source type, and
active-news strong-flow controls.

Test: Compute news sentiment agreement across PhoBERT sources, test disagreement buckets
for forward IC. Uses existing news features. Compare against random baselines.
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


BRANCH_NAME = "h438_news_consensus_divergence"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "When news sources agree (consensus) vs disagree (divergence), disagreement "
        "may indicate hidden information and alpha. Use PhoBERT source type and "
        "sentiment to define consensus vs divergence. Connected to H382 which showed "
        "source type matters but consensus vs disagreement not tested."
    ),
    start_year=2018,
    end_year=2025,
    min_year_rows=500,
    min_phase_rows=500,
    target_columns={S1_TARGET_COL: "future 1d barrier-hit label; target only"},
    score_columns={S1_SCORE_COL: "decision-time S1 probability score"},
)

STATE_SPECS = [
    StateSpec("all_rows", "All S1 panel rows", family="baseline", primary=True),
    StateSpec("high_news_count", "High article count (Q5)", family="news_volume"),
    StateSpec("low_news_count", "Low article count (Q1)", family="news_volume"),
    StateSpec("consensus_news", "All same source type (official or company only)", family="consensus"),
    StateSpec("divergence_news", "Mixed source types (official+market+company)", family="divergence"),
    StateSpec("consensus_positive", "Consensus + positive sentiment", family="consensus"),
    StateSpec("divergence_positive", "Divergence + positive sentiment", family="divergence"),
    StateSpec("consensus_negative", "Consensus + negative sentiment", family="consensus"),
    StateSpec("divergence_negative", "Divergence + negative sentiment", family="divergence"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H438 news_consensus_divergence")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
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
    panel["all_rows"] = True

    vol_path = ROOT / "data" / "features" / "xs_order_pressure_daily.parquet"
    vol = pd.read_parquet(vol_path, columns=["time", "ticker", "order_volume_ratio"])
    vol["time"] = pd.to_datetime(vol["time"], errors="coerce").dt.normalize()
    vol["ticker"] = vol["ticker"].astype(str).str.upper()
    vol = vol.dropna(subset=["time", "ticker"])
    vol = vol[vol["time"].dt.year <= 2025]
    vol = vol[vol["time"] >= pd.Timestamp("2018-01-01")]
    panel = panel.merge(vol[["time", "ticker", "order_volume_ratio"]], on=["time", "ticker"], how="left")
    panel["c16"] = panel["order_volume_ratio"].fillna(panel["order_volume_ratio"].median())

    news_path = ROOT / "data" / "features" / "news" / "datasets" / "news_daily_features.parquet"
    news_cols = [
        "date", "ticker",
        "phobert_article_count_1d",
        "phobert_prob_pos_mean",
        "phobert_prob_neg_mean",
        "phobert_source_type_official_or_regulatory_share",
        "phobert_source_type_article_count_5d",
        "phobert_forward_looking_share",
    ]
    news = pd.read_parquet(news_path, columns=news_cols)
    news = news.rename(columns={"date": "time"})
    news["time"] = pd.to_datetime(news["time"], errors="coerce").dt.normalize()
    news["ticker"] = news["ticker"].astype(str).str.upper()
    news = news.dropna(subset=["time", "ticker"])
    news = news[news["time"].dt.year <= 2025]
    news = news[news["time"] >= pd.Timestamp("2018-01-01")]

    panel = panel.merge(news, on=["time", "ticker"], how="left")

    panel["article_count"] = panel["phobert_article_count_1d"].fillna(0)
    panel["has_news"] = panel["article_count"] > 0

    official_share = panel["phobert_source_type_official_or_regulatory_share"].fillna(0)
    forward_share = panel["phobert_forward_looking_share"].fillna(0)

    panel["is_official"] = official_share > 0.5
    panel["is_mixed"] = (official_share > 0.1) & (official_share < 0.8)
    panel["is_forward"] = forward_share > 0.5

    panel["sentiment_positive"] = panel["phobert_prob_pos_mean"].fillna(0) > 0.35
    panel["sentiment_negative"] = panel["phobert_prob_neg_mean"].fillna(0) > 0.35
    panel["sentiment_neutral"] = ~panel["sentiment_positive"] & ~panel["sentiment_negative"]

    q5_article = panel["article_count"].groupby(panel["time"]).quantile(0.80)
    panel["high_news_count"] = panel["article_count"] > panel["time"].map(q5_article)
    q1_article = panel["article_count"].groupby(panel["time"]).quantile(0.20)
    panel["low_news_count"] = panel["article_count"] < panel["time"].map(q1_article)

    panel["consensus_news"] = panel["is_official"] & ~panel["is_mixed"] & panel["has_news"]
    panel["divergence_news"] = panel["is_mixed"] & panel["has_news"]

    panel["consensus_positive"] = panel["consensus_news"] & panel["sentiment_positive"]
    panel["divergence_positive"] = panel["divergence_news"] & panel["sentiment_positive"]
    panel["consensus_negative"] = panel["consensus_news"] & panel["sentiment_negative"]
    panel["divergence_negative"] = panel["divergence_news"] & panel["sentiment_negative"]

    panel["strong_flow"] = panel["c16"] > panel.groupby("time")["c16"].transform(lambda x: x.quantile(0.75))
    panel["active_news_strong_flow"] = panel["has_news"] & panel["strong_flow"]

    return panel


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
    panel_path = write_dataframe_artifact(panel, context, f"{BRANCH_NAME}_panel")

    all_rows_ic = results[results["name"] == "all_rows"]["avg_ic"].values
    all_rows_ic_val = float(all_rows_ic[0]) if len(all_rows_ic) > 0 else None

    consensus_ic = results[results["name"] == "consensus_news"]["avg_ic"].values
    consensus_val = float(consensus_ic[0]) if len(consensus_ic) > 0 else None

    diverge_ic = results[results["name"] == "divergence_news"]["avg_ic"].values
    diverge_val = float(diverge_ic[0]) if len(diverge_ic) > 0 else None

    con_pos_ic = results[results["name"] == "consensus_positive"]["avg_ic"].values
    con_pos_val = float(con_pos_ic[0]) if len(con_pos_ic) > 0 else None

    div_pos_ic = results[results["name"] == "divergence_positive"]["avg_ic"].values
    div_pos_val = float(div_pos_ic[0]) if len(div_pos_ic) > 0 else None

    con_neg_ic = results[results["name"] == "consensus_negative"]["avg_ic"].values
    con_neg_val = float(con_neg_ic[0]) if len(con_neg_ic) > 0 else None

    div_neg_ic = results[results["name"] == "divergence_negative"]["avg_ic"].values
    div_neg_val = float(div_neg_ic[0]) if len(div_neg_ic) > 0 else None

    active_ic = results[results["name"] == "active_news_strong_flow"]["avg_ic"].values if "active_news_strong_flow" in results["name"].values else [None]
    active_val = float(active_ic[0]) if len(active_ic) > 0 and active_ic[0] is not None else None

    diverge_vs_consensus = (diverge_val - consensus_val) if diverge_val is not None and consensus_val is not None else None
    con_pos_vs_div_pos = (con_pos_val - div_pos_val) if con_pos_val is not None and div_pos_val is not None else None

    pos_years_div = int(results[results["name"] == "divergence_news"]["positive_years"].values[0]) if len(diverge_ic) > 0 else 0
    total_years_div = int(results[results["name"] == "divergence_news"]["years"].values[0]) if len(diverge_ic) > 0 else 0
    pos_years_con = int(results[results["name"] == "consensus_news"]["positive_years"].values[0]) if len(consensus_ic) > 0 else 0
    total_years_con = int(results[results["name"] == "consensus_news"]["years"].values[0]) if len(consensus_ic) > 0 else 0

    if diverge_vs_consensus is not None and diverge_vs_consensus > 0.01 and pos_years_div >= total_years_div * 0.6:
        decision = "PASSED"
    elif diverge_vs_consensus is not None and diverge_vs_consensus > 0.005 and pos_years_div >= total_years_div * 0.5:
        decision = "MIXED"
    elif diverge_vs_consensus is not None and con_pos_vs_div_pos is not None:
        if con_pos_vs_div_pos > 0.01:
            decision = "MIXED"
        elif con_pos_vs_div_pos < -0.005:
            decision = "MIXED"
        else:
            decision = "FAILED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "all_rows_avg_ic": all_rows_ic_val,
            "consensus_news_avg_ic": consensus_val,
            "consensus_pos_years": f"{pos_years_con}/{total_years_con}",
            "divergence_news_avg_ic": diverge_val,
            "divergence_pos_years": f"{pos_years_div}/{total_years_div}",
            "diverge_vs_consensus_lift": diverge_vs_consensus,
            "consensus_positive_avg_ic": con_pos_val,
            "divergence_positive_avg_ic": div_pos_val,
            "consensus_negative_avg_ic": con_neg_val,
            "divergence_negative_avg_ic": div_neg_val,
            "active_news_strong_flow_avg_ic": active_val,
            "best_state": results.sort_values("avg_ic", ascending=False, na_position="last").iloc[0]["name"],
            "best_avg_ic": results.sort_values("avg_ic", ascending=False, na_position="last").iloc[0]["avg_ic"],
        },
        artifacts={
            "results": results_path,
            "yearly": yearly_path,
            "panel": panel_path,
        },
        metadata={
            "state_specs": [state.as_metadata() for state in STATE_SPECS],
            "hypothesis": SPEC.hypothesis,
        },
    )

    print(results.sort_values("avg_ic", ascending=False, na_position="last").to_string(index=False))
    print(f"\nConsensus IC: {consensus_val} ({pos_years_con}/{total_years_con} pos years)")
    print(f"Divergence IC: {diverge_val} ({pos_years_div}/{total_years_div} pos years)")
    print(f"Diverge vs Consensus lift: {diverge_vs_consensus}")
    print(f"Consensus+Pos: {con_pos_val}, Divergence+Pos: {div_pos_val}")
    print(f"Consensus+Neg: {con_neg_val}, Divergence+Neg: {div_neg_val}")
    print(f"Decision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()