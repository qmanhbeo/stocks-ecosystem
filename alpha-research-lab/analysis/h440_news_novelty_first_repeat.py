"""
H440: news_novelty_first_repeat

Hypothesis: News novelty (first article in N days vs repeat coverage vs high-frequency saturation)
predicts forward IC differently from raw article count. Connected to H383 (active news
strong-flow) which showed active news + high C16 = confirmation. Among news-present stocks,
NEW (first in 5+ days) vs REPEAT vs high-frequency may show different IC patterns.

Mechanism: Among stocks with news, flag "first in 5d" (no prior coverage), "repeat" (prior
coverage), and "high frequency" (multiple articles same day). Test novelty buckets for
forward IC against raw article count or active-news strong-flow controls.

Test: Compute 1d article count, rolling 5d count, flag novelty states. Test forward IC
for first vs repeat vs high-frequency states vs baseline news states. Uses existing PhoBERT
features. Compare against random baselines (not S1/C16 direct variations).
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


BRANCH_NAME = "h440_news_novelty_first_repeat"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "News novelty (first in N days vs repeat coverage vs high-frequency saturation) "
        "predicts forward IC differently from raw article count. Among news-present stocks, "
        "NEW vs REPEAT vs high-frequency may show different patterns. Connected to H383 "
        "(active news + high C16 = confirmation). Test novelty states vs raw article count "
        "vs active-news strong-flow controls."
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
    StateSpec("has_news", "Any news (article count > 0)", family="news_presence"),
    StateSpec("first_in_5d", "First article in last 5 days (no prior coverage)", family="novelty"),
    StateSpec("repeat_news", "Repeat coverage (had news in prior 5 days)", family="novelty"),
    StateSpec("high_freq_news", "Multiple articles same day (count >= 3)", family="novelty"),
    StateSpec("single_article", "Single article day (count == 1)", family="novelty"),
    StateSpec("first_strong_flow", "First in 5d + strong C16 flow", family="combined"),
    StateSpec("repeat_strong_flow", "Repeat news + strong C16 flow", family="combined"),
    StateSpec("high_freq_strong_flow", "High freq + strong C16 flow", family="combined"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H440 news_novelty_first_repeat")
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

    news_cols = [
        "date", "ticker",
        "phobert_article_count_1d",
        "phobert_article_count_5d",
        "phobert_prob_pos_mean",
        "phobert_source_type_official_or_regulatory_share",
        "phobert_forward_looking_share",
    ]
    news = pd.read_parquet(
        ROOT / "data" / "features" / "news" / "datasets" / "news_daily_features.parquet",
        columns=news_cols,
    )
    news = news.rename(columns={"date": "time"})
    news["time"] = pd.to_datetime(news["time"], errors="coerce").dt.normalize()
    news["ticker"] = news["ticker"].astype(str).str.upper()
    news = news.dropna(subset=["time", "ticker"])
    news = news[news["time"].dt.year <= 2025]
    news = news[news["time"] >= pd.Timestamp("2018-01-01")]

    panel = panel.merge(news, on=["time", "ticker"], how="left")

    panel["article_count_1d"] = panel["phobert_article_count_1d"].fillna(0)
    panel["article_count_5d"] = panel["phobert_article_count_5d"].fillna(0)
    panel["has_news"] = panel["article_count_1d"] > 0

    prior_5d_news = panel.groupby("ticker")["article_count_1d"].transform(
        lambda x: x.shift().rolling(5, min_periods=1).sum().fillna(0)
    )
    panel["prior_5d_news"] = prior_5d_news

    panel["first_in_5d"] = panel["has_news"] & (panel["prior_5d_news"] == 0)
    panel["repeat_news"] = panel["has_news"] & (panel["prior_5d_news"] > 0)
    panel["high_freq_news"] = panel["article_count_1d"] >= 3
    panel["single_article"] = panel["article_count_1d"] == 1

    panel["strong_flow"] = panel["c16"] > panel.groupby("time")["c16"].transform(
        lambda x: x.quantile(0.75)
    )
    panel["first_strong_flow"] = panel["first_in_5d"] & panel["strong_flow"]
    panel["repeat_strong_flow"] = panel["repeat_news"] & panel["strong_flow"]
    panel["high_freq_strong_flow"] = panel["high_freq_news"] & panel["strong_flow"]

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

    has_news_ic = results[results["name"] == "has_news"]["avg_ic"].values
    has_news_val = float(has_news_ic[0]) if len(has_news_ic) > 0 else None

    first_ic = results[results["name"] == "first_in_5d"]["avg_ic"].values
    first_val = float(first_ic[0]) if len(first_ic) > 0 else None
    first_rows = int(results[results["name"] == "first_in_5d"]["pooled_rows"].values[0]) if len(first_ic) > 0 else 0
    first_pos = int(results[results["name"] == "first_in_5d"]["positive_years"].values[0]) if len(first_ic) > 0 else 0
    first_total = int(results[results["name"] == "first_in_5d"]["years"].values[0]) if len(first_ic) > 0 else 0

    repeat_ic = results[results["name"] == "repeat_news"]["avg_ic"].values
    repeat_val = float(repeat_ic[0]) if len(repeat_ic) > 0 else None

    hf_ic = results[results["name"] == "high_freq_news"]["avg_ic"].values
    hf_val = float(hf_ic[0]) if len(hf_ic) > 0 else None

    single_ic = results[results["name"] == "single_article"]["avg_ic"].values
    single_val = float(single_ic[0]) if len(single_ic) > 0 else None

    fsf_ic = results[results["name"] == "first_strong_flow"]["avg_ic"].values
    fsf_val = float(fsf_ic[0]) if len(fsf_ic) > 0 else None
    rsf_ic = results[results["name"] == "repeat_strong_flow"]["avg_ic"].values
    rsf_val = float(rsf_ic[0]) if len(rsf_ic) > 0 else None
    hff_ic = results[results["name"] == "high_freq_strong_flow"]["avg_ic"].values
    hff_val = float(hff_ic[0]) if len(hff_ic) > 0 else None

    first_vs_repeat = (first_val - repeat_val) if first_val is not None and repeat_val is not None else None
    hf_vs_single = (hf_val - single_val) if hf_val is not None and single_val is not None else None

    if first_vs_repeat is not None and abs(first_vs_repeat) > 0.01 and first_pos >= first_total * 0.6:
        if first_vs_repeat > 0:
            decision = "PASSED"
        else:
            decision = "MIXED"
    elif first_vs_repeat is not None and abs(first_vs_repeat) > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "all_rows_avg_ic": all_rows_ic_val,
            "has_news_avg_ic": has_news_val,
            "first_in_5d_avg_ic": first_val,
            "first_in_5d_rows": first_rows,
            "first_in_5d_pos_years": f"{first_pos}/{first_total}",
            "repeat_news_avg_ic": repeat_val,
            "high_freq_news_avg_ic": hf_val,
            "single_article_avg_ic": single_val,
            "first_strong_flow_avg_ic": fsf_val,
            "repeat_strong_flow_avg_ic": rsf_val,
            "high_freq_strong_flow_avg_ic": hff_val,
            "first_vs_repeat_lift": first_vs_repeat,
            "hf_vs_single_lift": hf_vs_single,
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
    print(f"\nHas news IC: {has_news_val}")
    print(f"First in 5d IC: {first_val} ({first_pos}/{first_total} pos years, {first_rows} rows)")
    print(f"Repeat news IC: {repeat_val}")
    print(f"High freq IC: {hf_val}, Single article IC: {single_val}")
    print(f"First vs Repeat lift: {first_vs_repeat}")
    print(f"HF vs Single lift: {hf_vs_single}")
    print(f"First+Flow: {fsf_val}, Repeat+Flow: {rsf_val}, HF+Flow: {hff_val}")
    print(f"Decision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()