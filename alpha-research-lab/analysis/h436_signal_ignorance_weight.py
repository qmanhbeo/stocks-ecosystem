"""
H436: signal_ignorance_weight

Hypothesis: True edge is knowing WHEN to ignore S1/C16, not how to weight them.
When S1/C16 are in certain regimes, they hurt; ignorance is alpha.

Mechanism: Train a classifier on regime features (market state, volatility,
breadth, volume regime, news state, time-of-day/session) to predict when
S1/C16 IC degrades below noise. Use this as a cash/veto signal vs normal buy.

Test: regime features -> degrade/no-degrade labels, then test whether
ignoring signal in degrade-state improves forward returns vs always-buying.
Compare against random baselines (not S1/C16 direct variations).

This is NOT a S1/C16 combination - it's a regime-aware IGNORANCE signal.
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


BRANCH_NAME = "h436_signal_ignorance_weight"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "True edge is knowing WHEN to ignore S1/C16, not how to weight them. "
        "Train a classifier to predict signal degradation regimes, use as cash/veto. "
        "Compare against random baselines, not S1/C16 direct variations."
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
    StateSpec("always_buy_top10", "Top-10 S1 always buy", family="baseline"),
    StateSpec("ignore_degrade_state", "Ignore signal when degrade-state predicted", family="ignorance"),
    StateSpec("always_buy_in_degrade", "Always buy even in degrade-state", family="degrade_control"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H436 signal_ignorance_weight")
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
    panel["s1_rank"] = panel.groupby("time")[S1_SCORE_COL].rank(pct=True)
    panel["c16_rank"] = panel.groupby("time")["c16"].rank(pct=True)
    panel = panel.dropna(subset=["c16"])

    date_panel = panel.groupby("time").agg(
        market_breadth=("s1_barrier_hit_1d", "mean"),
        c16_mean=("c16", "mean"),
        c16_std=("c16", lambda x: x.std()),
        c16_p90=("c16", lambda x: x.quantile(0.90)),
    ).reset_index()

    panel = panel.merge(date_panel, on="time", how="left")

    panel["high_vol_regime"] = panel.groupby("ticker")["c16"].transform(
        lambda x: x > x.rolling(20, min_periods=5).mean() * 1.5
    )
    panel["low_breadth"] = panel["market_breadth"] < 0.35
    roll_std = panel.groupby("time")["c16_std"].transform(
        lambda x: x.rolling(60, min_periods=15).mean()
    )
    panel["high_c16_spread"] = panel["c16_std"] > roll_std.fillna(roll_std.mean())

    news_path = ROOT / "data" / "features" / "news" / "datasets" / "news_daily_features.parquet"
    if news_path.exists():
        news = pd.read_parquet(news_path, columns=["date", "ticker", "phobert_prob_pos_mean", "phobert_article_count_1d"])
        news = news.rename(columns={"date": "time"})
        news["time"] = pd.to_datetime(news["time"], errors="coerce").dt.normalize()
        news["ticker"] = news["ticker"].astype(str).str.upper()
        news = news.dropna(subset=["time", "ticker"])
        news = news[news["time"].dt.year <= 2025]
        panel = panel.merge(news[["time", "ticker", "phobert_prob_pos_mean", "phobert_article_count_1d"]], on=["time", "ticker"], how="left")
        panel["has_news"] = panel["phobert_article_count_1d"].fillna(0) > 0
    else:
        panel["has_news"] = False

    week = panel["time"].dt.dayofweek
    panel["is_monday"] = week == 0
    panel["is_friday"] = week == 4
    panel["month_start"] = panel["time"].dt.day <= 5
    panel["month_end"] = panel["time"].dt.day >= 25

    panel["degrade_composite"] = (
        panel["high_vol_regime"].fillna(False) |
        panel["low_breadth"] |
        panel["high_c16_spread"].fillna(False)
    ).astype(int)

    panel["always_buy_top10"] = panel["s1_rank"] >= 0.90

    panel["ignore_degrade_state"] = panel["always_buy_top10"] & (panel["degrade_composite"] == 0)
    panel["always_buy_in_degrade"] = panel["always_buy_top10"] & (panel["degrade_composite"] == 1)

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

    always_ic = results[results["name"] == "always_buy_top10"]["avg_ic"].values
    always_val = float(always_ic[0]) if len(always_ic) > 0 else None

    ignore_ic = results[results["name"] == "ignore_degrade_state"]["avg_ic"].values
    ignore_val = float(ignore_ic[0]) if len(ignore_ic) > 0 else None

    degrade_ic = results[results["name"] == "always_buy_in_degrade"]["avg_ic"].values
    degrade_val = float(degrade_ic[0]) if len(degrade_ic) > 0 else None

    pos_years_ignore = int(results[results["name"] == "ignore_degrade_state"]["positive_years"].values[0]) if len(ignore_ic) > 0 else 0
    total_years_ignore = int(results[results["name"] == "ignore_degrade_state"]["years"].values[0]) if len(ignore_ic) > 0 else 0
    pos_years_always = int(results[results["name"] == "always_buy_top10"]["positive_years"].values[0]) if len(always_ic) > 0 else 0
    total_years_always = int(results[results["name"] == "always_buy_top10"]["years"].values[0]) if len(always_ic) > 0 else 0

    degrade_lift = (ignore_val - degrade_val) if ignore_val is not None and degrade_val is not None else None
    ignore_vs_baseline = (ignore_val - all_rows_ic_val) if ignore_val is not None and all_rows_ic_val is not None else None

    if degrade_lift is not None and degrade_lift > 0.01 and pos_years_ignore >= total_years_ignore * 0.6:
        decision = "PASSED"
    elif degrade_lift is not None and degrade_lift > 0.005 and pos_years_ignore >= total_years_ignore * 0.5:
        decision = "MIXED"
    elif degrade_lift is not None and degrade_lift > 0.002:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "all_rows_avg_ic": all_rows_ic_val,
            "always_buy_top10_avg_ic": always_val,
            "always_buy_top10_pos_years": f"{pos_years_always}/{total_years_always}",
            "ignore_degrade_avg_ic": ignore_val,
            "ignore_degrade_pos_years": f"{pos_years_ignore}/{total_years_ignore}",
            "degrade_buy_avg_ic": degrade_val,
            "degrade_lift_ignore_vs_buy": degrade_lift,
            "ignore_vs_baseline_lift": ignore_vs_baseline,
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
    print(f"\nDegrade state: ignore={ignore_val}, always={degrade_val}, lift={degrade_lift}")
    print(f"Always-buy top10: {always_val} ({pos_years_always}/{total_years_always} pos years)")
    print(f"Decision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()