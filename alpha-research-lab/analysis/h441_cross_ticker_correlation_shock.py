"""
H441: cross_ticker_correlation_shock (date-level version)

Hypothesis: When market-level cross-sectional correlation drops (stocks less aligned
with each other), individual stock IC may change. Test whether date-level correlation
regime (high vs low cross-sectional stock correlation) predicts forward IC.

Mechanism: For each date, compute cross-sectional Spearman correlation between
S1 scores and returns. Flag high-corr vs low-corr dates. Test whether S1 IC differs
by date-level correlation regime.

Test: Uses existing S1 features and returns. Compare against random baselines.
Fast date-level computation, no per-ticker rolling.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import pandas as pd
import numpy as np
from scipy.stats import spearmanr

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


BRANCH_NAME = "h441_cross_ticker_correlation_shock"
MODE = "research_branch"

SPEC = ExperimentSpec(
    name=BRANCH_NAME,
    mode=MODE,
    hypothesis=(
        "When market-level cross-sectional correlation drops (stocks less aligned), "
        "individual stock IC may change. Compute date-level cross-sectional correlation "
        "between S1 scores and returns. Flag high vs low corr dates. Test whether S1 IC "
        "differs by date-level correlation regime. Fast date-level computation."
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
    StateSpec("high_corr_date", "High cross-sectional correlation dates (Q5)", family="corr_regime"),
    StateSpec("low_corr_date", "Low cross-sectional correlation dates (Q1)", family="corr_regime"),
    StateSpec("high_corr_strong_flow", "High corr date + strong C16 flow", family="combined"),
    StateSpec("low_corr_strong_flow", "Low corr date + strong C16 flow", family="combined"),
    StateSpec("high_corr_first_news", "High corr date + first-in-5d news", family="combined2"),
    StateSpec("low_corr_first_news", "Low corr date + first-in-5d news", family="combined2"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H441 cross_ticker_correlation_shock")
    parser.add_argument("--s1-path", type=str, default=str(S1_DEFAULT_PATH))
    parser.add_argument("--start-year", type=int, default=SPEC.start_year)
    parser.add_argument("--end-year", type=int, default=SPEC.end_year)
    parser.add_argument("--min-year-rows", type=int, default=SPEC.min_year_rows)
    parser.add_argument("--min-phase-rows", type=int, default=SPEC.min_phase_rows)
    return parser.parse_args()


def compute_returns(df):
    df = df.sort_values(["ticker", "time"])
    for lag in range(1, 6):
        shifted = df.groupby("ticker")[S1_SCORE_COL].shift(lag)
        df[f"ret_lag_{lag}"] = df[S1_SCORE_COL] - shifted
    ret_cols = [f"ret_lag_{lag}" for lag in range(1, 6)]
    df["ret_5d"] = df[ret_cols].mean(axis=1)
    return df


def date_level_corr(panel):
    date_corrs = []
    for time, grp in panel.groupby("time"):
        scores = grp[S1_SCORE_COL].values
        rets = grp["ret_5d"].values
        if len(scores) >= 20 and np.std(scores) > 1e-9 and np.std(rets) > 1e-9:
            corr, _ = spearmanr(scores, rets)
        else:
            corr = 0.0
        date_corrs.append({"time": time, "date_corr": corr})
    return pd.DataFrame(date_corrs)


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
    panel = panel.dropna(subset=["c16"])

    panel = compute_returns(panel)

    print("Computing date-level cross-sectional correlations...")
    date_corrs = date_level_corr(panel)
    print(f"Computed {len(date_corrs)} date-level correlations.")

    panel = panel.merge(date_corrs, on="time", how="left")
    panel["date_corr"] = panel["date_corr"].fillna(0)

    q5_corr = panel["date_corr"].quantile(0.80)
    panel["high_corr_date"] = panel["date_corr"] > q5_corr
    q1_corr = panel["date_corr"].quantile(0.20)
    panel["low_corr_date"] = panel["date_corr"] < q1_corr

    panel["strong_flow"] = panel["c16"] > panel.groupby("time")["c16"].transform(
        lambda x: x.quantile(0.75)
    )
    panel["high_corr_strong_flow"] = panel["high_corr_date"] & panel["strong_flow"]
    panel["low_corr_strong_flow"] = panel["low_corr_date"] & panel["strong_flow"]

    news_cols = ["date", "ticker", "phobert_article_count_1d", "phobert_article_count_5d"]
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

    prior_5d_news = panel.groupby("ticker")["article_count_1d"].transform(
        lambda x: x.shift().rolling(5, min_periods=1).sum().fillna(0)
    )
    panel["prior_5d_news"] = prior_5d_news
    panel["first_in_5d"] = (panel["article_count_1d"] > 0) & (panel["prior_5d_news"] == 0)

    panel["high_corr_first_news"] = panel["high_corr_date"] & panel["first_in_5d"]
    panel["low_corr_first_news"] = panel["low_corr_date"] & panel["first_in_5d"]

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

    hc_ic = results[results["name"] == "high_corr_date"]["avg_ic"].values
    hc_val = float(hc_ic[0]) if len(hc_ic) > 0 else None
    hc_rows = int(results[results["name"] == "high_corr_date"]["pooled_rows"].values[0]) if len(hc_ic) > 0 else 0
    hc_pos = int(results[results["name"] == "high_corr_date"]["positive_years"].values[0]) if len(hc_ic) > 0 else 0
    hc_total = int(results[results["name"] == "high_corr_date"]["years"].values[0]) if len(hc_ic) > 0 else 0

    lc_ic = results[results["name"] == "low_corr_date"]["avg_ic"].values
    lc_val = float(lc_ic[0]) if len(lc_ic) > 0 else None
    lc_rows = int(results[results["name"] == "low_corr_date"]["pooled_rows"].values[0]) if len(lc_ic) > 0 else 0

    hcf_ic = results[results["name"] == "high_corr_strong_flow"]["avg_ic"].values
    hcf_val = float(hcf_ic[0]) if len(hcf_ic) > 0 else None
    lcf_ic = results[results["name"] == "low_corr_strong_flow"]["avg_ic"].values
    lcf_val = float(lcf_ic[0]) if len(lcf_ic) > 0 else None

    hcfirst_ic = results[results["name"] == "high_corr_first_news"]["avg_ic"].values
    hcfirst_val = float(hcfirst_ic[0]) if len(hcfirst_ic) > 0 else None
    lcfirst_ic = results[results["name"] == "low_corr_first_news"]["avg_ic"].values
    lcfirst_val = float(lcfirst_ic[0]) if len(lcfirst_ic) > 0 else None

    hc_vs_lc = (hc_val - lc_val) if hc_val is not None and lc_val is not None else None

    if hc_vs_lc is not None and abs(hc_vs_lc) > 0.01 and hc_pos >= hc_total * 0.6:
        if hc_vs_lc > 0:
            decision = "PASSED"
        else:
            decision = "MIXED"
    elif hc_vs_lc is not None and abs(hc_vs_lc) > 0.005:
        decision = "MIXED"
    else:
        decision = "FAILED"

    summary_path = context.write_summary(
        summary={
            "decision": decision,
            "panel_rows": int(len(panel)),
            "all_rows_avg_ic": all_rows_ic_val,
            "high_corr_date_avg_ic": hc_val,
            "high_corr_date_rows": hc_rows,
            "high_corr_date_pos_years": f"{hc_pos}/{hc_total}",
            "low_corr_date_avg_ic": lc_val,
            "low_corr_date_rows": lc_rows,
            "hc_vs_lc_lift": hc_vs_lc,
            "high_corr_strong_flow_avg_ic": hcf_val,
            "low_corr_strong_flow_avg_ic": lcf_val,
            "high_corr_first_news_avg_ic": hcfirst_val,
            "low_corr_first_news_avg_ic": lcfirst_val,
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
    print(f"\nHigh corr date IC: {hc_val} ({hc_pos}/{hc_total} pos years, {hc_rows} rows)")
    print(f"Low corr date IC: {lc_val} ({lc_rows} rows)")
    print(f"High vs Low lift: {hc_vs_lc}")
    print(f"High+Flow: {hcf_val}, Low+Flow: {lcf_val}")
    print(f"High+FirstNews: {hcfirst_val}, Low+FirstNews: {lcfirst_val}")
    print(f"Decision: {decision}")
    print(f"Summary: {summary_path}")
    return summary_path


def main() -> None:
    run_branch(parse_args())


if __name__ == "__main__":
    main()